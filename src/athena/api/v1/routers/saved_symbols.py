"""Owner-curated "Saved Symbols" watch list router (UX-9b)."""

from __future__ import annotations

from datetime import datetime, timezone

from fastapi import APIRouter, Depends, Request, status

from athena.api.dependencies import get_saved_symbols_service
from athena.api.security import Permission, RequirePermission
from athena.api.security.models import AuthenticatedPrincipal
from athena.api.v1.dtos import AthenaResponse, ResponseMeta
from athena.api.v1.dtos.saved_symbols import (
    AddSavedSymbolRequest,
    RemoveSavedSymbolResultDTO,
    SavedSymbolDTO,
    SavedSymbolListDTO,
)
from athena.api.v1.services.saved_symbols_service import SavedSymbolsService

router = APIRouter(prefix="/saved-symbols", tags=["Saved Symbols"])


def _meta(request: Request) -> ResponseMeta:
    request_id = getattr(request.state, "request_id", "unknown")
    return ResponseMeta(
        request_id=request_id,
        api_version="v1",
        as_of=datetime.now(tz=timezone.utc),
    )


@router.get(
    "",
    response_model=AthenaResponse[SavedSymbolListDTO],
    summary="List the owner's saved symbols (personal watch list)",
    status_code=status.HTTP_200_OK,
    operation_id="listSavedSymbols",
)
def list_saved_symbols(
    request: Request,
    service: SavedSymbolsService = Depends(get_saved_symbols_service),  # noqa: B008
    principal: AuthenticatedPrincipal = Depends(RequirePermission(Permission.READ)),  # noqa: B008
) -> AthenaResponse[SavedSymbolListDTO]:
    data = service.list_saved_symbols()
    return AthenaResponse(status="success", data=data, meta=_meta(request))


@router.post(
    "",
    response_model=AthenaResponse[SavedSymbolDTO],
    summary="Save a symbol to the owner's personal watch list",
    status_code=status.HTTP_201_CREATED,
    operation_id="addSavedSymbol",
)
def add_saved_symbol(
    body: AddSavedSymbolRequest,
    request: Request,
    service: SavedSymbolsService = Depends(get_saved_symbols_service),  # noqa: B008
    principal: AuthenticatedPrincipal = Depends(RequirePermission(Permission.EXECUTE)),  # noqa: B008
) -> AthenaResponse[SavedSymbolDTO]:
    data = service.add_saved_symbol(body)
    return AthenaResponse(status="success", data=data, meta=_meta(request))


@router.delete(
    "/{symbol}",
    response_model=AthenaResponse[RemoveSavedSymbolResultDTO],
    summary="Remove a symbol from the owner's personal watch list",
    status_code=status.HTTP_200_OK,
    operation_id="removeSavedSymbol",
)
def remove_saved_symbol(
    symbol: str,
    request: Request,
    service: SavedSymbolsService = Depends(get_saved_symbols_service),  # noqa: B008
    principal: AuthenticatedPrincipal = Depends(RequirePermission(Permission.EXECUTE)),  # noqa: B008
) -> AthenaResponse[RemoveSavedSymbolResultDTO]:
    data = service.remove_saved_symbol(symbol)
    return AthenaResponse(status="success", data=data, meta=_meta(request))
