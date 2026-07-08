"""Typed exception hierarchy. Every user-facing error carries a remediation hint."""

from __future__ import annotations


class ADPError(Exception):
    """Base error for ai-data-platform."""

    def __init__(self, message: str, *, hint: str | None = None) -> None:
        self.hint = hint
        super().__init__(message if hint is None else f"{message}\nHint: {hint}")


class ConfigError(ADPError):
    """Invalid or missing project configuration (adp.yaml)."""


class ProjectNotInitializedError(ConfigError):
    def __init__(self, path: str) -> None:
        super().__init__(
            f"No adp.yaml found in {path!r}.",
            hint="Run `adp init` in your project directory first.",
        )


class ConnectorError(ADPError):
    """Connector I/O or configuration failure."""


class ConnectorNotAvailableError(ConnectorError):
    """Connector exists as an interface but its driver extra is not installed
    or the implementation is a declared placeholder."""


class SourceNotFoundError(ConnectorError):
    def __init__(self, name: str, known: list[str]) -> None:
        super().__init__(
            f"Source {name!r} is not defined in adp.yaml.",
            hint=f"Known sources: {', '.join(known) or '(none)'}. Add one with `adp connect`.",
        )


class CatalogError(ADPError):
    """Metadata catalog storage failure."""


class TableNotFoundError(CatalogError):
    def __init__(self, table: str) -> None:
        super().__init__(
            f"Table {table!r} not found in the metadata catalog.",
            hint="Run `adp scan` to populate the catalog, or check the table name.",
        )


class ProfilingError(ADPError):
    """Profiling computation failure."""


class GenerationError(ADPError):
    """Synthetic data generation failure."""


class ValidationError(ADPError):
    """Quality check failure (engine failure, not a failed check)."""


class SemanticModelError(ADPError):
    """Semantic model build/render failure."""


class AIProviderError(ADPError):
    """LLM provider call failure."""


class AIExtractionError(AIProviderError):
    """LLM output failed schema validation after retry."""


class UnsafeSQLError(ADPError):
    """Generated/submitted SQL was rejected by the read-only guard."""


class UnsafePathError(ADPError):
    """A file write attempted to escape the project root."""
