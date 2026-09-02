"""My Portfolio import/reconciliation endpoints (PS-P2)."""

from __future__ import annotations

from datetime import datetime, timezone

from fastapi import APIRouter, Depends, Query, Request, Response, status

from athena.api.dependencies import get_my_portfolio_service
from athena.api.security import Permission, RequirePermission
from athena.api.security.models import AuthenticatedPrincipal
from athena.api.v1.dtos import AthenaResponse, ResponseMeta
from athena.api.v1.dtos.portfolio import (
    MyPortfolioHoldingDTO,
    PortfolioImportConfirmRequest,
    PortfolioImportConfirmResultDTO,
    PortfolioImportHistoryDTO,
    PortfolioImportPreviewDTO,
    PortfolioReconciliationChangeDTO,
)
from athena.api.v1.services.my_portfolio_service import MyPortfolioService

router = APIRouter(prefix="/my-portfolio", tags=["My Portfolio"])


def _meta(request: Request) -> ResponseMeta:
    request_id = getattr(request.state, "request_id", "unknown")
    return ResponseMeta(
        request_id=request_id,
        api_version="v1",
        as_of=datetime.now(tz=timezone.utc),
    )


@router.post(
    "/imports",
    response_model=AthenaResponse[PortfolioImportPreviewDTO],
    summary="Upload and preview My Portfolio holdings",
    status_code=status.HTTP_201_CREATED,
    operation_id="previewMyPortfolioImport",
)
async def preview_import(
    request: Request,
    response: Response,
    filename: str = Query(min_length=1),
    service: MyPortfolioService = Depends(get_my_portfolio_service),  # noqa: B008
    principal: AuthenticatedPrincipal = Depends(RequirePermission(Permission.EXECUTE)),  # noqa: B008
) -> AthenaResponse[PortfolioImportPreviewDTO]:
    """Parse CSV/XLSX bytes and persist a preview without mutating holdings."""

    data = await request.body()
    preview = service.preview_import(filename=filename, content=data)
    if preview.status.value == "FAILED":
        response.status_code = status.HTTP_400_BAD_REQUEST
    return AthenaResponse(status="success", data=preview, meta=_meta(request))


@router.get(
    "/imports",
    response_model=AthenaResponse[PortfolioImportHistoryDTO],
    summary="List My Portfolio import history",
    status_code=status.HTTP_200_OK,
    operation_id="listMyPortfolioImports",
)
def list_imports(
    request: Request,
    limit: int = Query(default=50, ge=1, le=500),
    service: MyPortfolioService = Depends(get_my_portfolio_service),  # noqa: B008
    principal: AuthenticatedPrincipal = Depends(RequirePermission(Permission.READ)),  # noqa: B008
) -> AthenaResponse[PortfolioImportHistoryDTO]:
    return AthenaResponse(
        status="success",
        data=service.import_history(limit=limit),
        meta=_meta(request),
    )


@router.get(
    "/imports/{import_id}",
    response_model=AthenaResponse[PortfolioImportPreviewDTO],
    summary="Retrieve a persisted My Portfolio import preview",
    status_code=status.HTTP_200_OK,
    operation_id="getMyPortfolioImport",
)
def get_import(
    import_id: str,
    request: Request,
    service: MyPortfolioService = Depends(get_my_portfolio_service),  # noqa: B008
    principal: AuthenticatedPrincipal = Depends(RequirePermission(Permission.READ)),  # noqa: B008
) -> AthenaResponse[PortfolioImportPreviewDTO]:
    return AthenaResponse(
        status="success",
        data=service.get_import_preview(import_id),
        meta=_meta(request),
    )


@router.post(
    "/imports/{import_id}/confirm",
    response_model=AthenaResponse[PortfolioImportConfirmResultDTO],
    summary="Confirm a clean My Portfolio import preview",
    status_code=status.HTTP_200_OK,
    operation_id="confirmMyPortfolioImport",
)
def confirm_import(
    import_id: str,
    body: PortfolioImportConfirmRequest,
    request: Request,
    service: MyPortfolioService = Depends(get_my_portfolio_service),  # noqa: B008
    principal: AuthenticatedPrincipal = Depends(RequirePermission(Permission.EXECUTE)),  # noqa: B008
) -> AthenaResponse[PortfolioImportConfirmResultDTO]:
    return AthenaResponse(
        status="success",
        data=service.confirm_import(import_id=import_id, confirmation=body.confirmation),
        meta=_meta(request),
    )


@router.get(
    "/holdings",
    response_model=AthenaResponse[list[MyPortfolioHoldingDTO]],
    summary="List canonical My Portfolio holdings",
    status_code=status.HTTP_200_OK,
    operation_id="listMyPortfolioHoldings",
)
def list_holdings(
    request: Request,
    service: MyPortfolioService = Depends(get_my_portfolio_service),  # noqa: B008
    principal: AuthenticatedPrincipal = Depends(RequirePermission(Permission.READ)),  # noqa: B008
) -> AthenaResponse[list[MyPortfolioHoldingDTO]]:
    return AthenaResponse(
        status="success",
        data=service.list_holdings(),
        meta=_meta(request),
    )


@router.get(
    "/imports/{import_id}/reconciliations",
    response_model=AthenaResponse[list[PortfolioReconciliationChangeDTO]],
    summary="List reconciliation audit entries for a My Portfolio import",
    status_code=status.HTTP_200_OK,
    operation_id="listMyPortfolioReconciliations",
)
def list_reconciliations(
    import_id: str,
    request: Request,
    service: MyPortfolioService = Depends(get_my_portfolio_service),  # noqa: B008
    principal: AuthenticatedPrincipal = Depends(RequirePermission(Permission.READ)),  # noqa: B008
) -> AthenaResponse[list[PortfolioReconciliationChangeDTO]]:
    return AthenaResponse(
        status="success",
        data=service.reconciliation_history(import_id),
        meta=_meta(request),
    )
