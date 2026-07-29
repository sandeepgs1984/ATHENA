"""API error handling: Problem Details (RFC 9457) and AthenaExceptionMapper (P8.1).

AthenaExceptionMapper is the single registry responsible for:
- Exception classification by type
- HTTP status code mapping
- Problem Details DTO construction

Exception handlers in app.py are thin delegators to this mapper.
New exception types are registered here without touching handlers.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import ClassVar

from athena.api.exceptions import (
    APIResourceError,
    BacktestRunNotFoundError,
    BackupNotFoundError,
    DatabaseUnavailableError,
    DecisionNotFoundError,
    DecisionsResetConfirmationError,
    ExportArtifactNotFoundError,
    ExportGenerationError,
    ExportSnapshotNotFoundError,
    PerformanceSnapshotNotFoundError,
    PipelineRunNotFoundError,
    PortfolioResetConfirmationError,
    PortfolioUnavailableError,
    ReportNotFoundError,
    ResourceNotFoundError,
    RestoreConfirmationError,
    SchedulerRunNotFoundError,
    WorkspaceSnapshotNotFoundError,
)
from athena.api.platform.problem_details import ProblemDetail
from athena.api.security.exceptions import (
    AuthenticationError,
    AuthenticationLockedError,
    ExpiredTokenError,
    InvalidAPIKeyError,
    InvalidCredentialsError,
    InvalidTokenError,
    PermissionDeniedError,
    SecurityError,
    SessionRevokedError,
)
from athena.errors import (
    AllocationError,
    AthenaError,
    ConfigError,
    DataStaleError,
    DataValidationError,
    LifecycleError,
    MonitoringError,
    OrchestrationError,
    OrderPlanningError,
    PortfolioAnalyticsError,
    PortfolioError,
    ProviderError,
    ReplayMismatchError,
    ReportingError,
    RepositoryError,
    SizingError,
    WorkspaceError,
)
from athena.ops.full_validation import CycleBusyError
from athena.ops.serve_runtime import RestartUnavailableError

logger = logging.getLogger(__name__)

_BASE_TYPE_URI = "https://athena.internal/errors"





@dataclass(frozen=True, slots=True)
class ExceptionMapping:
    """Maps one exception type to an HTTP status code and Problem Details URI."""

    exc_type: type[Exception]
    http_status: int
    problem_slug: str       # appended to _BASE_TYPE_URI
    title: str


class AthenaExceptionMapper:
    """Registry mapping ATHENA exceptions to RFC 9457 Problem Details.

    Classification uses MRO order: the first matching entry in the registry wins.
    More specific exceptions must be registered before their base classes.
    """

    _registry: ClassVar[list[ExceptionMapping]] = [
        # Specific ATHENA errors (most specific first)
        ExceptionMapping(ConfigError,           500, "config-error",        "Configuration Error"),
        ExceptionMapping(DataStaleError,        503, "data-stale",          "Data Stale"),
        ExceptionMapping(DataValidationError,   422, "data-validation",     "Data Validation Error"),
        ExceptionMapping(ProviderError,         502, "provider-error",      "Provider Unavailable"),
        ExceptionMapping(ReplayMismatchError,   500, "replay-mismatch",     "Replay Mismatch"),
        ExceptionMapping(RepositoryError,       503, "repository-error",    "Repository Unavailable"),
        ExceptionMapping(OrchestrationError,    500, "orchestration-error", "Orchestration Error"),
        ExceptionMapping(WorkspaceError,        500, "workspace-error",     "Workspace Error"),
        ExceptionMapping(PortfolioError,        422, "portfolio-error",     "Portfolio Constraint Violation"),
        ExceptionMapping(AllocationError,       422, "allocation-error",    "Allocation Error"),
        ExceptionMapping(SizingError,           422, "sizing-error",        "Sizing Error"),
        ExceptionMapping(OrderPlanningError,    422, "order-planning-error","Order Planning Error"),
        ExceptionMapping(LifecycleError,        422, "lifecycle-error",     "Lifecycle Error"),
        ExceptionMapping(PortfolioAnalyticsError, 500, "analytics-error",  "Analytics Error"),
        ExceptionMapping(ReportingError,        500, "reporting-error",     "Reporting Error"),
        ExceptionMapping(MonitoringError,       500, "monitoring-error",    "Monitoring Error"),
        # Resource Exceptions (P8.3 / P8.4)
        ExceptionMapping(DecisionNotFoundError, 404, "decision-not-found", "Decision Not Found"),
        ExceptionMapping(PipelineRunNotFoundError, 404, "pipeline-run-not-found", "Pipeline Run Not Found"),
        ExceptionMapping(WorkspaceSnapshotNotFoundError, 404, "workspace-not-found", "Workspace Snapshot Not Found"),
        ExceptionMapping(SchedulerRunNotFoundError, 404, "scheduler-run-not-found", "Scheduler Run Not Found"),
        ExceptionMapping(ReportNotFoundError, 404, "report-not-found", "Report Not Found"),
        ExceptionMapping(BacktestRunNotFoundError, 404, "backtest-run-not-found", "Backtest Run Not Found"),
        ExceptionMapping(BackupNotFoundError, 404, "backup-not-found", "Backup Not Found"),
        ExceptionMapping(
            RestoreConfirmationError,
            400,
            "restore-confirmation-required",
            "Restore Confirmation Required",
        ),
        ExceptionMapping(
            PortfolioResetConfirmationError,
            400,
            "portfolio-reset-confirmation-required",
            "Portfolio Reset Confirmation Required",
        ),
        ExceptionMapping(
            DecisionsResetConfirmationError,
            400,
            "decisions-reset-confirmation-required",
            "Decisions Reset Confirmation Required",
        ),
        ExceptionMapping(DatabaseUnavailableError, 503, "database-unavailable", "Database Unavailable"),
        ExceptionMapping(
            PerformanceSnapshotNotFoundError, 404, "performance-snapshot-not-found", "Performance Snapshot Not Found"
        ),
        ExceptionMapping(ExportSnapshotNotFoundError, 404, "export-snapshot-not-found", "Export Snapshot Not Found"),
        ExceptionMapping(ExportArtifactNotFoundError, 404, "export-artifact-not-found", "Export Artifact Not Found"),
        ExceptionMapping(ResourceNotFoundError, 404, "resource-not-found", "Resource Not Found"),
        ExceptionMapping(PortfolioUnavailableError, 503, "portfolio-unavailable", "Portfolio Unavailable"),
        ExceptionMapping(ExportGenerationError, 400, "export-generation-failed", "Export Generation Failed"),
        ExceptionMapping(CycleBusyError, 409, "cycle-busy", "Cycle Busy"),
        ExceptionMapping(RestartUnavailableError, 501, "restart-unavailable", "Restart Unavailable"),
        ExceptionMapping(APIResourceError, 400, "api-resource-error", "API Resource Error"),
        # Security Errors (P8.2)
        ExceptionMapping(AuthenticationLockedError, 429, "authentication-locked", "Unlock Temporarily Locked"),
        ExceptionMapping(InvalidCredentialsError, 401, "invalid-credentials", "Invalid Credentials"),
        ExceptionMapping(ExpiredTokenError,       401, "expired-token",       "Token Expired"),
        ExceptionMapping(InvalidTokenError,       401, "invalid-token",       "Invalid Token"),
        ExceptionMapping(InvalidAPIKeyError,      401, "invalid-api-key",     "Invalid API Key"),
        ExceptionMapping(SessionRevokedError,     401, "session-revoked",     "Session Revoked"),
        ExceptionMapping(PermissionDeniedError,   403, "permission-denied",   "Permission Denied"),
        ExceptionMapping(AuthenticationError,     401, "unauthorized",        "Unauthorized"),
        ExceptionMapping(SecurityError,           400, "security-error",      "Security Error"),
        # Base ATHENA error catch-all (before generic Exception)
        ExceptionMapping(AthenaError,           500, "internal-error",      "Internal Domain Error"),
        # Standard Python errors
        ExceptionMapping(ValueError,            400, "bad-request",         "Bad Request"),
        ExceptionMapping(KeyError,              500, "internal-error",      "Internal Error"),
        # Final catch-all
        ExceptionMapping(Exception,             500, "unexpected-error",    "Unexpected Internal Error"),
    ]

    def classify(
        self,
        exc: Exception,
        instance: str,
        request_id: str,
        correlation_id: str | None = None,
    ) -> ProblemDetail:
        """Classify exception and produce a Problem Details response.

        Always logs the full exception server-side. Never leaks stack traces to clients.
        """
        mapping = self._find_mapping(exc)

        if mapping.http_status >= 500:
            logger.exception(
                "Unhandled %s on %s [request_id=%s, correlation_id=%s]",
                type(exc).__name__,
                instance,
                request_id,
                correlation_id,
                exc_info=exc,
            )

        return ProblemDetail(
            type=f"{_BASE_TYPE_URI}/{mapping.problem_slug}",
            title=mapping.title,
            status=mapping.http_status,
            detail=str(exc) if str(exc) else mapping.title,
            instance=instance,
            request_id=request_id,
            correlation_id=correlation_id or request_id,
        )

    def _find_mapping(self, exc: Exception) -> ExceptionMapping:
        for mapping in self._registry:
            if isinstance(exc, mapping.exc_type):
                return mapping
        # Unreachable because Exception is the final entry, but satisfies type checker
        return self._registry[-1]

    @classmethod
    def register(cls, mapping: ExceptionMapping, *, prepend: bool = True) -> None:
        """Register a new exception mapping.

        prepend=True inserts before the base AthenaError/Exception catch-alls,
        ensuring more specific types are matched first.
        """
        if prepend:
            # Insert before AthenaError (the base catch-all)
            base_idx = next(
                (i for i, m in enumerate(cls._registry) if m.exc_type is AthenaError),
                len(cls._registry) - 1,
            )
            cls._registry.insert(base_idx, mapping)
        else:
            cls._registry.append(mapping)


# Module-level singleton used by exception handlers in app.py
exception_mapper = AthenaExceptionMapper()
