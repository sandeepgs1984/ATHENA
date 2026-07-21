"""Unified Intelligence Workspace package (P6.7).

Orchestrates a consolidated read-only query surface across all Phase 6 intelligence artifacts.
Performs no state mutation or external network delivery.
"""

from athena.workspace.engine import UnifiedIntelligenceWorkspace
from athena.workspace.models import (
    WorkspaceEntry,
    WorkspaceHistory,
    WorkspaceReferences,
    WorkspaceSnapshot,
    WorkspaceSummary,
)

__all__ = [
    "UnifiedIntelligenceWorkspace",
    "WorkspaceEntry",
    "WorkspaceHistory",
    "WorkspaceReferences",
    "WorkspaceSnapshot",
    "WorkspaceSummary",
]
