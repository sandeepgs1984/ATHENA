"""Pure Portfolio Interpretation methodology (PS-P5B).

Consumes only already-accepted Portfolio Sync evidence and produces the
methodology-sensitive My Portfolio fields approved for PS-P5B. No repository,
provider, indicator, scoring, or decision-engine access belongs here.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from enum import Enum, unique

from athena.confidence.models import ConfidenceLevel
from athena.domain.decision import Decision, TradePlan
from athena.domain.enums import DecisionType, QualityGate
from athena.intraday.entry_qualification_models import (
    EntryQualification,
    EntryQualificationState,
)
from athena.portfolio.setup_adapter import PortfolioSetup, PortfolioSetupReason
from athena.portfolio.trend_adapter import PortfolioTrend, PortfolioTrendReason

PORTFOLIO_INTERPRETATION_VERSION = "portfolio-interpretation-v3"


@unique
class PortfolioStatus(str, Enum):
    STRONG = "STRONG"
    HEALTHY = "HEALTHY"
    CAUTION = "CAUTION"
    AT_RISK = "AT_RISK"
    UNAVAILABLE = "UNAVAILABLE"


@unique
class PortfolioNextAction(str, Enum):
    HOLD = "HOLD"
    ADD = "ADD"
    EXIT = "EXIT"
    WATCH = "WATCH"


@unique
class PortfolioInterpretationReason(str, Enum):
    PRICE_UNAVAILABLE = "PRICE_UNAVAILABLE"
    STALE_PRICE_SESSION = "STALE_PRICE_SESSION"
    NO_CURRENT_DECISION = "NO_CURRENT_DECISION"
    STALE_DECISION_EVIDENCE = "STALE_DECISION_EVIDENCE"
    INSUFFICIENT_DECISION_DATA = "INSUFFICIENT_DECISION_DATA"
    DECISION_GATE_FAILED_DATA = "DECISION_GATE_FAILED_DATA"
    DECISION_GATE_FAILED_EVIDENCE = "DECISION_GATE_FAILED_EVIDENCE"
    DECISION_GATE_FAILED_RISK = "DECISION_GATE_FAILED_RISK"
    DECISION_GATE_FAILED_CONFIDENCE = "DECISION_GATE_FAILED_CONFIDENCE"
    DECISION_GATE_FAILED_MARKET = "DECISION_GATE_FAILED_MARKET"
    NO_TRADE_DECISION_EVIDENCE = "NO_TRADE_DECISION_EVIDENCE"
    WATCH_STRUCTURE_INTACT = "WATCH_STRUCTURE_INTACT"
    STRUCTURE_INTACT = "STRUCTURE_INTACT"
    CURRENT_TRADE_PLAN = "CURRENT_TRADE_PLAN"
    ALL_DECISION_GATES_PASSED = "ALL_DECISION_GATES_PASSED"
    ENTRY_QUALIFICATION_READY = "ENTRY_QUALIFICATION_READY"
    ENTRY_QUALIFICATION_NOT_READY = "ENTRY_QUALIFICATION_NOT_READY"
    ENTRY_QUALIFICATION_NOT_COHERENT = "ENTRY_QUALIFICATION_NOT_COHERENT"
    ADD_NOT_CONFIRMED = "ADD_NOT_CONFIRMED"
    TRADE_PLAN_ENTRY_TRIGGER_ACTIVE = "TRADE_PLAN_ENTRY_TRIGGER_ACTIVE"
    ENTRY_TRIGGER_CONSUMED = "ENTRY_TRIGGER_CONSUMED"
    TRADE_PLAN_EXPIRED = "TRADE_PLAN_EXPIRED"
    NO_ACTIVE_TRIGGER_EVIDENCE = "NO_ACTIVE_TRIGGER_EVIDENCE"
    TRADE_PLAN_STOP_AVAILABLE = "TRADE_PLAN_STOP_AVAILABLE"
    TRADE_PLAN_STOP_BREACHED = "TRADE_PLAN_STOP_BREACHED"
    MAJOR_INVALIDATION_BREACHED = "MAJOR_INVALIDATION_BREACHED"
    SUPPORT_1_METHODOLOGY_UNAVAILABLE = "SUPPORT_1_METHODOLOGY_UNAVAILABLE"
    NO_APPROVED_SECONDARY_TARGET = "NO_APPROVED_SECONDARY_TARGET"
    CONFIDENCE_EVIDENCE_UNAVAILABLE = "CONFIDENCE_EVIDENCE_UNAVAILABLE"
    CONVICTION_FROM_CONFIDENCE = "CONVICTION_FROM_CONFIDENCE"
    CONVICTION_CONFIDENCE_UNAVAILABLE = "CONVICTION_CONFIDENCE_UNAVAILABLE"
    CONVICTION_CONFIDENCE_INCOHERENT = "CONVICTION_CONFIDENCE_INCOHERENT"
    TREND_UP_FROM_D1_SMA_STRUCTURE = "TREND_UP_FROM_D1_SMA_STRUCTURE"
    TREND_DOWN_FROM_D1_SMA_STRUCTURE = "TREND_DOWN_FROM_D1_SMA_STRUCTURE"
    TREND_MIXED_FROM_D1_SMA_STRUCTURE = "TREND_MIXED_FROM_D1_SMA_STRUCTURE"
    TREND_D1_EVIDENCE_UNAVAILABLE = "TREND_D1_EVIDENCE_UNAVAILABLE"
    TREND_D1_EVIDENCE_INCOHERENT = "TREND_D1_EVIDENCE_INCOHERENT"
    SETUP_METHODOLOGY_DEFERRED = "SETUP_METHODOLOGY_DEFERRED"
    SETUP_BREAKOUT_FROM_OPENING_RANGE_AGREEMENT = (
        "SETUP_BREAKOUT_FROM_OPENING_RANGE_AGREEMENT"
    )
    SETUP_BREAKDOWN_FROM_OPENING_RANGE_AGREEMENT = (
        "SETUP_BREAKDOWN_FROM_OPENING_RANGE_AGREEMENT"
    )
    SETUP_EVIDENCE_INCOHERENT = "SETUP_EVIDENCE_INCOHERENT"
    SETUP_EVIDENCE_STALE = "SETUP_EVIDENCE_STALE"
    SETUP_EVIDENCE_UNAVAILABLE = "SETUP_EVIDENCE_UNAVAILABLE"
    SETUP_OR_INCOMPLETE = "SETUP_OR_INCOMPLETE"
    SETUP_OR_WINDOWS_CONFLICT = "SETUP_OR_WINDOWS_CONFLICT"
    SETUP_RETURNED_INSIDE_RANGE = "SETUP_RETURNED_INSIDE_RANGE"
    SETUP_SINGLE_WINDOW_ONLY = "SETUP_SINGLE_WINDOW_ONLY"
    SETUP_NOT_PRESENT = "SETUP_NOT_PRESENT"
    CONTEXT_CAUTION = "CONTEXT_CAUTION"
    NO_STRONGER_ACTION_SUPPORTED = "NO_STRONGER_ACTION_SUPPORTED"


@dataclass(frozen=True, slots=True)
class PortfolioInterpretationEvidence:
    instrument_id: str
    as_of: datetime
    last_price: Decimal | None
    price_is_current: bool
    decision: Decision | None
    decision_is_coherent: bool
    trade_plan: TradePlan | None
    trade_plan_is_active: bool
    entry_qualification: EntryQualification | None = None
    entry_qualification_is_coherent: bool = False
    confidence_level: ConfidenceLevel | None = None
    confidence_is_coherent: bool = False
    trend: PortfolioTrend | None = None
    trend_is_coherent: bool = False
    trend_reason: PortfolioTrendReason | None = None
    setup: PortfolioSetup | None = None
    setup_is_coherent: bool = False
    setup_reason: PortfolioSetupReason | None = None

    def __post_init__(self) -> None:
        if not self.instrument_id:
            raise ValueError("PortfolioInterpretationEvidence.instrument_id is mandatory")
        if self.as_of.tzinfo is None:
            raise ValueError("PortfolioInterpretationEvidence.as_of must be timezone-aware")


@dataclass(frozen=True, slots=True)
class PortfolioInterpretationResult:
    status: PortfolioStatus
    key_trigger: Decimal | None
    major_support_exit: Decimal | None
    next_action: PortfolioNextAction
    conviction: str | None
    trend_setup: str | None
    support_1: Decimal | None
    target_2: Decimal | None
    target_3: Decimal | None
    reason_codes: tuple[PortfolioInterpretationReason, ...]
    interpretation_version: str = PORTFOLIO_INTERPRETATION_VERSION


class PortfolioInterpreter:
    """Deterministic PS-P5B portfolio interpretation."""

    def interpret(
        self,
        evidence: PortfolioInterpretationEvidence,
    ) -> PortfolioInterpretationResult:
        reasons: list[PortfolioInterpretationReason] = [
            PortfolioInterpretationReason.SUPPORT_1_METHODOLOGY_UNAVAILABLE,
            PortfolioInterpretationReason.NO_APPROVED_SECONDARY_TARGET,
        ]
        conviction = self._conviction(evidence, reasons)
        trend_setup = self._trend_setup(evidence, reasons)

        if evidence.trade_plan is not None and not evidence.trade_plan_is_active:
            reasons.append(PortfolioInterpretationReason.TRADE_PLAN_EXPIRED)
        plan = evidence.trade_plan if evidence.trade_plan_is_active else None
        stop = plan.stop_loss if plan is not None else None
        key_trigger = self._key_trigger(evidence, plan, reasons)
        major_support_exit = stop
        if stop is not None:
            reasons.append(PortfolioInterpretationReason.TRADE_PLAN_STOP_AVAILABLE)

        status = self._status(evidence, plan, stop, reasons)
        next_action = self._next_action(evidence, plan, stop, status, reasons)

        return PortfolioInterpretationResult(
            status=status,
            key_trigger=key_trigger,
            major_support_exit=major_support_exit,
            next_action=next_action,
            conviction=conviction,
            trend_setup=trend_setup,
            support_1=None,
            target_2=None,
            target_3=None,
            reason_codes=tuple(dict.fromkeys(reasons)),
        )

    @staticmethod
    def _conviction(
        evidence: PortfolioInterpretationEvidence,
        reasons: list[PortfolioInterpretationReason],
    ) -> str | None:
        if (
            evidence.confidence_level is not None
            and evidence.confidence_is_coherent
            and evidence.decision is not None
            and evidence.decision_is_coherent
        ):
            reasons.append(PortfolioInterpretationReason.CONVICTION_FROM_CONFIDENCE)
            return evidence.confidence_level.value
        if (
            not evidence.confidence_is_coherent
            and evidence.decision is not None
            and evidence.decision_is_coherent is False
        ) or (evidence.confidence_level is not None and not evidence.confidence_is_coherent):
            reasons.append(PortfolioInterpretationReason.CONVICTION_CONFIDENCE_INCOHERENT)
        else:
            reasons.append(PortfolioInterpretationReason.CONVICTION_CONFIDENCE_UNAVAILABLE)
        return None

    @staticmethod
    def _trend_setup(
        evidence: PortfolioInterpretationEvidence,
        reasons: list[PortfolioInterpretationReason],
    ) -> str | None:
        trend_label: str | None = None
        if evidence.trend is not None and evidence.trend_is_coherent:
            if evidence.trend_reason is not None:
                reasons.append(PortfolioInterpretationReason(evidence.trend_reason.value))
            trend_label = evidence.trend.value
        elif evidence.trend_reason is PortfolioTrendReason.D1_EVIDENCE_INCOHERENT:
            reasons.append(PortfolioInterpretationReason.TREND_D1_EVIDENCE_INCOHERENT)
        else:
            reasons.append(PortfolioInterpretationReason.TREND_D1_EVIDENCE_UNAVAILABLE)

        setup_label: str | None = None
        if evidence.setup is not None and evidence.setup_is_coherent:
            if evidence.setup_reason is not None:
                reasons.append(PortfolioInterpretationReason(evidence.setup_reason.value))
            setup_label = evidence.setup.value
        elif evidence.setup_reason is not None:
            reasons.append(PortfolioInterpretationReason(evidence.setup_reason.value))
        else:
            reasons.append(PortfolioInterpretationReason.SETUP_EVIDENCE_UNAVAILABLE)

        if trend_label is None and setup_label is None:
            return None
        return f"{trend_label or '-'} / {setup_label or '-'}"

    def _status(
        self,
        evidence: PortfolioInterpretationEvidence,
        plan: TradePlan | None,
        stop: Decimal | None,
        reasons: list[PortfolioInterpretationReason],
    ) -> PortfolioStatus:
        if evidence.last_price is None:
            reasons.append(PortfolioInterpretationReason.PRICE_UNAVAILABLE)
            return PortfolioStatus.UNAVAILABLE
        if not evidence.price_is_current:
            reasons.append(PortfolioInterpretationReason.STALE_PRICE_SESSION)
            return PortfolioStatus.UNAVAILABLE
        if evidence.decision is None:
            reasons.append(PortfolioInterpretationReason.NO_CURRENT_DECISION)
            return PortfolioStatus.UNAVAILABLE
        if not evidence.decision_is_coherent:
            reasons.append(PortfolioInterpretationReason.STALE_DECISION_EVIDENCE)
            return PortfolioStatus.UNAVAILABLE

        if stop is not None and evidence.last_price <= stop:
            reasons.extend(
                [
                    PortfolioInterpretationReason.TRADE_PLAN_STOP_BREACHED,
                    PortfolioInterpretationReason.MAJOR_INVALIDATION_BREACHED,
                ]
            )
            return PortfolioStatus.AT_RISK

        decision = evidence.decision
        if decision.decision_type in (
            DecisionType.INSUFFICIENT_DATA,
            DecisionType.DATA_VALIDATION_FAILED,
        ):
            reasons.append(PortfolioInterpretationReason.INSUFFICIENT_DECISION_DATA)
            return PortfolioStatus.UNAVAILABLE

        failed_gates = [gate.gate for gate in decision.gate_results if not gate.passed]
        if failed_gates:
            reasons.extend(self._gate_reasons(failed_gates))
            return PortfolioStatus.CAUTION

        if decision.decision_type is DecisionType.NO_TRADE:
            reasons.append(PortfolioInterpretationReason.NO_TRADE_DECISION_EVIDENCE)
            return PortfolioStatus.CAUTION

        if self._entry_qualified(evidence):
            reasons.append(PortfolioInterpretationReason.ENTRY_QUALIFICATION_READY)
            return PortfolioStatus.STRONG

        if decision.decision_type is DecisionType.TRADE and plan is not None:
            reasons.extend(
                [
                    PortfolioInterpretationReason.CURRENT_TRADE_PLAN,
                    PortfolioInterpretationReason.ALL_DECISION_GATES_PASSED,
                ]
            )
            return PortfolioStatus.STRONG

        if decision.decision_type is DecisionType.WATCH:
            reasons.append(PortfolioInterpretationReason.WATCH_STRUCTURE_INTACT)
            return PortfolioStatus.HEALTHY

        reasons.append(PortfolioInterpretationReason.STRUCTURE_INTACT)
        return PortfolioStatus.HEALTHY

    def _next_action(
        self,
        evidence: PortfolioInterpretationEvidence,
        plan: TradePlan | None,
        stop: Decimal | None,
        status: PortfolioStatus,
        reasons: list[PortfolioInterpretationReason],
    ) -> PortfolioNextAction:
        if status is PortfolioStatus.UNAVAILABLE:
            reasons.append(PortfolioInterpretationReason.NO_STRONGER_ACTION_SUPPORTED)
            return PortfolioNextAction.WATCH
        if (
            status is PortfolioStatus.AT_RISK
            and stop is not None
            and evidence.last_price is not None
            and evidence.last_price <= stop
        ):
            return PortfolioNextAction.EXIT
        if status is PortfolioStatus.CAUTION:
            reasons.append(PortfolioInterpretationReason.CONTEXT_CAUTION)
            return PortfolioNextAction.WATCH
        if plan is not None and self._entry_qualified(evidence):
            return PortfolioNextAction.ADD
        if plan is not None:
            reasons.append(PortfolioInterpretationReason.ADD_NOT_CONFIRMED)
            return PortfolioNextAction.HOLD
        if evidence.decision is not None and evidence.decision.decision_type is DecisionType.WATCH:
            return PortfolioNextAction.HOLD
        reasons.append(PortfolioInterpretationReason.NO_STRONGER_ACTION_SUPPORTED)
        return PortfolioNextAction.WATCH

    @staticmethod
    def _key_trigger(
        evidence: PortfolioInterpretationEvidence,
        plan: TradePlan | None,
        reasons: list[PortfolioInterpretationReason],
    ) -> Decimal | None:
        if plan is None or evidence.last_price is None:
            reasons.append(PortfolioInterpretationReason.NO_ACTIVE_TRIGGER_EVIDENCE)
            return None
        if evidence.last_price < plan.entry_low:
            reasons.append(PortfolioInterpretationReason.TRADE_PLAN_ENTRY_TRIGGER_ACTIVE)
            return plan.entry_low
        reasons.append(PortfolioInterpretationReason.ENTRY_TRIGGER_CONSUMED)
        return None

    @staticmethod
    def _entry_qualified(evidence: PortfolioInterpretationEvidence) -> bool:
        if evidence.entry_qualification is None:
            return False
        if not evidence.entry_qualification_is_coherent:
            return False
        return evidence.entry_qualification.state is EntryQualificationState.QUALIFIED

    @staticmethod
    def _gate_reasons(
        failed_gates: list[QualityGate],
    ) -> list[PortfolioInterpretationReason]:
        mapping = {
            QualityGate.DATA: PortfolioInterpretationReason.DECISION_GATE_FAILED_DATA,
            QualityGate.EVIDENCE: PortfolioInterpretationReason.DECISION_GATE_FAILED_EVIDENCE,
            QualityGate.RISK: PortfolioInterpretationReason.DECISION_GATE_FAILED_RISK,
            QualityGate.CONFIDENCE: PortfolioInterpretationReason.DECISION_GATE_FAILED_CONFIDENCE,
            QualityGate.MARKET: PortfolioInterpretationReason.DECISION_GATE_FAILED_MARKET,
        }
        return [
            mapping.get(gate, PortfolioInterpretationReason.CONTEXT_CAUTION)
            for gate in failed_gates
        ]
