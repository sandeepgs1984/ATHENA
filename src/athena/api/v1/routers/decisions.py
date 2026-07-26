"""Decisions endpoint router (P8.3)."""

from __future__ import annotations

from datetime import datetime, timezone

from fastapi import APIRouter, Depends, Query, Request, status

from athena.api.dependencies import get_decisions_service
from athena.api.security import Permission, RequirePermission
from athena.api.security.models import AuthenticatedPrincipal
from athena.api.v1.dtos import (
    AthenaResponse,
    DecisionAnalogsDTO,
    DecisionContextDTO,
    DecisionCounterfactualDTO,
    DecisionDepthDTO,
    DecisionDTO,
    DecisionFilterParams,
    DecisionTraceDTO,
    JournalEntryDTO,
    PaginationParams,
    RecordJournalRequest,
    RecordOutcomeRequest,
    ResetDecisionsRequest,
    ResetDecisionsResultDTO,
    ResponseMeta,
    SortParams,
    TradeOutcomeDTO,
    TradePlanFreshnessDTO,
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
    "/{decision_id}/counterfactual",
    response_model=AthenaResponse[DecisionCounterfactualDTO],
    summary="Get the exact quantified distance from this decision to the TRADE gate",
    status_code=status.HTTP_200_OK,
    operation_id="getDecisionCounterfactual",
)
def get_decision_counterfactual(
    request: Request,
    decision_id: str,
    service: DecisionsService = Depends(get_decisions_service),  # noqa: B008
    principal: AuthenticatedPrincipal = Depends(RequirePermission(Permission.READ)),  # noqa: B008
) -> AthenaResponse[DecisionCounterfactualDTO]:
    """Arithmetic over already-persisted score/confidence/risk values and
    current config thresholds — never a recomputed decision (M-X2)."""
    counterfactual = service.get_decision_counterfactual(decision_id)
    request_id = getattr(request.state, "request_id", "unknown")
    return AthenaResponse(
        status="success",
        data=counterfactual,
        meta=ResponseMeta(
            request_id=request_id, api_version="v1", as_of=datetime.now(tz=timezone.utc)
        ),
    )


@router.get(
    "/{decision_id}/plan-freshness",
    response_model=AthenaResponse[TradePlanFreshnessDTO],
    summary="Get the deterministic decay clock for this decision's TradePlan validity window",
    status_code=status.HTTP_200_OK,
    operation_id="getDecisionPlanFreshness",
)
def get_decision_plan_freshness(
    request: Request,
    decision_id: str,
    as_of: datetime | None = Query(default=None),  # noqa: B008
    service: DecisionsService = Depends(get_decisions_service),  # noqa: B008
    principal: AuthenticatedPrincipal = Depends(RequirePermission(Permission.READ)),  # noqa: B008
) -> AthenaResponse[TradePlanFreshnessDTO]:
    """Pure arithmetic over the plan's already-persisted valid_from/valid_until
    and an as_of instant — never a recomputed plan (M-X3)."""
    freshness = service.get_trade_plan_freshness(decision_id, as_of=as_of)
    request_id = getattr(request.state, "request_id", "unknown")
    return AthenaResponse(
        status="success",
        data=freshness,
        meta=ResponseMeta(
            request_id=request_id, api_version="v1", as_of=datetime.now(tz=timezone.utc)
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
    "/{decision_id}/analogs",
    response_model=AthenaResponse[DecisionAnalogsDTO],
    summary="Get historical decisions with a similar score/confidence/risk fingerprint",
    status_code=status.HTTP_200_OK,
    operation_id="getDecisionAnalogs",
)
def get_decision_analogs(
    request: Request,
    decision_id: str,
    limit: int = Query(default=5, ge=1, le=20),
    service: DecisionsService = Depends(get_decisions_service),  # noqa: B008
    principal: AuthenticatedPrincipal = Depends(RequirePermission(Permission.READ)),  # noqa: B008
) -> AthenaResponse[DecisionAnalogsDTO]:
    """Deterministic nearest-neighbor retrieval over persisted decision
    history, with each match's logged human response and realized outcome
    if any. No generated text, no recomputation of any comparison (M-X1)."""
    analogs = service.get_decision_analogs(decision_id, limit=limit)
    request_id = getattr(request.state, "request_id", "unknown")
    return AthenaResponse(
        status="success",
        data=analogs,
        meta=ResponseMeta(
            request_id=request_id, api_version="v1", as_of=datetime.now(tz=timezone.utc)
        ),
    )


@router.post(
    "/{decision_id}/journal",
    response_model=AthenaResponse[JournalEntryDTO],
    summary="Record the owner's response to a decision (accept/reject/ignore)",
    status_code=status.HTTP_201_CREATED,
    operation_id="recordDecisionJournalEntry",
)
def record_journal_entry(
    body: RecordJournalRequest,
    request: Request,
    decision_id: str,
    service: DecisionsService = Depends(get_decisions_service),  # noqa: B008
    principal: AuthenticatedPrincipal = Depends(RequirePermission(Permission.EXECUTE)),  # noqa: B008
) -> AthenaResponse[JournalEntryDTO]:
    """Persist the owner's response (M-X0, R-9) — nothing is unrecorded."""
    entry = service.record_journal_entry(decision_id, body.user_action, body.notes)
    request_id = getattr(request.state, "request_id", "unknown")
    return AthenaResponse(
        status="success",
        data=entry,
        meta=ResponseMeta(
            request_id=request_id, api_version="v1", as_of=datetime.now(tz=timezone.utc)
        ),
    )


@router.get(
    "/{decision_id}/journal",
    response_model=AthenaResponse[JournalEntryDTO | None],
    summary="Get the owner's most recent response to a decision",
    status_code=status.HTTP_200_OK,
    operation_id="getDecisionJournalEntry",
)
def get_decision_journal_entry(
    request: Request,
    decision_id: str,
    service: DecisionsService = Depends(get_decisions_service),  # noqa: B008
    principal: AuthenticatedPrincipal = Depends(RequirePermission(Permission.READ)),  # noqa: B008
) -> AthenaResponse[JournalEntryDTO | None]:
    """None if the owner has never recorded a response for this decision."""
    entry = service.get_journal_entry(decision_id)
    request_id = getattr(request.state, "request_id", "unknown")
    return AthenaResponse(
        status="success",
        data=entry,
        meta=ResponseMeta(
            request_id=request_id, api_version="v1", as_of=datetime.now(tz=timezone.utc)
        ),
    )


@router.post(
    "/{decision_id}/outcome",
    response_model=AthenaResponse[TradeOutcomeDTO],
    summary="Record the realized outcome for an accepted decision",
    status_code=status.HTTP_201_CREATED,
    operation_id="recordTradeOutcome",
)
def record_trade_outcome(
    body: RecordOutcomeRequest,
    request: Request,
    decision_id: str,
    service: DecisionsService = Depends(get_decisions_service),  # noqa: B008
    principal: AuthenticatedPrincipal = Depends(RequirePermission(Permission.EXECUTE)),  # noqa: B008
) -> AthenaResponse[TradeOutcomeDTO]:
    """PnL, holding time, and TradePlan adherence are computed server-side —
    deterministic and explainable, never client-supplied (M-X0, ADR-005)."""
    outcome = service.record_trade_outcome(decision_id, body)
    request_id = getattr(request.state, "request_id", "unknown")
    return AthenaResponse(
        status="success",
        data=outcome,
        meta=ResponseMeta(
            request_id=request_id, api_version="v1", as_of=datetime.now(tz=timezone.utc)
        ),
    )


@router.get(
    "/{decision_id}/outcome",
    response_model=AthenaResponse[TradeOutcomeDTO | None],
    summary="Get the realized outcome for a decision",
    status_code=status.HTTP_200_OK,
    operation_id="getTradeOutcome",
)
def get_trade_outcome(
    request: Request,
    decision_id: str,
    service: DecisionsService = Depends(get_decisions_service),  # noqa: B008
    principal: AuthenticatedPrincipal = Depends(RequirePermission(Permission.READ)),  # noqa: B008
) -> AthenaResponse[TradeOutcomeDTO | None]:
    """None if no outcome has been logged for this decision."""
    outcome = service.get_trade_outcome(decision_id)
    request_id = getattr(request.state, "request_id", "unknown")
    return AthenaResponse(
        status="success",
        data=outcome,
        meta=ResponseMeta(
            request_id=request_id, api_version="v1", as_of=datetime.now(tz=timezone.utc)
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


@router.post(
    "/reset",
    response_model=AthenaResponse[ResetDecisionsResultDTO],
    summary="Reset the Decisions & Trace domain (CONFIRM-gated)",
    status_code=status.HTTP_200_OK,
    operation_id="resetDecisions",
)
def reset_decisions(
    body: ResetDecisionsRequest,
    request: Request,
    service: DecisionsService = Depends(get_decisions_service),  # noqa: B008
    principal: AuthenticatedPrincipal = Depends(RequirePermission(Permission.ADMIN)),  # noqa: B008
) -> AthenaResponse[ResetDecisionsResultDTO]:
    """Delete all decisions, traces, journal entries, and realized outcomes
    after a typed CONFIRM, with a best-effort automatic backup first. Does
    not touch runs, portfolio positions, or owner candidates."""
    result = service.reset_decisions(confirmation=body.confirmation)
    return AthenaResponse(
        status="success",
        data=result,
        meta=ResponseMeta(
            request_id=getattr(request.state, "request_id", "unknown"),
            api_version="v1",
            as_of=datetime.now(tz=timezone.utc),
        ),
    )

