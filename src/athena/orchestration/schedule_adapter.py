"""System Schedule Adapter implementation (P7.5).

Bridges the scheduling domain (M4.7) to the orchestration runtime (P7.4).
The adapter accepts a ScheduleRunRequest, constructs a valid PipelineContext,
delegates execution to SystemPipelineRunner, and returns a PipelineScheduleRun.

Neither M4.7 scheduling models nor P7.1-P7.4 orchestration models are modified.
"""

from __future__ import annotations

import time

from athena.orchestration.contract import (
    EXECUTION_PIPELINE_CONTRACT,
    INTELLIGENCE_PIPELINE_CONTRACT,
    PipelineContract,
)
from athena.orchestration.models import (
    PipelineContext,
    PipelineDefinition,
)
from athena.orchestration.pipelines.keys import ExecutionArtifactKey
from athena.orchestration.schedule_models import (
    PipelineScheduleHistory,
    PipelineScheduleRun,
    ScheduleRunRequest,
)
from athena.orchestration.system_runner import SystemPipelineRunner


class _ScheduleContextBuilder:
    """Private helper: constructs a valid PipelineContext from a ScheduleRunRequest.

    Separates context construction from adapter coordination.
    Not part of the public API — internal to this module only.
    """

    @staticmethod
    def build(request: ScheduleRunRequest) -> PipelineContext:
        """Build an initial PipelineContext satisfying the Execution Pipeline Contract."""
        return PipelineContext(
            run_id=request.job.job_id,
            as_of=request.as_of,
            data={
                ExecutionArtifactKey.DECISIONS.value: list(request.decisions),
                ExecutionArtifactKey.CURRENT_PRICES.value: dict(request.current_prices),
            },
        )


class SystemScheduleAdapter:
    """Orchestration-layer bridge from the scheduling domain to SystemPipelineRunner.

    Accepts a ScheduleRunRequest, delegates execution to the runtime, and
    returns a PipelineScheduleRun. The scheduling domain never touches
    PipelineDefinition, stage topology, contracts, or artifact keys.

    Failure recording policy:
    - Request rejected (ScheduleRunRequest.__post_init__ raises ValueError):
        No execution begins. No history record. Exception propagates to caller.
    - Execution started (any failure during pipeline or workspace execution):
        Always produces a PipelineScheduleRun. Always recorded in history.
    """

    def __init__(
        self,
        system_runner: SystemPipelineRunner,
        execution_def: PipelineDefinition,
        intelligence_def: PipelineDefinition,
        *,
        execution_contract: PipelineContract = EXECUTION_PIPELINE_CONTRACT,
        intelligence_contract: PipelineContract = INTELLIGENCE_PIPELINE_CONTRACT,
    ) -> None:
        self._runner = system_runner
        self._execution_def = execution_def
        self._intelligence_def = intelligence_def
        self._execution_contract = execution_contract
        self._intelligence_contract = intelligence_contract
        self._history = PipelineScheduleHistory()
        self._counter = 0

    def execute(self, request: ScheduleRunRequest) -> PipelineScheduleRun:
        """Execute a scheduled pipeline cycle.

        Args:
            request: A valid ScheduleRunRequest. Validation (tz-aware as_of,
                non-empty decisions) has already fired at request construction.

        Returns:
            PipelineScheduleRun wrapping the SystemPipelineResult.

        Raises:
            ValueError: If request construction was invalid (caller bug — should
                not reach execute() in normal flow).
        """
        # 1. Build initial context (request already validated at construction time)
        initial_context = _ScheduleContextBuilder.build(request)

        # 2. Measure wall-clock duration from this point — execution has started
        start = time.monotonic()

        # 3. Delegate entirely to SystemPipelineRunner
        system_result = self._runner.run_system_cycle(
            self._execution_def,
            self._intelligence_def,
            initial_context,
            execution_contract=self._execution_contract,
            intelligence_contract=self._intelligence_contract,
        )

        # 4. Wrap as scheduling envelope
        duration = round(time.monotonic() - start, 6)
        run = PipelineScheduleRun(
            schedule_run_id=self._next_run_id(),
            job_id=request.job.job_id,
            definition_id=request.job.definition_id,
            system_result=system_result,
            duration_seconds=duration,
        )

        # 5. Record in history — always, because execution started
        self._history = self._history.record(run)
        return run

    @property
    def history(self) -> PipelineScheduleHistory:
        """Read-only view of the current execution history."""
        return self._history

    def _next_run_id(self) -> str:
        self._counter += 1
        return f"schedrun-{self._counter:04d}"
