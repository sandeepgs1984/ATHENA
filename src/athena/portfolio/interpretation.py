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

PORTFOLIO_INTERPRETATION_VERSION = "portfolio-interpretation-v1"


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
    TREND_SETUP_NOT_AVAILABLE = "TREND_SETUP_NOT_AVAILABLE"
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
            PortfolioInterpretationReason.TREND_SETUP_NOT_AVAILABLE,
            PortfolioInterpretationReason.SUPPORT_1_METHODOLOGY_UNAVAILABLE,
            PortfolioInterpretationReason.NO_APPROVED_SECONDARY_TARGET,
        ]
        conviction = self._conviction(evidence, reasons)

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
            trend_setup=None,
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
