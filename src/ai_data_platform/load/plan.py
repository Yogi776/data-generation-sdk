"""Compile a LoadPlan from project config + catalog (pure, no I/O)."""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

from ai_data_platform.core.exceptions import LoadError
from ai_data_platform.load.config_models import DestinationConfig, LoadConfig, SourceConfig, StagingFormat
from ai_data_platform.load.local_sources import (
    detect_staging_format,
    resolve_source_table,
    resolve_source_uri,
)
from ai_data_platform.load.ordering import table_waves
from ai_data_platform.load.types import LoadPlan, TableLoadSpec

if TYPE_CHECKING:  # pragma: no cover
    from ai_data_platform.config import GenerationConfig, ProjectConfig
    from ai_data_platform.metadata.catalog import Catalog


def _primary_key_for_table(catalog: Catalog, table: str) -> str | None:
    try:
        meta = catalog.get_table(table)
    except Exception:
        return None
    for col in meta.get("columns", []):
        if col.get("primary_key"):
            return col["name"]
    return None


def build_load_plan(
    cfg: ProjectConfig,
    catalog: Catalog,
    destination: DestinationConfig,
    *,
    data_dir: Path,
    tables: list[str] | None = None,
    load_cfg: LoadConfig | None = None,
    generation_cfg: GenerationConfig | None = None,
) -> LoadPlan:
    load_cfg = load_cfg or cfg.load
    generation_cfg = generation_cfg or cfg.generation
    gen_fmt = generation_cfg.output_format
    if gen_fmt == "sql":
        raise LoadError(
            "Cannot load from sql output format.",
            hint="Regenerate with `adp generate-data -o parquet` then `adp load`.",
        )
    preferred: StagingFormat | None = load_cfg.staging_format
    if preferred is None and gen_fmt in ("parquet", "csv", "duckdb"):
        preferred = gen_fmt  # type: ignore[assignment]
    fmt = detect_staging_format(data_dir, preferred)
    dest_uri = destination.resolved_uri()
    waves_names = table_waves(catalog, tables)
    if not waves_names:
        raise LoadError("No tables to load.", hint="Run `adp scan` and `adp generate-data` first.")

    waves: list[list[TableLoadSpec]] = []
    for wave in waves_names:
        specs: list[TableLoadSpec] = []
        for table in wave:
            pk = destination.primary_key or _primary_key_for_table(catalog, table)
            is_live = destination.source is not None
            if is_live:
                src_uri = destination.source.resolved_uri()
                src_table = destination.source.table or table
                src_sql = destination.source.sql
                src_inc_key = destination.source.incremental_key
            else:
                src_uri = resolve_source_uri(data_dir, table, fmt)
                src_table = resolve_source_table(table, fmt)
                src_sql = None
                src_inc_key = destination.incremental_key
            specs.append(
                TableLoadSpec(
                    table=table,
                    source_uri=src_uri,
                    source_table=src_table,
                    dest_uri=dest_uri,
                    dest_table=destination.dest_table(table),
                    incremental_strategy=destination.incremental_strategy,
                    primary_key=pk if destination.incremental_strategy == "merge" else None,
                    incremental_key=src_inc_key,
                    ingestr_options=dict(destination.ingestr_options),
                    stream=destination.stream.enabled if destination.stream else False,
                    flush_interval=destination.stream.flush_interval if destination.stream else None,
                    flush_records=destination.stream.flush_records if destination.stream else None,
                    metrics_addr=destination.stream.metrics_addr if destination.stream else None,
                    interval_start=destination.stream.interval_start if destination.stream else None,
                    interval_end=destination.stream.interval_end if destination.stream else None,
                    is_live_source=is_live,
                    source_sql=src_sql,
                )
            )
        waves.append(specs)

    return LoadPlan(
        destination_name=destination.name,
        staging_format=fmt,
        data_dir=str(data_dir),
        waves=waves,
    )
