"""Tests for agent skill and MCP config installation."""

from __future__ import annotations

from pathlib import Path

import pytest

from ai_data_platform.agent.setup import ensure_global_agent_skills, install_agent
from ai_data_platform.agent.workflow import (
    agent_orchestrator_prompt,
    calibrate_dataset_prompt,
    intake_wizard_prompt,
    mcp_server_instructions,
    research_and_generate_prompt,
)


def test_install_agent_writes_mcp_and_skills(tmp_path: Path) -> None:
    result = install_agent(project_root=tmp_path, clients=["cursor", "windsurf", "vscode"], force=True)
    assert (tmp_path / ".cursor" / "mcp.json").exists()
    assert (tmp_path / ".windsurf" / "mcp.json").exists()
    assert (tmp_path / ".vscode" / "mcp.json").exists()
    skills = tmp_path / ".cursor" / "skills"
    assert skills.exists()
    assert (skills / "adp-orchestrator" / "SKILL.md").exists()
    assert (skills / "adp-intake" / "SKILL.md").exists()
    assert len(result["skills"]) >= 7
    content = (tmp_path / ".cursor" / "mcp.json").read_text()
    assert str(tmp_path.resolve()) in content


def test_install_agent_skips_existing_without_force(tmp_path: Path) -> None:
    install_agent(project_root=tmp_path, clients=["cursor"], force=True)
    mcp = tmp_path / ".cursor" / "mcp.json"
    mtime = mcp.stat().st_mtime
    result = install_agent(project_root=tmp_path, clients=["cursor"], force=False)
    assert result["mcp_configs"] == []
    assert mcp.stat().st_mtime == mtime


def test_install_agent_claude_snippet(tmp_path: Path) -> None:
    result = install_agent(project_root=tmp_path, clients=["claude"], force=True)
    snippet = result["claude"]["desktop_snippet"]
    assert str(tmp_path.resolve()) in snippet
    assert "mcpServers" in snippet


def test_ensure_global_agent_skills_version_gate(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    cursor_home = tmp_path / ".cursor"
    monkeypatch.setattr(Path, "home", lambda: tmp_path)
    first = ensure_global_agent_skills(force=True)
    assert first["skipped"] is False
    assert (cursor_home / "skills" / "adp-orchestrator" / "SKILL.md").exists()
    second = ensure_global_agent_skills(force=False)
    assert second["skipped"] is True


def test_workflow_prompts_contain_hard_rules() -> None:
    assert "apply_spec" in research_and_generate_prompt("retail")
    assert "PHASE" in intake_wizard_prompt("retail")
    assert "drift" in calibrate_dataset_prompt().lower()
    assert "Flow" in agent_orchestrator_prompt() or "FLOW" in agent_orchestrator_prompt()


def test_mcp_server_instructions_non_empty() -> None:
    instr = mcp_server_instructions()
    assert "apply_spec" in instr
    assert "Flow" in instr or "flow" in instr


@pytest.mark.asyncio
async def test_mcp_prompts_registered(profiled_project) -> None:
    from ai_data_platform.mcp.server import create_server

    mcp = create_server(str(profiled_project.root))
    prompts = {p.name for p in await mcp.list_prompts()}
    expected = {
        "agent_orchestrator",
        "intake_wizard",
        "research_and_generate",
        "calibrate_dataset",
        "new_dataset_wizard",
    }
    assert expected.issubset(prompts)
