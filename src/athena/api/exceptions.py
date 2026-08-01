"""API Resource Exceptions (P8.3).

Defines exceptions for resource lookups and platform states returned to callers.
"""

from __future__ import annotations

from athena.errors import AthenaError


class APIResourceError(AthenaError):
    """Base exception for all API resource errors."""


class ResourceNotFoundError(APIResourceError):
    """Base exception for all HTTP 404 resource not found errors."""


class DecisionNotFoundError(ResourceNotFoundError):
    """Specific decision not found."""


class PipelineRunNotFoundError(ResourceNotFoundError):
    """Specific pipeline execution run not found."""


class WorkspaceSnapshotNotFoundError(ResourceNotFoundError):
    """Specific workspace snapshot not found."""


class SchedulerRunNotFoundError(ResourceNotFoundError):
    """Specific scheduler history execution run not found."""


class PortfolioUnavailableError(APIResourceError):
    """Current portfolio state is unconstructed or unavailable (HTTP 503)."""


class ReportNotFoundError(ResourceNotFoundError):
    """Specific generic report not found."""


class PerformanceSnapshotNotFoundError(ResourceNotFoundError):
    """Specific analytics performance snapshot not found."""


class ExportSnapshotNotFoundError(ResourceNotFoundError):
    """Specific batch export snapshot not found."""


class ExportArtifactNotFoundError(ResourceNotFoundError):
    """Specific exported presentation artifact not found."""


class ExportGenerationError(APIResourceError):
    """Failed to dynamically adapt/generate presentation format for an artifact."""


class BacktestRunNotFoundError(ResourceNotFoundError):
    """Specific backtest run not found."""


class BackupNotFoundError(ResourceNotFoundError):
    """Specific database backup artifact not found."""


class IndexNotFoundError(ResourceNotFoundError):
    """Specific tracked index key not found or disabled (IX-4a)."""


class RestoreConfirmationError(APIResourceError):
    """Restore refused because confirmation token was missing or incorrect."""


class PortfolioResetConfirmationError(APIResourceError):
    """Portfolio reset refused because confirmation token was missing or incorrect."""


class DecisionsResetConfirmationError(APIResourceError):
    """Decisions & Trace reset refused because confirmation token was missing or incorrect."""


class DatabaseUnavailableError(APIResourceError):
    """Live SQLite database path is missing or cannot be opened for backup ops."""

