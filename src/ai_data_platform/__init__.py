"""ai-data-platform: local-first AI data platform.

Public API:
    from ai_data_platform import ADPClient, __version__
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from ai_data_platform.__about__ import __version__

if TYPE_CHECKING:  # pragma: no cover
    from ai_data_platform.sdk import ADPClient

__all__ = ["ADPClient", "__version__"]


def __getattr__(name: str) -> Any:
    """Lazy import to keep `import ai_data_platform` fast and side-effect free."""
    if name == "ADPClient":
        from ai_data_platform.sdk import ADPClient

        return ADPClient
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
