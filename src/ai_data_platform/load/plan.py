"""Compile a LoadPlan from project config + catalog (pure, no I/O)."""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

from ai_data_platform.core.exceptions import LoadError
from ai_data_platform.load.config_models import DestinationConfig, LoadConfig, StagingFormat
from ai_data_platform.load.local_sources import (
    detect_staging_format,
    resolve_source_table,
    resolve_source_uri,
)
from ai_data_platform.load.ordering import table_waves
from ai_data_platform.load.partition_hints import auto_extract_options
from ai_data_platform.load.types import LoadPlan, TableLoadSpec

if TYPE_CHECKING:  # pragma: no cover
    from ai_data_platform.config import GenerationConfig, ProjectConfig
    from ai_data_platform.metadata.catalog import Catalog


def build_load_plan(
    cfg: ProjectConfig,
    catalog: Catalog,
    destination: DestinationConfig,
    *,
    data_dir: Path,
    tables: list[str] | None = None,
    load_cfg: LoadConfig | None = None,
    generation_cfg: GenerationConfig | None = None,
    staging_must_exist: bool = True,
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

    all_wave_tables = [t for wave in waves_names for t in wave]
    pk_map = (
        {}
        if destination.primary_key
        else catalog.primary_keys_for_tables(all_wave_tables)
    )

    waves: list[list[TableLoadSpec]] = []
    for wave in waves_names:
        specs: list[TableLoadSpec] = []
        for table in wave:
            pk = destination.primary_key or pk_map.get(table)
            is_live = destination.source is not None
            if is_live:
                src_uri = destination.source.resolved_uri()
                src_table = destination.source.table or table
                src_sql = destination.source.sql
                src_inc_key = destination.source.incremental_key
                src_options = dict(destination.source.ingestr_options)
            else:
                src_uri = resolve_source_uri(data_dir, table, fmt, must_exist=staging_must_exist)
                src_table = resolve_source_table(table, fmt)
                src_sql = None
                src_inc_key = destination.incremental_key
                src_options = {}
            ingestr_options = {
                **src_options,
                **destination.ingestr_options,
            }
            if (
                not is_live
                and destination.auto_extract_partition
                and destination.incremental_strategy != "replace"
            ):
                row_count: int | None = None
                try:
                    row_count = catalog.get_table(table).get("row_count")
                except Exception:
                    pass
                hints = auto_extract_options(catalog, table, row_count=row_count)
                ingestr_options = {**hints, **ingestr_options}
            ingestr_options = {
                **ingestr_options,
                **destination.table_ingestr_options.get(table, {}),
            }
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
                    ingestr_options=ingestr_options,
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
