"""Declarative ATHENA Execution Pipeline registration and validation (P7.2).

Assembles canonical ATHENA execution stages into an immutable PipelineDefinition.
Performs topology validation (duplicate IDs, stage metadata checks) prior to returning.
"""

from __future__ import annotations

from collections.abc import Sequence

from athena.errors import OrchestrationError
from athena.orchestration.models import (
    PipelineDefinition,
    PipelineMetadata,
    PipelineStage,
)


def validate_pipeline_definition(definition: PipelineDefinition) -> None:
    """Validate pipeline topology and stage uniqueness during construction."""
    seen_ids: set[str] = set()

    for stage in definition.stages:
        sid = stage.stage_id
        if not sid:
            raise OrchestrationError("Pipeline stage must have a non-empty stage_id")
        if sid in seen_ids:
            raise OrchestrationError(f"Duplicate stage_id '{sid}' in pipeline definition")
        seen_ids.add(sid)


def create_execution_pipeline(
    stages: Sequence[PipelineStage],
    *,
    version: str = "1.0.0",
    description: str = "Canonical ATHENA decision-to-execution-analytics pipeline",
) -> PipelineDefinition:
    """Construct and validate an immutable PipelineDefinition for ATHENA execution stages.

    Pure declarative pipeline builder. Does not execute or bind runner engines.
    """
    if not stages:
        raise OrchestrationError("Cannot create execution pipeline with empty stages sequence")

    metadata = PipelineMetadata(
        definition_id="execution-pipeline",
        version=version,
        name="ATHENA Execution Pipeline",
        description=description,
        metadata={
            "owning_module": "athena.orchestration.pipelines.execution",
            "semantic_version": version,
            "stage_count": len(stages),
        },
    )

    definition = PipelineDefinition(metadata=metadata, stages=tuple(stages))
    validate_pipeline_definition(definition)

    return definition
