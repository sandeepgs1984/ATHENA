"""Sector Health result types (M2.3).

Descriptive per-sector market-intelligence objects (not frozen domain §4).
Immutable and explainable; each dimension carries inputs, thresholds, outcome,
and a human explanation.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum, unique
from types import MappingProxyType


@unique
class SectorHealthLabel(str, Enum):
    """Descriptive per-sector labels. Never a ranking or recommendation."""

    # Trend
    SECTOR_UPTREND = "SECTOR_UPTREND"
    SECTOR_DOWNTREND = "SECTOR_DOWNTREND"
    SECTOR_SIDEWAYS = "SECTOR_SIDEWAYS"
    SECTOR_TREND_UNKNOWN = "SECTOR_TREND_UNKNOWN"
    # Breadth
    STRONG_SECTOR_BREADTH = "STRONG_SECTOR_BREADTH"
    WEAK_SECTOR_BREADTH = "WEAK_SECTOR_BREADTH"
    MIXED_SECTOR_BREADTH = "MIXED_SECTOR_BREADTH"
    SECTOR_BREADTH_UNKNOWN = "SECTOR_BREADTH_UNKNOWN"
    # Momentum
    HEALTHY_SECTOR_MOMENTUM = "HEALTHY_SECTOR_MOMENTUM"
    WEAK_SECTOR_MOMENTUM = "WEAK_SECTOR_MOMENTUM"
    FLAT_SECTOR_MOMENTUM = "FLAT_SECTOR_MOMENTUM"
    SECTOR_MOMENTUM_UNKNOWN = "SECTOR_MOMENTUM_UNKNOWN"
    # Volatility context
    SECTOR_VOLATILITY_CALM = "SECTOR_VOLATILITY_CALM"
    SECTOR_VOLATILITY_NORMAL = "SECTOR_VOLATILITY_NORMAL"
    SECTOR_VOLATILITY_ELEVATED = "SECTOR_VOLATILITY_ELEVATED"
    SECTOR_VOLATILITY_UNKNOWN = "SECTOR_VOLATILITY_UNKNOWN"


@dataclass(frozen=True, slots=True)
class SectorHealthEvidence:
    """Supporting evidence for one sector-health dimension."""

    evidence_id: str
    dimension: str
    outcome: SectorHealthLabel
    explanation: str
    inputs: Mapping[str, str] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not self.explanation:
            raise ValueError("SectorHealthEvidence.explanation is mandatory (explainability)")
        object.__setattr__(self, "inputs", MappingProxyType(dict(self.inputs)))


@dataclass(frozen=True, slots=True)
class SectorHealthAssessment:
    """Immutable per-sector health assessment of independently explainable dimensions."""

    assessment_id: str
    ts: datetime
    sector: str
    dimensions: Mapping[str, str]
    evidence_ids: tuple[str, ...]
    explanation: str

    def __post_init__(self) -> None:
        if not self.sector:
            raise ValueError("SectorHealthAssessment.sector is mandatory")
        if not self.dimensions:
            raise ValueError("SectorHealthAssessment must have at least one dimension")
        if not self.explanation:
            raise ValueError("SectorHealthAssessment.explanation is mandatory")
        if self.ts.tzinfo is None:
            raise ValueError("SectorHealthAssessment.ts must be timezone-aware")
        object.__setattr__(self, "dimensions", MappingProxyType(dict(self.dimensions)))


@dataclass(frozen=True, slots=True)
class SectorHealthResult:
    """A SectorHealthAssessment plus its complete supporting evidence chain."""

    assessment: SectorHealthAssessment
    evidence: tuple[SectorHealthEvidence, ...]

    def __post_init__(self) -> None:
        if not self.evidence:
            raise ValueError("SectorHealthResult must carry supporting evidence")
