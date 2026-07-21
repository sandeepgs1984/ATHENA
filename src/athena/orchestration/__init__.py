"""Generic Pipeline Infrastructure package (P7.1).

Provides domain-agnostic stage protocols, lightweight immutable context propagation,
pipeline definitions, and execution runners.

Zero coupling to ATHENA business domains.
"""

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
)

__all__ = [
    "PipelineContext",
    "PipelineDefinition",
    "PipelineHistory",
    "PipelineMetadata",
    "PipelineResult",
    "PipelineRunner",
    "PipelineStage",
    "PipelineStatus",
    "StageExecutionResult",
    "StageResult",
    "StageStatus",
]
