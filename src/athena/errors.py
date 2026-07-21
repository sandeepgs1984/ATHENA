"""ATHENA error taxonomy (ATHENA-002 §11).

Every failure fails loudly and carries a human-readable reason.
Modules never let exceptions cross boundaries as surprises; the
orchestrator (Phase 3) decides run status from typed failures.
"""

from __future__ import annotations


class AthenaError(Exception):
    """Base class for all ATHENA errors."""


class ConfigError(AthenaError):
    """Invalid, missing, or contradictory configuration. Policy: refuse to start."""


class CalendarError(AthenaError):
    """Calendar data missing or unusable for the requested date. Policy: refuse, name the fix."""


class DataStaleError(AthenaError):
    """Data older than the freshness budget. Policy: degrade loudly, never silently."""


class DataValidationError(AthenaError):
    """Impossible or corrupt market data. Policy: quarantine and report."""


class ProviderError(AthenaError):
    """Market data provider failure (rate limit, auth, outage). Policy: bounded retry, then degrade."""


class ReplayMismatchError(AthenaError):
    """Replay produced different output than the original run. Policy: hard failure, investigate."""


class CorporateActionError(AthenaError):
    """Invalid or implausible corporate action definition. Policy: refuse, name the problem."""


class RepositoryError(AthenaError):
    """Persistence failure (integrity, duplicate, corruption). Policy: fail loudly, name it."""


class WorkflowError(AthenaError):
    """Invalid workflow definition (missing dependency, cycle, duplicate stage). Refuse to run."""


class PortfolioError(AthenaError):
    """Invalid portfolio operation or state constraint violation. Policy: fail loudly."""


class AllocationError(AthenaError):
    """Invalid capital allocation policy, constraint, or state violation. Policy: fail loudly."""


class SizingError(AthenaError):
    """Invalid position sizing policy, price, precision, or constraint violation. Policy: fail loudly."""


class OrderPlanningError(AthenaError):
    """Invalid order planning instruction, price, batching, or constraint violation. Policy: fail loudly."""


class BrokerError(AthenaError):
    """Invalid broker contract, capability violation, or translation failure. Policy: fail loudly."""


class LifecycleError(AthenaError):
    """Invalid order lifecycle transition or state constraint violation. Policy: fail loudly."""


class PortfolioAnalyticsError(AthenaError):
    """Invalid portfolio analytics calculation or constraint violation. Policy: fail loudly."""


class ReportingError(AthenaError):
    """Invalid report generation request or template failure. Policy: fail loudly."""


class DashboardError(AthenaError):
    """Invalid dashboard generation request or section aggregation failure. Policy: fail loudly."""


class ExplainabilityError(AthenaError):
    """Invalid explainability request or rationale derivation failure. Policy: fail loudly."""


class TimelineAuditError(AthenaError):
    """Invalid timeline reconstruction request or causal sequencing failure. Policy: fail loudly."""


class MonitoringError(AthenaError):
    """Invalid operational monitoring evaluation or health check failure. Policy: fail loudly."""












