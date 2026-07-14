"""Optional Groq-backed classification (CLAUDE.md §4.1's "LLM-backed").

Not installed/configured in every environment (`groq` isn't always present,
no API key is checked into the repo), so this must degrade cleanly:
`classify_with_llm` returns `None` -- never raises -- when it can't run, and
`detect()` falls back to the deterministic `classify.py` rules. Same pattern
already used for RingSAGE (`src/graph/README.md`) and message paraphrase
(`src/generate/messages.py`): build the honest deterministic core first,
wire the model in as a strict enhancement over it.

Never let the model see `_gt` (there is none here -- this takes raw text
only) and never let it invent identifiers: this function does NOT return
entities. Entity extraction stays regex-only (`entities.py`); the LLM is
only ever asked for `scam_type` / `device_hint` / verdict refinement, per
docs/SOLUTION_DESIGN.md §2.
"""
from __future__ import annotations

import json
import os
from typing import get_args

from dotenv import load_dotenv

from src.schema.report import RedFlag, ScamType

# `.env` (gitignored, holds GROQ_API_KEY on the demo machine) was never
# actually loaded anywhere -- os.environ.get below would silently see nothing
# and fall back to the rules floor even with a valid key on disk (CLAUDE.md
# B8). Loading it here, at the one place the key is read, covers every entry
# point (tests, notebooks, the future app backend) without each needing to
# remember to call it themselves.
load_dotenv()

_VALID_SCAM_TYPES = set(get_args(ScamType))
_VALID_RED_FLAGS = set(get_args(RedFlag))

_SYSTEM_PROMPT = (
    "You are a scam-message classifier for an Indian public-safety tool. "
    "Given a raw SMS/WhatsApp/call-transcript message, decide if it is a scam "
    "and classify it. Respond with ONLY a JSON object with keys: "
    'is_scam (bool), confidence (0..1 float), '
    'scam_type (one of: digital_arrest, parcel_customs, kyc_update, lottery_prize, '
    'relative_distress, loan_app, investment, other, legit), '
    'red_flags (list, subset of: urgency, authority_impersonation, payment_demand, '
    'threat, secrecy, suspicious_link, too_good_to_be_true, otp_request, '
    'remote_access_request), '
    'device_hint (string or null -- ONLY a value that identifies one specific '
    "device or remote-access session named in the message: an IMEI, a device id, "
    "an AnyDesk/TeamViewer session id, a handset model number. It is NOT the "
    'contact channel: never answer "video call", "phone call", "whatsapp". '
    "Use null if the message names no such device). "
    "Do not invent phone numbers, UPI IDs, or amounts -- that is handled elsewhere."
)


def _individuates_a_device(value: str) -> bool:
    """A `device_hint` becomes a `device:` graph node, and a shared node is a
    Layer 1 HARD CONNECTION -- the thing the evidence pack puts before a court.
    So it has to identify one device, not describe the channel.

    Asked for a free-form "string or null", the model returns "video_call" for
    any digital-arrest message ("do not disconnect the video call"). That would
    link every unrelated victim of that pretext into one false ring, on the
    proof surface -- the same false-hard-edge class as B17's emails-as-UPIs.

    Individuating values (IMEI, device ids, AnyDesk session ids, model numbers)
    carry a digit; channel words and bare brand names ("video call", "mobile",
    "Samsung") do not. Deliberately conservative: this can only ever drop a weak
    identifier, never invent one, and Layer 1 is the layer that must not guess.
    """
    return any(ch.isdigit() for ch in value)


def active_classifier_path() -> str:
    """`"llm"` when the Groq path can actually run (key present and the
    `groq` package importable), else `"rules"`. For the app backend's
    startup log (CLAUDE.md B8/§16) -- the demo-day failure this prevents is
    silently running on the rules floor with a `.env` everyone assumed was
    loaded."""
    if not os.environ.get("GROQ_API_KEY"):
        return "rules"
    try:
        import groq  # noqa: F401
    except ImportError:
        return "rules"
    return "llm"


def classify_with_llm(text: str, *, model: str = "llama-3.3-70b-versatile") -> dict | None:
    """Returns a dict shaped like `Verdict` (+ optional `device_hint`), or
    `None` when the LLM path can't produce one: no API key, no `groq`
    package, the API call fails (network outage, stale key, rate limit), or
    the response isn't usable JSON -- the caller (`detect.py`) must fall back
    to `classify.py`."""
    api_key = os.environ.get("GROQ_API_KEY")
    if not api_key:
        return None
    try:
        from groq import Groq
    except ImportError:
        return None

    try:
        # Client construction itself can raise: the underlying httpx client
        # parses proxy env vars at build time, so a malformed HTTP_PROXY on
        # the venue laptop raised httpx.InvalidURL here, past B9's guard on
        # the call alone (CLAUDE.md B16) -- construction failures are the
        # same class as call failures, degrade identically.
        client = Groq(api_key=api_key)
        # json_object mode guarantees syntactically valid JSON from the real
        # API (Groq requires the word "JSON" in the prompt -- the system
        # prompt satisfies that) but NOT our schema, so every sanitiser
        # below stays. Response extraction sits inside the try: an empty
        # choices list or a None content is the same class of failure as
        # the call itself failing (CLAUDE.md B9 -- degrade, never crash).
        response = client.chat.completions.create(
            model=model,
            max_tokens=512,
            response_format={"type": "json_object"},
            messages=[
                {"role": "system", "content": _SYSTEM_PROMPT},
                {"role": "user", "content": text},
            ],
        )
        raw = response.choices[0].message.content or ""
    except Exception:
        # A configured key is no guarantee the path works: venue network down,
        # stale key, rate limit (CLAUDE.md B9). Same contract as no key at all
        # -- degrade to the rules floor, never crash the citizen's report.
        return None
    try:
        parsed = json.loads(raw)
    except json.JSONDecodeError:
        return None
    if not isinstance(parsed, dict):
        return None

    # The model's output is untrusted input to `Report.model_validate`
    # (CLAUDE.md B2/B9) -- a plausible-looking but out-of-contract verdict
    # (confidence > 1 or non-numeric, an unknown scam_type, a made-up or
    # non-list red_flags, is_scam=False paired with a real scam_type, or a
    # non-string device_hint) must not reach it raw. device_hint matters
    # doubly: it lands in `entities`, which detect()'s ValidationError
    # fallback does NOT replace -- a bad value there fails both attempts.
    is_scam = bool(parsed.get("is_scam", False))
    try:
        confidence = max(0.0, min(1.0, float(parsed.get("confidence", 0.5))))
    except (TypeError, ValueError):
        confidence = 0.5
    # Membership tests against the _VALID_* sets hash their operand -- an
    # unhashable scam_type or red_flags element (a dict/list from the model)
    # raised TypeError right here, past every earlier guard (CLAUDE.md B12).
    scam_type = parsed.get("scam_type", "other")
    if not isinstance(scam_type, str):
        scam_type = "other"
    if not is_scam:
        if scam_type not in ("legit", "other"):
            scam_type = "legit"
    elif scam_type not in _VALID_SCAM_TYPES:
        scam_type = "other"
    raw_flags = parsed.get("red_flags", [])
    red_flags = (
        [f for f in raw_flags if isinstance(f, str) and f in _VALID_RED_FLAGS]
        if isinstance(raw_flags, list) else []
    )
    device_hint = parsed.get("device_hint")
    if not isinstance(device_hint, str) or not _individuates_a_device(device_hint):
        device_hint = None

    return {
        "is_scam": is_scam,
        "confidence": confidence,
        "scam_type": scam_type,
        "red_flags": red_flags,
        "device_hint": device_hint,
    }
