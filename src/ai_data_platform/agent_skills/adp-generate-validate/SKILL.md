---
name: adp-generate-validate
description: Execute synthetic data generation and structural validation via ADP MCP. Use after apply_spec or with sample data — generate_synthetic_data, run_quality_check, preview_data.
---

# ADP Generate & Validate

## MCP sequence

1. `generate_synthetic_data(rows, seed, output_format=parquet)`
2. `run_quality_check()` — require score >= 95 or diagnose `failing_checks`
3. `preview_data` on fact + dim tables

## Flow C (sample data)

If no spec yet:
1. `scan_sources` → `profile_source`
2. Confirm FK confidence with user if low
3. Then generate

## Handoff

Do **not** stop here. Hand off to **adp-analytics-readiness** for KPI verification.
