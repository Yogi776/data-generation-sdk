"""Local REST API — a thin layer over ADPClient (same backend as CLI/MCP).

Binds to localhost by default; this is a single-user local console, not a
multi-tenant service (that's the platform's job).
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from fastapi import FastAPI, HTTPException
from fastapi.responses import HTMLResponse
from pydantic import BaseModel, Field

from ai_data_platform.__about__ import __version__
from ai_data_platform.core.exceptions import ADPError
from ai_data_platform.sdk import ADPClient

UI_HTML = Path(__file__).parent.parent / "ui" / "static" / "index.html"


class GenerateRequest(BaseModel):
    rows: int | None = Field(default=None, ge=1, le=10_000_000)
    tables: list[str] | None = None
    seed: int | None = None
    output_format: str | None = None


class SQLRequest(BaseModel):
    question: str


class SemanticRequest(BaseModel):
    name: str = "default"
    format: str | None = None


class ProfileRequest(BaseModel):
    source: str | None = None
    sample_rows: int = Field(default=10_000, ge=100, le=1_000_000)


class ExplorerRegisterRequest(BaseModel):
    dataset: str = "default"
    data_dir: str | None = None
    replace: bool = True


class ExplorerSqlRequest(BaseModel):
    sql: str
    dataset: str = "default"
    max_rows: int | None = Field(default=None, ge=1, le=1_000_000)


class ExplorerSuggestRequest(BaseModel):
    dataset: str = "default"
    table: str | None = None
    limit: int = Field(default=8, ge=1, le=25)


class ExplorerValidateRequest(BaseModel):
    questions: list[str]
    dataset: str = "default"


class ExplorerExportRequest(BaseModel):
    sql: str
    filename: str
    dataset: str = "default"
    format: str = "csv"


def create_app(project_path: str = ".") -> FastAPI:
    app = FastAPI(
        title="ai-data-platform",
        version=__version__,
        description="Local AI data platform API. Single-user; do not expose publicly.",
    )
    client = ADPClient(project_path)

    def _run(fn: Any, *args: Any, **kwargs: Any) -> Any:
        try:
            return fn(*args, **kwargs)
        except ADPError as e:
            raise HTTPException(status_code=400, detail=str(e)) from e

    @app.get("/health")
    def health() -> dict[str, str]:
        return {"status": "ok", "version": __version__}

    @app.get("/sources")
    def sources() -> list[dict[str, Any]]:
        return _run(client.catalog.list_sources)

    @app.get("/metadata/tables")
    def tables() -> list[dict[str, Any]]:
        return _run(client.list_tables)

    @app.get("/metadata/tables/{table}")
    def table_detail(table: str) -> dict[str, Any]:
        return _run(client.get_table, table)

    @app.get("/metadata/search")
    def search(q: str, limit: int = 20) -> list[dict[str, Any]]:
        return _run(client.search_metadata, q, limit)

    @app.post("/scan")
    def scan() -> list[dict[str, Any]]:
        return _run(client.scan)

    @app.post("/profile/run")
    def profile(req: ProfileRequest) -> list[dict[str, Any]]:
        return _run(client.profile, req.source, sample_rows=req.sample_rows)

    @app.post("/generate-data")
    def generate(req: GenerateRequest) -> dict[str, Any]:
        return _run(
            client.generate_data,
            req.rows,
            tables=req.tables,
            seed=req.seed,
            output_format=req.output_format,
        )

    @app.post("/semantic-model")
    def semantic(req: SemanticRequest) -> dict[str, Any]:
        return _run(client.create_semantic_model, req.name, req.format)

    @app.post("/quality-check")
    def quality() -> dict[str, Any]:
        return _run(client.quality_check)

    @app.post("/sql")
    def sql(req: SQLRequest) -> dict[str, Any]:
        return _run(client.generate_sql, req.question)

    @app.post("/docs/generate")
    def docs() -> dict[str, str]:
        return {"markdown": _run(client.generate_docs)}

    # -- MCP Data Explorer (DuckDB) --------------------------------------------
    @app.post("/explorer/register")
    def explorer_register(req: ExplorerRegisterRequest) -> dict[str, Any]:
        return _run(client.register_datasets, req.dataset, req.data_dir, replace=req.replace)

    @app.get("/explorer/datasets")
    def explorer_datasets() -> list[dict[str, Any]]:
        return _run(client.list_datasets)

    @app.get("/explorer/datasets/{dataset}/tables")
    def explorer_tables(dataset: str = "default") -> list[dict[str, Any]]:
        return _run(client.list_explorer_tables, dataset)

    @app.get("/explorer/datasets/{dataset}/tables/{table}")
    def explorer_describe(table: str, dataset: str = "default") -> dict[str, Any]:
        return _run(client.describe_dataset_table, table, dataset)

    @app.get("/explorer/datasets/{dataset}/tables/{table}/schema")
    def explorer_schema(table: str, dataset: str = "default") -> dict[str, Any]:
        return _run(client.show_table_schema, table, dataset)

    @app.get("/explorer/datasets/{dataset}/tables/{table}/preview")
    def explorer_preview(table: str, dataset: str = "default", limit: int = 20) -> dict[str, Any]:
        return _run(client.preview_dataset_table, table, dataset, limit)

    @app.get("/explorer/datasets/{dataset}/tables/{table}/profile")
    def explorer_profile(table: str, dataset: str = "default") -> dict[str, Any]:
        return _run(client.profile_dataset_table, table, dataset)

    @app.post("/explorer/sql")
    def explorer_sql(req: ExplorerSqlRequest) -> dict[str, Any]:
        return _run(client.execute_explorer_sql, req.sql, req.dataset, req.max_rows)

    @app.post("/explorer/explain")
    def explorer_explain(req: ExplorerSqlRequest) -> dict[str, Any]:
        return _run(client.explain_explorer_sql, req.sql, req.dataset)

    @app.post("/explorer/suggest")
    def explorer_suggest(req: ExplorerSuggestRequest) -> dict[str, Any]:
        return _run(client.suggest_analytics_queries, req.dataset, req.table, req.limit)

    @app.post("/explorer/insights")
    def explorer_insights(req: ExplorerSqlRequest) -> dict[str, Any]:
        return _run(client.generate_business_insights, req.sql, req.dataset)

    @app.post("/explorer/validate")
    def explorer_validate(req: ExplorerValidateRequest) -> dict[str, Any]:
        return _run(client.validate_business_questions, req.questions, req.dataset)

    @app.post("/explorer/export")
    def explorer_export(req: ExplorerExportRequest) -> dict[str, Any]:
        return _run(client.export_explorer_result, req.sql, req.filename, req.dataset, req.format)

    @app.get("/", response_class=HTMLResponse)
    def index() -> str:
        if UI_HTML.exists():
            return UI_HTML.read_text(encoding="utf-8")
        return "<h1>ai-data-platform</h1><p>UI asset missing; API is live at /docs</p>"

    return app
