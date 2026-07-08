---
name: adp-intake
description: Structured Phase 0–1 intake questions for synthetic data projects. Use before proposing specs or generating data — purpose, persona, locale, KPIs, entities, grain, volume.
---

# ADP Intake

Ask these questions **before** any MCP tools. MCP equivalent: `intake_wizard` prompt.

## Phase 0 — Purpose

1. Who uses this data? **Demo / QA / ML / Compliance**
2. What KPIs must look believable? (payment mix, AOV, delivery rate, etc.)
3. Geography/locale? (e.g. India retail, US healthcare)
4. Target row counts and seed?

## Phase 1 — Structure

5. Core entities/tables? (propose star schema for e-commerce)
6. Grain per fact table?
7. Key relationships and cardinalities?

## Output brief

Carry forward as markdown:

```yaml
intent: {persona, domain, locale, kpis[]}
structure: {tables_proposed[], grain, confirmed: false}
volume: {rows_per_table, seed, format: parquet}
validation: {kpi_targets[], drift_tolerance: 0.05}
```

Get user confirmation before proceeding to research or spec.
