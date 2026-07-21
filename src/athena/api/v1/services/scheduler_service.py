"""Scheduler history business service (P8.3)."""

from __future__ import annotations

from typing import TYPE_CHECKING

from athena.api.exceptions import SchedulerRunNotFoundError
from athena.api.v1.dtos import (
    CollectionResult,
    PipelineScheduleRunDTO,
    QuerySpecification,
    ResourceReference,
)
from athena.api.v1.services.pipelines_service import PipelinesService

if TYPE_CHECKING:
    from athena.api.v1.dtos import PaginationParams, SchedulerHistoryFilterParams, SortParams
    from athena.api.v1.providers import SchedulerHistoryProvider
    from athena.orchestration.schedule_models import PipelineScheduleRun


class SchedulerService:
    """Orchestrates scheduler runs history queries and DTO mapping."""

    def __init__(
        self, provider: SchedulerHistoryProvider, pipelines_service: PipelinesService
    ) -> None:
        self._provider = provider
        self._pipelines_service = pipelines_service

    def list_history(
        self,
        filters: SchedulerHistoryFilterParams,
        sort: SortParams,
        pagination: PaginationParams,
    ) -> CollectionResult[PipelineScheduleRunDTO]:
        """Lists scheduler execution entries using specifications."""
        spec = QuerySpecification(filters=filters, sort=sort, pagination=pagination)
        result = self._provider.get_history(spec)

        dto_items = tuple(self._map_to_dto(r) for r in result.items)
        return CollectionResult(
            items=dto_items,
            total_count=result.total_count,
            page=result.page,
            page_size=result.page_size,
        )

    def get_run(self, schedule_run_id: str) -> PipelineScheduleRunDTO:
        """Retrieves a single scheduled execution run envelope or raises SchedulerRunNotFoundError."""
        r = self._provider.get_run(schedule_run_id)
        if not r:
            raise SchedulerRunNotFoundError(
                f"Scheduler run '{schedule_run_id}' not found"
            )
        return self._map_to_dto(r)

    def _map_to_dto(self, r: PipelineScheduleRun) -> PipelineScheduleRunDTO:
        # Re-use pipelines_service to map SystemPipelineResult domain model to DTO
        system_dto = self._pipelines_service._map_to_system_dto(r.system_result)

        return PipelineScheduleRunDTO(
            schedule_run_id=r.schedule_run_id,
            job=ResourceReference(id=r.job_id, resource_type="job"),
            definition_id=r.definition_id,
            system_result=system_dto,
            duration_seconds=r.duration_seconds,
        )
