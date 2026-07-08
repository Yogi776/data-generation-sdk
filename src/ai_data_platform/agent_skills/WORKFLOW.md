# ADP Agent Workflow (shared source)

This file is the canonical workflow for MCP server instructions, Cursor skills, and docs.

## Hard rules

- Never call `apply_spec` without explicit user approval of the spec YAML.
- Never declare done without KPI SQL verification when research targets exist.
- Always run `run_quality_check` after `generate_synthetic_data`.
- Structural quality score >= 95 is necessary but not sufficient for realism.

## Flow routing

| User has | Flow | Sequence |
|----------|------|----------|
| Nothing | A — Research-driven | intake → research → spec → generate-validate → analytics |
| Schema/ERD only | B — Schema-first | intake → spec → generate-validate |
| CSV/DB sample | C — Learn-from-sample | scan → profile → generate-validate |
| Existing spec | D — Generate only | generate-validate → analytics |
| "More realistic" | E — Calibrate | calibrate → spec patch → generate-validate |

## Intake (Phase 0–1)

**Phase 0 — Purpose**
1. Who uses this data? (demo / QA / ML / compliance)
2. What KPIs must look believable?
3. Geography/locale?
4. Target row counts and seed?

**Phase 1 — Structure**
5. Core entities/tables?
6. Grain per fact table?
7. Key relationships and cardinalities?

**Output brief:**

```yaml
intent: {persona, domain, locale, kpis[]}
structure: {tables_proposed[], grain, confirmed: false}
volume: {rows_per_table, seed, format: parquet}
validation: {kpi_targets[], drift_tolerance: 0.05}
```

## Research

Before `propose_spec`, web-search for:
- Sources (URL + year)
- Category distributions with percentages
- Numeric ranges (mean, currency)
- Business rules (return rate, fraud rate)

Present research table; get explicit approval before spec draft.

## Spec authoring

1. `propose_spec(description, research_notes)` OR draft from retail/examples patterns
2. Review YAML: joins, `values_by` column order, `after`/`expr`/`null_unless`
3. User approves weights and cardinalities
4. Only then `apply_spec`

## Generate and validate

1. `generate_synthetic_data(rows, seed, output_format=parquet)`
2. `run_quality_check()` — score >= 95 or diagnose `failing_checks`
3. `preview_data` on fact + dim tables

## Analytics readiness

1. `validate_business_questions(kpis from intake)`
2. `execute_sql` for each KPI
3. `generate_business_insights` on top revenue/trend query
4. Compare SQL results to research targets

## Calibrate

1. Drift: `|generated_pct - research_pct| / research_pct`
2. If drift > tolerance (default 5%): suggest spec weight patches
3. Re-run `apply_spec` + `generate_synthetic_data`
4. Re-verify KPI SQL
