"""DatasetRegistrar: register generated files into a persistent DuckDB database.

Each file (or hive-partitioned directory) becomes a DuckDB **view** over the
source file(s). Views are preferred over materialized tables so exploration
always reflects the latest generated output with zero copy, and Parquet gets
predicate/projection pushdown for free. Detected schema, row counts, partitions
and file paths are written to the explorer metastore.
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any

import duckdb

from ai_data_platform.core.exceptions import ExplorerError
from ai_data_platform.core.paths import adp_dir, safe_resolve
from ai_data_platform.explorer.metastore import ExplorerMetastore

_IDENT_OK = set("abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789_")
_HIVE = re.compile(r"([^/=]+)=([^/]+)")

# Extension -> (format, DuckDB reader function)
_READERS: dict[str, tuple[str, str]] = {
    ".parquet": ("parquet", "read_parquet"),
    ".csv": ("csv", "read_csv_auto"),
    ".tsv": ("csv", "read_csv_auto"),
    ".json": ("json", "read_json_auto"),
    ".ndjson": ("json", "read_json_auto"),
    ".jsonl": ("json", "read_json_auto"),
}

# Prefer these when the same table exists in multiple formats.
_FORMAT_PRIORITY = {"parquet": 0, "json": 1, "csv": 2}


def quote_ident(name: str) -> str:
    if not name or not set(name) <= _IDENT_OK:
        return '"' + name.replace('"', '""') + '"'
    return name


def _sql_str(value: str) -> str:
    return "'" + value.replace("'", "''") + "'"


class DatasetRegistrar:
    def __init__(self, root: str | Path, metastore: ExplorerMetastore) -> None:
        self.root = Path(root).expanduser().resolve()
        self.metastore = metastore

    def db_path(self, db_filename: str) -> Path:
        return adp_dir(self.root) / db_filename

    def register_dir(
        self,
        data_dir: str | Path,
        *,
        dataset: str,
        db_filename: str,
        replace: bool = True,
    ) -> dict[str, Any]:
        """Discover data files under ``data_dir`` and register each as a view."""
        target = safe_resolve(self.root, data_dir)
        if not target.exists():
            raise ExplorerError(
                f"Data directory {target} does not exist.",
                hint="Generate data first, or pass an existing data_dir.",
            )

        candidates = self._discover(target)
        if not candidates:
            raise ExplorerError(
                f"No csv/parquet/json files found in {target}.",
                hint="Run `adp generate-data` (parquet or csv), then register.",
            )

        db = self.db_path(db_filename)
        registered: list[dict[str, Any]] = []
        skipped: list[str] = []

        con = duckdb.connect(str(db))
        try:
            for table, (fmt, reader, path_expr, part_keys) in candidates.items():
                ident = quote_ident(table)
                verb = "CREATE OR REPLACE VIEW" if replace else "CREATE VIEW IF NOT EXISTS"
                try:
                    con.execute(f"{verb} {ident} AS SELECT * FROM {reader}({path_expr})")
                except duckdb.Error as e:  # noqa: PERF203 - per-table isolation is intentional
                    skipped.append(f"{table}: {e}")
                    continue

                cols = con.execute(f"DESCRIBE {ident}").fetchall()
                columns = [
                    {"name": r[0], "type": str(r[1]), "nullable": str(r[2]).upper() != "NO"}
                    for r in cols
                ]
                row_count = con.execute(f"SELECT count(*) FROM {ident}").fetchone()
                n = int(row_count[0]) if row_count else None

                self.metastore.upsert_table(
                    dataset,
                    name=table,
                    file_format=fmt,
                    path=str(path_expr).strip("'"),
                    row_count=n,
                    partitioned=bool(part_keys),
                    partition_keys=part_keys,
                    columns=columns,
                )
                registered.append(
                    {
                        "table": table,
                        "format": fmt,
                        "path": str(path_expr).strip("'"),
                        "row_count": n,
                        "column_count": len(columns),
                        "partitioned": bool(part_keys),
                        "partition_keys": part_keys,
                    }
                )
        finally:
            con.close()

        self.metastore.upsert_dataset(dataset, str(db))
        return {
            "dataset": dataset,
            "db_path": str(db),
            "registered": registered,
            "skipped": skipped,
        }

    def _discover(self, target: Path) -> dict[str, tuple[str, str, str, list[str]]]:
        """Map table name -> (format, reader, path_expr, partition_keys).

        Handles flat files and hive-partitioned directories. When a table is
        available in multiple formats, the highest-priority format wins.
        """
        found: dict[str, tuple[str, str, str, list[str]]] = {}
        best_priority: dict[str, int] = {}

        # Hive-partitioned directories: subdir named `table` containing key=value/…
        for child in sorted(target.iterdir()):
            if child.is_dir():
                parts = list(child.rglob("*.parquet"))
                if parts and any(_HIVE.search(str(p.relative_to(child))) for p in parts):
                    keys = self._partition_keys(child, parts)
                    glob = _sql_str(f"{child}/**/*.parquet")
                    found[child.name] = (
                        "parquet",
                        "read_parquet",
                        f"{glob}, hive_partitioning=true",
                        keys,
                    )
                    best_priority[child.name] = -1  # partitioned dir beats flat files

        # Flat files
        for f in sorted(target.iterdir()):
            if not f.is_file():
                continue
            meta = _READERS.get(f.suffix.lower())
            if meta is None:
                continue
            fmt, reader = meta
            table = f.stem
            prio = _FORMAT_PRIORITY.get(fmt, 9)
            if table in best_priority and best_priority[table] <= prio:
                continue
            best_priority[table] = prio
            found[table] = (fmt, reader, _sql_str(str(f)), [])

        return found

    @staticmethod
    def _partition_keys(base: Path, parts: list[Path]) -> list[str]:
        keys: list[str] = []
        for p in parts[:1]:
            for seg in p.relative_to(base).parts:
                m = _HIVE.fullmatch(seg)
                if m and m.group(1) not in keys:
                    keys.append(m.group(1))
        return keys
