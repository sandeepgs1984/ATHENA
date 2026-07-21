"""Decisions endpoint router (P8.3)."""

from __future__ import annotations

from datetime import datetime, timezone

from fastapi import APIRouter, Depends, Request, status

from athena.api.dependencies import get_decisions_service
from athena.api.security import Permission, RequirePermission
from athena.api.security.models import AuthenticatedPrincipal
from athena.api.v1.dtos import (
    AthenaResponse,
    DecisionDTO,
    DecisionFilterParams,
    PaginationParams,
    ResponseMeta,
    SortParams,
)
from athena.api.v1.dtos.base import PaginationMeta
from athena.api.v1.services.decisions_service import DecisionsService

router = APIRouter(prefix="/decisions", tags=["Decisions"])


@router.get(
    "",
    response_model=AthenaResponse[list[DecisionDTO]],
    summary="List trading decisions",
    status_code=status.HTTP_200_OK,
    operation_id="listDecisions",
)
def list_decisions(
    request: Request,
    filters: DecisionFilterParams = Depends(),  # noqa: B008
    sort: SortParams = Depends(),  # noqa: B008
    pagination: PaginationParams = Depends(),  # noqa: B008
    service: DecisionsService = Depends(get_decisions_service),  # noqa: B008
    principal: AuthenticatedPrincipal = Depends(RequirePermission(Permission.READ)),  # noqa: B008
) -> AthenaResponse[list[DecisionDTO]]:
    """Retrieve a paginated collection of trading decisions, supporting sorting and filtering."""
    result = service.list_decisions(filters, sort, pagination)
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
    "/{decision_id}",
    response_model=AthenaResponse[DecisionDTO],
    summary="Get decision details",
    status_code=status.HTTP_200_OK,
    operation_id="getDecision",
)
def get_decision(
    request: Request,
    decision_id: str,
    service: DecisionsService = Depends(get_decisions_service),  # noqa: B008
    principal: AuthenticatedPrincipal = Depends(RequirePermission(Permission.READ)),  # noqa: B008
) -> AthenaResponse[DecisionDTO]:
    """Retrieve detailed analysis, quality gates, and trade plans for a specific decision."""
    decision_data = service.get_decision(decision_id)
    request_id = getattr(request.state, "request_id", "unknown")

    meta = ResponseMeta(
        request_id=request_id,
        api_version="v1",
        as_of=datetime.now(tz=timezone.utc),
    )

    return AthenaResponse(
        status="success",
        data=decision_data,
        meta=meta,
    )
