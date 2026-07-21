"""Scheduler history endpoint router (P8.3)."""

from __future__ import annotations

from datetime import datetime, timezone

from fastapi import APIRouter, Depends, Request, status

from athena.api.dependencies import get_scheduler_service
from athena.api.security import Permission, RequirePermission
from athena.api.security.models import AuthenticatedPrincipal
from athena.api.v1.dtos import (
    AthenaResponse,
    PaginationParams,
    PipelineScheduleRunDTO,
    ResponseMeta,
    SchedulerHistoryFilterParams,
    SortParams,
)
from athena.api.v1.dtos.base import PaginationMeta
from athena.api.v1.services.scheduler_service import SchedulerService

router = APIRouter(prefix="/scheduler", tags=["Scheduler"])


@router.get(
    "/history",
    response_model=AthenaResponse[list[PipelineScheduleRunDTO]],
    summary="List scheduled pipeline runs history",
    status_code=status.HTTP_200_OK,
    operation_id="listSchedulerHistory",
)
def list_history(
    request: Request,
    filters: SchedulerHistoryFilterParams = Depends(),  # noqa: B008
    sort: SortParams = Depends(),  # noqa: B008
    pagination: PaginationParams = Depends(),  # noqa: B008
    service: SchedulerService = Depends(get_scheduler_service),  # noqa: B008
    principal: AuthenticatedPrincipal = Depends(RequirePermission(Permission.READ)),  # noqa: B008
) -> AthenaResponse[list[PipelineScheduleRunDTO]]:
    """Retrieve history of scheduler cycle executions and durations."""
    result = service.list_history(filters, sort, pagination)
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
    "/history/{schedule_run_id}",
    response_model=AthenaResponse[PipelineScheduleRunDTO],
    summary="Get scheduled pipeline run details",
    status_code=status.HTTP_200_OK,
    operation_id="getSchedulerRun",
)
def get_run(
    request: Request,
    schedule_run_id: str,
    service: SchedulerService = Depends(get_scheduler_service),  # noqa: B008
    principal: AuthenticatedPrincipal = Depends(RequirePermission(Permission.READ)),  # noqa: B008
) -> AthenaResponse[PipelineScheduleRunDTO]:
    """Retrieve detailed scheduled cycle envelope execution details."""
    run_data = service.get_run(schedule_run_id)
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
