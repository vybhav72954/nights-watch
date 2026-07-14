# app — web demo (Streamlit)

Pure-Streamlit single-process demo (design: `docs/APP_DESIGN.md`; demo flow:
`docs/DEMO_SCRIPT.md`). Two pages — a **citizen chat detector** (the sensor) and a
**command-centre dashboard** (live ring graph + kingpin leads + evidence packs +
threshold slider + validation). Web, not mobile. Do NOT integrate real WhatsApp.

Run from the repo root:

```
streamlit run app/streamlit_app.py
```

Works with no API key and no internet (deterministic rules-floor classifier, graph
assets inlined). With `GROQ_API_KEY` in `.env`, the detector uses the LLM path and
falls back to rules on any failure.

```
streamlit_app.py    entry: navigation, session state, classifier badge
core.py             cached seeded network, graph assembly, pyvis rendering
app_pages/
  citizen.py        beat 1  — chat → verdict card + guidance
  command_centre.py beats 2–5 — Network / Kingpins / Evidence / Validation tabs
```
