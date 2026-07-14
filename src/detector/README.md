# src/detector — Detect (the sensor)

Text in → scam verdict + red flags + guidance + a `Report` (schema). Two jobs:
(1) classify scam/legit with a red-flag breakdown; (2) **extract + normalise entities**
(UPI/phone/account/IFSC/url/amount/device) — this is what the graph consumes. See
`docs/SOLUTION_DESIGN.md` §2.

## Status

Implemented and tested (`tests/test_detector.py`, 29 tests — including an integration
check that redetects every message in `src/generate/messages.py`'s answer-key corpus
and confirms `is_scam` matches the planted ground truth exactly and every scam UPI is
recovered verbatim):

- **`entities.py`** — regex-only extraction (payee_upi, phone, account, ifsc, url,
  amount). Deliberately has no LLM dependency: the graph must work with zero API keys
  configured. A `_SpanClaims` tracker stops e.g. a 10-digit phone number from also
  matching the account-number pattern. `amount` uses a proximity heuristic (nearest to
  a payment-verb like "pay"/"fee"/"deposit") to pick the *demanded* amount over a lure
  amount when a message contains more than one (see the lottery/loan templates, which
  both mention a bigger "prize"/"loan" figure alongside the actual fee being asked for).
- **`red_flags.py`** — keyword/phrase rules per `docs/REPORT_SCHEMA.md` §5 flag. Notably
  `otp_request` requires "share" near "otp" (not just "otp" appearing) with an explicit
  negation check, so a bank's own "here is your OTP, don't share it" notice doesn't trip
  it — only a message *asking* the recipient to hand the OTP over does.
- **`classify.py`** — deterministic scam_type/is_scam classifier: a keyword score per
  `scam_type` plus the red-flag count. This is the always-available floor, not a stand-in
  for "LLM-backed" — see `llm.py`.
- **`llm.py`** — optional Groq-backed classification. Returns `None` (never raises) when
  `GROQ_API_KEY` isn't set or `groq` isn't installed — neither is guaranteed in
  every dev environment, so `detect()` must degrade to `classify.py` cleanly. Only ever
  asked for `scam_type`/`device_hint`/verdict refinement, never entities — identifiers
  stay regex-sourced so a hallucinated UPI can never reach the graph.
- **`guidance.py`** — citizen-facing text (not part of the `Report` schema — pure UX,
  never consumed downstream).
- **`detect.py`** — orchestrates the above into a schema-valid `Report`.

Verified end to end against a pre-seeded network (`src/generate/network.py`): a live
`detect()` call whose extracted `payee_upi` matches a seeded mule UPI visibly joins that
ring and the kingpin ranking stays correct — this is the exact demo mechanic in
CLAUDE.md §8.
