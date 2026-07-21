"""Workflow execution report (M4.1).

Presentation-only summary of a WorkflowExecution — machine-readable (``to_dict``)
and human-readable (``to_text``). Adds no information beyond the execution record.
"""

from __future__ import annotations

import json
from collections.abc import Mapping
from dataclasses import dataclass
from types import MappingProxyType

from athena.runtime.models import ExecutionStatus, WorkflowExecution


@dataclass(frozen=True, slots=True)
class WorkflowReport:
    """Immutable, faithful summary of a workflow execution."""

    execution_id: str
    workflow_name: str
    status: str
    machine: Mapping[str, object]
    text: str

    def __post_init__(self) -> None:
        object.__setattr__(self, "machine", MappingProxyType(dict(self.machine)))

    @classmethod
    def of(cls, execution: WorkflowExecution) -> WorkflowReport:
        counts: dict[str, int] = {s.value: 0 for s in ExecutionStatus}
        for r in execution.stage_results:
            counts[r.status.value] += 1
        machine = {
            "execution_id": execution.execution_id,
            "workflow": execution.workflow_name,
            "as_of": execution.as_of.isoformat(),
            "status": execution.status.value,
            "total_duration_seconds": execution.total_duration_seconds,
            "stage_counts": {k: v for k, v in counts.items() if v},
            "produced_keys": list(execution.produced_keys),
            "stages": [
                {"stage": r.stage_name, "status": r.status.value,
                 "started_offset_seconds": r.started_offset_seconds,
                 "duration_seconds": r.duration_seconds,
                 "output_keys": list(r.output_keys), "error": r.error,
                 "explanation": r.explanation}
                for r in execution.stage_results
            ],
        }
        lines = [
            "ATHENA WORKFLOW EXECUTION REPORT",
            "=" * 60,
            f"Workflow : {execution.workflow_name}",
            f"Status   : {execution.status.value}",
            f"As of    : {execution.as_of.isoformat()}",
            f"Duration : {execution.total_duration_seconds:.6f}s",
            "",
            "STAGES",
            "-" * 60,
        ]
        for r in execution.stage_results:
            mark = {"COMPLETED": "OK  ", "FAILED": "FAIL", "SKIPPED": "SKIP"}.get(
                r.status.value, r.status.value)
            line = f"  [{mark}] {r.stage_name}: {r.explanation}"
            if r.error:
                line += f" (error: {r.error})"
            lines.append(line)
        return cls(execution_id=execution.execution_id, workflow_name=execution.workflow_name,
                   status=execution.status.value, machine=machine, text="\n".join(lines))

    def to_dict(self) -> dict[str, object]:
        return json.loads(json.dumps(dict(self.machine)))

    def to_json(self) -> str:
        return json.dumps(dict(self.machine), sort_keys=True, indent=2)

    def to_text(self) -> str:
        return self.text
