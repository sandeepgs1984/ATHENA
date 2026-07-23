"""In-memory default provider implementations (P8.3).

Exposes mock/seeded datasets for development and testing. Filtering, sorting, and
pagination logic are executed using pure-Python collection query evaluation.
"""

from __future__ import annotations

import contextlib
from collections.abc import Callable
from datetime import datetime, timezone
from decimal import Decimal
from typing import Any, TypeVar

from athena.analytics.portfolio.models import (
    AnalyticsSummary,
    PerformanceSnapshot,
    PortfolioAnalyticsReferences,
    PortfolioPerformance,
    TradePerformance,
)
from athena.api.v1.dtos import (
    CollectionResult,
    EmptyFilterParams,
    QuerySpecification,
    ReportFilterParams,
)
from athena.api.v1.providers.base import (
    BacktestRunProvider,
    ExportGenerationProvider,
    ExportQueryProvider,
    PerformanceAnalyticsProvider,
    ReportProvider,
)
from athena.backtest.models import (
    BacktestRun,
    BacktestSession,
    BacktestStep,
    BacktestSummary,
    StrategyPerformance,
)
from athena.config.models import ExportFormat, ReportType
from athena.domain.decision import Decision, GateResult, Portfolio, Position
from athena.domain.enums import DecisionType, Direction, QualityGate
from athena.export.models import (
    ExportArtifact,
    ExportReferences,
    ExportSnapshot,
    ExportSummary,
)
from athena.orchestration.models import (
    PipelineContext,
    PipelineMetadata,
    PipelineResult,
    PipelineStatus,
    StageResult,
    StageStatus,
    SystemPipelineResult,
)
from athena.orchestration.schedule_models import PipelineScheduleRun
from athena.reporting.models import GenericReport, ReportingReferences
from athena.runtime.models import ExecutionStatus
from athena.workspace.models import WorkspaceSnapshot, WorkspaceSummary

T = TypeVar("T")
F = TypeVar("F")


def apply_query_spec(
    items: list[T],
    spec: QuerySpecification[Any],
    filter_func: Callable[[T], bool],
    sort_key_func: Callable[[T], Any] | None = None,
) -> CollectionResult[T]:
    """Generic helper evaluating QuerySpecification constraints against a list."""
    # 1. Apply filtering
    filtered_items = [x for x in items if filter_func(x)]

    # 2. Apply sorting
    if spec.sort.sort_by and sort_key_func:
        reverse = spec.sort.sort_dir == "desc"
        with contextlib.suppress(Exception):
            filtered_items = sorted(
                filtered_items, key=sort_key_func, reverse=reverse
            )

    # 3. Apply pagination
    total = len(filtered_items)
    start = (spec.pagination.page - 1) * spec.pagination.page_size
    end = start + spec.pagination.page_size
    sliced = filtered_items[start:end]

    return CollectionResult(
        items=tuple(sliced),
        total_count=total,
        page=spec.pagination.page,
        page_size=spec.pagination.page_size,
    )


class InMemoryDecisionProvider:
    """In-memory provider for Decisions."""

    def __init__(self) -> None:
        self.decisions: list[Decision] = []

    def get_decisions(
        self, spec: QuerySpecification[Any]
    ) -> CollectionResult[Decision]:
        def filter_func(d: Decision) -> bool:
            f = spec.filters
            if f.instrument_id and d.instrument_id != f.instrument_id:
                return False
            if f.decision_type and d.decision_type != f.decision_type:
                return False
            if f.direction and d.direction != f.direction:
                return False
            if f.from_date and d.ts < f.from_date:
                return False
            return not (f.to_date and d.ts > f.to_date)

        def sort_func(d: Decision) -> Any:
            sort_by = spec.sort.sort_by
            if sort_by == "ts":
                return d.ts
            if sort_by == "instrument_id":
                return d.instrument_id or ""
            return d.decision_id

        return apply_query_spec(self.decisions, spec, filter_func, sort_func)

    def get_decision(self, decision_id: str) -> Decision | None:
        for d in self.decisions:
            if d.decision_id == decision_id:
                return d
        return None


class InMemoryPortfolioProvider:
    """In-memory provider for Portfolio."""

    def __init__(self) -> None:
        self.portfolio: Portfolio | None = None

    def get_portfolio(self) -> Portfolio | None:
        return self.portfolio


class InMemoryPipelineRunProvider:
    """In-memory provider for Pipeline runs."""

    def __init__(self) -> None:
        self.runs: list[SystemPipelineResult] = []

    def get_runs(
        self, spec: QuerySpecification[Any]
    ) -> CollectionResult[SystemPipelineResult]:
        def filter_func(r: SystemPipelineResult) -> bool:
            f = spec.filters
            if f.overall_status and r.overall_status != f.overall_status:
                return False
            if f.from_date and r.as_of < f.from_date:
                return False
            return not (f.to_date and r.as_of > f.to_date)

        def sort_func(r: SystemPipelineResult) -> Any:
            if spec.sort.sort_by == "as_of":
                return r.as_of
            return r.run_id

        return apply_query_spec(self.runs, spec, filter_func, sort_func)

    def get_run(self, run_id: str) -> SystemPipelineResult | None:
        for r in self.runs:
            if r.run_id == run_id:
                return r
        return None


class InMemorySchedulerHistoryProvider:
    """In-memory provider for Scheduler executions."""

    def __init__(self) -> None:
        self.runs: list[PipelineScheduleRun] = []

    def get_history(
        self, spec: QuerySpecification[Any]
    ) -> CollectionResult[PipelineScheduleRun]:
        def filter_func(r: PipelineScheduleRun) -> bool:
            f = spec.filters
            if f.job_id and r.job_id != f.job_id:
                return False
            if (
                f.overall_status
                and r.system_result.overall_status != f.overall_status
            ):
                return False
            if f.from_date and r.system_result.as_of < f.from_date:
                return False
            return not (f.to_date and r.system_result.as_of > f.to_date)

        def sort_func(r: PipelineScheduleRun) -> Any:
            if spec.sort.sort_by == "as_of":
                return r.system_result.as_of
            return r.schedule_run_id

        return apply_query_spec(self.runs, spec, filter_func, sort_func)

    def get_run(self, schedule_run_id: str) -> PipelineScheduleRun | None:
        for r in self.runs:
            if r.schedule_run_id == schedule_run_id:
                return r
        return None


class InMemoryWorkspaceProvider:
    """In-memory provider for Workspace snapshots."""

    def __init__(self) -> None:
        self.snapshots: list[WorkspaceSnapshot] = []

    def get_snapshots(
        self, spec: QuerySpecification[Any]
    ) -> CollectionResult[WorkspaceSnapshot]:
        def filter_func(s: WorkspaceSnapshot) -> bool:
            f = spec.filters
            if f.overall_health and s.summary.overall_health != f.overall_health:
                return False
            if f.from_date and s.as_of < f.from_date:
                return False
            return not (f.to_date and s.as_of > f.to_date)

        def sort_func(s: WorkspaceSnapshot) -> Any:
            if spec.sort.sort_by == "as_of":
                return s.as_of
            return s.snapshot_id

        return apply_query_spec(self.snapshots, spec, filter_func, sort_func)

    def get_snapshot(self, snapshot_id: str) -> WorkspaceSnapshot | None:
        for s in self.snapshots:
            if s.snapshot_id == snapshot_id:
                return s
        return None

class InMemoryReportProvider(ReportProvider):
    """In-memory GenericReport provider."""

    def __init__(self) -> None:
        self.reports: list[GenericReport] = []

    def get_reports(
        self, spec: QuerySpecification[ReportFilterParams]
    ) -> CollectionResult[GenericReport]:
        def filter_func(r: GenericReport) -> bool:
            return not (spec.filters.report_type and r.report_type != spec.filters.report_type)

        def sort_func(r: GenericReport) -> Any:
            if spec.sort.sort_by == "as_of":
                return r.as_of
            return r.report_id

        return apply_query_spec(self.reports, spec, filter_func, sort_func)

    def get_report(self, report_id: str) -> GenericReport | None:
        for r in self.reports:
            if r.report_id == report_id:
                return r
        return None


class InMemoryPerformanceAnalyticsProvider(PerformanceAnalyticsProvider):
    """In-memory PerformanceSnapshot provider."""

    def __init__(self) -> None:
        self.snapshots: list[PerformanceSnapshot] = []

    def get_snapshots(
        self, spec: QuerySpecification[EmptyFilterParams]
    ) -> CollectionResult[PerformanceSnapshot]:
        def filter_func(s: PerformanceSnapshot) -> bool:
            return True

        def sort_func(s: PerformanceSnapshot) -> Any:
            if spec.sort.sort_by == "as_of":
                return s.as_of
            return s.snapshot_id

        return apply_query_spec(self.snapshots, spec, filter_func, sort_func)

    def get_snapshot(self, snapshot_id: str) -> PerformanceSnapshot | None:
        for s in self.snapshots:
            if s.snapshot_id == snapshot_id:
                return s
        return None


class InMemoryExportProvider(ExportQueryProvider, ExportGenerationProvider):
    """In-memory Export snapshot and artifact provider implementing both query and command roles."""

    def __init__(self) -> None:
        self.snapshots: list[ExportSnapshot] = []

    def get_snapshots(
        self, spec: QuerySpecification[EmptyFilterParams]
    ) -> CollectionResult[ExportSnapshot]:
        def filter_func(s: ExportSnapshot) -> bool:
            return True

        def sort_func(s: ExportSnapshot) -> Any:
            if spec.sort.sort_by == "as_of":
                return s.as_of
            return s.snapshot_id

        return apply_query_spec(self.snapshots, spec, filter_func, sort_func)

    def get_snapshot(self, snapshot_id: str) -> ExportSnapshot | None:
        for s in self.snapshots:
            if s.snapshot_id == snapshot_id:
                return s
        return None

    def get_artifact(self, export_id: str) -> ExportArtifact | None:
        for s in self.snapshots:
            for e in s.exports:
                if e.export_id == export_id:
                    return e
        return None

    def save_snapshot(self, snapshot: ExportSnapshot) -> None:
        self.snapshots.append(snapshot)


class InMemoryBacktestRunProvider(BacktestRunProvider):
    """In-memory provider for backtest runs (P9.5)."""

    def __init__(self) -> None:
        self.runs: list[BacktestRun] = []

    def get_runs(
        self, spec: QuerySpecification[EmptyFilterParams]
    ) -> CollectionResult[BacktestRun]:
        def filter_func(r: BacktestRun) -> bool:
            return True

        def sort_func(r: BacktestRun) -> Any:
            return r.run_id

        return apply_query_spec(self.runs, spec, filter_func, sort_func)

    def get_run(self, run_id: str) -> BacktestRun | None:
        for r in self.runs:
            if r.run_id == run_id:
                return r
        return None


# ---------------------------------------------------------------------------
# Default Sample Data Seed Functions (P8.3 scaffolding)
# ---------------------------------------------------------------------------

def seed_sample_data(
    decision_prov: InMemoryDecisionProvider,
    portfolio_prov: InMemoryPortfolioProvider,
    pipeline_prov: InMemoryPipelineRunProvider,
    scheduler_prov: InMemorySchedulerHistoryProvider,
    workspace_prov: InMemoryWorkspaceProvider,
    report_prov: InMemoryReportProvider,
    analytics_prov: InMemoryPerformanceAnalyticsProvider,
    export_prov: InMemoryExportProvider,
    backtest_prov: InMemoryBacktestRunProvider,
) -> None:
    """Seeds in-memory providers with compliant sample data for Swagger/CLI usage."""
    now = datetime.now(tz=timezone.utc)

    # 1. Seed Decisions
    dec = Decision(
        decision_id="dec-sample-1",
        ts=now,
        run_id="run-sample-1",
        cycle_id="cycle-sample-1",
        instrument_id="SBIN",
        direction=Direction.LONG,
        decision_type=DecisionType.WATCH,
        explanation="Bullish crossover with strong score support",
        score_ref="score-sample-1",
        confidence_ref="conf-sample-1",
        risk_ref="risk-sample-1",
        gate_results=(
            GateResult(gate=QualityGate.DATA, passed=True, detail="Daily volume ok"),
        ),
        trade_plan=None,
    )
    decision_prov.decisions.append(dec)

    # 2. Seed Portfolio
    pos = Position(
        position_id="pos-sample-1",
        instrument_id="SBIN",
        opened_ts=now,
        quantity=100,
        avg_price=Decimal("750.50"),
    )
    port = Portfolio(
        ts=now,
        positions=(pos,),
        cash=Decimal("50000.00"),
        exposure_by_sector={"Financials": Decimal("75050.00")},
    )
    portfolio_prov.portfolio = port

    # 3. Seed Workspace Snapshot
    summary = WorkspaceSummary(
        total_entries=1,
        artifact_counts={"report": 1},
        overall_health="HEALTHY",
    )
    ws_snap = WorkspaceSnapshot(
        snapshot_id="ws-sample-1",
        as_of=now,
        summary=summary,
        entries=(),
        references=None,
    )
    workspace_prov.snapshots.append(ws_snap)

    # 4. Seed Generic Report
    report = GenericReport(
        report_id="rep-sample-1",
        report_type=ReportType.PORTFOLIO,
        title="Sample Portfolio Status Report",
        as_of=now,
        content={"cash": "50000.00", "positions_count": 1},
        text_summary="Sample Portfolio Status Report: Cash 50000.00, Positions 1",
        references=ReportingReferences(portfolio_snapshot_id="ws-sample-1"),
    )
    report_prov.reports.append(report)

    # 5. Seed Performance Snapshot
    trade_perf = TradePerformance(
        trade_id="trd-sample-1",
        instrument_id="SBIN",
        direction=Direction.LONG,
        entry_price=Decimal("700.00"),
        exit_price=Decimal("750.00"),
        quantity=Decimal("100"),
        realized_pnl=Decimal("5000.00"),
        return_pct=Decimal("7.14"),
        holding_period_days=5.0,
        is_win=True,
        is_loss=False,
        as_of=now,
        references=PortfolioAnalyticsReferences(decision_id="dec-sample-1"),
    )
    port_perf = PortfolioPerformance(
        as_of=now,
        realized_pnl=Decimal("5000.00"),
        unrealized_pnl=Decimal("0.00"),
        total_pnl=Decimal("5000.00"),
        total_return_pct=Decimal("10.0"),
        portfolio_value=Decimal("55000.00"),
        peak_portfolio_value=Decimal("55000.00"),
        drawdown=Decimal("0.00"),
        drawdown_pct=Decimal("0.00"),
        max_drawdown_pct=Decimal("0.00"),
        gross_exposure=Decimal("0.00"),
        net_exposure=Decimal("0.00"),
        cash_utilization_pct=Decimal("0.00"),
    )
    summary_perf = AnalyticsSummary(
        as_of=now,
        total_trades=1,
        winning_trades=1,
        losing_trades=0,
        win_rate_pct=Decimal("100.0"),
        avg_gain=Decimal("5000.00"),
        avg_loss=Decimal("0.00"),
        win_loss_ratio=Decimal("1.0"),
        avg_holding_period_days=5.0,
        max_drawdown_pct=Decimal("0.00"),
    )
    analytics_snap = PerformanceSnapshot(
        snapshot_id="perfsnap-sample-1",
        as_of=now,
        portfolio_performance=port_perf,
        trade_performances=(trade_perf,),
        summary=summary_perf,
        references=PortfolioAnalyticsReferences(portfolio_snapshot_id="ws-sample-1"),
    )
    analytics_prov.snapshots.append(analytics_snap)

    # 6. Seed Export Snapshot
    export_art = ExportArtifact(
        export_id="exp-sample-1",
        format=ExportFormat.JSON,
        filename="report_rep-sample-1.json",
        content_type="application/json",
        payload='{"report_id": "rep-sample-1", "title": "Sample Portfolio Status Report"}',
        as_of=now,
        references=ExportReferences(report_id="rep-sample-1"),
    )
    export_sum = ExportSummary(
        total_exports=1,
        formats_used=(ExportFormat.JSON,),
        total_bytes=len(export_art.payload.encode("utf-8")),
    )
    export_snap = ExportSnapshot(
        snapshot_id="expsnap-sample-1",
        as_of=now,
        exports=(export_art,),
        summary=export_sum,
        references=ExportReferences(report_id="rep-sample-1"),
    )
    export_prov.snapshots.append(export_snap)

    # 7. Seed System Pipeline Run (incorporating regime and universe trace results)
    final_ctx = PipelineContext(
        run_id="run-sample-1",
        as_of=now,
        data={
            "regime_assessment": {
                "trend": "BULL_TREND",
                "volatility": "LOW_VOLATILITY",
                "gap": "NO_GAP",
                "market_health": 85,
                "sector_health": {
                    "Financials": 90,
                    "Technology": 75,
                    "Energy": 80,
                },
                "explanation": "Strong index price action supported by high breadth and low VIX readings.",
            },
            "universe_members": {
                "SBIN": {
                    "symbol": "SBIN",
                    "included": True,
                    "trace": [
                        "Daily volume is 1.5x of 20-day average (PASS)",
                        "RSI is in bullish zone (PASS)",
                        "Price is above 50-day EMA (PASS)",
                    ],
                },
                "RELIANCE": {
                    "symbol": "RELIANCE",
                    "included": True,
                    "trace": [
                        "Daily volume is 1.2x of 20-day average (PASS)",
                        "Trend classification is positive (PASS)",
                        "Close is near daily high (PASS)",
                    ],
                },
                "TCS": {
                    "symbol": "TCS",
                    "included": True,
                    "trace": [
                        "Daily volume is 0.8x of 20-day average (PASS)",
                        "RSI is in neutral zone (PASS)",
                        "Excludes from high-momentum watchlist (FAIL)",
                    ],
                },
            },
        },
    )

    sys_run = SystemPipelineResult(
        run_id="run-sample-1",
        as_of=now,
        pipeline_runs=(
            PipelineResult(
                pipeline_run_id="run-sample-1-exec",
                metadata=PipelineMetadata(
                    definition_id="exec-pipeline",
                    version="1.0",
                    name="Execution Pipeline",
                    description="Processes decisions and prepares executions",
                ),
                as_of=now,
                stages=(
                    StageResult(
                        stage_id="stage_portfolio_snapshot",
                        status=StageStatus.SUCCESS,
                        message="Portfolio snapshot loaded successfully",
                        output_key="portfolio_snapshot",
                    ),
                ),
                overall_status=PipelineStatus.SUCCESS,
                final_context=final_ctx,
            ),
        ),
        workspace_snapshot=ws_snap,
        overall_status=PipelineStatus.SUCCESS,
        final_context=final_ctx,
    )
    pipeline_prov.runs.append(sys_run)

    # 8. Seed Backtest Run
    from datetime import date, timedelta
    first_date = now.date() - timedelta(days=10)
    last_date = now.date()

    bt_steps = []
    for i in range(10):
        step_date = first_date + timedelta(days=i)
        step_as_of = datetime.combine(step_date, datetime.min.time(), tzinfo=timezone.utc)
        bt_steps.append(
            BacktestStep(
                replay_date=step_date,
                as_of=step_as_of,
                status=ExecutionStatus.COMPLETED,
                scan_report=None,
                watchlist=None,
                strategy_execution=None,
                note=f"Successful replay for date {step_date.isoformat()}",
            )
        )

    perf_mom = StrategyPerformance(
        strategy="momentum",
        total_matches=15,
        steps_with_matches=8,
        instruments=("SBIN", "RELIANCE", "TCS"),
    )
    perf_swg = StrategyPerformance(
        strategy="swing",
        total_matches=22,
        steps_with_matches=10,
        instruments=("SBIN", "RELIANCE", "TCS", "INFY", "LT"),
    )
    perf_brk = StrategyPerformance(
        strategy="breakout",
        total_matches=8,
        steps_with_matches=5,
        instruments=("RELIANCE", "LT"),
    )
    perf_rev = StrategyPerformance(
        strategy="mean_reversion",
        total_matches=4,
        steps_with_matches=3,
        instruments=("TCS", "INFY"),
    )
    perf_rot = StrategyPerformance(
        strategy="sector_rotation",
        total_matches=12,
        steps_with_matches=7,
        instruments=("SBIN", "RELIANCE"),
    )

    bt_summary = BacktestSummary(
        total_steps=10,
        completed_steps=10,
        failed_steps=0,
        performance=(perf_mom, perf_swg, perf_brk, perf_rev, perf_rot),
    )

    bt_session = BacktestSession(
        session_id="session-bt-sample-1",
        steps=tuple(bt_steps),
        summary=bt_summary,
    )

    bt_run = BacktestRun(
        run_id="bt-sample-1",
        first_replay_date=first_date,
        last_replay_date=last_date,
        session=bt_session,
        meta={"profile": "swing_trading_default", "reproduced_by": "Administrator"},
    )
    backtest_prov.runs.append(bt_run)
