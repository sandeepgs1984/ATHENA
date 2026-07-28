"""Pipeline runs business service (P8.3)."""

from __future__ import annotations

from collections.abc import Mapping
from datetime import datetime
from typing import TYPE_CHECKING, Any

from athena.api.exceptions import PipelineRunNotFoundError
from athena.api.v1.dtos import (
    CollectionResult,
    PaginationParams,
    PipelineContextDTO,
    PipelineMetadataDTO,
    PipelineResultDTO,
    PipelineRunFilterParams,
    QuerySpecification,
    ResourceReference,
    SortParams,
    StageResultDTO,
    SystemPipelineResultDTO,
    ValidationFunnelDTO,
    ValidationFunnelStageDTO,
)

if TYPE_CHECKING:
    from athena.api.v1.providers import PipelineRunProvider
    from athena.orchestration.models import (
        PipelineContext,
        PipelineMetadata,
        PipelineResult,
        StageResult,
        SystemPipelineResult,
    )

_FUNNEL_STAGES: tuple[tuple[str, str], ...] = (
    ("universe", "Universe"),
    ("eligible", "Eligible"),
    ("filtered", "Filtered"),
    ("watch", "Watch"),
    ("trade", "Trade"),
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

    def validation_funnel(self) -> ValidationFunnelDTO:
        """MI-3: expose the latest owner_validation count breakdown as a typed
        5-stage funnel. Reads already-persisted run context only — no new
        scan, no mutation. Filtered = max(0, eligible − watch − trade)."""
        empty = self._empty_funnel()
        spec = QuerySpecification(
            filters=PipelineRunFilterParams(),
            sort=SortParams(sort_by="as_of", sort_dir="desc"),
            pagination=PaginationParams(page=1, page_size=50),
        )
        result = self._provider.get_runs(spec)
        for run in result.items:
            status = (
                run.overall_status.value
                if hasattr(run.overall_status, "value")
                else str(run.overall_status)
            )
            if str(status).upper() in {"FAILED", "RUNNING"}:
                continue
            summary = self._extract_validation_summary(run)
            if summary is None:
                continue
            return self._funnel_from_summary(
                summary,
                run_id=run.run_id,
                as_of=run.as_of,
            )
        return empty

    def _empty_funnel(self) -> ValidationFunnelDTO:
        stages = [
            ValidationFunnelStageDTO(id=sid, label=label, count=0, pct_of_universe=None)
            for sid, label in _FUNNEL_STAGES
        ]
        return ValidationFunnelDTO(stages=stages, available=False)

    def _extract_validation_summary(
        self, run: SystemPipelineResult
    ) -> dict[str, Any] | None:
        contexts: list[Mapping[str, object]] = []
        # Prefer system final_context, then each pipeline run's context —
        # mirrors the Market Intelligence tab's existing extractData() path.
        if run.final_context is not None:
            contexts.append(run.final_context.data)
        for pr in run.pipeline_runs:
            contexts.append(pr.final_context.data)
        for data in contexts:
            if not data:
                continue
            raw = data.get("validation_summary")
            if isinstance(raw, dict):
                return dict(raw)
        return None

    def _funnel_from_summary(
        self,
        summary: dict[str, Any],
        *,
        run_id: str,
        as_of: datetime,
    ) -> ValidationFunnelDTO:
        universe = _as_nonneg_int(summary.get("candidates"))
        # Fall back to evaluated when candidates is missing on older runs.
        if universe == 0:
            evaluated = _as_nonneg_int(summary.get("evaluated"))
            if evaluated > 0:
                universe = evaluated
        eligible = _as_nonneg_int(summary.get("eligible"))
        counts_raw = summary.get("decision_counts")
        counts: dict[str, Any] = counts_raw if isinstance(counts_raw, dict) else {}
        watch = _as_nonneg_int(counts.get("WATCH"))
        trade = _as_nonneg_int(counts.get("TRADE"))
        filtered = max(0, eligible - watch - trade)
        values = {
            "universe": universe,
            "eligible": eligible,
            "filtered": filtered,
            "watch": watch,
            "trade": trade,
        }
        stages = [
            ValidationFunnelStageDTO(
                id=sid,
                label=label,
                count=values[sid],
                pct_of_universe=_pct_of_universe(values[sid], universe),
            )
            for sid, label in _FUNNEL_STAGES
        ]
        return ValidationFunnelDTO(
            run_id=run_id,
            as_of=as_of,
            stages=stages,
            available=True,
        )

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


def _as_nonneg_int(value: object) -> int:
    try:
        return max(0, int(value))  # type: ignore[arg-type]
    except (TypeError, ValueError):
        return 0


def _pct_of_universe(count: int, universe: int) -> float | None:
    if universe <= 0:
        return None
    return round((count / universe) * 100.0, 1)

