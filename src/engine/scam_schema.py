"""Night's Watch role->column map for the scam-incident graph.

The vendored engine (``inject_ring`` / ``RingSAGE``) is parameterised by a
``Schema`` — an abstract role -> real column-name map — so the SAME ring-detection
machinery that ran on Sparkov card data runs on scam-incident data unchanged. The
engine's ``SPARKOV`` maps card-transaction columns; ``SCAM`` (here) maps the
columns Night's Watch builds its synthetic scam network on.

Ring semantics carry over directly. On Sparkov the ring is *many distinct cards
(entity) fanning into one merchant (target) inside a time window*. For scam mules
it is *many distinct victims (entity) paying into one shared mule payee_upi
(target) inside a window* — the shared payee is the fan-in hub `RingSAGE` scores.

Only the five REQUIRED roles are set. With no ``category`` column and no location
quad, ``supported_typologies()`` -> {ring, velocity, temporal}; geo/category stay
Sparkov-only (as documented in the engine adapters). Ring is the slot the kingpin
graph is built on.
"""
from __future__ import annotations

from src.engine.schema import Schema

SCAM = Schema(
    entity="victim",       # the many that fan in   (one report / victim each)
    target="payee_upi",    # the shared mule hub they converge on
    time="timestamp",      # incident time — windowed fan-in needs continuous time
    amount="amount",       # amount demanded / transferred
    label="is_scam",       # answer-key flag
)
