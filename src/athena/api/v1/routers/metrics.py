"""Metrics endpoint controller (P8.1)."""

from __future__ import annotations

from datetime import datetime, timezone

from fastapi import APIRouter, Depends, Request, status

from athena.api.dependencies import get_metrics_service
from athena.api.v1.dtos.base import AthenaResponse, ResponseMeta
from athena.api.v1.dtos.common import MetricsResponse
from athena.api.v1.services.metrics_service import MetricsService

router = APIRouter()


@router.get(
    "/metrics",
    response_model=AthenaResponse[MetricsResponse],
    summary="Get platform telemetry and metrics",
    status_code=status.HTTP_200_OK,
    tags=["Metrics"],
    operation_id="v1GetMetrics",
)
def get_metrics(
    request: Request,
    service: MetricsService = Depends(get_metrics_service),  # noqa: B008
) -> AthenaResponse[MetricsResponse]:
    """Retrieve operational metrics including run status and platform counters."""
    metrics_data = service.get_metrics()
    request_id = getattr(request.state, "request_id", "unknown")

    meta = ResponseMeta(
        request_id=request_id,
        api_version="v1",
        as_of=datetime.now(tz=timezone.utc),
    )

    return AthenaResponse(
        status="success",
        data=metrics_data,
        meta=meta,
    )
