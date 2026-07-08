"""Logging with secret masking.

Any log record passing through `get_logger()` has values of secret-shaped
keys and obvious token literals redacted. Tested in tests/test_config.py.
"""

from __future__ import annotations

import logging
import re

MASK = "***REDACTED***"

# key=value / "key": "value" pairs whose key looks secret-shaped
_KV_PATTERN = re.compile(
    r"""(?ix)
    (?P<key>["']?(?:password|passwd|secret|token|api[_-]?key|authorization|dsn)["']?
    \s*[:=]\s*)
    (?P<q>["']?)(?P<value>[^"'\s,}]+)(?P=q)
    """
)
# long bearer-ish literals (sk-..., 40+ char base62 blobs)
_TOKEN_PATTERN = re.compile(r"\b(sk-[A-Za-z0-9\-_]{16,}|[A-Za-z0-9\-_]{48,})\b")


def mask_secrets(text: str) -> str:
    """Redact secret-shaped substrings from a string."""
    text = _KV_PATTERN.sub(lambda m: f"{m.group('key')}{MASK}", text)
    return _TOKEN_PATTERN.sub(MASK, text)


class _MaskingFilter(logging.Filter):
    def filter(self, record: logging.LogRecord) -> bool:
        try:
            msg = record.getMessage()
        except Exception:  # noqa: BLE001 - never let logging crash the app
            return True
        masked = mask_secrets(msg)
        if masked != msg:
            record.msg = masked
            record.args = ()
        return True


_configured = False


def get_logger(name: str = "adp") -> logging.Logger:
    """Return a logger with the masking filter installed exactly once."""
    global _configured
    logger = logging.getLogger(name)
    if not _configured:
        handler = logging.StreamHandler()
        handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(name)s %(message)s"))
        root = logging.getLogger("adp")
        root.addHandler(handler)
        root.setLevel(logging.INFO)
        root.addFilter(_MaskingFilter())
        for h in root.handlers:
            h.addFilter(_MaskingFilter())
        _configured = True
    return logger
