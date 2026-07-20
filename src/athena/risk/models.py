"""Risk result types (M3.5).

Immutable exposure artifacts (not frozen domain §4). Risk measures exposure and
uncertainty only — never whether a trade should be taken. Higher value = more risk.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from enum import Enum, unique


@unique
class RiskStatus(str, Enum):
    OK = "OK"
    UNKNOWN = "UNKNOWN"


@unique
class RiskLevel(str, Enum):
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"


@dataclass(frozen=True, slots=True)
class RiskContribution:
    """One traceable input to a risk dimension."""

    source: str
    reference: str
    description: str

    def __post_init__(self) -> None:
        if not self.source or not self.description:
            raise ValueError("RiskContribution.source and description are mandatory")


@dataclass(frozen=True, slots=True)
class RiskDimension:
    """One independently explainable risk dimension, 0..100 (higher = more risk) or UNKNOWN."""

    name: str
    status: RiskStatus
    value: Decimal | None
    level: RiskLevel | None
    contributions: tuple[RiskContribution, ...]
    explanation: str

    def __post_init__(self) -> None:
        if not self.explanation:
            raise ValueError("RiskDimension.explanation is mandatory")
        if self.status is RiskStatus.OK:
            if self.value is None or self.level is None:
                raise ValueError("an OK RiskDimension needs a value and level")
            if not 0 <= self.value <= 100:
                raise ValueError(f"risk value must be 0..100, got {self.value}")
            if not self.contributions:
                raise ValueError("an OK RiskDimension must have a contribution trace")
        elif self.value is not None:
            raise ValueError("an UNKNOWN RiskDimension must not carry a value")

    @property
    def is_known(self) -> bool:
        return self.status is RiskStatus.OK


@dataclass(frozen=True, slots=True)
class RiskAssessment:
    """Immutable overall risk assessment across independent dimensions."""

    assessment_id: str
    ts: datetime
    dimensions: Mapping[str, RiskDimension]
    overall_status: RiskStatus
    overall_value: Decimal | None
    overall_level: RiskLevel | None
    completeness: Decimal
    unknown_stats: Mapping[str, int]
    explanation: str

    def __post_init__(self) -> None:
        if self.ts.tzinfo is None:
            raise ValueError("RiskAssessment.ts must be timezone-aware")
        if not self.dimensions:
            raise ValueError("RiskAssessment must contain dimensions")
        if not self.explanation:
            raise ValueError("RiskAssessment.explanation is mandatory")
