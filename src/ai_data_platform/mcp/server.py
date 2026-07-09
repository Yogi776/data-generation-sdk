"""MCP server: thin adapter over ADPClient (same backend as CLI/API/UI).

Canonical local tool registry (subset of the platform registry, docs/03):
apply_spec, scan_sources, profile_source, search_metadata, get_table_schema,
generate_synthetic_data, preview_data, run_quality_check, preview_seasonality,
run_seasonality_check, plan_execution, analyze_complexity, create_semantic_model,
generate_sql, generate_docs.

Parity rule: every capability of the CLI is reachable here. All tools are
read-only against user sources; generation/spec/docs write only inside the
project directory. Errors are structured and actionable — never stack traces
(all handlers are wrapped; unexpected exceptions become structured errors too).
"""

from __future__ import annotations

import functools
import json
from collections.abc import Callable
from typing import Any

from mcp.server.fastmcp import FastMCP

from ai_data_platform.core.exceptions import ADPError
from ai_data_platform.sdk import ADPClient

PREVIEW_MAX_ROWS = 50
GENERATE_MAX_ROWS = 1_000_000


def _ok(payload: Any) -> str:
    return json.dumps({"ok": True, "result": payload}, default=str)


def _err(e: Exception) -> str:
    return json.dumps({"ok": False, "error": str(e)})


def _safe(fn: Callable[..., str]) -> Callable[..., str]:
    """Every tool returns structured JSON — expected errors carry hints,
    unexpected ones are wrapped, never raised as stack traces."""

    @functools.wraps(fn)
    def wrapper(*args: Any, **kwargs: Any) -> str:
        try:
            return fn(*args, **kwargs)
        except ADPError as e:
            return _err(e)
        except Exception as e:  # noqa: BLE001 - MCP boundary must not leak traces
            return _err(RuntimeError(f"unexpected error ({type(e).__name__}): {e}"))

    return wrapper


def create_server(project_path: str = ".") -> FastMCP:
    from ai_data_platform.agent.workflow import mcp_server_instructions

    client = ADPClient(project_path)
    mcp = FastMCP(
        "ai-data-platform",
        instructions=mcp_server_instructions(),
    )

    # -- design-time -----------------------------------------------------------
    @mcp.tool()
    @_safe
    def propose_spec(description: str, research_notes: str = "") -> str:
        """AI-draft a dataset spec from a plain-language description. Uses the
        project's configured LLM provider; output is schema-validated before
        return (never applied automatically). For maximum realism, first use
        YOUR web search to research the domain — real entity lists, category
        distributions (e.g. actual payment-method market shares), typical value
        ranges — and pass findings as research_notes. Review the returned YAML,
        adjust, then call apply_spec."""
        return _ok(client.propose_spec(description, research_notes))

    @mcp.tool()
    @_safe
    def apply_spec(spec_yaml: str) -> str:
        """Register a declarative dataset spec and generate WITHOUT seed data.
        Pass the full spec YAML content: tables, columns (types, values weights,
        mean/std/min/max, format templates, null_ratio), joins (one_to_many /
        many_to_one / one_to_one), and dependencies (expr, after, null_unless,
        values_by). Side effect: writes spec.yaml into the project and registers
        tables in the catalog. Follow with generate_synthetic_data."""
        from ai_data_platform.core.paths import safe_write_text

        safe_write_text(client.root, "spec.yaml", spec_yaml)
        return _ok(client.apply_spec("spec.yaml"))

    @mcp.tool()
    @_safe
    def scan_sources(source: str | None = None) -> str:
        """Scan configured data sources into the metadata catalog
        (discovers tables, columns, relationship candidates). Use when adp.yaml
        has sources; for spec-based projects use apply_spec instead."""
        return _ok(client.scan(source))

    @mcp.tool()
    @_safe
    def profile_source(source: str | None = None, sample_rows: int = 10000) -> str:
        """Profile tables: statistics, distributions, PII detection, PK/FK
        confirmation. Improves generation realism; run after scan_sources."""
        return _ok(client.profile(source, sample_rows=min(sample_rows, 100_000)))

    # -- discovery ---------------------------------------------------------------
    @mcp.tool()
    @_safe
    def search_metadata(query: str, limit: int = 20) -> str:
        """Search cataloged tables and columns by name/description.
        Use this first to discover what data exists."""
        return _ok(client.search_metadata(query, min(limit, 50)))

    @mcp.tool()
    @_safe
    def get_table_schema(table: str) -> str:
        """Get a table's columns, types, primary key, PII flags, and description."""
        return _ok(client.get_table(table))

    # -- generation ---------------------------------------------------------------
    @mcp.tool()
    @_safe
    def generate_synthetic_data(
        rows: int = 1000,
        tables: list[str] | None = None,
        seed: int | None = None,
        rows_per_table: dict[str, int] | None = None,
        output_format: str = "parquet",
    ) -> str:
        """Generate FK-safe synthetic data from the catalog into the project's
        output directory. Deterministic per seed. Side effect: writes files.
        `rows` is the default count; `rows_per_table` overrides per table
        (e.g. {"products": 20, "customers": 1000, "transactions": 100000}) —
        parents with few rows are reused across many child rows automatically.
        Max 1,000,000 rows per table per call via MCP."""
        counts = list((rows_per_table or {}).values()) + [rows]
        if max(counts) > GENERATE_MAX_ROWS:
            return _err(
                ADPError(
                    f"a table exceeds the MCP per-call limit of {GENERATE_MAX_ROWS:,} rows.",
                    hint="Use the CLI for larger volumes: adp generate-data --rows-per-table ...",
                )
            )
        return _ok(
            client.generate_data(
                rows,
                tables=tables,
                seed=seed,
                rows_per_table=rows_per_table,
                output_format=output_format,
            )
        )

    @mcp.tool()
    @_safe
    def preview_data(table: str, limit: int = 10) -> str:
        """Preview generated rows for a table (max 50 rows, token-budgeted).
        Use after generate_synthetic_data to inspect the output."""
        import polars as pl

        from ai_data_platform.core.paths import safe_resolve

        out = safe_resolve(client.root, client.config.output_dir)
        n = max(1, min(limit, PREVIEW_MAX_ROWS))
        for suffix, reader in ((".parquet", pl.read_parquet), (".csv", pl.read_csv)):
            path = out / f"{table}{suffix}"
            if path.exists():
                df = reader(path).head(n)
                return _ok({"table": table, "rows": df.to_dicts(), "showing": len(df)})
        return _err(
            ADPError(
                f"No generated output found for table {table!r} in {out}.",
                hint="Run generate_synthetic_data first (parquet or csv format).",
            )
        )

    # -- quality / artifacts ---------------------------------------------------------
    @mcp.tool()
    @_safe
    def run_quality_check() -> str:
        """Run auto-derived quality checks (integrity, completeness, validity,
        consistency) against generated data; returns the quality score and
        failing checks with evidence."""
        report = client.quality_check()
        slim = {
            "quality_score": report["quality_score"],
            "category_scores": report["category_scores"],
            "failing_checks": [
                {
                    "table": t["table"],
                    "rule": c["rule_type"],
                    "column": c["params"].get("column"),
                    "evidence": c["evidence"],
                }
                for t in report["tables"]
                for c in t["checks"]
                if not c["passed"]
            ][:50],
        }
        return _ok(slim)

    @mcp.tool()
    @_safe
    def plan_execution(
        rows: int | None = None,
        tables: list[str] | None = None,
        memory_budget_mb: float | None = None,
    ) -> str:
        """Size a generation run BEFORE running it: recommended batch size,
        parallelism, output format, partition-by column, memory estimate, runtime
        class, and optimization warnings. Read-only, no generation."""
        return _ok(client.plan_execution(rows=rows, tables=tables, memory_budget_mb=memory_budget_mb))

    @mcp.tool()
    @_safe
    def analyze_complexity(rows: int | None = None, tables: list[str] | None = None) -> str:
        """Static complexity analysis of the plan: a module time/space table,
        per-table/-column cost classes, and hot-spot warnings (GIL-bound string
        samplers, O(rows) scatter). Read-only, no generation."""
        return _ok(client.analyze_complexity(rows=rows, tables=tables))

    @mcp.tool()
    @_safe
    def preview_seasonality(table: str) -> str:
        """Inspect a table's seasonality config and its expected factor curve
        (trend, weekly, yearly peaks, holidays, events). Read-only, no generation.
        Use before generating to sanity-check the declared temporal shape."""
        return _ok(client.preview_seasonality(table))

    @mcp.tool()
    @_safe
    def run_seasonality_check(
        data_dir: str | None = None, tables: list[str] | None = None
    ) -> str:
        """Validate that generated data follows the declared seasonality: weekly
        pattern, event/holiday spikes, growth trend, expected-vs-observed
        correlation, and cross-table peak alignment (parents and children peak on
        the same days). Returns the score plus failing metrics with evidence."""
        report = client.seasonality_check(data_dir, tables)
        slim = {
            "seasonality_score": report["seasonality_score"],
            "category_scores": report["category_scores"],
            "failing_metrics": [
                {"table": t["table"], "metric": c["metric"], "evidence": c["evidence"]}
                for t in report["tables"]
                for c in t["checks"]
                if not c["passed"]
            ][:50],
            "cross_table": [
                {"child": x["child"], "parent": x["parent"], "passed": x["passed"],
                 "evidence": x["evidence"]}
                for x in report["cross_table"]
            ][:50],
        }
        return _ok(slim)

    @mcp.tool()
    @_safe
    def create_semantic_model(name: str = "default", format: str = "generic") -> str:
        """Build a semantic model (facts, dimensions, measures, joins) from the
        catalog and return it as YAML. Formats: generic, cube (Cube.js)."""
        result = client.create_semantic_model(name, format)
        return _ok({"format": result["format"], "yaml": result["rendered"]})

    @mcp.tool()
    @_safe
    def generate_sql(question: str) -> str:
        """Generate a read-only SQL SELECT (DuckDB dialect) from a natural-language
        question, grounded in the catalog. Requires a configured LLM provider."""
        return _ok(client.generate_sql(question))

    @mcp.tool()
    @_safe
    def generate_docs() -> str:
        """Generate a Markdown data dictionary for the whole catalog."""
        return _ok({"markdown": client.generate_docs()})

    # -- MCP Data Explorer (DuckDB) --------------------------------------------
    # Generated files are auto-registered into DuckDB after
    # generate_synthetic_data. These tools explore them with governed, read-only
    # SQL. All are read-only; export writes only inside the project export dir.

    @mcp.tool()
    @_safe
    def register_datasets(dataset: str = "default", data_dir: str | None = None) -> str:
        """Register generated files (parquet/csv/json) in a directory into DuckDB
        as views for exploration. Usually automatic after generation; call this to
        (re)register manually or to register a specific data_dir under a named
        dataset."""
        return _ok(client.register_datasets(dataset, data_dir))

    @mcp.tool()
    @_safe
    def list_datasets() -> str:
        """List registered datasets with table counts, total rows, and DB path.
        Start here to discover what data is available to query."""
        return _ok(client.list_datasets())

    @mcp.tool()
    @_safe
    def list_tables(dataset: str = "default") -> str:
        """List tables in a dataset with format, row count, column count, and
        partition info."""
        return _ok(client.list_explorer_tables(dataset))

    @mcp.tool()
    @_safe
    def describe_table(table: str, dataset: str = "default") -> str:
        """Full description of a registered table: source file, format, row count,
        columns (name/type/nullable), and partition keys."""
        return _ok(client.describe_dataset_table(table, dataset))

    @mcp.tool()
    @_safe
    def show_schema(table: str, dataset: str = "default") -> str:
        """Show a table's column schema as CREATE-VIEW-style DDL plus a structured
        column list."""
        return _ok(client.show_table_schema(table, dataset))

    @mcp.tool()
    @_safe
    def preview_table(table: str, dataset: str = "default", limit: int = 20) -> str:
        """Preview the first N rows of a table (max 200)."""
        return _ok(client.preview_dataset_table(table, dataset, min(limit, 200)))

    @mcp.tool()
    @_safe
    def get_row_count(table: str, dataset: str = "default") -> str:
        """Exact row count for a registered table."""
        return _ok(client.get_table_row_count(table, dataset))

    @mcp.tool()
    @_safe
    def profile_table(table: str, dataset: str = "default") -> str:
        """Per-column profile: null counts/fractions, distinct counts, min/max/avg/
        stddev for numerics, date ranges, and top values for low-cardinality
        columns. Large tables are sampled (flagged sampled=true)."""
        return _ok(client.profile_dataset_table(table, dataset))

    @mcp.tool()
    @_safe
    def execute_sql(sql: str, dataset: str = "default", max_rows: int | None = None) -> str:
        """Run a single read-only SELECT/WITH query (DuckDB dialect) against the
        dataset. Enforced: SELECT-only guard, read-only connection, row limit
        (result flagged truncated/sampled), scan-size guard, and query timeout.
        Query the registered table names directly — raw file readers are blocked."""
        return _ok(client.execute_explorer_sql(sql, dataset, max_rows))

    @mcp.tool()
    @_safe
    def explain_sql(sql: str, dataset: str = "default") -> str:
        """Return the DuckDB query plan and an estimated row count for a SELECT —
        inspect cost before running."""
        return _ok(client.explain_explorer_sql(sql, dataset))

    @mcp.tool()
    @_safe
    def suggest_analytics_queries(
        dataset: str = "default", table: str | None = None, limit: int = 8
    ) -> str:
        """Suggest useful analytical SQL (trends, rankings, distributions, joins)
        derived from the schema and — if an LLM provider is configured — enriched
        with model-generated ideas. Ready to run via execute_sql."""
        return _ok(client.suggest_analytics_queries(dataset, table, min(limit, 25)))

    @mcp.tool()
    @_safe
    def generate_business_insights(sql: str, dataset: str = "default") -> str:
        """Execute a SELECT and summarize it: key findings, anomalies, trends,
        data-quality notes, dashboard-ready metrics, and recommended follow-up
        queries. Narrative is LLM-enhanced when a provider is configured, else
        deterministic."""
        return _ok(client.generate_business_insights(sql, dataset))

    @mcp.tool()
    @_safe
    def validate_business_questions(questions: list[str], dataset: str = "default") -> str:
        """Given business questions in plain language, judge which are answerable
        from the registered tables/columns and suggest a starting SQL for each."""
        return _ok(client.validate_business_questions(questions, dataset))

    @mcp.tool()
    @_safe
    def export_query_result(
        sql: str, filename: str, dataset: str = "default", format: str = "csv"
    ) -> str:
        """Run a SELECT and write the full result to a file (csv/parquet/json)
        inside the project's export directory. The destination is sandboxed — only
        a filename is accepted, never an arbitrary path."""
        return _ok(client.export_explorer_result(sql, filename, dataset, format))

    # -- Universal ingestion (DuckDB) ------------------------------------------
    # Read ANY common file/format on demand — local, folder, URL, or cloud — and
    # make it queryable. Independent of the generation catalog; ingested tables
    # live in .adp/ingestion.duckdb.

    def _ingestion():  # lazy: keeps `adp --help`/import light
        from ai_data_platform.ingestion.engine import IngestionEngine

        return IngestionEngine(project_path)

    @mcp.tool()
    @_safe
    def ingest_data(
        source_path: str,
        table_name: str | None = None,
        persist: bool = False,
        sample_size: int = 10000,
        options: dict[str, Any] | None = None,
    ) -> str:
        """Detect, read, profile, and register ANY supported data source into
        DuckDB, returning schema, row/column counts, per-column stats, quality
        warnings, sample rows, and ready-to-run SQL. Supports csv/tsv, json/ndjson,
        parquet (incl. folders/partitions/globs), excel (options={'sheet': …}),
        arrow, orc, avro, sqlite, and — with optional extensions — delta/iceberg
        and s3/gs/az/http paths. `persist=true` materializes a table; otherwise a
        lazy view is created for native formats. `options` may set format,
        delimiter, has_header, encoding, sheet, flatten (JSON), sqlite_table."""
        report = _ingestion().ingest(source_path, table_name, persist, sample_size, options)
        # Trim sample rows for token budget; full report persisted to disk.
        report = {**report, "sample_rows": report["sample_rows"][:10]}
        return _ok(report)

    @mcp.tool()
    @_safe
    def query_data(sql: str, max_rows: int | None = None) -> str:
        """Run a single read-only SELECT/WITH over previously ingested tables/views
        (DuckDB dialect). Row-capped and SELECT-guarded."""
        return _ok(_ingestion().query(sql, max_rows))

    @mcp.tool()
    @_safe
    def list_ingested_sources() -> str:
        """List sources ingested into the DuckDB ingestion database, with format,
        relation kind, row/column counts, and timestamps."""
        return _ok(_ingestion().list_sources())

    @mcp.tool()
    @_safe
    def describe_ingested_source(table: str) -> str:
        """Return the full stored metadata report for an ingested source (schema,
        profile, quality warnings, generated SQL, documentation)."""
        return _ok(_ingestion().describe(table))

    @mcp.tool()
    @_safe
    def preview_ingested(table: str, limit: int = 20) -> str:
        """Preview rows of an ingested table (max 200)."""
        return _ok(_ingestion().preview(table, min(limit, 200)))

    # -- resources -----------------------------------------------------------
    @mcp.resource("catalog://tables")
    def catalog_tables() -> str:
        """All cataloged tables (JSON)."""
        return json.dumps(client.list_tables(), default=str)

    @mcp.resource("catalog://relationships")
    def catalog_relationships() -> str:
        """All inferred/confirmed relationships (JSON)."""
        return json.dumps(client.catalog.get_relationships(), default=str)

    # -- prompts ---------------------------------------------------------------
    from ai_data_platform.agent.workflow import (
        agent_orchestrator_prompt,
        calibrate_dataset_prompt,
        intake_wizard_prompt,
        new_dataset_wizard_prompt,
        research_and_generate_prompt,
    )

    @mcp.prompt()
    def agent_orchestrator() -> str:
        """Route to flow A/B/C/D/E before calling tools — read this first."""
        return agent_orchestrator_prompt()

    @mcp.prompt()
    def intake_wizard(domain: str = "your domain") -> str:
        """Structured Phase 0–1 questions before any MCP tools."""
        return intake_wizard_prompt(domain)

    @mcp.prompt()
    def research_and_generate(domain: str = "your domain") -> str:
        """Research real-world distributions, then generate production-grade data."""
        return research_and_generate_prompt(domain)

    @mcp.prompt()
    def calibrate_dataset() -> str:
        """Post-generation KPI compare and spec weight patch loop."""
        return calibrate_dataset_prompt()

    @mcp.prompt()
    def new_dataset_wizard(domain: str = "your domain") -> str:
        """Guided flow: design a spec, generate, validate — no seed data needed."""
        return new_dataset_wizard_prompt(domain)

    return mcp


def run_server(project_path: str = ".") -> None:
    create_server(project_path).run()
