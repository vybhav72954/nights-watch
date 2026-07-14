"""The Report contract — the single interface between Detect and Link/Prove.

See ``docs/REPORT_SCHEMA.md`` for the full spec (worked examples, field rules,
entities -> graph mapping). All three workstreams import THIS definition;
do not fork it.

Identifier-first: the graph runs on ``entities``, not on ``verdict``.
"""
from __future__ import annotations

import re
import uuid
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

Channel = Literal["sms", "whatsapp", "call_transcript", "email"]

ScamType = Literal[
    "digital_arrest", "parcel_customs", "kyc_update", "lottery_prize",
    "relative_distress", "loan_app", "investment", "other", "legit",
]

RedFlag = Literal[
    "urgency", "authority_impersonation", "payment_demand", "threat",
    "secrecy", "suspicious_link", "too_good_to_be_true", "otp_request",
    "remote_access_request",
]

PlantedTypology = Literal["ring", "velocity", "temporal", "legit"]


# ── normalisation (§3 of the schema doc) ─────────────────────────────────────
# This is what makes two reports *share* a node — without it `Fraud@okhdfc` and
# `fraud@OKHDFC` become two nodes and a ring silently fragments.

def normalize_upi(upi: str) -> str:
    return upi.strip().lower()


def normalize_phone(phone: str) -> str:
    """`098123 45678` / `+919812345678` / `9812345678` -> `+919812345678`."""
    digits = re.sub(r"\D", "", phone).lstrip("0")
    if digits.startswith("91") and len(digits) == 12:
        digits = digits[2:]
    if len(digits) != 10:
        raise ValueError(f"cannot normalise phone to a 10-digit Indian number: {phone!r}")
    return f"+91{digits}"


def normalize_account(account: str) -> str:
    return re.sub(r"\D", "", account)


def normalize_ifsc(ifsc: str) -> str:
    return ifsc.strip().upper()


def normalize_url(url: str) -> str:
    """Lower-case the host, keep the path/query as-is."""
    m = re.match(r"^(https?://)([^/]+)(/.*)?$", url.strip(), re.IGNORECASE)
    if not m:
        return url.strip().lower()
    scheme, host, path = m.group(1).lower(), m.group(2).lower(), m.group(3) or ""
    return f"{scheme}{host}{path}"


class Verdict(BaseModel):
    """Citizen-facing. NOT used by the graph."""
    is_scam: bool
    confidence: float = Field(ge=0.0, le=1.0)
    scam_type: ScamType
    red_flags: list[RedFlag] = Field(default_factory=list)


class Entities(BaseModel):
    """The graph runs on this. Every value here is a potential graph node;
    shared values become edges. Lists default to `[]`, never missing."""
    payee_upi: list[str] = Field(default_factory=list)
    phone: list[str] = Field(default_factory=list)
    account: list[str] = Field(default_factory=list)
    ifsc: list[str] = Field(default_factory=list)
    url: list[str] = Field(default_factory=list)
    amount: int | None = None
    device_hint: str | None = None

    @field_validator("payee_upi")
    @classmethod
    def _norm_upi(cls, v: list[str]) -> list[str]:
        return [normalize_upi(x) for x in v]

    @field_validator("phone")
    @classmethod
    def _norm_phone(cls, v: list[str]) -> list[str]:
        return [normalize_phone(x) for x in v]

    @field_validator("account")
    @classmethod
    def _norm_account(cls, v: list[str]) -> list[str]:
        return [normalize_account(x) for x in v]

    @field_validator("ifsc")
    @classmethod
    def _norm_ifsc(cls, v: list[str]) -> list[str]:
        return [normalize_ifsc(x) for x in v]

    @field_validator("url")
    @classmethod
    def _norm_url(cls, v: list[str]) -> list[str]:
        return [normalize_url(x) for x in v]


class GroundTruth(BaseModel):
    """Answer key — present ONLY in synthetic data. The model must NEVER read
    this; use `Report.for_model_input()` to strip it before any model call."""
    ring_id: str | None = None
    is_kingpin_incident: bool = False
    planted_typology: PlantedTypology = "legit"


class Report(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    report_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    timestamp: datetime
    channel: Channel
    raw_text: str
    language: str = "en"
    verdict: Verdict
    entities: Entities = Field(default_factory=Entities)
    extraction_confidence: float = Field(ge=0.0, le=1.0)
    gt: GroundTruth | None = Field(default=None, alias="_gt")

    @field_validator("timestamp")
    @classmethod
    def _tz_aware(cls, v: datetime) -> datetime:
        if v.tzinfo is None:
            raise ValueError("timestamp must carry a timezone (ISO-8601 with offset)")
        return v

    @model_validator(mode="after")
    def _legit_scam_type(self) -> "Report":
        if not self.verdict.is_scam and self.verdict.scam_type not in ("legit", "other"):
            raise ValueError(
                "verdict.is_scam is False but scam_type="
                f"{self.verdict.scam_type!r}; expected 'legit' or 'other'"
            )
        return self

    def for_model_input(self) -> dict:
        """Serialised form safe to hand to the detector/classifier. Strips
        `_gt` — the model must NEVER see ground truth (§8)."""
        return self.model_dump(mode="json", exclude={"gt"})

    def is_graph_eligible(self, threshold: float = 0.5) -> bool:
        """Gate weak extractions out of the graph (§8, configurable τ)."""
        return self.extraction_confidence >= threshold
