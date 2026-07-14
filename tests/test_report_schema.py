"""Contract tests for src/schema/report.py — see docs/REPORT_SCHEMA.md."""
from __future__ import annotations

import pytest
from pydantic import ValidationError

from src.schema import Report


def _base(**overrides):
    payload = {
        "timestamp": "2026-07-07T14:03:22+05:30",
        "channel": "whatsapp",
        "raw_text": "This is CBI. A parcel in your name…",
        "verdict": {
            "is_scam": True,
            "confidence": 0.94,
            "scam_type": "digital_arrest",
            "red_flags": ["authority_impersonation", "threat", "payment_demand"],
        },
        "entities": {"payee_upi": ["fraudguy@okhdfc"], "amount": 45000},
        "extraction_confidence": 0.88,
    }
    payload.update(overrides)
    return payload


# ── worked examples from the schema doc ──────────────────────────────────────

def test_scam_report_joins_ring():
    r = Report.model_validate({
        "timestamp": "2026-07-07T10:00:00+05:30",
        "channel": "whatsapp",
        "raw_text": "…",
        "verdict": {"is_scam": True, "confidence": 0.9, "scam_type": "parcel_customs"},
        "entities": {"payee_upi": ["mule07@okaxis"], "phone": ["+919800000007"], "amount": 30000},
        "extraction_confidence": 0.9,
        "_gt": {"ring_id": "R07", "is_kingpin_incident": True, "planted_typology": "ring"},
    })
    assert r.gt.ring_id == "R07"
    assert r.gt.is_kingpin_incident is True


def test_legit_report_no_ring():
    r = Report.model_validate({
        "timestamp": "2026-07-07T10:00:00+05:30",
        "channel": "sms",
        "raw_text": "…",
        "verdict": {"is_scam": False, "confidence": 0.1, "scam_type": "legit"},
        "entities": {"payee_upi": ["swiggy@ybl"], "amount": 420},
        "extraction_confidence": 0.95,
        "_gt": {"ring_id": None, "is_kingpin_incident": False, "planted_typology": "legit"},
    })
    assert r.gt.ring_id is None


# ── normalisation (§3) ────────────────────────────────────────────────────────

@pytest.mark.parametrize("raw,expected", [
    ("Fraud@OKHDFC", "fraud@okhdfc"),
    (" fraud@okhdfc ", "fraud@okhdfc"),
])
def test_upi_normalised(raw, expected):
    r = Report.model_validate(_base(entities={"payee_upi": [raw]}))
    assert r.entities.payee_upi == [expected]


@pytest.mark.parametrize("raw", ["098123 45678", "+919812345678", "9812345678"])
def test_phone_normalised_to_e164(raw):
    r = Report.model_validate(_base(entities={"phone": [raw]}))
    assert r.entities.phone == ["+919812345678"]


def test_account_digits_only():
    r = Report.model_validate(_base(entities={"account": ["5010 0123 4567 89"]}))
    assert r.entities.account == ["50100123456789"]


def test_ifsc_uppercased():
    r = Report.model_validate(_base(entities={"ifsc": [" hdfc0001234 "]}))
    assert r.entities.ifsc == ["HDFC0001234"]


def test_url_host_lowercased_path_preserved():
    r = Report.model_validate(_base(entities={"url": ["HTTP://CBI-Verify.in/Pay?x=1"]}))
    assert r.entities.url == ["http://cbi-verify.in/Pay?x=1"]


def test_two_case_variant_upis_collide_after_normalisation():
    a = Report.model_validate(_base(entities={"payee_upi": ["Fraud@okhdfc"]}))
    b = Report.model_validate(_base(entities={"payee_upi": ["fraud@OKHDFC"]}))
    assert a.entities.payee_upi == b.entities.payee_upi


# ── field rules / validation (§2, §8) ────────────────────────────────────────

def test_entities_default_to_empty_not_missing():
    r = Report.model_validate(_base(entities={}))
    assert r.entities.payee_upi == []
    assert r.entities.phone == []


def test_timestamp_without_tz_rejected():
    with pytest.raises(ValidationError):
        Report.model_validate(_base(timestamp="2026-07-07T14:03:22"))


def test_confidence_out_of_range_rejected():
    with pytest.raises(ValidationError):
        Report.model_validate(_base(verdict={
            "is_scam": True, "confidence": 1.5, "scam_type": "digital_arrest",
        }))


def test_non_scam_must_carry_legit_or_other_scam_type():
    with pytest.raises(ValidationError):
        Report.model_validate(_base(verdict={
            "is_scam": False, "confidence": 0.1, "scam_type": "digital_arrest",
        }))


def test_non_scam_legit_is_accepted():
    r = Report.model_validate(_base(verdict={
        "is_scam": False, "confidence": 0.1, "scam_type": "legit",
    }))
    assert r.verdict.scam_type == "legit"


def test_unknown_channel_rejected():
    with pytest.raises(ValidationError):
        Report.model_validate(_base(channel="carrier_pigeon"))


def test_report_id_auto_generated_and_unique():
    a = Report.model_validate(_base())
    b = Report.model_validate(_base())
    assert a.report_id != b.report_id


# ── _gt isolation (§8 — the model must never read it) ────────────────────────

def test_gt_absent_by_default():
    r = Report.model_validate(_base())
    assert r.gt is None


def test_for_model_input_strips_gt():
    r = Report.model_validate(_base(_gt={"ring_id": "R01"}))
    dumped = r.for_model_input()
    assert "gt" not in dumped and "_gt" not in dumped
    assert dumped["raw_text"] == r.raw_text


def test_gt_constructible_by_python_name_or_alias():
    from src.schema import GroundTruth
    by_alias = Report.model_validate(_base(_gt={"ring_id": "R01"}))
    by_name = Report(**_base(gt=GroundTruth(ring_id="R01")))
    assert by_alias.gt.ring_id == by_name.gt.ring_id == "R01"


# ── graph eligibility gate (§8) ───────────────────────────────────────────────

def test_is_graph_eligible_threshold():
    weak = Report.model_validate(_base(extraction_confidence=0.2))
    strong = Report.model_validate(_base(extraction_confidence=0.9))
    assert weak.is_graph_eligible(threshold=0.5) is False
    assert strong.is_graph_eligible(threshold=0.5) is True
