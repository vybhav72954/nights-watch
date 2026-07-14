# src/evidence — Prove (court-admissible layer)

Two layers: **Layer 1** deterministic hard-connection evidence pack (the proof); **Layer 2**
kingpin score (a lead, *not* proof). Guardrails: legit-high-degree hub, adversarial split,
precision/recall threshold slider. Validate ring recovery + kingpin hit-rate vs the
injection answer key. **FDR is cut** — see `CLAUDE.md` §8. Details: `docs/SOLUTION_DESIGN.md` §4.

## Status

Implemented and tested (`tests/test_evidence.py`, 13 tests — built against
`src/generate/network.py`/`messages.py`'s planted answer key, not hand-picked examples):

- **`pack.py`** — Layer 1 evidence pack for one `Ring`: every incident (report_id,
  timestamp, channel, scam_type, amount, raw_text) + every shared identifier and which
  reports use it, plus a narrative. Exports to `.json` (structured, re-parseable), `.md`
  (readable), and `.pdf` (`reportlab`, optional — `to_pdf()` raises a clear `ImportError`
  if it isn't installed rather than degrading silently, since a missing evidence export
  should be loud). `to_dict()` always stamps `"layer": 1, "label": "proof"`.
- **`lead.py`** — Layer 2 kingpin lead: wraps a `KingpinScore` with a narrative and a
  disclaimer that ships on *every* instance (`label: "lead"`, hard-coded) — there is no
  `to_pdf`/`to_json`-as-evidence path for this object on purpose, so a lead can't
  accidentally get exported to look like a Layer-1 proof pack.
- **`guardrails.py`** — the two guardrails this module owns (the threshold slider is
  `validate.precision_recall_curve`, below):
  - `legit_hub_guardrail` — proves the hub-degree cap is load-bearing by showing the
    planted legit hub (e.g. `swiggy@ybl`) WOULD fuse dozens of unrelated reports into one
    false ring uncapped, and does not once the cap is applied.
  - `adversarial_split_reports` / `describe_adversarial_case` — a mule-farm scenario: each
    victim gets a unique payee UPI and phone (nothing pairwise shared) but all share one
    device, reused at a scale (`n_victims > hub_degree_cap`) that gets it excluded by the
    *same* guardrail protecting legitimate hubs. Layer 1 honestly finds nothing; Layer 2
    still surfaces the device as the top lead bridging every victim. The honest point: this
    isn't "the graph can't see shared infra" — it's the real precision/recall tension the
    guardrail creates, stated rather than hidden.
- **`validate.py`** — pairwise precision/recall of ring recovery against `_gt.ring_id`
  (`precision_recall_curve` sweeps `hub_degree_cap` — this is what the demo slider plots)
  and `kingpin_rank`/`kingpin_hit_rate` against `_gt.is_kingpin_incident`. No FDR/
  correlated-trait correction (cut per CLAUDE.md §8) — plain, auditable pair counts.

On the pre-seeded network (`generate_network`, 500 victims, rings of 30/14/9/6/5/4)
precision/recall both hit 1.0 at `DEMO_HUB_DEGREE_CAP` = **40** — the substrate the demo
actually uses, and the cap is 40 because it has to sit in the gap between the largest ring
(30) and the smallest popular-but-legit payee (merchants ~75, hub ~200). Measured over 20
independently seeded networks: kingpin ranked #1 in 20/20, ring P/R 1.0 ± 0.0
(`python -m src.evidence.validate`). Both ends of the sweep fail visibly — too strict a cap
prunes a ring's own mule UPI as if it were a hub, too loose a one re-admits the kingpin
phone, then the merchants, then the hub — which is what shows the 1.0s in the middle aren't
rigged. On the smaller text corpus (`generate_messages`) pushed past its tuned `n_legit`
default, precision visibly degrades as merchant-pool collisions start to look ring-sized —
a real, honest illustration of why the threshold is validated against an answer key rather
than asserted.
