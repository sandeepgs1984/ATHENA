"""Backtesting Engine (M4.5).

Answers one question: "How would ATHENA's completed analytical pipeline and
strategy framework have behaved across historical market snapshots?" It replays
a chronological sequence of :class:`ReplayPoint`s through the *existing*
operational components — the Daily Market Scanner (M4.2), Watchlist Manager
(M4.3), and Strategy Framework (M4.4), which themselves run the Workflow Engine
(M4.1) and analytical core — and records the immutable artifacts each produced.

It ORCHESTRATES ONLY: it introduces no alternate analytical logic, computes no
market values, and replays the same deterministic pipeline used live. The
analytical core remains the single source of truth.

Determinism: replay points run in strict chronological order; watchlist state
threads forward (per config); no clock is read (each point's ``as_of`` is
injected). The same historical dataset therefore yields an identical
:class:`BacktestRun` on every run.
"""

from __future__ import annotations

from collections.abc import Sequence

from athena.backtest.models import (
    BacktestRun,
    BacktestSession,
    BacktestStep,
    BacktestSummary,
    ReplayPoint,
    StrategyPerformance,
)
from athena.config.models import BacktestConfig
from athena.runtime.models import ExecutionStatus
from athena.scanner.scanner import DailyMarketScanner
from athena.strategy.framework import StrategyFramework
from athena.watchlist.manager import WatchlistManager
from athena.watchlist.models import WatchlistSnapshot


class BacktestingEngine:
    """Coordinates a chronological replay through ATHENA's operational pipeline."""

    def __init__(
        self,
        scanner: DailyMarketScanner,
        watchlist_manager: WatchlistManager,
        strategy_framework: StrategyFramework,
        config: BacktestConfig | None = None,
    ) -> None:
        self._scanner = scanner
        self._watchlist = watchlist_manager
        self._strategy = strategy_framework
        self._config = config or BacktestConfig()

    def run(self, points: Sequence[ReplayPoint], *, run_id: str | None = None) -> BacktestRun:
        """Replay ``points`` in chronological order into an immutable BacktestRun."""
        ordered = self._chronological(points)

        steps: list[BacktestStep] = []
        previous: WatchlistSnapshot | None = None
        for point in ordered:
            step = self._replay_one(point, previous)
            steps.append(step)
            if step.status is ExecutionStatus.COMPLETED:
                if self._config.carry_watchlist and step.watchlist is not None:
                    previous = step.watchlist
            elif not self._config.continue_on_error:
                break  # stop the replay; remaining points are not executed

        summary = self._summarise(steps)
        first = ordered[0].replay_date if ordered else None
        last = ordered[len(steps) - 1].replay_date if steps else None
        resolved_id = run_id or self._default_run_id(first, last)
        session = BacktestSession(session_id=f"session-{resolved_id}",
                                  steps=tuple(steps), summary=summary)
        return BacktestRun(run_id=resolved_id, first_replay_date=first,
                           last_replay_date=last, session=session)

    # ------------------------------------------------------------- internals

    @staticmethod
    def _chronological(points: Sequence[ReplayPoint]) -> list[ReplayPoint]:
        ordered = sorted(points, key=lambda p: p.as_of)
        seen: set = set()
        for point in ordered:
            if point.as_of in seen:
                raise ValueError(f"duplicate replay point for as_of {point.as_of.isoformat()}")
            seen.add(point.as_of)
        return ordered

    def _replay_one(self, point: ReplayPoint, previous: WatchlistSnapshot | None) -> BacktestStep:
        try:
            scan_report = self._scanner.scan(point.universe, as_of=point.as_of,
                                             pipeline_builder=point.pipeline_builder)
            watchlist = self._watchlist.apply(scan_report, as_of=point.as_of, previous=previous)
            execution = self._strategy.execute(scan_report, watchlist, as_of=point.as_of)
        except Exception as exc:
            return BacktestStep(
                replay_date=point.replay_date, as_of=point.as_of,
                status=ExecutionStatus.FAILED, scan_report=None, watchlist=None,
                strategy_execution=None,
                note=f"replay failed: {type(exc).__name__}: {exc}")
        return BacktestStep(
            replay_date=point.replay_date, as_of=point.as_of,
            status=ExecutionStatus.COMPLETED, scan_report=scan_report,
            watchlist=watchlist, strategy_execution=execution,
            note=(f"replayed: {scan_report.statistics.total} scanned, "
                  f"{execution.summary.total_matches} strategy match(es)"))

    @staticmethod
    def _summarise(steps: Sequence[BacktestStep]) -> BacktestSummary:
        completed = sum(1 for s in steps if s.status is ExecutionStatus.COMPLETED)
        failed = sum(1 for s in steps if s.status is ExecutionStatus.FAILED)

        total_matches: dict[str, int] = {}
        steps_with_matches: dict[str, int] = {}
        instruments: dict[str, set] = {}
        for step in steps:
            if step.strategy_execution is None:
                continue
            for result in step.strategy_execution.results:
                total_matches.setdefault(result.strategy, 0)
                steps_with_matches.setdefault(result.strategy, 0)
                instruments.setdefault(result.strategy, set())
                if result.matches:
                    total_matches[result.strategy] += len(result.matches)
                    steps_with_matches[result.strategy] += 1
                    instruments[result.strategy].update(m.instrument_id for m in result.matches)

        performance = tuple(
            StrategyPerformance(
                strategy=name, total_matches=total_matches[name],
                steps_with_matches=steps_with_matches[name],
                instruments=tuple(sorted(instruments[name])))
            for name in sorted(total_matches)
        )
        return BacktestSummary(total_steps=len(steps), completed_steps=completed,
                               failed_steps=failed, performance=performance)

    @staticmethod
    def _default_run_id(first, last) -> str:
        if first is None or last is None:
            return "backtest-empty"
        return f"backtest-{first.isoformat()}_{last.isoformat()}"
