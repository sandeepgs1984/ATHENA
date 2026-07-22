"""Generic reports operational query service (P8.4)."""

from __future__ import annotations

from typing import TYPE_CHECKING

from athena.api.exceptions import ReportNotFoundError
from athena.api.v1.dtos import (
    CollectionResult,
    QuerySpecification,
    ReportDTO,
    ReportMetadataDTO,
    ReportReferencesDTO,
    ReportSummaryDTO,
    ResourceReference,
)

if TYPE_CHECKING:
    from athena.api.v1.dtos import PaginationParams, ReportFilterParams, SortParams
    from athena.api.v1.providers import ReportProvider
    from athena.reporting.models import GenericReport, ReportingReferences


class ReportsService:
    """Orchestrates generic reports query resolution and DTO mapping."""

    def __init__(self, provider: ReportProvider) -> None:
        self._provider = provider

    def list_reports(
        self,
        filters: ReportFilterParams,
        sort: SortParams,
        pagination: PaginationParams,
    ) -> CollectionResult[ReportSummaryDTO]:
        """Lists report summaries using query specifications."""
        spec = QuerySpecification(filters=filters, sort=sort, pagination=pagination)
        result = self._provider.get_reports(spec)

        dto_items = tuple(self._map_to_summary_dto(r) for r in result.items)
        return CollectionResult(
            items=dto_items,
            total_count=result.total_count,
            page=result.page,
            page_size=result.page_size,
        )

    def get_report(self, report_id: str) -> ReportDTO:
        """Retrieves complete report details or raises ReportNotFoundError."""
        r = self._provider.get_report(report_id)
        if not r:
            raise ReportNotFoundError(f"Report '{report_id}' not found")
        return self._map_to_detail_dto(r)

    def _map_to_summary_dto(self, r: GenericReport) -> ReportSummaryDTO:
        return ReportSummaryDTO(
            metadata=self._map_metadata_dto(r),
            text_summary=r.text_summary,
            references=self._map_references_dto(r.references),
        )

    def _map_to_detail_dto(self, r: GenericReport) -> ReportDTO:
        return ReportDTO(
            metadata=self._map_metadata_dto(r),
            content=dict(r.content) if r.content else {},
            text_summary=r.text_summary,
            references=self._map_references_dto(r.references),
        )

    def _map_metadata_dto(self, r: GenericReport) -> ReportMetadataDTO:
        # Determine source reference if available in references
        source_ref = None
        if r.references:
            if r.references.portfolio_snapshot_id:
                source_ref = r.references.portfolio_snapshot_id
            elif r.references.execution_state_id:
                source_ref = r.references.execution_state_id
            elif r.references.allocation_plan_id:
                source_ref = r.references.allocation_plan_id
            elif r.references.performance_snapshot_id:
                source_ref = r.references.performance_snapshot_id
            elif r.references.audit_id:
                source_ref = r.references.audit_id

        return ReportMetadataDTO(
            report_id=r.report_id,
            report_type=r.report_type,
            title=r.title,
            as_of=r.as_of,
            report_version=1,  # Default fallback version
            generated_at=r.as_of,  # Default fallback generation ts
            source_snapshot_reference=source_ref,
        )

    def _map_references_dto(self, ref: ReportingReferences | None) -> ReportReferencesDTO:
        if not ref:
            return ReportReferencesDTO()

        return ReportReferencesDTO(
            portfolio_snapshot_ref=(
                ResourceReference(id=ref.portfolio_snapshot_id, resource_type="portfolio_snapshot")
                if ref.portfolio_snapshot_id
                else None
            ),
            execution_state_ref=(
                ResourceReference(id=ref.execution_state_id, resource_type="execution_state")
                if ref.execution_state_id
                else None
            ),
            allocation_plan_ref=(
                ResourceReference(id=ref.allocation_plan_id, resource_type="allocation_plan")
                if ref.allocation_plan_id
                else None
            ),
            performance_snapshot_ref=(
                ResourceReference(id=ref.performance_snapshot_id, resource_type="performance_snapshot")
                if ref.performance_snapshot_id
                else None
            ),
            audit_ref=(
                ResourceReference(id=ref.audit_id, resource_type="audit")
                if ref.audit_id
                else None
            ),
        )
