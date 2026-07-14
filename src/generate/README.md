# src/generate — answer-key synthetic data

Owner: shared (build early — unblocks graph + evidence before the detector is done).
Procedures: `docs/DATASETS.md` §3–§4.

## Status

Implemented and tested (`tests/test_messages.py`, `tests/test_network.py` — 16 tests,
generation and `src/graph` detection verified together, not just each in isolation):

- **`templates.py`** — shared scam/legit text templates + `render()`, which guarantees any
  `phone`/`url` passed in ends up in the output text (inline via the template's slot, else
  appended) so `entities` and `raw_text` never disagree regardless of which template a
  scam_type happens to use.
- **`messages.py`** — `generate_messages()`: a small (~65-report default) scam+legit text
  corpus for detector training/eval. Every ring shares one mule `payee_upi`; a designated
  subset of rings ALSO shares one kingpin phone number.
- **`network.py`** — `generate_network()`: the larger (~300-victim default) pre-seeded graph
  — CLAUDE.md §8's "existing intelligence base" the live demo report joins. Reuses the
  vendored engine's `inject_ring` (windowed K-victim fan-in, parameterised by the `SCAM`
  schema) for structure, then overwrites each ring's target with a fresh mule UPI and stamps
  the kingpin phone across a subset of rings — see the module docstring for why
  `inject_ring`'s own merchant-reuse behaviour needed that adaptation.
- **`io.py`** — `write_reports_jsonl`/`read_reports_jsonl` (`data/synthetic/*.jsonl`) +
  `answer_key()`, a small `_gt`-derived summary for validating ring/kingpin recovery without
  re-parsing the whole corpus.

Run `python -m src.generate.messages` / `python -m src.generate.network` to (re)generate
`data/synthetic/` (gitignored).

**The kingpin-bridge mechanic, deliberately**: both generators give the kingpin identifier
higher fan-in (degree) than any single ring's own identifiers — so with `src/graph`'s
`hub_degree_cap` set between the two, Layer 1 keeps the kingpin's rings legally separate
while Layer 2 surfaces the kingpin as the top cross-ring lead. See `src/graph/README.md`.

## Follow-up: LLM paraphrase (not built)

`messages.py`'s `raw_text` is template-rendered, not LLM-paraphrased. The
graph/evidence pipeline never reads `raw_text` (only `entities`), so this is a demo-polish
gap, not a correctness one. To add it: pass each rendered message through the LLM with a
prompt that preserves every identifier verbatim (never let the model invent or drop a
UPI/phone/amount — that breaks `_gt`), gated behind an API key, falling back to template
text when one isn't configured.
