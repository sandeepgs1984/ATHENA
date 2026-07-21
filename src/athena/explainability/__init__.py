"""Explainability Engine package (P6.3).

Generates deterministic, human-readable explanations describing why platform outcomes were produced.
Performs no LLM generation, dynamic reasoning, or state mutation.
"""

from athena.explainability.engine import ExplainabilityEngine
from athena.explainability.models import (
    Explanation,
    ExplanationHistory,
    ExplanationReferences,
    ExplanationSection,
    ExplanationSnapshot,
)

__all__ = [
    "ExplainabilityEngine",
    "Explanation",
    "ExplanationHistory",
    "ExplanationReferences",
    "ExplanationSection",
    "ExplanationSnapshot",
]
