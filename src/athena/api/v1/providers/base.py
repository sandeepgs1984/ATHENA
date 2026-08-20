"""Provider protocol interfaces for health and metrics (P8.1).

Services depend only on these protocols, not on concrete implementations.
This allows future integration with Prometheus, OpenTelemetry, or cloud
monitoring without modifying controllers, services, or tests.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Protocol, runtime_checkable

from athena.api.v1.dtos.common import HealthResponse, MetricsResponse

if TYPE_CHECKING:
    from athena.analytics.portfolio.models import PerformanceSnapshot
    from athena.api.v1.dtos import (
        CollectionResult,
        DecisionFilterParams,
        EmptyFilterParams,
        PipelineRunFilterParams,
        QuerySpecification,
        ReportFilterParams,
        SchedulerHistoryFilterParams,
        WorkspaceFilterParams,
    )
    from athena.backtest.models import BacktestRun
    from athena.domain.decision import (
        Decision,
        DecisionJournalEntry,
        DecisionTrace,
        Portfolio,
        TradeOutcome,
    )
    from athena.domain.enums import Timeframe
    from athena.domain.market import Candle
    from athena.domain.run import RunRecord
    from athena.export.models import ExportArtifact, ExportSnapshot
    from athena.orchestration.models import SystemPipelineResult
    from athena.orchestration.schedule_models import PipelineScheduleRun
    from athena.reporting.models import GenericReport
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

    def get_trace(self, decision_id: str) -> DecisionTrace | None:
        ...

    def get_run_detail(self, run_id: str) -> dict[str, object]:
        """Return persisted run detail used to render decision depth."""
        ...

    def save_journal_entry(self, entry: DecisionJournalEntry) -> None:
        """Persist the owner's response to a decision (R-9)."""
        ...

    def get_journal_entry(self, decision_id: str) -> DecisionJournalEntry | None:
        """Most recent journal entry for one decision, or None if never recorded."""
        ...

    def save_trade_outcome(self, outcome: TradeOutcome) -> None:
        """Persist a realized outcome for an accepted decision."""
        ...

    def get_trade_outcome(self, decision_id: str) -> TradeOutcome | None:
        """Most recent realized outcome for one decision, or None if never logged."""
        ...

    def list_journal(self, *, limit: int = 500) -> list[DecisionJournalEntry]:
        """All journal entries, newest first — for rollups (AUX-5) rather
        than a single decision's response."""
        ...

    def list_trade_outcomes(self, *, limit: int = 500) -> list[TradeOutcome]:
        """All realized outcomes, newest first — for rollups (AUX-5) rather
        than a single decision's outcome."""
        ...

    def list_recent_decisions(self, *, limit: int = 500) -> list[Decision]:
        """Most recent decisions, newest first, unfiltered — for read-only
        analytical queries (e.g. historical analog matching) that need a raw
        pool rather than a paginated/filtered API listing."""
        ...

    def reset_decisions_data(self) -> dict[str, int]:
        """Owner-triggered full wipe of decisions, traces, journal entries,
        and realized outcomes. Returns per-table deleted row counts."""
        ...


@runtime_checkable
class CandleHistoryProvider(Protocol):
    """Read-only, provider-independent access to persisted market candles."""

    def list_recent_candles(
        self,
        instrument_id: str,
        timeframe: Timeframe,
        *,
        limit: int,
    ) -> list[Candle]:
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
class CycleRunHistoryProvider(Protocol):
    """Read-only access to persisted runtime cycle provenance."""

    def list_runs(
        self, *, trigger: str | None = None, limit: int = 100
    ) -> list[RunRecord]:
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


@runtime_checkable
class ReportProvider(Protocol):
    """Abstract provider for generated generic reports."""

    def get_reports(
        self, spec: QuerySpecification[ReportFilterParams]
    ) -> CollectionResult[GenericReport]:
        ...

    def get_report(self, report_id: str) -> GenericReport | None:
        ...


@runtime_checkable
class PerformanceAnalyticsProvider(Protocol):
    """Abstract provider for portfolio performance snapshots."""

    def get_snapshots(
        self, spec: QuerySpecification[EmptyFilterParams]
    ) -> CollectionResult[PerformanceSnapshot]:
        ...

    def get_snapshot(self, snapshot_id: str) -> PerformanceSnapshot | None:
        ...


@runtime_checkable
class ExportQueryProvider(Protocol):
    """Abstract provider for querying exported artifacts history."""

    def get_snapshots(
        self, spec: QuerySpecification[EmptyFilterParams]
    ) -> CollectionResult[ExportSnapshot]:
        ...

    def get_snapshot(self, snapshot_id: str) -> ExportSnapshot | None:
        ...

    def get_artifact(self, export_id: str) -> ExportArtifact | None:
        ...


@runtime_checkable
class ExportGenerationProvider(Protocol):
    """Abstract provider responsible for executing and saving exports."""

    def save_snapshot(self, snapshot: ExportSnapshot) -> None:
        ...


@runtime_checkable
class BacktestRunProvider(Protocol):
    """Abstract provider for querying backtest execution history."""

    def get_runs(
        self, spec: QuerySpecification[EmptyFilterParams]
    ) -> CollectionResult[BacktestRun]:
        ...

    def get_run(self, run_id: str) -> BacktestRun | None:
        ...
