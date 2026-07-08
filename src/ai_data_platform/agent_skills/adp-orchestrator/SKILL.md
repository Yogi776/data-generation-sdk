---
name: adp-orchestrator
description: Route ADP synthetic data requests to the correct flow (A–E) before MCP tools. Use when the user asks to create a dataset, generate synthetic data, start a new domain, or mentions retail/healthcare/e-commerce data.
---

# ADP Orchestrator

Route to the correct flow **before** any MCP tool calls.

## Flow table

| User has | Flow | Next skills |
|----------|------|-------------|
| Nothing | A — Research-driven | adp-intake → adp-domain-research → adp-spec-author → adp-generate-validate → adp-analytics-readiness |
| Schema/ERD only | B — Schema-first | adp-intake → adp-spec-author → adp-generate-validate |
| CSV/DB sample | C — Learn-from-sample | adp-intake (light) → adp-generate-validate |
| Existing spec | D — Generate only | adp-generate-validate → adp-analytics-readiness |
| "More realistic" / drift | E — Calibrate | adp-calibrate → adp-spec-author → adp-generate-validate |

## Hard rules

- Never call `apply_spec` without user checkpoint.
- Never declare done without KPI SQL verification.
- Use MCP prompt `agent_orchestrator` for parity with non-Cursor clients.

Full workflow: `ai_data_platform/agent_skills/WORKFLOW.md`.
