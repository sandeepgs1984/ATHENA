"""Generic Pipeline Contract definition and validation (P7.4).

Provides reusable, symmetric contract declarations for pipelines (required inputs,
optional inputs, produced outputs) and pure validation functions.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum

from athena.errors import OrchestrationError
from athena.orchestration.models import PipelineContext
from athena.orchestration.pipelines.intelligence import (
    INTELLIGENCE_PIPELINE_OPTIONAL_INPUTS,
    INTELLIGENCE_PIPELINE_REQUIRED_INPUTS,
)
from athena.orchestration.pipelines.keys import (
    ExecutionArtifactKey,
    IntelligenceArtifactKey,
)


@dataclass(frozen=True, slots=True)
class PipelineContract:
    """Explicit declaration of input requirements and output guarantees for a pipeline."""

    name: str
    version: str
    required_inputs: frozenset[str | Enum]
    optional_inputs: frozenset[str | Enum] = field(default_factory=frozenset)
    produced_outputs: frozenset[str | Enum] = field(default_factory=frozenset)

    def __post_init__(self) -> None:
        if not self.name or not self.version:
            raise ValueError("PipelineContract name and version are mandatory")
        overlap = self.required_inputs & self.optional_inputs
        if overlap:
            raise ValueError(
                f"PipelineContract required and optional inputs overlap: {overlap}"
            )


def validate_contract(contract: PipelineContract, context: PipelineContext) -> None:
    """Validate that context satisfies all required_inputs declared by the contract.

    Raises OrchestrationError if any required key is missing or contains None.
    """
    for req_key in contract.required_inputs:
        k_str = req_key.value if isinstance(req_key, Enum) else str(req_key)
        val = context.get(k_str)
        if val is None:
            raise OrchestrationError(
                f"PipelineContract validation failed for '{contract.name}': "
                f"required input key '{k_str}' is missing or None"
            )


# Pre-defined, frozen pipeline contracts
EXECUTION_PIPELINE_CONTRACT = PipelineContract(
    name="Execution Pipeline Contract",
    version="1.0.0",
    required_inputs=frozenset({
        ExecutionArtifactKey.DECISIONS,
        ExecutionArtifactKey.CURRENT_PRICES,
    }),
    optional_inputs=frozenset(),
    produced_outputs=frozenset({
        ExecutionArtifactKey.PORTFOLIO_SNAPSHOT,
        ExecutionArtifactKey.ALLOCATION_PLAN,
        ExecutionArtifactKey.SIZING_PLAN,
        ExecutionArtifactKey.EXECUTION_PLAN,
        ExecutionArtifactKey.BROKER_PLAN,
        ExecutionArtifactKey.EXECUTION_STATE,
        ExecutionArtifactKey.PERFORMANCE_SNAPSHOT,
    }),
)

INTELLIGENCE_PIPELINE_CONTRACT = PipelineContract(
    name="Intelligence Pipeline Contract",
    version="1.0.0",
    required_inputs=INTELLIGENCE_PIPELINE_REQUIRED_INPUTS,
    optional_inputs=INTELLIGENCE_PIPELINE_OPTIONAL_INPUTS,
    produced_outputs=frozenset({
        IntelligenceArtifactKey.REPORTS,
        IntelligenceArtifactKey.EXPLANATION_SNAPSHOT,
        IntelligenceArtifactKey.DASHBOARD_SNAPSHOT,
        IntelligenceArtifactKey.MONITORING_SNAPSHOT,
        IntelligenceArtifactKey.TIMELINE_SNAPSHOT,
        IntelligenceArtifactKey.EXPORT_SNAPSHOT,
    }),
)
