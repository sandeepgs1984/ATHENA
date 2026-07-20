"""Confidence result types (M3.4).

Immutable reliability artifacts (not frozen domain §4). Confidence describes how
trustworthy the evaluation is — never market direction or attractiveness.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from enum import Enum, unique


@unique
class ConfidenceStatus(str, Enum):
    OK = "OK"
    UNKNOWN = "UNKNOWN"


@unique
class ConfidenceLevel(str, Enum):
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"


@dataclass(frozen=True, slots=True)
class ConfidenceContribution:
    """One traceable input to a confidence dimension."""

    source: str
    reference: str
    description: str

    def __post_init__(self) -> None:
        if not self.source or not self.description:
            raise ValueError("ConfidenceContribution.source and description are mandatory")


@dataclass(frozen=True, slots=True)
class ConfidenceDimension:
    """One independently explainable confidence dimension, 0..100 or UNKNOWN."""

    name: str
    status: ConfidenceStatus
    value: Decimal | None
    level: ConfidenceLevel | None
    contributions: tuple[ConfidenceContribution, ...]
    explanation: str

    def __post_init__(self) -> None:
        if not self.explanation:
            raise ValueError("ConfidenceDimension.explanation is mandatory")
        if self.status is ConfidenceStatus.OK:
            if self.value is None or self.level is None:
                raise ValueError("an OK ConfidenceDimension needs a value and level")
            if not 0 <= self.value <= 100:
                raise ValueError(f"confidence value must be 0..100, got {self.value}")
        elif self.value is not None:
            raise ValueError("an UNKNOWN ConfidenceDimension must not carry a value")

    @property
    def is_known(self) -> bool:
        return self.status is ConfidenceStatus.OK


@dataclass(frozen=True, slots=True)
class ConfidenceAssessment:
    """Immutable overall confidence assessment across independent dimensions."""

    assessment_id: str
    ts: datetime
    dimensions: Mapping[str, ConfidenceDimension]
    overall_status: ConfidenceStatus
    overall_value: Decimal | None
    overall_level: ConfidenceLevel | None
    completeness: Decimal
    unknown_stats: Mapping[str, int]
    explanation: str

    def __post_init__(self) -> None:
        if self.ts.tzinfo is None:
            raise ValueError("ConfidenceAssessment.ts must be timezone-aware")
        if not self.dimensions:
            raise ValueError("ConfidenceAssessment must contain dimensions")
        if not self.explanation:
            raise ValueError("ConfidenceAssessment.explanation is mandatory")
