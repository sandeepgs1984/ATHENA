"""Position Sizing Engine package (P5.3).

Converts approved capital allocations into executable share/unit quantities.
Performs no market analysis, capital allocation policy decision, or order execution.
"""

from athena.sizing.engine import PositionSizingEngine
from athena.sizing.models import (
    PositionSize,
    PositionSizingDecision,
    PositionSizingHistory,
    PositionSizingPlan,
    PositionSizingSummary,
    SizingReferences,
)

__all__ = [
    "PositionSize",
    "PositionSizingDecision",
    "PositionSizingEngine",
    "PositionSizingHistory",
    "PositionSizingPlan",
    "PositionSizingSummary",
    "SizingReferences",
]
