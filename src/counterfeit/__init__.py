"""Counterfeit-currency circulation intelligence -- the FICN re-point.

The note-image CV (the counterfeit-detection *accuracy* line) is out of scope by
design (CLAUDE.md §3 row 1): a real number there needs a labelled genuine-vs-fake
dataset we will not fabricate. This package is the *intelligence* half the brief
also asks for -- linking counterfeit circulation (reused plate serials, courier
accounts) into the same deterministic ring evidence the scam side produces, by
re-pointing the engine's `Schema` to FICN roles and reusing the entire Link/Prove
pipeline unchanged.
"""
from __future__ import annotations

from src.counterfeit.generate import (
    FICN_HUB_DEGREE_CAP,
    FICN_KINGPIN_RING_COUNT,
    FICN_RING_SIZES,
    SeizureRecord,
    generate_seizures,
)
from src.counterfeit.graph import build_seizure_graph
from src.counterfeit.schema import FICN
from src.counterfeit.validate import (
    sample_evidence_pack,
    validate_across_seeds,
    validate_seed,
)

__all__ = [
    "FICN",
    "FICN_HUB_DEGREE_CAP",
    "FICN_KINGPIN_RING_COUNT",
    "FICN_RING_SIZES",
    "SeizureRecord",
    "generate_seizures",
    "build_seizure_graph",
    "sample_evidence_pack",
    "validate_across_seeds",
    "validate_seed",
]
