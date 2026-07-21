"""Provider protocol interfaces for health and metrics (P8.1).

Services depend only on these protocols, not on concrete implementations.
This allows future integration with Prometheus, OpenTelemetry, or cloud
monitoring without modifying controllers, services, or tests.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Protocol, runtime_checkable

from athena.api.v1.dtos.common import HealthResponse, MetricsResponse

if TYPE_CHECKING:
    from athena.api.v1.dtos import (
        CollectionResult,
        DecisionFilterParams,
        PipelineRunFilterParams,
        QuerySpecification,
        SchedulerHistoryFilterParams,
        WorkspaceFilterParams,
    )
    from athena.domain.decision import Decision, Portfolio
    from athena.orchestration.models import SystemPipelineResult
    from athena.orchestration.schedule_models import PipelineScheduleRun
    from athena.workspace.models import WorkspaceSnapshot


@runtime_checkable
class HealthProvider(Protocol):
    """Abstract health information provider.

    Default implementation: ObservabilityHealthProvider.
    Future: PrometheusHealthProvider, OpenTelemetryHealthProvider, etc.
    """

    def get_health(self) -> HealthResponse:
        ...


@runtime_checkable
class MetricsProvider(Protocol):
    """Abstract metrics information provider.

    Default implementation returns scaffold values (P8.1 scope).
    Future: aggregated from PipelineHistory, ScheduleHistory, observability platform.
    """

    def get_metrics(self) -> MetricsResponse:
        ...


@runtime_checkable
class DecisionProvider(Protocol):
    """Abstract provider for trade decisions."""

    def get_decisions(
        self, spec: QuerySpecification[DecisionFilterParams]
    ) -> CollectionResult[Decision]:
        ...

    def get_decision(self, decision_id: str) -> Decision | None:
        ...


@runtime_checkable
class PortfolioProvider(Protocol):
    """Abstract provider for portfolio exposure and positions."""

    def get_portfolio(self) -> Portfolio | None:
        ...


@runtime_checkable
class PipelineRunProvider(Protocol):
    """Abstract provider for pipeline run logs."""

    def get_runs(
        self, spec: QuerySpecification[PipelineRunFilterParams]
    ) -> CollectionResult[SystemPipelineResult]:
        ...

    def get_run(self, run_id: str) -> SystemPipelineResult | None:
        ...


@runtime_checkable
class SchedulerHistoryProvider(Protocol):
    """Abstract provider for scheduled run histories."""

    def get_history(
        self, spec: QuerySpecification[SchedulerHistoryFilterParams]
    ) -> CollectionResult[PipelineScheduleRun]:
        ...

    def get_run(self, schedule_run_id: str) -> PipelineScheduleRun | None:
        ...


@runtime_checkable
class WorkspaceProvider(Protocol):
    """Abstract provider for unified workspace snapshot catalog."""

    def get_snapshots(
        self, spec: QuerySpecification[WorkspaceFilterParams]
    ) -> CollectionResult[WorkspaceSnapshot]:
        ...

    def get_snapshot(self, snapshot_id: str) -> WorkspaceSnapshot | None:
        ...
