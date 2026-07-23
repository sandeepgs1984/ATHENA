"""Strategy profiles endpoint router (P9.5)."""

from __future__ import annotations

from datetime import datetime, timezone

from fastapi import APIRouter, Depends, Request, status

from athena.api.dependencies import get_strategies_service
from athena.api.security import Permission, RequirePermission
from athena.api.security.models import AuthenticatedPrincipal
from athena.api.v1.dtos import AthenaResponse, ResponseMeta, StrategyProfileDTO
from athena.api.v1.services.strategies_service import StrategyService

router = APIRouter(prefix="/strategies", tags=["Strategies"])


@router.get(
    "/profiles",
    response_model=AthenaResponse[list[StrategyProfileDTO]],
    summary="List strategy profiles and selection rules",
    status_code=status.HTTP_200_OK,
    operation_id="listStrategyProfiles",
)
def list_profiles(
    request: Request,
    service: StrategyService = Depends(get_strategies_service),  # noqa: B008
    principal: AuthenticatedPrincipal = Depends(RequirePermission(Permission.READ)),  # noqa: B008
) -> AthenaResponse[list[StrategyProfileDTO]]:
    """Retrieve all registered strategy profiles and their selection rule thresholds."""
    profiles = service.list_profiles()
    request_id = getattr(request.state, "request_id", "unknown")

    meta = ResponseMeta(
        request_id=request_id,
        api_version="v1",
        as_of=datetime.now(tz=timezone.utc),
    )

    return AthenaResponse(
        status="success",
        data=profiles,
        meta=meta,
    )
