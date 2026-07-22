"""Dashboard controller router (P9.2)."""

from __future__ import annotations

from datetime import datetime, timezone

from fastapi import APIRouter, Depends, Request, status

from athena.api.dependencies import get_dashboard_service
from athena.api.v1.dtos import AthenaResponse, ResponseMeta
from athena.api.v1.dtos.dashboard import DashboardSummaryDTO
from athena.api.v1.services.dashboard_service import DashboardService

router = APIRouter(prefix="/dashboard", tags=["Dashboard"])


@router.get(
    "/summary",
    response_model=AthenaResponse[DashboardSummaryDTO],
    summary="Get aggregated dashboard summary",
    status_code=status.HTTP_200_OK,
    operation_id="getDashboardSummary",
)
def get_dashboard_summary(
    request: Request,
    service: DashboardService = Depends(get_dashboard_service),  # noqa: B008
) -> AthenaResponse[DashboardSummaryDTO]:
    """Retrieve portfolio valuation, regime trend classification, scan dates, and system health summaries."""
    data = service.get_summary()
    request_id = getattr(request.state, "request_id", "unknown")

    meta = ResponseMeta(
        request_id=request_id,
        api_version="v1",
        as_of=datetime.now(tz=timezone.utc),
    )

    return AthenaResponse(
        status="success",
        data=data,
        meta=meta,
    )
