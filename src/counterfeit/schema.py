"""FICN role->column map: the counterfeit-currency-circulation re-point.

This is the reframe made literal (CLAUDE.md §3, row 1). The vendored engine's
ring injector is parameterised by a `Schema` -- an abstract role -> column map --
so the SAME controlled-injection machinery that ran on Sparkov card data and on
scam-incident data (`src.engine.scam_schema.SCAM`) runs on counterfeit-currency
*circulation* data with nothing but a third role map.

The ring semantics carry over exactly. On Sparkov: many distinct cards fanning
into one merchant. For scam mules: many distinct victims paying one mule
`payee_upi`. For FICN: many distinct *seizure records* carrying one reused plate
`serial` -- the duplicate-serial signature of a single print operation, the
individuating hard link two seizures share. We do NOT do note-image CV here (a
separate vision problem, out of scope by design); this is the intelligence half
-- linking counterfeit circulation into the same court-admissible ring evidence.

Only the five required roles are set (no category column, no location quad), so
`supported_typologies() -> {ring, velocity, temporal}` exactly as SCAM -- ring is
the slot the circulation graph is built on.
"""
from __future__ import annotations

from src.engine.schema import Schema

FICN = Schema(
    entity="seizure",         # the many seizure records that fan in
    target="serial",          # the reused counterfeit plate serial they converge on
    time="timestamp",         # seizure time
    amount="face_value",      # fake face value recovered in the seizure
    label="is_counterfeit",   # answer-key flag
)
