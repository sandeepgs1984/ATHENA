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
from dataclasses import dataclass, field
from typing import ClassVar

from athena.api.security.exceptions import (
    AuthenticationError,
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

logger = logging.getLogger(__name__)

_BASE_TYPE_URI = "https://athena.internal/errors"


@dataclass(frozen=True, slots=True)
class ProblemDetail:
    """RFC 9457 Problem Details for HTTP APIs.

    Never leaks internal stack traces. All 500 responses are logged server-side.
    """

    type: str
    title: str
    status: int
    detail: str
    instance: str
    request_id: str
    extensions: dict[str, object] = field(default_factory=dict)

    def to_dict(self) -> dict[str, object]:
        base: dict[str, object] = {
            "type": self.type,
            "title": self.title,
            "status": self.status,
            "detail": self.detail,
            "instance": self.instance,
            "request_id": self.request_id,
        }
        base.update(self.extensions)
        return base


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
        # Security Errors (P8.2)
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
    ) -> ProblemDetail:
        """Classify exception and produce a Problem Details response.

        Always logs the full exception server-side. Never leaks stack traces to clients.
        """
        mapping = self._find_mapping(exc)

        if mapping.http_status >= 500:
            logger.exception(
                "Unhandled %s on %s [request_id=%s]",
                type(exc).__name__, instance, request_id,
                exc_info=exc,
            )

        return ProblemDetail(
            type=f"{_BASE_TYPE_URI}/{mapping.problem_slug}",
            title=mapping.title,
            status=mapping.http_status,
            detail=str(exc) if str(exc) else mapping.title,
            instance=instance,
            request_id=request_id,
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
