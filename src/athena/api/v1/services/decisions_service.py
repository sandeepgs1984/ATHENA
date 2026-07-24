"""Decisions business service (P8.3)."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from athena.api.exceptions import DecisionNotFoundError
from athena.api.v1.dtos import (
    CollectionResult,
    DecisionAnalysisDTO,
    DecisionDTO,
    DecisionMetadataDTO,
    DecisionTraceDTO,
    GateResultDTO,
    QuerySpecification,
    ResourceReference,
    TraceStageDTO,
    TradePlanDTO,
)

if TYPE_CHECKING:
    from athena.api.v1.dtos import DecisionFilterParams, PaginationParams, SortParams
    from athena.api.v1.providers import DecisionProvider
    from athena.domain.decision import Decision, DecisionTrace, TraceStage


class DecisionsService:
    """Orchestrates decision retrieval and DTO mapping."""

    def __init__(self, provider: DecisionProvider) -> None:
        self._provider = provider

    def list_decisions(
        self,
        filters: DecisionFilterParams,
        sort: SortParams,
        pagination: PaginationParams,
    ) -> CollectionResult[DecisionDTO]:
        """Queries the provider with a QuerySpecification and maps results to DTOs."""
        spec = QuerySpecification(filters=filters, sort=sort, pagination=pagination)
        result = self._provider.get_decisions(spec)

        dto_items = tuple(self._map_to_dto(d) for d in result.items)
        return CollectionResult(
            items=dto_items,
            total_count=result.total_count,
            page=result.page,
            page_size=result.page_size,
        )

    def get_decision(self, decision_id: str) -> DecisionDTO:
        """Retrieves a single decision or raises DecisionNotFoundError."""
        d = self._provider.get_decision(decision_id)
        if not d:
            raise DecisionNotFoundError(f"Decision '{decision_id}' not found")
        return self._map_to_dto(d)

    def _map_to_dto(self, d: Decision) -> DecisionDTO:
        # Resolve enums safely to strings
        direction_str = (
            d.direction.value if hasattr(d.direction, "value") else str(d.direction)
        )
        dec_type_str = (
            d.decision_type.value
            if hasattr(d.decision_type, "value")
            else str(d.decision_type)
        )

        metadata = DecisionMetadataDTO(
            decision_id=d.decision_id,
            ts=d.ts,
            run_id=d.run_id,
            cycle_id=d.cycle_id,
            instrument_id=d.instrument_id,
            direction=direction_str,
            decision_type=dec_type_str,
        )

        # Map quality gate results
        gates = []
        if d.gate_results:
            for g in d.gate_results:
                gate_str = g.gate.value if hasattr(g.gate, "value") else str(g.gate)
                gates.append(
                    GateResultDTO(
                        gate=gate_str,
                        passed=g.passed,
                        detail=g.detail,
                    )
                )

        analysis = DecisionAnalysisDTO(
            score_ref=(
                ResourceReference(id=d.score_ref, resource_type="score")
                if d.score_ref
                else None
            ),
            confidence_ref=(
                ResourceReference(
                    id=d.confidence_ref, resource_type="confidence"
                )
                if d.confidence_ref
                else None
            ),
            risk_ref=(
                ResourceReference(id=d.risk_ref, resource_type="risk")
                if d.risk_ref
                else None
            ),
            gate_results=gates,
        )

        trade_plan = None
        if d.trade_plan:
            tp = d.trade_plan
            trade_plan = TradePlanDTO(
                entry_low=tp.entry_low,
                entry_high=tp.entry_high,
                stop_loss=tp.stop_loss,
                targets=list(tp.targets),
                position_size=tp.position_size,
                risk_amount=tp.risk_amount,
                risk_reward=tp.risk_reward,
                valid_from=tp.valid_from,
                valid_until=tp.valid_until,
            )

        return DecisionDTO(
            metadata=metadata,
            analysis=analysis,
            trade_plan=trade_plan,
            explanation=d.explanation,
        )

    def get_decision_trace(self, decision_id: str) -> DecisionTraceDTO:
        """Return stored DecisionTrace stages when present; never synthesize demo DAG."""
        d = self._provider.get_decision(decision_id)
        if not d:
            raise DecisionNotFoundError(f"Decision '{decision_id}' not found")

        trace = self._provider.get_trace(decision_id)
        stages = (
            [self._map_trace_stage(s) for s in trace.stages]
            if trace is not None
            else []
        )
        return DecisionTraceDTO(
            decision_id=d.decision_id,
            instrument_id=d.instrument_id or "UNKNOWN",
            stages=stages,
        )

    @staticmethod
    def _map_trace_stage(stage: TraceStage) -> TraceStageDTO:
        details: dict[str, Any] = {}
        if stage.ref_ids:
            details["ref_ids"] = list(stage.ref_ids)
        return TraceStageDTO(
            stage_id=stage.stage,
            name=stage.stage.replace("_", " ").title(),
            status="COMPLETED",
            summary=stage.summary,
            details=details,
        )
