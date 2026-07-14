"""Rule-based red-flag detection (docs/REPORT_SCHEMA.md §5).

Keyword/phrase spotting, not ML -- these are meant to be citizen-legible
("why was this flagged?") as much as they're classifier features, so a
transparent rule per flag beats a learned one here.
"""
from __future__ import annotations

import re

_FLAG_KEYWORDS: dict[str, tuple[str, ...]] = {
    "urgency": (
        "urgent", "immediately", "right now", "within 1 hour", "within 24 hours",
        "expires", "expire", "act now", "today only", "do not disconnect",
        "turant",  # Hinglish (CLAUDE.md §15 G4)
    ),
    "authority_impersonation": (
        "cbi", " ed ", "enforcement directorate", "police", "customs", "income tax",
        "rbi", "trai", "officer", "investigation", "money-laundering", "money laundering",
    ),
    "payment_demand": (
        # Directional demand forms only -- bare "pay " fired on "I'll pay you
        # back", bare "deposit" on "money is deposited" (CLAUDE.md B11). This
        # flag is shown to citizens as the reason; it must mean a demand.
        "pay a ", "pay to", "pay rs", "pay ₹", "pay via", "pay now",
        "pay immediately", "pay karein",  # Hinglish (CLAUDE.md §15 G4)
        "transfer", " deposit ", "processing fee", "clearance fee",
        "verification charge", "security deposit", "send rs", "send it",
        "bhej do",  # Hinglish (CLAUDE.md §15 G4)
    ),
    "threat": (
        "arrest", "warrant", "blocked", "suspension", "suspended", "destroyed",
        " fir ", "jail", "legal action", "digital arrest",
    ),
    "secrecy": (
        "don't tell", "do not tell", "keep this confidential", "don't disconnect",
        "do not disconnect", "between us", "explain everything later", "don't share this",
    ),
    "suspicious_link": (
        "http://", "https://", "click here", "click the link",
    ),
    "too_good_to_be_true": (
        "guaranteed", "300%", "won rs", "congratulations", "lucky draw",
        "pre-approved", "free ", "jackpot",
    ),
    "remote_access_request": (
        "anydesk", "teamviewer", "remote access", "screen share", "quick support",
        "install this app",
    ),
}

# OTP is a red flag only when the message asks the recipient to *share* it --
# a bank's own "here is your OTP, don't share it" notice must NOT trip this,
# so a bare "otp" keyword isn't enough; negation ("do not share") wins.
_OTP_SHARE_RE = re.compile(r"\bshare\b.{0,20}\botp\b|\botp\b.{0,20}\bshare\b", re.IGNORECASE)
_OTP_SHARE_NEGATED_RE = re.compile(r"(?:do not|don't|never)\s+share.{0,20}\botp\b", re.IGNORECASE)


def _requests_otp_share(text: str) -> bool:
    if _OTP_SHARE_NEGATED_RE.search(text):
        return False
    return bool(_OTP_SHARE_RE.search(text))


def detect_red_flags(text: str, entities: dict | None = None) -> list[str]:
    lowered = f" {text.lower()} "
    flags = [flag for flag, kws in _FLAG_KEYWORDS.items() if any(kw in lowered for kw in kws)]
    if _requests_otp_share(text):
        flags.append("otp_request")
    if entities and entities.get("url") and "suspicious_link" not in flags:
        flags.append("suspicious_link")
    order = list(_FLAG_KEYWORDS) + ["otp_request"]
    return sorted(set(flags), key=order.index)
