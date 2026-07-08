"""ExplorerService: the single backend for the MCP Data Explorer.

The SDK, MCP tools, REST API, and CLI all call these methods — none of them
reimplement registration, querying, or insight logic. Construct via
``ExplorerService.from_project(...)`` so config, metastore, and provider wiring
stay in one place.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from ai_data_platform.config import ExplorerConfig, ModelProviderConfig
from ai_data_platform.explorer.engine import DuckDBExplorer
from ai_data_platform.explorer.insights import InsightAgent
from ai_data_platform.explorer.metastore import ExplorerMetastore
from ai_data_platform.explorer.registrar import DatasetRegistrar


class ExplorerService:
    def __init__(
        self,
        root: str | Path,
        cfg: ExplorerConfig,
        *,
        default_data_dir: str = "output",
        export_dir: str = "exports",
        provider_cfg: ModelProviderConfig | None = None,
    ) -> None:
        self.root = Path(root).expanduser().resolve()
        self.cfg = cfg
        self.default_data_dir = default_data_dir
        self.export_dir = export_dir
        self.metastore = ExplorerMetastore(self.root, metadata_dsn=cfg.resolved_metadata_dsn())
        self.registrar = DatasetRegistrar(self.root, self.metastore)
        self.engine = DuckDBExplorer(self.root, cfg, self.metastore)
        self.insights = InsightAgent(self.metastore, self.engine, provider_cfg)

    # -- registration --------------------------------------------------------
    def register(
        self, dataset: str = "default", data_dir: str | None = None, *, replace: bool = True
    ) -> dict[str, Any]:
        return self.registrar.register_dir(
            data_dir or self.default_data_dir,
            dataset=dataset,
            db_filename=self.cfg.db_filename,
            replace=replace,
        )

    # -- metadata ------------------------------------------------------------
    def list_datasets(self) -> list[dict[str, Any]]:
        return self.metastore.list_datasets()

    def list_tables(self, dataset: str = "default") -> list[dict[str, Any]]:
        return self.metastore.list_tables(dataset)

    def describe_table(self, table: str, dataset: str = "default") -> dict[str, Any]:
        return self.engine.describe_table(dataset, table)

    def show_schema(self, table: str, dataset: str = "default") -> dict[str, Any]:
        return self.engine.show_schema(dataset, table)

    def preview_table(
        self, table: str, dataset: str = "default", limit: int = 20
    ) -> dict[str, Any]:
        return self.engine.preview_table(dataset, table, limit)

    def get_row_count(self, table: str, dataset: str = "default") -> dict[str, Any]:
        return self.engine.get_row_count(dataset, table)

    def profile_table(self, table: str, dataset: str = "default") -> dict[str, Any]:
        return self.engine.profile_table(dataset, table)

    # -- sql -----------------------------------------------------------------
    def execute_sql(
        self, sql: str, dataset: str = "default", max_rows: int | None = None
    ) -> dict[str, Any]:
        return self.engine.execute_sql(dataset, sql, max_rows=max_rows)

    def explain_sql(self, sql: str, dataset: str = "default") -> dict[str, Any]:
        return self.engine.explain_sql(dataset, sql)

    def export_query_result(
        self,
        sql: str,
        filename: str,
        dataset: str = "default",
        fmt: str = "csv",
    ) -> dict[str, Any]:
        return self.engine.export_query_result(
            dataset, sql, fmt=fmt, filename=filename, export_dir=self.export_dir
        )

    # -- insights ------------------------------------------------------------
    def suggest_analytics_queries(
        self, dataset: str = "default", table: str | None = None, limit: int = 8
    ) -> dict[str, Any]:
        return self.insights.suggest_analytics_queries(dataset, table, limit)

    def generate_business_insights(self, sql: str, dataset: str = "default") -> dict[str, Any]:
        return self.insights.generate_business_insights(dataset, sql)

    def validate_business_questions(
        self, questions: list[str], dataset: str = "default"
    ) -> dict[str, Any]:
        return self.insights.validate_business_questions(dataset, questions)
