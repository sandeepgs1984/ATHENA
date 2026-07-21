"""Reporting & Analytics Engine (M4.6).

Answers questions like "What happened today?", "How many instruments matched
each strategy?", and "What operational activity occurred during replay?" purely
by aggregating ATHENA's completed artifacts — the Daily Market Scanner (M4.2),
Watchlist Manager (M4.3), Strategy Framework (M4.4), and Backtesting Engine
(M4.5) outputs.

It is PRESENTATION + AGGREGATION ONLY: it never invokes an analytical engine,
never derives new market intelligence, and never modifies a completed decision.
Every metric is a count or roll-up of an existing immutable artifact, and every
report preserves references back to its sources.

Determinism: all inputs are immutable, no clock is read (``as_of`` is injected),
and distributions are built in a fixed, config-driven order — so identical
inputs always produce an identical report.
"""

from __future__ import annotations

from collections.abc import Mapping
from datetime import datetime

from athena.analytics.models import (
    AnalyticsReport,
    AnalyticsSummary,
    BacktestAnalytics,
    DailyAnalytics,
    StrategyAnalytics,
    WatchlistAnalytics,
)
from athena.backtest.models import BacktestRun
from athena.config.models import AnalyticsConfig
from athena.runtime.models import ExecutionStatus
from athena.scanner.models import DailyScanReport
from athena.strategy.models import StrategyExecution
from athena.watchlist.models import WatchlistSnapshot

_UNKNOWN = "UNKNOWN"


class ReportingAnalyticsEngine:
    """Deterministic, aggregation-only reporting over completed artifacts."""

    def __init__(self, config: AnalyticsConfig | None = None) -> None:
        self._config = config or AnalyticsConfig()

    # ------------------------------------------------------------- daily

    def daily_report(
        self,
        scan_report: DailyScanReport,
        *,
        as_of: datetime,
        watchlist: WatchlistSnapshot | None = None,
        strategy_execution: StrategyExecution | None = None,
    ) -> AnalyticsReport:
        """Build a 'daily' analytics report for one scan cycle."""
        if as_of.tzinfo is None:
            raise ValueError("daily_report requires timezone-aware as_of")

        daily = self.daily_analytics(scan_report, as_of=as_of, watchlist=watchlist,
                                     strategy_execution=strategy_execution)
        references = {"scan_id": scan_report.scan_id}
        if watchlist is not None:
            references["watchlist_snapshot_id"] = watchlist.snapshot_id
        if strategy_execution is not None:
            references["strategy_execution_id"] = strategy_execution.execution_id

        totals = {
            "instruments_scanned": daily.instruments_scanned,
            "successful": daily.successful, "failed": daily.failed,
            "skipped": daily.skipped,
            "watchlist_entries": daily.watchlist.total_entries if daily.watchlist else 0,
            "strategy_matches": daily.strategy.total_matches if daily.strategy else 0,
        }
        return AnalyticsReport(
            report_id=f"analytics-daily-{scan_report.scan_id}", kind="daily", as_of=as_of,
            summary=AnalyticsSummary(kind="daily", totals=totals), references=references,
            daily=daily)

    def daily_analytics(
        self,
        scan_report: DailyScanReport,
        *,
        as_of: datetime,
        watchlist: WatchlistSnapshot | None = None,
        strategy_execution: StrategyExecution | None = None,
    ) -> DailyAnalytics:
        stats = scan_report.statistics
        return DailyAnalytics(
            scan_id=scan_report.scan_id, as_of=as_of,
            instruments_scanned=stats.total, successful=stats.successful,
            failed=stats.failed, skipped=stats.skipped,
            decision_distribution=dict(scan_report.summary.decision_counts),
            confidence_distribution=self._level_distribution(
                scan_report, "confidence", self._config.confidence_levels),
            risk_distribution=self._level_distribution(
                scan_report, "risk", self._config.risk_levels),
            watchlist=self.watchlist_analytics(watchlist) if watchlist else None,
            strategy=self.strategy_analytics(strategy_execution) if strategy_execution else None)

    @staticmethod
    def watchlist_analytics(snapshot: WatchlistSnapshot) -> WatchlistAnalytics:
        return WatchlistAnalytics(
            snapshot_id=snapshot.snapshot_id, scan_id=snapshot.scan_id,
            total_entries=len(snapshot.entries), counts=dict(snapshot.summary.counts),
            added=snapshot.summary.added, retained=snapshot.summary.retained,
            removed=snapshot.summary.removed)

    @staticmethod
    def strategy_analytics(execution: StrategyExecution) -> StrategyAnalytics:
        return StrategyAnalytics(
            execution_id=execution.execution_id, scan_id=execution.scan_id,
            watchlist_snapshot_id=execution.watchlist_snapshot_id,
            match_counts=dict(execution.summary.match_counts),
            total_matches=execution.summary.total_matches,
            instruments_matched=execution.summary.instruments_matched,
            overlapping_instruments=execution.summary.overlapping_instruments)

    # ------------------------------------------------------------- replay

    def backtest_report(self, run: BacktestRun, *, as_of: datetime) -> AnalyticsReport:
        """Build a 'replay' analytics report for one BacktestRun."""
        if as_of.tzinfo is None:
            raise ValueError("backtest_report requires timezone-aware as_of")

        analytics = self.backtest_analytics(run)
        references = {"run_id": run.run_id, "session_id": run.session.session_id}
        totals = {
            "total_steps": analytics.total_steps,
            "completed_steps": analytics.completed_steps,
            "failed_steps": analytics.failed_steps,
            "total_strategy_matches": sum(analytics.strategy_match_counts.values()),
        }
        return AnalyticsReport(
            report_id=f"analytics-replay-{run.run_id}", kind="replay", as_of=as_of,
            summary=AnalyticsSummary(kind="replay", totals=totals), references=references,
            backtest=analytics)

    def backtest_analytics(self, run: BacktestRun) -> BacktestAnalytics:
        decisions: dict[str, int] = {}
        for step in run.steps:
            if step.scan_report is None:
                continue
            for dtype, count in step.scan_report.summary.decision_counts.items():
                decisions[dtype] = decisions.get(dtype, 0) + count

        match_counts = {p.strategy: p.total_matches for p in run.summary.performance}
        instruments = {p.strategy: p.distinct_instruments for p in run.summary.performance}
        return BacktestAnalytics(
            run_id=run.run_id, session_id=run.session.session_id,
            first_replay_date=(run.first_replay_date.isoformat()
                               if run.first_replay_date else None),
            last_replay_date=(run.last_replay_date.isoformat()
                              if run.last_replay_date else None),
            total_steps=run.summary.total_steps,
            completed_steps=run.summary.completed_steps,
            failed_steps=run.summary.failed_steps,
            decision_distribution=decisions,
            strategy_match_counts=match_counts,
            strategy_instruments=instruments)

    # ------------------------------------------------------------- internals

    def _level_distribution(
        self,
        scan_report: DailyScanReport,
        section: str,
        level_order: list[str],
    ) -> dict[str, int]:
        raw: dict[str, int] = {}
        for result in scan_report.results:
            if result.status is not ExecutionStatus.COMPLETED or result.report is None:
                continue
            block = result.report.machine.get(section)
            level = block.get("level") if isinstance(block, Mapping) else None
            key = str(level) if level else _UNKNOWN
            raw[key] = raw.get(key, 0) + 1

        if not self._config.include_unknown:
            raw.pop(_UNKNOWN, None)

        ordered: dict[str, int] = {}
        for level in level_order:
            if level in raw:
                ordered[level] = raw[level]
        for level in sorted(raw):
            if level not in ordered:
                ordered[level] = raw[level]
        return ordered
