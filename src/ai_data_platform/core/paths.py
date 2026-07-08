"""Safe, project-rooted filesystem helpers."""

from __future__ import annotations

from pathlib import Path

from ai_data_platform.core.exceptions import UnsafePathError

ADP_DIR = ".adp"
CATALOG_DB = "catalog.db"


def project_root(path: str | Path = ".") -> Path:
    return Path(path).expanduser().resolve()


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
