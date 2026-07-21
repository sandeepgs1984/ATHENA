"""Declarative ATHENA Intelligence Pipeline registration and validation (P7.3).

Assembles canonical ATHENA intelligence stages into an immutable PipelineDefinition.
Performs topology validation prior to returning.

The Intelligence Pipeline consists of:
  - Four independent producer stages (Reporting, Explainability, Dashboard, Monitoring)
  - One intermediate aggregator stage (Timeline)
  - One terminal aggregator stage (Export)

All stages consume execution artifacts from the pipeline context. Cross-pipeline
context threading (feeding the Execution Pipeline's output context into the
Intelligence Pipeline's input) is deferred to P7.4.

Explicit input contract:
  INTELLIGENCE_PIPELINE_REQUIRED_INPUTS  — execution artifacts that must be present
  INTELLIGENCE_PIPELINE_OPTIONAL_INPUTS  — execution artifacts that enrich outputs
"""

from __future__ import annotations

from collections.abc import Sequence

from athena.errors import OrchestrationError
from athena.orchestration.models import (
    PipelineDefinition,
    PipelineMetadata,
    PipelineStage,
)
from athena.orchestration.pipelines.keys import (
    ExecutionArtifactKey,
    IntelligenceStageId,
)

# ---------------------------------------------------------------------------
# Explicit execution-artifact input contract
# ---------------------------------------------------------------------------

INTELLIGENCE_PIPELINE_REQUIRED_INPUTS: frozenset[ExecutionArtifactKey] = frozenset({
    ExecutionArtifactKey.PORTFOLIO_SNAPSHOT,
    ExecutionArtifactKey.PERFORMANCE_SNAPSHOT,
    ExecutionArtifactKey.EXECUTION_STATE,
    ExecutionArtifactKey.ALLOCATION_PLAN,
})
"""Execution artifacts that MUST be present in context before the Intelligence Pipeline runs."""

INTELLIGENCE_PIPELINE_OPTIONAL_INPUTS: frozenset[ExecutionArtifactKey] = frozenset({
    ExecutionArtifactKey.SIZING_PLAN,
    ExecutionArtifactKey.EXECUTION_PLAN,
    ExecutionArtifactKey.BROKER_PLAN,
})
"""Execution artifacts that MAY be present; their absence degrades output richness but does not fail."""

# ---------------------------------------------------------------------------
# Expected topology constants
# ---------------------------------------------------------------------------

_EXPECTED_STAGE_COUNT = 6
_EXPECTED_INDEPENDENT_PRODUCER_IDS = frozenset({
    IntelligenceStageId.REPORTING.value,
    IntelligenceStageId.EXPLAINABILITY.value,
    IntelligenceStageId.DASHBOARD.value,
    IntelligenceStageId.MONITORING.value,
})
_EXPECTED_TERMINAL_STAGE_ID = IntelligenceStageId.EXPORT.value


def validate_intelligence_pipeline(definition: PipelineDefinition) -> None:
    """Validate the intelligence pipeline topology at definition time.

    Checks:
    - Correct stage count (6)
    - No duplicate stage IDs
    - All four expected independent producer stage IDs are present
    - The terminal Export stage ID is present
    """
    if len(definition.stages) != _EXPECTED_STAGE_COUNT:
        raise OrchestrationError(
            f"Intelligence pipeline expects {_EXPECTED_STAGE_COUNT} stages, "
            f"got {len(definition.stages)}"
        )

    seen_ids: set[str] = set()
    for stage in definition.stages:
        sid = stage.stage_id
        if not sid:
            raise OrchestrationError("Pipeline stage must have a non-empty stage_id")
        if sid in seen_ids:
            raise OrchestrationError(f"Duplicate stage_id '{sid}' in pipeline definition")
        seen_ids.add(sid)

    missing_producers = _EXPECTED_INDEPENDENT_PRODUCER_IDS - seen_ids
    if missing_producers:
        raise OrchestrationError(
            f"Intelligence pipeline missing required producer stage ID(s): {missing_producers}"
        )

    if _EXPECTED_TERMINAL_STAGE_ID not in seen_ids:
        raise OrchestrationError(
            f"Intelligence pipeline missing terminal stage '{_EXPECTED_TERMINAL_STAGE_ID}'"
        )


def create_intelligence_pipeline(
    stages: Sequence[PipelineStage],
    *,
    version: str = "1.0.0",
    description: str = "Canonical ATHENA intelligence-to-export pipeline",
) -> PipelineDefinition:
    """Construct and validate an immutable PipelineDefinition for ATHENA intelligence stages.

    Pure declarative pipeline builder. Does not execute or bind runner engines.
    The caller is responsible for instantiating and injecting stage engine dependencies.
    """
    if not stages:
        raise OrchestrationError("Cannot create intelligence pipeline with empty stages sequence")

    metadata = PipelineMetadata(
        definition_id="intelligence-pipeline",
        version=version,
        name="ATHENA Intelligence Pipeline",
        description=description,
        metadata={
            "owning_module": "athena.orchestration.pipelines.intelligence",
            "semantic_version": version,
            "stage_count": len(stages),
        },
    )

    definition = PipelineDefinition(metadata=metadata, stages=tuple(stages))
    validate_intelligence_pipeline(definition)

    return definition
