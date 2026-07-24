"""Market Intelligence candidate list router."""

from __future__ import annotations

from datetime import datetime, timezone

from fastapi import APIRouter, Depends, Query, Request, status

from athena.api.dependencies import get_candidates_service
from athena.api.security import Permission, RequirePermission
from athena.api.security.models import AuthenticatedPrincipal
from athena.api.v1.dtos import AthenaResponse, ResponseMeta
from athena.api.v1.dtos.market import (
    DeleteCandidateResultDTO,
    OwnerCandidateDTO,
    OwnerCandidateListDTO,
    UpsertCandidateRequest,
    ValidateSymbolsRequest,
    ValidateSymbolsResultDTO,
)
from athena.api.v1.services.candidates_service import CandidatesService

router = APIRouter(prefix="/market", tags=["Market"])


def _meta(request: Request) -> ResponseMeta:
    request_id = getattr(request.state, "request_id", "unknown")
    return ResponseMeta(
        request_id=request_id,
        api_version="v1",
        as_of=datetime.now(tz=timezone.utc),
    )


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
