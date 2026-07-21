"""Pipeline Scheduler bridge models (P7.5).

Provides the scheduling-domain input contract (ScheduleRunRequest) and the
orchestration-layer bridge artifacts (PipelineScheduleRun, PipelineScheduleHistory)
that connect the M4.7 scheduling subsystem to the P7.4 runtime.

No M4.7 scheduling models are modified; no P7.1-P7.4 orchestration models are modified.
"""

from __future__ import annotations

import json
from collections.abc import Mapping
from dataclasses import dataclass, field
from datetime import datetime
from decimal import Decimal

from athena.domain.decision import Decision
from athena.orchestration.models import PipelineStatus, SystemPipelineResult
from athena.scheduling.models import ScheduledJob


@dataclass(frozen=True, slots=True)
class ScheduleRunRequest:
    """Input contract for a scheduled pipeline cycle execution.

    Bundles all caller-provided inputs into a stable, versioned request object.
    Future additions (dry_run, replay_mode, portfolio_snapshot, trigger_source, etc.)
    add fields here without changing the adapter's execute() signature.

    Validation fires at construction: a failed __post_init__ raises ValueError
    and prevents execution from starting (request-rejected lifecycle phase).
    """

    job: ScheduledJob
    decisions: tuple[Decision, ...]
    current_prices: Mapping[str, Decimal]
    as_of: datetime

    def __post_init__(self) -> None:
        if not self.decisions:
            raise ValueError("ScheduleRunRequest.decisions must be non-empty")
        if self.as_of.tzinfo is None:
            raise ValueError("ScheduleRunRequest.as_of must be timezone-aware")

    def to_dict(self) -> dict[str, object]:
        return {
            "job": self.job.to_dict(),
            "decisions": [d.decision_id for d in self.decisions],
            "current_prices": {k: str(v) for k, v in self.current_prices.items()},
            "as_of": self.as_of.isoformat(),
        }


@dataclass(frozen=True, slots=True)
class PipelineScheduleRun:
    """Immutable scheduling envelope for one scheduled pipeline cycle.

    The authoritative execution state (status, pipeline_runs, workspace_snapshot,
    final_context, as_of, run_id) lives inside system_result.
    This record captures only the scheduling-domain envelope.
    """

    schedule_run_id: str
    job_id: str
    definition_id: str
    system_result: SystemPipelineResult
    duration_seconds: float

    def __post_init__(self) -> None:
        if not self.schedule_run_id:
            raise ValueError("PipelineScheduleRun.schedule_run_id is mandatory")
        if not self.job_id:
            raise ValueError("PipelineScheduleRun.job_id is mandatory")
        if self.duration_seconds < 0:
            raise ValueError("PipelineScheduleRun.duration_seconds must be non-negative")

    def to_dict(self) -> dict[str, object]:
        return {
            "schedule_run_id": self.schedule_run_id,
            "job_id": self.job_id,
            "definition_id": self.definition_id,
            "system_result": self.system_result.to_dict(),
            "duration_seconds": self.duration_seconds,
        }

    def to_json(self) -> str:
        """Deterministic JSON representation."""
        return json.dumps(self.to_dict(), sort_keys=True, indent=2)


@dataclass(frozen=True, slots=True)
class PipelineScheduleHistory:
    """Immutable append-only record of scheduled pipeline cycle executions.

    record() returns a new instance; the original is never mutated.
    """

    runs: tuple[PipelineScheduleRun, ...] = field(default_factory=tuple)

    def record(self, run: PipelineScheduleRun) -> PipelineScheduleHistory:
        """Return a new history with *run* appended."""
        return PipelineScheduleHistory(runs=(*self.runs, run))

    def for_job(self, job_id: str) -> tuple[PipelineScheduleRun, ...]:
        """All runs for the given job_id."""
        return tuple(r for r in self.runs if r.job_id == job_id)

    def for_status(self, status: PipelineStatus) -> tuple[PipelineScheduleRun, ...]:
        """All runs whose system_result carries the given overall_status."""
        return tuple(
            r for r in self.runs if r.system_result.overall_status == status
        )

    def summarize(self) -> dict[str, object]:
        total = len(self.runs)
        success = sum(
            1 for r in self.runs
            if r.system_result.overall_status == PipelineStatus.SUCCESS
        )
        return {
            "total": total,
            "success": success,
            "failed": total - success,
        }

    def to_dict(self) -> dict[str, object]:
        return {"runs": [r.to_dict() for r in self.runs]}
