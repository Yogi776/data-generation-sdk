"""Ingestion engine — orchestrates the pipeline and owns the DuckDB database.

    Input Source → Format Detector → DuckDB Reader Selector → Schema Inference
    → Data Profiler → Quality Validator → View/Table Creator → SQL Generator
    → Metadata Export

The engine keeps a persistent DuckDB database at ``.adp/ingestion.duckdb`` so
created views/tables survive across processes (e.g. `adp ingest` then later
`adp query`). Known optional extensions are loaded best-effort on connect so that
delta/iceberg/cloud views created earlier remain queryable.
"""

from __future__ import annotations

import contextlib
import re
import time
from pathlib import Path
from typing import Any

import duckdb

from ai_data_platform.core.exceptions import ADPError, IngestionError
from ai_data_platform.core.logging import get_logger
from ai_data_platform.core.paths import adp_dir
from ai_data_platform.ingestion import detector as detector_mod
from ai_data_platform.ingestion import metadata as meta_mod
from ai_data_platform.ingestion import profiler as profiler_mod
from ai_data_platform.ingestion import quality as quality_mod
from ai_data_platform.ingestion import sql_generator as sqlgen
from ai_data_platform.ingestion.duckdb_reader import DuckDBReader, guard_select, quote_ident

log = get_logger("adp.ingestion")

DB_FILENAME = "ingestion.duckdb"
_QUERY_MAX_ROWS = 10_000
_AUTOLOAD_EXTENSIONS = ("httpfs", "sqlite_scanner", "delta", "iceberg")


class IngestionEngine:
    def __init__(self, root: str | Path = ".") -> None:
        self.root = Path(root).expanduser().resolve()

    @property
    def db_path(self) -> Path:
        return adp_dir(self.root) / DB_FILENAME

    def _connect(self, *, read_only: bool = False) -> duckdb.DuckDBPyConnection:
        con = duckdb.connect(str(self.db_path), read_only=read_only)
        for ext in _AUTOLOAD_EXTENSIONS:
            # Best-effort: not installed yet is fine; the reader installs on demand.
            with contextlib.suppress(duckdb.Error):
                con.execute(f"LOAD {ext}")
        return con

    # -- ingest --------------------------------------------------------------
    def ingest(
        self,
        source_path: str,
        table_name: str | None = None,
        persist: bool = False,
        sample_size: int = 10_000,
        options: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        options = options or {}
        started = time.perf_counter()
        detection = detector_mod.detect(source_path, options)
        name = _safe_table_name(table_name or _derive_name(source_path))

        con = self._connect()
        try:
            reader = DuckDBReader(con)
            plan = reader.build(detection, options, sample_size)
            applied_ddl = reader.ddl_for(name, plan, persist=persist)
            kind = reader.create_relation(name, plan, persist=persist)
            persisted = kind == "table"

            prof = profiler_mod.profile(con, name, sample_size=sample_size)
        except ADPError:
            raise
        except Exception as e:  # noqa: BLE001 - normalize unexpected engine errors
            raise IngestionError(f"Ingestion failed for {source_path!r}: {e}") from e
        finally:
            con.close()

        warnings = quality_mod.evaluate(prof["profile"], thresholds=options.get("quality"))
        samples = sqlgen.sample_queries(name, prof["schema"])
        creates = sqlgen.create_statements(applied_ddl, name, plan.scan_expr)
        report = meta_mod.build_report(
            source_path=source_path,
            detected_format=detection.fmt,
            table_name=name,
            relation_kind=kind,
            persisted=persisted,
            profile_result=prof,
            quality_warnings=warnings,
            sql_examples=samples,
            create_statements=creates,
            profiling_sql=sqlgen.profiling_sql(name),
            quality_sql=sqlgen.quality_sql(name, prof["schema"]),
            schema_export=sqlgen.schema_export_json(name, prof["schema"]),
            documentation="",  # filled below (needs the assembled report)
            detection_notes=detection.notes,
            excel_sheets=plan.excel_sheets,
            sheet_used=plan.sheet_used,
        )
        report["generated"]["documentation_markdown"] = sqlgen.documentation(
            name, detection.fmt, report
        )
        report["elapsed_ms"] = round((time.perf_counter() - started) * 1000, 2)
        meta_mod.persist_report(self.root, report)
        log.info(
            "ingested %s as %s (%s, %d rows, %.0f ms)",
            source_path, name, kind, report["row_count"], report["elapsed_ms"],
        )
        return report

    # -- query ---------------------------------------------------------------
    def query(self, sql: str, max_rows: int | None = None) -> dict[str, Any]:
        clean = guard_select(sql)
        cap = min(max_rows or _QUERY_MAX_ROWS, _QUERY_MAX_ROWS)
        started = time.perf_counter()
        con = self._connect(read_only=True)
        try:
            df = con.execute(f"SELECT * FROM ({clean}) AS _q LIMIT {cap + 1}").pl()
        except duckdb.Error as e:
            raise IngestionError(f"Query failed: {e}") from e
        finally:
            con.close()
        truncated = len(df) > cap
        if truncated:
            df = df.head(cap)
        return {
            "columns": df.columns,
            "rows": df.to_dicts(),
            "row_count": len(df),
            "truncated": truncated,
            "elapsed_ms": round((time.perf_counter() - started) * 1000, 2),
        }

    # -- registry ------------------------------------------------------------
    def list_sources(self) -> dict[str, Any]:
        return meta_mod.load_manifest(self.root)

    def describe(self, table: str) -> dict[str, Any]:
        path = meta_mod.registry_dir(self.root) / f"{_safe_table_name(table)}.json"
        if not path.exists():
            raise IngestionError(
                f"No ingested source named {table!r}.",
                hint="Run `adp ingest` first, or check `adp list-sources`.",
            )
        import json

        return json.loads(path.read_text(encoding="utf-8"))

    def preview(self, table: str, limit: int = 20) -> dict[str, Any]:
        return self.query(f"SELECT * FROM {quote_ident(_safe_table_name(table))}", max_rows=limit)


def ingest_data(
    source_path: str,
    table_name: str | None = None,
    persist: bool = False,
    sample_size: int = 10_000,
    options: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Universal ingestion entry point.

    Detect the format of ``source_path`` (file/folder/URL/cloud), read it with
    DuckDB where possible, create a queryable view (or a persisted table when
    ``persist=True`` or the format must be loaded), profile it, flag quality
    issues, and return a full metadata report matching the documented schema.

    ``options`` (all optional): ``project`` (root dir), ``format``, ``delimiter``,
    ``has_header``, ``encoding``, ``sheet`` (Excel), ``flatten``/``record_path``
    (JSON), ``sqlite_table``, ``ignore_errors``, ``quality`` (threshold overrides).
    """
    options = options or {}
    engine = IngestionEngine(options.get("project", "."))
    return engine.ingest(source_path, table_name, persist, sample_size, options)


def _derive_name(source_path: str) -> str:
    base = source_path.rstrip("/").split("/")[-1] or source_path.rstrip("/").split("/")[-2]
    base = re.sub(r"\.(gz|zip|zst|snappy|bz2)$", "", base, flags=re.IGNORECASE)
    stem = Path(base).stem or base
    return stem or "ingested"


def _safe_table_name(name: str) -> str:
    cleaned = re.sub(r"\W+", "_", name).strip("_").lower()
    if not cleaned:
        cleaned = "ingested"
    if cleaned[0].isdigit():
        cleaned = f"t_{cleaned}"
    return cleaned
