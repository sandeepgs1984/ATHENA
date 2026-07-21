"""Pipeline Infrastructure, Registration, Integration & Scheduling package (P7.1-P7.5).

Provides domain-agnostic stage protocols, lightweight immutable context propagation,
pipeline definitions, execution runners, pipeline registration, contract validation,
pipeline coordination, workspace post-processing, integrated system execution, and
scheduling-domain bridge adapters.
"""

from athena.orchestration.contract import (
    EXECUTION_PIPELINE_CONTRACT,
    INTELLIGENCE_PIPELINE_CONTRACT,
    PipelineContract,
    validate_contract,
)
from athena.orchestration.coordinator import PipelineCoordinator
from athena.orchestration.engine import PipelineRunner
from athena.orchestration.models import (
    PipelineContext,
    PipelineDefinition,
    PipelineHistory,
    PipelineMetadata,
    PipelineResult,
    PipelineStage,
    PipelineStatus,
    StageExecutionResult,
    StageResult,
    StageStatus,
    SystemPipelineResult,
)
from athena.orchestration.pipelines import (
    INTELLIGENCE_PIPELINE_OPTIONAL_INPUTS,
    INTELLIGENCE_PIPELINE_REQUIRED_INPUTS,
    ExecutionArtifactKey,
    ExecutionStageId,
    IntelligenceArtifactKey,
    IntelligenceStageId,
    create_execution_pipeline,
    create_intelligence_pipeline,
    validate_intelligence_pipeline,
    validate_pipeline_definition,
)
from athena.orchestration.schedule_adapter import SystemScheduleAdapter
from athena.orchestration.schedule_models import (
    PipelineScheduleHistory,
    PipelineScheduleRun,
    ScheduleRunRequest,
)
from athena.orchestration.stages import (
    BrokerTranslationStage,
    CapitalAllocationStage,
    DashboardStage,
    DecisionsLoadStage,
    ExplainabilityStage,
    ExportStage,
    MonitoringStage,
    OrderLifecycleStage,
    OrderPlanningStage,
    PortfolioAnalyticsStage,
    PortfolioSnapshotStage,
    PositionSizingStage,
    ReportingStage,
    TimelineStage,
)
from athena.orchestration.system_runner import SystemPipelineRunner
from athena.orchestration.workspace_adapter import WorkspaceAssembler

__all__ = [
    "EXECUTION_PIPELINE_CONTRACT",
    "INTELLIGENCE_PIPELINE_CONTRACT",
    "INTELLIGENCE_PIPELINE_OPTIONAL_INPUTS",
    "INTELLIGENCE_PIPELINE_REQUIRED_INPUTS",
    "BrokerTranslationStage",
    "CapitalAllocationStage",
    "DashboardStage",
    "DecisionsLoadStage",
    "ExecutionArtifactKey",
    "ExecutionStageId",
    "ExplainabilityStage",
    "ExportStage",
    "IntelligenceArtifactKey",
    "IntelligenceStageId",
    "MonitoringStage",
    "OrderLifecycleStage",
    "OrderPlanningStage",
    "PipelineContext",
    "PipelineContract",
    "PipelineCoordinator",
    "PipelineDefinition",
    "PipelineHistory",
    "PipelineMetadata",
    "PipelineResult",
    "PipelineRunner",
    "PipelineScheduleHistory",
    "PipelineScheduleRun",
    "PipelineStage",
    "PipelineStatus",
    "PortfolioAnalyticsStage",
    "PortfolioSnapshotStage",
    "PositionSizingStage",
    "ReportingStage",
    "ScheduleRunRequest",
    "StageExecutionResult",
    "StageResult",
    "StageStatus",
    "SystemPipelineResult",
    "SystemPipelineRunner",
    "SystemScheduleAdapter",
    "TimelineStage",
    "WorkspaceAssembler",
    "create_execution_pipeline",
    "create_intelligence_pipeline",
    "validate_contract",
    "validate_intelligence_pipeline",
    "validate_pipeline_definition",
]

