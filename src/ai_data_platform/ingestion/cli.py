"""CLI command implementations for ingestion.

Kept separate from the main Typer app so the commands can be registered onto
`adp` (`adp ingest`, `adp query`, `adp list-sources`) while the logic stays in
the ingestion package. Heavy imports happen inside the functions.
"""

from __future__ import annotations

import json
from typing import Any

from rich.console import Console
from rich.table import Table

console = Console()
err_console = Console(stderr=True)


def _engine(project: str) -> Any:
    from ai_data_platform.ingestion.engine import IngestionEngine

    return IngestionEngine(project)


def ingest_command(
    source_path: str,
    table: str | None,
    persist: bool,
    profile: bool,
    sheet: str | None,
    fmt: str | None,
    flatten: bool,
    sample_size: int,
    project: str,
) -> None:
    options: dict[str, Any] = {}
    if sheet is not None:
        options["sheet"] = int(sheet) if sheet.isdigit() else sheet
    if fmt:
        options["format"] = fmt
    if flatten:
        options["flatten"] = True
    report = _engine(project).ingest(
        source_path, table, persist, sample_size, options
    )

    console.print(
        f"[green]Ingested[/green] [bold]{report['table_name']}[/bold] "
        f"({report['detected_format']}, {report['relation_kind']}) — "
        f"{report['row_count']:,} rows × {report['column_count']} cols "
        f"in {report['elapsed_ms']:.0f} ms"
    )
    if report["quality_warnings"]:
        console.print(f"[yellow]{len(report['quality_warnings'])} quality warning(s):[/yellow]")
        for w in report["quality_warnings"][:10]:
            console.print(f"  [{w['severity']}] {w.get('column') or 'table'}: {w['message']}")

    if profile:
        t = Table("column", "type", "null %", "distinct", "min", "max")
        cols = report["profile"]["columns"]
        for c in report["schema"]:
            s = cols.get(c["name"], {})
            t.add_row(
                c["name"], c["type"], str(s.get("null_percentage", "")),
                str(s.get("distinct", "")), str(s.get("min", "")), str(s.get("max", "")),
            )
        console.print(t)
    console.print("[dim]Sample queries:[/dim]")
    for q in report["sql_examples"][:4]:
        console.print(f"  • {q['title']}: [cyan]{q['sql']}[/cyan]")


def query_command(sql: str, max_rows: int | None, project: str, as_json: bool) -> None:
    res = _engine(project).query(sql, max_rows)
    if as_json:
        console.print_json(json.dumps(res, default=str))
        return
    if not res["rows"]:
        console.print("[dim](no rows)[/dim]")
        return
    t = Table(*res["columns"])
    for row in res["rows"]:
        t.add_row(*[str(row.get(c)) for c in res["columns"]])
    console.print(t)
    note = " (truncated)" if res["truncated"] else ""
    console.print(f"[dim]{res['row_count']} row(s) in {res['elapsed_ms']:.0f} ms{note}[/dim]")


def list_sources_command(project: str) -> None:
    manifest = _engine(project).list_sources()
    if not manifest:
        console.print("[dim]No ingested sources yet. Run `adp ingest <path>`.[/dim]")
        return
    t = Table("table", "format", "kind", "rows", "cols", "ingested at")
    for name, m in manifest.items():
        t.add_row(
            name, m["detected_format"], m["relation_kind"],
            str(m["row_count"]), str(m["column_count"]), m["ingested_at"],
        )
    console.print(t)
