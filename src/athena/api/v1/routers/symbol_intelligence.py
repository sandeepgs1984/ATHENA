"""Symbol Intelligence composition endpoints (SI-P1).

GET is read-only. POST Analyze may hydrate this symbol's D1, then re-reads.
Neither path runs DecisionEngine, Portfolio Sync, or DarvaX scan.
"""

from __future__ import annotations

from datetime import datetime, timezone

from fastapi import APIRouter, Depends, Query, Request, status

from athena.api.dependencies import get_symbol_intelligence_service
from athena.api.security import Permission, RequirePermission
from athena.api.security.models import AuthenticatedPrincipal
from athena.api.v1.dtos import AthenaResponse, ResponseMeta
from athena.api.v1.dtos.symbol_intelligence import SiSearchResultDTO, SymbolIntelligenceBundleDTO
from athena.api.v1.services.symbol_intelligence_service import SymbolIntelligenceService

router = APIRouter(prefix="/symbol-intelligence", tags=["Symbol Intelligence"])


def _meta(request: Request) -> ResponseMeta:
    request_id = getattr(request.state, "request_id", "unknown")
    return ResponseMeta(
        request_id=request_id,
        api_version="v1",
        as_of=datetime.now(tz=timezone.utc),
    )


@router.get(
    "/search",
    response_model=AthenaResponse[SiSearchResultDTO],
    summary="Search canonical instruments for Symbol Intelligence",
    status_code=status.HTTP_200_OK,
    operation_id="searchSymbolIntelligence",
)
def search_symbols(
    request: Request,
    q: str = Query(min_length=1, max_length=64),
    service: SymbolIntelligenceService = Depends(get_symbol_intelligence_service),  # noqa: B008
    principal: AuthenticatedPrincipal = Depends(RequirePermission(Permission.READ)),  # noqa: B008
) -> AthenaResponse[SiSearchResultDTO]:
    return AthenaResponse(status="success", data=service.search(q), meta=_meta(request))


@router.get(
    "/{query:path}",
    response_model=AthenaResponse[SymbolIntelligenceBundleDTO],
    summary="Compose current persisted Symbol Intelligence for one query",
    status_code=status.HTTP_200_OK,
    operation_id="getSymbolIntelligence",
)
def get_symbol_intelligence(
    query: str,
    request: Request,
    service: SymbolIntelligenceService = Depends(get_symbol_intelligence_service),  # noqa: B008
    principal: AuthenticatedPrincipal = Depends(RequirePermission(Permission.READ)),  # noqa: B008
) -> AthenaResponse[SymbolIntelligenceBundleDTO]:
    """Read-only composition. Does not generate Decisions, sync Portfolio, or scan DarvaX."""
    return AthenaResponse(status="success", data=service.compose(query), meta=_meta(request))


@router.post(
    "/{query:path}",
    response_model=AthenaResponse[SymbolIntelligenceBundleDTO],
    summary="Analyze one symbol with symbol-scoped D1 hydration when stale",
    status_code=status.HTTP_200_OK,
    operation_id="analyzeSymbolIntelligence",
)
def analyze_symbol_intelligence(
    query: str,
    request: Request,
    service: SymbolIntelligenceService = Depends(get_symbol_intelligence_service),  # noqa: B008
    principal: AuthenticatedPrincipal = Depends(RequirePermission(Permission.EXECUTE)),  # noqa: B008
) -> AthenaResponse[SymbolIntelligenceBundleDTO]:
    """Hydrate missing/stale D1 for this symbol, then re-read SI. No DecisionEngine."""
    return AthenaResponse(
        status="success",
        data=service.compose(query, refresh_market=True),
        meta=_meta(request),
    )
