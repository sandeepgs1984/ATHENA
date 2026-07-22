"""Health endpoint controller (P8.1)."""

from __future__ import annotations

from datetime import datetime, timezone

from fastapi import APIRouter, Depends, Request, status

from athena.api.dependencies import get_health_service
from athena.api.v1.dtos.base import AthenaResponse, ResponseMeta
from athena.api.v1.dtos.common import HealthResponse
from athena.api.v1.services.health_service import HealthService

router = APIRouter()


@router.get(
    "/health",
    response_model=AthenaResponse[HealthResponse],
    summary="Get platform health status",
    status_code=status.HTTP_200_OK,
    tags=["Health"],
    operation_id="v1GetHealth",
)
def get_health(
    request: Request,
    service: HealthService = Depends(get_health_service),  # noqa: B008
) -> AthenaResponse[HealthResponse]:
    """Retrieve current system and orchestration status check.

    Returns the system-health report, categorized by components.
    """
    health_data = service.get_health()
    request_id = getattr(request.state, "request_id", "unknown")

    meta = ResponseMeta(
        request_id=request_id,
        api_version="v1",
        as_of=datetime.now(tz=timezone.utc),
    )

    return AthenaResponse(
        status="success",
        data=health_data,
        meta=meta,
    )
