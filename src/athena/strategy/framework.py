"""Strategy Framework (M4.4).

Answers one question: "Which completed ATHENA decisions satisfy each strategy's
deterministic selection policy?" It registers strategies and runs them over the
immutable outputs of the Daily Market Scanner (M4.2) and Watchlist Manager
(M4.3), producing an immutable StrategyExecution.

It COORDINATES STRATEGY EVALUATION ONLY: it parses completed decision artifacts
into read-only views, invokes each strategy, and aggregates the results. It
never invokes an analytical engine, never computes an indicator, and never
reinterprets a decision.

Determinism: instruments are viewed in stable sorted order, strategies run in
registration order, and matches are ordered by instrument. With no clock read
(``as_of`` injected), identical inputs always produce an identical execution.
"""

from __future__ import annotations

from collections.abc import Mapping
from datetime import datetime
from decimal import Decimal, InvalidOperation

from athena.config.models import StrategyConfig
from athena.runtime.models import ExecutionStatus
from athena.scanner.models import DailyScanReport, InstrumentScanResult
from athena.strategy.base import Strategy
from athena.strategy.models import (
    InstrumentView,
    StrategyExecution,
    StrategyMatch,
    StrategyResult,
    StrategySummary,
)
from athena.strategy.strategies import REFERENCE_STRATEGIES
from athena.watchlist.models import WatchlistSnapshot


class StrategyFramework:
    """Registers strategies and evaluates them over completed artifacts."""

    def __init__(self) -> None:
        self._strategies: list[Strategy] = []
        self._names: set[str] = set()

    def register(self, strategy: Strategy) -> None:
        """Register a strategy. Duplicate names are rejected (fail loudly)."""
        if not strategy.name:
            raise ValueError("strategy must declare a non-empty name")
        if strategy.name in self._names:
            raise ValueError(f"strategy already registered: {strategy.name}")
        self._names.add(strategy.name)
        self._strategies.append(strategy)

    def strategies(self) -> tuple[Strategy, ...]:
        return tuple(self._strategies)

    def execute(
        self,
        scan_report: DailyScanReport,
        watchlist: WatchlistSnapshot,
        *,
        as_of: datetime,
    ) -> StrategyExecution:
        """Run every registered strategy over one scan report + watchlist snapshot."""
        if as_of.tzinfo is None:
            raise ValueError("StrategyFramework.execute requires timezone-aware as_of")

        views = self._build_views(scan_report, watchlist)

        results: list[StrategyResult] = []
        match_counts: dict[str, int] = {}
        matched_instruments: dict[str, int] = {}
        for strategy in self._strategies:
            proposals = strategy.select(views)
            matches = tuple(
                StrategyMatch(
                    strategy=strategy.name, instrument_id=p.view.instrument_id,
                    decision_type=p.view.decision_type, decision_id=p.view.decision_id,
                    watchlists=tuple(sorted(p.view.watchlists)),
                    explanation=p.reason,
                    references=self._references(scan_report, watchlist, p.view))
                for p in sorted(proposals, key=lambda p: p.view.instrument_id)
            )
            results.append(StrategyResult(
                strategy=strategy.name, version=strategy.version,
                description=strategy.description, considered=len(views), matches=matches))
            match_counts[strategy.name] = len(matches)
            for m in matches:
                matched_instruments[m.instrument_id] = \
                    matched_instruments.get(m.instrument_id, 0) + 1

        overlapping = tuple(sorted(i for i, n in matched_instruments.items() if n > 1))
        summary = StrategySummary(
            match_counts=match_counts,
            total_matches=sum(match_counts.values()),
            instruments_matched=len(matched_instruments),
            overlapping_instruments=overlapping)
        return StrategyExecution(
            execution_id=f"strategy-exec-{as_of.isoformat()}", as_of=as_of,
            scan_id=scan_report.scan_id, watchlist_snapshot_id=watchlist.snapshot_id,
            results=tuple(results), summary=summary)

    # ------------------------------------------------------------- internals

    @staticmethod
    def _build_views(
        scan_report: DailyScanReport,
        watchlist: WatchlistSnapshot,
    ) -> tuple[InstrumentView, ...]:
        memberships: dict[str, set[str]] = {}
        for entry in watchlist.entries:
            memberships.setdefault(entry.instrument_id, set()).add(entry.watchlist)

        views: list[InstrumentView] = []
        for result in sorted(scan_report.results, key=lambda r: r.instrument_id):
            if not _has_decision(result):
                continue
            decision = result.report.machine.get("decision")
            decision = decision if isinstance(decision, dict) else {}
            views.append(InstrumentView(
                instrument_id=result.instrument_id,
                decision_type=result.decision_type or "",
                direction=str(decision.get("direction") or "NONE"),
                decision_id=result.report.decision_id,
                decision_ts=result.report.ts,
                explanation=str(decision.get("explanation") or f"decision {result.decision_type}"),
                composite_score=_num(result.report.machine, "score", "composite"),
                confidence_value=_num(result.report.machine, "confidence", "overall"),
                risk_value=_num(result.report.machine, "risk", "overall"),
                watchlists=frozenset(memberships.get(result.instrument_id, set())),
                report=result.report))
        return tuple(views)

    @staticmethod
    def _references(
        scan_report: DailyScanReport,
        watchlist: WatchlistSnapshot,
        view: InstrumentView,
    ) -> dict[str, str]:
        refs = {
            "decision_id": view.decision_id,
            "scan_id": scan_report.scan_id,
            "watchlist_snapshot_id": watchlist.snapshot_id,
        }
        machine_refs = view.report.machine.get("references")
        if isinstance(machine_refs, Mapping):
            for key, value in machine_refs.items():
                if value:
                    refs[str(key)] = str(value)
        return refs

    @classmethod
    def from_config(cls, config: StrategyConfig) -> StrategyFramework:
        """Build a framework with the enabled reference strategies from config.

        Strategies register in a stable, id-sorted order for determinism.
        """
        framework = cls()
        for strategy_id in sorted(config.strategies):
            rule = config.strategies[strategy_id]
            if not rule.enabled:
                continue
            factory = REFERENCE_STRATEGIES.get(strategy_id)
            if factory is None:
                raise ValueError(f"unknown reference strategy id: {strategy_id}")
            framework.register(factory(rule))
        return framework


def _has_decision(result: InstrumentScanResult) -> bool:
    return (result.status is ExecutionStatus.COMPLETED
            and result.report is not None
            and result.decision_type is not None)


def _num(machine: Mapping[str, object], section: str, key: str) -> Decimal | None:
    """Read an already-computed numeric field from a decision report. Never
    fabricates: absent or UNKNOWN stays None."""
    block = machine.get(section)
    if not isinstance(block, Mapping):
        return None
    raw = block.get(key)
    if raw is None:
        return None
    try:
        return Decimal(str(raw))
    except (InvalidOperation, ValueError):
        return None
