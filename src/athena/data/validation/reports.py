"""Immutable validation results (M1.3).

These are data-layer result types, not additions to the frozen canonical domain
model (ATHENA-002 §4) — the validation layer produces them, downstream code and
quarantine consume them. Every report is immutable, explainable, and carries the
evidence and statistics needed for audit and replay.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum, unique
from types import MappingProxyType


@unique
class ValidationType(str, Enum):
    FRESHNESS = "FRESHNESS"
    OHLC = "OHLC"
    DUPLICATE = "DUPLICATE"
    GAP = "GAP"


@unique
class ValidationResult(str, Enum):
    PASSED = "PASSED"
    FAILED = "FAILED"


@unique
class Severity(str, Enum):
    INFO = "INFO"
    WARNING = "WARNING"
    ERROR = "ERROR"
    CRITICAL = "CRITICAL"


@dataclass(frozen=True, slots=True)
class ValidationReport:
    """One validation check's outcome. Immutable and self-explaining."""

    validation_type: ValidationType
    result: ValidationResult
    severity: Severity
    explanation: str
    ts: datetime
    evidence: tuple[str, ...] = ()
    statistics: Mapping[str, object] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not self.explanation:
            raise ValueError("ValidationReport.explanation is mandatory (explainability)")
        if self.ts.tzinfo is None:
            raise ValueError("ValidationReport.ts must be timezone-aware")
        if self.result is ValidationResult.PASSED and self.severity in (
            Severity.ERROR, Severity.CRITICAL
        ):
            raise ValueError("a PASSED report cannot carry ERROR/CRITICAL severity")
        # Freeze statistics so a report can never be mutated after creation.
        object.__setattr__(self, "statistics", MappingProxyType(dict(self.statistics)))

    @property
    def passed(self) -> bool:
        return self.result is ValidationResult.PASSED


@dataclass(frozen=True, slots=True)
class ValidationSummary:
    """Aggregate of all reports for one dataset."""

    dataset_id: str
    reports: tuple[ValidationReport, ...]
    ts: datetime

    def __post_init__(self) -> None:
        if not self.dataset_id:
            raise ValueError("ValidationSummary.dataset_id is mandatory")
        if not self.reports:
            raise ValueError("ValidationSummary must contain at least one report")
        if self.ts.tzinfo is None:
            raise ValueError("ValidationSummary.ts must be timezone-aware")

    @property
    def failures(self) -> tuple[ValidationReport, ...]:
        return tuple(r for r in self.reports if r.result is ValidationResult.FAILED)

    @property
    def passed(self) -> bool:
        return not self.failures
