"""DuckDB reader selector.

Turns a :class:`~ai_data_platform.ingestion.detector.Detection` into a concrete
way to get the data into DuckDB:

* **Native** formats (csv/tsv/json/ndjson/parquet, incl. folders/partitions/
  globs, compression, cloud paths, and — via extensions — delta/iceberg) become a
  DuckDB table-function scan expression, so they can back a lazy **view** with
  predicate/projection pushdown and streaming (no full load into memory).
* **Loaded** formats (excel/arrow/orc/avro/sqlite/postgres_sql) are read in
  Python into an Arrow table and **materialized** as a DuckDB table (the only way
  to keep them queryable across connections).

Optional pieces (cloud httpfs/azure, delta, iceberg, sqlite_scanner, avro) are
loaded lazily and degrade with a clear :class:`FormatDependencyError`.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import TYPE_CHECKING, Any

from ai_data_platform.core.exceptions import (
    FormatDependencyError,
    IngestionError,
    UnsafeSQLError,
)
from ai_data_platform.core.logging import get_logger
from ai_data_platform.ingestion.detector import Detection

if TYPE_CHECKING:  # pragma: no cover
    import duckdb

log = get_logger("adp.ingestion.reader")

_IDENT_OK = set("abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789_")

_FORBIDDEN = re.compile(
    r"(?is)\b(insert|update|delete|drop|alter|create|truncate|grant|revoke|"
    r"attach|detach|call|merge|replace|vacuum|pragma|set|reset|install|load|"
    r"export|import|checkpoint|use|copy)\b"
)


def quote_ident(name: str) -> str:
    if not name or not set(name) <= _IDENT_OK:
        return '"' + name.replace('"', '""') + '"'
    return name


def sql_str(value: str) -> str:
    return "'" + value.replace("'", "''") + "'"


def guard_select(sql: str) -> str:
    """Accept a single read-only SELECT/WITH; reject everything else."""
    stripped = sql.strip().rstrip(";").strip()
    if not stripped:
        raise UnsafeSQLError("Empty SQL statement.")
    if ";" in stripped:
        raise UnsafeSQLError("Multiple SQL statements are not allowed.")
    head = stripped.split(None, 1)[0].lower()
    if head not in ("select", "with"):
        raise UnsafeSQLError(f"Only SELECT queries are allowed (got {head!r}).")
    if _FORBIDDEN.search(stripped):
        raise UnsafeSQLError("Statement contains a forbidden keyword.")
    return stripped


@dataclass
class ReaderPlan:
    fmt: str
    native: bool
    scan_expr: str | None = None  # for native formats (table function call)
    arrow_table: Any | None = None  # for loaded formats
    materialize: bool = False  # loaded formats must become a physical table
    sheet_used: str | None = None
    excel_sheets: list[str] = field(default_factory=list)
    notes: list[str] = field(default_factory=list)


# Community/core extensions we may need, and the remedy text if unavailable.
_EXT_REMEDY = {
    "httpfs": "cloud/URL access needs DuckDB httpfs (auto-installed; check network).",
    "azure": "Azure paths need the DuckDB azure extension and credentials.",
    "sqlite_scanner": "SQLite reading needs the DuckDB sqlite extension.",
    "delta": "Delta Lake needs the DuckDB delta extension.",
    "iceberg": "Iceberg needs the DuckDB iceberg extension.",
    "avro": "Avro needs the DuckDB avro community extension or fastavro.",
}


class DuckDBReader:
    def __init__(self, con: duckdb.DuckDBPyConnection) -> None:
        self.con = con
        self._loaded: set[str] = set()

    # -- extensions ----------------------------------------------------------
    def ensure_extension(self, name: str, *, community: bool = False) -> None:
        if name in self._loaded:
            return
        try:
            src = " FROM community" if community else ""
            self.con.execute(f"INSTALL {name}{src}")
            self.con.execute(f"LOAD {name}")
            self._loaded.add(name)
        except Exception as e:  # noqa: BLE001
            raise FormatDependencyError(name, _EXT_REMEDY.get(name, str(e))) from e

    def _ensure_cloud(self, detection: Detection) -> None:
        if detection.scheme in ("s3", "gs", "http"):
            self.ensure_extension("httpfs")
        elif detection.scheme == "az":
            self.ensure_extension("azure")

    # -- planning ------------------------------------------------------------
    def build(
        self, detection: Detection, options: dict[str, Any], sample_size: int
    ) -> ReaderPlan:
        fmt = detection.fmt
        builder = getattr(self, f"_plan_{fmt}", None)
        if builder is None:
            raise IngestionError(f"No reader for format {fmt!r}.")
        return builder(detection, options, sample_size)

    # -- native text/columnar -----------------------------------------------
    def _path_expr(self, detection: Detection, default_glob: str) -> str:
        path = detection.source_path
        if detection.is_folder and "*" not in path:
            path = path.rstrip("/") + default_glob
        return sql_str(path)

    def _plan_csv(self, d: Detection, o: dict[str, Any], sample: int) -> ReaderPlan:
        self._ensure_cloud(d)
        args = [self._path_expr(d, "/**/*.csv")]
        delim = o.get("delimiter") or d.delimiter or ","
        args.append(f"delim={sql_str(delim)}")
        header = o.get("has_header")
        header = d.has_header if header is None else header
        args.append(f"header={'true' if header else 'false'}")
        args.append(f"sample_size={int(sample)}")
        args.append("union_by_name=true")
        if o.get("ignore_errors"):
            args.append("ignore_errors=true")
        expr = f"read_csv_auto({', '.join(args)})"
        return ReaderPlan(fmt="csv", native=True, scan_expr=expr, notes=list(d.notes))

    _plan_tsv = _plan_csv

    def _plan_json(self, d: Detection, o: dict[str, Any], sample: int) -> ReaderPlan:
        if o.get("flatten"):
            from ai_data_platform.ingestion.json_flattener import flatten_json_file

            table = flatten_json_file(d.source_path, o)
            return ReaderPlan(
                fmt="json", native=False, arrow_table=table, materialize=True,
                notes=["nested JSON flattened via json_normalize"],
            )
        self._ensure_cloud(d)
        expr = f"read_json_auto({self._path_expr(d, '/**/*.json')})"
        return ReaderPlan(fmt="json", native=True, scan_expr=expr, notes=list(d.notes))

    def _plan_ndjson(self, d: Detection, o: dict[str, Any], sample: int) -> ReaderPlan:
        if o.get("flatten"):
            from ai_data_platform.ingestion.json_flattener import flatten_json_file

            table = flatten_json_file(d.source_path, {**o, "ndjson": True})
            return ReaderPlan(
                fmt="ndjson", native=False, arrow_table=table, materialize=True,
                notes=["NDJSON flattened via json_normalize"],
            )
        self._ensure_cloud(d)
        expr = (
            f"read_json_auto({self._path_expr(d, '/**/*.jsonl')}, "
            "format='newline_delimited')"
        )
        return ReaderPlan(fmt="ndjson", native=True, scan_expr=expr, notes=list(d.notes))

    def _plan_parquet(self, d: Detection, o: dict[str, Any], sample: int) -> ReaderPlan:
        self._ensure_cloud(d)
        path = self._path_expr(d, "/**/*.parquet")
        hive = "true" if d.partitioned else "false"
        expr = f"read_parquet({path}, hive_partitioning={hive})"
        return ReaderPlan(fmt="parquet", native=True, scan_expr=expr, notes=list(d.notes))

    def _plan_delta(self, d: Detection, o: dict[str, Any], sample: int) -> ReaderPlan:
        self._ensure_cloud(d)
        self.ensure_extension("delta")
        expr = f"delta_scan({sql_str(d.source_path)})"
        return ReaderPlan(fmt="delta", native=True, scan_expr=expr, notes=["Delta Lake table"])

    def _plan_iceberg(self, d: Detection, o: dict[str, Any], sample: int) -> ReaderPlan:
        self._ensure_cloud(d)
        self.ensure_extension("iceberg")
        expr = f"iceberg_scan({sql_str(d.source_path)})"
        return ReaderPlan(fmt="iceberg", native=True, scan_expr=expr, notes=["Iceberg table"])

    # -- loaded via Arrow ----------------------------------------------------
    def _plan_excel(self, d: Detection, o: dict[str, Any], sample: int) -> ReaderPlan:
        from ai_data_platform.ingestion.excel_reader import read_excel

        table, sheet, sheets = read_excel(d.source_path, o)
        return ReaderPlan(
            fmt="excel", native=False, arrow_table=table, materialize=True,
            sheet_used=sheet, excel_sheets=sheets,
            notes=[f"Excel sheet {sheet!r} of {len(sheets)}"],
        )

    def _plan_arrow(self, d: Detection, o: dict[str, Any], sample: int) -> ReaderPlan:
        try:
            import pyarrow.feather as feather

            table = feather.read_table(Path(d.source_path).expanduser())
        except Exception as e:  # noqa: BLE001
            raise IngestionError(f"Failed to read Arrow/Feather file: {e}") from e
        return ReaderPlan(
            fmt="arrow", native=False, arrow_table=table, materialize=True,
            notes=["Arrow IPC/Feather via pyarrow"],
        )

    def _plan_orc(self, d: Detection, o: dict[str, Any], sample: int) -> ReaderPlan:
        try:
            import pyarrow.orc as orc

            table = orc.read_table(Path(d.source_path).expanduser())
        except ImportError as e:  # pragma: no cover
            raise FormatDependencyError("orc", "pyarrow with ORC support required.") from e
        except Exception as e:  # noqa: BLE001
            raise IngestionError(f"Failed to read ORC file: {e}") from e
        return ReaderPlan(
            fmt="orc", native=False, arrow_table=table, materialize=True,
            notes=["ORC via pyarrow"],
        )

    def _plan_avro(self, d: Detection, o: dict[str, Any], sample: int) -> ReaderPlan:
        # Prefer the DuckDB avro community extension (keeps it native-ish); fall
        # back to fastavro → Arrow.
        try:
            self.ensure_extension("avro", community=True)
            expr = f"read_avro({sql_str(d.source_path)})"
            return ReaderPlan(fmt="avro", native=True, scan_expr=expr, notes=["Avro via DuckDB"])
        except FormatDependencyError:
            pass
        try:
            import fastavro
            import pyarrow as pa

            with open(Path(d.source_path).expanduser(), "rb") as fh:
                records = list(fastavro.reader(fh))
            table = pa.Table.from_pylist(records)
        except ImportError as e:
            raise FormatDependencyError(
                "avro", "Install the DuckDB avro extension or `pip install fastavro`."
            ) from e
        except Exception as e:  # noqa: BLE001
            raise IngestionError(f"Failed to read Avro file: {e}") from e
        return ReaderPlan(
            fmt="avro", native=False, arrow_table=table, materialize=True,
            notes=["Avro via fastavro"],
        )

    def _plan_sqlite(self, d: Detection, o: dict[str, Any], sample: int) -> ReaderPlan:
        self.ensure_extension("sqlite_scanner")
        src_path = str(Path(d.source_path).expanduser())
        self.con.execute(f"ATTACH {sql_str(src_path)} AS _adp_src (TYPE sqlite)")
        try:
            tables = [
                r[0]
                for r in self.con.execute(
                    "SELECT name FROM _adp_src.sqlite_master "
                    "WHERE type='table' ORDER BY name"
                ).fetchall()
            ]
            if not tables:
                raise IngestionError(f"No tables found in SQLite database {src_path}.")
            chosen = o.get("sqlite_table") or tables[0]
            if chosen not in tables:
                raise IngestionError(
                    f"Table {chosen!r} not in SQLite db.", hint=f"Available: {', '.join(tables)}."
                )
            table = self.con.execute(
                f"SELECT * FROM _adp_src.{quote_ident(chosen)}"  # noqa: S608 - ident quoted
            ).arrow()
        finally:
            self.con.execute("DETACH _adp_src")
        return ReaderPlan(
            fmt="sqlite", native=False, arrow_table=table, materialize=True,
            notes=[f"SQLite table {chosen!r}"],
        )

    def _plan_postgres_sql(self, d: Detection, o: dict[str, Any], sample: int) -> ReaderPlan:
        from ai_data_platform.ingestion.pg_dump import load_pg_copy_block

        table, name = load_pg_copy_block(d.source_path, o)
        return ReaderPlan(
            fmt="postgres_sql", native=False, arrow_table=table, materialize=True,
            notes=[f"PostgreSQL dump COPY block for {name!r}"],
        )

    # -- relation creation ---------------------------------------------------
    def create_relation(self, name: str, plan: ReaderPlan, *, persist: bool) -> str:
        ident = quote_ident(name)
        if plan.native and not plan.materialize:
            if persist:
                self.con.execute(f"CREATE OR REPLACE TABLE {ident} AS SELECT * FROM {plan.scan_expr}")
                return "table"
            self.con.execute(f"CREATE OR REPLACE VIEW {ident} AS SELECT * FROM {plan.scan_expr}")
            return "view"
        # Loaded (Arrow) formats must be materialized to persist across connections.
        arrow_table = plan.arrow_table
        self.con.register("_adp_arrow", arrow_table)
        try:
            self.con.execute(f"CREATE OR REPLACE TABLE {ident} AS SELECT * FROM _adp_arrow")
        finally:
            self.con.unregister("_adp_arrow")
        return "table"

    def ddl_for(self, name: str, plan: ReaderPlan, *, persist: bool) -> str:
        """The CREATE statement text (for the metadata report)."""
        ident = quote_ident(name)
        if plan.native and not plan.materialize:
            verb = "CREATE OR REPLACE TABLE" if persist else "CREATE OR REPLACE VIEW"
            suffix = "" if persist else ""
            return f"{verb} {ident} AS SELECT * FROM {plan.scan_expr}{suffix};"
        return f"CREATE OR REPLACE TABLE {ident} AS SELECT * FROM <loaded {plan.fmt} source>;"
