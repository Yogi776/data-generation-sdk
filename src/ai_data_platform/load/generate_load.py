"""Generate FK-safe waves and load each wave to a warehouse in one pass."""

from __future__ import annotations

import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from typing import TYPE_CHECKING, Any

from ai_data_platform.core.exceptions import LoadError
from ai_data_platform.core.logging import get_logger
from ai_data_platform.core.paths import safe_resolve
from ai_data_platform.generator.engine import GenerationPlan, build_plan
from ai_data_platform.generator.executor_dispatch import dispatch_generate
from ai_data_platform.load.ingestr import get_transport
from ai_data_platform.load.ordering import table_waves
from ai_data_platform.load.plan import build_load_plan
from ai_data_platform.load.types import LoadReport, TableLoadResult

if TYPE_CHECKING:  # pragma: no cover
    from ai_data_platform.config import ProjectConfig
    from ai_data_platform.metadata.catalog import Catalog

log = get_logger("adp.generate_load")


class GenerateLoadEngine:
    """Generate each FK wave, then immediately load it to the destination."""

    def __init__(self, root: str | Path, catalog: Catalog, cfg: ProjectConfig) -> None:
        self.root = Path(root).expanduser().resolve()
        self.catalog = catalog
        self.cfg = cfg

    def run(
        self,
        *,
        destination: str | None = None,
        tables: list[str] | None = None,
        rows: int | None = None,
        seed: int | None = None,
        rows_per_table: dict[str, int] | None = None,
        output_dir: str | None = None,
        dry_run: bool = False,
        skip_quality: bool = True,
    ) -> dict[str, Any]:
        load_cfg = self.cfg.load
        gen_cfg = self.cfg.generation
        dest_name = destination or load_cfg.default_destination
        if not dest_name:
            raise LoadError(
                "No destination specified.",
                hint="Set load.default_destination in adp.yaml or pass --destination.",
            )
        dest = self.cfg.destination(dest_name)
        if dest.source is not None:
            raise LoadError(
                "generate-load writes synthetic data; use `adp load` for live sources.",
            )

        rel_dir = output_dir or self.cfg.output_dir
        out_dir = safe_resolve(self.root, rel_dir)
        out_dir.mkdir(parents=True, exist_ok=True)

        plan = GenerationPlan.model_validate(
            build_plan(
                self.catalog,
                rows=rows or gen_cfg.default_rows,
                seed=seed if seed is not None else gen_cfg.seed,
                tables=tables,
                rows_per_table=rows_per_table,
                chunk_rows=gen_cfg.chunk_rows,
            )
        )
        wave_names = table_waves(self.catalog, tables)

        transport = get_transport()
        if not dry_run:
            transport.ensure_available()

        key_pool: dict[tuple[str, str], Any] = {}
        gen_results: dict[str, Any] = {}
        load_results: list[TableLoadResult] = []
        started = time.perf_counter()
        parallel = load_cfg.parallel_tables

        with ThreadPoolExecutor(max_workers=max(1, parallel)) as pool:
            for wave_idx, wave in enumerate(wave_names):
                wave_tables = set(wave)
                log.info(
                    "wave %d/%d: generate %s",
                    wave_idx + 1,
                    len(wave_names),
                    ", ".join(sorted(wave_tables)),
                )

                if dry_run:
                    for table in wave_tables:
                        gen_results[table] = {
                            "rows": next(t.rows for t in plan.tables if t.name == table),
                            "path": str(out_dir / f"{table}.parquet"),
                        }
                    wave_plan = build_load_plan(
                        self.cfg,
                        self.catalog,
                        dest,
                        data_dir=out_dir,
                        tables=wave,
                        staging_must_exist=False,
                    )
                    load_results.extend(
                        transport.load_table(spec, dry_run=True)
                        for spec in wave_plan.waves[0]
                    )
                    continue

                wave_gen = dispatch_generate(
                    plan,
                    out_dir,
                    output_format=gen_cfg.output_format,
                    cfg=gen_cfg,
                    tables=wave_tables,
                    key_pool=key_pool,
                )
                gen_results.update(wave_gen)

                wave_plan = build_load_plan(
                    self.cfg,
                    self.catalog,
                    dest,
                    data_dir=out_dir,
                    tables=wave,
                )
                wave_specs = wave_plan.waves[0]

                if len(wave_specs) <= 1 or parallel <= 1:
                    load_results.extend(transport.load_table(spec) for spec in wave_specs)
                else:
                    futures = {
                        pool.submit(transport.load_table, spec): spec for spec in wave_specs
                    }
                    wave_out: list[TableLoadResult] = []
                    for fut in as_completed(futures):
                        wave_out.append(fut.result())
                    order = {s.table: i for i, s in enumerate(wave_specs)}
                    wave_out.sort(key=lambda r: order.get(r.table, 0))
                    load_results.extend(wave_out)

                if any(r.status == "failed" for r in load_results[-len(wave_specs) :]):
                    log.error("wave %d failed; aborting", wave_idx + 1)
                    break

        elapsed = (time.perf_counter() - started) * 1000
        staging_format = gen_cfg.output_format if gen_cfg.output_format != "sql" else "parquet"
        report = LoadReport(
            destination=dest.name,
            staging_format=staging_format,  # type: ignore[arg-type]
            quality_score=None if skip_quality else None,
            tables=load_results,
            elapsed_ms=elapsed,
        )
        if not report.ok and not dry_run:
            failed = [r for r in load_results if r.status == "failed"]
            raise LoadError(
                f"generate-load failed for {len(failed)} table(s): "
                f"{', '.join(r.table for r in failed)}",
                hint=(failed[0].error or "See logs above.")[:500],
            )

        return {
            "destination": dest.name,
            "seed": plan.seed,
            "format": gen_cfg.output_format,
            "generated": gen_results,
            "load": {
                "ok": report.ok,
                "elapsed_ms": report.elapsed_ms,
                "tables": [
                    {
                        "table": t.table,
                        "dest_table": t.dest_table,
                        "status": t.status,
                        "elapsed_ms": t.elapsed_ms,
                        "error": t.error,
                    }
                    for t in load_results
                ],
            },
        }
