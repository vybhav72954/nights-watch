# Provenance — vendored engine code

The four modules in this folder are **copied** from Vybhav's fraud-detection engine
and lightly adapted. They are **not** an upstream dependency — we vendor so this repo
stays self-contained and so we never modify the source (which carries a byte-identical
seeded-build invariant).

- **Upstream repo:** https://github.com/vybhav72954/cross-border-fraud
- **Local source dir:** `Z:\Projects\2026\cross-border-credit`
- **Vendored at commit:** `a5d5fb7` (`a5d5fb7dc1a966a8cdb552595598025d2ca2e27d`)
- **Source date / branch:** 2026-06-29 / `feat/ssm`
- **Vendored on:** 2026-07-07

## Files & mapping

| here | upstream path | change made |
|---|---|---|
| `schema.py` | `src/schema.py` | none (verbatim) |
| `inject.py` | `src/inject.py` | import: `from src.schema` → `from src.engine.schema` |
| `adapters.py` | `src/adapters.py` | import: `from src.schema` → `from src.engine.schema` |
| `gnn.py` | `src/models/gnn.py` | import: `from src.schema` → `from src.engine.schema` |

Added locally (not from upstream): `__init__.py`, `scam_schema.py` (the `SCAM` Schema),
this file.

## Re-sync procedure

If the upstream engine changes and we want the update, re-copy the four files and re-apply
the single import rewrite:

```bash
sed -i 's/from src\.schema import/from src.engine.schema import/' inject.py adapters.py gnn.py
```

Then re-run the smoke import (see repo `tests/`).

## What we deliberately did NOT vendor

`glm.py`, `features.py`, `evaluation.py`, `ssm.py`, `sequence.py`, `robustness.py`,
`labels.py`, `benchmark.py`, `external.py` — none are on the ring/graph path Night's
Watch needs. Pull `ssm.py` later only if the velocity/temporal timing feature is added.
