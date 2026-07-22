"""Answer-key validation for counterfeit-circulation detection -- the same
"prove it, don't assert it" pass the scam network gets (`src.evidence.validate`),
run on the FICN world.

The claim this produces is deliberately the same SHAPE as G6's ring-recovery
number, and carries the same caveat: planted rings are clean by construction, so
a perfect score means the method recovers the PLANTED answer key across
independent seeds -- NOT a real-world counterfeit-detection accuracy (there is no
labelled FICN-circulation corpus to measure that against, and we do not fake
one). What it demonstrates is that the identical Layer 1 / Layer 2 machinery,
re-pointed to FICN roles, recovers a counterfeit circulation ring and its
launderer, and emits the same court-admissible evidence pack.

`python -m src.counterfeit.validate` regenerates the number from scratch and
writes data/processed/ficn_validation.json + a sample evidence pack.
"""
from __future__ import annotations

import json
from pathlib import Path

from src.counterfeit.generate import (
    FICN_HUB_DEGREE_CAP,
    FICN_KINGPIN_RING_COUNT,
    FICN_RING_SIZES,
    generate_seizures,
)
from src.counterfeit.graph import build_seizure_graph
from src.evidence.pack import _code_version, build_evidence_pack
from src.evidence.validate import (
    MultiSeedValidation,
    SeedValidation,
    kingpin_rank,
    pairwise_precision_recall,
)
from src.graph import detect_rings, rank_kingpins


def validate_seed(seed: int, *, hub_degree_cap: int | None = FICN_HUB_DEGREE_CAP) -> SeedValidation:
    """One full answer-key pass: generate the seeded FICN network, build the
    graph, detect rings at `hub_degree_cap`, score ring recovery pairwise, and
    rank the kingpin -- reusing the scam pipeline's own scorers unchanged."""
    seizures = generate_seizures(seed=seed)
    g = build_seizure_graph(seizures)
    rings = detect_rings(g, hub_degree_cap=hub_degree_cap)
    precision, recall, f1 = pairwise_precision_recall(seizures, rings)
    scores = rank_kingpins(g, rings)
    rank = kingpin_rank(scores, g, seizures)
    return SeedValidation(seed, len(rings), precision, recall, f1, rank)


def validate_across_seeds(
    n_seeds: int = 20, *, hub_degree_cap: int | None = FICN_HUB_DEGREE_CAP,
) -> MultiSeedValidation:
    if n_seeds < 1:
        raise ValueError("n_seeds must be >= 1")
    runs = [validate_seed(seed, hub_degree_cap=hub_degree_cap) for seed in range(n_seeds)]
    return MultiSeedValidation(hub_degree_cap, runs)


def sample_evidence_pack(seed: int = 0):
    """Build the Layer 1 evidence pack for the largest detected circulation ring
    -- the same `build_evidence_pack` the scam side uses, proving the admissible
    output is the identical machinery (only the incident noun differs)."""
    seizures = generate_seizures(seed=seed)
    g = build_seizure_graph(seizures)
    rings = detect_rings(g, hub_degree_cap=FICN_HUB_DEGREE_CAP)
    by_id = {s.report_id: s for s in seizures}
    pack = build_evidence_pack(rings[0], g, by_id, incident_noun="seizure records")
    return rings[0], pack


def main(
    n_seeds: int = 20,
    out_path: Path = Path("data/processed/ficn_validation.json"),
    pack_path: Path = Path("data/processed/ficn_evidence_pack.md"),
) -> dict:
    multi = validate_across_seeds(n_seeds)
    ring, pack = sample_evidence_pack(seed=0)

    result = {
        "generated_by": "python -m src.counterfeit.validate",
        "code_version": _code_version(),
        "domain": "counterfeit_currency_circulation",
        "caveat": "recovers the planted answer key across seeds; not a real-world "
                  "counterfeit-detection accuracy. Note-image CV is out of scope by "
                  "design -- this is the circulation-intelligence half.",
        "hub_degree_cap": FICN_HUB_DEGREE_CAP,
        "ring_sizes": list(FICN_RING_SIZES),
        "kingpin_ring_count": FICN_KINGPIN_RING_COUNT,
        "multi_seed": multi.to_dict(),
        "sample_ring": {
            "ring_id": ring.ring_id,
            "n_seizures": ring.size,
            "shared_identifiers": len(pack.shared_identifiers),
            "content_sha256": pack.content_sha256,
            "certificate_statute": pack.certificate["statute"],
        },
        "evidence_pack_markdown": pack_path.as_posix(),
    }

    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(result, indent=2), encoding="utf-8")
    pack_path.write_text(pack.to_markdown(), encoding="utf-8")
    print(json.dumps(result, indent=2))
    print(f"wrote {out_path} and {pack_path}")
    return result


if __name__ == "__main__":
    main()
