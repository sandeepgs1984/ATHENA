"""Evidence chain objects (ATHENA-002 §4, R-5). Every observation becomes Evidence."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from decimal import Decimal
from typing import Any, Mapping, Optional, Tuple

from athena.domain.enums import Direction, EvidenceCategory


@dataclass(frozen=True, slots=True)
class Evidence:
    """Atomic observation. The Decision Engine operates ONLY on Evidence (R-5)."""

    evidence_id: str
    category: EvidenceCategory
    source: str
    ts: datetime
    raw_value: Decimal
    normalized_value: Decimal
    weight: Decimal
    confidence: Decimal
    explanation: str
    instrument_id: Optional[str] = None
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not self.explanation:
            raise ValueError("Evidence.explanation is mandatory (ADR-005: explainability as data)")
        if self.ts.tzinfo is None:
            raise ValueError("Evidence.ts must be timezone-aware")
        if not Decimal(0) <= self.confidence <= Decimal(1):
            raise ValueError(f"Evidence.confidence must be 0..1, got {self.confidence}")


@dataclass(frozen=True, slots=True)
class Signal:
    """Directional aggregation of Evidence."""

    signal_id: str
    instrument_id: str
    direction: Direction
    strength: Decimal
    evidence_ids: Tuple[str, ...]
    explanation: str

    def __post_init__(self) -> None:
        if not self.explanation:
            raise ValueError("Signal.explanation is mandatory (ADR-005)")
        if not self.evidence_ids:
            raise ValueError("Signal must reference at least one Evidence")


@dataclass(frozen=True, slots=True)
class Score:
    """Opportunity quality with full per-factor attribution."""

    score_id: str
    instrument_id: str
    total: int
    breakdown: Mapping[str, int]
    evidence_ids: Tuple[str, ...]
    config_snapshot_id: str
    explanation: str

    def __post_init__(self) -> None:
        if not self.explanation:
            raise ValueError("Score.explanation is mandatory (ADR-005)")
        if sum(self.breakdown.values()) != self.total:
            raise ValueError(
                f"Score.breakdown must sum to total: {dict(self.breakdown)} != {self.total}"
            )
        if not self.evidence_ids:
            raise ValueError("Score must reference the Evidence behind it")


@dataclass(frozen=True, slots=True)
class ConfidenceAssessment:
    """Historical trust in a score (R-7) — empirical calibration, never parametric fiction."""

    score_bucket: str
    empirical_hit_rate: Decimal
    sample_size: int
    method: str
    explanation: str

    def __post_init__(self) -> None:
        if not self.explanation:
            raise ValueError("ConfidenceAssessment.explanation is mandatory (ADR-005)")
        if self.sample_size < 0:
            raise ValueError("ConfidenceAssessment.sample_size must be >= 0")


@dataclass(frozen=True, slots=True)
class ExplainabilityReport:
    """Input to the explainability quality gate (R-8)."""

    decision_ref: str
    factor_coverage: Mapping[str, int]
    completeness: Decimal
    missing: Tuple[str, ...] = ()

    def __post_init__(self) -> None:
        if not Decimal(0) <= self.completeness <= Decimal(1):
            raise ValueError(f"completeness must be 0..1, got {self.completeness}")
