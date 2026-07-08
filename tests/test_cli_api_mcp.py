"""CLI (Typer runner), local API (TestClient), and MCP tool contracts."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from typer.testing import CliRunner

from ai_data_platform.cli import app
from ai_data_platform.sdk import ADPClient

runner = CliRunner()


# -- CLI -------------------------------------------------------------------
def test_cli_version() -> None:
    result = runner.invoke(app, ["version"])
    assert result.exit_code == 0
    assert "ai-data-platform" in result.output


def test_cli_init_and_reinit(tmp_path: Path) -> None:
    result = runner.invoke(app, ["init", "--path", str(tmp_path), "--name", "x"])
    assert result.exit_code == 0
    assert (tmp_path / "adp.yaml").exists()
    again = runner.invoke(app, ["init", "--path", str(tmp_path)])
    assert again.exit_code == 1  # refuses without --force
    forced = runner.invoke(app, ["init", "--path", str(tmp_path), "--force"])
    assert forced.exit_code == 0


def test_cli_full_flow(tmp_path: Path, sample_data_dir: Path) -> None:
    p = str(tmp_path)
    assert runner.invoke(app, ["init", "--path", p]).exit_code == 0
    r = runner.invoke(
        app,
        [
            "connect",
            "--name",
            "shop",
            "--type",
            "csv",
            "--path",
            str(sample_data_dir),
            "--project",
            p,
        ],
    )
    assert r.exit_code == 0, r.output
    assert runner.invoke(app, ["scan", "--project", p]).exit_code == 0
    assert runner.invoke(app, ["profile", "--project", p]).exit_code == 0
    r = runner.invoke(app, ["generate-data", "--rows", "100", "--project", p])
    assert r.exit_code == 0, r.output
    r = runner.invoke(app, ["quality-check", "--project", p, "--report", "q.md"])
    assert r.exit_code == 0, r.output
    assert (tmp_path / "q.md").exists()
    r = runner.invoke(
        app, ["semantic-model", "--project", p, "--format", "cube", "--out", "model/cubes.yml"]
    )
    assert r.exit_code == 0, r.output
    assert (tmp_path / "model" / "cubes.yml").exists()
    assert runner.invoke(app, ["docs", "--project", p]).exit_code == 0
    r = runner.invoke(app, ["tables", "--project", p, "--json"])
    assert r.exit_code == 0


def test_cli_scan_without_init(tmp_path: Path) -> None:
    result = runner.invoke(app, ["scan", "--project", str(tmp_path)])
    assert result.exit_code == 1
    assert "adp init" in result.output


def test_cli_bad_source_type(tmp_path: Path) -> None:
    runner.invoke(app, ["init", "--path", str(tmp_path)])
    r = runner.invoke(
        app, ["connect", "--name", "x", "--type", "oracle", "--project", str(tmp_path)]
    )
    assert r.exit_code == 1


# -- API -------------------------------------------------------------------
@pytest.fixture()
def api_client(profiled_project: ADPClient):  # type: ignore[no-untyped-def]
    from fastapi.testclient import TestClient

    from ai_data_platform.api.app import create_app

    return TestClient(create_app(str(profiled_project.root)))


def test_api_health(api_client) -> None:  # type: ignore[no-untyped-def]
    body = api_client.get("/health").json()
    assert body["status"] == "ok"


def test_api_metadata_and_generate(api_client) -> None:  # type: ignore[no-untyped-def]
    tables = api_client.get("/metadata/tables").json()
    assert {t["table"] for t in tables} == {"customers", "orders"}
    detail = api_client.get("/metadata/tables/orders").json()
    assert any(c["name"] == "total_amount" for c in detail["columns"])
    hits = api_client.get("/metadata/search", params={"q": "amount"}).json()
    assert hits
    gen = api_client.post("/generate-data", json={"rows": 100}).json()
    assert gen["tables"]["orders"]["rows"] == 100
    q = api_client.post("/quality-check").json()
    assert q["quality_score"] > 0
    sem = api_client.post("/semantic-model", json={"format": "cube"}).json()
    assert "cubes" in sem["rendered"]


def test_api_error_shape(api_client) -> None:  # type: ignore[no-untyped-def]
    resp = api_client.get("/metadata/tables/nope")
    assert resp.status_code == 400
    assert "catalog" in resp.json()["detail"].lower()


def test_api_serves_ui(api_client) -> None:  # type: ignore[no-untyped-def]
    resp = api_client.get("/")
    assert resp.status_code == 200
    assert "ai-data-platform" in resp.text


# -- MCP -------------------------------------------------------------------
mcp = pytest.importorskip("mcp", reason="mcp extra not installed")


def _payload(out):  # type: ignore[no-untyped-def]
    content = out[0] if isinstance(out, tuple) else out
    return json.loads(content[0].text)


@pytest.mark.anyio
async def test_mcp_tools_registered(profiled_project: ADPClient) -> None:
    from ai_data_platform.mcp.server import create_server

    server = create_server(str(profiled_project.root))
    tools = {t.name for t in await server.list_tools()}
    assert tools >= {
        "search_metadata",
        "get_table_schema",
        "generate_sql",
        "generate_synthetic_data",
        "create_semantic_model",
        "run_quality_check",
        "generate_docs",
        "scan_sources",
        "profile_source",
    }


@pytest.mark.anyio
async def test_mcp_tool_calls(profiled_project: ADPClient) -> None:
    from ai_data_platform.mcp.server import create_server

    server = create_server(str(profiled_project.root))
    p = _payload(await server.call_tool("search_metadata", {"query": "order"}))
    assert p["ok"] and p["result"]
    p = _payload(await server.call_tool("get_table_schema", {"table": "orders"}))
    assert p["ok"] and p["result"]["table"] == "orders"
    p = _payload(
        await server.call_tool("generate_synthetic_data", {"rows": 50, "output_format": "parquet"})
    )
    assert p["ok"] and p["result"]["tables"]["orders"]["rows"] == 50
    p = _payload(await server.call_tool("run_quality_check", {}))
    assert p["ok"] and "quality_score" in p["result"]


SPEC_FOR_MCP = """
version: 1
tables:
  - name: sensors
    columns:
      - {name: sensor_id, type: uuid, primary_key: true}
      - {name: sensor_code, type: string, format: "SNS-####"}
      - {name: status, type: string, values: {active: 80, faulty: 20}}
"""


@pytest.mark.anyio
async def test_mcp_apply_spec_and_preview(tmp_path: Path) -> None:
    """Parity: config-only generation must work end-to-end through MCP alone."""
    from ai_data_platform.mcp.server import create_server

    ADPClient(tmp_path).init("mcp-spec")
    server = create_server(str(tmp_path))
    p = _payload(await server.call_tool("apply_spec", {"spec_yaml": SPEC_FOR_MCP}))
    assert p["ok"] and p["result"]["tables"] == 1
    p = _payload(
        await server.call_tool("generate_synthetic_data", {"rows": 200, "output_format": "parquet"})
    )
    assert p["ok"] and p["result"]["tables"]["sensors"]["rows"] == 200
    p = _payload(await server.call_tool("preview_data", {"table": "sensors", "limit": 5}))
    assert p["ok"] and p["result"]["showing"] == 5
    assert p["result"]["rows"][0]["sensor_code"].startswith("SNS-")
    # preview cap enforced
    p = _payload(await server.call_tool("preview_data", {"table": "sensors", "limit": 500}))
    assert p["ok"] and p["result"]["showing"] <= 50


@pytest.mark.anyio
async def test_mcp_unexpected_errors_wrapped(tmp_path: Path) -> None:
    """Non-ADP exceptions must come back structured, never as stack traces."""
    from ai_data_platform.mcp.server import create_server

    server = create_server(str(tmp_path))  # no adp.yaml at all
    p = _payload(await server.call_tool("apply_spec", {"spec_yaml": "tables: [broken"}))
    assert p["ok"] is False and "error" in p


@pytest.mark.anyio
async def test_mcp_errors_are_structured(profiled_project: ADPClient) -> None:
    from ai_data_platform.mcp.server import create_server

    server = create_server(str(profiled_project.root))
    p = _payload(await server.call_tool("get_table_schema", {"table": "ghost"}))
    assert p["ok"] is False and "catalog" in p["error"].lower()
    p = _payload(await server.call_tool("generate_synthetic_data", {"rows": 2_000_000}))
    assert p["ok"] is False and "limit" in p["error"].lower()


@pytest.fixture()
def anyio_backend() -> str:
    return "asyncio"
