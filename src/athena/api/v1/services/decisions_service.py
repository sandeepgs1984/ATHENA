"""Decisions business service (P8.3)."""

from __future__ import annotations

from collections.abc import Mapping
from datetime import datetime, timezone
from decimal import Decimal
from pathlib import Path
from typing import TYPE_CHECKING, Any
from zoneinfo import ZoneInfo

from athena.api.exceptions import DecisionNotFoundError, DecisionsResetConfirmationError
from athena.api.v1.dtos import (
    AnalysisBlockDTO,
    AnalysisContributionDTO,
    AnalysisDimensionDTO,
    CalendarContextDTO,
    CalendarEventDTO,
    CollectionResult,
    ContextEvidenceDTO,
    CounterfactualGapDTO,
    DecisionAnalogDTO,
    DecisionAnalogsDTO,
    DecisionAnalysisDTO,
    DecisionContextDTO,
    DecisionCounterfactualDTO,
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
    ResetDecisionsResultDTO,
    ResourceReference,
    TraceStageDTO,
    TradeOutcomeDTO,
    TradePlanDTO,
    TradePlanFreshnessDTO,
)
from athena.api.v1.services.ops_service import default_backup_dir, default_db_path
from athena.calendar.engine import CalendarEngine
from athena.config.loader import load_config, load_decision_config, load_external_links_file
from athena.data.store.backup import create_backup, prune_backups
from athena.data.store.repository import SqliteRepository
from athena.data.store.serialization import trade_outcome_id
from athena.domain.decision import DecisionJournalEntry, TradeOutcome
from athena.domain.enums import Direction, QualityGate, UserAction

_RESET_CONFIRM_TOKEN = "CONFIRM"
_BACKUP_PREFIX = "athena-pre-decisions-reset-"

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
        db_path: Path | None = None,
        backup_dir: Path | None = None,
        repo: SqliteRepository | None = None,
    ) -> None:
        self._provider = provider
        self._config_dir = Path(config_dir) if config_dir else Path("config")
        self._db_path = Path(db_path) if db_path else default_db_path()
        self._backup_dir = Path(backup_dir) if backup_dir else default_backup_dir()
        # Optional persistent repo for read-only instrument lookups (real
        # company name — see _lookup_instrument_name) — mirrors the same
        # optional-repo-alongside-primary-abstraction precedent already used
        # by MarketHistoryService, avoiding a fresh sqlite connection per
        # decision the way reset_decisions' one-off backup step does.
        self._repo = repo
        # Populated per list_decisions() call so _lookup_instrument_name can
        # do one batched lookup instead of one repo query per decision row
        # (owner-reported, 2026-08-04: up to page_size extra serialized
        # round-trips per page was part of the Decisions & Trace slowness).
        self._instrument_name_cache: dict[str, str] | None = None

    def list_decisions(
        self,
        filters: DecisionFilterParams,
        sort: SortParams,
        pagination: PaginationParams,
    ) -> CollectionResult[DecisionDTO]:
        """Queries the provider with a QuerySpecification and maps results to DTOs."""
        spec = QuerySpecification(filters=filters, sort=sort, pagination=pagination)
        result = self._provider.get_decisions(spec)

        self._instrument_name_cache = self._load_instrument_names(result.items)
        try:
            dto_items = tuple(self._map_to_dto(d) for d in result.items)
        finally:
            self._instrument_name_cache = None
        return CollectionResult(
            items=dto_items,
            total_count=result.total_count,
            page=result.page,
            page_size=result.page_size,
        )

    def list_latest_decisions(self) -> tuple[DecisionDTO, ...]:
        """One current decision per instrument — what the Decisions & Trace
        dashboard actually displays after its own latest-per-instrument
        dedupe, so it can ask for exactly that instead of paginating through
        the full historical event log to reconstruct it client-side.

        Reads self._repo directly rather than through DecisionProvider, the
        same precedent already used by MarketHistoryService for this exact
        repository method — it's a live-repository convenience query, not
        part of the deterministic decision pipeline that needs to be
        replayable against an in-memory provider.
        """
        if self._repo is None:
            return ()
        decisions = tuple(self._repo.list_latest_decisions_by_instrument())
        self._instrument_name_cache = self._load_instrument_names(decisions)
        try:
            return tuple(self._map_to_dto(d) for d in decisions)
        finally:
            self._instrument_name_cache = None

    def _load_instrument_names(self, decisions: tuple[Decision, ...]) -> dict[str, str]:
        if self._repo is None:
            return {}
        wanted = {d.instrument_id for d in decisions if d.instrument_id}
        if not wanted:
            return {}
        return {
            instrument.instrument_id: instrument.name
            for instrument in self._repo.list_instruments()
            if instrument.instrument_id in wanted and instrument.name
        }

    def get_decision(self, decision_id: str) -> DecisionDTO:
        """Retrieves a single decision or raises DecisionNotFoundError."""
        d = self._provider.get_decision(decision_id)
        if not d:
            raise DecisionNotFoundError(f"Decision '{decision_id}' not found")
        return self._map_to_dto(d)

    def _lookup_instrument_name(self, instrument_id: str | None) -> str | None:
        """Real company name from the instruments table — None (never a
        fabricated value) if no repo is wired, the instrument isn't found,
        or the catalog hasn't been re-synced since the name column was
        added."""
        if not instrument_id:
            return None
        if self._instrument_name_cache is not None:
            return self._instrument_name_cache.get(instrument_id)
        if self._repo is None:
            return None
        instrument = self._repo.get_instrument(instrument_id)
        return instrument.name if instrument else None

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
            instrument_name=self._lookup_instrument_name(d.instrument_id),
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
            return_pct, holding_days = self._outcome_return_and_holding(outcome)
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
                    outcome_return_pct=return_pct,
                    outcome_holding_days=holding_days,
                )
            )

        win_rate_pct, avg_return_pct, avg_holding_days, min_holding_days, max_holding_days, sample_size = (
            self._aggregate_analog_outcomes(analogs)
        )

        return DecisionAnalogsDTO(
            decision_id=decision_id,
            analogs=analogs,
            compared_count=len(scored),
            win_rate_pct=win_rate_pct,
            avg_return_pct=avg_return_pct,
            avg_holding_days=avg_holding_days,
            min_holding_days=min_holding_days,
            max_holding_days=max_holding_days,
            outcomes_sample_size=sample_size,
        )

    def reset_decisions(self, *, confirmation: str) -> ResetDecisionsResultDTO:
        """Owner-triggered full wipe of the Decisions & Trace domain (decisions,
        traces, journal entries, realized outcomes) — CONFIRM-gated, with a
        best-effort automatic backup first, mirroring PortfolioService's
        reset_positions. Does not touch runs (shared with Market
        Intelligence's universe/regime history), portfolio positions, or
        owner candidates."""
        if confirmation != _RESET_CONFIRM_TOKEN:
            raise DecisionsResetConfirmationError(
                "Decisions reset refused: confirmation must be the exact token CONFIRM"
            )

        backup_path: str | None = None
        if self._db_path.is_file():
            try:
                self._backup_dir.mkdir(parents=True, exist_ok=True)
                stamp = datetime.now(tz=timezone.utc).strftime("%Y%m%dT%H%M%SZ")
                dest = self._backup_dir / f"{_BACKUP_PREFIX}{stamp}.db"
                with SqliteRepository(self._db_path) as repo:
                    result = create_backup(repo, dest, as_of=datetime.now(tz=timezone.utc))
                backup_path = result.destination
                # Owner direction (2026-08-03): these auto-backups exist only
                # as an undo window for this one reset action, not a history
                # — keep just the one just created, drop older ones with the
                # same prefix so this can never accumulate unbounded disk use.
                prune_backups(self._backup_dir, prefix=_BACKUP_PREFIX, keep_newest=1)
            except Exception:
                # Reset must still proceed; backup failure is non-fatal but loud via None path
                backup_path = None

        deleted_counts = self._provider.reset_decisions_data()
        return ResetDecisionsResultDTO(
            deleted_counts=deleted_counts,
            total_deleted=sum(deleted_counts.values()),
            backup_path=backup_path,
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

    def get_decision_counterfactual(self, decision_id: str) -> DecisionCounterfactualDTO:
        """Exact quantified distance from this decision to the TRADE gate —
        arithmetic over already-persisted values and current config
        thresholds only; never a recomputed score/confidence/risk (M-X2)."""
        decision = self._provider.get_decision(decision_id)
        if decision is None:
            raise DecisionNotFoundError(f"Decision '{decision_id}' not found")

        if decision.decision_type.value == "TRADE":
            return DecisionCounterfactualDTO(
                decision_id=decision_id,
                decision_type=decision.decision_type.value,
                is_trade=True,
                summary="Already a TRADE — every gate cleared.",
            )

        thresholds = load_decision_config(self._config_dir).thresholds
        report = self._fetch_report(decision)
        score_block = report.get("score") if isinstance(report.get("score"), Mapping) else {}
        confidence_block = (
            report.get("confidence") if isinstance(report.get("confidence"), Mapping) else {}
        )
        risk_block = report.get("risk") if isinstance(report.get("risk"), Mapping) else {}

        score_current = self._decimal_or_none(score_block.get("composite"))
        score_required = Decimal(thresholds.min_composite_for_trade)
        score_gap = (
            max(Decimal(0), score_required - score_current) if score_current is not None else None
        )
        confidence_current = self._decimal_or_none(confidence_block.get("overall"))
        risk_current = self._decimal_or_none(risk_block.get("overall"))
        completeness_current = self._decimal_or_none(score_block.get("completeness"))
        market_current = self._market_quality_value(score_block)

        gates: list[CounterfactualGapDTO] = []
        for g in decision.gate_results:
            if g.passed:
                continue
            if g.gate is QualityGate.CONFIDENCE:
                required = Decimal(thresholds.min_confidence_for_trade)
                gap = (
                    max(Decimal(0), required - confidence_current)
                    if confidence_current is not None else None
                )
                gates.append(CounterfactualGapDTO(
                    gate=g.gate.value, detail=g.detail,
                    current=confidence_current, required=required, gap=gap,
                ))
            elif g.gate is QualityGate.RISK:
                required = Decimal(thresholds.max_risk_for_trade)
                gap = (
                    max(Decimal(0), risk_current - required)
                    if risk_current is not None else None
                )
                gates.append(CounterfactualGapDTO(
                    gate=g.gate.value, detail=g.detail,
                    current=risk_current, required=required, gap=gap,
                ))
            elif g.gate is QualityGate.MARKET:
                required = Decimal(thresholds.market_floor)
                gap = (
                    max(Decimal(0), required - market_current)
                    if market_current is not None else None
                )
                gates.append(CounterfactualGapDTO(
                    gate=g.gate.value, detail=g.detail,
                    current=market_current, required=required, gap=gap,
                ))
            elif g.gate is QualityGate.EVIDENCE:
                required = Decimal(str(thresholds.min_evidence_completeness))
                gap = (
                    max(Decimal(0), required - completeness_current)
                    if completeness_current is not None else None
                )
                gates.append(CounterfactualGapDTO(
                    gate=g.gate.value, detail=g.detail,
                    current=completeness_current, required=required, gap=gap,
                ))
            else:
                gates.append(CounterfactualGapDTO(gate=g.gate.value, detail=g.detail))

        # A decision can clear score + every gate and still not be a TRADE:
        # direction/trade_plan are separately required and already persisted
        # on the decision itself — check them directly, never recomputed.
        if not gates and (score_gap is None or score_gap <= 0):
            if decision.direction is Direction.NONE:
                gates.append(CounterfactualGapDTO(
                    gate="DIRECTION",
                    detail="no clear trend direction from regime (required for a TRADE)",
                ))
            elif decision.trade_plan is None:
                gates.append(CounterfactualGapDTO(
                    gate="TRADE_PLAN",
                    detail="ATR/SMA indicators unavailable to build a trade plan",
                ))

        summary = self._counterfactual_summary(score_gap, gates)

        return DecisionCounterfactualDTO(
            decision_id=decision_id,
            decision_type=decision.decision_type.value,
            is_trade=False,
            score_current=score_current,
            score_required=score_required,
            score_gap=score_gap,
            gates=gates,
            summary=summary,
        )

    @staticmethod
    def _decimal_or_none(value: object) -> Decimal | None:
        if value is None:
            return None
        try:
            return Decimal(str(value))
        except (ArithmeticError, ValueError):
            return None

    @classmethod
    def _market_quality_value(cls, score_block: Mapping[str, Any]) -> Decimal | None:
        components = score_block.get("components")
        if not isinstance(components, list):
            return None
        for item in components:
            if isinstance(item, Mapping) and item.get("dimension") == "market_quality":
                return cls._decimal_or_none(item.get("value"))
        return None

    @staticmethod
    def _counterfactual_summary(
        score_gap: Decimal | None, gates: list[CounterfactualGapDTO]
    ) -> str:
        parts: list[str] = []
        if score_gap is not None and score_gap > 0:
            parts.append(f"score +{score_gap:.1f}")
        for gate in gates:
            if gate.gap is None or gate.gap <= 0:
                continue
            sign = "-" if gate.gate == "RISK" else "+"
            parts.append(f"{gate.gate.lower()} {sign}{gate.gap:.2f}")
        if parts:
            return "To become a TRADE: " + ", ".join(parts) + "."
        non_numeric = [g.gate for g in gates if g.gap is None]
        if non_numeric:
            return f"Blocked on: {', '.join(non_numeric)} — see gate detail."
        return "No persisted gap — decision has not yet been through a full scoring cycle."

    def get_trade_plan_freshness(
        self, decision_id: str, *, as_of: datetime | None = None
    ) -> TradePlanFreshnessDTO:
        """Deterministic decay clock for a decision's TradePlan validity window
        (M-X3). Pure arithmetic over the plan's already-persisted
        valid_from/valid_until and an as_of instant — never a recomputed
        plan, never a hidden clock read inside an analytical engine."""
        decision = self._provider.get_decision(decision_id)
        if decision is None:
            raise DecisionNotFoundError(f"Decision '{decision_id}' not found")

        as_of = as_of or datetime.now(tz=timezone.utc)
        plan = decision.trade_plan
        if plan is None:
            return TradePlanFreshnessDTO(
                decision_id=decision_id,
                has_trade_plan=False,
                as_of=as_of,
                status="NO_PLAN",
                summary="No trade plan was generated for this decision.",
            )

        cfg = load_decision_config(self._config_dir).plan
        total = (plan.valid_until - plan.valid_from).total_seconds()
        elapsed = max(0.0, min(total, (as_of - plan.valid_from).total_seconds()))
        remaining = total - elapsed
        decay_fraction = Decimal(str(elapsed / total)) if total > 0 else Decimal(1)

        if as_of >= plan.valid_until:
            status = "EXPIRED"
        elif decay_fraction >= Decimal(str(cfg.freshness_stale_fraction)):
            status = "STALE"
        elif decay_fraction >= Decimal(str(cfg.freshness_warn_fraction)):
            status = "AGING"
        else:
            status = "FRESH"

        return TradePlanFreshnessDTO(
            decision_id=decision_id,
            has_trade_plan=True,
            as_of=as_of,
            valid_from=plan.valid_from,
            valid_until=plan.valid_until,
            elapsed_seconds=int(elapsed),
            remaining_seconds=int(remaining),
            total_seconds=int(total),
            decay_fraction=decay_fraction,
            status=status,
            summary=self._freshness_summary(status, decay_fraction, remaining),
        )

    @staticmethod
    def _freshness_summary(status: str, decay_fraction: Decimal, remaining_seconds: float) -> str:
        pct = int((decay_fraction * 100).to_integral_value())
        if status == "EXPIRED":
            return f"{pct}% of the validity window has elapsed — this plan has EXPIRED."
        remaining_minutes = max(0, int(remaining_seconds // 60))
        return (
            f"{pct}% of the validity window elapsed — plan is {status}, "
            f"{remaining_minutes} min remaining."
        )

    @staticmethod
    def _compute_pnl(direction, entry_price, exit_price, quantity):
        if direction is Direction.SHORT:
            return (entry_price - exit_price) * quantity
        return (exit_price - entry_price) * quantity

    @staticmethod
    def _outcome_return_and_holding(
        outcome: TradeOutcome | None,
    ) -> tuple[Decimal | None, Decimal | None]:
        """Return % and holding period (days) for one realized outcome — exact
        arithmetic over the already-persisted pnl/entry/quantity/holding_seconds
        (UX-6 Historical Validation), never a new independent computation of
        pnl itself."""
        if outcome is None:
            return None, None
        cost_basis = outcome.entry_price * outcome.quantity
        return_pct = (outcome.pnl / cost_basis) * 100 if cost_basis != 0 else None
        holding_days = Decimal(outcome.holding_seconds) / Decimal(86400)
        return return_pct, holding_days

    @staticmethod
    def _aggregate_analog_outcomes(
        analogs: list[DecisionAnalogDTO],
    ) -> tuple[Decimal | None, Decimal | None, Decimal | None, Decimal | None, Decimal | None, int]:
        """Win-rate/avg-return/avg-holding (+ min/max holding) across whichever
        returned analogs have a realized outcome — exact arithmetic over
        persisted values, None (not a fabricated 0) when the sample is empty.
        min/max reuse the exact same per-analog outcome_holding_days values
        already collected for the average — a real historical range across
        past trades, not a forward-looking guarantee for the current one."""
        with_outcome = [a for a in analogs if a.outcome_pnl is not None]
        if not with_outcome:
            return None, None, None, None, None, 0
        wins = sum(1 for a in with_outcome if a.outcome_pnl > 0)
        win_rate_pct = (Decimal(wins) / Decimal(len(with_outcome))) * 100
        returns = [a.outcome_return_pct for a in with_outcome if a.outcome_return_pct is not None]
        avg_return_pct = sum(returns) / Decimal(len(returns)) if returns else None
        holdings = [a.outcome_holding_days for a in with_outcome if a.outcome_holding_days is not None]
        avg_holding_days = sum(holdings) / Decimal(len(holdings)) if holdings else None
        min_holding_days = min(holdings) if holdings else None
        max_holding_days = max(holdings) if holdings else None
        return (
            win_rate_pct,
            avg_return_pct,
            avg_holding_days,
            min_holding_days,
            max_holding_days,
            len(with_outcome),
        )

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
