"""LoadEngine — orchestrate quality gate, LoadPlan, FK waves, and ingestr transport."""

from __future__ import annotations

import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from typing import TYPE_CHECKING

from ai_data_platform.core.exceptions import LoadError
from ai_data_platform.core.logging import get_logger
from ai_data_platform.core.paths import safe_resolve
from ai_data_platform.load.ingestr import get_transport
from ai_data_platform.load.local_sources import staging_file_path
from ai_data_platform.load.plan import build_load_plan
from ai_data_platform.load.quality_gate import run_quality_gate
from ai_data_platform.load.types import LoadReport, TableLoadResult, TableLoadSpec

if TYPE_CHECKING:  # pragma: no cover
    from ai_data_platform.config import ProjectConfig
    from ai_data_platform.metadata.catalog import Catalog

log = get_logger("adp.load")


class LoadEngine:
    def __init__(self, root: str | Path, catalog: Catalog, cfg: ProjectConfig) -> None:
        self.root = Path(root).expanduser().resolve()
        self.catalog = catalog
        self.cfg = cfg

    def load(
        self,
        *,
        destination: str | None = None,
        tables: list[str] | None = None,
        data_dir: str | None = None,
        dry_run: bool = False,
        skip_quality: bool = False,
        force_quality: bool = False,
    ) -> LoadReport:
        from ai_data_platform.sdk import ADPClient

        load_cfg = self.cfg.load
        dest_name = destination or load_cfg.default_destination
        if not dest_name:
            raise LoadError(
                "No destination specified.",
                hint="Set load.default_destination in adp.yaml or pass --destination.",
            )
        dest = self.cfg.destination(dest_name)
        rel_dir = data_dir or self.cfg.output_dir
        out_dir = safe_resolve(self.root, rel_dir)

        plan = build_load_plan(
            self.cfg,
            self.catalog,
            dest,
            data_dir=out_dir,
            tables=tables,
        )

        all_tables: list[str] = []
        has_live_source = False
        stream_tables: set[str] = set()
        for wave in plan.waves:
            for spec in wave:
                all_tables.append(spec.table)
                if spec.is_live_source:
                    has_live_source = True
                if spec.stream:
                    stream_tables.add(spec.table)

        if not has_live_source:
            for table in all_tables:
                staging_file_path(out_dir, table, plan.staging_format)  # type: ignore[arg-type]

        client = ADPClient(self.root)
        quality_score: float | None = None
        if not skip_quality and not has_live_source:
            quality_score = run_quality_gate(
                client,
                out_dir,
                all_tables,
                plan.staging_format,  # type: ignore[arg-type]
                load_cfg,
                force=force_quality,
            )

        transport = get_transport()
        if not dry_run:
            transport.ensure_available()

        if stream_tables:
            log.warning(
                "Stream/CDC mode enabled for: %s. "
                "ingestr will run continuously — press Ctrl+C to stop.",
                ", ".join(sorted(stream_tables)),
            )

        started = time.perf_counter()
        results: list[TableLoadResult] = []
        parallel = load_cfg.parallel_tables
        max_workers = max(
            (min(parallel, len(wave)) for wave in plan.waves if len(wave) > 1),
            default=1,
        )

        with ThreadPoolExecutor(max_workers=max_workers) as pool:
            for wave in plan.waves:
                wave_results = self._run_wave(
                    transport, wave, pool=pool, dry_run=dry_run, parallel=parallel
                )
                results.extend(wave_results)
                if any(r.status == "failed" for r in wave_results):
                    log.error("load wave failed; aborting remaining waves")
                    break

        elapsed = (time.perf_counter() - started) * 1000
        report = LoadReport(
            destination=dest.name,
            staging_format=plan.staging_format,
            quality_score=quality_score,
            tables=results,
            elapsed_ms=elapsed,
        )
        if not report.ok and not dry_run:
            failed = [r for r in results if r.status == "failed"]
            raise LoadError(
                f"Load failed for {len(failed)} table(s): {', '.join(r.table for r in failed)}",
                hint=(failed[0].error or "See logs above.")[:500],
            )
        return report

    def _run_wave(
        self,
        transport: object,
        wave: list[TableLoadSpec],
        *,
        pool: ThreadPoolExecutor,
        dry_run: bool,
        parallel: int,
    ) -> list[TableLoadResult]:
        if len(wave) <= 1 or parallel <= 1:
            return [transport.load_table(spec, dry_run=dry_run) for spec in wave]  # type: ignore[attr-defined]

        out: list[TableLoadResult] = []
        futures = {
            pool.submit(transport.load_table, spec, dry_run=dry_run): spec  # type: ignore[attr-defined]
            for spec in wave
        }
        for fut in as_completed(futures):
            out.append(fut.result())
        order = {s.table: i for i, s in enumerate(wave)}
        out.sort(key=lambda r: order.get(r.table, 0))
        return out
