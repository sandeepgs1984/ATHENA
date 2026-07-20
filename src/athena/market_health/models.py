"""Market Health result types (M2.2).

Descriptive market-intelligence objects (not additions to the frozen domain §4).
Immutable and explainable; every dimension carries its own evidence including
the thresholds that produced the label.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum, unique
from types import MappingProxyType


@unique
class MarketHealthLabel(str, Enum):
    """Descriptive labels per health dimension. Never prescriptive."""

    # Breadth
    STRONG_BREADTH = "STRONG_BREADTH"
    WEAK_BREADTH = "WEAK_BREADTH"
    MIXED_BREADTH = "MIXED_BREADTH"
    BREADTH_UNKNOWN = "BREADTH_UNKNOWN"
    # Trend quality
    STRONG_TREND_QUALITY = "STRONG_TREND_QUALITY"
    WEAK_TREND_QUALITY = "WEAK_TREND_QUALITY"
    MIXED_TREND_QUALITY = "MIXED_TREND_QUALITY"
    TREND_QUALITY_UNKNOWN = "TREND_QUALITY_UNKNOWN"
    # Momentum
    HEALTHY_MOMENTUM = "HEALTHY_MOMENTUM"
    WEAK_MOMENTUM = "WEAK_MOMENTUM"
    FLAT_MOMENTUM = "FLAT_MOMENTUM"
    MOMENTUM_UNKNOWN = "MOMENTUM_UNKNOWN"
    # Volatility context
    VOLATILITY_CALM = "VOLATILITY_CALM"
    VOLATILITY_NORMAL = "VOLATILITY_NORMAL"
    VOLATILITY_ELEVATED = "VOLATILITY_ELEVATED"
    VOLATILITY_UNKNOWN = "VOLATILITY_UNKNOWN"


@dataclass(frozen=True, slots=True)
class HealthEvidence:
    """Supporting evidence for one health dimension — inputs, thresholds, outcome, why."""

    evidence_id: str
    dimension: str
    outcome: MarketHealthLabel
    explanation: str
    inputs: Mapping[str, str] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not self.explanation:
            raise ValueError("HealthEvidence.explanation is mandatory (explainability)")
        object.__setattr__(self, "inputs", MappingProxyType(dict(self.inputs)))


@dataclass(frozen=True, slots=True)
class MarketHealthAssessment:
    """Immutable market-health assessment composed of independently explainable dimensions."""

    assessment_id: str
    ts: datetime
    dimensions: Mapping[str, str]
    evidence_ids: tuple[str, ...]
    explanation: str

    def __post_init__(self) -> None:
        if not self.dimensions:
            raise ValueError("MarketHealthAssessment must have at least one dimension")
        if not self.explanation:
            raise ValueError("MarketHealthAssessment.explanation is mandatory")
        if self.ts.tzinfo is None:
            raise ValueError("MarketHealthAssessment.ts must be timezone-aware")
        object.__setattr__(self, "dimensions", MappingProxyType(dict(self.dimensions)))


@dataclass(frozen=True, slots=True)
class MarketHealthResult:
    """A MarketHealthAssessment plus the complete supporting evidence chain."""

    assessment: MarketHealthAssessment
    evidence: tuple[HealthEvidence, ...]

    def __post_init__(self) -> None:
        if not self.evidence:
            raise ValueError("MarketHealthResult must carry supporting evidence")
