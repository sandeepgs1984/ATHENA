"""Generic Pipeline Infrastructure domain models (P7.1).

Immutable models for pipeline stage execution, functional context propagation,
metadata, definitions, results, and history.

The orchestration framework has ZERO knowledge of ATHENA business domains.
"""

from __future__ import annotations

import json
from collections.abc import Mapping
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from types import MappingProxyType
from typing import TYPE_CHECKING, Protocol, runtime_checkable

if TYPE_CHECKING:
    pass


class StageStatus(str, Enum):
    """Execution status of an individual pipeline stage."""

    SUCCESS = "SUCCESS"
    SKIPPED = "SKIPPED"
    FAILED = "FAILED"


class PipelineStatus(str, Enum):
    """Overall status of a pipeline run."""

    SUCCESS = "SUCCESS"
    FAILED = "FAILED"


@dataclass(frozen=True, slots=True)
class PipelineContext:
    """Immutable, lightweight state container passed sequentially between stages."""

    run_id: str
    as_of: datetime
    data: Mapping[str, object] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not self.run_id:
            raise ValueError("PipelineContext mandatory run_id missing")
        if self.as_of.tzinfo is None:
            raise ValueError("PipelineContext.as_of must be timezone-aware")
        object.__setattr__(self, "data", MappingProxyType(dict(self.data)))

    def get(self, key: str, default: object = None) -> object:
        """Retrieve a value from the pipeline context."""
        return self.data.get(key, default)

    def with_value(self, key: str, value: object) -> PipelineContext:
        """Return a new PipelineContext with key set to value (functional immutability)."""
        new_data = dict(self.data)
        new_data[key] = value
        return PipelineContext(run_id=self.run_id, as_of=self.as_of, data=new_data)

    def to_dict(self) -> dict[str, object]:
        return {
            "run_id": self.run_id,
            "as_of": self.as_of.isoformat(),
            "data": json.loads(json.dumps({k: str(v) for k, v in self.data.items()})),
        }


@dataclass(frozen=True, slots=True)
class StageResult:
    """Execution result of a single pipeline stage (excluding non-deterministic timing)."""

    stage_id: str
    status: StageStatus
    message: str
    output_key: str | None = None

    def __post_init__(self) -> None:
        if not self.stage_id:
            raise ValueError("StageResult mandatory stage_id missing")

    def to_dict(self) -> dict[str, object]:
        return {
            "stage_id": self.stage_id,
            "status": self.status.value,
            "message": self.message,
            "output_key": self.output_key,
        }


@dataclass(frozen=True, slots=True)
class StageExecutionResult:
    """Combined output of executing a stage: status result and updated context."""

    stage_result: StageResult
    context: PipelineContext

    def to_dict(self) -> dict[str, object]:
        return {
            "stage_result": self.stage_result.to_dict(),
            "context": self.context.to_dict(),
        }


@dataclass(frozen=True, slots=True)
class PipelineMetadata:
    """Metadata describing a pipeline definition."""

    definition_id: str
    version: str
    name: str
    description: str
    metadata: Mapping[str, object] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not self.definition_id or not self.version or not self.name:
            raise ValueError("PipelineMetadata mandatory fields missing")
        object.__setattr__(self, "metadata", MappingProxyType(dict(self.metadata)))

    def to_dict(self) -> dict[str, object]:
        return {
            "definition_id": self.definition_id,
            "version": self.version,
            "name": self.name,
            "description": self.description,
            "metadata": json.loads(json.dumps(dict(self.metadata))),
        }


@runtime_checkable
class PipelineStage(Protocol):
    """Protocol for executable pipeline stages."""

    @property
    def stage_id(self) -> str:
        ...

    @property
    def name(self) -> str:
        ...

    def execute(self, context: PipelineContext) -> StageExecutionResult:
        ...


@dataclass(frozen=True, slots=True)
class PipelineDefinition:
    """Immutable collection of pipeline stages and metadata."""

    metadata: PipelineMetadata
    stages: tuple[PipelineStage, ...]

    def __post_init__(self) -> None:
        if isinstance(self.stages, list):
            object.__setattr__(self, "stages", tuple(self.stages))

    def to_dict(self) -> dict[str, object]:
        return {
            "metadata": self.metadata.to_dict(),
            "stages": [
                {"stage_id": s.stage_id, "name": s.name} for s in self.stages
            ],
        }


@dataclass(frozen=True, slots=True)
class PipelineResult:
    """Immutable result of a complete pipeline execution."""

    pipeline_run_id: str
    metadata: PipelineMetadata
    as_of: datetime
    stages: tuple[StageResult, ...]
    overall_status: PipelineStatus
    final_context: PipelineContext

    def __post_init__(self) -> None:
        if not self.pipeline_run_id:
            raise ValueError("PipelineResult mandatory pipeline_run_id missing")
        if self.as_of.tzinfo is None:
            raise ValueError("PipelineResult.as_of must be timezone-aware")

    def to_dict(self) -> dict[str, object]:
        return {
            "pipeline_run_id": self.pipeline_run_id,
            "metadata": self.metadata.to_dict(),
            "as_of": self.as_of.isoformat(),
            "stages": [s.to_dict() for s in self.stages],
            "overall_status": self.overall_status.value,
            "final_context": self.final_context.to_dict(),
        }

    def to_json(self) -> str:
        """Deterministic JSON representation."""
        return json.dumps(self.to_dict(), sort_keys=True, indent=2)


@dataclass(frozen=True, slots=True)
class PipelineHistory:
    """Append-only record of completed pipeline executions."""

    records: tuple[PipelineResult, ...] = ()

    def record(self, result: PipelineResult) -> PipelineHistory:
        """Return a new history with result appended."""
        return PipelineHistory(records=(*self.records, result))

    def to_dict(self) -> dict[str, object]:
        return {"records": [r.to_dict() for r in self.records]}
