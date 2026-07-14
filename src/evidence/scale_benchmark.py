"""Scale benchmark -- wall-clock timing of the pipeline (generate -> build_graph
-> detect_rings -> rank_kingpins) as the network grows, so the deck's scale
claim is a measured number (CLAUDE.md §17: no asserted numbers), not a guess.

Two knobs matter differently, and the sweep varies both so neither cost hides:
`n_victims` (legit background) drives build_graph's node/edge count linearly,
but barely touches detect_rings/rank_kingpins once the legit hub and the
common-merchant pool are excluded as hubs (`rings.hub_nodes`, degree >
hub_degree_cap) -- at scale almost every legit identifier node clears that
bar, so legit incidents fall out as singletons before ring detection even
runs. `n_rings` drives `ring_union_graph`, the (much smaller) subgraph
`rank_kingpins` actually runs centrality on -- betweenness_centrality
(Brandes' algorithm, O(V*E)) is the dominant per-call cost there, so scaling
rings independently of the legit background is what stresses Layer 2.

`python -m src.evidence.scale_benchmark` regenerates the deck's scale numbers
from scratch and writes data/processed/scale_benchmark.json + assets/scale_benchmark.png.
"""
from __future__ import annotations

import time
from dataclasses import dataclass
from pathlib import Path

from src.evidence.validate import DEMO_HUB_DEGREE_CAP

# The first point mirrors the demo network's own background (n_victims=500), and
# every point stays above it -- below ~270 victims a common merchant's degree
# falls under DEMO_HUB_DEGREE_CAP (0.6 legit share / 4 payees = 0.15 each), the
# cap stops excluding it, and its legit fan-in shows up as a spurious "ring".
# That is a real small-scale artifact of connected-component clustering, not a
# benchmark bug, but it would corrupt the n_rings_detected column.
DEFAULT_SWEEP: list[dict] = [
    {"n_victims": 500, "n_rings": 6},
    {"n_victims": 1_000, "n_rings": 20},
    {"n_victims": 5_000, "n_rings": 50},
    {"n_victims": 20_000, "n_rings": 100},
    {"n_victims": 50_000, "n_rings": 150},
]


@dataclass(frozen=True)
class ScaleBenchmarkRun:
    n_victims: int
    n_rings: int
    cards_per_ring: int
    n_reports: int
    n_graph_nodes: int
    n_graph_edges: int
    n_rings_detected: int
    generate_seconds: float
    build_graph_seconds: float
    detect_rings_seconds: float
    rank_kingpins_seconds: float

    @property
    def total_seconds(self) -> float:
        return round(
            self.generate_seconds + self.build_graph_seconds
            + self.detect_rings_seconds + self.rank_kingpins_seconds, 4,
        )

    def to_dict(self) -> dict:
        return {
            "n_victims": self.n_victims,
            "n_rings": self.n_rings,
            "cards_per_ring": self.cards_per_ring,
            "n_reports": self.n_reports,
            "n_graph_nodes": self.n_graph_nodes,
            "n_graph_edges": self.n_graph_edges,
            "n_rings_detected": self.n_rings_detected,
            "generate_seconds": self.generate_seconds,
            "build_graph_seconds": self.build_graph_seconds,
            "detect_rings_seconds": self.detect_rings_seconds,
            "rank_kingpins_seconds": self.rank_kingpins_seconds,
            "total_seconds": self.total_seconds,
        }


def benchmark_at_scale(
    n_victims: int,
    n_rings: int,
    cards_per_ring: int = 4,
    kingpin_ring_count: int = 0,
    hub_degree_cap: int = DEMO_HUB_DEGREE_CAP,
    seed: int = 0,
) -> ScaleBenchmarkRun:
    """One timed pass at a given network size. Imports live here, not at
    module top, matching validate.py's `validate_seed` convention -- keeps
    this a `src.generate` dependency only for the callers that need it.

    `kingpin_ring_count=0` because the kingpin is a story element, not a cost
    driver, and at these uniform ring sizes it would corrupt the
    `n_rings_detected` sanity column for a reason that says nothing about
    latency: a bridge phone shared by `kingpin_ring_count * cards_per_ring`
    incidents (12, at the sweep's defaults) sits well UNDER the hub cap, so
    Layer 1 treats it as an ordinary hard identifier -- correctly, by its own
    rule -- and merges those rings into one. The demo network avoids that by
    being large enough for the bridge to read as a hub (degree 53 > cap 40);
    see `generate_network`'s degree hierarchy."""
    from src.generate.network import generate_network
    from src.graph import build_graph, detect_rings, rank_kingpins

    t0 = time.perf_counter()
    # Uniform rings here on purpose: this sweep measures how cost scales with
    # ring COUNT, so holding each ring the same size keeps the two knobs
    # independent. The demo's own network is deliberately non-uniform
    # (`generate_network`'s DEMO_RING_SIZES) -- a different question.
    reports = generate_network(
        n_victims=n_victims, ring_sizes=(cards_per_ring,) * n_rings,
        kingpin_ring_count=kingpin_ring_count, seed=seed,
    )
    t1 = time.perf_counter()
    g = build_graph(reports)
    t2 = time.perf_counter()
    rings = detect_rings(g, hub_degree_cap=hub_degree_cap)
    t3 = time.perf_counter()
    rank_kingpins(g, rings)
    t4 = time.perf_counter()

    return ScaleBenchmarkRun(
        n_victims=n_victims,
        n_rings=n_rings,
        cards_per_ring=cards_per_ring,
        n_reports=len(reports),
        n_graph_nodes=g.number_of_nodes(),
        n_graph_edges=g.number_of_edges(),
        n_rings_detected=len(rings),
        generate_seconds=round(t1 - t0, 4),
        build_graph_seconds=round(t2 - t1, 4),
        detect_rings_seconds=round(t3 - t2, 4),
        rank_kingpins_seconds=round(t4 - t3, 4),
    )


def run_sweep(configs: list[dict] = DEFAULT_SWEEP, **common_kwargs) -> list[ScaleBenchmarkRun]:
    return [benchmark_at_scale(**cfg, **common_kwargs) for cfg in configs]


def _write_scale_figure(runs: list[ScaleBenchmarkRun], path: Path) -> None:
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    n = [r.n_reports for r in runs]
    fig, ax = plt.subplots(figsize=(8, 4.5))
    ax.plot(n, [r.build_graph_seconds for r in runs], marker="o", label="build_graph")
    ax.plot(n, [r.detect_rings_seconds for r in runs], marker="s", label="detect_rings")
    ax.plot(n, [r.rank_kingpins_seconds for r in runs], marker="^", label="rank_kingpins")
    ax.plot(n, [r.total_seconds for r in runs], marker="D", label="total (incl. generation)",
            linewidth=2, color="black")
    ax.set_xlabel("reports in the network")
    ax.set_ylabel("wall-clock seconds")
    ax.set_title("Pipeline latency vs network size (single run, this machine)")
    ax.legend()
    fig.tight_layout()
    path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(path, dpi=200)
    plt.close(fig)


def main(
    configs: list[dict] = DEFAULT_SWEEP,
    out_path: Path = Path("data/processed/scale_benchmark.json"),
    figure_path: Path = Path("assets/scale_benchmark.png"),
) -> dict:
    """Regenerates the deck's scale numbers from scratch (CLAUDE.md §17: no
    asserted numbers). Writes the JSON artifact + the latency-vs-size figure
    and returns the dict so notebooks can reuse it."""
    import json

    from src.evidence.pack import _code_version

    runs = run_sweep(configs)
    result = {
        "generated_by": "python -m src.evidence.scale_benchmark",
        "code_version": _code_version(),
        "hub_degree_cap": DEMO_HUB_DEGREE_CAP,
        "runs": [r.to_dict() for r in runs],
    }

    _write_scale_figure(runs, figure_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(result, indent=2), encoding="utf-8")
    print(json.dumps(result, indent=2))
    print(f"wrote {out_path} and {figure_path}")
    return result


if __name__ == "__main__":
    main()
