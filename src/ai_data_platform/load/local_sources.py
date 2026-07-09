"""Resolve local staging artifacts for ingestr source-uri."""

from __future__ import annotations

from pathlib import Path

from ai_data_platform.core.exceptions import LoadError
from ai_data_platform.load.config_models import StagingFormat


def detect_staging_format(data_dir: Path, preferred: StagingFormat | None) -> StagingFormat:
    if preferred:
        return preferred
    if any(data_dir.glob("*.parquet")):
        return "parquet"
    if any(data_dir.glob("*.csv")):
        return "csv"
    if (data_dir / "generated.duckdb").exists():
        return "duckdb"
    raise LoadError(
        f"No staging files found in {data_dir}.",
        hint="Run `adp generate-data` first (parquet/csv/duckdb output).",
    )


def resolve_source_uri(data_dir: Path, table: str, fmt: StagingFormat) -> str:
    """Per-table ingestr source URI (ingestr uses csv://, parquet://, duckdb://)."""
    path = staging_file_path(data_dir, table, fmt)
    if fmt == "duckdb":
        return f"duckdb:///{path.resolve()}"
    if fmt == "parquet":
        return f"parquet://{path.resolve()}"
    return f"csv://{path.resolve()}"


def resolve_source_table(table: str, fmt: StagingFormat) -> str:
    if fmt == "duckdb":
        return table
    if fmt == "parquet":
        return f"{table}#parquet"
    return table


def staging_file_path(data_dir: Path, table: str, fmt: StagingFormat) -> Path:
    if fmt == "duckdb":
        return data_dir / "generated.duckdb"
    ext = "parquet" if fmt == "parquet" else "csv"
    path = data_dir / f"{table}.{ext}"
    if not path.exists():
        raise LoadError(
            f"Staging file missing for table {table!r}: {path}",
            hint="Run `adp generate-data` or pass --tables with existing outputs.",
        )
    return path


def max_staging_mtime(data_dir: Path, tables: list[str], fmt: StagingFormat) -> float:
    if fmt == "duckdb":
        p = data_dir / "generated.duckdb"
        return p.stat().st_mtime if p.exists() else 0.0
    mtimes = []
    for t in tables:
        try:
            mtimes.append(staging_file_path(data_dir, t, fmt).stat().st_mtime)
        except LoadError:
            continue
    return max(mtimes) if mtimes else 0.0
