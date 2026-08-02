"""Scoring result types (M3.3).

Transparent, immutable scoring artifacts (not frozen domain §4). Every score is
traceable to specific evidence, indicators, and configuration. Scores are
intermediate decision artifacts — never recommendations.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from enum import Enum, unique


@unique
class ScoreStatus(str, Enum):
    OK = "OK"
    UNKNOWN = "UNKNOWN"


@dataclass(frozen=True, slots=True)
class Contribution:
    """One traceable input to a component score."""

    source: str            # e.g. "regime:trend", "indicator:RSI", "market_health:breadth"
    reference_id: str      # evidence_id / indicator name / assessment id
    description: str
    points: Decimal | None  # points contributed (None when informational only)

    def __post_init__(self) -> None:
        if not self.source or not self.reference_id:
            raise ValueError("Contribution.source and reference_id are mandatory")
        if not self.description:
            raise ValueError("Contribution.description is mandatory")


@dataclass(frozen=True, slots=True)
class ConfluenceInputs:
    """Per-instrument multi-timeframe trend-direction agreement (M-X7).

    ``daily_bullish`` is the anchor (daily last-close-vs-SMA read, the same
    basis technical_structure already uses). The 5m/15m fields are ``None``
    when that timeframe lacks enough history for its own short SMA — real
    production 15m history runs as thin as 9 bars/session, so this
    UNKNOWN-tolerance is load-bearing, not defensive boilerplate.
    """

    daily_bullish: bool
    five_min_bullish: bool | None
    fifteen_min_bullish: bool | None

    @property
    def checked(self) -> int:
        return sum(1 for v in (self.five_min_bullish, self.fifteen_min_bullish) if v is not None)

    @property
    def agreeing(self) -> int:
        return sum(
            1 for v in (self.five_min_bullish, self.fifteen_min_bullish)
            if v is not None and v == self.daily_bullish
        )


@dataclass(frozen=True, slots=True)
class ComponentScore:
    """One independent scoring dimension, 0..100, or UNKNOWN. Fully explained."""

    dimension: str
    status: ScoreStatus
    value: Decimal | None
    contributions: tuple[Contribution, ...]
    explanation: str

    def __post_init__(self) -> None:
        if not self.explanation:
            raise ValueError("ComponentScore.explanation is mandatory (explainability)")
        if self.status is ScoreStatus.OK:
            if self.value is None:
                raise ValueError("an OK ComponentScore must have a value")
            if not 0 <= self.value <= 100:
                raise ValueError(f"ComponentScore.value must be 0..100, got {self.value}")
            if not self.contributions:
                raise ValueError("an OK ComponentScore must have a contribution trace")
        elif self.value is not None:
            raise ValueError("an UNKNOWN ComponentScore must not carry a value")

    @property
    def is_known(self) -> bool:
        return self.status is ScoreStatus.OK


@dataclass(frozen=True, slots=True)
class CompositeBreakdownItem:
    """One component's contribution to the composite."""

    dimension: str
    weight: int
    status: ScoreStatus
    value: Decimal | None
    weighted: Decimal | None


@dataclass(frozen=True, slots=True)
class CompositeScore:
    """Weighted composite over known components, retaining the full breakdown."""

    status: ScoreStatus
    value: Decimal | None
    completeness: Decimal              # known weight / total weight (0..1)
    breakdown: tuple[CompositeBreakdownItem, ...]
    explanation: str

    def __post_init__(self) -> None:
        if not self.explanation:
            raise ValueError("CompositeScore.explanation is mandatory")
        if not self.breakdown:
            raise ValueError("CompositeScore must retain a breakdown of components")


@dataclass(frozen=True, slots=True)
class ScoringResult:
    """All component scores plus the composite for one instrument."""

    instrument_id: str
    ts: datetime
    components: Mapping[str, ComponentScore]
    composite: CompositeScore

    def __post_init__(self) -> None:
        if self.ts.tzinfo is None:
            raise ValueError("ScoringResult.ts must be timezone-aware")
        if not self.components:
            raise ValueError("ScoringResult must contain component scores")
