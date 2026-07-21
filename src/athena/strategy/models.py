"""Strategy Framework artifacts (M4.4).

Immutable records of which completed ATHENA decisions satisfy each strategy's
deterministic selection policy. Strategies express *selection*, not market
intelligence — nothing here recalculates or reinterprets a decision.

``InstrumentView`` is the read-only, pre-parsed lens a strategy sees: it bundles
one instrument's completed decision facts (already produced by the analytical
core) with its current watchlist memberships. Strategies filter these views;
they never touch analytical engines or raw market data.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from types import MappingProxyType

from athena.reporting.models import DecisionReport


@dataclass(frozen=True, slots=True)
class InstrumentView:
    """Read-only view of one completed decision + its watchlist memberships."""

    instrument_id: str
    decision_type: str
    direction: str
    decision_id: str
    decision_ts: datetime
    explanation: str
    composite_score: Decimal | None
    confidence_value: Decimal | None
    risk_value: Decimal | None
    watchlists: frozenset[str]
    report: DecisionReport

    def __post_init__(self) -> None:
        if not self.instrument_id:
            raise ValueError("InstrumentView.instrument_id is mandatory")
        if not self.decision_type:
            raise ValueError("InstrumentView.decision_type is mandatory")


@dataclass(frozen=True, slots=True)
class MatchProposal:
    """A strategy's proposal that one instrument matched, with its reason."""

    view: InstrumentView
    reason: str

    def __post_init__(self) -> None:
        if not self.reason:
            raise ValueError("MatchProposal.reason is mandatory — matches explain themselves")


@dataclass(frozen=True, slots=True)
class StrategyMatch:
    """One instrument selected by one strategy."""

    strategy: str
    instrument_id: str
    decision_type: str
    decision_id: str
    watchlists: tuple[str, ...]
    explanation: str
    references: Mapping[str, str]

    def __post_init__(self) -> None:
        for name in ("strategy", "instrument_id", "decision_type",
                     "decision_id", "explanation"):
            if not getattr(self, name):
                raise ValueError(f"StrategyMatch.{name} is mandatory")
        object.__setattr__(self, "references", MappingProxyType(dict(self.references)))


@dataclass(frozen=True, slots=True)
class StrategyResult:
    """Everything one strategy selected in a single execution."""

    strategy: str
    version: str
    description: str
    considered: int
    matches: tuple[StrategyMatch, ...]

    def __post_init__(self) -> None:
        for name in ("strategy", "version", "description"):
            if not getattr(self, name):
                raise ValueError(f"StrategyResult.{name} is mandatory")
        if self.considered < 0:
            raise ValueError("StrategyResult.considered must be >= 0")


@dataclass(frozen=True, slots=True)
class StrategySummary:
    """Cross-strategy roll-up for one execution."""

    match_counts: Mapping[str, int]
    total_matches: int
    instruments_matched: int
    overlapping_instruments: tuple[str, ...]

    def __post_init__(self) -> None:
        object.__setattr__(self, "match_counts", MappingProxyType(dict(self.match_counts)))
        if self.total_matches < 0 or self.instruments_matched < 0:
            raise ValueError("StrategySummary counts must be >= 0")


@dataclass(frozen=True, slots=True)
class StrategyExecution:
    """Immutable output of running every registered strategy over one input set."""

    execution_id: str
    as_of: datetime
    scan_id: str
    watchlist_snapshot_id: str
    results: tuple[StrategyResult, ...]
    summary: StrategySummary

    def __post_init__(self) -> None:
        if self.as_of.tzinfo is None:
            raise ValueError("StrategyExecution.as_of must be timezone-aware")
        if not self.scan_id:
            raise ValueError("StrategyExecution.scan_id is mandatory")

    def result_for(self, strategy: str) -> StrategyResult | None:
        return next((r for r in self.results if r.strategy == strategy), None)

    def matches_for_instrument(self, instrument_id: str) -> tuple[StrategyMatch, ...]:
        return tuple(m for r in self.results for m in r.matches
                     if m.instrument_id == instrument_id)

    def to_dict(self) -> dict[str, object]:
        return {
            "execution_id": self.execution_id,
            "as_of": self.as_of.isoformat(),
            "scan_id": self.scan_id,
            "watchlist_snapshot_id": self.watchlist_snapshot_id,
            "summary": {
                "match_counts": dict(self.summary.match_counts),
                "total_matches": self.summary.total_matches,
                "instruments_matched": self.summary.instruments_matched,
                "overlapping_instruments": list(self.summary.overlapping_instruments),
            },
            "results": [
                {
                    "strategy": r.strategy, "version": r.version,
                    "description": r.description, "considered": r.considered,
                    "matches": [
                        {"strategy": m.strategy, "instrument_id": m.instrument_id,
                         "decision_type": m.decision_type, "decision_id": m.decision_id,
                         "watchlists": list(m.watchlists), "explanation": m.explanation,
                         "references": dict(m.references)}
                        for m in r.matches
                    ],
                }
                for r in self.results
            ],
        }
