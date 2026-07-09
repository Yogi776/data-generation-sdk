"""Batch size, parallelism, format, and runtime-class recommendations.

Given the plan's largest table and a memory budget, pick a chunk size that keeps
the per-worker working set inside the budget, a worker count matched to CPU and
chunk count, and a format/runtime class matched to scale.
"""

from __future__ import annotations

import os
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:  # pragma: no cover
    from ai_data_platform.config import GenerationConfig
    from ai_data_platform.generator.engine import GenerationPlan

MIN_BATCH = 10_000
MAX_BATCH = 1_000_000
MAX_WORKERS = 16
PARQUET_ROW_THRESHOLD = 1_000_000
# total-row thresholds for the runtime class
_RUNTIME_CLASSES = ((1_000_000, "small"), (10_000_000, "medium"), (100_000_000, "large"))


def default_cpu() -> int:
    return os.cpu_count() or 4


def runtime_class(total_rows: int) -> str:
    for threshold, label in _RUNTIME_CLASSES:
        if total_rows < threshold:
            return label
    return "xlarge"


def recommend_batch(
    plan: GenerationPlan,
    largest_row_bytes: int,
    *,
    cfg: GenerationConfig,
    memory_budget_mb: float,
    cpu: int,
) -> dict[str, Any]:
    """Recommend batch size, parallelism, format, and runtime class."""
    total_rows = sum(t.rows for t in plan.tables)
    largest_rows = max((t.rows for t in plan.tables), default=0)

    # keep one worker's chunk working set (row_bytes × batch × overhead) within a
    # fair share of the budget; overhead ~2 folded in via the /2 share
    workers = max(1, min(cpu - 2, MAX_WORKERS)) if cpu > 2 else 1
    share_bytes = max(memory_budget_mb * 1e6 / max(workers, 1) / 2, 1e6)
    fit_batch = int(share_bytes / max(largest_row_bytes, 1))
    batch = max(MIN_BATCH, min(cfg.chunk_rows, fit_batch, MAX_BATCH))
    if largest_rows and largest_rows < batch:
        batch = largest_rows

    n_chunks = max(1, -(-largest_rows // batch)) if largest_rows else 1
    parallelism = max(1, min(workers, n_chunks))

    fmt = "parquet" if largest_rows >= PARQUET_ROW_THRESHOLD else cfg.output_format

    return {
        "recommended_batch_size": batch,
        "parallelism": parallelism,
        "recommended_format": fmt,
        "expected_runtime_class": runtime_class(total_rows),
        "total_rows": total_rows,
        "largest_table_rows": largest_rows,
    }
