"""Dashboard controller router (P9.2)."""

from __future__ import annotations

from datetime import datetime, timezone

from fastapi import APIRouter, Depends, Request, status

from athena.api.dependencies import get_advisory_freshness_service, get_dashboard_service
from athena.api.v1.dtos import AthenaResponse, ResponseMeta
from athena.api.v1.dtos.dashboard import (
    AdvisoryFreshnessDTO,
    CalendarDataDTO,
    DashboardSummaryDTO,
    MarketSessionStatusDTO,
)
from athena.api.v1.services.advisory_freshness_service import AdvisoryFreshnessService
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


@router.get(
    "/calendar",
    response_model=AthenaResponse[CalendarDataDTO],
    summary="Get trading calendar configuration details",
    status_code=status.HTTP_200_OK,
    operation_id="getCalendarData",
)
def get_calendar_data(
    request: Request,
    service: DashboardService = Depends(get_dashboard_service),  # noqa: B008
) -> AthenaResponse[CalendarDataDTO]:
    """Retrieve holidays, weekly/monthly expiries, special trading sessions, and scheduled macroeconomic events."""
    data = service.get_calendar_data()
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


@router.get(
    "/session-status",
    response_model=AthenaResponse[MarketSessionStatusDTO],
    summary="Get current exchange session status",
    status_code=status.HTTP_200_OK,
    operation_id="getMarketSessionStatus",
)
def get_market_session_status(
    request: Request,
    as_of: datetime | None = None,
    service: DashboardService = Depends(get_dashboard_service),  # noqa: B008
) -> AthenaResponse[MarketSessionStatusDTO]:
    """Retrieve market-live/review-mode status from ATHENA's Calendar Engine."""
    data = service.get_market_session_status(as_of=as_of)
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


@router.get(
    "/advisory-freshness",
    response_model=AthenaResponse[AdvisoryFreshnessDTO],
    summary="Get persisted market-observation freshness",
    status_code=status.HTTP_200_OK,
    operation_id="getAdvisoryFreshness",
)
def get_advisory_freshness(
    request: Request,
    as_of: datetime | None = None,
    service: AdvisoryFreshnessService = Depends(get_advisory_freshness_service),  # noqa: B008
) -> AthenaResponse[AdvisoryFreshnessDTO]:
    """Return a Calendar Engine-aware classification for the shared header."""
    data = service.get_freshness(as_of=as_of)
    request_id = getattr(request.state, "request_id", "unknown")
    return AthenaResponse(
        status="success",
        data=data,
        meta=ResponseMeta(
            request_id=request_id,
            api_version="v1",
            as_of=datetime.now(tz=timezone.utc),
        ),
    )
