"""ingestr CLI/SDK transport for warehouse load."""

from __future__ import annotations

import re
import shutil
import subprocess
import time
from collections.abc import Callable
from threading import Thread
from typing import Any

from ai_data_platform.core.exceptions import LoadError
from ai_data_platform.core.logging import get_logger
from ai_data_platform.load.types import TableLoadResult, TableLoadSpec

log = get_logger("adp.load.ingestr")

Runner = Callable[..., subprocess.CompletedProcess[str]]


def _flag_name(key: str) -> str:
    return key.replace("_", "-")


def build_ingestr_argv(spec: TableLoadSpec) -> list[str]:
    argv = [
        "ingest",
        "--source-uri",
        spec.source_uri,
        "--source-table",
        spec.source_table,
        "--dest-uri",
        spec.dest_uri,
        "--dest-table",
        spec.dest_table,
        "--incremental-strategy",
        spec.incremental_strategy,
    ]
    if spec.primary_key:
        argv.extend(["--primary-key", spec.primary_key])
    if spec.incremental_key:
        argv.extend(["--incremental-key", spec.incremental_key])
    if spec.interval_start:
        argv.extend(["--interval-start", spec.interval_start])
    if spec.interval_end:
        argv.extend(["--interval-end", spec.interval_end])

    # Stream / CDC flags — only emit when explicitly enabled
    if spec.stream:
        argv.append("--stream")
        if spec.flush_interval:
            argv.extend(["--flush-interval", spec.flush_interval])
        if spec.flush_records is not None:
            argv.extend(["--flush-records", str(spec.flush_records)])
        if spec.metrics_addr:
            argv.extend(["--metrics-addr", spec.metrics_addr])

    # Custom SQL on live sources is not passed as a CLI flag (ingestr has no --sql).
    # Use source.table + incremental_key + interval_start/interval_end instead,
    # or filter via source.ingestr_options (e.g. sql_limit).
    if spec.source_sql:
        log.warning(
            "source.sql is set for %s but ingestr has no --sql flag; "
            "use source.table + incremental_key + interval_start/interval_end",
            spec.table,
        )

    for key, value in spec.ingestr_options.items():
        flag = _flag_name(key)
        if value is True:
            argv.append(f"--{flag}")
        elif value is not None and value is not False:
            argv.extend([f"--{flag}", str(value)])
    return argv


def _redact_uri(uri: str) -> str:
    return re.sub(r":([^:@/]+)@", ":***@", uri)


def _read_stream(stream: Any, prefix: str) -> None:
    """Drain a stream line-by-line, emitting each as a log INFO message."""
    try:
        for line in iter(stream.readline, ""):
            if line := line.rstrip():
                log.info("%s %s", prefix, line)
    except Exception:
        pass  # stream closed — process ended


class IngestrTransport:
    def __init__(self, runner: Runner | None = None) -> None:
        self._runner = runner or subprocess.run
        self._availability_checked = False

    def ensure_available(self) -> None:
        if self._availability_checked:
            return
        if shutil.which("ingestr") is None:
            raise LoadError(
                "ingestr is not installed or not on PATH.",
                hint="pip install 'ai-data-platform[load]' or pip install 'ingestr[sdk]'",
            )
        self._availability_checked = True

    def load_table(
        self, spec: TableLoadSpec, *, dry_run: bool = False
    ) -> TableLoadResult:
        argv = build_ingestr_argv(spec)
        cmd = ["ingestr", *argv]
        redacted = " ".join(
            _redact_uri(a) if "://" in a else a for a in argv
        )
        log.info("ingestr %s", redacted)
        if dry_run:
            return TableLoadResult(
                table=spec.table,
                dest_table=spec.dest_table,
                status="dry_run",
                elapsed_ms=0.0,
            )

        started = time.perf_counter()
        if self._runner is not subprocess.run:
            proc = self._runner(cmd, capture_output=True, text=True, check=False)
            elapsed = (time.perf_counter() - started) * 1000
            if proc.returncode != 0:
                return TableLoadResult(
                    table=spec.table,
                    dest_table=spec.dest_table,
                    status="failed",
                    elapsed_ms=elapsed,
                    error=f"ingestr exited with code {proc.returncode}",
                )
            return TableLoadResult(
                table=spec.table,
                dest_table=spec.dest_table,
                status="ok",
                elapsed_ms=elapsed,
            )

        proc = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,  # merge stderr → stdout for ingestr
            text=True,
            bufsize=1,
        )
        t_out = Thread(target=_read_stream, args=(proc.stdout, "ingestr"), daemon=True)
        t_out.start()
        proc.wait()
        t_out.join(timeout=2)
        elapsed = (time.perf_counter() - started) * 1000

        if proc.returncode != 0:
            return TableLoadResult(
                table=spec.table,
                dest_table=spec.dest_table,
                status="failed",
                elapsed_ms=elapsed,
                error=f"ingestr exited with code {proc.returncode}",
            )
        return TableLoadResult(
            table=spec.table,
            dest_table=spec.dest_table,
            status="ok",
            elapsed_ms=elapsed,
        )


def get_transport(name: str = "ingestr") -> IngestrTransport:
    if name == "ingestr":
        return IngestrTransport()
    raise LoadError(f"Unknown load transport {name!r}.", hint="Only 'ingestr' is supported.")
