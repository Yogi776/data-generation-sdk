"""Project path resolution and discovery."""

from __future__ import annotations

from pathlib import Path

import pytest

from ai_data_platform.config import default_config, save_config
from ai_data_platform.core.exceptions import ProjectNotInitializedError
from ai_data_platform.core.paths import discover_project_root, resolve_project_path


def test_discover_project_root_from_child(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    save_config(default_config("nested"), tmp_path)
    child = tmp_path / "output" / "data"
    child.mkdir(parents=True)
    monkeypatch.chdir(child)
    assert discover_project_root() == tmp_path.resolve()


def test_discover_project_root_missing_raises(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.chdir(tmp_path)
    with pytest.raises(ProjectNotInitializedError):
        discover_project_root()


def test_resolve_project_explicit_path(tmp_path: Path) -> None:
    save_config(default_config("explicit"), tmp_path)
    assert resolve_project_path(tmp_path) == tmp_path.resolve()


def test_resolve_project_dot_discovers(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    save_config(default_config("dot"), tmp_path)
    monkeypatch.chdir(tmp_path)
    assert resolve_project_path(".") == tmp_path.resolve()
