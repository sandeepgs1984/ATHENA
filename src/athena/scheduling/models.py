"""Scheduling Framework artifacts (M4.7).

Immutable scheduling definitions, jobs, execution records, and history.
The scheduling framework coordinates WHEN ATHENA executes — it never
changes HOW ATHENA analyzes markets.  Every execution record preserves
references to the upstream artifacts it produced; scheduling decisions
never depend on hidden mutable state.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from datetime import datetime
from enum import Enum, unique
from types import MappingProxyType

from athena.runtime.models import ExecutionStatus


def _frozen_int_map(value: Mapping[str, int]) -> Mapping[str, int]:
    return MappingProxyType(dict(value))


# ------------------------------------------------------------------ enums


@unique
class ScheduleMode(str, Enum):
    """When and why a schedule fires."""

    MANUAL = "MANUAL"
    DAILY = "DAILY"
    WEEKLY = "WEEKLY"
    REPLAY = "REPLAY"
    ONE_TIME = "ONE_TIME"


# ------------------------------------------------------------ definition


@dataclass(frozen=True, slots=True)
class ScheduleDefinition:
    """What to run — a named, mode-labelled schedule template."""

    definition_id: str
    name: str
    mode: ScheduleMode
    description: str
    enabled: bool = True

    def __post_init__(self) -> None:
        if not self.definition_id:
            raise ValueError("ScheduleDefinition.definition_id is mandatory")
        if not self.name:
            raise ValueError("ScheduleDefinition.name is mandatory")
        if not self.description:
            raise ValueError("ScheduleDefinition.description is mandatory")

    def to_dict(self) -> dict[str, object]:
        return {
            "definition_id": self.definition_id, "name": self.name,
            "mode": self.mode.value, "description": self.description,
            "enabled": self.enabled,
        }


# ------------------------------------------------------------------- job


@dataclass(frozen=True, slots=True)
class ScheduledJob:
    """When to run — a scheduled instance of a definition."""

    job_id: str
    definition_id: str
    definition_name: str
    mode: ScheduleMode
    scheduled_for: datetime

    def __post_init__(self) -> None:
        if not self.job_id:
            raise ValueError("ScheduledJob.job_id is mandatory")
        if self.scheduled_for.tzinfo is None:
            raise ValueError("ScheduledJob.scheduled_for must be timezone-aware")

    def to_dict(self) -> dict[str, object]:
        return {
            "job_id": self.job_id, "definition_id": self.definition_id,
            "definition_name": self.definition_name, "mode": self.mode.value,
            "scheduled_for": self.scheduled_for.isoformat(),
        }


# -------------------------------------------------------------- references


@dataclass(frozen=True, slots=True)
class ExecutionReferences:
    """Cross-references to upstream artifacts produced during execution."""

    scan_id: str | None = None
    watchlist_snapshot_id: str | None = None
    strategy_execution_id: str | None = None
    analytics_report_id: str | None = None
    backtest_run_id: str | None = None

    def to_dict(self) -> dict[str, object]:
        return {
            "scan_id": self.scan_id,
            "watchlist_snapshot_id": self.watchlist_snapshot_id,
            "strategy_execution_id": self.strategy_execution_id,
            "analytics_report_id": self.analytics_report_id,
            "backtest_run_id": self.backtest_run_id,
        }


# -------------------------------------------------------------- execution


@dataclass(frozen=True, slots=True)
class ScheduleExecution:
    """What happened — immutable record of one scheduled execution."""

    execution_id: str
    job_id: str
    definition_id: str
    definition_name: str
    mode: ScheduleMode
    status: ExecutionStatus
    as_of: datetime
    references: ExecutionReferences
    duration_seconds: float
    note: str

    def __post_init__(self) -> None:
        if not self.execution_id:
            raise ValueError("ScheduleExecution.execution_id is mandatory")
        if self.as_of.tzinfo is None:
            raise ValueError("ScheduleExecution.as_of must be timezone-aware")
        if not self.note:
            raise ValueError("ScheduleExecution.note is mandatory")

    def to_dict(self) -> dict[str, object]:
        return {
            "execution_id": self.execution_id, "job_id": self.job_id,
            "definition_id": self.definition_id,
            "definition_name": self.definition_name,
            "mode": self.mode.value, "status": self.status.value,
            "as_of": self.as_of.isoformat(),
            "references": self.references.to_dict(),
            "duration_seconds": self.duration_seconds, "note": self.note,
        }


# --------------------------------------------------------------- history


@dataclass(frozen=True, slots=True)
class ScheduleHistory:
    """Append-only execution history.  Immutable — ``record()`` returns a new instance."""

    executions: tuple[ScheduleExecution, ...] = ()

    def record(self, execution: ScheduleExecution) -> ScheduleHistory:
        """Return a new history with *execution* appended."""
        return ScheduleHistory(executions=self.executions + (execution,))

    def for_definition(self, definition_id: str) -> tuple[ScheduleExecution, ...]:
        """All executions that ran under *definition_id*."""
        return tuple(e for e in self.executions if e.definition_id == definition_id)

    def for_mode(self, mode: ScheduleMode) -> tuple[ScheduleExecution, ...]:
        """All executions with the given scheduling mode."""
        return tuple(e for e in self.executions if e.mode is mode)

    def to_dict(self) -> dict[str, object]:
        return {"executions": [e.to_dict() for e in self.executions]}


# --------------------------------------------------------------- summary


@dataclass(frozen=True, slots=True)
class ScheduleSummary:
    """Aggregated counts across the execution history."""

    total_executions: int
    completed: int
    failed: int
    by_mode: Mapping[str, int]
    by_definition: Mapping[str, int]

    def __post_init__(self) -> None:
        object.__setattr__(self, "by_mode", _frozen_int_map(self.by_mode))
        object.__setattr__(self, "by_definition", _frozen_int_map(self.by_definition))

    def to_dict(self) -> dict[str, object]:
        return {
            "total_executions": self.total_executions,
            "completed": self.completed, "failed": self.failed,
            "by_mode": dict(self.by_mode),
            "by_definition": dict(self.by_definition),
        }
