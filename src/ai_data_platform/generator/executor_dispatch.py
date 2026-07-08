"""Generation executor dispatch: Python (default) or external Go binary."""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import tempfile
from pathlib import Path
from typing import TYPE_CHECKING, Any

from ai_data_platform.core.exceptions import GenerationError
from ai_data_platform.core.logging import get_logger
from ai_data_platform.generator.engine import GenerationPlan, generate

if TYPE_CHECKING:  # pragma: no cover
    from ai_data_platform.config import GenerationConfig

log = get_logger("adp.executor")

GO_BINARY_NAMES = ("adp-executor", "adp_executor")


def go_executor_path() -> str | None:
    """Locate the Go executor on PATH or next to the Python package."""
    for name in GO_BINARY_NAMES:
        found = shutil.which(name)
        if found:
            return found
    # Developer layout: ai-data-platform/adp-executor/adp-executor
    here = Path(__file__).resolve().parents[3]
    for candidate in (
        here / "adp-executor" / "adp-executor",
        here / "adp-executor" / "bin" / "adp-executor",
    ):
        if candidate.is_file() and os.access(candidate, os.X_OK):
            return str(candidate)
    return None


def should_use_go(cfg: GenerationConfig, max_table_rows: int) -> bool:
    if cfg.executor == "python":
        return False
    if cfg.executor == "go":
        return go_executor_path() is not None
    # auto: use Go when binary is present and any table exceeds threshold
    return (
        go_executor_path() is not None and max_table_rows >= cfg.go_executor_threshold_rows
    )


def run_go_executor(
    plan: GenerationPlan,
    output_dir: str | Path,
    *,
    output_format: str,
) -> dict[str, Any]:
    binary = go_executor_path()
    if not binary:
        raise GenerationError(
            "Go executor requested but adp-executor binary not found.",
            hint="Build with: cd adp-executor && go build -o adp-executor ./cmd/adp-executor",
        )
    out = Path(output_dir)
    out.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(
        mode="w", suffix=".json", delete=False, encoding="utf-8"
    ) as tmp:
        tmp.write(plan.model_dump_json())
        plan_path = tmp.name
    try:
        proc = subprocess.run(
            [
                binary,
                "run",
                "--plan",
                plan_path,
                "--output",
                str(out),
                "--format",
                output_format,
            ],
            capture_output=True,
            text=True,
            check=False,
        )
        if proc.returncode != 0:
            raise GenerationError(
                f"Go executor failed (exit {proc.returncode}): {proc.stderr.strip() or proc.stdout}",
                hint="Fall back with generation.executor: python in adp.yaml.",
            )
        payload = json.loads(proc.stdout)
        if not payload.get("ok"):
            raise GenerationError(str(payload.get("error", "unknown Go executor error")))
        return payload["result"]
    finally:
        Path(plan_path).unlink(missing_ok=True)


def dispatch_generate(
    plan: GenerationPlan,
    output_dir: str | Path,
    *,
    output_format: str,
    cfg: GenerationConfig,
) -> dict[str, Any]:
    """Run generation via Go (when configured) or the in-process Python engine."""
    max_rows = max((t.rows for t in plan.tables), default=0)
    if should_use_go(cfg, max_rows):
        log.info("dispatching generation to Go executor (%d max rows)", max_rows)
        try:
            return run_go_executor(plan, output_dir, output_format=output_format)
        except GenerationError:
            if cfg.executor == "go":
                raise
            log.warning("Go executor failed; falling back to Python")
    workers = cfg.parallel_workers
    return generate(
        plan,
        output_dir,
        output_format=output_format,
        parallel_workers=workers,
    )
