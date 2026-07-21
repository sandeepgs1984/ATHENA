"""Pipelines package for ATHENA orchestration (P7.2).

Exports execution pipeline builders, typed artifact keys, and stage identifiers.
"""

from athena.orchestration.pipelines.execution import (
    create_execution_pipeline,
    validate_pipeline_definition,
)
from athena.orchestration.pipelines.keys import ExecutionArtifactKey, ExecutionStageId

__all__ = [
    "ExecutionArtifactKey",
    "ExecutionStageId",
    "create_execution_pipeline",
    "validate_pipeline_definition",
]
