"""Safe, project-rooted filesystem helpers."""

from __future__ import annotations

import os
from pathlib import Path

from ai_data_platform.config import CONFIG_FILENAME
from ai_data_platform.core.exceptions import ProjectNotInitializedError, UnsafePathError

ADP_DIR = ".adp"
CATALOG_DB = "catalog.db"


def project_root(path: str | Path = ".") -> Path:
    return Path(path).expanduser().resolve()


def discover_project_root(start: str | Path | None = None) -> Path:
    """Walk up from *start* (default: cwd) until ``adp.yaml`` is found.

    Resolution order:
    1. ``ADP_PROJECT`` env var (set in MCP config when the host cwd is not the workspace)
    2. Walk upward from *start* or process cwd

    Lets ``adp mcp-server`` run with no ``--project`` arg when the MCP host sets
    ``cwd`` to the workspace or ``ADP_PROJECT`` to the project directory.
    """
    env_root = os.environ.get("ADP_PROJECT", "").strip()
    if env_root:
        resolved = Path(env_root).expanduser().resolve()
        if (resolved / CONFIG_FILENAME).is_file():
            return resolved
    current = Path(start or Path.cwd()).expanduser().resolve()
    for directory in (current, *current.parents):
        if (directory / CONFIG_FILENAME).is_file():
            return directory
    raise ProjectNotInitializedError(str(current))


def resolve_project_path(path: str | Path = ".") -> Path:
    """Resolve CLI/MCP ``--project``: explicit path, or auto-discover from cwd."""
    candidate = Path(path).expanduser()
    if str(path) in (".", ""):
        return discover_project_root()
    resolved = candidate.resolve()
    if (resolved / CONFIG_FILENAME).is_file():
        return resolved
    raise ProjectNotInitializedError(str(resolved))


def adp_dir(root: str | Path = ".") -> Path:
    d = project_root(root) / ADP_DIR
    d.mkdir(parents=True, exist_ok=True)
    return d


def catalog_path(root: str | Path = ".") -> Path:
    return adp_dir(root) / CATALOG_DB


def safe_resolve(root: str | Path, relative: str | Path) -> Path:
    """Resolve `relative` under `root`; refuse traversal outside the project.

    Raises:
        UnsafePathError: if the resolved path escapes the project root.
    """
    base = project_root(root)
    candidate = (base / Path(relative)).resolve()
    if not candidate.is_relative_to(base):
        raise UnsafePathError(
            f"Refusing to write outside the project root: {candidate}",
            hint="Output paths must stay inside the project directory.",
        )
    return candidate


def safe_write_text(root: str | Path, relative: str | Path, content: str) -> Path:
    """Write text to a project-rooted path, creating parent dirs."""
    target = safe_resolve(root, relative)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(content, encoding="utf-8")
    return target
