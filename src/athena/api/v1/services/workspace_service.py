"""Workspace snapshot catalog service (P8.3)."""

from __future__ import annotations

from typing import TYPE_CHECKING

from athena.api.exceptions import WorkspaceSnapshotNotFoundError
from athena.api.v1.dtos import (
    CollectionResult,
    QuerySpecification,
    ResourceReference,
    WorkspaceEntryDTO,
    WorkspaceReferencesDTO,
    WorkspaceSnapshotDTO,
    WorkspaceSnapshotSummaryDTO,
    WorkspaceSummaryDTO,
)

if TYPE_CHECKING:
    from athena.api.v1.dtos import PaginationParams, SortParams, WorkspaceFilterParams
    from athena.api.v1.providers import WorkspaceProvider
    from athena.workspace.models import (
        WorkspaceEntry,
        WorkspaceReferences,
        WorkspaceSnapshot,
        WorkspaceSummary,
    )


class WorkspaceService:
    """Orchestrates workspace snapshots query resolution and DTO mapping."""

    def __init__(self, provider: WorkspaceProvider) -> None:
        self._provider = provider

    def list_snapshots(
        self,
        filters: WorkspaceFilterParams,
        sort: SortParams,
        pagination: PaginationParams,
    ) -> CollectionResult[WorkspaceSnapshotSummaryDTO]:
        """Lists workspace snapshot summaries using query specifications."""
        spec = QuerySpecification(filters=filters, sort=sort, pagination=pagination)
        result = self._provider.get_snapshots(spec)

        dto_items = tuple(self._map_to_summary_dto(s) for s in result.items)
        return CollectionResult(
            items=dto_items,
            total_count=result.total_count,
            page=result.page,
            page_size=result.page_size,
        )

    def get_snapshot(self, snapshot_id: str) -> WorkspaceSnapshotDTO:
        """Retrieves complete workspace snapshot catalog details or raises WorkspaceSnapshotNotFoundError."""
        s = self._provider.get_snapshot(snapshot_id)
        if not s:
            raise WorkspaceSnapshotNotFoundError(
                f"Workspace snapshot '{snapshot_id}' not found"
            )
        return self._map_to_detail_dto(s)

    def _map_to_summary_dto(self, s: WorkspaceSnapshot) -> WorkspaceSnapshotSummaryDTO:
        return WorkspaceSnapshotSummaryDTO(
            snapshot_id=s.snapshot_id,
            as_of=s.as_of,
            summary=self._map_summary_dto(s.summary),
            references=self._map_references_dto(s.references),
        )

    def _map_to_detail_dto(self, s: WorkspaceSnapshot) -> WorkspaceSnapshotDTO:
        entries_dtos = [self._map_entry_dto(e) for e in s.entries] if s.entries else []

        return WorkspaceSnapshotDTO(
            snapshot_id=s.snapshot_id,
            as_of=s.as_of,
            summary=self._map_summary_dto(s.summary),
            references=self._map_references_dto(s.references),
            entries=entries_dtos,
        )

    def _map_summary_dto(self, sum_val: WorkspaceSummary) -> WorkspaceSummaryDTO:
        return WorkspaceSummaryDTO(
            total_entries=sum_val.total_entries,
            artifact_counts=dict(sum_val.artifact_counts)
            if sum_val.artifact_counts
            else {},
            overall_health=sum_val.overall_health,
        )

    def _map_references_dto(
        self, ref: WorkspaceReferences | None
    ) -> WorkspaceReferencesDTO:
        if not ref:
            return WorkspaceReferencesDTO()

        return WorkspaceReferencesDTO(
            report_ref=(
                ResourceReference(id=ref.report_id, resource_type="report")
                if ref.report_id
                else None
            ),
            dashboard_ref=(
                ResourceReference(
                    id=ref.dashboard_snapshot_id, resource_type="dashboard"
                )
                if ref.dashboard_snapshot_id
                else None
            ),
            explanation_ref=(
                ResourceReference(
                    id=ref.explanation_snapshot_id, resource_type="explanation"
                )
                if ref.explanation_snapshot_id
                else None
            ),
            timeline_ref=(
                ResourceReference(
                    id=ref.timeline_snapshot_id, resource_type="timeline"
                )
                if ref.timeline_snapshot_id
                else None
            ),
            monitoring_ref=(
                ResourceReference(
                    id=ref.monitoring_snapshot_id, resource_type="monitoring"
                )
                if ref.monitoring_snapshot_id
                else None
            ),
            export_ref=(
                ResourceReference(id=ref.export_snapshot_id, resource_type="export")
                if ref.export_snapshot_id
                else None
            ),
        )

    def _map_entry_dto(self, e: WorkspaceEntry) -> WorkspaceEntryDTO:
        return WorkspaceEntryDTO(
            entry_id=e.entry_id,
            artifact_type=e.artifact_type,
            title=e.title,
            as_of=e.as_of,
            references=self._map_references_dto(e.references),
        )
