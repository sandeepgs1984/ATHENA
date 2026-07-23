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
from athena.domain.enums import (
    DecisionType,
    Direction,
    QualityGate,
    RunStatus,
    RunTrigger,
    Timeframe,
    UserAction,
)
from athena.domain.market import Candle, CorporateAction, Instrument, MarketSnapshot, Quote
from athena.domain.decision import (
    Decision,
    DecisionJournalEntry,
    DecisionTrace,
    GateResult,
    TraceStage,
    TradePlan,
)
from athena.domain.run import RunRecord


def _opt_date(value: str | None) -> date | None:
    return date.fromisoformat(value) if value else None


# --------------------------------------------------------------------- instruments

def instrument_to_row(i: Instrument) -> tuple:
    return (
        i.instrument_id, i.isin, i.symbol, i.exchange, i.series,
        i.lot_size, str(i.tick_size), i.status,
        i.listed_date.isoformat() if i.listed_date else None,
        i.delisted_date.isoformat() if i.delisted_date else None,
    )


def row_to_instrument(r: Sequence[Any]) -> Instrument:
    return Instrument(
        instrument_id=r[0], isin=r[1], symbol=r[2], exchange=r[3], series=r[4],
        lot_size=int(r[5]), tick_size=Decimal(r[6]), status=r[7],
        listed_date=_opt_date(r[8]), delisted_date=_opt_date(r[9]),
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
