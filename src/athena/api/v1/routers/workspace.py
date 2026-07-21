"""Workspace snapshots endpoint router (P8.3)."""

from __future__ import annotations

from datetime import datetime, timezone

from fastapi import APIRouter, Depends, Request, status

from athena.api.dependencies import get_workspace_service
from athena.api.security import Permission, RequirePermission
from athena.api.security.models import AuthenticatedPrincipal
from athena.api.v1.dtos import (
    AthenaResponse,
    PaginationParams,
    ResponseMeta,
    SortParams,
    WorkspaceFilterParams,
    WorkspaceSnapshotDTO,
    WorkspaceSnapshotSummaryDTO,
)
from athena.api.v1.dtos.base import PaginationMeta
from athena.api.v1.services.workspace_service import WorkspaceService

router = APIRouter(prefix="/workspace", tags=["Workspace"])


@router.get(
    "/snapshots",
    response_model=AthenaResponse[list[WorkspaceSnapshotSummaryDTO]],
    summary="List workspace snapshot summaries",
    status_code=status.HTTP_200_OK,
    operation_id="listWorkspaceSnapshots",
)
def list_snapshots(
    request: Request,
    filters: WorkspaceFilterParams = Depends(),  # noqa: B008
    sort: SortParams = Depends(),  # noqa: B008
    pagination: PaginationParams = Depends(),  # noqa: B008
    service: WorkspaceService = Depends(get_workspace_service),  # noqa: B008
    principal: AuthenticatedPrincipal = Depends(RequirePermission(Permission.READ)),  # noqa: B008
) -> AthenaResponse[list[WorkspaceSnapshotSummaryDTO]]:
    """Retrieve history of workspace snapshot metadata summaries."""
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
    response_model=AthenaResponse[WorkspaceSnapshotDTO],
    summary="Get workspace snapshot details",
    status_code=status.HTTP_200_OK,
    operation_id="getWorkspaceSnapshot",
)
def get_snapshot(
    request: Request,
    snapshot_id: str,
    service: WorkspaceService = Depends(get_workspace_service),  # noqa: B008
    principal: AuthenticatedPrincipal = Depends(RequirePermission(Permission.READ)),  # noqa: B008
) -> AthenaResponse[WorkspaceSnapshotDTO]:
    """Retrieve detailed catalog entries for a specific workspace snapshot."""
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
