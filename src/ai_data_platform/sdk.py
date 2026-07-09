"""ADPClient: the Python SDK and the single backend behind CLI, API, and MCP.

"One backend, many faces": every interface calls these use cases; none of them
reimplements logic.

Example:
    from ai_data_platform import ADPClient

    client = ADPClient(project_path=".")
    client.scan()
    client.profile()
    client.generate_data(rows=10_000)
    client.create_semantic_model()
"""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING, Any

from ai_data_platform.config import (
    ProjectConfig,
    SourceConfig,
    default_config,
    load_config,
    save_config,
)
from ai_data_platform.core.exceptions import ADPError
from ai_data_platform.core.paths import safe_resolve
from ai_data_platform.metadata.catalog import Catalog

if TYPE_CHECKING:  # pragma: no cover
    from ai_data_platform.explorer.service import ExplorerService


class ADPClient:
    """Facade over all platform use cases, rooted at a project directory."""

    def __init__(self, project_path: str | Path = ".") -> None:
        self.root = Path(project_path).expanduser().resolve()
        self._catalog: Catalog | None = None
        self._explorer: ExplorerService | None = None

    # -- lazy internals ------------------------------------------------------
    @property
    def config(self) -> ProjectConfig:
        return load_config(self.root)

    @property
    def catalog(self) -> Catalog:
        if self._catalog is None:
            self._catalog = Catalog(self.root)
        return self._catalog

    @property
    def explorer(self) -> ExplorerService:
        """MCP Data Explorer backend (DuckDB registration + governed queries)."""
        if self._explorer is None:
            from ai_data_platform.explorer.service import ExplorerService

            cfg = self.config
            self._explorer = ExplorerService(
                self.root,
                cfg.explorer,
                default_data_dir=cfg.output_dir,
                provider_cfg=cfg.model_provider,
            )
        return self._explorer

    # -- project -------------------------------------------------------------
    def init(self, project_name: str | None = None, *, force: bool = False) -> Path:
        """Create adp.yaml (and .adp/) in the project directory."""
        from ai_data_platform.config import config_path

        path = config_path(self.root)
        if path.exists() and not force:
            from ai_data_platform.core.exceptions import ConfigError

            raise ConfigError(
                f"{path} already exists.", hint="Use force=True / --force to overwrite."
            )
        cfg = default_config(project_name or self.root.name)
        self.root.mkdir(parents=True, exist_ok=True)
        path = save_config(cfg, self.root)
        try:
            from ai_data_platform.agent.setup import install_agent

            install_agent(project_root=self.root, clients=["all"])
        except Exception:
            pass  # agent setup is best-effort during init
        return path

    def add_source(self, source: SourceConfig, *, test: bool = True) -> dict[str, Any]:
        """Add (or replace) a source in adp.yaml; optionally test the connection."""
        cfg = self.config
        cfg.sources = [s for s in cfg.sources if s.name != source.name] + [source]
        result: dict[str, Any] = {"name": source.name, "type": source.type}
        if test:
            from ai_data_platform.connectors import get_connector

            check = get_connector(source).test_connection()
            result.update(ok=check.ok, message=check.message)
            if not check.ok:
                return result  # do not persist a broken source
        save_config(cfg, self.root)
        result.setdefault("ok", True)
        return result

    def apply_spec(self, spec_path: str | Path) -> dict[str, Any]:
        """Apply a declarative dataset spec (YAML) — generate without seed data."""
        from ai_data_platform.spec import apply_spec, load_spec

        gen = self.config.generation
        calendar_defaults = {
            "fiscal_year_start_month": gen.fiscal_year_start_month,
            "hemisphere": gen.hemisphere,
            "country": gen.holiday_country,
        }
        return apply_spec(
            self.catalog,
            load_spec(safe_resolve(self.root, spec_path)),
            calendar_defaults=calendar_defaults,
        )

    def propose_spec(self, description: str, research_notes: str = "") -> dict[str, Any]:
        """AI-draft a validated dataset spec from a description (+ optional
        research notes with real-world distributions). Does not apply it."""
        from ai_data_platform.spec import propose_spec

        yaml_text, spec = propose_spec(self.config.model_provider, description, research_notes)
        return {
            "yaml": yaml_text,
            "tables": [t.name for t in spec.tables],
            "columns": sum(len(t.columns) for t in spec.tables),
        }

    # -- metadata --------------------------------------------------------------
    def scan(self, source: str | None = None) -> list[dict[str, Any]]:
        from ai_data_platform.metadata.scan import scan_all, scan_source

        if source:
            return [scan_source(self.config, self.catalog, source)]
        return scan_all(self.config, self.catalog)

    def profile(self, source: str | None = None, sample_rows: int = 10_000) -> list[dict[str, Any]]:
        from ai_data_platform.profiler.profiler import profile_source

        cfg = self.config
        names = [source] if source else [s.name for s in cfg.sources]
        out: list[dict[str, Any]] = []
        for name in names:
            out += profile_source(cfg, self.catalog, name, sample_rows=sample_rows)
        return out

    def list_tables(self, source: str | None = None) -> list[dict[str, Any]]:
        return self.catalog.list_tables(source)

    def get_table(self, table: str) -> dict[str, Any]:
        return self.catalog.get_table(table)

    def search_metadata(self, query: str, limit: int = 20) -> list[dict[str, Any]]:
        return self.catalog.search(query, limit)

    # -- generation ---------------------------------------------------------------
    def build_plan(
        self,
        rows: int | None = None,
        tables: list[str] | None = None,
        seed: int | None = None,
        rows_per_table: dict[str, int] | None = None,
    ) -> dict[str, Any]:
        from ai_data_platform.generator.engine import build_plan

        gen = self.config.generation
        plan = build_plan(
            self.catalog,
            rows=rows or gen.default_rows,
            seed=seed if seed is not None else gen.seed,
            tables=tables,
            rows_per_table=rows_per_table,
            chunk_rows=gen.chunk_rows,
        )
        return plan.model_dump()

    def save_plan(
        self,
        path: str | Path,
        rows: int | None = None,
        tables: list[str] | None = None,
        seed: int | None = None,
        rows_per_table: dict[str, int] | None = None,
    ) -> Path:
        """Write the generation Plan IR to JSON (for Go executor or inspection)."""
        import json

        from ai_data_platform.core.paths import safe_write_text

        plan = self.build_plan(rows, tables, seed, rows_per_table)
        return safe_write_text(self.root, path, json.dumps(plan, indent=2) + "\n")

    def analyze_complexity(
        self, rows: int | None = None, tables: list[str] | None = None, seed: int | None = None
    ) -> dict[str, Any]:
        """Static complexity analysis of the plan: per-column cost classes, a
        module complexity table, and hot-spot warnings. No generation."""
        from ai_data_platform.generator.engine import GenerationPlan
        from ai_data_platform.optimizer import analyze_complexity

        plan = GenerationPlan.model_validate(self.build_plan(rows, tables, seed))
        return analyze_complexity(plan)

    def plan_execution(
        self,
        rows: int | None = None,
        tables: list[str] | None = None,
        seed: int | None = None,
        memory_budget_mb: float | None = None,
    ) -> dict[str, Any]:
        """Execution plan for a run: batch size, parallelism, format, partitioning,
        memory estimate, runtime class, and optimization warnings. No generation."""
        from ai_data_platform.generator.engine import GenerationPlan
        from ai_data_platform.optimizer import plan_execution

        plan = GenerationPlan.model_validate(self.build_plan(rows, tables, seed))
        return plan_execution(plan, self.config.generation, memory_budget_mb=memory_budget_mb)

    def generate_data(
        self,
        rows: int | None = None,
        *,
        tables: list[str] | None = None,
        seed: int | None = None,
        rows_per_table: dict[str, int] | None = None,
        output_format: str | None = None,
        output_dir: str | None = None,
        dataset: str = "default",
        register: bool | None = None,
        optimized: bool = False,
    ) -> dict[str, Any]:
        from ai_data_platform.generator.engine import GenerationPlan
        from ai_data_platform.generator.executor_dispatch import dispatch_generate

        cfg = self.config
        plan = GenerationPlan.model_validate(self.build_plan(rows, tables, seed, rows_per_table))
        rel_dir = output_dir or cfg.output_dir
        out_dir = safe_resolve(self.root, rel_dir)
        fmt = output_format or cfg.generation.output_format
        # apply execution-plan recommendations (batch size, parallelism, format)
        if optimized:
            from ai_data_platform.optimizer import plan_execution

            ep = plan_execution(plan, cfg.generation)
            plan.chunk_rows = int(ep["recommended_batch_size"])
            cfg.generation.parallel_workers = int(ep["parallelism"])
            if output_format is None:
                fmt = ep["recommended_format"]
        results = dispatch_generate(
            plan, out_dir, output_format=fmt, cfg=cfg.generation
        )
        out: dict[str, Any] = {"seed": plan.seed, "format": fmt, "tables": results}

        # Auto-register generated files into DuckDB for exploration via MCP.
        should_register = (
            register
            if register is not None
            else (cfg.explorer.enabled and cfg.explorer.auto_register)
        )
        if should_register and fmt in ("csv", "parquet", "json"):
            try:
                reg = self.explorer.register(dataset=dataset, data_dir=rel_dir)
                out["explorer"] = {
                    "dataset": reg["dataset"],
                    "db_path": reg["db_path"],
                    "registered": [r["table"] for r in reg["registered"]],
                }
            except ADPError as e:
                out["explorer"] = {"registered": [], "error": str(e)}
        return out

    # -- quality ---------------------------------------------------------------------
    def quality_check(self, data_dir: str | None = None) -> dict[str, Any]:
        """Run derived checks against generated outputs (default) or a data dir.

        Uses DuckDB streaming against parquet/csv files — no full-table Polars load.
        """
        from ai_data_platform.quality.duckdb_checks import run_quality_checks_on_dir

        cfg = self.config
        target = safe_resolve(self.root, data_dir or cfg.output_dir)
        return run_quality_checks_on_dir(self.catalog, target)

    def load_data(
        self,
        *,
        destination: str | None = None,
        tables: list[str] | None = None,
        data_dir: str | None = None,
        dry_run: bool = False,
        skip_quality: bool = False,
        force_quality: bool = False,
    ) -> dict[str, Any]:
        """Push generated staging files to a configured warehouse via ingestr."""
        from ai_data_platform.load.engine import LoadEngine

        report = LoadEngine(self.root, self.catalog, self.config).load(
            destination=destination,
            tables=tables,
            data_dir=data_dir,
            dry_run=dry_run,
            skip_quality=skip_quality,
            force_quality=force_quality,
        )
        return {
            "destination": report.destination,
            "staging_format": report.staging_format,
            "quality_score": report.quality_score,
            "elapsed_ms": report.elapsed_ms,
            "ok": report.ok,
            "tables": [
                {
                    "table": t.table,
                    "dest_table": t.dest_table,
                    "status": t.status,
                    "elapsed_ms": t.elapsed_ms,
                    "error": t.error,
                }
                for t in report.tables
            ],
        }

    # -- seasonality ----------------------------------------------------------------
    def preview_seasonality(self, table: str) -> dict[str, Any]:
        """Inspect a table's seasonality config and its expected factor curve.

        Read-only — no generation. Returns the anchor, factor config, and a
        downsampled expected daily-intensity curve for charting.
        """
        from ai_data_platform.core.exceptions import ConfigError
        from ai_data_platform.generator.seasonality import (
            _range_dates,
            _to_date,
            build_day_weights,
        )

        profile = self.catalog.get_latest_profile(table) or {}
        anchor: str | None = None
        factor: dict[str, Any] = {}
        for c in profile.get("columns", []):
            if c.get("seasonality"):
                anchor = c["name"]
                factor = c["seasonality"].get("factor", {}) or {}
                break
        if anchor is None:
            raise ConfigError(
                f"Table {table!r} has no seasonality block.",
                hint="Add a `seasonality:` block to the table in your spec.",
            )
        start = _to_date(factor.get("_start", "2024-01-01"))
        end = _to_date(factor.get("_end", "2026-01-01"))
        days = _range_dates(start, end)
        weights = build_day_weights(start, end, factor)
        step = max(1, len(days) // 120)  # downsample to <=120 points
        curve = [
            {"date": days[i].isoformat(), "intensity": round(float(weights[i]), 8)}
            for i in range(0, len(days), step)
        ]
        return {"table": table, "anchor": anchor, "factor": factor, "days": len(days), "curve": curve}

    def seasonality_check(
        self, data_dir: str | None = None, tables: list[str] | None = None
    ) -> dict[str, Any]:
        """Validate generated data against the declared seasonality (volume peaks,
        weekly pattern, trend, expected/observed correlation, cross-table alignment)."""
        from ai_data_platform.quality.seasonality_report import build_seasonality_report

        target = safe_resolve(self.root, data_dir or self.config.output_dir)
        return build_seasonality_report(self.catalog, target, tables=tables)

    # -- semantic / sql / docs ----------------------------------------------------------
    def create_semantic_model(
        self, name: str = "default", fmt: str | None = None
    ) -> dict[str, Any]:
        from ai_data_platform.semantic.builder import build_semantic_model, render_semantic_model

        model = build_semantic_model(self.catalog, name)
        rendered = render_semantic_model(model, fmt or self.config.semantic.format)
        return {"model": model, "rendered": rendered, "format": fmt or self.config.semantic.format}

    def generate_sql(self, question: str) -> dict[str, Any]:
        from ai_data_platform.sql.assistant import SQLAssistant

        return SQLAssistant(self.catalog, self.config.model_provider).generate_sql(question)

    def generate_docs(self) -> str:
        from ai_data_platform.docs.generator import generate_docs

        return generate_docs(self.catalog, self.config.project)

    # -- explorer (MCP Data Explorer) --------------------------------------------------
    def register_datasets(
        self, dataset: str = "default", data_dir: str | None = None, *, replace: bool = True
    ) -> dict[str, Any]:
        return self.explorer.register(dataset, data_dir, replace=replace)

    def list_datasets(self) -> list[dict[str, Any]]:
        return self.explorer.list_datasets()

    def list_explorer_tables(self, dataset: str = "default") -> list[dict[str, Any]]:
        return self.explorer.list_tables(dataset)

    def describe_dataset_table(self, table: str, dataset: str = "default") -> dict[str, Any]:
        return self.explorer.describe_table(table, dataset)

    def show_table_schema(self, table: str, dataset: str = "default") -> dict[str, Any]:
        return self.explorer.show_schema(table, dataset)

    def preview_dataset_table(
        self, table: str, dataset: str = "default", limit: int = 20
    ) -> dict[str, Any]:
        return self.explorer.preview_table(table, dataset, limit)

    def get_table_row_count(self, table: str, dataset: str = "default") -> dict[str, Any]:
        return self.explorer.get_row_count(table, dataset)

    def profile_dataset_table(self, table: str, dataset: str = "default") -> dict[str, Any]:
        return self.explorer.profile_table(table, dataset)

    def execute_explorer_sql(
        self, sql: str, dataset: str = "default", max_rows: int | None = None
    ) -> dict[str, Any]:
        return self.explorer.execute_sql(sql, dataset, max_rows)

    def explain_explorer_sql(self, sql: str, dataset: str = "default") -> dict[str, Any]:
        return self.explorer.explain_sql(sql, dataset)

    def export_explorer_result(
        self, sql: str, filename: str, dataset: str = "default", fmt: str = "csv"
    ) -> dict[str, Any]:
        return self.explorer.export_query_result(sql, filename, dataset, fmt)

    def suggest_analytics_queries(
        self, dataset: str = "default", table: str | None = None, limit: int = 8
    ) -> dict[str, Any]:
        return self.explorer.suggest_analytics_queries(dataset, table, limit)

    def generate_business_insights(self, sql: str, dataset: str = "default") -> dict[str, Any]:
        return self.explorer.generate_business_insights(sql, dataset)

    def validate_business_questions(
        self, questions: list[str], dataset: str = "default"
    ) -> dict[str, Any]:
        return self.explorer.validate_business_questions(questions, dataset)
