"""MCP Data Explorer: register generated files into DuckDB and explore them
with governed SQL, metadata inspection, and (optional) LLM-assisted insights.

Public surface is :class:`ExplorerService` (the single backend behind the SDK,
MCP tools, REST API, and CLI — same "one backend, many faces" rule as the rest
of the platform).
"""

from ai_data_platform.explorer.service import ExplorerService

__all__ = ["ExplorerService"]
