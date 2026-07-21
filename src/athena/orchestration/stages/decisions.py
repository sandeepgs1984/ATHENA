"""Decisions Load stage implementation (P7.2).

Validates or publishes candidate Decision objects in the PipelineContext
under ExecutionArtifactKey.DECISIONS.
"""

from __future__ import annotations

from collections.abc import Sequence

from athena.domain.decision import Decision
from athena.orchestration.models import (
    PipelineContext,
    StageExecutionResult,
    StageResult,
    StageStatus,
)
from athena.orchestration.pipelines.keys import ExecutionArtifactKey, ExecutionStageId


class DecisionsLoadStage:
    """Stage that ensures candidate decisions are present in pipeline context."""

    def __init__(self, decisions: Sequence[Decision] | None = None) -> None:
        self._default_decisions = tuple(decisions) if decisions is not None else None

    @property
    def stage_id(self) -> str:
        return ExecutionStageId.DECISIONS_LOAD.value

    @property
    def name(self) -> str:
        return "Decisions Load"

    def execute(self, context: PipelineContext) -> StageExecutionResult:
        decisions = context.get(ExecutionArtifactKey.DECISIONS.value)

        if decisions is None and self._default_decisions is not None:
            decisions = self._default_decisions

        if decisions is None:
            result = StageResult(
                stage_id=self.stage_id,
                status=StageStatus.FAILED,
                message="No decisions provided in context or default decisions configuration",
            )
            return StageExecutionResult(stage_result=result, context=context)

        updated_context = context.with_value(
            ExecutionArtifactKey.DECISIONS.value, decisions
        )
        count = len(decisions) if isinstance(decisions, Sequence) else 0
        result = StageResult(
            stage_id=self.stage_id,
            status=StageStatus.SUCCESS,
            message=f"Loaded {count} candidate decision(s)",
            output_key=ExecutionArtifactKey.DECISIONS.value,
        )
        return StageExecutionResult(stage_result=result, context=updated_context)
