"""DuckDBExplorer: the governed query engine over registered datasets.

Every query runs on a **read-only** DuckDB connection, is validated by the
:mod:`~ai_data_platform.explorer.security` guard, bounded by a row limit, guarded
against oversized scans via ``EXPLAIN`` estimates, interrupted on timeout, and
recorded in the query log. This class is the only place that talks to DuckDB for
reads.
"""

from __future__ import annotations

import contextlib
import re
import threading
import time
from pathlib import Path
from typing import Any

import duckdb
import polars as pl

from ai_data_platform.config import ExplorerConfig
from ai_data_platform.core.exceptions import (
    ExplorerError,
    QueryTimeoutError,
    QueryTooLargeError,
)
from ai_data_platform.core.paths import safe_resolve
from ai_data_platform.explorer.metastore import ExplorerMetastore
from ai_data_platform.explorer.registrar import quote_ident
from ai_data_platform.explorer.security import guard_select, wrap_with_limit

_EC = re.compile(r"~?(\d+)\s*(?:rows|EC)|EC[:=]\s*(\d+)", re.IGNORECASE)
_PROFILE_SAMPLE_THRESHOLD = 2_000_000
_PROFILE_SAMPLE_ROWS = 200_000
_TOP_VALUES = 10


class DuckDBExplorer:
    def __init__(
        self,
        root: str | Path,
        cfg: ExplorerConfig,
        metastore: ExplorerMetastore,
    ) -> None:
        self.root = Path(root).expanduser().resolve()
        self.cfg = cfg
        self.metastore = metastore

    # -- connection ----------------------------------------------------------
    def _connect(self, dataset: str) -> duckdb.DuckDBPyConnection:
        db_path = self.metastore.db_path_for(dataset)
        if not Path(db_path).exists():
            raise ExplorerError(
                f"Explorer database for dataset {dataset!r} is missing ({db_path}).",
                hint="Re-run registration (`adp explore register`).",
            )
        return duckdb.connect(db_path, read_only=True)

    def _resolve_table(self, dataset: str, table: str) -> dict[str, Any]:
        return self.metastore.get_table(dataset, table)

    # -- metadata ------------------------------------------------------------
    def describe_table(self, dataset: str, table: str) -> dict[str, Any]:
        meta = self._resolve_table(dataset, table)
        return {
            "table": table,
            "dataset": dataset,
            "format": meta["format"],
            "path": meta["path"],
            "row_count": meta["row_count"],
            "columns": meta["columns"],
            "partition_keys": meta["partition_keys"],
        }

    def show_schema(self, dataset: str, table: str) -> dict[str, Any]:
        meta = self._resolve_table(dataset, table)
        cols = meta["columns"]
        col_ddl = ",\n  ".join(f"{quote_ident(c['name'])} {c['type']}" for c in cols)
        ddl = f"CREATE VIEW {quote_ident(table)} (\n  {col_ddl}\n);"
        return {"table": table, "ddl": ddl, "columns": cols}

    def preview_table(self, dataset: str, table: str, limit: int = 20) -> dict[str, Any]:
        self._resolve_table(dataset, table)  # validates existence
        n = max(1, min(limit, 200))
        ident = quote_ident(table)
        with self._connect(dataset) as con:
            df = con.execute(f"SELECT * FROM {ident} LIMIT {n}").pl()  # noqa: S608 - ident quoted
        return {
            "table": table,
            "columns": df.columns,
            "rows": df.to_dicts(),
            "showing": len(df),
        }

    def get_row_count(self, dataset: str, table: str) -> dict[str, Any]:
        self._resolve_table(dataset, table)
        ident = quote_ident(table)
        with self._connect(dataset) as con:
            row = con.execute(f"SELECT count(*) FROM {ident}").fetchone()  # noqa: S608
        return {"table": table, "row_count": int(row[0]) if row else 0}

    def profile_table(self, dataset: str, table: str) -> dict[str, Any]:
        meta = self._resolve_table(dataset, table)
        ident = quote_ident(table)
        with self._connect(dataset) as con:
            total_row = con.execute(f"SELECT count(*) FROM {ident}").fetchone()  # noqa: S608
            total = int(total_row[0]) if total_row else 0
            sampled = total > _PROFILE_SAMPLE_THRESHOLD
            src = (
                f"(SELECT * FROM {ident} USING SAMPLE reservoir({_PROFILE_SAMPLE_ROWS} ROWS))"
                if sampled
                else ident
            )
            base = max(1, min(total, _PROFILE_SAMPLE_ROWS) if sampled else total or 1)

            columns: list[dict[str, Any]] = []
            for col in meta["columns"]:
                columns.append(self._profile_column(con, src, col, base))
        return {
            "table": table,
            "row_count": total,
            "sampled": sampled,
            "columns": columns,
        }

    def _profile_column(
        self,
        con: duckdb.DuckDBPyConnection,
        src: str,
        col: dict[str, Any],
        base_rows: int,
    ) -> dict[str, Any]:
        name = col["name"]
        ident = quote_ident(name)
        dtype = str(col["type"]).upper()
        numeric = any(k in dtype for k in ("INT", "DECIMAL", "DOUBLE", "FLOAT", "REAL", "HUGEINT"))
        temporal = any(k in dtype for k in ("DATE", "TIME", "TIMESTAMP"))

        row = con.execute(
            f"SELECT count(*) - count({ident}), count(DISTINCT {ident}) FROM {src}"  # noqa: S608
        ).fetchone()
        nulls = int(row[0]) if row else 0
        distinct = int(row[1]) if row and row[1] is not None else None
        out: dict[str, Any] = {
            "column": name,
            "type": col["type"],
            "null_count": nulls,
            "null_fraction": round(nulls / base_rows, 6) if base_rows else 0.0,
            "distinct": distinct,
            "min": None,
            "max": None,
            "mean": None,
            "stddev": None,
            "top_values": [],
        }

        if numeric:
            stat = con.execute(
                f"SELECT min({ident}), max({ident}), avg({ident}), stddev_samp({ident}) "  # noqa: S608
                f"FROM {src}"
            ).fetchone()
            if stat:
                out["min"], out["max"] = stat[0], stat[1]
                out["mean"] = float(stat[2]) if stat[2] is not None else None
                out["stddev"] = float(stat[3]) if stat[3] is not None else None
        elif temporal:
            stat = con.execute(
                f"SELECT min({ident}), max({ident}) FROM {src}"  # noqa: S608
            ).fetchone()
            if stat:
                out["min"], out["max"] = stat[0], stat[1]

        # Top values for low/medium-cardinality columns.
        if distinct is not None and 0 < distinct <= 50:
            top = con.execute(
                f"SELECT {ident} AS v, count(*) AS c FROM {src} "  # noqa: S608
                f"WHERE {ident} IS NOT NULL GROUP BY 1 ORDER BY c DESC LIMIT {_TOP_VALUES}"
            ).fetchall()
            out["top_values"] = [{"value": r[0], "count": int(r[1])} for r in top]
        return out

    # -- query ---------------------------------------------------------------
    def execute_sql(self, dataset: str, sql: str, *, max_rows: int | None = None) -> dict[str, Any]:
        clean = guard_select(sql)
        cap = min(max_rows or self.cfg.max_result_rows, self.cfg.max_result_rows)
        started = time.perf_counter()
        try:
            with self._connect(dataset) as con:
                self._enforce_scan_guard(con, clean)
                wrapped = wrap_with_limit(clean, max_rows=cap, sample=self.cfg.sample_large_results)
                df = self._run_with_timeout(con, wrapped)
        except Exception as e:  # noqa: BLE001 - normalize + log then re-raise
            self.metastore.log_query(
                dataset=dataset, sql=clean, status=_status_for(e), error=str(e)
            )
            raise

        elapsed = (time.perf_counter() - started) * 1000
        truncated = len(df) > cap
        if truncated:
            df = df.head(cap)
        self.metastore.log_query(
            dataset=dataset,
            sql=clean,
            status="ok",
            row_count=len(df),
            truncated=truncated,
            elapsed_ms=elapsed,
        )
        return {
            "columns": df.columns,
            "rows": df.to_dicts(),
            "row_count": len(df),
            "truncated": truncated,
            "sampled": truncated and self.cfg.sample_large_results,
            "elapsed_ms": round(elapsed, 2),
        }

    def explain_sql(self, dataset: str, sql: str) -> dict[str, Any]:
        clean = guard_select(sql)
        with self._connect(dataset) as con:
            rows = con.execute(f"EXPLAIN {clean}").fetchall()
        plan = "\n".join(str(r[-1]) for r in rows)
        return {"plan": plan, "estimated_rows": _max_estimated_rows(plan)}

    def export_query_result(
        self, dataset: str, sql: str, *, fmt: str, filename: str, export_dir: str
    ) -> dict[str, Any]:
        clean = guard_select(sql)
        if fmt not in ("csv", "parquet", "json"):
            raise ExplorerError(f"Unsupported export format {fmt!r}.")
        # Server-controlled, sandboxed destination — never a user-supplied path.
        safe_name = Path(filename).name
        target = safe_resolve(self.root, str(Path(export_dir) / safe_name))
        target.parent.mkdir(parents=True, exist_ok=True)

        with self._connect(dataset) as con:
            self._enforce_scan_guard(con, clean)
            df = self._run_with_timeout(con, clean)
        if fmt == "csv":
            df.write_csv(target)
        elif fmt == "parquet":
            df.write_parquet(target)
        else:
            df.write_ndjson(target)
        self.metastore.log_query(dataset=dataset, sql=clean, status="ok", row_count=len(df))
        return {"path": str(target), "format": fmt, "row_count": len(df)}

    # -- internals -----------------------------------------------------------
    def _run_with_timeout(self, con: duckdb.DuckDBPyConnection, sql: str) -> pl.DataFrame:
        timed_out = threading.Event()

        def _interrupt() -> None:
            timed_out.set()
            with contextlib.suppress(Exception):  # best effort
                con.interrupt()

        timer = threading.Timer(self.cfg.query_timeout_seconds, _interrupt)
        timer.start()
        try:
            return con.execute(sql).pl()
        except duckdb.Error as e:
            if timed_out.is_set():
                raise QueryTimeoutError(
                    f"Query exceeded the {self.cfg.query_timeout_seconds:g}s timeout.",
                    hint="Add filters/aggregation or raise explorer.query_timeout_seconds.",
                ) from e
            raise ExplorerError(f"Query failed: {e}") from e
        finally:
            timer.cancel()

    def _enforce_scan_guard(self, con: duckdb.DuckDBPyConnection, sql: str) -> None:
        if not self.cfg.max_scan_rows:
            return
        try:
            rows = con.execute(f"EXPLAIN {sql}").fetchall()
        except duckdb.Error:
            return  # best-effort; don't block a legitimate query on EXPLAIN quirks
        est = _max_estimated_rows("\n".join(str(r[-1]) for r in rows))
        if est is not None and est > self.cfg.max_scan_rows:
            raise QueryTooLargeError(
                f"Estimated scan of ~{est:,} rows exceeds the "
                f"{self.cfg.max_scan_rows:,} row guard.",
                hint="Narrow the query or raise explorer.max_scan_rows.",
            )


def _max_estimated_rows(plan: str) -> int | None:
    values = [
        int(m.group(1) or m.group(2)) for m in _EC.finditer(plan) if (m.group(1) or m.group(2))
    ]
    return max(values) if values else None


def _status_for(e: Exception) -> str:
    from ai_data_platform.core.exceptions import QueryTimeoutError as _T
    from ai_data_platform.core.exceptions import UnsafeSQLError as _U

    if isinstance(e, _T):
        return "timeout"
    if isinstance(e, _U):
        return "rejected"
    return "error"
