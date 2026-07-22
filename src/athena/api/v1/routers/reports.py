"""Generic reports endpoint router (P8.4)."""

from __future__ import annotations

from datetime import datetime, timezone

from fastapi import APIRouter, Depends, Request, status

from athena.api.dependencies import get_reports_service
from athena.api.security import Permission, RequirePermission
from athena.api.security.models import AuthenticatedPrincipal
from athena.api.v1.dtos import (
    AthenaResponse,
    PaginationParams,
    ReportDTO,
    ReportFilterParams,
    ReportSummaryDTO,
    ResponseMeta,
    SortParams,
)
from athena.api.v1.dtos.base import PaginationMeta
from athena.api.v1.services.reports_service import ReportsService

router = APIRouter(prefix="/reports", tags=["Reports"])


@router.get(
    "",
    response_model=AthenaResponse[list[ReportSummaryDTO]],
    summary="List generic reports",
    status_code=status.HTTP_200_OK,
    operation_id="listReports",
)
def list_reports(
    request: Request,
    filters: ReportFilterParams = Depends(),  # noqa: B008
    sort: SortParams = Depends(),  # noqa: B008
    pagination: PaginationParams = Depends(),  # noqa: B008
    service: ReportsService = Depends(get_reports_service),  # noqa: B008
    principal: AuthenticatedPrincipal = Depends(RequirePermission(Permission.READ)),  # noqa: B008
) -> AthenaResponse[list[ReportSummaryDTO]]:
    """Retrieve history of generic reports summaries."""
    result = service.list_reports(filters, sort, pagination)
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
    "/{report_id}",
    response_model=AthenaResponse[ReportDTO],
    summary="Get generic report details",
    status_code=status.HTTP_200_OK,
    operation_id="getReport",
)
def get_report(
    request: Request,
    report_id: str,
    service: ReportsService = Depends(get_reports_service),  # noqa: B008
    principal: AuthenticatedPrincipal = Depends(RequirePermission(Permission.READ)),  # noqa: B008
) -> AthenaResponse[ReportDTO]:
    """Retrieve detailed data payload for a specific report."""
    report_data = service.get_report(report_id)
    request_id = getattr(request.state, "request_id", "unknown")

    meta = ResponseMeta(
        request_id=request_id,
        api_version="v1",
        as_of=datetime.now(tz=timezone.utc),
    )

    return AthenaResponse(
        status="success",
        data=report_data,
        meta=meta,
    )
