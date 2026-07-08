"""MCP server: thin adapter over ADPClient (same backend as CLI/API/UI).

Canonical local tool registry (subset of the platform registry, docs/03):
apply_spec, scan_sources, profile_source, search_metadata, get_table_schema,
generate_synthetic_data, preview_data, run_quality_check, create_semantic_model,
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
    client = ADPClient(project_path)
    mcp = FastMCP(
        "ai-data-platform",
        instructions=(
            "Local AI data platform. Two entry paths: "
            "(A) no data: apply_spec with a dataset spec YAML, then "
            "generate_synthetic_data; "
            "(B) sample data configured in adp.yaml: scan_sources -> profile_source "
            "-> generate_synthetic_data. "
            "Always finish with run_quality_check; inspect rows with preview_data. "
            "Generation is deterministic per seed."
        ),
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
    @mcp.prompt()
    def research_and_generate(domain: str = "your domain") -> str:
        """Research real-world distributions on the web, then generate
        production-grade data grounded in the findings."""
        return (
            f"Create a production-realistic synthetic {domain} dataset using this "
            "research-driven workflow:\n"
            f"1. RESEARCH (use your web search): find real-world facts about {domain} — "
            "the standard entities and their relationships; actual category "
            "distributions with percentages (market shares, status mixes, "
            "demographic splits); realistic numeric ranges (prices, quantities, "
            "durations); common ID/code formats. Cite each source.\n"
            "2. REASON: summarize the findings as research notes — every "
            "distribution you'll encode, with its source.\n"
            "3. DRAFT: call propose_spec with the description AND your research "
            "notes (or write the spec YAML yourself). Review the returned YAML: "
            "check weights match your research, add joins with correct "
            "cardinalities and dependencies (after/expr/null_unless/values_by).\n"
            "4. GENERATE: apply_spec, then generate_synthetic_data (ask me for "
            "row count and seed).\n"
            "5. VALIDATE: run_quality_check and preview_data; verify the generated "
            "distributions against your researched numbers and report the "
            "comparison with citations."
        )

    @mcp.prompt()
    def new_dataset_wizard(domain: str = "your domain") -> str:
        """Guided flow: design a spec, generate, validate — no seed data needed."""
        return (
            f"Help me create a synthetic {domain} dataset with this workflow:\n"
            "1. Ask me for the tables and key columns I need (or propose typical "
            f"ones for {domain}).\n"
            "2. Draft a dataset spec YAML: types, PKs, weighted `values`, "
            "`format` templates for IDs, joins with cardinalities, and "
            "dependencies (`after` for temporal order, `expr` for arithmetic, "
            "`null_unless` for conditionals, `values_by` for hierarchies).\n"
            "3. Call apply_spec with the YAML, then generate_synthetic_data "
            "(ask me for row count).\n"
            "4. Call run_quality_check and preview_data, and summarize the results."
        )

    return mcp


def run_server(project_path: str = ".") -> None:
    create_server(project_path).run()
