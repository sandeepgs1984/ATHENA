"""Backtests endpoint router (P9.5)."""

from __future__ import annotations

from datetime import datetime, timezone

from fastapi import APIRouter, Depends, Request, status

from athena.api.dependencies import get_backtests_service
from athena.api.security import Permission, RequirePermission
from athena.api.security.models import AuthenticatedPrincipal
from athena.api.v1.dtos import (
    AthenaResponse,
    BacktestRunDTO,
    BacktestRunSummaryDTO,
    EmptyFilterParams,
    PaginationParams,
    ResponseMeta,
    SortParams,
)
from athena.api.v1.dtos.base import PaginationMeta
from athena.api.v1.services.backtests_service import BacktestsService

router = APIRouter(prefix="/backtests", tags=["Backtests"])


@router.get(
    "/runs",
    response_model=AthenaResponse[list[BacktestRunSummaryDTO]],
    summary="List backtest runs history",
    status_code=status.HTTP_200_OK,
    operation_id="listBacktestRuns",
)
def list_runs(
    request: Request,
    filters: EmptyFilterParams = Depends(),  # noqa: B008
    sort: SortParams = Depends(),  # noqa: B008
    pagination: PaginationParams = Depends(),  # noqa: B008
    service: BacktestsService = Depends(get_backtests_service),  # noqa: B008
    principal: AuthenticatedPrincipal = Depends(RequirePermission(Permission.READ)),  # noqa: B008
) -> AthenaResponse[list[BacktestRunSummaryDTO]]:
    """Retrieve history of completed historical backtest runs."""
    result = service.list_runs(filters, sort, pagination)
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
    "/runs/{run_id}",
    response_model=AthenaResponse[BacktestRunDTO],
    summary="Get backtest run details",
    status_code=status.HTTP_200_OK,
    operation_id="getBacktestRun",
)
def get_run(
    request: Request,
    run_id: str,
    service: BacktestsService = Depends(get_backtests_service),  # noqa: B008
    principal: AuthenticatedPrincipal = Depends(RequirePermission(Permission.READ)),  # noqa: B008
) -> AthenaResponse[BacktestRunDTO]:
    """Retrieve detailed step chronology and strategy performance logs for a specific backtest run."""
    run_data = service.get_run(run_id)
    request_id = getattr(request.state, "request_id", "unknown")

    meta = ResponseMeta(
        request_id=request_id,
        api_version="v1",
        as_of=datetime.now(tz=timezone.utc),
    )

    return AthenaResponse(
        status="success",
        data=run_data,
        meta=meta,
    )
