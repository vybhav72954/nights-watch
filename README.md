# Night's Watch — Digital Public Safety Intelligence

*"The shield that guards the realms of men."*

*"AI for Digital Public Safety: Defeating Counterfeiting, Fraud & Digital Arrest Scams."*

**Detect → Link → Prove.** A consent-first platform that turns individual citizen scam
reports into coordinated-ring intelligence:

1. **Detect** — paste a suspicious message or call transcript; get a scam verdict, the red
   flags it fired on, and what to do (don't pay; report to 1930). Every check becomes a
   structured report.
2. **Link** — the identifiers in those reports (payee UPI, phone, account, device) feed a
   fraud-network graph that clusters incidents into **scam rings** and ranks the **kingpin**.
3. **Prove** — a two-layer evidence pack: deterministic hard-connection clusters (the legal
   proof) + a kingpin prioritisation score (a lead, not proof), with a live precision/recall
   threshold.

## Why it's different

- **Court-admissible by design** — the proof layer is deterministic shared-connection
  evidence; the AI score is explicitly labelled a lead, not proof.
- **Low false-positive** — alerts fire on *co-occurrence of independent hard connections*,
  which is rare among legitimate users; a legit-high-degree guardrail proves popular ≠ fraud.
- **Provable** — validated on planted scam networks with a known answer key, so the kingpin
  ranking can be checked against ground truth (not just asserted).

## Status

Pipeline, evidence layer, and web demo built and tested (full pytest suite green; the app
runs offline with no API key). See `CLAUDE.md` for the master plan and `docs/` for detailed
specs: `SOLUTION_DESIGN.md`, `REPORT_SCHEMA.md`, `DATASETS.md`, `DEMO_SCRIPT.md`.

## Scope

Financial-network + text-scam intelligence. **Out of scope by design:** counterfeit-currency
computer vision and any call-tapping / location-tracking (consent-first, text-in only).

## Quickstart

```bash
python -m venv .venv && .venv/Scripts/activate   # or reuse uv
pip install -r requirements.txt
streamlit run app/streamlit_app.py
```

Built on the controlled fraud-injection + GraphSAGE ring engine
(`docs/reference/engine_story.html`).
