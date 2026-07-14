# src/graph — Link (the intelligence)

Owner: **Vybhav**. Reports → incident↔identifier graph → Layer-1 rings (connected
components) → Layer-2 kingpin (centrality across rings). `RingSAGE` learned clustering
is a deliberate follow-up (see below).

## Status

Implemented and tested (`tests/test_graph.py`):

- **`build.py`** — `build_graph(reports)`: the incident<->identifier graph. `account` and
  `ifsc` share one node kind (`"account"`) per `docs/REPORT_SCHEMA.md` §6.
- **`rings.py`** — `detect_rings(g, hub_degree_cap=…)`: Layer 1, connected components.
  `hub_degree_cap` implements the legit-high-degree-hub guardrail at the graph layer —
  a popular payee (Swiggy) must not fuse thousands of unrelated incidents into one false
  ring. Without it, `test_hub_guardrail_prevents_false_merge` shows the naive collapse.
- **`kingpin.py`** — `rank_kingpins(g, rings)`: Layer 2, degree + betweenness +
  eigenvector centrality (min-max normalised, averaged) over `ring_union_graph`, which
  deliberately **restores** hub-capped nodes for each ring's incidents. That's the whole
  trick for making "central *across* rings" meaningful: Layer-1 rings are disjoint
  connected components by construction, so a coordinator who reuses one device/phone as a
  front across otherwise-unrelated rings gets excluded from Layer-1 evidence (rightly —
  fan-in alone isn't proof) and re-surfaces in Layer 2 as the bridging, top-ranked lead.
  See `test_kingpin_bridges_rings_hub_capped_out_of_layer1`.

## Follow-up: RingSAGE (not wired yet)

`torch-geometric` isn't installed in this environment, so the learned `RingSAGE` signal
(`src/engine/gnn.py`, parameterised by the `SCAM` schema in `src/engine/scam_schema.py`)
isn't hooked up yet — only the deterministic Layer 1/Layer 2 pipeline above, which needs
no torch and is the part judges actually score (auditability). To add it: convert a
`Report` list to a DataFrame matching `SCAM`'s roles (`entity=victim, target=payee_upi,
time=timestamp, amount=amount, label=is_scam`), fit `RingSAGE` with a `ring` label sourced
from `_gt.planted_typology == "ring"` on synthetic data, and treat its output as a third,
learned signal feeding Layer 2 — not a replacement for connected components (§ CLAUDE.md
"the engine's key adaptation is re-pointing `Schema`... `RingSAGE` transfers directly").
