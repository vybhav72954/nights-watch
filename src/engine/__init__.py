"""Vendored subset of the cross-border-fraud engine, adapted for Night's Watch.

Source: https://github.com/vybhav72954/cross-border-fraud  (local dir: cross-border-credit)
Vendored at commit a5d5fb7 (2026-06-29, branch feat/ssm). See ``PROVENANCE.md``.

**Copied, not referenced.** Night's Watch stays self-contained (one clonable repo)
and never edits the source engine, so the engine's byte-identical Sparkov invariant
is untouched. The only change to the copied files is the intra-package import
(``from src.schema`` -> ``from src.engine.schema``).

``RingSAGE`` / ``SnapshotRingSAGE`` (in ``.gnn``) need torch + torch-geometric, so
they are intentionally NOT imported here — a bare ``import src.engine`` should not
require torch. Import them directly::

    from src.engine.gnn import RingSAGE, merchant_window_features
"""
from __future__ import annotations

from src.engine.schema import Schema, SPARKOV
from src.engine.scam_schema import SCAM
from src.engine.inject import (
    inject_ring,
    inject_velocity,
    inject_temporal,
    inject_overlap,
    build_controlled_dataset,
    legit_background,
    typology_dummies,
    is_cross_border,
    TYPOLOGY_COL,
)
from src.engine.adapters import adapt_paysim, adapt_banksim, PAYSIM_FILE

__all__ = [
    "Schema",
    "SPARKOV",
    "SCAM",
    "inject_ring",
    "inject_velocity",
    "inject_temporal",
    "inject_overlap",
    "build_controlled_dataset",
    "legit_background",
    "typology_dummies",
    "is_cross_border",
    "TYPOLOGY_COL",
    "adapt_paysim",
    "adapt_banksim",
    "PAYSIM_FILE",
]
