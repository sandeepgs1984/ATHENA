"""Workflow execution result types (M4.1).

Immutable orchestration records. The runtime coordinates existing analytical
engines; it performs no analysis. These types capture what ran, in what order,
with what outcome and timing — never analytical results themselves.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from enum import Enum, unique


@unique
class ExecutionStatus(str, Enum):
    PENDING = "PENDING"
    RUNNING = "RUNNING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"
    SKIPPED = "SKIPPED"


@dataclass(frozen=True, slots=True)
class StageResult:
    """Outcome of one workflow stage. Timing is offset-from-start (deterministic under a fixed clock)."""

    stage_name: str
    status: ExecutionStatus
    started_offset_seconds: float
    duration_seconds: float
    output_keys: tuple[str, ...]
    error: str | None
    explanation: str

    def __post_init__(self) -> None:
        if not self.stage_name:
            raise ValueError("StageResult.stage_name is mandatory")
        if not self.explanation:
            raise ValueError("StageResult.explanation is mandatory")
        if self.status is ExecutionStatus.FAILED and not self.error:
            raise ValueError("a FAILED stage must record its error")
        if self.duration_seconds < 0:
            raise ValueError("StageResult.duration_seconds must be >= 0")

    @property
    def passed(self) -> bool:
        return self.status is ExecutionStatus.COMPLETED


@dataclass(frozen=True, slots=True)
class WorkflowExecution:
    """Immutable record of one workflow execution — the execution report."""

    execution_id: str
    workflow_name: str
    as_of: datetime
    status: ExecutionStatus
    stage_results: tuple[StageResult, ...]
    total_duration_seconds: float
    produced_keys: tuple[str, ...]

    def __post_init__(self) -> None:
        if self.as_of.tzinfo is None:
            raise ValueError("WorkflowExecution.as_of must be timezone-aware")
        if not self.stage_results:
            raise ValueError("WorkflowExecution must contain stage results")

    def stage(self, name: str) -> StageResult | None:
        return next((s for s in self.stage_results if s.stage_name == name), None)

    @property
    def completed(self) -> bool:
        return self.status is ExecutionStatus.COMPLETED
