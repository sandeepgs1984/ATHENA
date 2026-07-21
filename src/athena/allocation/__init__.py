"""Capital Allocation Engine package (P5.2).

Determines capital allocation policy for approved investment opportunities.
Performs no market analysis, position sizing, or order execution.
"""

from athena.allocation.engine import CapitalAllocationEngine
from athena.allocation.models import (
    AllocationDecision,
    AllocationHistory,
    AllocationPlan,
    AllocationReferences,
    AllocationSummary,
    CapitalAllocation,
)

__all__ = [
    "AllocationDecision",
    "AllocationHistory",
    "AllocationPlan",
    "AllocationReferences",
    "AllocationSummary",
    "CapitalAllocation",
    "CapitalAllocationEngine",
]
