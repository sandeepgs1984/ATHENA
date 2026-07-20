"""Universe Engine result types (M2.4).

Eligibility-focused market-intelligence objects (not additions to the frozen
domain §4, which already provides Universe/UniverseMember for the canonical
included set). Immutable and fully explainable — every inclusion and exclusion
carries its evidence.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from types import MappingProxyType


@dataclass(frozen=True, slots=True)
class RuleEvidence:
    """Outcome of one eligibility rule for one instrument."""

    rule: str
    passed: bool
    explanation: str
    inputs: Mapping[str, str] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not self.explanation:
            raise ValueError("RuleEvidence.explanation is mandatory (explainability)")
        object.__setattr__(self, "inputs", MappingProxyType(dict(self.inputs)))


@dataclass(frozen=True, slots=True)
class UniverseAssessment:
    """Per-instrument eligibility decision with complete evidence."""

    instrument_id: str
    included: bool
    exclusion_reasons: tuple[str, ...]
    evidence: tuple[RuleEvidence, ...]
    eligibility_summary: str

    def __post_init__(self) -> None:
        if not self.evidence:
            raise ValueError("UniverseAssessment must carry rule evidence")
        if not self.eligibility_summary:
            raise ValueError("UniverseAssessment.eligibility_summary is mandatory")
        if self.included and self.exclusion_reasons:
            raise ValueError("an included instrument cannot have exclusion reasons")
        if not self.included and not self.exclusion_reasons:
            raise ValueError("an excluded instrument must name its exclusion reasons")
