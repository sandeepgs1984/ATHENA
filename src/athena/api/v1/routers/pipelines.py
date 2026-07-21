"""Pipeline runs endpoint router (P8.3)."""

from __future__ import annotations

from datetime import datetime, timezone

from fastapi import APIRouter, Depends, Request, status

from athena.api.dependencies import get_pipelines_service
from athena.api.security import Permission, RequirePermission
from athena.api.security.models import AuthenticatedPrincipal
from athena.api.v1.dtos import (
    AthenaResponse,
    PaginationParams,
    PipelineRunFilterParams,
    ResponseMeta,
    SortParams,
    SystemPipelineResultDTO,
)
from athena.api.v1.dtos.base import PaginationMeta
from athena.api.v1.services.pipelines_service import PipelinesService

router = APIRouter(prefix="/pipelines", tags=["Pipelines"])


@router.get(
    "/runs",
    response_model=AthenaResponse[list[SystemPipelineResultDTO]],
    summary="List pipeline execution runs",
    status_code=status.HTTP_200_OK,
    operation_id="listPipelineRuns",
)
def list_runs(
    request: Request,
    filters: PipelineRunFilterParams = Depends(),  # noqa: B008
    sort: SortParams = Depends(),  # noqa: B008
    pagination: PaginationParams = Depends(),  # noqa: B008
    service: PipelinesService = Depends(get_pipelines_service),  # noqa: B008
    principal: AuthenticatedPrincipal = Depends(RequirePermission(Permission.READ)),  # noqa: B008
) -> AthenaResponse[list[SystemPipelineResultDTO]]:
    """Retrieve system pipeline chains runs history logs."""
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
    response_model=AthenaResponse[SystemPipelineResultDTO],
    summary="Get pipeline execution run details",
    status_code=status.HTTP_200_OK,
    operation_id="getPipelineRun",
)
def get_run(
    request: Request,
    run_id: str,
    service: PipelinesService = Depends(get_pipelines_service),  # noqa: B008
    principal: AuthenticatedPrincipal = Depends(RequirePermission(Permission.READ)),  # noqa: B008
) -> AthenaResponse[SystemPipelineResultDTO]:
    """Retrieve fine-grained stage context and outputs mapping for a specific run."""
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
