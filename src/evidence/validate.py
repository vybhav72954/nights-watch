"""Answer-key validation: precision/recall of ring recovery + kingpin
hit-rate against the planted `_gt` (docs/SOLUTION_DESIGN.md §4). This is the
"we can *prove* it, not just assert it" slide, and it's what the demo's
threshold slider is actually plotting.

Precision/recall is computed pairwise over incidents (standard clustering
evaluation): for every pair of reports, "linked" means the same detected
ring; "should be linked" means the same planted `_gt.ring_id`. FDR /
correlated-trait correction is explicitly cut (CLAUDE.md §8) -- this stays a
plain, auditable pair count.

`python -m src.evidence.validate` regenerates the deck's slide-8 numbers
from scratch: a multi-seed robustness sweep (kingpin top-1 rate + ring P/R
mean/sd over independently seeded networks) and the threshold-slider curve,
written to data/processed/validation.json + assets/pr_curve.png.
"""
from __future__ import annotations

import statistics
from dataclasses import dataclass
from itertools import combinations
from pathlib import Path

import networkx as nx

from src.graph import KingpinScore, detect_rings
from src.graph.rings import Ring
from src.schema import Report

# The cap the demo runs at. It has to sit inside the seeded world's degree
# hierarchy (`src.generate.network.generate_network` documents it in full):
#
#   largest ring (30) < CAP (40) < kingpin phone (53) < merchants (~75) < hub (~200)
#
# so Layer 1 keeps every ring whole -- each ring's own mule UPI stays under the
# cap -- while the cross-ring bridge, the popular merchants and the legit hub
# are all excluded as hubs. The 10 points of slack above the largest ring are
# live headroom: each report a judge sends that names `mule00@okaxis` adds 1 to
# its degree, and at 41 Layer 1 would drop the ring off the screen mid-demo.
DEMO_HUB_DEGREE_CAP = 40

# Sweep for the slider curve. Three regimes, and both failure ends are meant to
# be visible -- that is what shows the 1.0s in the middle aren't rigged:
#   5-20  too strict: the cap excludes the bigger rings' own mule UPIs, so those
#         rings are never recovered at all (recall collapses, precision stays
#         1.0 only because what little is claimed is still correct)
#   30-50 the working band: every ring recovered, nothing false (P = R = 1.0)
#   60    re-admits the kingpin phone (53), which fuses its three rings into one
#   80    re-admits the common merchants (~75), each a false ring of legit traffic
#   None  the legit hub (~200) fuses nearly everything: precision -> ~0
DEFAULT_CURVE_CAPS: list[int | None] = [5, 10, 20, 30, 40, 50, 60, 80, None]


def _predicted_ring_of(rings: list[Ring]) -> dict[str, str]:
    return {inc.split(":", 1)[1]: r.ring_id for r in rings for inc in r.incident_ids}


def _true_ring_of(reports: list[Report]) -> dict[str, str | None]:
    return {r.report_id: (r.gt.ring_id if r.gt else None) for r in reports}


@dataclass(frozen=True)
class PairwiseScore:
    hub_degree_cap: int | None
    n_rings: int
    precision: float
    recall: float
    f1: float

    def to_dict(self) -> dict:
        return {
            "hub_degree_cap": self.hub_degree_cap, "n_rings": self.n_rings,
            "precision": self.precision, "recall": self.recall, "f1": self.f1,
        }


def pairwise_precision_recall(reports: list[Report], rings: list[Ring]) -> tuple[float, float, float]:
    predicted = _predicted_ring_of(rings)
    truth = _true_ring_of(reports)
    report_ids = [r.report_id for r in reports]

    tp = fp = fn = 0
    for a, b in combinations(report_ids, 2):
        same_pred = a in predicted and b in predicted and predicted[a] == predicted[b]
        same_true = truth.get(a) is not None and truth.get(a) == truth.get(b)
        if same_pred and same_true:
            tp += 1
        elif same_pred and not same_true:
            fp += 1
        elif same_true and not same_pred:
            fn += 1

    precision = tp / (tp + fp) if (tp + fp) else 1.0
    recall = tp / (tp + fn) if (tp + fn) else 1.0
    f1 = 2 * precision * recall / (precision + recall) if (precision + recall) else 0.0
    return round(precision, 4), round(recall, 4), round(f1, 4)


def precision_recall_curve(
    reports: list[Report], g: nx.Graph, hub_degree_caps: list[int | None], min_incidents: int = 2,
) -> list[PairwiseScore]:
    """Sweeps `hub_degree_cap` -- the one live threshold the demo slider
    controls -- and reports the resulting ring-recovery precision/recall at
    each setting."""
    curve = []
    for cap in hub_degree_caps:
        rings = detect_rings(g, min_incidents=min_incidents, hub_degree_cap=cap)
        precision, recall, f1 = pairwise_precision_recall(reports, rings)
        curve.append(PairwiseScore(cap, len(rings), precision, recall, f1))
    return curve


def _kingpin_identifier_nodes(scores: list[KingpinScore], g: nx.Graph, reports: list[Report]) -> set[str]:
    """Identifier nodes adjacent to a planted kingpin incident AND bridging
    more than one detected ring -- the cross-ring bridge a kingpin claim is
    actually about, not just that ring's own mule identifier (which would
    also neighbour the incident but says nothing about *this* incident being
    a kingpin's; CLAUDE.md B6)."""
    kingpin_incidents = {f"incident:{r.report_id}" for r in reports if r.gt and r.gt.is_kingpin_incident}
    neighbours = {nb for inc in kingpin_incidents if inc in g for nb in g.neighbors(inc)}
    node_ring_ids = {s.node: s.ring_ids for s in scores}
    return {n for n in neighbours if len(node_ring_ids.get(n, ())) > 1}


def kingpin_rank(scores: list[KingpinScore], g: nx.Graph, reports: list[Report]) -> int | None:
    """1-indexed rank of the first ranked node that is a planted kingpin
    identifier, or `None` if none of `scores` are."""
    targets = _kingpin_identifier_nodes(scores, g, reports)
    if not targets:
        return None
    for i, s in enumerate(scores, start=1):
        if s.node in targets:
            return i
    return None


def kingpin_hit_rate(scores: list[KingpinScore], g: nx.Graph, reports: list[Report], k: int = 1) -> bool:
    rank = kingpin_rank(scores, g, reports)
    return rank is not None and rank <= k


@dataclass(frozen=True)
class SeedValidation:
    seed: int
    n_rings: int
    precision: float
    recall: float
    f1: float
    kingpin_rank: int | None

    def to_dict(self) -> dict:
        return {
            "seed": self.seed, "n_rings": self.n_rings,
            "precision": self.precision, "recall": self.recall, "f1": self.f1,
            "kingpin_rank": self.kingpin_rank,
        }


@dataclass(frozen=True)
class MultiSeedValidation:
    """Answer-key validation repeated over independently seeded networks --
    the difference between "it worked on our demo seed" and a robustness
    claim (deck slide 8). Every seed regenerates the network, the graph, the
    rings, and the kingpin ranking from scratch."""
    hub_degree_cap: int | None
    runs: list[SeedValidation]

    @property
    def n_seeds(self) -> int:
        return len(self.runs)

    @property
    def kingpin_top1_hits(self) -> int:
        return sum(1 for r in self.runs if r.kingpin_rank == 1)

    @property
    def kingpin_top1_rate(self) -> float:
        return round(self.kingpin_top1_hits / self.n_seeds, 4) if self.runs else 0.0

    def _mean_sd(self, values: list[float]) -> tuple[float, float]:
        sd = statistics.stdev(values) if len(values) > 1 else 0.0
        return round(statistics.mean(values), 4), round(sd, 4)

    def to_dict(self) -> dict:
        p_mean, p_sd = self._mean_sd([r.precision for r in self.runs])
        r_mean, r_sd = self._mean_sd([r.recall for r in self.runs])
        return {
            "hub_degree_cap": self.hub_degree_cap,
            "n_seeds": self.n_seeds,
            "kingpin_top1_hits": self.kingpin_top1_hits,
            "kingpin_top1_rate": self.kingpin_top1_rate,
            "kingpin_ranks": [r.kingpin_rank for r in self.runs],
            "precision_mean": p_mean, "precision_sd": p_sd,
            "recall_mean": r_mean, "recall_sd": r_sd,
            "runs": [r.to_dict() for r in self.runs],
        }


def validate_seed(
    seed: int, *, hub_degree_cap: int | None = DEMO_HUB_DEGREE_CAP, **network_kwargs,
) -> SeedValidation:
    """One full answer-key validation pass: generate the seeded network,
    build the graph, detect rings at `hub_degree_cap`, score ring recovery
    pairwise, and rank kingpins. Imports live here, not at module top, to
    keep this library module free of a src.generate dependency for its
    ordinary callers (the app's slider endpoint only needs the functions
    above)."""
    from src.generate.network import generate_network
    from src.graph import build_graph, rank_kingpins

    reports = generate_network(seed=seed, **network_kwargs)
    g = build_graph(reports)
    rings = detect_rings(g, hub_degree_cap=hub_degree_cap)
    precision, recall, f1 = pairwise_precision_recall(reports, rings)
    scores = rank_kingpins(g, rings)
    rank = kingpin_rank(scores, g, reports)
    return SeedValidation(seed, len(rings), precision, recall, f1, rank)


def validate_across_seeds(
    n_seeds: int = 20, *, hub_degree_cap: int | None = DEMO_HUB_DEGREE_CAP, **network_kwargs,
) -> MultiSeedValidation:
    if n_seeds < 1:
        raise ValueError("n_seeds must be >= 1")
    runs = [validate_seed(seed, hub_degree_cap=hub_degree_cap, **network_kwargs) for seed in range(n_seeds)]
    return MultiSeedValidation(hub_degree_cap, runs)


def _write_pr_curve_figure(curve: list[PairwiseScore], path: Path) -> None:
    """The slide-8 / demo-slider figure: precision and recall vs
    hub_degree_cap. Caps are plotted categorically (they're a slider's
    detents, not a continuous axis); None renders as "no cap"."""
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    positions = range(len(curve))
    labels = ["no cap" if s.hub_degree_cap is None else str(s.hub_degree_cap) for s in curve]
    fig, ax = plt.subplots(figsize=(8, 4.5))
    ax.plot(positions, [s.precision for s in curve], marker="o", label="precision")
    ax.plot(positions, [s.recall for s in curve], marker="s", label="recall")
    if DEMO_HUB_DEGREE_CAP in [s.hub_degree_cap for s in curve]:
        demo_pos = [s.hub_degree_cap for s in curve].index(DEMO_HUB_DEGREE_CAP)
        ax.axvline(demo_pos, color="grey", linestyle="--", linewidth=1)
        ax.annotate("demo setting", (demo_pos, 0.5), textcoords="offset points",
                    xytext=(6, 0), fontsize=9, color="grey")
    ax.set_xticks(list(positions), labels)
    ax.set_xlabel("hub degree cap (the demo threshold slider)")
    ax.set_ylabel("pairwise ring-recovery score")
    ax.set_ylim(-0.05, 1.05)
    ax.set_title("Ring recovery vs hub-degree cap: seeded answer-key network (seed 0)")
    ax.legend()
    fig.tight_layout()
    path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(path, dpi=200)
    plt.close(fig)


def main(
    n_seeds: int = 20,
    curve_caps: list[int | None] = DEFAULT_CURVE_CAPS,
    out_path: Path = Path("data/processed/validation.json"),
    figure_path: Path = Path("assets/pr_curve.png"),
) -> dict:
    """Regenerates every slide-8 number from scratch (CLAUDE.md §17: no
    asserted numbers -- every quantitative deck claim must be produced by
    code in this repo). Writes the JSON artifact + the P/R curve figure and
    returns the dict so notebooks can reuse it."""
    import inspect
    import json

    from src.evidence.pack import _code_version
    from src.generate.network import generate_network
    from src.graph import build_graph

    multi_seed = validate_across_seeds(n_seeds)
    reports = generate_network(seed=0)
    g = build_graph(reports)
    curve = precision_recall_curve(reports, g, hub_degree_caps=curve_caps)

    # Record the exact network parameters the claim was measured under --
    # pulled from generate_network's own signature so this can't drift.
    network_params = {
        name: p.default for name, p in inspect.signature(generate_network).parameters.items()
        if p.default is not inspect.Parameter.empty and name != "seed"
    }
    result = {
        "generated_by": "python -m src.evidence.validate",
        "code_version": _code_version(),
        "network_params": network_params,
        "multi_seed": multi_seed.to_dict(),
        "curve": {"seed": 0, "points": [s.to_dict() for s in curve]},
        "figure": figure_path.as_posix(),
    }

    _write_pr_curve_figure(curve, figure_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(result, indent=2), encoding="utf-8")
    print(json.dumps({k: v for k, v in result.items() if k != "curve"}, indent=2))
    print(f"wrote {out_path} and {figure_path}")
    return result


if __name__ == "__main__":
    main()
