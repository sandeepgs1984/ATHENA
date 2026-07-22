"""Presentation exports operational and generation service (P8.4)."""

from __future__ import annotations

import hashlib
from datetime import datetime, timezone
from typing import TYPE_CHECKING

from athena.api.exceptions import (
    ExportArtifactNotFoundError,
    ExportGenerationError,
    ExportSnapshotNotFoundError,
    ReportNotFoundError,
)
from athena.api.v1.dtos import (
    ArtifactMetadataDTO,
    CollectionResult,
    ExportArtifactDTO,
    ExportJobDTO,
    ExportJobStatus,
    ExportSnapshotDTO,
    ExportSnapshotSummaryDTO,
    ExportSummaryDTO,
    QuerySpecification,
)
from athena.export.engine import ExportPresentationEngine

if TYPE_CHECKING:
    from athena.api.v1.dtos import EmptyFilterParams, ExportRequestDTO, PaginationParams, SortParams
    from athena.api.v1.providers import ExportGenerationProvider, ExportQueryProvider, ReportProvider
    from athena.export.models import ExportArtifact, ExportSnapshot, ExportSummary


class ExportsService:
    """Orchestrates presentation exports lookup, tracking, and on-demand generation."""

    def __init__(
        self,
        query_provider: ExportQueryProvider,
        generation_provider: ExportGenerationProvider,
        report_provider: ReportProvider,
    ) -> None:
        self._query_provider = query_provider
        self._generation_provider = generation_provider
        self._report_provider = report_provider
        self._engine = ExportPresentationEngine()

    def list_snapshots(
        self,
        filters: EmptyFilterParams,
        sort: SortParams,
        pagination: PaginationParams,
    ) -> CollectionResult[ExportSnapshotSummaryDTO]:
        """Lists export snapshots using query specifications."""
        spec = QuerySpecification(filters=filters, sort=sort, pagination=pagination)
        result = self._query_provider.get_snapshots(spec)

        dto_items = tuple(self._map_to_summary_dto(s) for s in result.items)
        return CollectionResult(
            items=dto_items,
            total_count=result.total_count,
            page=result.page,
            page_size=result.page_size,
        )

    def get_snapshot(self, snapshot_id: str) -> ExportSnapshotDTO:
        """Retrieves complete export snapshot details or raises ExportSnapshotNotFoundError."""
        s = self._query_provider.get_snapshot(snapshot_id)
        if not s:
            raise ExportSnapshotNotFoundError(f"Export snapshot '{snapshot_id}' not found")
        return self._map_to_detail_dto(s)

    def get_artifact(self, export_id: str) -> ExportArtifactDTO:
        """Retrieves specific export artifact payload or raises ExportArtifactNotFoundError."""
        art = self._query_provider.get_artifact(export_id)
        if not art:
            raise ExportArtifactNotFoundError(f"Export artifact '{export_id}' not found")
        return self._map_artifact_dto(art)

    def create_export(
        self, req: ExportRequestDTO, idempotency_key: str | None = None
    ) -> ExportJobDTO:
        """Generates a presentation export artifact synchronously, returning an ExportJobDTO.

        Future asynchronous worker queues can execute this using identical signature/payload.
        """
        now = datetime.now(tz=timezone.utc)
        payload_key = f"{req.source.artifact_id}-{req.format.value}-{now.isoformat()}"
        job_id = f"job-{hashlib.md5(payload_key.encode()).hexdigest()[:8]}"

        try:
            # 1. Resolve source artifact by type
            if req.source.artifact_type.value == "REPORT":
                source_obj = self._report_provider.get_report(req.source.artifact_id)
                if not source_obj:
                    raise ReportNotFoundError(f"Source report '{req.source.artifact_id}' not found")

                # 2. Export source using presentation engine
                artifact = self._engine.export_report(source_obj, req.format, as_of=now)
            else:
                # Unsupported source artifact type for export in P8.4
                raise ExportGenerationError(f"Unsupported export source artifact type: {req.source.artifact_type}")

            # 3. Save snapshot
            snapshot = self._engine.create_snapshot([artifact], as_of=now)
            self._generation_provider.save_snapshot(snapshot)

            return ExportJobDTO(
                job_id=job_id,
                status=ExportJobStatus.COMPLETED,
                created_at=now,
                completed_at=now,
                result_artifact_id=artifact.export_id,
            )

        except Exception as e:
            if isinstance(e, (ReportNotFoundError, ExportGenerationError)):
                raise e
            raise ExportGenerationError(f"Failed to generate export: {e!s}") from e

    def _map_to_summary_dto(self, s: ExportSnapshot) -> ExportSnapshotSummaryDTO:
        return ExportSnapshotSummaryDTO(
            snapshot_id=s.snapshot_id,
            as_of=s.as_of,
            summary=self._map_summary_dto(s.summary),
        )

    def _map_to_detail_dto(self, s: ExportSnapshot) -> ExportSnapshotDTO:
        exports_dtos = [self._map_artifact_dto(e) for e in s.exports] if s.exports else []

        return ExportSnapshotDTO(
            snapshot_id=s.snapshot_id,
            as_of=s.as_of,
            exports=exports_dtos,
            summary=self._map_summary_dto(s.summary),
        )

    def _map_summary_dto(self, sum_val: ExportSummary) -> ExportSummaryDTO:
        return ExportSummaryDTO(
            total_exports=sum_val.total_exports,
            formats_used=list(sum_val.formats_used),
            total_bytes=sum_val.total_bytes,
        )

    def _map_artifact_dto(self, art: ExportArtifact) -> ExportArtifactDTO:
        checksum = hashlib.sha256(art.payload.encode("utf-8")).hexdigest()
        meta = ArtifactMetadataDTO(
            artifact_id=art.export_id,
            artifact_type=self._resolve_artifact_type(art.filename),
            format=art.format,
            filename=art.filename,
            created_at=art.as_of,
            generated_by="ExportsService",
            size_bytes=len(art.payload.encode("utf-8")),
            content_type=art.content_type,
            checksum=checksum,
        )
        return ExportArtifactDTO(
            metadata=meta,
            payload=art.payload,
        )

    def _resolve_artifact_type(self, filename: str) -> str:
        if filename.startswith("report"):
            return "REPORT"
        elif filename.startswith("dashboard"):
            return "DASHBOARD"
        elif filename.startswith("explanation"):
            return "EXPLANATION"
        elif filename.startswith("timeline"):
            return "TIMELINE"
        return "MONITORING"
