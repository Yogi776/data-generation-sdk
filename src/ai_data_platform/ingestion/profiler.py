"""Data profiler.

Computes a schema summary, row/column counts, per-column statistics (nulls,
distinct, min/max/avg/std/median), duplicate rows, and sample rows — all through
DuckDB SQL (`SUMMARIZE` + targeted aggregates) so it streams over large
views/tables without pulling data into Python. Duplicate detection is exact for
modest tables and skipped (flagged) above a threshold.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from ai_data_platform.core.logging import get_logger
from ai_data_platform.ingestion.duckdb_reader import quote_ident

if TYPE_CHECKING:  # pragma: no cover
    import duckdb

log = get_logger("adp.ingestion.profiler")

_DUP_CHECK_MAX_ROWS = 5_000_000


def profile(
    con: duckdb.DuckDBPyConnection, name: str, *, sample_size: int = 10_000
) -> dict[str, Any]:
    ident = quote_ident(name)

    row_count = int(con.execute(f"SELECT count(*) FROM {ident}").fetchone()[0])  # noqa: S608
    describe = con.execute(f"DESCRIBE {ident}").fetchall()
    schema = [
        {"name": r[0], "type": str(r[1]), "nullable": str(r[2]).upper() != "NO"}
        for r in describe
    ]
    column_count = len(schema)

    columns = _summarize(con, ident, row_count)
    duplicate_rows, dup_checked = _duplicates(con, ident, row_count)
    sample_rows = _sample(con, ident, sample_size)

    profile_payload: dict[str, Any] = {
        "row_count": row_count,
        "column_count": column_count,
        "duplicate_rows": duplicate_rows,
        "duplicate_check": "exact" if dup_checked else "skipped (table too large)",
        "columns": columns,
    }
    return {
        "schema": schema,
        "profile": profile_payload,
        "sample_rows": sample_rows,
        "row_count": row_count,
        "column_count": column_count,
    }


def _summarize(
    con: duckdb.DuckDBPyConnection, ident: str, row_count: int
) -> dict[str, dict[str, Any]]:
    try:
        rel = con.execute(f"SUMMARIZE SELECT * FROM {ident}")  # noqa: S608
        cols = [c[0] for c in rel.description]
        rows = rel.fetchall()
    except Exception as e:  # noqa: BLE001 - SUMMARIZE unsupported for exotic types
        log.info("SUMMARIZE failed (%s); returning schema-only profile", e)
        return {}

    idx = {c: i for i, c in enumerate(cols)}

    def val(r: tuple, key: str) -> Any:
        return r[idx[key]] if key in idx else None

    out: dict[str, dict[str, Any]] = {}
    for r in rows:
        cname = val(r, "column_name")
        null_pct = _to_float(val(r, "null_percentage"))
        null_count = int(round((null_pct or 0.0) / 100.0 * row_count)) if row_count else 0
        out[cname] = {
            "type": val(r, "column_type"),
            "null_count": null_count,
            "null_percentage": round(null_pct, 4) if null_pct is not None else None,
            "distinct": _to_int(val(r, "approx_unique")),
            "min": _stringify(val(r, "min")),
            "max": _stringify(val(r, "max")),
            "avg": _to_float(val(r, "avg")),
            "std": _to_float(val(r, "std")),
            "median": _stringify(val(r, "q50")),
        }
    return out


def _duplicates(
    con: duckdb.DuckDBPyConnection, ident: str, row_count: int
) -> tuple[int | None, bool]:
    if row_count == 0 or row_count > _DUP_CHECK_MAX_ROWS:
        return (0 if row_count == 0 else None), False
    try:
        distinct = int(
            con.execute(f"SELECT count(*) FROM (SELECT DISTINCT * FROM {ident})").fetchone()[0]  # noqa: S608
        )
        return row_count - distinct, True
    except Exception as e:  # noqa: BLE001 - unhashable/nested types
        log.info("duplicate check skipped (%s)", e)
        return None, False


def _sample(con: duckdb.DuckDBPyConnection, ident: str, n: int) -> list[dict[str, Any]]:
    n = max(1, min(n, 100))  # sample_rows in the report stays small; full sample used for stats
    df = con.execute(f"SELECT * FROM {ident} LIMIT {n}").pl()  # noqa: S608
    return df.to_dicts()


def _to_float(v: Any) -> float | None:
    try:
        return float(v) if v is not None else None
    except (TypeError, ValueError):
        return None


def _to_int(v: Any) -> int | None:
    try:
        return int(v) if v is not None else None
    except (TypeError, ValueError):
        return None


def _stringify(v: Any) -> Any:
    return v if v is None or isinstance(v, (int, float, str, bool)) else str(v)
