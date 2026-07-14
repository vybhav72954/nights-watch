"""Tests for src/detector -- entity extraction, red flags, the rules
classifier, the optional LLM hook, and the detect() orchestrator.

The last section runs `detect()` over the *generated* corpus
(`src/generate/messages.py`) so extraction/classification are checked
against the same texts the graph/evidence tests already treat as ground
truth -- not just hand-picked examples.
"""
from __future__ import annotations

import importlib
import json
import os
import sys
import types

import pytest

from src.detector import (
    active_classifier_path,
    classify,
    classify_with_llm,
    detect,
    detect_red_flags,
    entity_spans,
    extract_entities,
    extraction_confidence,
    guidance,
)
from src.generate.messages import generate_messages
from src.generate.templates import SCAM_TEMPLATES, render
from src.graph import build_graph, detect_rings
from src.schema import normalize_phone


# ── entity extraction ────────────────────────────────────────────────────

def test_extract_upi_case_and_whitespace():
    e = extract_entities("Pay to Fraud@OKHDFC now.")
    assert e["payee_upi"] == ["Fraud@OKHDFC"]  # normalisation happens in Entities, not here


def test_extract_phone_plain_and_prefixed():
    e = extract_entities("Call +91 9812345678 or 9812345678.")
    assert e["phone"]
    assert {normalize_phone(p) for p in e["phone"]} == {"+919812345678"}


def test_extract_ifsc_and_account_are_distinguished_from_phone():
    e = extract_entities("Account 50100123456789, IFSC HDFC0001234, call 9812345678.")
    assert e["account"] == ["50100123456789"]
    assert e["ifsc"] == ["HDFC0001234"]
    assert e["phone"] == ["9812345678"]
    assert "50100123456789" not in e["phone"]


def test_extract_phone_does_not_steal_the_tail_of_a_longer_account_number():
    # regression for CLAUDE.md B4: _PHONE_RE had no left boundary, so it could
    # match the last 10 digits of a 14-digit account number.
    e = extract_entities("Please transfer to account 12349876543210 to proceed.")
    assert e["phone"] == []
    assert e["account"] == ["12349876543210"]


@pytest.mark.parametrize("text", [
    "Contact us at support@gmail.com for help with your booking",
    "Send your resume to hr.team@infosys.com by Friday",
    "My email is john.doe123@yahoo.co.in, write anytime",
    "Meeting invite sent from calendar-noreply@google.com",
])
def test_extract_does_not_mistake_an_email_for_a_upi(text):
    # regression for CLAUDE.md B17: emails fully matched the old UPI regex, so
    # every email in a message became a payee_upi graph node -- two unrelated
    # reports both mentioning support@gmail.com formed a false hard-connection
    # edge, the exact thing Layer 1 presents as proof. UPI PSP handles are
    # alphanumeric with no dots; email domains virtually always have one.
    assert extract_entities(text)["payee_upi"] == []


def test_extract_upi_still_matches_at_sentence_end_and_numeric_vpas():
    # the B17 fix must not overshoot: sentence punctuation after the handle
    # (render() appends "Pay to: {upi}.") and phone-number VPAs stay UPIs.
    assert extract_entities("Pay to: mule00@okaxis.")["payee_upi"] == ["mule00@okaxis"]
    e = extract_entities("Send money to 9876543210@ybl right now")
    assert e["payee_upi"] == ["9876543210@ybl"]
    assert e["phone"] == []  # the VPA span is claimed by the UPI extractor


@pytest.mark.parametrize("text", [
    "Call 098765 43210 about your parcel",
    "Call 98765 43210 now",
    "Call +91 98765 43210 today",
    "Call 09876543210 now",
])
def test_extract_phone_handles_spaced_and_zero_prefixed_forms(text):
    # regression for CLAUDE.md B18: the old pattern required 10 contiguous
    # digits, silently dropping the standard Indian "98765 43210" display
    # form (and any 0-prefixed number) from the graph for live pasted text --
    # normalize_phone() in the schema always expected these forms.
    e = extract_entities(text)
    assert {normalize_phone(p) for p in e["phone"]} == {"+919876543210"}


def test_extract_url():
    e = extract_entities("Verify at http://CBI-Verify.in/pay now.")
    assert e["url"] == ["http://CBI-Verify.in/pay"]


def test_extract_amount_single_mention():
    e = extract_entities(render(SCAM_TEMPLATES["parcel_customs"][0], amount=4500, upi="x@y", phone="9812345678"))
    assert e["amount"] == 4500


def test_extract_amount_prefers_the_payment_demand_over_the_lure_amount():
    text = render(SCAM_TEMPLATES["lottery_prize"][0], amount=3000, upi="mule@okaxis")
    e = extract_entities(text)
    assert e["amount"] == 3000  # not the fixed Rs.25,00,000 prize amount


def test_extract_amount_absent_returns_none():
    assert extract_entities("Hello, how are you?")["amount"] is None


def test_extraction_confidence_scales_with_identifier_types_found():
    none_found = extraction_confidence(extract_entities("hello there"))
    one_found = extraction_confidence(extract_entities("pay to fraud@okhdfc"))
    two_found = extraction_confidence(extract_entities("pay to fraud@okhdfc or call 9812345678"))
    assert none_found < one_found < two_found
    assert none_found < 0.5  # below Report.is_graph_eligible's default threshold


# ── red flags ─────────────────────────────────────────────────────────────

def test_digital_arrest_message_fires_expected_flags():
    text = render(SCAM_TEMPLATES["digital_arrest"][0], amount=45000, upi="fraud@okhdfc")
    flags = detect_red_flags(text)
    assert "authority_impersonation" in flags
    assert "threat" in flags
    assert "payment_demand" in flags
    assert "urgency" in flags


def test_legit_otp_notice_does_not_fire_otp_request():
    text = "OTP for your transaction of Rs.500 is 482913. Valid for 10 minutes. Do not share this OTP with anyone."
    assert "otp_request" not in detect_red_flags(text)


def test_kyc_scam_asking_to_share_otp_fires_otp_request():
    text = render(SCAM_TEMPLATES["kyc_update"][1], upi="x@y", url="http://kyc-verify.in")
    assert "otp_request" in detect_red_flags(text)


def test_remote_access_flag():
    assert "remote_access_request" in detect_red_flags("Please install AnyDesk so our agent can verify your account.")


def test_too_good_to_be_true_flag():
    text = render(SCAM_TEMPLATES["investment"][0], amount=5000, upi="x@y")
    assert "too_good_to_be_true" in detect_red_flags(text)


def test_suspicious_link_flag_from_entities():
    entities = {"url": ["http://evil.in"]}
    assert "suspicious_link" in detect_red_flags("no scheme text here but a link was extracted", entities)


@pytest.mark.parametrize("text", [
    "Your ticket is confirmed for tomorrow.",
    "Payment of Rs.500 to zomato@ybl was successful. Your order will be delivered soon.",
    "Your order has been shipped and confirmed for delivery.",
])
def test_ordinary_words_containing_ed_or_fir_do_not_fire_flags(text):
    # regression for CLAUDE.md B1: "ed " / "fir" matched inside "confirmed",
    # "delivered" -- whole-word padding was missing its leading space.
    flags = detect_red_flags(text)
    assert "authority_impersonation" not in flags
    assert "threat" not in flags


# ── classify() (deterministic rules) ────────────────────────────────────

@pytest.mark.parametrize("scam_type", list(SCAM_TEMPLATES.keys()))
def test_classify_recovers_scam_type_for_every_template(scam_type):
    for template in SCAM_TEMPLATES[scam_type]:
        text = render(template, amount=9000, upi="mule@okaxis", phone="9812345678", url="http://x.in/pay")
        result = classify(text)
        assert result["is_scam"] is True
        assert result["scam_type"] == scam_type, text


def test_classify_legit_message_is_not_scam():
    result = classify("Your order from zomato@ybl has been placed. Amount Rs.420 paid successfully.")
    assert result["is_scam"] is False
    assert result["scam_type"] == "legit"


@pytest.mark.parametrize("text", [
    "My amazon parcel was delivered today",
    "I won the office lottery",
])
def test_classify_single_coincidental_keyword_stays_legit(text):
    # regression for CLAUDE.md B3: one scam_type keyword hit with no
    # corroborating red flag used to force is_scam=True.
    result = classify(text)
    assert result["is_scam"] is False
    assert result["scam_type"] == "legit"


def test_classify_legit_confidence_decreases_with_more_red_flags():
    # regression for CLAUDE.md B5: legit confidence used to *increase* with
    # red-flag count, the inverse of what it should signal.
    calm = classify("Your order from zomato@ybl has been placed. Amount Rs.420 paid successfully.")
    flagged = classify("Your order from zomato@ybl has been placed urgently. Amount Rs.420 paid successfully.")
    assert flagged["is_scam"] is False  # single red flag, no scam_type keyword -- still legit
    assert flagged["confidence"] < calm["confidence"]


# ── Hinglish coverage (CLAUDE.md §15 G4) ─────────────────────────────────
# The rules-floor classifier is the fallback if the LLM path is unavailable
# (venue network dies, no API key) -- and a Hinglish paste is a likely judge
# probe. One Hinglish variant was appended to each SCAM_TEMPLATES[scam_type]
# list, so it's always the *last* template for that type.

@pytest.mark.parametrize("scam_type", list(SCAM_TEMPLATES.keys()))
def test_classify_recovers_scam_type_for_hinglish_template(scam_type):
    hinglish_template = SCAM_TEMPLATES[scam_type][-1]
    text = render(hinglish_template, amount=9000, upi="mule@okaxis", phone="9812345678")
    result = classify(text)
    assert result["is_scam"] is True, text
    assert result["scam_type"] == scam_type, text


@pytest.mark.parametrize("scam_type", list(SCAM_TEMPLATES.keys()))
def test_extract_entities_recovers_identifiers_from_hinglish_template(scam_type):
    hinglish_template = SCAM_TEMPLATES[scam_type][-1]
    text = render(hinglish_template, amount=9000, upi="mule@okaxis", phone="9812345678")
    e = extract_entities(text)
    assert e["payee_upi"] == ["mule@okaxis"]
    assert e["amount"] == 9000


def test_hinglish_digital_arrest_fires_authority_and_threat_flags():
    text = render(SCAM_TEMPLATES["digital_arrest"][-1], amount=45000, upi="fraud@okhdfc")
    flags = detect_red_flags(text)
    assert "authority_impersonation" in flags
    assert "threat" in flags
    assert "urgency" in flags


def test_hinglish_relative_distress_recovered_via_hindi_keywords_not_english():
    # The English keywords ("mom", "lost my phone", ...) don't appear in the
    # Hinglish text at all -- this only passes if the Hinglish keywords added
    # to classify.py's _SCAM_TYPE_KEYWORDS are doing the work.
    text = render(SCAM_TEMPLATES["relative_distress"][-1], amount=15000, upi="mule@okaxis")
    result = classify(text)
    assert result["is_scam"] is True
    assert result["scam_type"] == "relative_distress"


@pytest.mark.parametrize("text", [
    "Mummy I reached home, call me when free",
    "Mummy khana bhej do ghar pe",
    "Mummy se poochh ke bataunga",
])
def test_everyday_hinglish_family_texts_stay_legit(text):
    # regression for CLAUDE.md B10: "mummy"/"bataunga" as scam_type keywords
    # scored ordinary family texts as relative_distress scams -- single
    # high-frequency Hindi words are not scam evidence (UCI is English-only,
    # so its FP number could never have caught this class).
    result = classify(text)
    assert result["is_scam"] is False
    assert result["scam_type"] == "legit"


def test_moment_does_not_match_the_mom_keyword():
    # same substring class as B1: bare "mom" matched inside "moment".
    result = classify("Just a moment, I'll send it now")
    assert result["is_scam"] is False
    assert result["scam_type"] == "legit"


@pytest.mark.parametrize("text", [
    "Can I please get a small loan from you? I'll pay you back by February.",
    "i see. When we finish we have loads of loans to pay",
    "My rent is due and I don't have enough. It's a loan I need, I hope to pay back by March.",
])
def test_friend_to_friend_money_requests_stay_legit(text):
    # regression for CLAUDE.md B11: bare "loan" scored any mention of the word
    # as loan_app, and bare "pay " fired payment_demand on "pay you back" --
    # every residual UCI ham false positive was this combination.
    result = classify(text)
    assert result["is_scam"] is False
    assert result["scam_type"] == "legit"


def test_loan_offer_scam_still_caught_after_keyword_tightening():
    result = classify(
        "Congratulations! Your personal loan is pre-approved. Pay a processing fee of Rs.999 to claim."
    )
    assert result["is_scam"] is True
    assert result["scam_type"] == "loan_app"


def test_pay_back_does_not_fire_payment_demand_but_a_demand_does():
    # the flag is citizen-facing ("why was this flagged?") -- it must mean a
    # demand for payment, not any occurrence of the verb (CLAUDE.md B11).
    assert "payment_demand" not in detect_red_flags("I'll pay you back tomorrow, promise")
    assert "payment_demand" in detect_red_flags("Pay Rs.2000 to resolve this immediately")


@pytest.mark.parametrize("text", [
    "Stuck at customs at the airport, flight got delayed",       # customs: keyword + authority flag
    "I guaranteed him I would be there by 5",                    # guaranteed: keyword + too_good flag
    "We are doing a lucky draw at the office party tomorrow",    # lucky draw: keyword + too_good flag
    "He got pre-approved for the home loan finally, great news",  # pre-approved: keyword + too_good flag
    "Did you see the ED investigation news today?",              # ed investigation: keyword + authority flag
    "My parcel arrived, the courier guy called twice",           # two correlated delivery nouns, zero flags
])
def test_double_counted_terms_do_not_alone_make_a_scam_verdict(text):
    # regression for CLAUDE.md B13: several terms sit in BOTH a scam_type
    # keyword list and a red-flag list, so one word counted as keyword AND
    # corroborating flag -- and two correlated nouns of one type passed the
    # old bare score>=2 branch with no flags at all. Corroboration must be
    # independent: it has to survive masking the type's own keywords.
    result = classify(text)
    assert result["is_scam"] is False
    assert result["scam_type"] == "legit"


def test_one_keyword_with_an_independent_red_flag_is_still_a_scam():
    # the B13 gate must not overshoot: a single scam-type keyword corroborated
    # by evidence in OTHER words (urgency + a link here) is still a scam.
    result = classify(
        "Your KYC expires today, verify at http://kyc-update.xyz immediately",
        {"url": ["http://kyc-update.xyz"]},
    )
    assert result["is_scam"] is True
    assert result["scam_type"] == "kyc_update"


# ── llm.py (must degrade cleanly when unconfigured) ─────────────────────

def test_classify_with_llm_returns_none_without_api_key(monkeypatch):
    monkeypatch.delenv("GROQ_API_KEY", raising=False)
    assert classify_with_llm("anything") is None


def _groq_response(raw_text):
    """Groq's chat.completions response shape (OpenAI-style):
    response.choices[0].message.content."""
    message = types.SimpleNamespace(content=raw_text)
    return types.SimpleNamespace(choices=[types.SimpleNamespace(message=message)])


def _install_fake_groq_client(monkeypatch, create):
    fake_module = types.ModuleType("groq")
    fake_module.Groq = lambda api_key: types.SimpleNamespace(
        chat=types.SimpleNamespace(completions=types.SimpleNamespace(create=create)))
    monkeypatch.setitem(sys.modules, "groq", fake_module)
    monkeypatch.setenv("GROQ_API_KEY", "fake-key-for-tests")


def _install_fake_groq(monkeypatch, payload):
    """Stubs `from groq import Groq` inside llm.classify_with_llm so tests
    can feed it a scripted (possibly malformed) model response without a
    real API key or network call."""
    _install_fake_groq_raw(monkeypatch, json.dumps(payload))


def _install_fake_groq_raw(monkeypatch, raw_text):
    """Like _install_fake_groq, but the response body is `raw_text`
    verbatim -- for responses that parse as JSON but aren't a dict."""
    _install_fake_groq_client(monkeypatch, lambda **kw: _groq_response(raw_text))


def _install_fake_groq_raising(monkeypatch, exc):
    """The API call itself fails -- network outage, stale key, rate limit."""
    def _raise(**kwargs):
        raise exc
    _install_fake_groq_client(monkeypatch, _raise)


# regression for CLAUDE.md B2: a plausible-looking but out-of-contract LLM
# verdict must be sanitised, not passed raw into Report.model_validate.

def test_classify_with_llm_clamps_out_of_range_confidence(monkeypatch):
    _install_fake_groq(monkeypatch, {
        "is_scam": True, "confidence": 1.7, "scam_type": "kyc_update", "red_flags": [],
    })
    result = classify_with_llm("anything")
    assert result["confidence"] == 1.0


def test_classify_with_llm_filters_unknown_red_flags(monkeypatch):
    _install_fake_groq(monkeypatch, {
        "is_scam": True, "confidence": 0.8, "scam_type": "kyc_update",
        "red_flags": ["impersonation", "urgency"],
    })
    result = classify_with_llm("anything")
    assert result["red_flags"] == ["urgency"]


def test_classify_with_llm_coerces_scam_type_when_not_scam(monkeypatch):
    _install_fake_groq(monkeypatch, {
        "is_scam": False, "confidence": 0.9, "scam_type": "kyc_update", "red_flags": [],
    })
    result = classify_with_llm("anything")
    assert result["scam_type"] in ("legit", "other")


# regression for CLAUDE.md B9: `classify_with_llm`'s own contract is
# "returns None -- never raises -- when it can't run", but with a key SET it
# crashed detect() on an API failure or a structurally weird response, which
# is worse than having no key at all (a stale demo-day .env would take the
# whole citizen tool down instead of degrading to the rules floor).

def test_classify_with_llm_returns_none_when_the_api_call_raises(monkeypatch):
    _install_fake_groq_raising(monkeypatch, ConnectionError("venue wifi down"))
    assert classify_with_llm("anything") is None


def test_classify_with_llm_returns_none_on_valid_json_that_is_not_a_dict(monkeypatch):
    _install_fake_groq_raw(monkeypatch, '"just a string"')
    assert classify_with_llm("anything") is None


def test_classify_with_llm_defaults_a_non_numeric_confidence(monkeypatch):
    _install_fake_groq(monkeypatch, {
        "is_scam": True, "confidence": "high", "scam_type": "kyc_update", "red_flags": [],
    })
    result = classify_with_llm("anything")
    assert result["confidence"] == 0.5


def test_classify_with_llm_ignores_a_non_list_red_flags(monkeypatch):
    _install_fake_groq(monkeypatch, {
        "is_scam": True, "confidence": 0.9, "scam_type": "kyc_update", "red_flags": 7,
    })
    result = classify_with_llm("anything")
    assert result["red_flags"] == []


def test_classify_with_llm_drops_a_non_string_device_hint(monkeypatch):
    # device_hint lands in `entities`, which detect()'s ValidationError
    # fallback does NOT replace -- unsanitised, a non-string here failed BOTH
    # validation attempts and crashed the report.
    _install_fake_groq(monkeypatch, {
        "is_scam": True, "confidence": 0.9, "scam_type": "kyc_update",
        "red_flags": [], "device_hint": 42,
    })
    result = classify_with_llm("anything")
    assert result["device_hint"] is None


# regression for CLAUDE.md B19: a device_hint becomes a `device:` graph node,
# and a shared node is a Layer 1 HARD CONNECTION -- the evidence pack's proof
# surface. Asked for a free-form "string or null", the model returns
# "video_call" for any digital-arrest message ("do not disconnect the video
# call"), which would link every unrelated victim of that pretext into one
# false ring. Only individuating values may become device nodes.

@pytest.mark.parametrize("hint", ["video_call", "video call", "phone call",
                                  "whatsapp", "mobile", "Samsung"])
def test_classify_with_llm_drops_a_device_hint_that_identifies_no_device(monkeypatch, hint):
    _install_fake_groq(monkeypatch, {
        "is_scam": True, "confidence": 0.9, "scam_type": "digital_arrest",
        "red_flags": [], "device_hint": hint,
    })
    assert classify_with_llm("anything")["device_hint"] is None


@pytest.mark.parametrize("hint", ["adv-device-rotator-01", "AnyDesk 123 456 789",
                                  "IMEI 358240051111110", "Redmi Note 12"])
def test_classify_with_llm_keeps_a_device_hint_that_identifies_one_device(monkeypatch, hint):
    _install_fake_groq(monkeypatch, {
        "is_scam": True, "confidence": 0.9, "scam_type": "digital_arrest",
        "red_flags": [], "device_hint": hint,
    })
    assert classify_with_llm("anything")["device_hint"] == hint


def test_a_shared_channel_word_does_not_forge_a_hard_connection(monkeypatch):
    """The end-to-end consequence: two unrelated digital-arrest victims, no
    shared payee/phone/account, both told not to hang up the video call. They
    must NOT come out as a ring."""
    _install_fake_groq(monkeypatch, {
        "is_scam": True, "confidence": 0.95, "scam_type": "digital_arrest",
        "red_flags": ["threat"], "device_hint": "video_call",
    })
    a = detect("CBI here. Do not disconnect the video call. Pay Rs 1000 to aaa@okaxis.",
               channel="whatsapp")
    b = detect("CBI here. Do not disconnect the video call. Pay Rs 9000 to zzz@okhdfc.",
               channel="whatsapp")
    assert a.entities.device_hint is None and b.entities.device_hint is None
    assert detect_rings(build_graph([a, b])) == []


# regression for CLAUDE.md B12: membership tests against the _VALID_* sets
# hash their operand, so an unhashable scam_type or red_flags element (a
# dict/list from the model) raised TypeError past every B2/B9 guard and
# crashed detect() end-to-end with a key set.

def test_classify_with_llm_survives_unhashable_red_flag_elements(monkeypatch):
    _install_fake_groq(monkeypatch, {
        "is_scam": True, "confidence": 0.9, "scam_type": "kyc_update",
        "red_flags": [{"flag": "urgency"}, ["urgency"], "urgency"],
    })
    result = classify_with_llm("anything")
    assert result["red_flags"] == ["urgency"]


def test_classify_with_llm_coerces_an_unhashable_scam_type(monkeypatch):
    _install_fake_groq(monkeypatch, {
        "is_scam": True, "confidence": 0.9, "scam_type": ["digital_arrest"], "red_flags": [],
    })
    result = classify_with_llm("anything")
    assert result["scam_type"] == "other"


def test_detect_survives_unhashable_llm_verdict_fields(monkeypatch):
    _install_fake_groq(monkeypatch, {
        "is_scam": True, "confidence": 0.9, "scam_type": {"t": 1},
        "red_flags": [{"flag": "urgency"}], "device_hint": None,
    })
    report = detect("Pay Rs.5000 to fraud@okhdfc immediately or face arrest", use_llm=True)
    assert report.verdict.is_scam is True  # must not raise


def test_detect_survives_an_api_outage_with_a_key_set(monkeypatch):
    _install_fake_groq_raising(monkeypatch, ConnectionError("venue wifi down"))
    text = "Your order from zomato@ybl has been placed. Amount Rs.420 paid successfully."
    report = detect(text, use_llm=True)  # must fall back to rules, not raise
    assert report.verdict.is_scam is False
    assert report.verdict.scam_type == "legit"


def test_classify_with_llm_returns_none_when_client_construction_raises(monkeypatch):
    # regression for CLAUDE.md B16: Groq() builds an httpx client at
    # construction time, which parses proxy env vars -- a malformed
    # HTTP_PROXY on the venue laptop raised httpx.InvalidURL *before* the
    # call-site try block and crashed detect() (reproduced with the real
    # SDK). Construction failures must degrade exactly like call failures.
    def _exploding_ctor(api_key):
        raise ValueError("Invalid port: ':'")
    fake_module = types.ModuleType("groq")
    fake_module.Groq = _exploding_ctor
    monkeypatch.setitem(sys.modules, "groq", fake_module)
    monkeypatch.setenv("GROQ_API_KEY", "fake-key-for-tests")
    assert classify_with_llm("anything") is None
    report = detect("Your order from zomato@ybl has been placed. Amount Rs.420 paid successfully.")
    assert report.verdict.is_scam is False  # rules floor, not a crash


def test_suite_never_sees_a_real_llm_key():
    # regression for CLAUDE.md B15: detect() defaults to use_llm=True, so a
    # real GROQ_API_KEY in the demo machine's env (or the auto-loaded .env,
    # B8) made every unmocked detect() test fire real network calls --
    # nondeterministic verdicts and rate limits on exactly the machine where
    # a green suite matters most. tests/conftest.py must strip the key.
    assert "GROQ_API_KEY" not in os.environ


def test_detect_end_to_end_survives_malformed_llm_output(monkeypatch):
    _install_fake_groq(monkeypatch, {
        "is_scam": False, "confidence": 1.5, "scam_type": "totally_unknown_type",
        "red_flags": ["not_a_real_flag"],
    })
    text = "Your order from zomato@ybl has been placed. Amount Rs.420 paid successfully."
    report = detect(text, use_llm=True)  # must not raise ValidationError
    assert report.verdict.is_scam is False


def test_detect_falls_back_to_rules_if_llm_output_still_fails_validation(monkeypatch):
    # Defence in depth: even if a future change to llm.py reintroduces a raw,
    # unsanitised verdict, detect() must not crash -- it should fall back to
    # the deterministic classifier (CLAUDE.md B2).
    def _broken_classify_with_llm(text, **kwargs):
        return {"is_scam": False, "confidence": 5.0, "scam_type": "kyc_update", "red_flags": []}

    monkeypatch.setattr(sys.modules["src.detector.detect"], "classify_with_llm", _broken_classify_with_llm)
    text = "Your order from zomato@ybl has been placed. Amount Rs.420 paid successfully."
    report = detect(text, use_llm=True)
    assert report.verdict.is_scam is False
    assert report.verdict.scam_type == "legit"


def test_active_classifier_path_is_rules_without_a_key(monkeypatch):
    monkeypatch.delenv("GROQ_API_KEY", raising=False)
    assert active_classifier_path() == "rules"


def test_active_classifier_path_is_llm_with_key_and_package(monkeypatch):
    _install_fake_groq(monkeypatch, {})
    assert active_classifier_path() == "llm"


def test_active_classifier_path_is_rules_when_package_missing(monkeypatch):
    monkeypatch.setenv("GROQ_API_KEY", "fake-key-for-tests")
    monkeypatch.setitem(sys.modules, "groq", None)  # makes `from groq import Groq` raise
    assert active_classifier_path() == "rules"


def test_llm_module_calls_load_dotenv_on_import(monkeypatch):
    # regression for CLAUDE.md B8: python-dotenv was a declared dependency
    # but load_dotenv() was never called anywhere, so a demo-day .env with
    # the API key was silently ignored. Spy on dotenv.load_dotenv
    # rather than asserting on real file discovery, since load_dotenv()'s
    # default search walks up from the *module's* location, not the cwd.
    calls = []
    monkeypatch.setattr("dotenv.load_dotenv", lambda *a, **k: calls.append((a, k)))

    import src.detector.llm as llm_module
    importlib.reload(llm_module)
    assert len(calls) == 1

    monkeypatch.undo()
    importlib.reload(llm_module)  # restore the real load_dotenv binding


# ── detect() orchestrator ────────────────────────────────────────────────

def test_detect_returns_schema_valid_report():
    text = render(SCAM_TEMPLATES["digital_arrest"][0], amount=45000, upi="fraud@okhdfc")
    report = detect(text, channel="sms")
    assert report.raw_text == text
    assert report.verdict.is_scam is True
    assert report.entities.payee_upi == ["fraud@okhdfc"]
    assert report.gt is None  # detector never fabricates ground truth


def test_detect_falls_back_to_rules_without_api_key(monkeypatch):
    monkeypatch.delenv("GROQ_API_KEY", raising=False)
    text = "Your order from zomato@ybl has been placed. Amount Rs.420 paid successfully."
    report = detect(text, use_llm=True)  # asks for LLM but none is configured
    assert report.verdict.is_scam is False
    assert report.verdict.scam_type == "legit"


def test_detect_requires_tz_and_defaults_timestamp():
    report = detect("hello")
    assert report.timestamp.tzinfo is not None


# ── guidance() ────────────────────────────────────────────────────────────

def test_guidance_for_scam_mentions_1930_and_no_payment():
    text = render(SCAM_TEMPLATES["digital_arrest"][0], amount=45000, upi="fraud@okhdfc")
    report = detect(text)
    msg = guidance(report)
    assert "1930" in msg
    assert "not pay" in msg.lower()


def test_guidance_for_legit_is_reassuring_not_alarming():
    report = detect("Your order from zomato@ybl has been placed. Amount Rs.420 paid successfully.")
    msg = guidance(report)
    assert "1930" not in msg


# ── integration: detect() against the generated answer-key corpus ───────

def test_detect_matches_generated_corpus_ground_truth():
    reports = generate_messages(seed=0, n_rings=6, kingpin_ring_count=3, n_legit=40)
    correct_is_scam = 0
    correct_upi = 0
    scam_count = 0
    for gt_report in reports:
        redetected = detect(gt_report.raw_text, channel=gt_report.channel, use_llm=False)
        correct_is_scam += redetected.verdict.is_scam == gt_report.verdict.is_scam
        if gt_report.verdict.is_scam:
            scam_count += 1
            correct_upi += redetected.entities.payee_upi == gt_report.entities.payee_upi

    assert correct_is_scam == len(reports)  # rules classifier matches the template generator exactly
    assert correct_upi == scam_count  # every scam UPI is recovered verbatim


# --- entity_spans: the app highlights these IN the message bubble, so a span
# that disagrees with extract_entities would show the judge a different set of
# identifiers than the graph actually runs on.

_SPAN_TEXT = (
    "CBI: parcel seized. Pay Rs 50,000 to mule00@okaxis or call 98765 43210. "
    "Account 12349876543210, IFSC HDFC0001234, details at https://cbi-verify.in/x"
)


def test_entity_spans_agree_exactly_with_extract_entities():
    spans = entity_spans(_SPAN_TEXT)
    entities = extract_entities(_SPAN_TEXT)
    by_kind: dict[str, list[str]] = {}
    for s in spans:
        by_kind.setdefault(s.kind, []).append(s.value)

    for kind in ("payee_upi", "phone", "account", "ifsc", "url"):
        assert sorted(set(by_kind.get(kind, []))) == entities[kind], kind
    amount = next(s for s in spans if s.kind == "amount")
    assert int(amount.value.split()[-1].replace(",", "")) == entities["amount"]


def test_entity_spans_are_non_overlapping_and_slice_the_original_text():
    spans = entity_spans(_SPAN_TEXT)
    assert spans == sorted(spans, key=lambda s: s.start)
    for a, b in zip(spans, spans[1:]):
        assert a.end <= b.start  # overlapping spans would corrupt the rendered HTML
    for s in spans:
        assert _SPAN_TEXT[s.start : s.end] == s.value


def test_entity_spans_empty_for_text_with_no_identifiers():
    assert entity_spans("Hey, just reached home. Talk tomorrow!") == []
