"""Partition-column recommendation for the largest (fact) table.

Preference order (all generic, no domain rules):
1. a seasonal anchor date column (sampler seasonal_date/seasonal_datetime) — bucket by month;
2. any date/datetime column — bucket by month;
3. a low-cardinality categorical (choice sampler, <= MAX_CARDINALITY distinct).
Otherwise no partitioning. Flags small-file and partition-explosion risk.
"""

from __future__ import annotations

from datetime import date
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:  # pragma: no cover
    from ai_data_platform.generator.engine import GenerationPlan, TablePlan

MAX_CARDINALITY = 50
SMALL_FILE_ROWS = 1_000_000  # rows/partition below this risks too-small files
MAX_PARTITIONS = 2_000


def _months_between(start: str, end: str) -> int:
    try:
        a, b = date.fromisoformat(start[:10]), date.fromisoformat(end[:10])
    except ValueError:
        return 12
    return max((b.year - a.year) * 12 + (b.month - a.month) + 1, 1)


def _largest_table(plan: GenerationPlan) -> TablePlan | None:
    return max(plan.tables, key=lambda t: t.rows, default=None)


def recommend_partitions(plan: GenerationPlan) -> dict[str, Any]:
    tp = _largest_table(plan)
    if tp is None or tp.rows == 0:
        return {"partition_by": [], "n_partitions": 1, "rows_per_partition": 0, "warnings": []}

    partition_by: list[str] = []
    n_partitions = 1
    granularity: str | None = None

    seasonal = next(
        (c for c in tp.columns if c.sampler in ("seasonal_datetime", "seasonal_date")), None
    )
    plain_date = next((c for c in tp.columns if c.sampler in ("datetime", "date")), None)
    date_col = seasonal or plain_date
    if date_col is not None:
        partition_by = [date_col.name]
        granularity = "month"
        n_partitions = _months_between(
            str(date_col.params.get("start", "2024-01-01")),
            str(date_col.params.get("end", "2026-01-01")),
        )
    else:
        cat = next(
            (
                c
                for c in tp.columns
                if c.sampler == "choice" and 0 < len(c.params.get("values") or []) <= MAX_CARDINALITY
            ),
            None,
        )
        if cat is not None:
            partition_by = [cat.name]
            granularity = "value"
            n_partitions = len(cat.params.get("values") or [])

    rows_per_partition = tp.rows // max(n_partitions, 1)
    warnings: list[str] = []
    if partition_by and rows_per_partition < SMALL_FILE_ROWS:
        warnings.append(
            f"partitioning {tp.name} by {partition_by[0]} gives ~{rows_per_partition:,} rows/"
            f"partition (<{SMALL_FILE_ROWS:,}); risks many small files — consider coarser buckets."
        )
    if n_partitions > MAX_PARTITIONS:
        warnings.append(
            f"{n_partitions} partitions for {tp.name} exceeds {MAX_PARTITIONS}; risk of "
            "file-handle/metadata overhead — bucket more coarsely."
        )

    return {
        "table": tp.name,
        "partition_by": partition_by,
        "granularity": granularity,
        "n_partitions": n_partitions,
        "rows_per_partition": rows_per_partition,
        "warnings": warnings,
    }
