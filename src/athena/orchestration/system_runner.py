"""System Pipeline Runner implementation (P7.4).

High-level system entry point coordinating generic pipeline execution (via PipelineCoordinator)
and workspace post-processing (via WorkspaceAssembler) across explicit failure boundaries.
"""

from __future__ import annotations

from athena.config.models import OrchestrationConfig, WorkspaceConfig
from athena.orchestration.contract import (
    EXECUTION_PIPELINE_CONTRACT,
    INTELLIGENCE_PIPELINE_CONTRACT,
    PipelineContract,
)
from athena.orchestration.coordinator import PipelineCoordinator
from athena.orchestration.models import (
    PipelineContext,
    PipelineDefinition,
    PipelineStatus,
    SystemPipelineResult,
)
from athena.orchestration.workspace_adapter import WorkspaceAssembler
from athena.workspace.engine import UnifiedIntelligenceWorkspace


class SystemPipelineRunner:
    """Integrated system runner coordinating Execution Pipeline, Intelligence Pipeline, and Workspace Assembly."""

    def __init__(
        self,
        coordinator: PipelineCoordinator | None = None,
        workspace_assembler: WorkspaceAssembler | None = None,
        orchestration_config: OrchestrationConfig | None = None,
        workspace_config: WorkspaceConfig | None = None,
    ) -> None:
        self._coordinator = coordinator or PipelineCoordinator(config=orchestration_config)
        self._workspace_assembler = workspace_assembler or WorkspaceAssembler(
            UnifiedIntelligenceWorkspace(workspace_config)
        )
        self._counter = 0

    def run_system_cycle(
        self,
        execution_def: PipelineDefinition,
        intelligence_def: PipelineDefinition,
        initial_context: PipelineContext,
        *,
        execution_contract: PipelineContract = EXECUTION_PIPELINE_CONTRACT,
        intelligence_contract: PipelineContract = INTELLIGENCE_PIPELINE_CONTRACT,
    ) -> SystemPipelineResult:
        """Run full ATHENA system cycle across Execution Pipeline and Intelligence Pipeline."""
        if initial_context.as_of.tzinfo is None:
            raise ValueError("initial_context.as_of datetime must be timezone-aware")

        # 1. Execute pipeline sequence via PipelineCoordinator
        pipeline_pairs = [
            (execution_def, execution_contract),
            (intelligence_def, intelligence_contract),
        ]

        runs, overall_status, final_context = self._coordinator.execute_sequence(
            pipeline_pairs, initial_context
        )

        ws_snapshot = None
        # 2. Assemble Workspace if both pipelines succeeded
        if overall_status == PipelineStatus.SUCCESS:
            try:
                ws_snapshot = self._workspace_assembler.assemble(final_context)
            except Exception:
                overall_status = PipelineStatus.FAILED
                ws_snapshot = None

        run_id = f"sysrun-{self._next_counter():04d}"
        return SystemPipelineResult(
            run_id=run_id,
            as_of=initial_context.as_of,
            pipeline_runs=runs,
            workspace_snapshot=ws_snapshot,
            overall_status=overall_status,
            final_context=final_context,
        )

    def _next_counter(self) -> int:
        self._counter += 1
        return self._counter
