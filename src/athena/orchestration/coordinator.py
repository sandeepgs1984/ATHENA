"""Pipeline Coordinator implementation (P7.4).

Sequentially executes an ordered sequence of (PipelineDefinition, PipelineContract) pairs,
enforcing contract validation generically prior to each pipeline execution and propagating
the functional PipelineContext between runs.
"""

from __future__ import annotations

from collections.abc import Sequence

from athena.config.models import OrchestrationConfig
from athena.orchestration.contract import PipelineContract, validate_contract
from athena.orchestration.engine import PipelineRunner
from athena.orchestration.models import (
    PipelineContext,
    PipelineDefinition,
    PipelineResult,
    PipelineStatus,
)


class PipelineCoordinator:
    """Generic coordinator executing contract-validated pipeline sequences."""

    def __init__(
        self,
        runner: PipelineRunner | None = None,
        config: OrchestrationConfig | None = None,
    ) -> None:
        self._config = config or OrchestrationConfig()
        self._runner = runner or PipelineRunner(self._config)

    def execute_sequence(
        self,
        pipeline_pairs: Sequence[tuple[PipelineDefinition, PipelineContract]],
        initial_context: PipelineContext,
    ) -> tuple[tuple[PipelineResult, ...], PipelineStatus, PipelineContext]:
        """Execute sequence of (definition, contract) pairs sequentially.

        Returns (pipeline_results, overall_status, final_context).
        """
        current_context = initial_context
        results: list[PipelineResult] = []
        overall_status = PipelineStatus.SUCCESS

        for definition, contract in pipeline_pairs:
            # 1. Validate symmetric contract before running pipeline
            validate_contract(contract, current_context)

            # 2. Run pipeline using PipelineRunner
            result = self._runner.run(definition, current_context)
            results.append(result)
            current_context = result.final_context

            # 3. Check failure boundary
            if result.overall_status == PipelineStatus.FAILED:
                overall_status = PipelineStatus.FAILED
                if self._config.stop_on_stage_failure:
                    break

        return tuple(results), overall_status, current_context
