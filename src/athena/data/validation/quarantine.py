"""Quarantine mechanism (M1.3).

Invalid datasets must never silently continue through the pipeline. Quarantine
preserves the failure evidence so downstream components can understand exactly
why a dataset was rejected. It DETECTS and RECORDS only — no automatic repair
(correction belongs to future workflows).
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from athena.data.validation.reports import ValidationReport, ValidationSummary


@dataclass(frozen=True, slots=True)
class QuarantineRecord:
    """Immutable record of a rejected dataset and why it was rejected."""

    dataset_id: str
    reason: str
    failed_reports: tuple[ValidationReport, ...]
    quarantined_ts: datetime

    def __post_init__(self) -> None:
        if not self.failed_reports:
            raise ValueError("a QuarantineRecord must preserve at least one failed report")


class QuarantineRegistry:
    """Explicit per-run collector of quarantined datasets (no global state)."""

    def __init__(self) -> None:
        self._records: dict[str, QuarantineRecord] = {}

    def review(self, summary: ValidationSummary) -> QuarantineRecord | None:
        """Quarantine the dataset iff its summary has failures. Returns the record,
        or None if the dataset is clean."""
        failures = summary.failures
        if not failures:
            return None
        reason = "; ".join(f"{r.validation_type.value}: {r.explanation}" for r in failures)
        record = QuarantineRecord(
            dataset_id=summary.dataset_id,
            reason=reason,
            failed_reports=failures,
            quarantined_ts=summary.ts,
        )
        self._records[summary.dataset_id] = record
        return record

    def is_quarantined(self, dataset_id: str) -> bool:
        return dataset_id in self._records

    def get(self, dataset_id: str) -> QuarantineRecord | None:
        return self._records.get(dataset_id)

    @property
    def records(self) -> tuple[QuarantineRecord, ...]:
        return tuple(self._records.values())
