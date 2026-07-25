"""Decisions business service (P8.3)."""

from __future__ import annotations

from collections.abc import Mapping
from datetime import datetime, timezone
from decimal import Decimal
from pathlib import Path
from typing import TYPE_CHECKING, Any
from zoneinfo import ZoneInfo

from athena.api.exceptions import DecisionNotFoundError
from athena.api.v1.dtos import (
    AnalysisBlockDTO,
    AnalysisContributionDTO,
    AnalysisDimensionDTO,
    CalendarContextDTO,
    CalendarEventDTO,
    CollectionResult,
    ContextEvidenceDTO,
    DecisionAnalogDTO,
    DecisionAnalogsDTO,
    DecisionAnalysisDTO,
    DecisionContextDTO,
    DecisionDepthDTO,
    DecisionDTO,
    DecisionMetadataDTO,
    DecisionTraceDTO,
    EligibilityDetailDTO,
    EligibilityRuleDTO,
    ExternalLinkDTO,
    GateResultDTO,
    JournalEntryDTO,
    MarketHealthContextDTO,
    QuerySpecification,
    RegimeContextDTO,
    ResourceReference,
    TraceStageDTO,
    TradeOutcomeDTO,
    TradePlanDTO,
)
from athena.calendar.engine import CalendarEngine
from athena.config.loader import load_config, load_external_links_file
from athena.data.store.serialization import trade_outcome_id
from athena.domain.decision import DecisionJournalEntry, TradeOutcome
from athena.domain.enums import Direction, UserAction

if TYPE_CHECKING:
    from athena.api.v1.dtos import (
        DecisionFilterParams,
        PaginationParams,
        RecordOutcomeRequest,
        SortParams,
    )
    from athena.api.v1.providers import DecisionProvider
    from athena.domain.decision import Decision, TraceStage


class DecisionsService:
    """Orchestrates decision retrieval and DTO mapping."""

    def __init__(
        self,
        provider: DecisionProvider,
        *,
        config_dir: Path | None = None,
    ) -> None:
        self._provider = provider
        self._config_dir = Path(config_dir) if config_dir else Path("config")

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
        report = self._fetch_report(decision, pipeline=pipeline)

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

    def get_decision_context(self, decision_id: str) -> DecisionContextDTO:
        """Session/calendar (live), persisted regime/market-health, and curated
        external links for a decision. No news ingestion, no generated rationale."""
        decision = self._provider.get_decision(decision_id)
        if decision is None:
            raise DecisionNotFoundError(f"Decision '{decision_id}' not found")

        cfg = load_config(self._config_dir)
        tz = ZoneInfo(cfg.market.timezone)
        calendar = CalendarEngine.from_config_dir(self._config_dir, cfg.market)
        calendar_ctx = calendar.context_for(decision.ts.astimezone(tz).date())

        report = self._fetch_report(decision)

        links_file = load_external_links_file(self._config_dir)
        bare = (decision.instrument_id or "").split(":", 1)[-1]
        links = [
            ExternalLinkDTO(
                title=item.title,
                url=item.url,
                source=item.source,
                added_by=item.added_by,
                date_added=item.date_added,
            )
            for item in links_file.links
            if item.instrument_id in ("GLOBAL", decision.instrument_id, bare)
        ]

        return DecisionContextDTO(
            decision_id=decision.decision_id,
            instrument_id=decision.instrument_id,
            calendar=self._map_calendar(calendar_ctx),
            regime=self._map_regime(report.get("regime")),
            market_health=self._map_market_health(report.get("market_health")),
            external_links=links,
        )

    def record_journal_entry(
        self, decision_id: str, user_action: str, notes: str
    ) -> JournalEntryDTO:
        """Persist the owner's response to a decision (M-X0, R-9)."""
        decision = self._provider.get_decision(decision_id)
        if decision is None:
            raise DecisionNotFoundError(f"Decision '{decision_id}' not found")

        entry = DecisionJournalEntry(
            decision_ref=decision_id,
            user_action=UserAction(user_action),
            action_ts=datetime.now(tz=timezone.utc),
            notes=notes,
        )
        self._provider.save_journal_entry(entry)
        return self._map_journal_entry(entry)

    def get_journal_entry(self, decision_id: str) -> JournalEntryDTO | None:
        """Most recent owner response for a decision, or None if never recorded."""
        entry = self._provider.get_journal_entry(decision_id)
        return self._map_journal_entry(entry) if entry is not None else None

    def record_trade_outcome(
        self, decision_id: str, req: RecordOutcomeRequest
    ) -> TradeOutcomeDTO:
        """Persist a realized outcome. PnL, holding time, and TradePlan adherence
        are computed here — deterministic and explainable, never client-supplied."""
        decision = self._provider.get_decision(decision_id)
        if decision is None:
            raise DecisionNotFoundError(f"Decision '{decision_id}' not found")

        closed_ts = req.closed_ts or datetime.now(tz=timezone.utc)
        pnl = self._compute_pnl(decision.direction, req.entry_price, req.exit_price, req.quantity)
        holding_seconds = max(0, int((closed_ts - decision.ts).total_seconds()))
        adherence = self._compute_adherence(
            decision.trade_plan, decision.direction, req.entry_price, req.exit_price
        )

        outcome = TradeOutcome(
            outcome_id=trade_outcome_id(decision_id, closed_ts),
            decision_ref=decision_id,
            entry_price=req.entry_price,
            exit_price=req.exit_price,
            quantity=req.quantity,
            pnl=pnl,
            holding_seconds=holding_seconds,
            adherence=adherence,
            closed_ts=closed_ts,
        )
        self._provider.save_trade_outcome(outcome)
        return self._map_trade_outcome(outcome)

    def get_trade_outcome(self, decision_id: str) -> TradeOutcomeDTO | None:
        """Most recent realized outcome for a decision, or None if never logged."""
        outcome = self._provider.get_trade_outcome(decision_id)
        return self._map_trade_outcome(outcome) if outcome is not None else None

    def get_decision_analogs(self, decision_id: str, *, limit: int = 5) -> DecisionAnalogsDTO:
        """Nearest-neighbor historical decisions by score/confidence/risk
        fingerprint, each with its logged human response and realized outcome
        if any (M-X1). Deterministic retrieval over persisted history — no
        generated text, no recomputation of any comparison."""
        target = self._provider.get_decision(decision_id)
        if target is None:
            raise DecisionNotFoundError(f"Decision '{decision_id}' not found")

        target_fp = self._fingerprint(self._fetch_report(target))
        if target_fp is None:
            return DecisionAnalogsDTO(decision_id=decision_id, analogs=[], compared_count=0)

        pool = self._provider.list_recent_decisions(limit=500)
        reports_by_run: dict[str, Mapping[str, Any]] = {}
        scored: list[tuple[Decimal, Decision, tuple[Decimal, Decimal, Decimal]]] = []
        for candidate in pool:
            if candidate.decision_id == decision_id:
                continue
            if candidate.run_id not in reports_by_run:
                detail = self._provider.get_run_detail(candidate.run_id)
                pipeline = detail.get("pipeline", detail)
                reports_by_run[candidate.run_id] = pipeline if isinstance(pipeline, Mapping) else {}
            report = self._fetch_report(candidate, pipeline=reports_by_run[candidate.run_id])
            fp = self._fingerprint(report)
            if fp is None:
                continue
            distance = (
                (fp[0] - target_fp[0]) ** 2
                + (fp[1] - target_fp[1]) ** 2
                + (fp[2] - target_fp[2]) ** 2
            ).sqrt()
            scored.append((distance, candidate, fp))

        scored.sort(key=lambda item: (item[0], item[1].ts), reverse=False)
        top = scored[:limit]

        analogs = []
        for distance, candidate, fp in top:
            journal = self._provider.get_journal_entry(candidate.decision_id)
            outcome = self._provider.get_trade_outcome(candidate.decision_id)
            analogs.append(
                DecisionAnalogDTO(
                    decision_id=candidate.decision_id,
                    instrument_id=candidate.instrument_id,
                    ts=candidate.ts,
                    decision_type=candidate.decision_type.value,
                    direction=candidate.direction.value,
                    score=fp[0],
                    confidence=fp[1],
                    risk=fp[2],
                    distance=distance,
                    user_action=journal.user_action.value if journal else None,
                    outcome_pnl=outcome.pnl if outcome else None,
                    outcome_closed_ts=outcome.closed_ts if outcome else None,
                )
            )

        return DecisionAnalogsDTO(
            decision_id=decision_id, analogs=analogs, compared_count=len(scored)
        )

    def _fetch_report(self, decision: Decision, *, pipeline: Mapping[str, Any] | None = None) -> Mapping[str, Any]:
        if pipeline is None:
            detail = self._provider.get_run_detail(decision.run_id)
            pipeline = detail.get("pipeline", detail)
            if not isinstance(pipeline, Mapping):
                pipeline = {}
        reports = pipeline.get("decision_reports")
        if not isinstance(reports, Mapping):
            return {}
        candidate = reports.get(decision.decision_id)
        return candidate if isinstance(candidate, Mapping) else {}

    @staticmethod
    def _fingerprint(report: Mapping[str, Any]) -> tuple[Decimal, Decimal, Decimal] | None:
        score = report.get("score")
        confidence = report.get("confidence")
        risk = report.get("risk")
        if not (
            isinstance(score, Mapping)
            and isinstance(confidence, Mapping)
            and isinstance(risk, Mapping)
        ):
            return None
        if score.get("status") != "OK" or confidence.get("status") != "OK" or risk.get("status") != "OK":
            return None
        try:
            return (
                Decimal(str(score.get("composite"))),
                Decimal(str(confidence.get("overall"))),
                Decimal(str(risk.get("overall"))),
            )
        except (TypeError, ArithmeticError, ValueError):
            return None

    @staticmethod
    def _compute_pnl(direction, entry_price, exit_price, quantity):
        if direction is Direction.SHORT:
            return (entry_price - exit_price) * quantity
        return (exit_price - entry_price) * quantity

    @staticmethod
    def _compute_adherence(trade_plan, direction, entry_price, exit_price) -> dict[str, bool]:
        if trade_plan is None:
            return {}
        entered_within_zone = trade_plan.entry_low <= entry_price <= trade_plan.entry_high
        if direction is Direction.SHORT:
            hit_stop = exit_price >= trade_plan.stop_loss
            hit_target = any(exit_price <= t for t in trade_plan.targets)
        else:
            hit_stop = exit_price <= trade_plan.stop_loss
            hit_target = any(exit_price >= t for t in trade_plan.targets)
        return {
            "entered_within_zone": entered_within_zone,
            "hit_stop": hit_stop,
            "hit_target": hit_target,
        }

    @staticmethod
    def _map_journal_entry(entry: DecisionJournalEntry) -> JournalEntryDTO:
        return JournalEntryDTO(
            decision_id=entry.decision_ref,
            user_action=entry.user_action.value,
            action_ts=entry.action_ts,
            notes=entry.notes,
        )

    @staticmethod
    def _map_trade_outcome(outcome: TradeOutcome) -> TradeOutcomeDTO:
        return TradeOutcomeDTO(
            decision_id=outcome.decision_ref,
            entry_price=outcome.entry_price,
            exit_price=outcome.exit_price,
            quantity=outcome.quantity,
            pnl=outcome.pnl,
            holding_seconds=outcome.holding_seconds,
            adherence=dict(outcome.adherence),
            closed_ts=outcome.closed_ts,
        )

    @staticmethod
    def _map_calendar(ctx) -> CalendarContextDTO:
        return CalendarContextDTO(
            context_date=ctx.context_date.isoformat(),
            session_type=ctx.session_type.value,
            exchange=ctx.exchange,
            timezone=ctx.timezone,
            open_time=ctx.open_time.isoformat() if ctx.open_time else None,
            close_time=ctx.close_time.isoformat() if ctx.close_time else None,
            holiday_name=ctx.holiday_name,
            is_weekly_expiry=ctx.is_weekly_expiry,
            is_monthly_expiry=ctx.is_monthly_expiry,
            events=[
                CalendarEventDTO(kind=e.kind, name=e.name) for e in ctx.events
            ],
        )

    @staticmethod
    def _map_context_evidence(raw: object) -> list[ContextEvidenceDTO]:
        if not isinstance(raw, list):
            return []
        return [
            ContextEvidenceDTO(
                dimension=str(item.get("dimension") or "unknown"),
                outcome=str(item.get("outcome") or "UNKNOWN"),
                explanation=str(item.get("explanation") or ""),
            )
            for item in raw
            if isinstance(item, Mapping)
        ]

    @classmethod
    def _map_regime(cls, raw: object) -> RegimeContextDTO:
        if not isinstance(raw, Mapping) or raw.get("status") != "ASSESSED":
            return RegimeContextDTO(status="UNKNOWN")
        labels = raw.get("labels")
        return RegimeContextDTO(
            status="ASSESSED",
            labels=[str(label) for label in labels] if isinstance(labels, list) else [],
            explanation=str(raw.get("explanation") or ""),
            evidence=cls._map_context_evidence(raw.get("evidence")),
        )

    @classmethod
    def _map_market_health(cls, raw: object) -> MarketHealthContextDTO:
        if not isinstance(raw, Mapping) or raw.get("status") != "ASSESSED":
            return MarketHealthContextDTO(status="UNKNOWN")
        dimensions = raw.get("dimensions")
        return MarketHealthContextDTO(
            status="ASSESSED",
            dimensions=(
                {str(k): str(v) for k, v in dimensions.items()}
                if isinstance(dimensions, Mapping)
                else {}
            ),
            explanation=str(raw.get("explanation") or ""),
            evidence=cls._map_context_evidence(raw.get("evidence")),
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
