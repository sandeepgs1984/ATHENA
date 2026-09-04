"""Row <-> canonical domain object conversion (M1.5).

The repository stores primitives and returns canonical domain objects — callers
never see database rows. Decimals are TEXT, timestamps are ISO-8601 (tz-aware),
JSON is serialized with sorted keys for deterministic, inspectable storage.
"""

from __future__ import annotations

import json
from collections.abc import Mapping, Sequence
from datetime import date, datetime
from decimal import Decimal
from typing import Any

from athena.data.validation.reports import (
    Severity,
    ValidationReport,
    ValidationResult,
    ValidationType,
)
from athena.domain.decision import (
    Decision,
    DecisionJournalEntry,
    DecisionTrace,
    GateResult,
    Position,
    TraceStage,
    TradeOutcome,
    TradePlan,
)
from athena.domain.enums import (
    DecisionType,
    Direction,
    QualityGate,
    RunStatus,
    RunTrigger,
    Timeframe,
    UserAction,
)
from athena.domain.market import (
    Candle,
    CorporateAction,
    InstitutionalFlowSession,
    Instrument,
    MarketSnapshot,
    Quote,
)
from athena.domain.run import RunRecord
from athena.intraday.entry_actionability_models import (
    EntryActionability,
    EntryActionabilityReasonCode,
    EntryActionabilityState,
    EntryLocationContext,
    EntryReference,
    EntryReferenceBasis,
    InvalidationBasis,
    OpeningRangeContextBasis,
    OpeningRangeContextReference,
    OperativeInvalidation,
    RewardBasis,
    RewardReference,
)
from athena.intraday.entry_qualification_models import (
    EntryEvidenceFinality,
    EntryQualification,
    EntryQualificationConfirmation,
    EntryQualificationEvidenceKind,
    EntryQualificationEvidenceRef,
    EntryQualificationReasonCode,
    EntryQualificationState,
)


def _opt_date(value: str | None) -> date | None:
    return date.fromisoformat(value) if value else None


# --------------------------------------------------------------------- instruments

def instrument_to_row(i: Instrument) -> tuple:
    return (
        i.instrument_id, i.isin, i.symbol, i.exchange, i.series, i.name, i.sector,
        i.lot_size, str(i.tick_size), i.status,
        i.listed_date.isoformat() if i.listed_date else None,
        i.delisted_date.isoformat() if i.delisted_date else None,
    )


def row_to_instrument(r: Sequence[Any]) -> Instrument:
    return Instrument(
        instrument_id=r[0], isin=r[1], symbol=r[2], exchange=r[3], series=r[4],
        name=r[5], sector=r[6], lot_size=int(r[7]), tick_size=Decimal(r[8]), status=r[9],
        listed_date=_opt_date(r[10]), delisted_date=_opt_date(r[11]),
    )


# ------------------------------------------------------------------------- candles

def candle_to_row(c: Candle) -> tuple:
    return (
        c.instrument_id, c.timeframe.value, c.ts_open.isoformat(),
        str(c.open), str(c.high), str(c.low), str(c.close),
        c.volume, c.source, 1 if c.adjusted else 0,
    )


def row_to_candle(r: Sequence[Any]) -> Candle:
    return Candle(
        instrument_id=r[0], timeframe=Timeframe(r[1]),
        ts_open=datetime.fromisoformat(r[2]),
        open=Decimal(r[3]), high=Decimal(r[4]), low=Decimal(r[5]), close=Decimal(r[6]),
        volume=int(r[7]), source=r[8], adjusted=bool(r[9]),
    )


# -------------------------------------------------------------------------- quotes

def quote_to_row(q: Quote) -> tuple:
    return (q.instrument_id, q.ts.isoformat(), str(q.last_price), q.volume, q.source)


def row_to_quote(r: Sequence[Any]) -> Quote:
    return Quote(instrument_id=r[0], ts=datetime.fromisoformat(r[1]),
                 last_price=Decimal(r[2]), volume=int(r[3]), source=r[4])


# ----------------------------------------------------------------------- snapshots

def snapshot_to_payload(s: MarketSnapshot) -> str:
    return json.dumps({
        "ts": s.ts.isoformat(),
        "indices": {k: str(v) for k, v in s.indices.items()},
        "breadth_advances": s.breadth_advances,
        "breadth_declines": s.breadth_declines,
        "breadth_neutral": s.breadth_neutral,
        "india_vix": str(s.india_vix) if s.india_vix is not None else None,
    }, sort_keys=True)


def payload_to_snapshot(payload: str) -> MarketSnapshot:
    data = json.loads(payload)
    return MarketSnapshot(
        ts=datetime.fromisoformat(data["ts"]),
        indices={k: Decimal(v) for k, v in data["indices"].items()},
        breadth_advances=int(data["breadth_advances"]),
        breadth_declines=int(data["breadth_declines"]),
        india_vix=Decimal(data["india_vix"]) if data["india_vix"] is not None else None,
        breadth_neutral=int(data.get("breadth_neutral", 0)),
    )


def institutional_flow_to_row(s: InstitutionalFlowSession) -> tuple:
    return (
        s.session_date.isoformat(),
        str(s.fii_buy), str(s.fii_sell), str(s.fii_net),
        str(s.dii_buy), str(s.dii_sell), str(s.dii_net),
        1 if s.provisional else 0,
        s.source_id,
        s.fetched_at.isoformat(),
        s.run_id or "",
    )


def row_to_institutional_flow(r: Sequence[Any]) -> InstitutionalFlowSession:
    return InstitutionalFlowSession(
        session_date=date.fromisoformat(r[0]),
        fii_buy=Decimal(r[1]), fii_sell=Decimal(r[2]), fii_net=Decimal(r[3]),
        dii_buy=Decimal(r[4]), dii_sell=Decimal(r[5]), dii_net=Decimal(r[6]),
        provisional=bool(int(r[7])),
        source_id=r[8],
        fetched_at=datetime.fromisoformat(r[9]),
        run_id=r[10] or "",
    )


# ---------------------------------------------------------------- corporate actions

def corporate_action_to_row(a: CorporateAction) -> tuple:
    return (
        a.action_id, a.instrument_id, a.action_type, a.ex_date.isoformat(),
        json.dumps({k: str(v) for k, v in a.details.items()}, sort_keys=True),
    )


def row_to_corporate_action(r: Sequence[Any]) -> CorporateAction:
    return CorporateAction(
        action_id=r[0], instrument_id=r[1], action_type=r[2],
        ex_date=date.fromisoformat(r[3]), details=json.loads(r[4]),
    )


# --------------------------------------------------------------------- validation

def _report_to_dict(r: ValidationReport) -> Mapping[str, Any]:
    return {
        "validation_type": r.validation_type.value,
        "result": r.result.value,
        "severity": r.severity.value,
        "explanation": r.explanation,
        "ts": r.ts.isoformat(),
        "evidence": list(r.evidence),
        "statistics": dict(r.statistics),
    }


def _dict_to_report(d: Mapping[str, Any]) -> ValidationReport:
    return ValidationReport(
        validation_type=ValidationType(d["validation_type"]),
        result=ValidationResult(d["result"]),
        severity=Severity(d["severity"]),
        explanation=d["explanation"],
        ts=datetime.fromisoformat(d["ts"]),
        evidence=tuple(d["evidence"]),
        statistics=d["statistics"],
    )


def reports_to_json(reports: Sequence[ValidationReport]) -> str:
    return json.dumps([_report_to_dict(r) for r in reports], sort_keys=True)


def json_to_reports(payload: str) -> tuple[ValidationReport, ...]:
    return tuple(_dict_to_report(d) for d in json.loads(payload))


# ---------------------------------------------------------------------------- runs

def run_to_row(run: RunRecord, detail_json: str) -> tuple:
    return (
        run.run_id,
        run.cycle_id,
        run.trigger.value,
        run.started_ts.isoformat(),
        run.finished_ts.isoformat() if run.finished_ts else None,
        run.status.value,
        run.software_version,
        run.blueprint_version,
        run.strategy_profile,
        run.strategy_profile_version,
        json.dumps(dict(run.indicator_versions), sort_keys=True),
        run.config_snapshot_id,
        run.input_digest,
        detail_json,
    )


def row_to_run(r: Sequence[Any]) -> RunRecord:
    finished = datetime.fromisoformat(r[4]) if r[4] else None
    return RunRecord(
        run_id=r[0],
        cycle_id=r[1],
        trigger=RunTrigger(r[2]),
        started_ts=datetime.fromisoformat(r[3]),
        status=RunStatus(r[5]),
        software_version=r[6],
        blueprint_version=r[7],
        strategy_profile=r[8],
        strategy_profile_version=r[9],
        indicator_versions=json.loads(r[10]),
        config_snapshot_id=r[11],
        input_digest=r[12] or "",
        finished_ts=finished,
    )


# ----------------------------------------------------------------------- decisions

def _trade_plan_to_json(plan: TradePlan | None) -> str | None:
    if plan is None:
        return None
    return json.dumps({
        "entry_low": str(plan.entry_low),
        "entry_high": str(plan.entry_high),
        "stop_loss": str(plan.stop_loss),
        "targets": [str(t) for t in plan.targets],
        "position_size": plan.position_size,
        "risk_amount": str(plan.risk_amount),
        "risk_reward": str(plan.risk_reward),
        "valid_from": plan.valid_from.isoformat(),
        "valid_until": plan.valid_until.isoformat(),
    }, sort_keys=True)


def _trade_plan_from_json(payload: str | None) -> TradePlan | None:
    if not payload:
        return None
    d = json.loads(payload)
    return TradePlan(
        entry_low=Decimal(d["entry_low"]),
        entry_high=Decimal(d["entry_high"]),
        stop_loss=Decimal(d["stop_loss"]),
        targets=tuple(Decimal(t) for t in d["targets"]),
        position_size=int(d["position_size"]),
        risk_amount=Decimal(d["risk_amount"]),
        risk_reward=Decimal(d["risk_reward"]),
        valid_from=datetime.fromisoformat(d["valid_from"]),
        valid_until=datetime.fromisoformat(d["valid_until"]),
    )


def _gates_to_json(gates: Sequence[GateResult]) -> str:
    return json.dumps([
        {"gate": g.gate.value, "passed": g.passed, "detail": g.detail}
        for g in gates
    ], sort_keys=True)


def _gates_from_json(payload: str) -> tuple[GateResult, ...]:
    return tuple(
        GateResult(gate=QualityGate(g["gate"]), passed=bool(g["passed"]), detail=g["detail"])
        for g in json.loads(payload)
    )


def decision_to_row(d: Decision) -> tuple:
    return (
        d.decision_id,
        d.ts.isoformat(),
        d.run_id,
        d.cycle_id,
        d.decision_type.value,
        d.explanation,
        d.instrument_id,
        d.direction.value,
        d.score_ref,
        d.confidence_ref,
        d.risk_ref,
        _gates_to_json(d.gate_results),
        _trade_plan_to_json(d.trade_plan),
    )


def row_to_decision(r: Sequence[Any]) -> Decision:
    return Decision(
        decision_id=r[0],
        ts=datetime.fromisoformat(r[1]),
        run_id=r[2],
        cycle_id=r[3],
        decision_type=DecisionType(r[4]),
        explanation=r[5],
        instrument_id=r[6],
        direction=Direction(r[7]),
        score_ref=r[8],
        confidence_ref=r[9],
        risk_ref=r[10],
        gate_results=_gates_from_json(r[11]),
        trade_plan=_trade_plan_from_json(r[12]),
    )


def trace_to_row(trace: DecisionTrace) -> tuple:
    stages = json.dumps([
        {"stage": s.stage, "ref_ids": list(s.ref_ids), "summary": s.summary}
        for s in trace.stages
    ], sort_keys=True)
    return (trace.decision_ref, stages)


def row_to_trace(r: Sequence[Any]) -> DecisionTrace:
    stages = tuple(
        TraceStage(stage=s["stage"], ref_ids=tuple(s["ref_ids"]), summary=s["summary"])
        for s in json.loads(r[1])
    )
    return DecisionTrace(decision_ref=r[0], stages=stages)


def journal_entry_id(entry: DecisionJournalEntry) -> str:
    return f"{entry.decision_ref}:{entry.action_ts.isoformat()}:{entry.user_action.value}"


def journal_to_row(entry: DecisionJournalEntry) -> tuple:
    return (
        journal_entry_id(entry),
        entry.decision_ref,
        entry.user_action.value,
        entry.action_ts.isoformat(),
        entry.notes or "",
    )


def row_to_journal(r: Sequence[Any]) -> DecisionJournalEntry:
    return DecisionJournalEntry(
        decision_ref=r[1],
        user_action=UserAction(r[2]),
        action_ts=datetime.fromisoformat(r[3]),
        notes=r[4] or "",
    )


def trade_outcome_id(decision_ref: str, closed_ts: datetime) -> str:
    """Canonical, deterministic id — callers should use this to construct
    ``TradeOutcome.outcome_id`` before persisting (mirrors journal_entry_id's
    determinism, but ``TradeOutcome`` has its own id field, so it is respected
    verbatim by ``trade_outcome_to_row``/``row_to_trade_outcome``, never
    recomputed on write)."""
    return f"{decision_ref}:{closed_ts.isoformat()}"


def trade_outcome_to_row(outcome: TradeOutcome) -> tuple:
    return (
        outcome.outcome_id,
        outcome.decision_ref,
        str(outcome.entry_price),
        str(outcome.exit_price),
        outcome.quantity,
        str(outcome.pnl),
        outcome.holding_seconds,
        json.dumps(dict(outcome.adherence), sort_keys=True),
        outcome.closed_ts.isoformat(),
    )


def row_to_trade_outcome(r: Sequence[Any]) -> TradeOutcome:
    return TradeOutcome(
        outcome_id=r[0],
        decision_ref=r[1],
        entry_price=Decimal(r[2]),
        exit_price=Decimal(r[3]),
        quantity=r[4],
        pnl=Decimal(r[5]),
        holding_seconds=r[6],
        adherence=json.loads(r[7]) if r[7] else {},
        closed_ts=datetime.fromisoformat(r[8]),
    )


def owner_position_to_row(
    *,
    position_id: str,
    instrument_id: str,
    opened_ts: datetime,
    quantity: int,
    avg_price: Decimal,
    closed_ts: datetime | None,
    exit_price: Decimal | None,
    decision_ref: str | None,
    broker: str,
    notes: str,
    sector: str,
    meta: Mapping[str, Any],
) -> tuple:
    return (
        position_id,
        instrument_id,
        opened_ts.isoformat(),
        int(quantity),
        str(avg_price),
        closed_ts.isoformat() if closed_ts is not None else None,
        str(exit_price) if exit_price is not None else None,
        decision_ref,
        broker or "",
        notes or "",
        sector or "",
        json.dumps(dict(meta), sort_keys=True, default=str),
    )


def row_to_owner_position(r: Sequence[Any]) -> Position:
    meta = dict(json.loads(r[11] or "{}"))
    if r[6] is not None:
        meta["exit_price"] = str(r[6])
    if r[7]:
        meta["decision_ref"] = r[7]
    if r[8]:
        meta["broker"] = r[8]
    if r[9]:
        meta["notes"] = r[9]
    if r[10]:
        meta["sector"] = r[10]
    return Position(
        position_id=r[0],
        instrument_id=r[1],
        opened_ts=datetime.fromisoformat(r[2]),
        quantity=int(r[3]),
        avg_price=Decimal(r[4]),
        closed_ts=datetime.fromisoformat(r[5]) if r[5] else None,
        meta=meta,
    )


# ----------------------------------------------------------- entry qualifications (ID-6C)

def _evidence_refs_to_json(refs: Sequence[EntryQualificationEvidenceRef]) -> str:
    return json.dumps(
        [
            {
                "kind": ref.kind.value,
                "ref_id": ref.ref_id,
                "as_of": ref.as_of.isoformat() if ref.as_of is not None else None,
                "explanation": ref.explanation,
            }
            for ref in refs
        ],
        sort_keys=True,
    )


def _evidence_refs_from_json(payload: str) -> tuple[EntryQualificationEvidenceRef, ...]:
    return tuple(
        EntryQualificationEvidenceRef(
            kind=EntryQualificationEvidenceKind(d["kind"]),
            ref_id=d["ref_id"],
            as_of=datetime.fromisoformat(d["as_of"]) if d["as_of"] is not None else None,
            explanation=d["explanation"],
        )
        for d in json.loads(payload)
    )


def _reason_codes_to_json(codes: Sequence[EntryQualificationReasonCode]) -> str:
    # Order-preserving: json.dumps(sort_keys=True) only sorts keys WITHIN
    # each object below, never the array itself (there are no objects here,
    # just a list of strings) -- the engine's deterministic reason-code
    # order (ID-6B.2 owner requirement) round-trips exactly.
    return json.dumps([c.value for c in codes])


def _reason_codes_from_json(payload: str) -> tuple[EntryQualificationReasonCode, ...]:
    return tuple(EntryQualificationReasonCode(v) for v in json.loads(payload))


def entry_qualification_to_row(eq: EntryQualification) -> tuple:
    return (
        eq.instrument_id,
        eq.session_date.isoformat(),
        eq.as_of.isoformat(),
        eq.decision_id,
        eq.methodology_version,
        eq.run_id,
        eq.cycle_id,
        eq.decision_type.value,
        eq.state.value,
        eq.evidence_finality.value,
        eq.confirmation.value,
        _reason_codes_to_json(eq.reason_codes),
        _evidence_refs_to_json(eq.evidence_refs),
        eq.config_snapshot_id,
        eq.explanation,
    )


def row_to_entry_qualification(r: Sequence[Any]) -> EntryQualification:
    return EntryQualification(
        instrument_id=r[0],
        session_date=date.fromisoformat(r[1]),
        as_of=datetime.fromisoformat(r[2]),
        decision_id=r[3],
        methodology_version=r[4],
        run_id=r[5],
        cycle_id=r[6],
        decision_type=DecisionType(r[7]),
        state=EntryQualificationState(r[8]),
        evidence_finality=EntryEvidenceFinality(r[9]),
        confirmation=EntryQualificationConfirmation(r[10]),
        reason_codes=_reason_codes_from_json(r[11]),
        evidence_refs=_evidence_refs_from_json(r[12]),
        config_snapshot_id=r[13],
        explanation=r[14],
    )


# ----------------------------------------------------------- entry actionabilities (ID-7A)

def _entry_actionability_reason_codes_to_json(
    codes: Sequence[EntryActionabilityReasonCode],
) -> str:
    # Order-preserving, mirroring _reason_codes_to_json's own rationale.
    return json.dumps([c.value for c in codes])


def _entry_actionability_reason_codes_from_json(
    payload: str,
) -> tuple[EntryActionabilityReasonCode, ...]:
    return tuple(EntryActionabilityReasonCode(v) for v in json.loads(payload))


def _entry_reference_to_json(ref: EntryReference | None) -> str | None:
    if ref is None:
        return None
    return json.dumps(
        {"price": str(ref.price), "basis": ref.basis.value}, sort_keys=True
    )


def _entry_reference_from_json(payload: str | None) -> EntryReference | None:
    if not payload:
        return None
    d = json.loads(payload)
    return EntryReference(price=Decimal(d["price"]), basis=EntryReferenceBasis(d["basis"]))


def _entry_location_context_to_json(ctx: EntryLocationContext | None) -> str | None:
    if ctx is None:
        return None
    return json.dumps(
        {"vwap": str(ctx.vwap), "vwap_deviation_pct": str(ctx.vwap_deviation_pct)},
        sort_keys=True,
    )


def _entry_location_context_from_json(payload: str | None) -> EntryLocationContext | None:
    if not payload:
        return None
    d = json.loads(payload)
    return EntryLocationContext(
        vwap=Decimal(d["vwap"]), vwap_deviation_pct=Decimal(d["vwap_deviation_pct"])
    )


def _operative_invalidation_to_json(inv: OperativeInvalidation | None) -> str | None:
    if inv is None:
        return None
    return json.dumps({"level": str(inv.level), "basis": inv.basis.value}, sort_keys=True)


def _operative_invalidation_from_json(payload: str | None) -> OperativeInvalidation | None:
    if not payload:
        return None
    d = json.loads(payload)
    return OperativeInvalidation(level=Decimal(d["level"]), basis=InvalidationBasis(d["basis"]))


def _opening_range_context_to_json(
    ctx: OpeningRangeContextReference | None,
) -> str | None:
    if ctx is None:
        return None
    return json.dumps({"level": str(ctx.level), "basis": ctx.basis.value}, sort_keys=True)


def _opening_range_context_from_json(
    payload: str | None,
) -> OpeningRangeContextReference | None:
    if not payload:
        return None
    d = json.loads(payload)
    return OpeningRangeContextReference(
        level=Decimal(d["level"]), basis=OpeningRangeContextBasis(d["basis"])
    )


def _reward_to_json(reward: RewardReference | None) -> str | None:
    if reward is None:
        return None
    return json.dumps(
        {
            "t1_price": str(reward.t1_price),
            "t2_price": str(reward.t2_price),
            "basis": reward.basis.value,
            "reward_risk_to_t1": (
                str(reward.reward_risk_to_t1) if reward.reward_risk_to_t1 is not None else None
            ),
            "reward_risk_to_t2": (
                str(reward.reward_risk_to_t2) if reward.reward_risk_to_t2 is not None else None
            ),
        },
        sort_keys=True,
    )


def _reward_from_json(payload: str | None) -> RewardReference | None:
    if not payload:
        return None
    d = json.loads(payload)
    return RewardReference(
        t1_price=Decimal(d["t1_price"]),
        t2_price=Decimal(d["t2_price"]),
        basis=RewardBasis(d["basis"]),
        reward_risk_to_t1=(
            Decimal(d["reward_risk_to_t1"]) if d["reward_risk_to_t1"] is not None else None
        ),
        reward_risk_to_t2=(
            Decimal(d["reward_risk_to_t2"]) if d["reward_risk_to_t2"] is not None else None
        ),
    )


def entry_actionability_to_row(ea: EntryActionability) -> tuple:
    return (
        ea.instrument_id,
        ea.session_date.isoformat(),
        ea.entry_qualification_as_of.isoformat(),
        ea.decision_id,
        ea.entry_qualification_methodology_version,
        ea.entry_actionability_as_of.isoformat(),
        ea.entry_actionability_methodology_version,
        ea.run_id,
        ea.cycle_id,
        ea.decision_type.value,
        ea.direction.value,
        ea.entry_qualification_state.value,
        ea.state.value,
        _entry_actionability_reason_codes_to_json(ea.reason_codes),
        ea.evidence_finality.value,
        ea.evidence_as_of.isoformat() if ea.evidence_as_of is not None else None,
        _entry_reference_to_json(ea.entry_reference),
        _entry_location_context_to_json(ea.entry_location_context),
        _operative_invalidation_to_json(ea.operative_invalidation),
        _reward_to_json(ea.reward),
        _opening_range_context_to_json(ea.opening_range_context),
        ea.evaluated_at.isoformat(),
        ea.explanation,
    )


def row_to_entry_actionability(r: Sequence[Any]) -> EntryActionability:
    return EntryActionability(
        instrument_id=r[0],
        session_date=date.fromisoformat(r[1]),
        entry_qualification_as_of=datetime.fromisoformat(r[2]),
        decision_id=r[3],
        entry_qualification_methodology_version=r[4],
        entry_actionability_as_of=datetime.fromisoformat(r[5]),
        entry_actionability_methodology_version=r[6],
        run_id=r[7],
        cycle_id=r[8],
        decision_type=DecisionType(r[9]),
        direction=Direction(r[10]),
        entry_qualification_state=EntryQualificationState(r[11]),
        state=EntryActionabilityState(r[12]),
        reason_codes=_entry_actionability_reason_codes_from_json(r[13]),
        evidence_finality=EntryEvidenceFinality(r[14]),
        evidence_as_of=datetime.fromisoformat(r[15]) if r[15] else None,
        entry_reference=_entry_reference_from_json(r[16]),
        entry_location_context=_entry_location_context_from_json(r[17]),
        operative_invalidation=_operative_invalidation_from_json(r[18]),
        reward=_reward_from_json(r[19]),
        opening_range_context=_opening_range_context_from_json(r[20]),
        evaluated_at=datetime.fromisoformat(r[21]),
        explanation=r[22],
    )
