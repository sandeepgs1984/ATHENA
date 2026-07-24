"""Portfolio endpoint router (P8.3 / owner fill ledger)."""

from __future__ import annotations

from datetime import datetime, timezone

from fastapi import APIRouter, Depends, Request, status

from athena.api.dependencies import get_portfolio_service
from athena.api.security import Permission, RequirePermission
from athena.api.security.models import AuthenticatedPrincipal
from athena.api.v1.dtos import AthenaResponse, PortfolioDTO, ResponseMeta
from athena.api.v1.dtos.portfolio import ClosePositionRequest, OpenPositionRequest
from athena.api.v1.services.portfolio_service import PortfolioService

router = APIRouter(prefix="/portfolio", tags=["Portfolio"])


def _meta(request: Request) -> ResponseMeta:
    request_id = getattr(request.state, "request_id", "unknown")
    return ResponseMeta(
        request_id=request_id,
        api_version="v1",
        as_of=datetime.now(tz=timezone.utc),
    )


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
    return AthenaResponse(
        status="success",
        data=portfolio_data,
        meta=_meta(request),
    )


@router.post(
    "/positions",
    response_model=AthenaResponse[PortfolioDTO],
    summary="Log an owner-entered open fill",
    status_code=status.HTTP_201_CREATED,
    operation_id="openPortfolioPosition",
)
def open_position(
    body: OpenPositionRequest,
    request: Request,
    service: PortfolioService = Depends(get_portfolio_service),  # noqa: B008
    principal: AuthenticatedPrincipal = Depends(RequirePermission(Permission.EXECUTE)),  # noqa: B008
) -> AthenaResponse[PortfolioDTO]:
    """Record a fill the owner placed on Kite/Groww after an ATHENA suggestion."""
    portfolio_data = service.open_position(
        instrument_id=body.instrument_id,
        quantity=body.quantity,
        avg_price=body.avg_price,
        opened_ts=body.opened_ts,
        decision_ref=body.decision_ref,
        broker=body.broker,
        notes=body.notes,
        sector=body.sector,
    )
    return AthenaResponse(
        status="success",
        data=portfolio_data,
        meta=_meta(request),
    )


@router.post(
    "/positions/{position_id}/close",
    response_model=AthenaResponse[PortfolioDTO],
    summary="Log an owner-entered exit fill",
    status_code=status.HTTP_200_OK,
    operation_id="closePortfolioPosition",
)
def close_position(
    position_id: str,
    body: ClosePositionRequest,
    request: Request,
    service: PortfolioService = Depends(get_portfolio_service),  # noqa: B008
    principal: AuthenticatedPrincipal = Depends(RequirePermission(Permission.EXECUTE)),  # noqa: B008
) -> AthenaResponse[PortfolioDTO]:
    """Close a previously logged open position with the owner exit price."""
    portfolio_data = service.close_position(
        position_id,
        exit_price=body.exit_price,
        closed_ts=body.closed_ts,
    )
    return AthenaResponse(
        status="success",
        data=portfolio_data,
        meta=_meta(request),
    )
