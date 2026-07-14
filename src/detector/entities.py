"""Deterministic entity extraction (docs/SOLUTION_DESIGN.md §2).

Regex only -- this is the part Link depends on, so it must work with no LLM
configured. `device_hint` is intentionally left out: the spec assigns it to
the LLM layer (see `llm.py`), and there's no honest regex for it.

Extraction order matters: a span already claimed by an earlier extractor
(url before upi before phone before account/ifsc) can't be claimed again --
without that, e.g. a 10-digit phone number would also match the account-number
pattern.
"""
from __future__ import annotations

import re
from dataclasses import dataclass

_URL_RE = re.compile(r"https?://[^\s,.;!?]+(?:\.[^\s,.;!?]+)*", re.IGNORECASE)
# UPI PSP handles (okaxis, ybl, okhdfc, ...) are alphanumeric with no dots;
# email domains virtually always contain one. Without the distinction every
# email in a message became a payee_upi graph node, and two unrelated reports
# both mentioning e.g. support@gmail.com formed a false hard-connection edge
# -- the exact thing Layer 1 presents as proof (CLAUDE.md B17). The trailing
# (?!\.\w) rejects a domain continuation but not sentence punctuation
# ("Pay to: mule00@okaxis." still matches); the \b before it prevents
# backtracking into a partial handle ("support@gmai").
_UPI_RE = re.compile(r"\b[\w][\w.\-]*@[A-Za-z]\w*\b(?!\.\w)")
# Optional 0/+91/91 prefix and one separator inside the number: Indian SMS
# convention writes phones as "98765 43210" / "098765 43210" -- the old
# 10-contiguous-digits form missed both, silently dropping the identifier
# from the graph for live pasted text (CLAUDE.md B18). normalize_phone()
# in the schema always expected these forms. (?<!\d) is B4's guard.
_PHONE_RE = re.compile(r"(?<!\d)(?:\+?91[-\s]?|0)?[6-9]\d{4}[-\s]?\d{5}\b")
_IFSC_RE = re.compile(r"\b[A-Z]{4}0[A-Z0-9]{6}\b")
_ACCOUNT_RE = re.compile(r"\b\d{9,18}\b")
_AMOUNT_RE = re.compile(r"(?:Rs\.?|₹|INR)\s*([\d][\d,]*)", re.IGNORECASE)
_PAYMENT_KEYWORDS = ("pay", "fee", "charge", "deposit", "transfer", "send")


class _SpanClaims:
    """Tracks which character ranges other extractors already own."""

    def __init__(self) -> None:
        self._claimed: list[tuple[int, int]] = []

    def take_spans(self, pattern: re.Pattern, text: str) -> list[tuple[int, int, str]]:
        hits = []
        for m in pattern.finditer(text):
            if any(m.start() < end and start < m.end() for start, end in self._claimed):
                continue
            self._claimed.append((m.start(), m.end()))
            hits.append((m.start(), m.end(), m.group(0)))
        return hits

    def take(self, pattern: re.Pattern, text: str) -> list[str]:
        return [v for _, _, v in self.take_spans(pattern, text)]

    def overlaps(self, start: int, end: int) -> bool:
        return any(start < e and s < end for s, e in self._claimed)


# Claim order is load-bearing (see module docstring): url > upi > phone >
# ifsc > account.
_CLAIM_ORDER: tuple[tuple[str, re.Pattern], ...] = (
    ("url", _URL_RE),
    ("payee_upi", _UPI_RE),
    ("phone", _PHONE_RE),
    ("ifsc", _IFSC_RE),
    ("account", _ACCOUNT_RE),
)


@dataclass(frozen=True)
class EntitySpan:
    """Where an extracted identifier sits in the source text. The app uses this
    to highlight identifiers in place -- the graph runs on these values, so the
    demo shows the text literally becoming graph nodes (CLAUDE.md §1)."""

    start: int
    end: int
    kind: str  # payee_upi | phone | account | ifsc | url | amount
    value: str


def _amount_match(text: str) -> re.Match | None:
    matches = list(_AMOUNT_RE.finditer(text))
    if not matches:
        return None
    if len(matches) == 1:
        return matches[0]
    lowered = text.lower()
    kw_positions = [
        m.start() for kw in _PAYMENT_KEYWORDS for m in re.finditer(re.escape(kw), lowered)
    ]
    if not kw_positions:
        return matches[0]
    return min(matches, key=lambda m: min(abs(m.start() - kp) for kp in kw_positions))


def _extract_amount(text: str) -> int | None:
    m = _amount_match(text)
    return int(m.group(1).replace(",", "")) if m else None


def entity_spans(text: str) -> list[EntitySpan]:
    """The same claims `extract_entities` makes, but positioned -- so a caller
    can render them in place. Non-overlapping and in document order.

    Amount is claimed last and only if it doesn't collide with an identifier:
    `_AMOUNT_RE` runs outside the claim chain during extraction (an amount is
    not a graph node, so it never needed to compete), which leaves a rare
    overlap possible (`Rs 987654321` is also account-shaped). Extraction's
    precedence stands; display just declines to draw the loser twice.
    """
    claims = _SpanClaims()
    by_kind = {kind: claims.take_spans(pat, text) for kind, pat in _CLAIM_ORDER}
    phone_values = {v for _, _, v in by_kind["phone"]}

    spans = [
        EntitySpan(s, e, kind, v)
        for kind, _ in _CLAIM_ORDER
        for s, e, v in by_kind[kind]
        if not (kind == "account" and v in phone_values)
    ]
    m = _amount_match(text)
    if m and not claims.overlaps(m.start(), m.end()):
        spans.append(EntitySpan(m.start(), m.end(), "amount", m.group(0)))
    return sorted(spans, key=lambda s: s.start)


def extract_entities(text: str) -> dict:
    """Returns a dict shaped like `Entities` (pre-normalisation -- the schema's
    field validators normalise on assignment, so raw matches are enough)."""
    claims = _SpanClaims()
    urls = claims.take(_URL_RE, text)
    upis = claims.take(_UPI_RE, text)
    phones = claims.take(_PHONE_RE, text)
    ifscs = claims.take(_IFSC_RE, text)
    accounts = [a for a in claims.take(_ACCOUNT_RE, text) if a not in phones]
    return {
        "payee_upi": sorted(set(upis)),
        "phone": sorted(set(phones)),
        "account": sorted(set(accounts)),
        "ifsc": sorted(set(ifscs)),
        "url": sorted(set(urls)),
        "amount": _extract_amount(text),
        "device_hint": None,
    }


def extraction_confidence(entities: dict) -> float:
    """More independent identifier *types* found -> more confidence the
    extraction is real, not noise. No identifiers at all is still a valid
    report (e.g. legit chatter) but shouldn't feed the graph by default --
    see `Report.is_graph_eligible`'s 0.5 threshold."""
    types_found = sum(1 for k in ("payee_upi", "phone", "account", "ifsc", "url") if entities.get(k))
    if types_found == 0:
        return 0.3
    return round(min(0.6 + 0.15 * types_found, 0.98), 2)
