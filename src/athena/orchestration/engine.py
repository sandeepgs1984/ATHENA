"""Generic Pipeline Infrastructure runner implementation (P7.1).

Executes ordered pipeline stages with functional context propagation,
strict failure isolation, and zero coupling to business domains.
"""

from __future__ import annotations

from athena.config.models import OrchestrationConfig
from athena.orchestration.models import (
    PipelineContext,
    PipelineDefinition,
    PipelineHistory,
    PipelineResult,
    PipelineStatus,
    StageExecutionResult,
    StageResult,
    StageStatus,
)


class PipelineRunner:
    """Deterministic, domain-agnostic generic pipeline runner."""

    def __init__(self, config: OrchestrationConfig | None = None) -> None:
        self._config = config or OrchestrationConfig()
        self._counter = 0
        self._history = PipelineHistory()

    @property
    def history(self) -> PipelineHistory:
        """Get accumulated pipeline history."""
        return self._history

    def run(
        self, definition: PipelineDefinition, initial_context: PipelineContext
    ) -> PipelineResult:
        """Run a PipelineDefinition starting from initial_context."""
        if initial_context.as_of.tzinfo is None:
            raise ValueError("initial_context.as_of datetime must be timezone-aware")

        current_context = initial_context
        stage_results: list[StageResult] = []
        overall_status = PipelineStatus.SUCCESS

        for stage in definition.stages:
            try:
                exec_result: StageExecutionResult = stage.execute(current_context)
                stage_results.append(exec_result.stage_result)
                current_context = exec_result.context

                if exec_result.stage_result.status == StageStatus.FAILED:
                    overall_status = PipelineStatus.FAILED
                    if self._config.stop_on_stage_failure:
                        break

            except Exception as exc:
                fail_result = StageResult(
                    stage_id=stage.stage_id,
                    status=StageStatus.FAILED,
                    message=f"Unhandled stage error: {exc}",
                )
                stage_results.append(fail_result)
                overall_status = PipelineStatus.FAILED
                if self._config.stop_on_stage_failure:
                    break

        run_id = f"piprun-{self._next_counter():04d}"
        result = PipelineResult(
            pipeline_run_id=run_id,
            metadata=definition.metadata,
            as_of=initial_context.as_of,
            stages=tuple(stage_results),
            overall_status=overall_status,
            final_context=current_context,
        )

        if self._config.record_history:
            self._history = self._history.record(result)

        return result

    def _next_counter(self) -> int:
        self._counter += 1
        return self._counter
