"""Auto-detect date partition columns for ingestr extract_partition_by."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:  # pragma: no cover
    from ai_data_platform.metadata.catalog import Catalog

_PREFERRED_DATE_COLS = ("order_date", "created_at", "updated_at", "event_date", "transaction_date")
_DATE_TYPE_MARKERS = ("date", "datetime", "timestamp", "time")


def _is_date_like(col_type: str) -> bool:
    t = col_type.lower()
    return any(m in t for m in _DATE_TYPE_MARKERS)


def partition_column_for_table(catalog: Catalog, table: str) -> str | None:
    """Return the best date/datetime column for extract partitioning, if any."""
    try:
        meta = catalog.get_table(table)
    except Exception:
        return None
    columns = meta.get("columns", [])
    by_name = {c["name"]: c for c in columns}
    for preferred in _PREFERRED_DATE_COLS:
        col = by_name.get(preferred)
        if col and _is_date_like(str(col.get("type", ""))):
            return preferred
    for col in columns:
        if _is_date_like(str(col.get("type", ""))):
            return col["name"]
    return None


def auto_extract_options(
    catalog: Catalog,
    table: str,
    *,
    row_count: int | None = None,
) -> dict[str, Any]:
    """Build ingestr_options for parallel extract when strategy allows partitioning.

  Only applies to tables with 1M+ rows and a date/datetime column.
  """
    if row_count is not None and row_count < 1_000_000:
        return {}
    col = partition_column_for_table(catalog, table)
    if not col:
        return {}
    return {
        "extract_partition_by": col,
        "extract_partition_interval": "auto",
    }
