# New User Flow — step by step, with internals

> **For a runnable tutorial with copy-paste commands and expected output at every step, see [GETTING-STARTED.md](GETTING-STARTED.md).**
> This document explains what the engine does internally at each step.

What a brand-new user does, and what the engine does underneath at every step.

## 1. Install — `pip install ai-data-platform`
One package delivers the `adp` CLI, Python SDK, local API/UI, and MCP server.
Nothing runs at import time; no account, no signup, no telemetry.

## 2. Create a project — `adp init`
**You get:** `adp.yaml` in the current directory.
**Internally:** default config written (project name, output dir, generation
defaults `rows=1000, seed=42`, MiniMax provider block referencing an env var —
never a key). The `.adp/` catalog directory is created on first use.

## 3. Connect a source — `adp connect --name shop --type csv --path ./data`
**You get:** a tested connection ("4 table(s) found") recorded in adp.yaml.
**Internally:** the connector registry instantiates the right connector,
`test_connection()` runs before anything is saved; broken sources are rejected.
Database DSNs use `${ENV_VAR}` interpolation — plaintext secrets refuse to load.

## 4. Scan — `adp scan`
**You get:** a metadata catalog (tables, columns, relationship candidates).
**Internally:** connector lists tables and normalized column types into SQLite
(`.adp/catalog.db`); FK candidates inferred from naming conventions
(`customer_id` → `customers`) at capped 0.6 confidence; a schema fingerprint is
stored so re-scans detect drift. No data is copied — only structure.

## 5. Profile — `adp profile`
**You get:** statistics + PII flags + confirmed keys per table.
**Internally (the step that makes generation realistic):** budgeted samples
(default 10k rows/table) flow through Polars: null ratios, distincts, min/max/
mean/std, top-10 values, entropy. PKs detected at uniqueness ≥ 99.9%; FK
candidates upgraded by inclusion testing (child ⊆ parent ≥ 95%); PII classified
by three signals (name pattern + value regex + Luhn). Everything lands in the
catalog with confidence + evidence.

## 6. Generate — `adp generate-data --rows 50000 --output parquet`
**You get:** FK-safe synthetic tables in `output/`.
**Internally:** the catalog compiles into a **Plan IR** — per column, the best
sampler: profiled categorical weights, moment-matched lognormal for money
(σ² = ln(1+(s/m)²)), floor-matched Poisson for counts, profiled date ranges,
name-pattern samplers for emails/names/phones. Tables generate parents-first
(topological order); child FKs draw from actual parent key pools → zero orphans.
Chunked execution bounds memory; per-(seed, table, chunk) PRNG makes every run
byte-identically reproducible.

## 7. Validate — `adp quality-check --report quality.md`
**You get:** a weighted quality score with per-check evidence.
**Internally:** rules are *derived from your metadata* (never handwritten):
PK uniqueness, not-null, FK inclusion, range-with-tolerance vs profile,
accepted-values for categoricals. Score = weighted category pass rates
(integrity .35, completeness .25, validity .25, consistency .15).

## 8. Use it
- `output/*.parquet|csv|sql|duckdb` → seed dev databases, pipeline tests, demos, ML.
- `adp semantic-model --format cube` → Cube.js-ready models from detected facts/dims.
- `adp sql "revenue by city last quarter"` → catalog-grounded, read-only SQL (needs the LLM key — the only online feature).
- `adp docs` → Markdown data dictionary. `adp ui` → local web console.

## Alternative entry: from an AI client (MCP)
Add once: `claude mcp add adp -- adp mcp-server --project /path/to/project`
(similar one-liners for Cursor/Windsurf/VS Code). Then steps 4–8 happen by
asking the agent — it calls `scan_sources → profile_source →
generate_synthetic_data → run_quality_check` against the exact same backend.

## If something goes wrong
Every error carries a hint: no adp.yaml → "run adp init"; missing driver →
"pip install 'ai-data-platform[postgres]'"; no parent keys → "add rows and
profile"; SQLite on network mounts → `export ADP_CATALOG_DIR=~/.adp-catalogs`.

## Minimum inputs (tested — see examples/retail-ecommerce/REQUIREMENTS-TO-GENERATE.md)
Headers-only CSV → single tables only · ~10 rows + profile → FK-safe dev data ·
500+ representative rows → production fidelity (validated 100/100).
