"""Portfolio analytics endpoint router (P8.4)."""

from __future__ import annotations

from datetime import datetime, timezone

from fastapi import APIRouter, Depends, Request, status

from athena.api.dependencies import get_analytics_service
from athena.api.security import Permission, RequirePermission
from athena.api.security.models import AuthenticatedPrincipal
from athena.api.v1.dtos import (
    AthenaResponse,
    EmptyFilterParams,
    PaginationParams,
    PerformanceSnapshotDTO,
    PerformanceSnapshotSummaryDTO,
    ResponseMeta,
    SortParams,
)
from athena.api.v1.dtos.base import PaginationMeta
from athena.api.v1.services.analytics_service import AnalyticsService

router = APIRouter(prefix="/analytics", tags=["Analytics"])


@router.get(
    "/performance/snapshots",
    response_model=AthenaResponse[list[PerformanceSnapshotSummaryDTO]],
    summary="List performance snapshots",
    status_code=status.HTTP_200_OK,
    operation_id="listPerformanceSnapshots",
)
def list_snapshots(
    request: Request,
    filters: EmptyFilterParams = Depends(),  # noqa: B008
    sort: SortParams = Depends(),  # noqa: B008
    pagination: PaginationParams = Depends(),  # noqa: B008
    service: AnalyticsService = Depends(get_analytics_service),  # noqa: B008
    principal: AuthenticatedPrincipal = Depends(RequirePermission(Permission.READ)),  # noqa: B008
) -> AthenaResponse[list[PerformanceSnapshotSummaryDTO]]:
    """Retrieve history of portfolio performance metrics snapshot summaries."""
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
    "/performance/snapshots/{snapshot_id}",
    response_model=AthenaResponse[PerformanceSnapshotDTO],
    summary="Get performance snapshot details",
    status_code=status.HTTP_200_OK,
    operation_id="getPerformanceSnapshot",
)
def get_snapshot(
    request: Request,
    snapshot_id: str,
    service: AnalyticsService = Depends(get_analytics_service),  # noqa: B008
    principal: AuthenticatedPrincipal = Depends(RequirePermission(Permission.READ)),  # noqa: B008
) -> AthenaResponse[PerformanceSnapshotDTO]:
    """Retrieve detailed valuation, metrics, and trades list for a performance snapshot."""
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
