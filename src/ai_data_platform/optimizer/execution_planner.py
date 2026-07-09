"""Compose the execution plan: batch/format/parallelism/partitioning/memory +
complexity, with actionable optimization warnings — the pre-flight sizing report.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from ai_data_platform.optimizer.batch_strategy import default_cpu, recommend_batch
from ai_data_platform.optimizer.complexity_analyzer import analyze_complexity
from ai_data_platform.optimizer.memory_estimator import (
    _bytes_by_table,
    estimate_memory,
    table_row_bytes,
)
from ai_data_platform.optimizer.partition_planner import recommend_partitions

if TYPE_CHECKING:  # pragma: no cover
    from ai_data_platform.config import GenerationConfig
    from ai_data_platform.generator.engine import GenerationPlan

DEFAULT_MEMORY_BUDGET_MB = 4096.0


def plan_execution(
    plan: GenerationPlan,
    cfg: GenerationConfig,
    *,
    memory_budget_mb: float | None = None,
    cpu: int | None = None,
) -> dict[str, Any]:
    """Return the JSON execution plan for a GenerationPlan under a memory budget."""
    cpu = cpu or default_cpu()
    budget = memory_budget_mb or DEFAULT_MEMORY_BUDGET_MB

    by_table = _bytes_by_table(plan)
    largest = max(plan.tables, key=lambda t: t.rows, default=None)
    largest_row_bytes = table_row_bytes(largest, by_table) if largest else 1

    batch = recommend_batch(
        plan, largest_row_bytes, cfg=cfg, memory_budget_mb=budget, cpu=cpu
    )
    mem = estimate_memory(plan, workers=batch["parallelism"])
    parts = recommend_partitions(plan)
    complexity = analyze_complexity(plan)

    warnings: list[str] = []
    if mem["peak_mb"] > budget:
        warnings.append(
            f"estimated peak {mem['peak_mb']:.0f} MB exceeds budget {budget:.0f} MB — lower "
            "chunk size/parallelism or split the run into fewer rows."
        )
    if mem["contributors"]["largest_table_mb"] > 0.5 * budget:
        warnings.append(
            f"the engine materializes every chunk of a table before writing, so "
            f"'{mem['largest_table']}' holds ~{mem['contributors']['largest_table_mb']:.0f} MB in "
            "RAM at once (Phase 3: stream chunk→write to restore the one-chunk bound)."
        )
    if mem["dominant"] == "key_pool_mb" and mem["contributors"]["key_pool_mb"] > 0.25 * budget:
        warnings.append(
            f"FK key_pool retains parent keys for the whole run (~"
            f"{mem['contributors']['key_pool_mb']:.0f} MB); large parent fan-in dominates memory."
        )
    warnings.extend(complexity["warnings"])
    warnings.extend(parts.get("warnings", []))
    if not parts["partition_by"] and batch["expected_runtime_class"] in ("large", "xlarge"):
        warnings.append(
            f"no partition column found for the largest table; a single "
            f"{batch['recommended_format']} file at this scale is unwieldy — add a date/"
            "low-cardinality column and enable partitioned output (Phase 2)."
        )

    return {
        "estimated_rows": batch["total_rows"],
        "recommended_batch_size": batch["recommended_batch_size"],
        "recommended_format": batch["recommended_format"],
        "partition_by": parts["partition_by"],
        "parallelism": batch["parallelism"],
        "memory_estimate_mb": mem["peak_mb"],
        "expected_runtime_class": batch["expected_runtime_class"],
        "optimization_warnings": warnings,
        # additive detail (superset of the prompt schema)
        "memory_budget_mb": budget,
        "cpu": cpu,
        "per_table": mem["per_table"],
        "memory": mem,
        "partitioning": parts,
        "complexity": complexity,
    }
