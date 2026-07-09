"""Quality gate before load with optional cache."""

from __future__ import annotations

import json
from pathlib import Path
from typing import TYPE_CHECKING, Any

from ai_data_platform.core.exceptions import LoadError
from ai_data_platform.core.paths import adp_dir
from ai_data_platform.load.config_models import LoadConfig, StagingFormat
from ai_data_platform.load.local_sources import max_staging_mtime

if TYPE_CHECKING:  # pragma: no cover
    from ai_data_platform.sdk import ADPClient


_CACHE_FILE = "load_quality_cache.json"


def _cache_path(root: Path) -> Path:
    return adp_dir(root) / _CACHE_FILE


def _read_cache(root: Path) -> dict[str, Any] | None:
    path = _cache_path(root)
    if not path.exists():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return None


def _write_cache(root: Path, payload: dict[str, Any]) -> None:
    path = _cache_path(root)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def run_quality_gate(
    client: ADPClient,
    data_dir: Path,
    tables: list[str],
    fmt: StagingFormat,
    load_cfg: LoadConfig,
    *,
    force: bool = False,
) -> float:
    if not load_cfg.require_quality_pass:
        return 100.0

    staging_mtime = max_staging_mtime(data_dir, tables, fmt)
    cached = None if force else _read_cache(client.root)
    if (
        cached
        and cached.get("data_dir") == str(data_dir)
        and float(cached.get("staging_mtime", 0)) >= staging_mtime
        and "quality_score" in cached
    ):
        score = float(cached["quality_score"])
        if score < load_cfg.min_quality_score:
            raise LoadError(
                f"Cached quality score {score} is below minimum {load_cfg.min_quality_score}.",
                hint="Fix data or run `adp quality-check`, then `adp load --force-quality-check`.",
            )
        return score

    rep = client.quality_check(
        data_dir=str(data_dir.relative_to(client.root))
        if data_dir.is_relative_to(client.root)
        else str(data_dir)
    )
    score = float(rep["quality_score"])
    _write_cache(
        client.root,
        {
            "data_dir": str(data_dir),
            "staging_mtime": staging_mtime,
            "quality_score": score,
        },
    )
    if score < load_cfg.min_quality_score:
        raise LoadError(
            f"Quality score {score} is below minimum {load_cfg.min_quality_score}.",
            hint="Fix failing checks with `adp quality-check` or use `adp load --skip-quality` (not recommended).",
        )
    return score
