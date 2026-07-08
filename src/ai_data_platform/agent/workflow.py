"""Shared agent workflow text — single source for MCP instructions and docs."""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path

ORCHESTRATOR_RULES = """
HARD RULES (all flows):
- Never call apply_spec without explicit user approval of the spec YAML.
- Never declare the task done without KPI SQL verification when research targets exist.
- Always run run_quality_check after generate_synthetic_data.
- Structural quality score >= 95 is necessary but not sufficient for realism.
""".strip()

FLOW_ROUTING = """
FLOW ROUTING — pick one before calling tools:
- Flow A (nothing): intake → research → propose_spec → user approves → apply_spec → generate → quality → KPI SQL
- Flow B (schema only): intake → propose_spec → apply_spec → generate → quality
- Flow C (sample data): scan_sources → profile_source → generate → quality (confirm low-confidence FKs first)
- Flow D (existing spec): generate_synthetic_data → run_quality_check → analytics
- Flow E (calibrate): execute_sql KPIs → compare to research → patch spec weights → regenerate → re-verify
""".strip()

INTAKE_QUESTIONS = """
PHASE 0 — Purpose:
1. Who uses this data? (demo / QA / ML / compliance)
2. What KPIs must look believable? (e.g. payment mix, AOV, delivery rate)
3. Geography/locale? (e.g. India retail, US healthcare)
4. Target row counts and seed?

PHASE 1 — Structure:
5. Core entities/tables? (propose dim/fact star schema if e-commerce)
6. Grain per fact table?
7. Key relationships and cardinalities?

Output a brief YAML block: intent, structure, volume, validation (kpi_targets, drift_tolerance: 0.05).
""".strip()

KPI_VALIDATION = """
After generation, verify KPIs with execute_sql:
- Category distributions: SELECT col, COUNT(*) * 100.0 / SUM(COUNT(*)) OVER () FROM t GROUP BY 1
- Compare to research targets; drift > 5% → suggest spec weight patches (Flow E).
""".strip()


@lru_cache(maxsize=1)
def mcp_server_instructions() -> str:
    """Full instructions string for the MCP server."""
    workflow_path = Path(__file__).resolve().parent.parent / "agent_skills" / "WORKFLOW.md"
    workflow_md = workflow_path.read_text(encoding="utf-8") if workflow_path.is_file() else ""
    parts = [
        "Local AI data platform. Use MCP prompts: agent_orchestrator, intake_wizard, "
        "research_and_generate, calibrate_dataset.",
        ORCHESTRATOR_RULES,
        FLOW_ROUTING,
        KPI_VALIDATION,
    ]
    if workflow_md:
        parts.append(workflow_md[:4000])  # cap size for MCP clients
    return "\n\n".join(parts)


def research_and_generate_prompt(domain: str) -> str:
    return f"""Create a production-realistic synthetic {domain} dataset.

1. INTAKE: Ask purpose, KPIs, locale, row count (or use intake_wizard prompt first).
2. RESEARCH: Web search for real distributions — cite sources. Present table for user approval.
3. DRAFT: propose_spec(description, research_notes). User MUST approve YAML before apply_spec.
4. GENERATE: apply_spec → generate_synthetic_data (parquet, seed). Ask row count if unknown.
5. STRUCTURAL: run_quality_check (target >= 95). preview_data on fact + dim tables.
6. KPI VERIFY: execute_sql for each KPI from intake. Compare to research (±5% tolerance).
7. ANALYTICS: validate_business_questions + generate_business_insights on a trend query.

{ORCHESTRATOR_RULES}
"""


def intake_wizard_prompt(domain: str) -> str:
    return f"""Guide intake for a synthetic {domain} dataset BEFORE any MCP tools.

{INTAKE_QUESTIONS}

Use multiple-choice shortcuts when helpful:
- Persona: Demo / QA / ML / Compliance
- Scale: 1k / 10k / 50k / 100k+ rows
- Realism: Structural only / Industry benchmarks / Match my sample

After answers, summarize as a brief YAML block and ask user to confirm before proceeding.
"""


def calibrate_dataset_prompt() -> str:
    return f"""Calibrate generated data against research targets (Flow E).

1. execute_sql for each KPI category distribution and numeric aggregate.
2. Compute drift: |generated - target| / target for each metric.
3. If drift > 5%: propose spec YAML weight patches (values: weights).
4. User approves patches → apply_spec → generate_synthetic_data.
5. Re-run run_quality_check and KPI SQL until within tolerance or user accepts.

{KPI_VALIDATION}
"""


def agent_orchestrator_prompt() -> str:
    return f"""Route the user's request to the correct ADP flow BEFORE calling tools.

{FLOW_ROUTING}

{ORCHESTRATOR_RULES}

Ask one clarifying question if unclear which flow applies, then follow that flow's MCP tool sequence.
"""


def new_dataset_wizard_prompt(domain: str) -> str:
    return f"""Help create a synthetic {domain} dataset (guided wizard).

1. Persona? Demo / QA / ML / Compliance
2. Tables needed? (propose typical {domain} schema)
3. Row count and seed?
4. propose_spec → USER REVIEWS YAML → apply_spec only after approval
5. generate_synthetic_data (parquet) → run_quality_check → preview_data
6. execute_sql on 2-3 KPIs if user cares about realism

{ORCHESTRATOR_RULES}
"""
