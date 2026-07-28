"""Market Intelligence candidate list router."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Literal

from fastapi import APIRouter, Depends, Query, Request, status

from athena.api.dependencies import (
    get_candidates_service,
    get_market_history_service,
    get_market_summary_service,
)
from athena.api.security import Permission, RequirePermission
from athena.api.security.models import AuthenticatedPrincipal
from athena.api.v1.dtos import AthenaResponse, ResponseMeta
from athena.api.v1.dtos.market import (
    CandleSeriesDTO,
    DeleteCandidateResultDTO,
    FullValidationProgressDTO,
    MarketSummaryDTO,
    MarketTickerDTO,
    OwnerCandidateDTO,
    OwnerCandidateListDTO,
    UpsertCandidateRequest,
    ValidateSymbolsRequest,
    ValidateSymbolsResultDTO,
)
from athena.api.v1.services.candidates_service import CandidatesService
from athena.api.v1.services.market_history_service import MarketHistoryService
from athena.api.v1.services.market_summary_service import MarketSummaryService
from athena.domain.enums import Timeframe

router = APIRouter(prefix="/market", tags=["Market"])


def _meta(request: Request) -> ResponseMeta:
    request_id = getattr(request.state, "request_id", "unknown")
    return ResponseMeta(
        request_id=request_id,
        api_version="v1",
        as_of=datetime.now(tz=timezone.utc),
    )


@router.get(
    "/instruments/{instrument_id}/candles",
    response_model=AthenaResponse[CandleSeriesDTO],
    summary="Recent persisted candles for an instrument",
    status_code=status.HTTP_200_OK,
    operation_id="getInstrumentCandles",
)
def get_instrument_candles(
    instrument_id: str,
    request: Request,
    timeframe: Literal["1m", "5m", "15m"] = Query(default="5m"),
    limit: int = Query(default=120, ge=1, le=500),
    service: MarketHistoryService = Depends(get_market_history_service),  # noqa: B008
    principal: AuthenticatedPrincipal = Depends(RequirePermission(Permission.READ)),  # noqa: B008
) -> AthenaResponse[CandleSeriesDTO]:
    """Return chronological OHLCV from the validated SQLite ledger only."""
    data = service.recent_candles(
        instrument_id,
        Timeframe(timeframe),
        limit=limit,
    )
    return AthenaResponse(status="success", data=data, meta=_meta(request))


@router.get(
    "/summary",
    response_model=AthenaResponse[MarketSummaryDTO],
    summary="Market Summary hero — regime, F-5 score, universe breadth, sparklines",
    status_code=status.HTTP_200_OK,
    operation_id="getMarketSummary",
)
def get_market_summary(
    request: Request,
    service: MarketSummaryService = Depends(get_market_summary_service),  # noqa: B008
    principal: AuthenticatedPrincipal = Depends(RequirePermission(Permission.READ)),  # noqa: B008
) -> AthenaResponse[MarketSummaryDTO]:
    """Persisted validation-run artifacts only — score/breadth null when absent."""
    data = service.market_summary()
    return AthenaResponse(status="success", data=data, meta=_meta(request))


@router.get(
    "/ticker",
    response_model=AthenaResponse[MarketTickerDTO],
    summary="Header market ticker — NIFTY 50 / BANK NIFTY / INDIA VIX",
    status_code=status.HTTP_200_OK,
    operation_id="getMarketTicker",
)
def get_market_ticker(
    request: Request,
    service: MarketHistoryService = Depends(get_market_history_service),  # noqa: B008
    principal: AuthenticatedPrincipal = Depends(RequirePermission(Permission.READ)),  # noqa: B008
) -> AthenaResponse[MarketTickerDTO]:
    """Level + day-change % for each index, from the latest persisted Kite
    snapshot and daily candles only — no new provider, no new calculations
    beyond simple arithmetic over already-persisted values."""
    data = service.market_ticker()
    return AthenaResponse(status="success", data=data, meta=_meta(request))


@router.get(
    "/candidates",
    response_model=AthenaResponse[OwnerCandidateListDTO],
    summary="List owner validation candidates",
    status_code=status.HTTP_200_OK,
    operation_id="listOwnerCandidates",
)
def list_candidates(
    request: Request,
    active_only: bool = Query(default=True),
    service: CandidatesService = Depends(get_candidates_service),  # noqa: B008
    principal: AuthenticatedPrincipal = Depends(RequirePermission(Permission.READ)),  # noqa: B008
) -> AthenaResponse[OwnerCandidateListDTO]:
    data = service.list_candidates(active_only=active_only)
    return AthenaResponse(status="success", data=data, meta=_meta(request))


@router.put(
    "/candidates",
    response_model=AthenaResponse[OwnerCandidateDTO],
    summary="Add or update an owner validation candidate",
    status_code=status.HTTP_200_OK,
    operation_id="upsertOwnerCandidate",
)
def upsert_candidate(
    body: UpsertCandidateRequest,
    request: Request,
    service: CandidatesService = Depends(get_candidates_service),  # noqa: B008
    principal: AuthenticatedPrincipal = Depends(RequirePermission(Permission.EXECUTE)),  # noqa: B008
) -> AthenaResponse[OwnerCandidateDTO]:
    data = service.upsert_candidate(body)
    return AthenaResponse(status="success", data=data, meta=_meta(request))


@router.post(
    "/candidates",
    response_model=AthenaResponse[OwnerCandidateDTO],
    summary="Add or update an owner validation candidate",
    status_code=status.HTTP_201_CREATED,
    operation_id="createOwnerCandidate",
)
def create_candidate(
    body: UpsertCandidateRequest,
    request: Request,
    service: CandidatesService = Depends(get_candidates_service),  # noqa: B008
    principal: AuthenticatedPrincipal = Depends(RequirePermission(Permission.EXECUTE)),  # noqa: B008
) -> AthenaResponse[OwnerCandidateDTO]:
    data = service.upsert_candidate(body)
    return AthenaResponse(status="success", data=data, meta=_meta(request))


@router.post(
    "/validate",
    response_model=AthenaResponse[ValidateSymbolsResultDTO],
    summary="Validate one or more owner candidates now (ingest + score)",
    status_code=status.HTTP_200_OK,
    operation_id="validateOwnerCandidates",
)
def validate_candidates(
    body: ValidateSymbolsRequest,
    request: Request,
    service: CandidatesService = Depends(get_candidates_service),  # noqa: B008
    principal: AuthenticatedPrincipal = Depends(RequirePermission(Permission.EXECUTE)),  # noqa: B008
) -> AthenaResponse[ValidateSymbolsResultDTO]:
    """Run a scoped kite ingest + eligibility + decision cycle for the given symbols."""
    data = service.validate_candidates(body)
    return AthenaResponse(status="success", data=data, meta=_meta(request))


@router.post(
    "/validate-all",
    response_model=AthenaResponse[FullValidationProgressDTO],
    summary="Start owner-triggered full-universe validation (background)",
    status_code=status.HTTP_202_ACCEPTED,
    operation_id="startFullUniverseValidation",
)
def start_full_validation(
    request: Request,
    service: CandidatesService = Depends(get_candidates_service),  # noqa: B008
    principal: AuthenticatedPrincipal = Depends(RequirePermission(Permission.EXECUTE)),  # noqa: B008
) -> AthenaResponse[FullValidationProgressDTO]:
    """ADR-007 / MI-5: one run over all active candidates; poll GET /validate-all."""
    data = service.start_full_validation()
    return AthenaResponse(status="success", data=data, meta=_meta(request))


@router.get(
    "/validate-all",
    response_model=AthenaResponse[FullValidationProgressDTO],
    summary="Poll full-universe validation progress",
    status_code=status.HTTP_200_OK,
    operation_id="getFullUniverseValidationStatus",
)
def full_validation_status(
    request: Request,
    service: CandidatesService = Depends(get_candidates_service),  # noqa: B008
    principal: AuthenticatedPrincipal = Depends(RequirePermission(Permission.READ)),  # noqa: B008
) -> AthenaResponse[FullValidationProgressDTO]:
    data = service.full_validation_status()
    return AthenaResponse(status="success", data=data, meta=_meta(request))


@router.delete(
    "/candidates/{symbol}",
    response_model=AthenaResponse[DeleteCandidateResultDTO],
    summary="Remove an owner validation candidate",
    status_code=status.HTTP_200_OK,
    operation_id="deleteOwnerCandidate",
)
def delete_candidate(
    symbol: str,
    request: Request,
    service: CandidatesService = Depends(get_candidates_service),  # noqa: B008
    principal: AuthenticatedPrincipal = Depends(RequirePermission(Permission.EXECUTE)),  # noqa: B008
) -> AthenaResponse[DeleteCandidateResultDTO]:
    data = service.delete_candidate(symbol)
    return AthenaResponse(status="success", data=data, meta=_meta(request))
