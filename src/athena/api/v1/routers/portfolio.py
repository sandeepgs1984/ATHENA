"""Portfolio endpoint router (P8.3)."""

from __future__ import annotations

from datetime import datetime, timezone

from fastapi import APIRouter, Depends, Request, status

from athena.api.dependencies import get_portfolio_service
from athena.api.security import Permission, RequirePermission
from athena.api.security.models import AuthenticatedPrincipal
from athena.api.v1.dtos import AthenaResponse, PortfolioDTO, ResponseMeta
from athena.api.v1.services.portfolio_service import PortfolioService

router = APIRouter(prefix="/portfolio", tags=["Portfolio"])


@router.get(
    "",
    response_model=AthenaResponse[PortfolioDTO],
    summary="Get portfolio status",
    status_code=status.HTTP_200_OK,
    operation_id="getPortfolio",
)
def get_portfolio(
    request: Request,
    service: PortfolioService = Depends(get_portfolio_service),  # noqa: B008
    principal: AuthenticatedPrincipal = Depends(RequirePermission(Permission.READ)),  # noqa: B008
) -> AthenaResponse[PortfolioDTO]:
    """Retrieve cash balances, open positions, and sector exposure weights for the portfolio."""
    portfolio_data = service.get_portfolio()
    request_id = getattr(request.state, "request_id", "unknown")

    meta = ResponseMeta(
        request_id=request_id,
        api_version="v1",
        as_of=datetime.now(tz=timezone.utc),
    )

    return AthenaResponse(
        status="success",
        data=portfolio_data,
        meta=meta,
    )
