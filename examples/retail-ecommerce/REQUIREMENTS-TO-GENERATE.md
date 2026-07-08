# What is required to generate data? (tested empirically)

Three input tiers, each actually executed against this engine:

## Tier A — Column headers only (zero data rows)

```
customers.csv:  customer_id,full_name,email,city          (no rows)
orders.csv:     order_id,customer_id,total_amount,status  (no rows)
```

**Result: partial.** Standalone tables generate fine (name-pattern samplers produce
names, emails, cities, amounts). **FK-linked tables fail** with an actionable error
(`No parent keys for orders.customer_id`) — primary keys are detected by *profiling
data* (uniqueness ≥ 99.9%), and with zero rows there is nothing to detect, so the
parent key pool is never built.

Use tier A only for single, unrelated tables.

## Tier B — Minimum viable: ~10 rows per table + profile ✅

```bash
adp init && adp connect --name s --type csv --path ./data
adp scan && adp profile          # profile is the required step
adp generate-data --rows 1000
```

**Result: works.** 1,000 FK-safe rows per table from 10 seed rows.
Quality score ~75/100 — integrity is perfect, but statistical checks are weak
because 10 rows barely define distributions (narrow ranges, incomplete category
sets). Fine for schema/dev seeding; not for analytics realism.

## Tier C — Recommended: 500+ representative rows per table ✅✅

This example (2k customers / 300 products / 12k orders / 11k transactions):

**Result: production-grade.** Quality 100/100; independent validation 32/32
(mean/σ drift ≤ 2.1%, categorical TVD ≤ 0.006, zero FK orphans, deterministic).

## Summary: the actual requirements

| # | Requirement | Mandatory? | Why |
|---|---|---|---|
| 1 | `adp init` → adp.yaml | ✅ | project config |
| 2 | A connected source (`adp connect`) | ✅ | csv / parquet / duckdb / postgres / mysql |
| 3 | `adp scan` | ✅ | catalog: tables, columns, FK candidates from naming |
| 4 | **Data rows + `adp profile`** | ✅ for multi-table / realism | PK detection, FK confirmation, distributions, categories, PII |
| 5 | 500+ representative rows | Recommended | statistical fidelity (means, σ, category weights) |
| 6 | LLM API key | ❌ | only needed for `adp sql` (NL→SQL); generation is fully offline |
| 7 | Seed (`--seed`) | Optional | reproducibility (defaults to 42 from adp.yaml) |

**One-line answer:** a project + a connected source + `scan` + `profile` over at
least a handful of representative rows per table. Everything else (volumes,
formats, seeds) is a flag. No API key, no internet, no domain configuration.

## Environment note

On network-mounted filesystems SQLite may fail (`disk I/O error`). Set
`export ADP_CATALOG_DIR=~/.adp-catalogs` to relocate the catalog to a local disk
— everything else stays in the project directory.
