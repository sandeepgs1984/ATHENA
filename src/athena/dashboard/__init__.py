"""Dashboard & Snapshot Engine package (P6.2).

Produces derived, read-only dashboard snapshots and operational views.
Performs no UI rendering, live polling, or state mutation.
"""

from athena.dashboard.engine import DashboardEngine
from athena.dashboard.models import (
    DashboardHistory,
    DashboardReferences,
    DashboardSection,
    DashboardSnapshot,
    DashboardSummary,
)

__all__ = [
    "DashboardEngine",
    "DashboardHistory",
    "DashboardReferences",
    "DashboardSection",
    "DashboardSnapshot",
    "DashboardSummary",
]
