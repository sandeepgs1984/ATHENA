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
        """MI-3: the day's owner_validation coverage as a typed 5-stage funnel.

        Reads already-persisted run context only — no new scan, no mutation.
        Filtered = max(0, eligible − watch − trade).

        A scoped validate writes a run whose ``universe_members`` holds only the
        symbols it was asked about, so reading the newest run alone collapsed the
        funnel to "Universe 1" and hid every symbol validated earlier the same
        day. Stages count distinct symbols across that day's completed runs,
        each keeping the verdict of the newest run that covered it — never the
        sum of per-run counts, which would count re-validations twice.
        """
        spec = QuerySpecification(
            filters=PipelineRunFilterParams(),
            sort=SortParams(sort_by="as_of", sort_dir="desc"),
            pagination=PaginationParams(page=1, page_size=50),
        )
        runs = [
            run
            for run in self._provider.get_runs(spec).items
            if not self._is_incomplete(run)
        ]
        runs.sort(key=lambda r: r.as_of, reverse=True)

        leading = next(
            (run for run in runs if self._extract_members(run)),
            None,
        )
        if leading is None:
            # Older runs recorded counts without per-symbol members: report the
            # newest such run's own breakdown rather than nothing at all.
            for run in runs:
                summary = self._extract_validation_summary(run)
                if summary is not None:
                    return self._funnel_from_summary(
                        summary, run_id=run.run_id, as_of=run.as_of
                    )
            return self._empty_funnel()

        day = leading.as_of.date()
        verdicts: dict[str, bool] = {}
        decisions: dict[str, str] = {}
        for run in runs:
            if run.as_of.date() != day:
                continue
            members = self._extract_members(run)
            if not members:
                continue
            qualified = self._extract_qualified(run)
            for symbol, included in members.items():
                if symbol in verdicts:
                    continue
                verdicts[symbol] = included
                # A symbol's decision is read from the same run that judged it:
                # a name later re-validated without qualifying must not keep the
                # WATCH/TRADE it earned in an earlier run.
                decision = qualified.get(symbol)
                if decision is not None:
                    decisions[symbol] = decision

        universe = len(verdicts)
        eligible = sum(1 for included in verdicts.values() if included)
        watch = sum(1 for decision in decisions.values() if decision == "WATCH")
        trade = sum(1 for decision in decisions.values() if decision == "TRADE")
        if not decisions:
            # Older runs recorded decision counts without a qualified list.
            watch, trade = self._qualified_counts(leading)
        return self._funnel(
            {
                "universe": universe,
                "eligible": eligible,
                "filtered": max(0, eligible - watch - trade),
                "watch": watch,
                "trade": trade,
            },
            run_id=leading.run_id,
            as_of=leading.as_of,
        )

    @staticmethod
    def _is_incomplete(run: SystemPipelineResult) -> bool:
        status = (
            run.overall_status.value
            if hasattr(run.overall_status, "value")
            else str(run.overall_status)
        )
        return str(status).upper() in {"FAILED", "RUNNING"}

    def _empty_funnel(self) -> ValidationFunnelDTO:
        stages = [
            ValidationFunnelStageDTO(id=sid, label=label, count=0, pct_of_universe=None)
            for sid, label in _FUNNEL_STAGES
        ]
        return ValidationFunnelDTO(stages=stages, available=False)

    def _contexts(self, run: SystemPipelineResult) -> list[Mapping[str, object]]:
        # Prefer system final_context, then each pipeline run's context —
        # mirrors the Market Intelligence tab's existing extractData() path.
        contexts: list[Mapping[str, object]] = []
        if run.final_context is not None:
            contexts.append(run.final_context.data)
        for pr in run.pipeline_runs:
            contexts.append(pr.final_context.data)
        return [data for data in contexts if data]

    def _extract_validation_summary(
        self, run: SystemPipelineResult
    ) -> dict[str, Any] | None:
        for data in self._contexts(run):
            raw = data.get("validation_summary")
            if isinstance(raw, dict):
                return dict(raw)
        return None

    def _extract_members(self, run: SystemPipelineResult) -> dict[str, bool]:
        """One run's per-symbol eligibility verdicts, keyed by display symbol."""
        for data in self._contexts(run):
            raw = data.get("universe_members")
            if not isinstance(raw, dict) or not raw:
                continue
            out: dict[str, bool] = {}
            for key, member in raw.items():
                if not isinstance(member, dict):
                    continue
                symbol = str(member.get("symbol") or key).upper()
                out[symbol] = bool(member.get("included"))
            if out:
                return out
        return {}

    def _extract_qualified(self, run: SystemPipelineResult) -> dict[str, str]:
        """One run's WATCH/TRADE decisions, keyed by display symbol."""
        for data in self._contexts(run):
            rows = data.get("qualified_today")
            if not isinstance(rows, list) or not rows:
                continue
            out: dict[str, str] = {}
            for row in rows:
                if not isinstance(row, dict):
                    continue
                symbol = str(row.get("symbol") or "").upper()
                decision = str(row.get("decision_type") or "").upper()
                if symbol and decision in {"WATCH", "TRADE"}:
                    out[symbol] = decision
            if out:
                return out
        return {}

    def _qualified_counts(self, run: SystemPipelineResult) -> tuple[int, int]:
        """WATCH/TRADE counts from the run's own qualified list, else its counts."""
        qualified = self._extract_qualified(run)
        if qualified:
            return (
                sum(1 for d in qualified.values() if d == "WATCH"),
                sum(1 for d in qualified.values() if d == "TRADE"),
            )
        summary = self._extract_validation_summary(run) or {}
        counts_raw = summary.get("decision_counts")
        counts: dict[str, Any] = counts_raw if isinstance(counts_raw, dict) else {}
        return _as_nonneg_int(counts.get("WATCH")), _as_nonneg_int(counts.get("TRADE"))

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
        return self._funnel(
            {
                "universe": universe,
                "eligible": eligible,
                "filtered": max(0, eligible - watch - trade),
                "watch": watch,
                "trade": trade,
            },
            run_id=run_id,
            as_of=as_of,
        )

    def _funnel(
        self,
        values: Mapping[str, int],
        *,
        run_id: str,
        as_of: datetime,
    ) -> ValidationFunnelDTO:
        universe = values["universe"]
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

