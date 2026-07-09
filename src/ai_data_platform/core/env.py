"""Environment interpolation for adp.yaml (${VAR} references)."""

from __future__ import annotations

import os
import re

from ai_data_platform.core.exceptions import ConfigError

_ENV_REF = re.compile(r"\$\{(?P<name>[A-Z0-9_]+)\}")
SECRET_SHAPED = re.compile(r"(sk-[A-Za-z0-9\-_]{16,}|[A-Za-z0-9\-_]{48,})")


def interpolate_env(value: str) -> str:
    """Replace ${VAR} with environment values; missing vars raise ConfigError."""

    def _sub(m: re.Match[str]) -> str:
        name = m.group("name")
        val = os.environ.get(name)
        if val is None:
            raise ConfigError(
                f"Environment variable {name!r} referenced in adp.yaml is not set.",
                hint=f"export {name}=... or add it to your .env file.",
            )
        return val

    return _ENV_REF.sub(_sub, value)
