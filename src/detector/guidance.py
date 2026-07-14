"""Citizen-facing guidance text (docs/SOLUTION_DESIGN.md §2's "+ guidance").

Kept separate from `Report` on purpose -- the schema is the Detect/Link/Prove
contract and guidance is pure citizen UX, never consumed downstream.
"""
from __future__ import annotations

from src.schema import Report

_RED_FLAG_ADVICE: dict[str, str] = {
    "otp_request": "Never share an OTP with anyone, even someone claiming to be a bank or government official.",
    "remote_access_request": "Do not install remote-access apps (AnyDesk, TeamViewer, etc.) or share your screen.",
    "authority_impersonation": "Real CBI/ED/police/customs officers never demand payment over call or SMS.",
    "payment_demand": "Do not transfer money or share payment details based on this message.",
    "threat": "Threats of arrest or account suspension over SMS/call are a scam pattern, not real procedure.",
}


def guidance(report: Report, *, similar_reports_count: int | None = None) -> str:
    if not report.verdict.is_scam:
        return (
            "No strong scam signals detected. Stay cautious with any unsolicited "
            "payment request, and verify independently before paying."
        )
    lines = ["This looks like a scam. Do not pay, and do not share any OTP."]
    for flag in report.verdict.red_flags:
        if flag in _RED_FLAG_ADVICE:
            lines.append(_RED_FLAG_ADVICE[flag])
    lines.append("Report this to the National Cyber Crime Helpline: call 1930 or visit cybercrime.gov.in.")
    if similar_reports_count:
        lines.append(f"This matches {similar_reports_count} prior reports we've seen.")
    return " ".join(lines)
