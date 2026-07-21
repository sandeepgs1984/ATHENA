"""Backtest artifacts (M4.5).

Immutable records of replaying ATHENA's existing operational pipeline across
historical points in time. Nothing here analyses markets, values a portfolio,
or computes P&L — a backtest step simply references the artifacts the real
scanner, watchlist manager, and strategy framework produced for one replay date.

``ReplayPoint`` is the caller-supplied input: a timezone-aware ``as_of``, the
universe to scan, and the per-instrument pipeline builder for that historical
date (identical in shape to what the live Daily Market Scanner consumes).
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from datetime import date, datetime
from types import MappingProxyType

from athena.runtime.models import ExecutionStatus
from athena.scanner.models import DailyScanReport, PipelineBuilder
from athena.strategy.models import StrategyExecution
from athena.watchlist.models import WatchlistSnapshot


@dataclass(frozen=True, slots=True)
class ReplayPoint:
    """One historical replay input: when, what universe, and how to build it."""

    as_of: datetime
    universe: tuple[str, ...]
    pipeline_builder: PipelineBuilder

    def __post_init__(self) -> None:
        if self.as_of.tzinfo is None:
            raise ValueError("ReplayPoint.as_of must be timezone-aware")

    @property
    def replay_date(self) -> date:
        return self.as_of.date()


@dataclass(frozen=True, slots=True)
class BacktestStep:
    """Outcome of replaying the full pipeline for a single point in time."""

    replay_date: date
    as_of: datetime
    status: ExecutionStatus
    scan_report: DailyScanReport | None
    watchlist: WatchlistSnapshot | None
    strategy_execution: StrategyExecution | None
    note: str

    def __post_init__(self) -> None:
        if self.as_of.tzinfo is None:
            raise ValueError("BacktestStep.as_of must be timezone-aware")
        if not self.note:
            raise ValueError("BacktestStep.note is mandatory")

    @property
    def scan_id(self) -> str | None:
        return self.scan_report.scan_id if self.scan_report else None

    @property
    def watchlist_snapshot_id(self) -> str | None:
        return self.watchlist.snapshot_id if self.watchlist else None

    @property
    def strategy_execution_id(self) -> str | None:
        return self.strategy_execution.execution_id if self.strategy_execution else None

    def to_dict(self) -> dict[str, object]:
        return {
            "replay_date": self.replay_date.isoformat(),
            "as_of": self.as_of.isoformat(),
            "status": self.status.value,
            "scan_id": self.scan_id,
            "watchlist_snapshot_id": self.watchlist_snapshot_id,
            "strategy_execution_id": self.strategy_execution_id,
            "note": self.note,
        }


@dataclass(frozen=True, slots=True)
class StrategyPerformance:
    """Aggregate behaviour of one strategy across the whole replay period."""

    strategy: str
    total_matches: int
    steps_with_matches: int
    instruments: tuple[str, ...]

    def __post_init__(self) -> None:
        if not self.strategy:
            raise ValueError("StrategyPerformance.strategy is mandatory")
        if min(self.total_matches, self.steps_with_matches) < 0:
            raise ValueError("StrategyPerformance counts must be >= 0")

    @property
    def distinct_instruments(self) -> int:
        return len(self.instruments)

    def to_dict(self) -> dict[str, object]:
        return {
            "strategy": self.strategy,
            "total_matches": self.total_matches,
            "steps_with_matches": self.steps_with_matches,
            "distinct_instruments": self.distinct_instruments,
            "instruments": list(self.instruments),
        }


@dataclass(frozen=True, slots=True)
class BacktestSummary:
    """Roll-up of a replay: step counts + per-strategy performance."""

    total_steps: int
    completed_steps: int
    failed_steps: int
    performance: tuple[StrategyPerformance, ...]

    def __post_init__(self) -> None:
        if self.completed_steps + self.failed_steps != self.total_steps:
            raise ValueError("BacktestSummary step counts must sum to total_steps")

    def performance_for(self, strategy: str) -> StrategyPerformance | None:
        return next((p for p in self.performance if p.strategy == strategy), None)

    def to_dict(self) -> dict[str, object]:
        return {
            "total_steps": self.total_steps,
            "completed_steps": self.completed_steps,
            "failed_steps": self.failed_steps,
            "performance": [p.to_dict() for p in self.performance],
        }


@dataclass(frozen=True, slots=True)
class BacktestSession:
    """The ordered, chronological result of one replay."""

    session_id: str
    steps: tuple[BacktestStep, ...]
    summary: BacktestSummary

    def __post_init__(self) -> None:
        if not self.session_id:
            raise ValueError("BacktestSession.session_id is mandatory")

    def to_dict(self) -> dict[str, object]:
        return {
            "session_id": self.session_id,
            "summary": self.summary.to_dict(),
            "steps": [s.to_dict() for s in self.steps],
        }


@dataclass(frozen=True, slots=True)
class BacktestRun:
    """Top-level immutable backtest artifact: run identity, period, and session."""

    run_id: str
    first_replay_date: date | None
    last_replay_date: date | None
    session: BacktestSession
    meta: Mapping[str, str] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not self.run_id:
            raise ValueError("BacktestRun.run_id is mandatory")
        object.__setattr__(self, "meta", MappingProxyType(dict(self.meta)))

    @property
    def steps(self) -> tuple[BacktestStep, ...]:
        return self.session.steps

    @property
    def summary(self) -> BacktestSummary:
        return self.session.summary

    def to_dict(self) -> dict[str, object]:
        return {
            "run_id": self.run_id,
            "first_replay_date": (self.first_replay_date.isoformat()
                                  if self.first_replay_date else None),
            "last_replay_date": (self.last_replay_date.isoformat()
                                 if self.last_replay_date else None),
            "meta": dict(self.meta),
            "session": self.session.to_dict(),
        }
