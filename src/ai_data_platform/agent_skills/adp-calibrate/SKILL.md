---
name: adp-calibrate
description: Iterate on spec weights when synthetic data KPIs drift from research targets. Use when quality passes but realism fails — calibrate_dataset MCP prompt equivalent.
---

# ADP Calibrate

When structural quality passes but KPIs drift from research (Flow E).

## Steps

1. `execute_sql` for each KPI distribution and aggregate
2. Compute drift: `|generated_pct - research_pct| / research_pct`
3. If drift > tolerance (default 5%): propose spec weight patches (`values:` weights)
4. User approves → `apply_spec` → `generate_synthetic_data` (or `rows_per_table` for targeted regen)
5. Re-run `run_quality_check` and KPI SQL

## MCP prompt

Use `calibrate_dataset` for non-Cursor parity.

Repeat until within tolerance or user accepts.
