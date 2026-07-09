"""CLI for adp load commands."""

from __future__ import annotations

import json
from typing import Any

from rich.console import Console
from rich.table import Table

console = Console()
err_console = Console(stderr=True)


def _client(project: str) -> Any:
    from ai_data_platform.sdk import ADPClient

    return ADPClient(project)


def load_command(
    destination: str | None,
    tables: str | None,
    data_dir: str | None,
    dry_run: bool,
    skip_quality: bool,
    force_quality: bool,
    project: str,
) -> None:
    table_list = [t.strip() for t in tables.split(",")] if tables else None
    res = _client(project).load_data(
        destination=destination,
        tables=table_list,
        data_dir=data_dir,
        dry_run=dry_run,
        skip_quality=skip_quality,
        force_quality=force_quality,
    )
    t = Table(title=f"Load → {res['destination']} ({res['staging_format']})")
    t.add_column("table")
    t.add_column("dest_table")
    t.add_column("status")
    t.add_column("ms", justify="right")
    for row in res["tables"]:
        style = "green" if row["status"] == "ok" else "yellow" if row["status"] == "dry_run" else "red"
        t.add_row(
            row["table"],
            row["dest_table"],
            f"[{style}]{row['status']}[/{style}]",
            f"{row['elapsed_ms']:.0f}",
        )
    console.print(t)
    if res.get("quality_score") is not None:
        console.print(f"Quality score: {res['quality_score']}")
    console.print(f"Total: {res['elapsed_ms']:.0f} ms")


def destinations_command(scheme: str | None, as_json: bool) -> None:
    from ai_data_platform.load.destinations import INGESTR_DESTINATIONS, lookup_by_scheme

    rows = lookup_by_scheme(scheme) if scheme else list(INGESTR_DESTINATIONS)
    if as_json:
        console.print_json(
            json.dumps(
                [
                    {
                        "id": d.id,
                        "label": d.label,
                        "scheme": d.scheme,
                        "doc_url": d.doc_url,
                        "example_uri": d.example_uri,
                    }
                    for d in rows
                ]
            )
        )
        return
    t = Table(title=f"ingestr destinations ({len(rows)})")
    t.add_column("id")
    t.add_column("label")
    t.add_column("scheme")
    t.add_column("docs")
    for d in rows:
        t.add_row(d.id, d.label, d.scheme, d.doc_url)
    console.print(t)


def doctor_command(destination: str | None, project: str) -> None:
    from ai_data_platform.load.destinations import lookup_uri
    from ai_data_platform.load.ingestr import IngestrTransport

    client = _client(project)
    cfg = client.config
    dest_name = destination or cfg.load.default_destination
    if not dest_name:
        err_console.print("[red]No destination configured.[/red]")
        raise SystemExit(1)
    dest = cfg.destination(dest_name)
    checks: list[tuple[str, bool, str]] = []
    try:
        uri = dest.resolved_uri()
        checks.append(("uri resolves", True, uri.split("@")[-1][:80]))
    except Exception as e:  # noqa: BLE001
        checks.append(("uri resolves", False, str(e)))
        uri = ""
    info = lookup_uri(uri) if uri else None
    checks.append(("scheme recognized", info is not None, info.label if info else "unknown (still may work)"))
    try:
        IngestrTransport().ensure_available()
        checks.append(("ingestr on PATH", True, "ok"))
    except Exception as e:  # noqa: BLE001
        checks.append(("ingestr on PATH", False, str(e)))
    t = Table(title=f"adp load doctor — {dest_name}")
    t.add_column("check")
    t.add_column("ok")
    t.add_column("detail")
    for name, ok, detail in checks:
        t.add_row(name, "[green]yes[/green]" if ok else "[red]no[/red]", detail)
    console.print(t)
    if not all(c[1] for c in checks[:2]):  # uri + ingestr required
        raise SystemExit(1)
