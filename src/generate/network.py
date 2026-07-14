"""The pre-seeded scam network (docs/DATASETS.md §4) -- the "existing
intelligence base" the live demo report joins (CLAUDE.md §8).

Reuses the vendored engine's windowed ring injector (`inject_ring`,
parameterised by the `SCAM` schema) for the fan-in structure -- K distinct
victims paying one shared mule `payee_upi` inside a time window -- then
converts the resulting DataFrame into `Report` objects, so `src/graph.build_graph`
consumes this exactly like live detector output: one path, not two.

`inject_ring` draws its shared target from the EXISTING merchant pool (realistic
for card fraud, where a ring fans into a real compromised merchant); a scam ring
needs a FRESH mule identity instead, so each ring's `payee_upi` is overwritten
post-injection using `inj_event` to find its rows (`_plant_rings`). The kingpin
is planted the same way `src/graph`'s own tests expect to find one: a
`mule_phone` shared across MULTIPLE rings, higher-degree than any one ring's own
`payee_upi` -- verified end-to-end in `tests/test_network.py` by feeding this
module's output through `src/graph.detect_rings` / `rank_kingpins`.
"""
from __future__ import annotations

from collections.abc import Sequence

import numpy as np
import pandas as pd

from src.engine import SCAM, TYPOLOGY_COL, inject_ring, legit_background
from src.engine.inject import EVENT_COL
from src.generate.templates import LEGIT_TEMPLATES, SCAM_TEMPLATES, SCAM_TYPE_RED_FLAGS, render
from src.schema import Report

KINGPIN_PHONE = "9999900000"
LEGIT_HUB_UPI = "swiggy@ybl"
BASE_TIME = pd.Timestamp("2026-06-01")
SPAN_DAYS = 30

# The intelligence base is shaped so ONE seeded world carries every beat of the
# demo: a big lead ring for the citizen's report to join AND for the lead-time
# replay to run on, two mid-size rings for the kingpin to bridge, and a tail of
# small ones so "largest ring" is a real quantity rather than a six-way tie.
# Sizes are deliberately unequal -- when every ring is the same size, any join
# is trivially "the largest ring" and that code path never gets exercised.
DEMO_RING_SIZES = (30, 14, 9, 6, 5, 4)

# Ring r's pretext -- assigned, not drawn. Ring 0 is digital_arrest because that
# is what the demo's hero message is, and the kingpin's OTHER rings are
# deliberately different pretexts: one controller running a digital-arrest ring,
# a KYC ring and a lottery ring is the Layer 2 story, and it has to be true of
# the data rather than asserted on a slide.
RING_SCAM_TYPES = ("digital_arrest", "kyc_update", "lottery_prize",
                   "parcel_customs", "loan_app", "investment", "relative_distress")

# Scam amounts are re-drawn rather than inherited from `inject_ring`, which
# samples `amount` from the legit pool on purpose (the engine's controlled-
# benchmark invariant: an injected row must not be separable on any axis except
# its intended signature). Nothing in THIS repo detects on amount -- it is not a
# graph node (`src.graph.build_graph`) and the classifier reads text -- but it is
# rendered into the message and summed into the ring's reported loss, so a
# legit-sized "Rs.1,847" digital-arrest demand would both misstate the harm and
# read as obviously fake.
SCAM_AMOUNT_RANGE = (25_000, 250_000)


def _legit_base(
    n_victims: int, hub_upi: str, hub_share: float, rng: np.random.Generator,
    n_common_payees: int = 4,
) -> pd.DataFrame:
    """`n_victims` legit incidents; `hub_share` of them at `hub_upi` (the
    guardrail's high-degree hub), the rest spread over a small merchant pool.

    The pool is small on purpose: every common merchant must land well ABOVE
    the hub-degree cap (see `generate_network`), or a popular-but-legit payee
    survives the cap and fuses its incidents into a false ring."""
    payees = [hub_upi] + [f"merchant{p:02d}@ybl" for p in range(n_common_payees)]
    weights = np.array([hub_share] + [(1 - hub_share) / n_common_payees] * n_common_payees)
    return pd.DataFrame({
        "victim": [f"victim{i:05d}" for i in range(n_victims)],
        "payee_upi": rng.choice(payees, size=n_victims, p=weights),
        "timestamp": BASE_TIME + pd.to_timedelta(rng.integers(0, 60 * 24 * SPAN_DAYS, size=n_victims), unit="m"),
        "amount": rng.integers(100, 3_000, size=n_victims).astype(float),
        "is_scam": np.zeros(n_victims, dtype=int),
    })


def _plant_rings(
    aug: pd.DataFrame, ring_sizes: Sequence[int], kingpin_ring_count: int,
    rng: np.random.Generator,
) -> pd.DataFrame:
    """Shape the engine's uniform injected rings into the seeded world: trim
    each ring to its target size, give it a fresh mule UPI (module docstring),
    stamp the cross-ring `mule_phone` on the first `kingpin_ring_count` rings,
    re-price it as a scam, and place its window so ring order is arrival order.

    `inject_ring` draws each ring's window start at random, which leaves the
    rings' ARRIVAL order to chance -- and the lead-time replay is a statement
    about arrival order. Whichever kingpin-bridged ring arrives first detects
    cleanly at its 2nd report; the ones that follow are delayed while the
    bridging phone is still under the cap (an honest, documented effect --
    `src.evidence.leadtime`). Placing the rings in size order across the corpus
    span makes the closer a property of the world instead of a property of the
    seed, and reads as an intelligence base that accumulated over a month."""
    aug = aug.copy()
    aug["mule_phone"] = pd.NA
    ring_mask = aug[TYPOLOGY_COL] == "ring"
    step = pd.Timedelta(days=SPAN_DAYS) / len(ring_sizes)

    trimmed = []
    for r, size in enumerate(ring_sizes):
        rows = aug.index[ring_mask & (aug[EVENT_COL] == f"ring_{r:04d}")]
        keep, cut = rows[:size], rows[size:]
        trimmed.extend(cut)

        aug.loc[keep, "payee_upi"] = f"mule{r:02d}@okaxis"
        if r < kingpin_ring_count:
            aug.loc[keep, "mule_phone"] = KINGPIN_PHONE
        aug.loc[keep, "amount"] = rng.integers(*SCAM_AMOUNT_RANGE, size=len(keep)).astype(float)

        window = aug.loc[keep, "timestamp"]
        start = BASE_TIME + (r + 0.5) * step + pd.Timedelta(hours=float(rng.uniform(-12, 12)))
        aug.loc[keep, "timestamp"] = start + (window - window.min())

    return aug.drop(index=trimmed).reset_index(drop=True)


def _ring_scam_types(n_rings: int) -> dict[int, str]:
    return {r: RING_SCAM_TYPES[r % len(RING_SCAM_TYPES)] for r in range(n_rings)}


def _ring_index(row: pd.Series) -> int | None:
    if row[TYPOLOGY_COL] != "ring":
        return None
    return int(str(row[EVENT_COL]).split("_")[1])


def _row_to_report(row: pd.Series, ring_scam_types: dict[int, str], rng: np.random.Generator) -> Report:
    is_scam = bool(row["is_scam"])
    ring_idx = _ring_index(row)
    ring_id = f"R{ring_idx:04d}" if ring_idx is not None else None
    is_kingpin = bool(ring_id) and not pd.isna(row.get("mule_phone"))
    phone = [] if pd.isna(row.get("mule_phone")) else [str(row["mule_phone"])]
    amount = int(round(float(row["amount"])))
    upi = str(row["payee_upi"])

    if is_scam:
        scam_type = ring_scam_types[ring_idx]
        template = str(rng.choice(SCAM_TEMPLATES[scam_type]))
        text = render(template, amount=amount, upi=upi, phone=phone[0] if phone else None)
        red_flags = SCAM_TYPE_RED_FLAGS[scam_type]
    else:
        scam_type, red_flags = "legit", []
        text = render(str(rng.choice(LEGIT_TEMPLATES)), amount=amount, upi=upi)

    timestamp = pd.Timestamp(row["timestamp"]).tz_localize("Asia/Kolkata")
    return Report.model_validate({
        "timestamp": timestamp.isoformat(),
        "channel": str(rng.choice(["sms", "whatsapp", "call_transcript"])),
        "raw_text": text,
        "verdict": {
            "is_scam": is_scam, "confidence": float(rng.uniform(0.85, 0.99)),
            "scam_type": scam_type, "red_flags": red_flags,
        },
        "entities": {"payee_upi": [upi], "phone": phone, "amount": amount},
        "extraction_confidence": float(rng.uniform(0.8, 0.99)),
        "_gt": {"ring_id": ring_id, "is_kingpin_incident": is_kingpin,
                "planted_typology": "ring" if ring_id else "legit"},
    })


def generate_network(
    n_victims: int = 500,
    ring_sizes: Sequence[int] = DEMO_RING_SIZES,
    window_hours: float = 2.0,
    kingpin_ring_count: int = 3,
    legit_hub_upi: str = LEGIT_HUB_UPI,
    legit_hub_share: float = 0.4,
    n_common_payees: int = 4,
    seed: int = 0,
) -> list[Report]:
    """The pre-seeded network: one windowed fan-in ring per entry in
    `ring_sizes` (that many victims each, the first `kingpin_ring_count`
    bridged by a shared kingpin phone), over a `n_victims`-victim legit
    background with a high-degree hub.

    The DEGREE HIERARCHY is the design, because `hub_degree_cap`
    (`src.evidence.DEMO_HUB_DEGREE_CAP`) has to fit inside it:

        max(ring_sizes)  <  cap  <  kingpin phone  <  merchants  <  legit hub
             30             40          53              ~75          ~200

    Layer 1 then keeps every planted ring -- each ring's own mule UPI stays
    under the cap -- while the kingpin's bridging phone, the common merchants
    and the legit hub are all excluded as hubs. Move any of those five
    quantities and the cap must move with it: widen a ring past the cap and
    Layer 1 loses that ring (the too-strict end of the slider curve); drop the
    cap below a merchant's degree and a popular legit payee fuses its incidents
    into a false ring (the too-loose end). Both ends are plotted, on purpose, by
    `src.evidence.precision_recall_curve`."""
    rng = np.random.default_rng(seed)
    base = _legit_base(n_victims, legit_hub_upi, legit_hub_share, rng, n_common_payees)
    legit = legit_background(base, SCAM)
    # The engine injects uniform rings; `_plant_rings` trims them to `ring_sizes`.
    aug = inject_ring(legit, n_rings=len(ring_sizes), cards_per_ring=max(ring_sizes),
                      window_hours=window_hours, schema=SCAM, rng=rng)
    aug = _plant_rings(aug, ring_sizes, kingpin_ring_count, rng)
    ring_scam_types = _ring_scam_types(len(ring_sizes))
    return [_row_to_report(row, ring_scam_types, rng) for _, row in aug.iterrows()]


if __name__ == "__main__":
    import json
    from pathlib import Path

    from src.generate.io import answer_key, write_reports_jsonl

    network = generate_network()
    write_reports_jsonl(network, "data/synthetic/network.jsonl")
    Path("data/synthetic/answer_key.json").write_text(json.dumps(answer_key(network), indent=2))
    print(f"wrote {len(network)} network reports")
