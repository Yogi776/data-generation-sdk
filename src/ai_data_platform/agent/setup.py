"""Install Cursor skills and multi-client MCP configs from bundled templates."""

from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path
from typing import Any

from ai_data_platform.__about__ import __version__

_SKILLS_PKG = "ai_data_platform.agent_skills"
_VERSION_FILE = ".adp-agent-skills-version"

ALL_CLIENTS = ("cursor", "claude", "windsurf", "vscode")
MCP_TEMPLATES: dict[str, tuple[str, str]] = {
    "cursor": ("mcp.cursor.json", ".cursor/mcp.json"),
    "windsurf": ("mcp.windsurf.json", ".windsurf/mcp.json"),
    "vscode": ("mcp.vscode.json", ".vscode/mcp.json"),
}


def _skills_root() -> Path:
    """Bundled agent_skills directory (works in editable and wheel installs)."""
    root = Path(__file__).resolve().parent.parent / "agent_skills"
    if not root.is_dir():
        from importlib import resources

        ref = resources.files(_SKILLS_PKG)
        root = Path(str(ref))
    if not root.is_dir():
        raise FileNotFoundError(f"agent_skills package data not found at {root}")
    return root


def _read_template(name: str) -> str:
    return (_skills_root() / "templates" / name).read_text(encoding="utf-8")


def _skill_dirs() -> list[Path]:
    root = _skills_root()
    return sorted(p for p in root.iterdir() if p.is_dir() and p.name.startswith("adp-"))


def _copy_skills(dest: Path, *, force: bool = False) -> list[str]:
    """Copy adp-* skill directories into dest."""
    dest.mkdir(parents=True, exist_ok=True)
    installed: list[str] = []
    for skill_dir in _skill_dirs():
        target = dest / skill_dir.name
        if target.exists() and not force:
            continue
        if target.exists():
            shutil.rmtree(target)
        shutil.copytree(skill_dir, target)
        installed.append(skill_dir.name)
    return installed


def _write_mcp_config(project_root: Path, client: str, *, force: bool = False) -> str | None:
    if client not in MCP_TEMPLATES:
        return None
    template_name, rel_path = MCP_TEMPLATES[client]
    dest = project_root / rel_path
    if dest.exists() and not force:
        return None
    dest.parent.mkdir(parents=True, exist_ok=True)
    content = _read_template(template_name)
    # Replace placeholder with project path for absolute cwd in some clients
    content = content.replace("{{PROJECT_ROOT}}", str(project_root.resolve()))
    dest.write_text(content, encoding="utf-8")
    return str(dest)


def _claude_desktop_snippet(project_root: Path) -> str:
    raw = _read_template("claude-desktop.snippet.json")
    snippet = json.loads(raw)
    for srv in snippet.get("mcpServers", {}).values():
        if "cwd" in srv:
            srv["cwd"] = str(project_root.resolve())
    return json.dumps(snippet, indent=2)


def _try_claude_mcp_add(project_root: Path) -> dict[str, Any]:
    """Register ADP with Claude Code CLI if available."""
    claude = shutil.which("claude")
    if not claude:
        return {"ok": False, "message": "claude CLI not on PATH"}
    cmd = [
        claude,
        "mcp",
        "add",
        "adp",
        "--",
        "adp",
        "mcp-server",
        "--project",
        str(project_root.resolve()),
    ]
    try:
        proc = subprocess.run(cmd, capture_output=True, text=True, timeout=30, check=False)
        return {
            "ok": proc.returncode == 0,
            "message": (proc.stdout or proc.stderr or "").strip() or f"exit {proc.returncode}",
        }
    except (subprocess.TimeoutExpired, OSError) as e:
        return {"ok": False, "message": str(e)}


def install_agent(
    *,
    project_root: Path | None = None,
    clients: list[str] | None = None,
    force: bool = False,
) -> dict[str, Any]:
    """Install MCP configs + optional Cursor skills from bundled templates."""
    root = (project_root or Path.cwd()).resolve()
    selected = list(clients) if clients else list(ALL_CLIENTS)
    if "all" in selected:
        selected = list(ALL_CLIENTS)

    result: dict[str, Any] = {
        "project_root": str(root),
        "version": __version__,
        "mcp_configs": [],
        "skills": [],
        "claude": {},
        "hints": [],
    }

    for client in selected:
        if client == "cursor":
            path = _write_mcp_config(root, "cursor", force=force)
            if path:
                result["mcp_configs"].append(path)
            skills_dest = root / ".cursor" / "skills"
            result["skills"] = _copy_skills(skills_dest, force=force)
        elif client == "windsurf":
            path = _write_mcp_config(root, "windsurf", force=force)
            if path:
                result["mcp_configs"].append(path)
        elif client == "vscode":
            path = _write_mcp_config(root, "vscode", force=force)
            if path:
                result["mcp_configs"].append(path)
        elif client == "claude":
            result["claude"]["desktop_snippet"] = _claude_desktop_snippet(root)
            result["claude"]["code_cli"] = _try_claude_mcp_add(root)

    result["hints"].append(
        "Any MCP client: adp mcp-server --project " + str(root)
    )
    if "cursor" in selected:
        result["hints"].append("Cursor: reload MCP after init; skills in .cursor/skills/adp-*")
    if "claude" in selected:
        result["hints"].append(
            "Claude: use MCP prompts agent_orchestrator, intake_wizard, research_and_generate"
        )
    return result


def ensure_global_agent_skills(*, force: bool = False) -> dict[str, Any]:
    """Install version-gated global Cursor skills to ~/.cursor/skills/."""
    home = Path.home()
    dest = home / ".cursor" / "skills"
    marker = home / ".cursor" / _VERSION_FILE
    current = marker.read_text(encoding="utf-8").strip() if marker.exists() else ""
    if current == __version__ and not force:
        return {"installed": [], "skipped": True, "version": __version__}
    installed = _copy_skills(dest, force=True)
    marker.parent.mkdir(parents=True, exist_ok=True)
    marker.write_text(__version__ + "\n", encoding="utf-8")
    return {"installed": installed, "skipped": False, "version": __version__}
