"""Scheduling Framework engine (M4.7).

Coordinates WHEN ATHENA executes its existing operational pipeline — it
never changes HOW ATHENA analyzes markets.  Two execution paths:

* ``execute()`` — runs the full daily pipeline: scanner → watchlist →
  strategy → analytics, producing an immutable ``ScheduleExecution``
  with cross-references to every upstream artifact.

* ``execute_replay()`` — runs the backtesting engine → analytics,
  producing an immutable ``ScheduleExecution`` with references to the
  backtest run and analytics report.

Determinism: all inputs are immutable, no clock is read for business
decisions (``as_of`` is injected), execution records use a monotonic
clock only for duration measurement, and identical inputs always produce
identical execution records.
"""

from __future__ import annotations

import time as _time
from collections.abc import Callable, Sequence
from datetime import datetime

from athena.analytics import ReportingAnalyticsEngine
from athena.backtest import BacktestingEngine
from athena.backtest.models import ReplayPoint
from athena.config.models import SchedulingConfig
from athena.runtime.models import ExecutionStatus
from athena.scanner import DailyMarketScanner
from athena.scanner.models import PipelineBuilder
from athena.scheduling.models import (
    ExecutionReferences,
    ScheduleDefinition,
    ScheduleExecution,
    ScheduleHistory,
    ScheduleMode,
    ScheduleSummary,
    ScheduledJob,
)
from athena.strategy import StrategyFramework
from athena.watchlist import WatchlistManager
from athena.watchlist.models import WatchlistSnapshot


class SchedulingFramework:
    """Deterministic scheduling coordinator over the completed pipeline."""

    def __init__(
        self,
        scanner: DailyMarketScanner,
        watchlist_manager: WatchlistManager,
        strategy_framework: StrategyFramework,
        backtesting_engine: BacktestingEngine,
        analytics_engine: ReportingAnalyticsEngine,
        config: SchedulingConfig | None = None,
        *,
        clock: Callable[[], float] = _time.monotonic,
    ) -> None:
        self._scanner = scanner
        self._watchlist = watchlist_manager
        self._strategy = strategy_framework
        self._backtester = backtesting_engine
        self._analytics = analytics_engine
        self._config = config or SchedulingConfig()
        self._clock = clock
        self._history = ScheduleHistory()
        self._job_counter = 0
        self._exec_counter = 0

    # --------------------------------------------------------- public API

    def create_job(
        self,
        definition: ScheduleDefinition,
        *,
        scheduled_for: datetime,
    ) -> ScheduledJob:
        """Create a pending job from a definition.

        Raises ``ValueError`` if the definition is disabled.
        """
        if not definition.enabled:
            raise ValueError(
                f"cannot schedule disabled definition '{definition.name}'")
        if scheduled_for.tzinfo is None:
            raise ValueError("scheduled_for must be timezone-aware")
        self._job_counter += 1
        return ScheduledJob(
            job_id=f"job-{self._job_counter:04d}",
            definition_id=definition.definition_id,
            definition_name=definition.name,
            mode=definition.mode,
            scheduled_for=scheduled_for,
        )

    def execute(
        self,
        definition: ScheduleDefinition,
        *,
        as_of: datetime,
        pipeline_builder: PipelineBuilder,
        universe: tuple[str, ...],
        previous_watchlist: WatchlistSnapshot | None = None,
    ) -> ScheduleExecution:
        """Execute a non-replay schedule through the full pipeline.

        Runs: scanner → watchlist → strategy → analytics.
        Returns an immutable ``ScheduleExecution`` referencing every
        upstream artifact.  Failures are caught and recorded — the
        framework never raises from a pipeline error.
        """
        if as_of.tzinfo is None:
            raise ValueError("execute requires timezone-aware as_of")
        if definition.mode is ScheduleMode.REPLAY:
            raise ValueError("use execute_replay for REPLAY schedules")

        job = self.create_job(definition, scheduled_for=as_of)
        start = self._clock()

        try:
            scan_report = self._scanner.scan(
                universe, as_of=as_of, pipeline_builder=pipeline_builder)
            watchlist = self._watchlist.apply(
                scan_report, as_of=as_of, previous=previous_watchlist)
            strategy_execution = self._strategy.execute(
                scan_report, watchlist, as_of=as_of)
            analytics_report = self._analytics.daily_report(
                scan_report, as_of=as_of, watchlist=watchlist,
                strategy_execution=strategy_execution)

            elapsed = self._clock() - start
            execution = self._build_execution(
                job=job, status=ExecutionStatus.COMPLETED, as_of=as_of,
                duration=elapsed, note="pipeline completed",
                references=ExecutionReferences(
                    scan_id=scan_report.scan_id,
                    watchlist_snapshot_id=watchlist.snapshot_id,
                    strategy_execution_id=strategy_execution.execution_id,
                    analytics_report_id=analytics_report.report_id,
                ),
            )
        except Exception as exc:
            elapsed = self._clock() - start
            execution = self._build_execution(
                job=job, status=ExecutionStatus.FAILED, as_of=as_of,
                duration=elapsed, note=f"pipeline failed: {exc}",
                references=ExecutionReferences(),
            )

        if self._config.record_history:
            self._history = self._history.record(execution)
        return execution

    def execute_replay(
        self,
        definition: ScheduleDefinition,
        *,
        as_of: datetime,
        replay_points: Sequence[ReplayPoint],
    ) -> ScheduleExecution:
        """Execute a replay schedule through the backtesting engine.

        Runs: backtester → analytics.
        Returns an immutable ``ScheduleExecution`` referencing the
        backtest run and analytics report.
        """
        if as_of.tzinfo is None:
            raise ValueError("execute_replay requires timezone-aware as_of")

        job = self.create_job(definition, scheduled_for=as_of)
        start = self._clock()

        try:
            run = self._backtester.run(list(replay_points))
            analytics_report = self._analytics.backtest_report(
                run, as_of=as_of)

            elapsed = self._clock() - start
            execution = self._build_execution(
                job=job, status=ExecutionStatus.COMPLETED, as_of=as_of,
                duration=elapsed, note="replay completed",
                references=ExecutionReferences(
                    backtest_run_id=run.run_id,
                    analytics_report_id=analytics_report.report_id,
                ),
            )
        except Exception as exc:
            elapsed = self._clock() - start
            execution = self._build_execution(
                job=job, status=ExecutionStatus.FAILED, as_of=as_of,
                duration=elapsed, note=f"replay failed: {exc}",
                references=ExecutionReferences(),
            )

        if self._config.record_history:
            self._history = self._history.record(execution)
        return execution

    @property
    def history(self) -> ScheduleHistory:
        """The accumulated execution history (immutable snapshot)."""
        return self._history

    def summarize(self) -> ScheduleSummary:
        """Build a summary of all recorded executions."""
        by_mode: dict[str, int] = {}
        by_definition: dict[str, int] = {}
        completed = 0
        failed = 0
        for ex in self._history.executions:
            by_mode[ex.mode.value] = by_mode.get(ex.mode.value, 0) + 1
            key = ex.definition_id
            by_definition[key] = by_definition.get(key, 0) + 1
            if ex.status is ExecutionStatus.COMPLETED:
                completed += 1
            elif ex.status is ExecutionStatus.FAILED:
                failed += 1
        return ScheduleSummary(
            total_executions=len(self._history.executions),
            completed=completed, failed=failed,
            by_mode=by_mode, by_definition=by_definition,
        )

    # --------------------------------------------------------- internals

    def _build_execution(
        self,
        *,
        job: ScheduledJob,
        status: ExecutionStatus,
        as_of: datetime,
        duration: float,
        note: str,
        references: ExecutionReferences,
    ) -> ScheduleExecution:
        self._exec_counter += 1
        return ScheduleExecution(
            execution_id=f"exec-{self._exec_counter:04d}",
            job_id=job.job_id,
            definition_id=job.definition_id,
            definition_name=job.definition_name,
            mode=job.mode,
            status=status,
            as_of=as_of,
            references=references,
            duration_seconds=round(duration, 6),
            note=note,
        )
