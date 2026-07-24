"""Decisions business service (P8.3)."""

from __future__ import annotations

from collections.abc import Mapping
from typing import TYPE_CHECKING, Any

from athena.api.exceptions import DecisionNotFoundError
from athena.api.v1.dtos import (
    AnalysisBlockDTO,
    AnalysisContributionDTO,
    AnalysisDimensionDTO,
    CollectionResult,
    DecisionAnalysisDTO,
    DecisionDepthDTO,
    DecisionDTO,
    DecisionMetadataDTO,
    DecisionTraceDTO,
    EligibilityDetailDTO,
    EligibilityRuleDTO,
    GateResultDTO,
    QuerySpecification,
    ResourceReference,
    TraceStageDTO,
    TradePlanDTO,
)

if TYPE_CHECKING:
    from athena.api.v1.dtos import DecisionFilterParams, PaginationParams, SortParams
    from athena.api.v1.providers import DecisionProvider
    from athena.domain.decision import Decision, TraceStage


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

    def get_decision_depth(self, decision_id: str) -> DecisionDepthDTO:
        """Return persisted eligibility and analytical report data only."""
        decision = self._provider.get_decision(decision_id)
        if decision is None:
            raise DecisionNotFoundError(f"Decision '{decision_id}' not found")

        detail = self._provider.get_run_detail(decision.run_id)
        pipeline = detail.get("pipeline", detail)
        if not isinstance(pipeline, Mapping):
            pipeline = {}

        eligibility = self._map_eligibility(
            pipeline.get("universe_members"),
            decision.instrument_id,
        )
        reports = pipeline.get("decision_reports")
        report: Mapping[str, Any] = {}
        if isinstance(reports, Mapping):
            candidate = reports.get(decision.decision_id)
            if isinstance(candidate, Mapping):
                report = candidate

        return DecisionDepthDTO(
            decision_id=decision.decision_id,
            instrument_id=decision.instrument_id,
            eligibility=eligibility,
            score=self._map_analysis_block(report.get("score"), kind="score"),
            confidence=self._map_analysis_block(
                report.get("confidence"), kind="confidence"
            ),
            risk=self._map_analysis_block(report.get("risk"), kind="risk"),
        )

    @staticmethod
    def _map_eligibility(
        raw_members: object,
        instrument_id: str | None,
    ) -> EligibilityDetailDTO:
        member: Mapping[str, Any] | None = None
        if isinstance(raw_members, Mapping):
            bare = (instrument_id or "").split(":", 1)[-1]
            for key in (instrument_id, bare):
                candidate = raw_members.get(key)
                if isinstance(candidate, Mapping):
                    member = candidate
                    break
            if member is None:
                for candidate in raw_members.values():
                    if (
                        isinstance(candidate, Mapping)
                        and candidate.get("instrument_id") == instrument_id
                    ):
                        member = candidate
                        break

        if member is None:
            return EligibilityDetailDTO(
                status="UNKNOWN",
                summary="No persisted eligibility assessment is available for this run.",
            )

        included = bool(member.get("included"))
        rules: list[EligibilityRuleDTO] = []
        evidence = member.get("evidence")
        if isinstance(evidence, list):
            for item in evidence:
                if not isinstance(item, Mapping):
                    continue
                inputs = item.get("inputs")
                rules.append(
                    EligibilityRuleDTO(
                        rule=str(item.get("rule") or "unknown"),
                        passed=bool(item.get("passed")),
                        explanation=str(item.get("explanation") or "No explanation recorded."),
                        inputs=(
                            {str(k): str(v) for k, v in inputs.items()}
                            if isinstance(inputs, Mapping)
                            else {}
                        ),
                    )
                )
        exclusions = member.get("exclusion_reasons")
        return EligibilityDetailDTO(
            status="INCLUDED" if included else "EXCLUDED",
            summary=str(
                member.get("eligibility_summary")
                or ("Included in universe." if included else "Excluded from universe.")
            ),
            exclusion_reasons=(
                [str(reason) for reason in exclusions]
                if isinstance(exclusions, list)
                else []
            ),
            rules=rules,
        )

    @staticmethod
    def _map_analysis_block(raw: object, *, kind: str) -> AnalysisBlockDTO:
        if not isinstance(raw, Mapping):
            return AnalysisBlockDTO(
                status="UNKNOWN",
                explanation=f"No persisted {kind} artifact is available for this decision.",
            )

        raw_dimensions = raw.get("components" if kind == "score" else "dimensions")
        dimensions: list[AnalysisDimensionDTO] = []
        if isinstance(raw_dimensions, list):
            for item in raw_dimensions:
                if not isinstance(item, Mapping):
                    continue
                contributions: list[AnalysisContributionDTO] = []
                raw_contributions = item.get("contributions")
                if isinstance(raw_contributions, list):
                    for contribution in raw_contributions:
                        if not isinstance(contribution, Mapping):
                            continue
                        contributions.append(
                            AnalysisContributionDTO(
                                source=str(contribution.get("source") or "unknown"),
                                reference=str(
                                    contribution.get("reference")
                                    or contribution.get("reference_id")
                                    or ""
                                ),
                                description=str(
                                    contribution.get("description")
                                    or "No description recorded."
                                ),
                                points=contribution.get("points"),
                            )
                        )
                dimensions.append(
                    AnalysisDimensionDTO(
                        name=str(
                            item.get("dimension")
                            or item.get("name")
                            or "unknown"
                        ),
                        status=str(item.get("status") or "UNKNOWN"),
                        value=item.get("value"),
                        level=(
                            str(item["level"])
                            if item.get("level") not in (None, "UNKNOWN")
                            else None
                        ),
                        weight=item.get("weight"),
                        weighted=item.get("weighted"),
                        explanation=str(item.get("explanation") or ""),
                        contributions=contributions,
                    )
                )

        value_key = "composite" if kind == "score" else "overall"
        level = raw.get("level")
        return AnalysisBlockDTO(
            status=str(raw.get("status") or "UNKNOWN"),
            value=raw.get(value_key),
            level=str(level) if level not in (None, "UNKNOWN") else None,
            completeness=raw.get("completeness"),
            explanation=str(
                raw.get("explanation")
                or (
                    f"No persisted {kind} explanation is available."
                    if str(raw.get("status") or "UNKNOWN") == "UNKNOWN"
                    else ""
                )
            ),
            dimensions=dimensions,
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
