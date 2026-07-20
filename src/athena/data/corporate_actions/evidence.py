"""Immutable adjustment evidence + result (M1.4).

Every adjustment is explainable: which action triggered it, what factor was
applied, and how many records were affected. No silent transformations.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime
from decimal import Decimal
from types import MappingProxyType
from typing import Mapping, Tuple

from athena.data.corporate_actions.models import AdjustmentStrategy, CorporateActionType
from athena.domain.market import Candle


@dataclass(frozen=True, slots=True)
class AdjustmentEvidence:
    """Structured record of one action's effect on the dataset."""

    action_id: str
    action_type: CorporateActionType
    ex_date: date
    price_factor: Decimal
    volume_factor: Decimal
    affected_records: int
    explanation: str
    metadata: Mapping[str, str] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not self.explanation:
            raise ValueError("AdjustmentEvidence.explanation is mandatory (explainability)")
        if self.affected_records < 0:
            raise ValueError("AdjustmentEvidence.affected_records must be >= 0")
        object.__setattr__(self, "metadata", MappingProxyType(dict(self.metadata)))


@dataclass(frozen=True, slots=True)
class AdjustmentResult:
    """Adjusted copy of a dataset plus the full evidence chain. Originals untouched."""

    instrument_id: str
    strategy: AdjustmentStrategy
    adjusted_candles: Tuple[Candle, ...]
    evidence: Tuple[AdjustmentEvidence, ...]
    explanation: str
    ts: datetime

    def __post_init__(self) -> None:
        if not self.explanation:
            raise ValueError("AdjustmentResult.explanation is mandatory (explainability)")
        if self.ts.tzinfo is None:
            raise ValueError("AdjustmentResult.ts must be timezone-aware")
