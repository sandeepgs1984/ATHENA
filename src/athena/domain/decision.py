"""Decision-side canonical objects (ATHENA-002 §4, R-6, F-15)."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from datetime import datetime
from decimal import Decimal
from typing import Any

from athena.domain.enums import DecisionType, Direction, QualityGate, UserAction


@dataclass(frozen=True, slots=True)
class TradePlan:
    """Actionable plan attached to a TRADE decision. ATHENA never executes it."""

    entry_low: Decimal
    entry_high: Decimal
    stop_loss: Decimal
    targets: tuple[Decimal, ...]
    position_size: int
    risk_amount: Decimal
    risk_reward: Decimal
    valid_from: datetime
    valid_until: datetime

    def __post_init__(self) -> None:
        if self.entry_low > self.entry_high:
            raise ValueError("TradePlan.entry_low must be <= entry_high")
        if not self.targets:
            raise ValueError("TradePlan.targets must be non-empty")
        if self.position_size < 1:
            raise ValueError("TradePlan.position_size must be >= 1")
        if self.valid_from >= self.valid_until:
            raise ValueError("TradePlan validity window is empty")


@dataclass(frozen=True, slots=True)
class RiskEvaluation:
    """Risk engine verdict (F-4: evaluation only — sizing lives in CapitalState)."""

    evaluation_id: str
    passed: bool
    rules_checked: tuple[str, ...]
    blocking_reasons: tuple[str, ...]
    explanation: str

    def __post_init__(self) -> None:
        if not self.explanation:
            raise ValueError("RiskEvaluation.explanation is mandatory (ADR-005)")
        if not self.passed and not self.blocking_reasons:
            raise ValueError("A failing RiskEvaluation must name its blocking reasons")


@dataclass(frozen=True, slots=True)
class CapitalState:
    """Capital Manager output (F-3). Amounts are Decimal INR."""

    daily_capital: Decimal
    allocated_capital: Decimal
    reserved_capital: Decimal
    risk_capital: Decimal
    available_buying_power: Decimal
    max_capital_per_sector: Decimal
    max_capital_per_position: Decimal
    explanation: str

    def __post_init__(self) -> None:
        if not self.explanation:
            raise ValueError("CapitalState.explanation is mandatory (ADR-005)")
        for name in ("daily_capital", "reserved_capital", "available_buying_power"):
            if getattr(self, name) < 0:
                raise ValueError(f"CapitalState.{name} must be >= 0")


@dataclass(frozen=True, slots=True)
class GateResult:
    """Outcome of one quality gate (F-12)."""

    gate: QualityGate
    passed: bool
    detail: str

    def __post_init__(self) -> None:
        if not self.detail:
            raise ValueError("GateResult.detail is mandatory — gates explain themselves")


@dataclass(frozen=True, slots=True)
class TraceStage:
    """One step in a DecisionTrace (F-15)."""

    stage: str
    ref_ids: tuple[str, ...]
    summary: str

    def __post_init__(self) -> None:
        if not self.summary:
            raise ValueError("TraceStage.summary is mandatory")


@dataclass(frozen=True, slots=True)
class DecisionTrace:
    """Complete reasoning path — the primary debugging and learning artifact (F-15)."""

    decision_ref: str
    stages: tuple[TraceStage, ...]

    def __post_init__(self) -> None:
        if not self.stages:
            raise ValueError("DecisionTrace must contain at least one stage")


@dataclass(frozen=True, slots=True)
class Decision:
    """Canonical recommendation (R-6). Advisory only — ATHENA never places orders."""

    decision_id: str
    ts: datetime
    run_id: str
    cycle_id: str
    decision_type: DecisionType
    explanation: str
    instrument_id: str | None = None
    direction: Direction = Direction.NONE
    score_ref: str | None = None
    confidence_ref: str | None = None
    risk_ref: str | None = None
    gate_results: tuple[GateResult, ...] = ()
    trade_plan: TradePlan | None = None

    def __post_init__(self) -> None:
        if not self.explanation:
            raise ValueError("Decision.explanation is mandatory (ATHENA-000 p9, ADR-005)")
        if self.ts.tzinfo is None:
            raise ValueError("Decision.ts must be timezone-aware")
        if self.decision_type is DecisionType.TRADE:
            if self.trade_plan is None:
                raise ValueError("A TRADE decision must carry a TradePlan")
            if self.direction is Direction.NONE:
                raise ValueError("A TRADE decision must have a direction")
            failed = [g.gate.value for g in self.gate_results if not g.passed]
            if failed:
                raise ValueError(
                    f"A TRADE decision cannot have failed quality gates: {failed} (F-12)"
                )


@dataclass(frozen=True, slots=True)
class Position:
    """An open or closed position (owner-entered; ATHENA observes, never creates)."""

    position_id: str
    instrument_id: str
    opened_ts: datetime
    quantity: int
    avg_price: Decimal
    closed_ts: datetime | None = None
    meta: Mapping[str, Any] = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class Portfolio:
    """Aggregate portfolio state at a moment."""

    ts: datetime
    positions: tuple[Position, ...]
    cash: Decimal
    exposure_by_sector: Mapping[str, Decimal] = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class DecisionJournalEntry:
    """Every recommendation + the human response (R-9). Nothing is unrecorded."""

    decision_ref: str
    user_action: UserAction
    action_ts: datetime
    notes: str = ""


@dataclass(frozen=True, slots=True)
class TradeOutcome:
    """Realized result for an accepted decision."""

    outcome_id: str
    decision_ref: str
    entry_price: Decimal
    exit_price: Decimal
    quantity: int
    pnl: Decimal
    holding_seconds: int
    adherence: Mapping[str, bool]
    closed_ts: datetime
