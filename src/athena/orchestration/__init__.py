"""Pipeline Infrastructure, Registration & Integration package (P7.1, P7.2, P7.3, P7.4).

Provides domain-agnostic stage protocols, lightweight immutable context propagation,
pipeline definitions, execution runners, pipeline registration, contract validation,
pipeline coordination, workspace post-processing, and integrated system execution.
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
    "PipelineStage",
    "PipelineStatus",
    "PortfolioAnalyticsStage",
    "PortfolioSnapshotStage",
    "PositionSizingStage",
    "ReportingStage",
    "StageExecutionResult",
    "StageResult",
    "StageStatus",
    "SystemPipelineResult",
    "SystemPipelineRunner",
    "TimelineStage",
    "WorkspaceAssembler",
    "create_execution_pipeline",
    "create_intelligence_pipeline",
    "validate_contract",
    "validate_intelligence_pipeline",
    "validate_pipeline_definition",
]

