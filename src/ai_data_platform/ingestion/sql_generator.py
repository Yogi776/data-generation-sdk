"""SQL & documentation generator.

For an ingested source, produce ready-to-use artifacts: CREATE VIEW / CREATE
TABLE AS statements, profiling SQL, data-quality SQL, sample queries, a JSON
schema export, and a Markdown documentation summary. All identifiers are quoted;
nothing is domain-specific.
"""

from __future__ import annotations

import json
from typing import Any

from ai_data_platform.ingestion.duckdb_reader import quote_ident


def sample_queries(name: str, schema: list[dict[str, Any]]) -> list[dict[str, str]]:
    ident = quote_ident(name)
    cols = [c["name"] for c in schema]
    numeric = [c["name"] for c in schema if _is_numeric(c["type"])]
    categorical = [c["name"] for c in schema if _is_text(c["type"])]
    temporal = [c["name"] for c in schema if _is_temporal(c["type"])]

    out: list[dict[str, str]] = [
        {"title": "Preview rows", "sql": f"SELECT * FROM {ident} LIMIT 20;"},
        {"title": "Row count", "sql": f"SELECT count(*) AS row_count FROM {ident};"},
    ]
    if categorical:
        c = quote_ident(categorical[0])
        out.append(
            {
                "title": f"Distribution of {categorical[0]}",
                "sql": f"SELECT {c}, count(*) AS n FROM {ident} "
                f"GROUP BY 1 ORDER BY n DESC LIMIT 20;",
            }
        )
    if numeric:
        n = quote_ident(numeric[0])
        out.append(
            {
                "title": f"Aggregate {numeric[0]}",
                "sql": f"SELECT min({n}) AS min, max({n}) AS max, "
                f"avg({n}) AS avg, sum({n}) AS total FROM {ident};",
            }
        )
    if numeric and categorical:
        out.append(
            {
                "title": f"{numeric[0]} by {categorical[0]}",
                "sql": f"SELECT {quote_ident(categorical[0])}, "
                f"sum({quote_ident(numeric[0])}) AS total_{numeric[0]} "
                f"FROM {ident} GROUP BY 1 ORDER BY 2 DESC LIMIT 20;",
            }
        )
    if temporal and numeric:
        out.append(
            {
                "title": f"Monthly {numeric[0]}",
                "sql": f"SELECT date_trunc('month', {quote_ident(temporal[0])}) AS month, "
                f"sum({quote_ident(numeric[0])}) AS total_{numeric[0]} "
                f"FROM {ident} GROUP BY 1 ORDER BY 1;",
            }
        )
    _ = cols
    return out


def profiling_sql(name: str) -> str:
    return f"SUMMARIZE SELECT * FROM {quote_ident(name)};"


def quality_sql(name: str, schema: list[dict[str, Any]]) -> list[dict[str, str]]:
    ident = quote_ident(name)
    checks: list[dict[str, str]] = [
        {
            "title": "Duplicate rows",
            "sql": f"SELECT count(*) - count(*) FILTER (WHERE rn = 1) AS duplicate_rows "
            f"FROM (SELECT row_number() OVER (PARTITION BY *) AS rn FROM {ident});",
        }
    ]
    null_terms = ", ".join(
        f"count(*) - count({quote_ident(c['name'])}) AS {quote_ident('nulls_' + c['name'])}"
        for c in schema
    )
    if null_terms:
        checks.append({"title": "Null counts per column", "sql": f"SELECT {null_terms} FROM {ident};"})
    return checks


def create_statements(view_ddl: str, name: str, scan_expr: str | None) -> dict[str, str]:
    ident = quote_ident(name)
    ctas = (
        f"CREATE TABLE {ident} AS SELECT * FROM {scan_expr};"
        if scan_expr
        else f"CREATE TABLE {ident} AS SELECT * FROM <loaded source>;"
    )
    create_view = (
        f"CREATE VIEW {ident} AS SELECT * FROM {scan_expr};"
        if scan_expr
        else f"-- {name}: loaded format; materialized as a table (no file-native view)."
    )
    return {"create_view": create_view, "create_table_as": ctas, "applied_ddl": view_ddl}


def schema_export_json(name: str, schema: list[dict[str, Any]]) -> str:
    return json.dumps(
        {"table": name, "columns": schema, "column_count": len(schema)},
        indent=2,
        default=str,
    )


def documentation(name: str, detected_format: str, report: dict[str, Any]) -> str:
    prof = report.get("profile", {})
    schema = report.get("schema", [])
    lines = [
        f"# Data dictionary — {name}",
        "",
        f"- **Source**: `{report.get('source_path')}`",
        f"- **Format**: {detected_format}",
        f"- **Rows**: {prof.get('row_count'):,}" if prof.get("row_count") is not None else "- **Rows**: n/a",
        f"- **Columns**: {prof.get('column_count')}",
    ]
    dup = prof.get("duplicate_rows")
    if dup is not None:
        lines.append(f"- **Duplicate rows**: {dup}")
    lines += ["", "## Columns", "", "| column | type | null % | distinct | min | max |", "|---|---|---|---|---|---|"]
    colstats = prof.get("columns", {})
    for col in schema:
        s = colstats.get(col["name"], {})
        lines.append(
            f"| {col['name']} | {col['type']} | "
            f"{s.get('null_percentage', 0)} | {s.get('distinct', '')} | "
            f"{s.get('min', '')} | {s.get('max', '')} |"
        )
    warns = report.get("quality_warnings", [])
    if warns:
        lines += ["", "## Quality warnings", ""]
        lines += [f"- **[{w['severity']}]** {w.get('column') or 'table'}: {w['message']}" for w in warns]
    return "\n".join(lines) + "\n"


def _is_numeric(t: str) -> bool:
    t = t.upper()
    return any(k in t for k in ("INT", "DECIMAL", "DOUBLE", "FLOAT", "REAL", "HUGEINT", "NUMERIC"))


def _is_text(t: str) -> bool:
    t = t.upper()
    return any(k in t for k in ("VARCHAR", "TEXT", "STRING", "CHAR")) and "BOOLEAN" not in t


def _is_temporal(t: str) -> bool:
    t = t.upper()
    return any(k in t for k in ("DATE", "TIME", "TIMESTAMP"))
