---
name: adp-analytics-readiness
description: Prove synthetic data answers business questions via KPI SQL and insights. Use after generation to validate_business_questions, execute_sql, and generate_business_insights.
---

# ADP Analytics Readiness

Prove data answers business questions — not just structural quality.

## MCP sequence

1. `validate_business_questions(questions from intake KPIs)`
2. `execute_sql` for each KPI:
   - Payment mix: `SELECT payment_method, COUNT(*) * 100.0 / SUM(COUNT(*)) OVER () FROM orders GROUP BY 1`
   - AOV, status rates, category splits as defined in intake
3. `generate_business_insights` on top revenue/trend query
4. Compare SQL results to research targets (table in response)

## Done criteria

- KPIs within `drift_tolerance` (default 5%) of research, OR user accepts variance
- Business questions validated

If drift too high → **adp-calibrate**.
