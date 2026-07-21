"""Daily scan result types (M4.2).

Immutable scan artifacts. The scanner coordinates workflow execution across the
universe; these types record what ran and what ATHENA concluded per instrument —
no analytical values are computed here.
"""

from __future__ import annotations

from collections.abc import Callable, Mapping
from dataclasses import dataclass
from datetime import datetime
from types import MappingProxyType

from athena.decision.models import DecisionOutcome
from athena.reporting.models import DecisionReport
from athena.runtime.models import ExecutionStatus, WorkflowExecution
from athena.runtime.workflow import WorkflowDefinition


@dataclass(frozen=True, slots=True)
class ScanCapture:
    """What a per-instrument workflow captured for reporting after execution."""

    outcome: DecisionOutcome
    scoring: object | None = None
    confidence: object | None = None
    risk: object | None = None
    evidence_bundle: object | None = None
    indicators: Mapping[object, object] | None = None


@dataclass(frozen=True, slots=True)
class InstrumentPlan:
    """A per-instrument workflow plus a collector for its captured outcome.

    ``definition`` is executed by the shared WorkflowEngine; ``collect`` returns
    the DecisionOutcome (and optional report inputs) captured by the workflow's
    stages, or None if the instrument produced no decision.
    """

    definition: WorkflowDefinition
    collect: Callable[[], ScanCapture | None]


@dataclass(frozen=True, slots=True)
class InstrumentScanResult:
    """Outcome of scanning one instrument."""

    instrument_id: str
    status: ExecutionStatus
    decision_type: str | None
    workflow_execution: WorkflowExecution | None
    report: DecisionReport | None
    note: str

    def __post_init__(self) -> None:
        if not self.instrument_id:
            raise ValueError("InstrumentScanResult.instrument_id is mandatory")
        if not self.note:
            raise ValueError("InstrumentScanResult.note is mandatory")


@dataclass(frozen=True, slots=True)
class ScanStatistics:
    """Execution counts for a scan."""

    total: int
    successful: int
    failed: int
    skipped: int

    def __post_init__(self) -> None:
        if self.successful + self.failed + self.skipped != self.total:
            raise ValueError("ScanStatistics counts must sum to total")


@dataclass(frozen=True, slots=True)
class ScanSummary:
    """Distribution of decision outcomes across successful scans."""

    decision_counts: Mapping[str, int]

    def __post_init__(self) -> None:
        object.__setattr__(self, "decision_counts", MappingProxyType(dict(self.decision_counts)))


@dataclass(frozen=True, slots=True)
class DailyScanReport:
    """Immutable report of a full-universe scan."""

    scan_id: str
    as_of: datetime
    results: tuple[InstrumentScanResult, ...]
    statistics: ScanStatistics
    summary: ScanSummary

    def __post_init__(self) -> None:
        if self.as_of.tzinfo is None:
            raise ValueError("DailyScanReport.as_of must be timezone-aware")

    def result_for(self, instrument_id: str) -> InstrumentScanResult | None:
        return next((r for r in self.results if r.instrument_id == instrument_id), None)

    def to_dict(self) -> dict[str, object]:
        return {
            "scan_id": self.scan_id,
            "as_of": self.as_of.isoformat(),
            "statistics": {
                "total": self.statistics.total, "successful": self.statistics.successful,
                "failed": self.statistics.failed, "skipped": self.statistics.skipped,
            },
            "summary": {"decision_counts": dict(self.summary.decision_counts)},
            "results": [
                {"instrument_id": r.instrument_id, "status": r.status.value,
                 "decision_type": r.decision_type,
                 "workflow_execution_id": (r.workflow_execution.execution_id
                                           if r.workflow_execution else None),
                 "has_report": r.report is not None, "note": r.note}
                for r in self.results
            ],
        }


#: A per-instrument pipeline builder: given an instrument id, return its plan
#: (or None to skip the instrument).
PipelineBuilder = Callable[[str], "InstrumentPlan | None"]
