"""The answer-key scam+legit message corpus (docs/DATASETS.md §3).

Text is template-rendered, not LLM-paraphrased -- real paraphrase (LLM, for
natural variation / Hinglish) is a documented, optional follow-up (see bottom
of this file). The graph/evidence pipeline this corpus feeds never reads
`raw_text`, only `entities` (CLAUDE.md §1), so template text is not a gap in
what's provable -- only in demo polish.

Ring linkage: every ring's messages share one mule `payee_upi`. Every ring also
carries a phone identifier -- ring-unique for ordinary rings, but the SAME
shared phone across a designated subset of "kingpin rings". That shared phone
has higher degree than any single ring's own `payee_upi`, which is exactly the
cross-ring bridge `src/graph`'s kingpin ranking is built to surface (see
`src/graph/README.md` and `tests/test_messages.py`).
"""
from __future__ import annotations

from datetime import timedelta

import numpy as np
import pandas as pd

from src.generate.templates import LEGIT_TEMPLATES, SCAM_TEMPLATES, SCAM_TYPE_RED_FLAGS, render
from src.schema import Report

KINGPIN_PHONE = "9999900000"
LEGIT_HUB_UPI = "swiggy@ybl"
#  Wide on purpose: with n_legit ~40 and legit_hub_share ~0.4, ~24 messages
# spread over 12 merchants averages ~2/merchant -- well under any ring's size,
# so the hub stays cleanly the only high-degree legit node (see test_messages.py).
LEGIT_MERCHANT_POOL = [
    "zomato@ybl", "amazon@apl", "irctc@sbi", "electricity@paytm", "netflix@icici",
    "uber@axl", "ola@ybl", "bigbasket@icici", "myntra@apl", "flipkart@ybl",
    "bookmyshow@paytm", "jio@icici",
]
BASE_TIME = pd.Timestamp("2026-06-01T09:00:00+05:30")


def _ring_phone(r: int) -> str:
    return f"98{r:08d}"


def _ring_url(scam_type: str, r: int) -> str:
    return f"http://{scam_type.replace('_', '-')}-{r:02d}.in/pay"


def _report(*, timestamp, channel, raw_text, is_scam, confidence, scam_type, red_flags,
            payee_upi=(), phone=(), url=(), amount=None, extraction_confidence,
            ring_id=None, is_kingpin_incident=False, planted_typology="legit") -> Report:
    return Report.model_validate({
        "timestamp": timestamp.isoformat(),
        "channel": channel,
        "raw_text": raw_text,
        "verdict": {
            "is_scam": is_scam, "confidence": confidence,
            "scam_type": scam_type, "red_flags": list(red_flags),
        },
        "entities": {
            "payee_upi": list(payee_upi), "phone": list(phone),
            "url": list(url), "amount": amount,
        },
        "extraction_confidence": extraction_confidence,
        "_gt": {
            "ring_id": ring_id, "is_kingpin_incident": is_kingpin_incident,
            "planted_typology": planted_typology,
        },
    })


def _scam_messages(rng: np.random.Generator, n_rings: int, kingpin_ring_count: int) -> list[Report]:
    scam_types = list(SCAM_TEMPLATES.keys())
    kingpin_rings = set(range(kingpin_ring_count))
    channel_pool = ["sms", "whatsapp", "call_transcript"]
    reports = []
    for r in range(n_rings):
        mule_upi = f"mule{r:02d}@okaxis"
        scam_type = str(rng.choice(scam_types))
        ring_phone = KINGPIN_PHONE if r in kingpin_rings else _ring_phone(r)
        ring_url = _ring_url(scam_type, r)
        ring_base = BASE_TIME + timedelta(days=int(r))
        for j in range(int(rng.integers(3, 7))):
            template = str(rng.choice(SCAM_TEMPLATES[scam_type]))
            amount = int(rng.integers(2_000, 50_000))
            text = render(template, amount=amount, upi=mule_upi, phone=ring_phone, url=ring_url)
            reports.append(_report(
                timestamp=ring_base + timedelta(minutes=15 * j),
                channel=str(rng.choice(channel_pool)),
                raw_text=text,
                is_scam=True,
                confidence=float(rng.uniform(0.85, 0.99)),
                scam_type=scam_type,
                red_flags=SCAM_TYPE_RED_FLAGS[scam_type],
                payee_upi=[mule_upi],
                phone=[ring_phone],
                url=[ring_url],
                amount=amount,
                extraction_confidence=float(rng.uniform(0.8, 0.99)),
                ring_id=f"R{r:04d}",
                is_kingpin_incident=r in kingpin_rings,
                planted_typology="ring",
            ))
    return reports


def _legit_messages(rng: np.random.Generator, n_legit: int, hub_upi: str, hub_share: float) -> list[Report]:
    reports = []
    for _ in range(n_legit):
        upi = hub_upi if rng.random() < hub_share else str(rng.choice(LEGIT_MERCHANT_POOL))
        amount = int(rng.integers(100, 3_000))
        text = render(str(rng.choice(LEGIT_TEMPLATES)), amount=amount, upi=upi)
        timestamp = BASE_TIME + timedelta(minutes=int(rng.integers(0, 60 * 24 * 30)))
        reports.append(_report(
            timestamp=timestamp,
            channel="sms",
            raw_text=text,
            is_scam=False,
            confidence=float(rng.uniform(0.85, 0.99)),
            scam_type="legit",
            red_flags=[],
            payee_upi=[upi],
            amount=amount,
            extraction_confidence=float(rng.uniform(0.85, 0.99)),
        ))
    return reports


def generate_messages(
    n_rings: int = 6,
    kingpin_ring_count: int = 3,
    n_legit: int = 40,
    legit_hub_upi: str = LEGIT_HUB_UPI,
    legit_hub_share: float = 0.4,
    seed: int = 0,
) -> list[Report]:
    """`n_rings` scam rings (the first `kingpin_ring_count` sharing the planted
    kingpin phone) plus `n_legit` background legit messages (`legit_hub_share`
    of them touching `legit_hub_upi`, the guardrail's high-degree hub),
    shuffled together."""
    rng = np.random.default_rng(seed)
    reports = _scam_messages(rng, n_rings, kingpin_ring_count) + _legit_messages(
        rng, n_legit, legit_hub_upi, legit_hub_share
    )
    order = rng.permutation(len(reports))
    return [reports[i] for i in order]


def train_eval_split(
    reports: list[Report], eval_frac: float = 0.2, seed: int = 0,
) -> tuple[list[Report], list[Report]]:
    rng = np.random.default_rng(seed)
    order = rng.permutation(len(reports))
    n_eval = int(len(reports) * eval_frac)
    eval_ids = set(order[:n_eval].tolist())
    train = [r for i, r in enumerate(reports) if i not in eval_ids]
    eval_ = [r for i, r in enumerate(reports) if i in eval_ids]
    return train, eval_


if __name__ == "__main__":
    from src.generate.io import write_reports_jsonl

    corpus = generate_messages()
    train, eval_ = train_eval_split(corpus)
    write_reports_jsonl(train, "data/synthetic/messages_train.jsonl")
    write_reports_jsonl(eval_, "data/synthetic/messages_eval.jsonl")
    print(f"wrote {len(train)} train / {len(eval_)} eval reports")

# Follow-up (not built): LLM paraphrase for natural variation / Hinglish. Take
# `_report`'s rendered `raw_text` and pass it through the LLM with a prompt that
# preserves every identifier verbatim (never let the model invent or drop a
# UPI/phone/amount -- that would break the entities/_gt ground truth this
# corpus exists to provide). Gate behind an API key; the pipeline above must
# keep working with template text alone when one isn't configured.
