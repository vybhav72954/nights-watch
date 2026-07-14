"""Deterministic scam/legit classifier -- the rules-layer fallback that always
works with no LLM configured (see `llm.py` for the optional Groq path,
which `detect()` prefers when available and falls back from otherwise).

Not a learned model: a keyword score per `scam_type` plus the red-flag count
decide `is_scam`. That's an intentional, testable floor, not a stand-in for
what "LLM-backed" in CLAUDE.md §4.1 ultimately means -- see `llm.py`.
"""
from __future__ import annotations

from src.detector.red_flags import detect_red_flags

# scam_type -> distinguishing keywords/phrases (lower-case). Chosen to
# separate the seven scam_type templates in src/generate/templates.py without
# overlapping the legit templates -- see tests/test_detector.py.
_SCAM_TYPE_KEYWORDS: dict[str, tuple[str, ...]] = {
    "digital_arrest": ("cbi", "ed investigation", "digital arrest", "money-laundering",
                        "money laundering", "arrest warrant", "illegal items"),
    "parcel_customs": ("parcel", "customs", "courier", "shipment", "clearance fee"),
    "kyc_update": ("kyc",),
    "lottery_prize": ("lottery", "lucky draw", "prize", "won rs"),
    # " mom " is space-padded (against the padded text in _score_scam_types,
    # same convention as red_flags.py's B1 fix) -- bare "mom" matched inside
    # "moment". The Hinglish keywords (CLAUDE.md §15 G4) are multi-word
    # phrases only: single high-frequency words ("mummy", "bataunga") scored
    # everyday family texts as scams (CLAUDE.md B10).
    "relative_distress": (" mom ", "lost my phone", "friend's number", "explain everything later",
                          "phone kho gaya", "dost ka number"),
    # Loan-OFFER phrasing only -- bare "loan" scored friend-to-friend loan
    # requests ("can I get a loan from you, I'll pay you back") as scams; all
    # four residual UCI ham FPs were this (CLAUDE.md B11).
    "loan_app": ("instant loan", "personal loan", "loan app", "loan approved", "pre-approved"),
    "investment": ("stock-tips", "guaranteed", "trading", "returns in"),
}

_LEGIT_CAP = 0.95


def _score_scam_types(text_lower: str) -> dict[str, int]:
    padded = f" {text_lower} "  # lets keywords opt into whole-word matching via " kw "
    return {t: sum(1 for kw in kws if kw in padded) for t, kws in _SCAM_TYPE_KEYWORDS.items()}


def _independent_red_flags(padded: str, scam_type: str, entities: dict | None) -> list[str]:
    """Red flags re-computed with `scam_type`'s own keywords masked out of the
    text. Several terms sit in BOTH a scam-type list and a red-flag list
    ("customs", "guaranteed", "lucky draw", "pre-approved") -- without masking,
    one word counted as keyword AND corroborating flag, so "stuck at customs
    at the airport" was a scam verdict; likewise two correlated nouns of one
    type ("my parcel arrived, the courier called") passed the old bare
    score>=2 branch with zero flags (CLAUDE.md B13). Corroboration only
    counts if it survives removing the keywords that raised the suspicion."""
    masked = padded
    for kw in _SCAM_TYPE_KEYWORDS[scam_type]:
        masked = masked.replace(kw, " ")
    return detect_red_flags(masked, entities)


def classify(text: str, entities: dict | None = None) -> dict:
    """Returns a dict shaped like `Verdict` (is_scam, confidence, scam_type,
    red_flags)."""
    red_flags = detect_red_flags(text, entities)
    padded = f" {text.lower()} "
    scores = _score_scam_types(text.lower())
    best_type, best_score = max(scores.items(), key=lambda kv: kv[1])

    # A scam verdict needs two INDEPENDENT signals: a scam-type keyword plus a
    # red flag that isn't the same words re-counted (B13; supersedes B3's
    # score-only branch). Every scam template still carries independent flags
    # -- they all demand payment or apply pressure in their own words.
    is_scam = best_score >= 1 and len(_independent_red_flags(padded, best_type, entities)) >= 1
    if not is_scam:
        confidence = round(max(0.5, min(_LEGIT_CAP, 0.9 - 0.15 * len(red_flags))), 2)
        return {"is_scam": False, "confidence": confidence, "scam_type": "legit", "red_flags": red_flags}

    signal = best_score + 0.5 * len(red_flags)
    scam_type = best_type if best_score > 0 else "other"
    confidence = round(min(0.5 + 0.1 * signal, 0.99), 2)
    return {"is_scam": True, "confidence": confidence, "scam_type": scam_type, "red_flags": red_flags}
