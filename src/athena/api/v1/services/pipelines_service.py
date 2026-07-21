"""Pipeline runs business service (P8.3)."""

from __future__ import annotations

from typing import TYPE_CHECKING

from athena.api.exceptions import PipelineRunNotFoundError
from athena.api.v1.dtos import (
    CollectionResult,
    PipelineContextDTO,
    PipelineMetadataDTO,
    PipelineResultDTO,
    QuerySpecification,
    ResourceReference,
    StageResultDTO,
    SystemPipelineResultDTO,
)

if TYPE_CHECKING:
    from athena.api.v1.dtos import PaginationParams, PipelineRunFilterParams, SortParams
    from athena.api.v1.providers import PipelineRunProvider
    from athena.orchestration.models import (
        PipelineContext,
        PipelineMetadata,
        PipelineResult,
        StageResult,
        SystemPipelineResult,
    )


class PipelinesService:
    """Orchestrates system pipeline run queries and DTO mapping."""

    def __init__(self, provider: PipelineRunProvider) -> None:
        self._provider = provider

    def list_runs(
        self,
        filters: PipelineRunFilterParams,
        sort: SortParams,
        pagination: PaginationParams,
    ) -> CollectionResult[SystemPipelineResultDTO]:
        """Lists pipeline executions using query specifications."""
        spec = QuerySpecification(filters=filters, sort=sort, pagination=pagination)
        result = self._provider.get_runs(spec)

        dto_items = tuple(self._map_to_system_dto(r) for r in result.items)
        return CollectionResult(
            items=dto_items,
            total_count=result.total_count,
            page=result.page,
            page_size=result.page_size,
        )

    def get_run(self, run_id: str) -> SystemPipelineResultDTO:
        """Retrieves single pipeline execution run detail or raises PipelineRunNotFoundError."""
        r = self._provider.get_run(run_id)
        if not r:
            raise PipelineRunNotFoundError(f"Pipeline run '{run_id}' not found")
        return self._map_to_system_dto(r)

    def _map_to_system_dto(self, r: SystemPipelineResult) -> SystemPipelineResultDTO:
        runs_dtos = [self._map_to_pipeline_dto(pr) for pr in r.pipeline_runs]

        snapshot_ref = None
        if r.workspace_snapshot:
            snapshot_ref = ResourceReference(
                id=r.workspace_snapshot.snapshot_id, resource_type="workspace"
            )

        status_str = (
            r.overall_status.value
            if hasattr(r.overall_status, "value")
            else str(r.overall_status)
        )

        return SystemPipelineResultDTO(
            run_id=r.run_id,
            as_of=r.as_of,
            pipeline_runs=runs_dtos,
            workspace_snapshot=snapshot_ref,
            overall_status=status_str,
            final_context=self._map_context_dto(r.final_context),
        )

    def _map_to_pipeline_dto(self, pr: PipelineResult) -> PipelineResultDTO:
        stage_dtos = [self._map_stage_dto(s) for s in pr.stages]
        status_str = (
            pr.overall_status.value
            if hasattr(pr.overall_status, "value")
            else str(pr.overall_status)
        )

        return PipelineResultDTO(
            pipeline_run_id=pr.pipeline_run_id,
            metadata=self._map_metadata_dto(pr.metadata),
            as_of=pr.as_of,
            stages=stage_dtos,
            overall_status=status_str,
            final_context=self._map_context_dto(pr.final_context),
        )

    def _map_metadata_dto(self, meta: PipelineMetadata) -> PipelineMetadataDTO:
        return PipelineMetadataDTO(
            definition_id=meta.definition_id,
            version=meta.version,
            name=meta.name,
            description=meta.description,
            metadata=dict(meta.metadata) if meta.metadata else {},
        )

    def _map_context_dto(self, ctx: PipelineContext) -> PipelineContextDTO:
        return PipelineContextDTO(
            run_id=ctx.run_id,
            as_of=ctx.as_of,
            data=dict(ctx.data) if ctx.data else {},
        )

    def _map_stage_dto(self, s: StageResult) -> StageResultDTO:
        status_str = s.status.value if hasattr(s.status, "value") else str(s.status)
        return StageResultDTO(
            stage_id=s.stage_id,
            status=status_str,
            message=s.message,
            output_key=s.output_key,
        )
