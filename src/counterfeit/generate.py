"""Synthetic answer-key counterfeit-circulation network -- the FICN analogue of
`src.generate.network` (CLAUDE.md §3 row 1: the counterfeit reframe, built).

Reuses the vendored engine's windowed ring injector (`inject_ring`, parameterised
by the `FICN` schema) for the fan-in structure -- K distinct seizure records
sharing one reused plate `serial` -- then, exactly as `network._plant_rings` does
for scam mules, overwrites each ring's shared serial with a fresh plate signature
and stamps a cross-ring courier account on the first `kingpin_ring_count` rings
(the launderer who banks proceeds from several print operations -- the Layer 2
bridge). The kingpin is planted the same way the scam network plants its
cross-ring mule phone: shared across MULTIPLE rings, higher-degree than any one
ring's own serial.

Every seizure carries a planted `_gt` (ring id + kingpin flag) the graph never
reads -- the same answer-key discipline as the scam corpus, so ring recovery and
the kingpin rank can be *proved* against ground truth, not asserted.

The `SeizureRecord` is deliberately NOT a scam `Report` (a currency seizure is
not a citizen scam report), but it exposes the same read surface the Link/Prove
layer already consumes -- `.report_id`, `.timestamp`, `.channel`, `.raw_text`,
`.verdict.scam_type`, `.entities.amount`, `.gt.*` -- so `detect_rings`,
`rank_kingpins`, `pairwise_precision_recall`, `kingpin_rank` and
`build_evidence_pack` all run on it unchanged. That reuse IS the reframe.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from types import SimpleNamespace

import numpy as np
import pandas as pd

from src.counterfeit.schema import FICN
from src.engine import TYPOLOGY_COL, inject_ring, legit_background
from src.engine.inject import EVENT_COL

BASE_TIME = pd.Timestamp("2026-05-01")
SPAN_DAYS = 60

# Five circulation rings, unequal on purpose (same reasoning as the scam world:
# a six-way size tie never exercises the "largest ring" path). The largest is the
# lead ring an evidence pack is demonstrated on.
FICN_RING_SIZES = (18, 11, 7, 5, 4)

# The first this-many rings are bridged by one shared courier account -- one
# launderer banking proceeds from several print operations.
FICN_KINGPIN_RING_COUNT = 2

# The degree hierarchy the hub cap must sit inside (same design as the scam
# network's cap, `src.evidence.DEMO_HUB_DEGREE_CAP`):
#
#   largest ring serial (18)  <  CAP (24)  <  courier bridge (18 + 11 = 29)
#
# so Layer 1 keeps each ring whole -- every ring's own reused serial stays under
# the cap -- while the cross-ring courier account is excluded as a hub (fan-in
# alone is not proof) and left for Layer 2 to surface as the kingpin lead.
FICN_HUB_DEGREE_CAP = 24

# Per-ring note denomination. Rs 500 dominates real FICN seizures; Rs 2000 notes
# are still counterfeited despite the 2023 withdrawal.
RING_DENOMINATIONS = (500, 2000, 500, 200, 100)

# Real FICN entry corridors (context only -- a seizure POINT is never a graph
# node; linking on a popular location would forge false edges, the same reason
# the scam graph never links on amount or url).
SEIZURE_POINTS = ("Malda", "Murshidabad", "Kolkata", "Patna", "Siliguri",
                  "Gaya", "Raxaul", "Guwahati")

_SERIAL_LETTERS = "ABCDEFGHJKLMNPQRSTUVWXYZ"  # INR serials skip I and O


def _serial_prefix(rng: np.random.Generator) -> str:
    """INR serial prefix: one numeral + two letters (e.g. `5AB`)."""
    return (f"{int(rng.integers(0, 10))}"
            f"{_SERIAL_LETTERS[int(rng.integers(0, len(_SERIAL_LETTERS)))]}"
            f"{_SERIAL_LETTERS[int(rng.integers(0, len(_SERIAL_LETTERS)))]}")


def _background_serial(rng: np.random.Generator, i: int) -> str:
    """A genuine note's unique serial: numeric part is the row index (< 10^6), so
    background serials are all distinct AND disjoint from ring serials, whose
    numeric part is drawn from [100000, 10^6). No two seizures ever share a serial
    by accident -- only a planted ring does."""
    return f"{_serial_prefix(rng)}{i:06d}"


def _fresh_ring_serial(rng: np.random.Generator) -> str:
    """The reused plate serial stamped across one ring's seizures (numeric part in
    [100000, 10^6), disjoint from background per `_background_serial`)."""
    return f"{_serial_prefix(rng)}{int(rng.integers(100_000, 1_000_000)):06d}"


@dataclass(frozen=True)
class SeizureRecord:
    """One counterfeit-currency seizure. FICN-native fields, plus the read surface
    the Link/Prove layer already consumes (via the `verdict`/`entities`/`gt`
    properties) so the existing machinery runs on it unchanged."""
    report_id: str
    timestamp: datetime
    channel: str
    raw_text: str
    denomination: int
    face_value: int
    serial: str
    courier_account: str | None
    seizure_point: str
    gt_ring_id: str | None
    gt_is_kingpin: bool

    @property
    def verdict(self) -> SimpleNamespace:
        """Duck-types `Report.verdict` for `build_evidence_pack` (reads
        `.scam_type` only). The 'type' of a seizure is its note class."""
        return SimpleNamespace(scam_type=f"counterfeit_inr{self.denomination}", is_scam=True)

    @property
    def entities(self) -> SimpleNamespace:
        """Duck-types `Report.entities` for `build_evidence_pack` (reads
        `.amount` only) -- the seizure's fake face value."""
        return SimpleNamespace(amount=self.face_value)

    @property
    def gt(self) -> SimpleNamespace:
        """Duck-types `Report.gt` for `pairwise_precision_recall` / `kingpin_rank`.
        Kept off the graph exactly as the scam `_gt` is."""
        return SimpleNamespace(ring_id=self.gt_ring_id, is_kingpin_incident=self.gt_is_kingpin)


def _legit_base(n_background: int, rng: np.random.Generator) -> pd.DataFrame:
    """One-off genuine-note recoveries: each a distinct serial, no courier
    network. These are the isolated seizures a circulation ring must be
    separated from -- they must never cluster (the false-positive story)."""
    denoms = rng.choice(RING_DENOMINATIONS, size=n_background)
    return pd.DataFrame({
        "seizure": [f"seizure{i:05d}" for i in range(n_background)],
        "serial": [_background_serial(rng, i) for i in range(n_background)],
        "timestamp": BASE_TIME + pd.to_timedelta(
            rng.integers(0, 60 * 24 * SPAN_DAYS, size=n_background), unit="m"),
        "face_value": (rng.integers(2, 40, size=n_background) * denoms).astype(float),
        "is_counterfeit": np.zeros(n_background, dtype=int),
        "denomination": denoms,
        "seizure_point": rng.choice(SEIZURE_POINTS, size=n_background),
        "courier_account": [None] * n_background,
    })


def _plant_rings(
    aug: pd.DataFrame, ring_sizes, kingpin_ring_count: int, rng: np.random.Generator,
) -> pd.DataFrame:
    """Shape the engine's uniform injected rings into the seeded FICN world: trim
    each to its target size, stamp a fresh reused plate serial, re-price to a
    real seizure face value, bridge the first `kingpin_ring_count` rings with one
    shared courier account, and place each ring's seizures over a multi-week
    window in ring order (a print operation seizes over weeks, not the injector's
    hours -- and Layer 1 links on the serial, not the time, so this is cosmetic
    for detection but honest for the evidence pack)."""
    aug = aug.copy()
    ring_mask = aug[TYPOLOGY_COL] == "ring"
    step = pd.Timedelta(days=SPAN_DAYS) / len(ring_sizes)
    kingpin_account = f"KP{int(rng.integers(10**9, 10**10))}"

    trimmed = []
    for r, size in enumerate(ring_sizes):
        rows = aug.index[ring_mask & (aug[EVENT_COL] == f"ring_{r:04d}")]
        keep, cut = rows[:size], rows[size:]
        trimmed.extend(cut)

        denom = RING_DENOMINATIONS[r % len(RING_DENOMINATIONS)]
        aug.loc[keep, "serial"] = _fresh_ring_serial(rng)
        aug.loc[keep, "denomination"] = denom
        aug.loc[keep, "face_value"] = (rng.integers(30, 400, size=len(keep)) * denom).astype(float)
        aug.loc[keep, "seizure_point"] = rng.choice(SEIZURE_POINTS, size=len(keep))
        if r < kingpin_ring_count:
            aug.loc[keep, "courier_account"] = kingpin_account

        start = BASE_TIME + (r + 0.5) * step + pd.Timedelta(hours=float(rng.uniform(-24, 24)))
        aug.loc[keep, "timestamp"] = start + pd.to_timedelta(
            rng.integers(0, 20 * 24 * 60, size=len(keep)), unit="m")

    return aug.drop(index=trimmed).reset_index(drop=True)


def _row_to_seizure(idx: int, row: pd.Series) -> SeizureRecord:
    is_ring = row[TYPOLOGY_COL] == "ring"
    ring_id = f"R{int(str(row[EVENT_COL]).split('_')[1]):04d}" if is_ring else None
    courier = None if pd.isna(row.get("courier_account")) else str(row["courier_account"])
    is_kingpin = bool(ring_id) and courier is not None

    denom = int(row["denomination"])
    face_value = int(round(float(row["face_value"])))
    serial = str(row["serial"])
    point = str(row["seizure_point"])
    n_notes = max(1, face_value // denom)
    # floor to seconds: the float-hours ring offset leaves sub-second precision
    # that to_pydatetime() would warn about discarding, and a seizure timestamp
    # has no meaningful sub-second component anyway.
    ts = pd.Timestamp(row["timestamp"]).floor("s").tz_localize("Asia/Kolkata")

    raw_text = (
        f"Field seizure at {point}: {n_notes} counterfeit INR {denom} notes recovered, "
        f"serial {serial}, face value Rs.{face_value:,}."
    )
    if courier:
        raw_text += f" Proceeds routed via courier account {courier}."

    return SeizureRecord(
        report_id=f"SZ{idx:05d}",
        timestamp=ts.to_pydatetime(),
        channel="field_seizure",
        raw_text=raw_text,
        denomination=denom,
        face_value=face_value,
        serial=serial,
        courier_account=courier,
        seizure_point=point,
        gt_ring_id=ring_id,
        gt_is_kingpin=is_kingpin,
    )


def generate_seizures(
    ring_sizes=FICN_RING_SIZES,
    kingpin_ring_count: int = FICN_KINGPIN_RING_COUNT,
    n_background: int = 120,
    seed: int = 0,
) -> list[SeizureRecord]:
    """The seeded counterfeit-circulation intelligence base: one reused-serial
    ring per entry in `ring_sizes` (the first `kingpin_ring_count` bridged by a
    shared courier account) over a background of isolated one-off recoveries."""
    rng = np.random.default_rng(seed)
    base = _legit_base(n_background, rng)
    legit = legit_background(base, FICN)
    # The engine injects uniform rings; `_plant_rings` trims them to `ring_sizes`.
    aug = inject_ring(legit, n_rings=len(ring_sizes), cards_per_ring=max(ring_sizes),
                      window_hours=2.0, schema=FICN, rng=rng)
    aug = _plant_rings(aug, ring_sizes, kingpin_ring_count, rng)
    return [_row_to_seizure(idx, row) for idx, row in aug.iterrows()]
