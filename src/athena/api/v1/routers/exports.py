"""Presentation exports endpoint router (P8.4)."""

from __future__ import annotations

from datetime import datetime, timezone

from fastapi import APIRouter, Depends, Header, Request, status

from athena.api.dependencies import get_exports_service
from athena.api.security import Permission, RequirePermission
from athena.api.security.models import AuthenticatedPrincipal
from athena.api.v1.dtos import (
    AthenaResponse,
    EmptyFilterParams,
    ExportArtifactDTO,
    ExportJobDTO,
    ExportRequestDTO,
    ExportSnapshotDTO,
    ExportSnapshotSummaryDTO,
    PaginationParams,
    ResponseMeta,
    SortParams,
)
from athena.api.v1.dtos.base import PaginationMeta
from athena.api.v1.services.exports_service import ExportsService

router = APIRouter(prefix="/exports", tags=["Exports"])


@router.get(
    "/snapshots",
    response_model=AthenaResponse[list[ExportSnapshotSummaryDTO]],
    summary="List export snapshots",
    status_code=status.HTTP_200_OK,
    operation_id="listExportSnapshots",
)
def list_snapshots(
    request: Request,
    filters: EmptyFilterParams = Depends(),  # noqa: B008
    sort: SortParams = Depends(),  # noqa: B008
    pagination: PaginationParams = Depends(),  # noqa: B008
    service: ExportsService = Depends(get_exports_service),  # noqa: B008
    principal: AuthenticatedPrincipal = Depends(RequirePermission(Permission.READ)),  # noqa: B008
) -> AthenaResponse[list[ExportSnapshotSummaryDTO]]:
    """Retrieve history of batch export snapshots metadata summaries."""
    result = service.list_snapshots(filters, sort, pagination)
    request_id = getattr(request.state, "request_id", "unknown")

    meta = ResponseMeta(
        request_id=request_id,
        api_version="v1",
        as_of=datetime.now(tz=timezone.utc),
    )

    pagination_meta = PaginationMeta(
        total=result.total_count,
        page=result.page,
        page_size=result.page_size,
        total_pages=result.total_pages,
        has_next=result.has_next,
        has_previous=result.has_previous,
    )

    return AthenaResponse(
        status="success",
        data=list(result.items),
        meta=meta,
        pagination=pagination_meta,
    )


@router.get(
    "/snapshots/{snapshot_id}",
    response_model=AthenaResponse[ExportSnapshotDTO],
    summary="Get export snapshot details",
    status_code=status.HTTP_200_OK,
    operation_id="getExportSnapshot",
)
def get_snapshot(
    request: Request,
    snapshot_id: str,
    service: ExportsService = Depends(get_exports_service),  # noqa: B008
    principal: AuthenticatedPrincipal = Depends(RequirePermission(Permission.READ)),  # noqa: B008
) -> AthenaResponse[ExportSnapshotDTO]:
    """Retrieve detailed data listings and nested items for a batch export snapshot."""
    snapshot_data = service.get_snapshot(snapshot_id)
    request_id = getattr(request.state, "request_id", "unknown")

    meta = ResponseMeta(
        request_id=request_id,
        api_version="v1",
        as_of=datetime.now(tz=timezone.utc),
    )

    return AthenaResponse(
        status="success",
        data=snapshot_data,
        meta=meta,
    )


@router.get(
    "/artifacts/{export_id}",
    response_model=AthenaResponse[ExportArtifactDTO],
    summary="Get export artifact details",
    status_code=status.HTTP_200_OK,
    operation_id="getExportArtifact",
)
def get_artifact(
    request: Request,
    export_id: str,
    service: ExportsService = Depends(get_exports_service),  # noqa: B008
    principal: AuthenticatedPrincipal = Depends(RequirePermission(Permission.READ)),  # noqa: B008
) -> AthenaResponse[ExportArtifactDTO]:
    """Retrieve payload contents and metadata for a specific exported document."""
    artifact_data = service.get_artifact(export_id)
    request_id = getattr(request.state, "request_id", "unknown")

    meta = ResponseMeta(
        request_id=request_id,
        api_version="v1",
        as_of=datetime.now(tz=timezone.utc),
    )

    return AthenaResponse(
        status="success",
        data=artifact_data,
        meta=meta,
    )


@router.post(
    "",
    response_model=AthenaResponse[ExportJobDTO],
    summary="Create export artifact",
    status_code=status.HTTP_202_ACCEPTED,
    operation_id="createExport",
)
def create_export(
    request: Request,
    body: ExportRequestDTO,
    x_idempotency_key: str | None = Header(default=None, alias="X-Idempotency-Key"),
    service: ExportsService = Depends(get_exports_service),  # noqa: B008
    principal: AuthenticatedPrincipal = Depends(RequirePermission(Permission.READ)),  # noqa: B008
) -> AthenaResponse[ExportJobDTO]:
    """Trigger formatting and payload transformation job for a target artifact."""
    job_dto = service.create_export(body, idempotency_key=x_idempotency_key)
    request_id = getattr(request.state, "request_id", "unknown")

    meta = ResponseMeta(
        request_id=request_id,
        api_version="v1",
        as_of=datetime.now(tz=timezone.utc),
    )

    return AthenaResponse(
        status="success",
        data=job_dto,
        meta=meta,
    )
