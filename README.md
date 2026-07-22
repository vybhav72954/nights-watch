# Night's Watch — Digital Public Safety Intelligence

*"The shield that guards the realms of men."*

*"AI for Digital Public Safety: Defeating Counterfeiting, Fraud & Digital Arrest Scams."*

Repository: <https://github.com/vybhav72954/nights-watch>

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
  evidence; the AI score is explicitly labelled a lead, not proof. Packs carry per-incident
  and pack-level SHA-256 hashes, the exact detection parameters read off the ring itself,
  and a Section 63 (Bharatiya Sakshya Adhiniyam 2023) certificate block.
- **Low false-positive** — alerts fire on *co-occurrence of independent hard connections*,
  which is rare among legitimate users; a legit-high-degree guardrail proves popular ≠ fraud.
- **Provable** — validated on planted scam networks with a known answer key, so the kingpin
  ranking can be checked against ground truth (not just asserted).

## Measured

Every number below is produced by code in this repo and regenerable from it.

| Result | Measurement |
|---|---|
| False alarms, real SMS | 0 / 4,825 (UCI); 4 / 55,835 (NUS, never tuned against) |
| Digital arrest detection | rules floor P/R 1.00 (recovers a planted key); LLM path P 0.82 / R 0.90 |
| Ring recovery | precision and recall 1.00, sd 0.00, across 20 seeded networks |
| Kingpin | planted cross-ring controller ranked first in 20 / 20 |
| Lead time | largest seeded ring detectable at report 2 of 30; 89.7% of its loss falls after |
| Counterfeit circulation | rings recovered P/R 1.00 over 20 seeds; laundering courier first in 20 / 20 |
| Throughput | 50,600 reports end to end in 17.7 s on a laptop |
| Tests | 246, green offline and on the live language-model path |

Regenerate: `python -m src.evidence.validate`, `python -m src.detector.eval_uci`,
`python -m src.detector.eval_nus`, `python -m src.detector.eval_digital_arrest`,
`python -m src.counterfeit.validate`.

## Status

Pipeline, evidence layer, and web demo built and tested (full pytest suite green; the app
runs offline with no API key). The demo has four pages: Live (chat plus network on one
screen), Command centre, Counterfeit, and Lead time.

Submission artifacts live in `assets/`: `report.pdf` (the formal project report),
`architecture.pdf`, `deck.pdf`, `pr_curve.png`, `scale_benchmark.png`. See `CLAUDE.md` for
the master plan and `docs/` for detailed specs: `SOLUTION_DESIGN.md`, `REPORT_SCHEMA.md`,
`DATASETS.md`, `DEMO_SCRIPT.md`.

## Scope

Financial-network + text-scam intelligence, including **counterfeit-currency circulation
intelligence** (seizure records sharing a reused plate serial cluster into a circulation
ring; the laundering courier surfaces as the prioritisation lead). **Out of scope by
design:** note-image computer vision, which is stated rather than faked because no labelled
genuine-versus-fake dataset backs it, and any call-tapping or location-tracking
(consent-first, text-in only).

## Quickstart

```bash
python -m venv .venv && .venv/Scripts/activate   # or reuse uv
pip install -r requirements.txt
streamlit run app/streamlit_app.py
```

The app runs with no API key on a deterministic rules floor. Set `GROQ_API_KEY` in `.env`
to enable the language-model classifier path.

Built on the controlled fraud-injection + GraphSAGE ring engine
(`docs/reference/engine_story.html`).
