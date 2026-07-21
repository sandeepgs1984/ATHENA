"""Reporting & Analytics artifacts (M4.6).

Immutable summaries of what ATHENA's completed pipeline produced. Reporting
explains what happened; analytics aggregate what happened. Nothing here executes
an analytical engine, derives new market intelligence, or changes a completed
decision — every metric is a count or roll-up of an existing immutable artifact,
and every artifact preserves references back to its sources.
"""

from __future__ import annotations

import json
from collections.abc import Mapping
from dataclasses import dataclass, field
from datetime import datetime
from types import MappingProxyType


def _frozen_int_map(value: Mapping[str, int]) -> Mapping[str, int]:
    return MappingProxyType(dict(value))


@dataclass(frozen=True, slots=True)
class WatchlistAnalytics:
    """Aggregated watchlist membership for one snapshot."""

    snapshot_id: str
    scan_id: str
    total_entries: int
    counts: Mapping[str, int]
    added: int
    retained: int
    removed: int

    def __post_init__(self) -> None:
        object.__setattr__(self, "counts", _frozen_int_map(self.counts))

    def to_dict(self) -> dict[str, object]:
        return {
            "snapshot_id": self.snapshot_id, "scan_id": self.scan_id,
            "total_entries": self.total_entries, "counts": dict(self.counts),
            "added": self.added, "retained": self.retained, "removed": self.removed,
        }


@dataclass(frozen=True, slots=True)
class StrategyAnalytics:
    """Aggregated strategy selection for one execution."""

    execution_id: str
    scan_id: str
    watchlist_snapshot_id: str
    match_counts: Mapping[str, int]
    total_matches: int
    instruments_matched: int
    overlapping_instruments: tuple[str, ...]

    def __post_init__(self) -> None:
        object.__setattr__(self, "match_counts", _frozen_int_map(self.match_counts))

    def to_dict(self) -> dict[str, object]:
        return {
            "execution_id": self.execution_id, "scan_id": self.scan_id,
            "watchlist_snapshot_id": self.watchlist_snapshot_id,
            "match_counts": dict(self.match_counts), "total_matches": self.total_matches,
            "instruments_matched": self.instruments_matched,
            "overlapping_instruments": list(self.overlapping_instruments),
        }


@dataclass(frozen=True, slots=True)
class DailyAnalytics:
    """"What happened today?" — one scan cycle, optionally with watchlist + strategy."""

    scan_id: str
    as_of: datetime
    instruments_scanned: int
    successful: int
    failed: int
    skipped: int
    decision_distribution: Mapping[str, int]
    confidence_distribution: Mapping[str, int]
    risk_distribution: Mapping[str, int]
    watchlist: WatchlistAnalytics | None = None
    strategy: StrategyAnalytics | None = None

    def __post_init__(self) -> None:
        if self.as_of.tzinfo is None:
            raise ValueError("DailyAnalytics.as_of must be timezone-aware")
        for name in ("decision_distribution", "confidence_distribution", "risk_distribution"):
            object.__setattr__(self, name, _frozen_int_map(getattr(self, name)))

    def to_dict(self) -> dict[str, object]:
        return {
            "scan_id": self.scan_id, "as_of": self.as_of.isoformat(),
            "instruments_scanned": self.instruments_scanned,
            "successful": self.successful, "failed": self.failed, "skipped": self.skipped,
            "decision_distribution": dict(self.decision_distribution),
            "confidence_distribution": dict(self.confidence_distribution),
            "risk_distribution": dict(self.risk_distribution),
            "watchlist": self.watchlist.to_dict() if self.watchlist else None,
            "strategy": self.strategy.to_dict() if self.strategy else None,
        }


@dataclass(frozen=True, slots=True)
class BacktestAnalytics:
    """"What operational activity occurred during replay?" — one BacktestRun."""

    run_id: str
    session_id: str
    first_replay_date: str | None
    last_replay_date: str | None
    total_steps: int
    completed_steps: int
    failed_steps: int
    decision_distribution: Mapping[str, int]
    strategy_match_counts: Mapping[str, int]
    strategy_instruments: Mapping[str, int]

    def __post_init__(self) -> None:
        for name in ("decision_distribution", "strategy_match_counts", "strategy_instruments"):
            object.__setattr__(self, name, _frozen_int_map(getattr(self, name)))

    @property
    def replay_coverage(self) -> int:
        """Number of successfully replayed steps."""
        return self.completed_steps

    def to_dict(self) -> dict[str, object]:
        return {
            "run_id": self.run_id, "session_id": self.session_id,
            "first_replay_date": self.first_replay_date,
            "last_replay_date": self.last_replay_date,
            "total_steps": self.total_steps, "completed_steps": self.completed_steps,
            "failed_steps": self.failed_steps,
            "decision_distribution": dict(self.decision_distribution),
            "strategy_match_counts": dict(self.strategy_match_counts),
            "strategy_instruments": dict(self.strategy_instruments),
        }


@dataclass(frozen=True, slots=True)
class AnalyticsSummary:
    """Top-level tallies for one analytics report."""

    kind: str
    totals: Mapping[str, int]

    def __post_init__(self) -> None:
        if not self.kind:
            raise ValueError("AnalyticsSummary.kind is mandatory")
        object.__setattr__(self, "totals", _frozen_int_map(self.totals))

    def to_dict(self) -> dict[str, object]:
        return {"kind": self.kind, "totals": dict(self.totals)}


@dataclass(frozen=True, slots=True)
class AnalyticsReport:
    """Immutable analytics report: a daily cycle or a replay, plus its summary."""

    report_id: str
    kind: str
    as_of: datetime
    summary: AnalyticsSummary
    references: Mapping[str, str]
    daily: DailyAnalytics | None = None
    backtest: BacktestAnalytics | None = None
    meta: Mapping[str, str] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if self.as_of.tzinfo is None:
            raise ValueError("AnalyticsReport.as_of must be timezone-aware")
        if self.kind not in {"daily", "replay"}:
            raise ValueError("AnalyticsReport.kind must be 'daily' or 'replay'")
        if self.kind == "daily" and self.daily is None:
            raise ValueError("a daily report must carry DailyAnalytics")
        if self.kind == "replay" and self.backtest is None:
            raise ValueError("a replay report must carry BacktestAnalytics")
        object.__setattr__(self, "references", MappingProxyType(dict(self.references)))
        object.__setattr__(self, "meta", MappingProxyType(dict(self.meta)))

    def to_dict(self) -> dict[str, object]:
        return {
            "report_id": self.report_id, "kind": self.kind,
            "as_of": self.as_of.isoformat(), "summary": self.summary.to_dict(),
            "references": dict(self.references), "meta": dict(self.meta),
            "daily": self.daily.to_dict() if self.daily else None,
            "backtest": self.backtest.to_dict() if self.backtest else None,
        }

    def to_json(self) -> str:
        """Deterministic JSON serialization (sorted keys)."""
        return json.dumps(self.to_dict(), sort_keys=True, indent=2)
