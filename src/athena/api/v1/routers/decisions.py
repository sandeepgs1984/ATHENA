"""Decisions endpoint router (P8.3)."""

from __future__ import annotations

from datetime import datetime, timezone

from fastapi import APIRouter, Depends, Request, status

from athena.api.dependencies import get_decisions_service
from athena.api.security import Permission, RequirePermission
from athena.api.security.models import AuthenticatedPrincipal
from athena.api.v1.dtos import (
    AthenaResponse,
    DecisionContextDTO,
    DecisionDepthDTO,
    DecisionDTO,
    DecisionFilterParams,
    DecisionTraceDTO,
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


@router.get(
    "/{decision_id}/depth",
    response_model=AthenaResponse[DecisionDepthDTO],
    summary="Get persisted decision analytical depth",
    status_code=status.HTTP_200_OK,
    operation_id="getDecisionDepth",
)
def get_decision_depth(
    request: Request,
    decision_id: str,
    service: DecisionsService = Depends(get_decisions_service),  # noqa: B008
    principal: AuthenticatedPrincipal = Depends(RequirePermission(Permission.READ)),  # noqa: B008
) -> AthenaResponse[DecisionDepthDTO]:
    """Render eligibility, score, confidence, and risk artifacts without recomputation."""
    depth = service.get_decision_depth(decision_id)
    request_id = getattr(request.state, "request_id", "unknown")
    return AthenaResponse(
        status="success",
        data=depth,
        meta=ResponseMeta(
            request_id=request_id,
            api_version="v1",
            as_of=datetime.now(tz=timezone.utc),
        ),
    )


@router.get(
    "/{decision_id}/context",
    response_model=AthenaResponse[DecisionContextDTO],
    summary="Get session/calendar, regime/market-health, and curated links for a decision",
    status_code=status.HTTP_200_OK,
    operation_id="getDecisionContext",
)
def get_decision_context(
    request: Request,
    decision_id: str,
    service: DecisionsService = Depends(get_decisions_service),  # noqa: B008
    principal: AuthenticatedPrincipal = Depends(RequirePermission(Permission.READ)),  # noqa: B008
) -> AthenaResponse[DecisionContextDTO]:
    """Render session/calendar context, persisted regime/market-health, and
    owner-curated external links. No news ingestion, no generated rationale."""
    context = service.get_decision_context(decision_id)
    request_id = getattr(request.state, "request_id", "unknown")
    return AthenaResponse(
        status="success",
        data=context,
        meta=ResponseMeta(
            request_id=request_id,
            api_version="v1",
            as_of=datetime.now(tz=timezone.utc),
        ),
    )


@router.get(
    "/{decision_id}/trace",
    response_model=AthenaResponse[DecisionTraceDTO],
    summary="Get decision execution trace DAG flow",
    status_code=status.HTTP_200_OK,
    operation_id="getDecisionTrace",
)
def get_decision_trace(
    request: Request,
    decision_id: str,
    service: DecisionsService = Depends(get_decisions_service),  # noqa: B008
    principal: AuthenticatedPrincipal = Depends(RequirePermission(Permission.READ)),  # noqa: B008
) -> AthenaResponse[DecisionTraceDTO]:
    """Retrieve the reasoning DAG trace showing pipeline stages from ingest to safety checks."""
    trace_data = service.get_decision_trace(decision_id)
    request_id = getattr(request.state, "request_id", "unknown")

    meta = ResponseMeta(
        request_id=request_id,
        api_version="v1",
        as_of=datetime.now(tz=timezone.utc),
    )

    return AthenaResponse(
        status="success",
        data=trace_data,
        meta=meta,
    )

