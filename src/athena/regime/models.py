"""Regime Engine result types (M2.1).

Descriptive market-context objects. These are market-intelligence result types,
not additions to the frozen canonical domain §4 (which already provides the
RegimeAssessment the engine produces). Immutable and explainable.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from enum import Enum, unique
from types import MappingProxyType

from athena.domain.market import RegimeAssessment


@unique
class RegimeLabel(str, Enum):
    """The labels ATHENA can assign, grouped by dimension. Descriptive, never prescriptive."""

    # Trend dimension
    BULL_TREND = "BULL_TREND"
    BEAR_TREND = "BEAR_TREND"
    SIDEWAYS = "SIDEWAYS"
    TREND_UNKNOWN = "TREND_UNKNOWN"
    # Volatility dimension
    HIGH_VOLATILITY = "HIGH_VOLATILITY"
    LOW_VOLATILITY = "LOW_VOLATILITY"
    NORMAL_VOLATILITY = "NORMAL_VOLATILITY"
    VOLATILITY_UNKNOWN = "VOLATILITY_UNKNOWN"
    # Gap dimension
    GAP_UP = "GAP_UP"
    GAP_DOWN = "GAP_DOWN"
    NO_GAP = "NO_GAP"
    GAP_UNKNOWN = "GAP_UNKNOWN"


@dataclass(frozen=True, slots=True)
class RegimeEvidence:
    """Supporting evidence for one regime dimension — the WHY behind a label."""

    evidence_id: str
    dimension: str
    outcome: RegimeLabel
    explanation: str
    inputs: Mapping[str, str] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not self.explanation:
            raise ValueError("RegimeEvidence.explanation is mandatory (explainability)")
        object.__setattr__(self, "inputs", MappingProxyType(dict(self.inputs)))


@dataclass(frozen=True, slots=True)
class RegimeResult:
    """A RegimeAssessment plus the complete supporting evidence chain."""

    assessment: RegimeAssessment
    evidence: tuple[RegimeEvidence, ...]

    def __post_init__(self) -> None:
        if not self.evidence:
            raise ValueError("RegimeResult must carry supporting evidence")

    def label_values(self) -> tuple[str, ...]:
        return self.assessment.labels
