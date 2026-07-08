"""adp — the ai-data-platform CLI (Typer).

Thin presentation layer: every command delegates to ADPClient.
Heavy imports happen inside commands to keep `adp --help` fast.
"""

from __future__ import annotations

import json
from pathlib import Path

import typer
from rich.console import Console
from rich.table import Table

from ai_data_platform.__about__ import __version__

app = typer.Typer(
    name="adp",
    help="AI Data Platform: catalog, profile, generate, model, query — local-first.",
    no_args_is_help=True,
    pretty_exceptions_show_locals=False,
)
console = Console()
err_console = Console(stderr=True)


def _client(path: str = ".") -> object:
    from ai_data_platform.sdk import ADPClient

    return ADPClient(path)


def _fail(e: Exception) -> None:
    err_console.print(f"[red]Error:[/red] {e}")
    raise typer.Exit(code=1)


@app.callback()
def _version_callback() -> None:
    """AI Data Platform CLI."""


@app.command()
def version() -> None:
    """Print the installed version."""
    console.print(f"ai-data-platform {__version__}")


@app.command()
def init(
    name: str = typer.Option(None, "--name", "-n", help="Project name (default: directory name)."),
    path: str = typer.Option(".", "--path", help="Project directory."),
    force: bool = typer.Option(False, "--force", help="Overwrite an existing adp.yaml."),
) -> None:
    """Initialize a project: create adp.yaml and the local catalog directory."""
    from ai_data_platform.core.exceptions import ADPError
    from ai_data_platform.sdk import ADPClient

    try:
        cfg_path = ADPClient(path).init(name, force=force)
        console.print(f"[green]✓[/green] Created {cfg_path}")
        console.print("Next: [bold]adp connect[/bold] to add a data source.")
    except ADPError as e:
        _fail(e)


@app.command()
def connect(
    name: str = typer.Option(..., "--name", "-n", help="Source name."),
    type_: str = typer.Option(..., "--type", "-t", help="csv|parquet|duckdb|postgres|mysql|…"),
    path: str = typer.Option(None, "--path", help="File/directory path (csv, parquet, duckdb)."),
    dsn: str = typer.Option(
        None, "--dsn", help='DSN, e.g. "postgresql+psycopg://u:${PGPASSWORD}@h/db"'
    ),
    schema: str = typer.Option(None, "--schema", help="Database schema (postgres/mysql)."),
    project: str = typer.Option(".", "--project", help="Project directory."),
    no_test: bool = typer.Option(False, "--no-test", help="Skip the connection test."),
) -> None:
    """Add a data source to adp.yaml (tests the connection by default)."""
    from ai_data_platform.config import SourceConfig
    from ai_data_platform.core.exceptions import ADPError
    from ai_data_platform.sdk import ADPClient

    try:
        source = SourceConfig(name=name, type=type_, path=path, dsn=dsn, schema=schema)  # type: ignore[arg-type]
        result = ADPClient(project).add_source(source, test=not no_test)
        if result.get("ok"):
            console.print(
                f"[green]✓[/green] Source [bold]{name}[/bold] added. {result.get('message', '')}"
            )
            console.print("Next: [bold]adp scan[/bold] to build the metadata catalog.")
        else:
            _fail(Exception(f"connection test failed: {result.get('message')}"))
    except ADPError as e:
        _fail(e)
    except Exception as e:  # pydantic validation
        _fail(e)


@app.command()
def scan(
    source: str = typer.Option(None, "--source", "-s", help="Scan one source (default: all)."),
    project: str = typer.Option(".", "--project", help="Project directory."),
) -> None:
    """Discover schemas, tables, columns, and relationship candidates."""
    from ai_data_platform.core.exceptions import ADPError
    from ai_data_platform.sdk import ADPClient

    try:
        summaries = ADPClient(project).scan(source)
        t = Table(title="Scan results")
        for col in ("source", "tables", "columns", "fk_candidates"):
            t.add_column(col)
        for s in summaries:
            t.add_row(s["source"], str(s["tables"]), str(s["columns"]), str(s["fk_candidates"]))
        console.print(t)
        console.print("Next: [bold]adp profile[/bold] for statistics, PII, and key detection.")
    except ADPError as e:
        _fail(e)


@app.command()
def profile(
    source: str = typer.Option(None, "--source", "-s", help="Profile one source (default: all)."),
    sample_rows: int = typer.Option(10_000, "--sample-rows", help="Sample budget per table."),
    project: str = typer.Option(".", "--project", help="Project directory."),
) -> None:
    """Profile tables: stats, distributions, PII, PK/FK confirmation."""
    from ai_data_platform.core.exceptions import ADPError
    from ai_data_platform.sdk import ADPClient

    try:
        summaries = ADPClient(project).profile(source, sample_rows=sample_rows)
        t = Table(title="Profile results")
        t.add_column("table")
        t.add_column("rows sampled")
        t.add_column("pk candidates")
        t.add_column("pii columns")
        for s in summaries:
            t.add_row(
                s["table"],
                str(s["rows_sampled"]),
                ", ".join(s["pk_candidates"]) or "—",
                ", ".join(s["pii_columns"]) or "—",
            )
        console.print(t)
    except ADPError as e:
        _fail(e)


@app.command("apply-spec")
def apply_spec(
    spec: str = typer.Argument(..., help="Path to a dataset spec YAML."),
    project: str = typer.Option(".", "--project", help="Project directory."),
) -> None:
    """Register a declarative dataset spec — generate with NO seed data.

    Declare tables, columns, category weights, numeric ranges, and foreign keys
    in YAML; then run `adp generate-data` directly (no scan/profile needed).
    """
    from ai_data_platform.core.exceptions import ADPError
    from ai_data_platform.sdk import ADPClient

    try:
        result = ADPClient(project).apply_spec(spec)
        console.print(
            f"[green]✓[/green] Spec applied: {result['tables']} table(s), "
            f"{result['columns']} column(s), {result['relationships']} relationship(s)."
        )
        console.print("Next: [bold]adp generate-data --rows N[/bold]")
    except ADPError as e:
        _fail(e)


@app.command("generate-data")
def generate_data(
    rows: int = typer.Option(None, "--rows", "-r", help="Default rows per table."),
    rows_per_table: str = typer.Option(
        None,
        "--rows-per-table",
        help='Per-table counts: "products=20,customers=1000,transactions=100000"',
    ),
    tables: str = typer.Option(None, "--tables", help="Comma-separated subset of tables."),
    seed: int = typer.Option(None, "--seed", help="Deterministic seed."),
    output: str = typer.Option(None, "--output", "-o", help="csv|parquet|duckdb|sql"),
    output_dir: str = typer.Option(None, "--output-dir", help="Output directory."),
    project: str = typer.Option(".", "--project", help="Project directory."),
) -> None:
    """Generate synthetic data from the catalog (FK-safe, seeded, profile-driven)."""
    from ai_data_platform.core.exceptions import ADPError
    from ai_data_platform.sdk import ADPClient

    try:
        rpt: dict[str, int] | None = None
        if rows_per_table:
            try:
                rpt = {
                    kv.split("=")[0].strip(): int(kv.split("=")[1])
                    for kv in rows_per_table.split(",")
                }
            except (IndexError, ValueError):
                _fail(Exception('--rows-per-table format: "table=count,table2=count"'))
        result = ADPClient(project).generate_data(
            rows,
            tables=[t.strip() for t in tables.split(",")] if tables else None,
            seed=seed,
            rows_per_table=rpt,
            output_format=output,
            output_dir=output_dir,
        )
        t = Table(title=f"Generated (seed={result['seed']}, format={result['format']})")
        t.add_column("table")
        t.add_column("rows")
        t.add_column("path")
        for name, info in result["tables"].items():
            t.add_row(name, str(info["rows"]), info["path"])
        console.print(t)
        console.print("Next: [bold]adp quality-check[/bold] to validate the output.")
    except ADPError as e:
        _fail(e)


@app.command("quality-check")
def quality_check(
    data_dir: str = typer.Option(None, "--data-dir", help="Directory of csv/parquet to check."),
    report: str = typer.Option(None, "--report", help="Write a Markdown report to this path."),
    project: str = typer.Option(".", "--project", help="Project directory."),
) -> None:
    """Run auto-derived quality checks and print the quality score."""
    from ai_data_platform.core.exceptions import ADPError
    from ai_data_platform.quality.checks import report_to_markdown
    from ai_data_platform.sdk import ADPClient

    try:
        client = ADPClient(project)
        rep = client.quality_check(data_dir)
        color = (
            "green"
            if rep["quality_score"] >= 90
            else "yellow"
            if rep["quality_score"] >= 70
            else "red"
        )
        console.print(f"Quality score: [{color}]{rep['quality_score']}/100[/{color}]")
        for cat, v in rep["category_scores"].items():
            console.print(f"  {cat}: {v}")
        for t in rep["tables"]:
            failed = [c for c in t["checks"] if not c["passed"]]
            if failed:
                console.print(f"[yellow]{t['table']}[/yellow]: {len(failed)} failing check(s)")
                for c in failed:
                    console.print(
                        f"  ✗ {c['rule_type']} {c['params'].get('column', '')}: {c['evidence']}"
                    )
        if report:
            from ai_data_platform.core.paths import safe_write_text

            path = safe_write_text(client.root, report, report_to_markdown(rep))
            console.print(f"Report written to {path}")
    except ADPError as e:
        _fail(e)


@app.command("semantic-model")
def semantic_model(
    name: str = typer.Option("default", "--name", help="Semantic model name."),
    fmt: str = typer.Option(None, "--format", "-f", help="generic|cube"),
    out: str = typer.Option(None, "--out", "-o", help="Write YAML to this path."),
    project: str = typer.Option(".", "--project", help="Project directory."),
) -> None:
    """Build a semantic model (facts, dimensions, measures, joins) as YAML."""
    from ai_data_platform.core.exceptions import ADPError
    from ai_data_platform.sdk import ADPClient

    try:
        client = ADPClient(project)
        result = client.create_semantic_model(name, fmt)
        if out:
            from ai_data_platform.core.paths import safe_write_text

            path = safe_write_text(client.root, out, result["rendered"])
            console.print(f"[green]✓[/green] Semantic model ({result['format']}) -> {path}")
        else:
            console.print(result["rendered"])
    except ADPError as e:
        _fail(e)


@app.command()
def sql(
    question: str = typer.Argument(..., help="Natural-language question."),
    execute: bool = typer.Option(
        False, "--execute", help="Execute against a duckdb output/source."
    ),
    project: str = typer.Option(".", "--project", help="Project directory."),
) -> None:
    """Ask a question; get a read-only SQL query (and optionally run it on DuckDB)."""
    from ai_data_platform.core.exceptions import ADPError
    from ai_data_platform.sdk import ADPClient

    try:
        client = ADPClient(project)
        result = client.generate_sql(question)
        console.print(f"[bold]SQL[/bold] (confidence {result['confidence']:.2f}):")
        console.print(result["sql"])
        if result["explanation"]:
            console.print(f"[dim]{result['explanation']}[/dim]")
        if execute:
            import duckdb

            from ai_data_platform.core.paths import safe_resolve

            db = safe_resolve(client.root, Path(client.config.output_dir) / "generated.duckdb")
            if not db.exists():
                _fail(
                    Exception(
                        f"No DuckDB file at {db}. Generate with `adp generate-data -o duckdb` first."
                    )
                )
            with duckdb.connect(str(db), read_only=True) as con:
                console.print(con.execute(result["sql"]).pl())
    except ADPError as e:
        _fail(e)


@app.command()
def docs(
    out: str = typer.Option("docs/data-dictionary.md", "--out", "-o", help="Output path."),
    project: str = typer.Option(".", "--project", help="Project directory."),
) -> None:
    """Generate a Markdown data dictionary from the catalog."""
    from ai_data_platform.core.exceptions import ADPError
    from ai_data_platform.core.paths import safe_write_text
    from ai_data_platform.sdk import ADPClient

    try:
        client = ADPClient(project)
        path = safe_write_text(client.root, out, client.generate_docs())
        console.print(f"[green]✓[/green] Data dictionary -> {path}")
    except ADPError as e:
        _fail(e)


@app.command()
def tables(
    search: str = typer.Option(None, "--search", "-q", help="Search tables/columns."),
    as_json: bool = typer.Option(False, "--json", help="JSON output."),
    project: str = typer.Option(".", "--project", help="Project directory."),
) -> None:
    """List or search cataloged tables."""
    from ai_data_platform.core.exceptions import ADPError
    from ai_data_platform.sdk import ADPClient

    try:
        client = ADPClient(project)
        rows = client.search_metadata(search) if search else client.list_tables()
        if as_json:
            console.print_json(json.dumps(rows))
            return
        t = Table(title="Catalog")
        if rows:
            for col in rows[0]:
                t.add_column(str(col))
            for r in rows:
                t.add_row(*(str(v) if v is not None else "—" for v in r.values()))
        console.print(t)
    except ADPError as e:
        _fail(e)


@app.command("mcp-server")
def mcp_server(
    project: str = typer.Option(".", "--project", help="Project directory."),
) -> None:
    """Start the MCP server (stdio) for Claude, Cursor, Windsurf, VS Code."""
    try:
        from ai_data_platform.mcp.server import run_server
    except ImportError:
        _fail(Exception("MCP support requires the mcp extra: pip install 'ai-data-platform[mcp]'"))
        return
    run_server(project)


@app.command()
def ui(
    host: str = typer.Option(
        "127.0.0.1", "--host", help="Bind address (localhost only by default)."
    ),
    port: int = typer.Option(8765, "--port", "-p"),
    project: str = typer.Option(".", "--project", help="Project directory."),
) -> None:
    """Start the local API + web console."""
    import uvicorn

    from ai_data_platform.api.app import create_app

    if host not in ("127.0.0.1", "localhost"):
        err_console.print(
            "[yellow]Warning:[/yellow] binding beyond localhost exposes your catalog "
            "to the network."
        )
    console.print(f"ADP console: http://{host}:{port}")
    uvicorn.run(create_app(project), host=host, port=port, log_level="warning")


if __name__ == "__main__":
    app()
