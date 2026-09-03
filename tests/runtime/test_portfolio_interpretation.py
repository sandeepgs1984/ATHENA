"""Pure PS-P5B Portfolio Interpretation tests."""

from __future__ import annotations

from datetime import date, datetime, timezone
from decimal import Decimal

import pytest

from athena.domain.decision import Decision, GateResult, TradePlan
from athena.domain.enums import DecisionType, Direction, QualityGate
from athena.intraday.entry_qualification_models import (
    EntryEvidenceFinality,
    EntryQualification,
    EntryQualificationConfirmation,
    EntryQualificationReasonCode,
    EntryQualificationState,
)
from athena.portfolio.interpretation import (
    PORTFOLIO_INTERPRETATION_VERSION,
    PortfolioInterpretationEvidence,
    PortfolioInterpretationReason,
    PortfolioInterpreter,
    PortfolioNextAction,
    PortfolioStatus,
)

AS_OF = datetime(2026, 9, 2, 10, 0, tzinfo=timezone.utc)


def _plan(*, entry_low: str = "1500", stop: str = "1450") -> TradePlan:
    return TradePlan(
        entry_low=Decimal(entry_low),
        entry_high=Decimal("1510"),
        stop_loss=Decimal(stop),
        targets=(Decimal("1700"),),
        position_size=1,
        risk_amount=Decimal("50"),
        risk_reward=Decimal("4"),
        valid_from=AS_OF,
        valid_until=datetime(2026, 9, 3, 10, 0, tzinfo=timezone.utc),
    )


def _decision(
    *,
    decision_type: DecisionType = DecisionType.TRADE,
    plan: TradePlan | None = None,
    failed_gate: QualityGate | None = None,
) -> Decision:
    gate_results = (
        (GateResult(gate=failed_gate, passed=False, detail="failed for test"),)
        if failed_gate is not None
        else ()
    )
    return Decision(
        decision_id="decision-1",
        ts=AS_OF,
        run_id="run-1",
        cycle_id="cycle-1",
        decision_type=decision_type,
        explanation="test decision",
        instrument_id="NSE:INFY",
        direction=Direction.LONG if decision_type is DecisionType.TRADE else Direction.NONE,
        trade_plan=plan if decision_type is DecisionType.TRADE else None,
        gate_results=gate_results,
    )


def _entry_qualification(
    state: EntryQualificationState = EntryQualificationState.QUALIFIED,
) -> EntryQualification:
    return EntryQualification(
        instrument_id="NSE:INFY",
        session_date=date(2026, 9, 2),
        as_of=AS_OF,
        run_id="run-1",
        cycle_id="cycle-1",
        decision_id="decision-1",
        decision_type=DecisionType.TRADE,
        state=state,
        evidence_finality=EntryEvidenceFinality.NO_DECISIVE_PROVISIONAL_M5_DEPENDENCY,
        confirmation=EntryQualificationConfirmation.CONFIRMED_BY_POLICY,
        reason_codes=(EntryQualificationReasonCode.V0_READINESS_POLICY_SATISFIED,),
        evidence_refs=(),
        methodology_version="entry-qualification-v0",
        config_snapshot_id=None,
        explanation="qualified by prior engine output",
    )


def _evidence(
    *,
    last_price: str | None = "1600",
    price_is_current: bool = True,
    decision: Decision | None = None,
    decision_is_coherent: bool = True,
    trade_plan_is_active: bool = True,
    entry_qualification: EntryQualification | None = None,
    entry_qualification_is_coherent: bool = False,
) -> PortfolioInterpretationEvidence:
    resolved_decision = decision if decision is not None else _decision(plan=_plan())
    return PortfolioInterpretationEvidence(
        instrument_id="NSE:INFY",
        as_of=AS_OF,
        last_price=Decimal(last_price) if last_price is not None else None,
        price_is_current=price_is_current,
        decision=resolved_decision,
        decision_is_coherent=decision_is_coherent,
        trade_plan=resolved_decision.trade_plan if resolved_decision is not None else None,
        trade_plan_is_active=trade_plan_is_active,
        entry_qualification=entry_qualification,
        entry_qualification_is_coherent=entry_qualification_is_coherent,
    )


def _interpret(evidence: PortfolioInterpretationEvidence):
    return PortfolioInterpreter().interpret(evidence)


def test_trade_with_active_plan_is_strong_hold_until_entry_qualification_is_ready() -> None:
    result = _interpret(_evidence())

    assert result.interpretation_version == PORTFOLIO_INTERPRETATION_VERSION
    assert result.status is PortfolioStatus.STRONG
    assert result.next_action is PortfolioNextAction.HOLD
    assert result.major_support_exit == Decimal("1450")
    assert result.key_trigger is None
    assert PortfolioInterpretationReason.ADD_NOT_CONFIRMED in result.reason_codes
    assert PortfolioInterpretationReason.ENTRY_TRIGGER_CONSUMED in result.reason_codes


def test_qualified_entry_qualification_allows_add_without_pnl_input() -> None:
    result = _interpret(
        _evidence(
            entry_qualification=_entry_qualification(),
            entry_qualification_is_coherent=True,
        )
    )

    assert result.status is PortfolioStatus.STRONG
    assert result.next_action is PortfolioNextAction.ADD
    assert PortfolioInterpretationReason.ENTRY_QUALIFICATION_READY in result.reason_codes


def test_stop_breach_including_exact_boundary_exits() -> None:
    for price in ("1450", "1449.95"):
        result = _interpret(_evidence(last_price=price))

        assert result.status is PortfolioStatus.AT_RISK
        assert result.next_action is PortfolioNextAction.EXIT
        assert result.major_support_exit == Decimal("1450")
        assert PortfolioInterpretationReason.TRADE_PLAN_STOP_BREACHED in result.reason_codes


@pytest.mark.parametrize(
    ("price", "expected_trigger", "expected_reason"),
    [
        ("1499.95", Decimal("1500"), PortfolioInterpretationReason.TRADE_PLAN_ENTRY_TRIGGER_ACTIVE),
        ("1500", None, PortfolioInterpretationReason.ENTRY_TRIGGER_CONSUMED),
        ("1505", None, PortfolioInterpretationReason.ENTRY_TRIGGER_CONSUMED),
        ("1510", None, PortfolioInterpretationReason.ENTRY_TRIGGER_CONSUMED),
        ("1600", None, PortfolioInterpretationReason.ENTRY_TRIGGER_CONSUMED),
    ],
)
def test_key_trigger_uses_only_trade_plan_entry_low_boundaries(
    price: str,
    expected_trigger: Decimal | None,
    expected_reason: PortfolioInterpretationReason,
) -> None:
    result = _interpret(_evidence(last_price=price))

    assert result.key_trigger == expected_trigger
    assert expected_reason in result.reason_codes


def test_missing_or_stale_evidence_blocks_trade_plan_interpretation() -> None:
    stale = _interpret(
        _evidence(
            price_is_current=False,
            decision_is_coherent=False,
            trade_plan_is_active=False,
        )
    )
    missing = _interpret(
        PortfolioInterpretationEvidence(
            instrument_id="NSE:INFY",
            as_of=AS_OF,
            last_price=None,
            price_is_current=True,
            decision=None,
            decision_is_coherent=False,
            trade_plan=None,
            trade_plan_is_active=False,
        )
    )

    assert stale.status is PortfolioStatus.UNAVAILABLE
    assert stale.next_action is PortfolioNextAction.WATCH
    assert stale.major_support_exit is None
    assert missing.status is PortfolioStatus.UNAVAILABLE
    assert missing.next_action is PortfolioNextAction.WATCH


def test_no_trade_and_failed_gates_watch_without_exit() -> None:
    no_trade = _interpret(
        _evidence(decision=_decision(decision_type=DecisionType.NO_TRADE, plan=None))
    )
    failed_gate = _interpret(
        _evidence(
            decision=_decision(
                decision_type=DecisionType.WATCH,
                plan=None,
                failed_gate=QualityGate.RISK,
            ),
            trade_plan_is_active=False,
        )
    )

    assert no_trade.status is PortfolioStatus.CAUTION
    assert no_trade.next_action is PortfolioNextAction.WATCH
    assert failed_gate.status is PortfolioStatus.CAUTION
    assert failed_gate.next_action is PortfolioNextAction.WATCH
    assert PortfolioInterpretationReason.DECISION_GATE_FAILED_RISK in failed_gate.reason_codes


def test_null_methodology_fields_remain_null_with_reasons() -> None:
    result = _interpret(_evidence())

    assert result.conviction is None
    assert result.trend_setup is None
    assert result.support_1 is None
    assert result.target_2 is None
    assert result.target_3 is None
    assert PortfolioInterpretationReason.CONFIDENCE_EVIDENCE_UNAVAILABLE in result.reason_codes
    assert PortfolioInterpretationReason.TREND_SETUP_NOT_AVAILABLE in result.reason_codes
    assert PortfolioInterpretationReason.SUPPORT_1_METHODOLOGY_UNAVAILABLE in result.reason_codes
    assert PortfolioInterpretationReason.NO_APPROVED_SECONDARY_TARGET in result.reason_codes
