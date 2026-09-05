"""Entry Actionability pure V0 deterministic evaluator (ID-7C).

Direct construction of value-object fixtures throughout (no
IntradayAnalyticsEngine/session wiring) so each test controls exactly
which upstream Decision/EntryQualification/market-evidence combination
appears. Proves the frozen V0 methodology (ID-7B/ID-7B.1/ID-7B.2/
ID-7B.2.1) is faithfully implemented, the upstream-eligibility-then-
layer-3 evaluation order (ID-7A.2's own domain invariant) is honored,
currentness/persistence/latest-lookup/provider concerns are entirely
absent, and every produced artifact passes `EntryActionability`'s own
domain construction naturally.
"""

from __future__ import annotations

import dataclasses
from datetime import date, datetime, timedelta
from decimal import Decimal
from zoneinfo import ZoneInfo

import pytest

from athena.domain.decision import Decision, TradePlan
from athena.domain.enums import DecisionType, Direction, Timeframe
from athena.domain.market import Candle
from athena.intraday.entry_actionability_engine import (
    EntryActionabilityEngine,
    EntryActionabilityMarketEvidence,
    EntryActionabilityPolicy,
)
from athena.intraday.entry_actionability_models import (
    DEFAULT_METHODOLOGY_VERSION as EA_DEFAULT_METHODOLOGY_VERSION,
    EntryActionabilityReasonCode,
    EntryActionabilityState,
)
from athena.intraday.entry_qualification_engine import DEFAULT_METHODOLOGY_VERSION as EQ_DEFAULT_METHODOLOGY_VERSION
from athena.intraday.entry_qualification_models import (
    EntryEvidenceFinality,
    EntryQualification,
    EntryQualificationConfirmation,
    EntryQualificationState,
)
from athena.intraday.opening_range_models import (
    OpeningRangeEvidence,
    OpeningRangeFormation,
    OpeningRangeFormationStatus,
    OpeningRangeRelation,
    OpeningRangeWindow,
    BreakoutEvent,
)

IST = ZoneInfo("Asia/Kolkata")
IID = "NSE:TEST"
DAY = date(2026, 9, 4)
EQ_AS_OF = datetime(2026, 9, 4, 9, 50, tzinfo=IST)
EVALUATED_AT = datetime(2026, 9, 4, 9, 51, tzinfo=IST)


def _plan() -> TradePlan:
    return TradePlan(
        entry_low=Decimal("99"), entry_high=Decimal("101"), stop_loss=Decimal("97"),
        targets=(Decimal("105"),), position_size=10, risk_amount=Decimal("20"),
        risk_reward=Decimal("2"), valid_from=EQ_AS_OF, valid_until=EQ_AS_OF + timedelta(days=1),
    )


def _decision(
    *,
    decision_id: str = "decision-1",
    decision_type: DecisionType = DecisionType.TRADE,
    direction: Direction = Direction.LONG,
    instrument_id: str | None = IID,
    run_id: str = "run-1",
    cycle_id: str = "cycle-1",
) -> Decision:
    return Decision(
        decision_id=decision_id, ts=EQ_AS_OF, run_id=run_id, cycle_id=cycle_id,
        decision_type=decision_type, explanation="test decision",
        instrument_id=instrument_id, direction=direction,
        trade_plan=_plan() if decision_type is DecisionType.TRADE else None,
    )


def _eq(
    *,
    decision_id: str = "decision-1",
    state: EntryQualificationState = EntryQualificationState.QUALIFIED,
    decision_type: DecisionType = DecisionType.TRADE,
    instrument_id: str = IID,
    run_id: str = "run-1",
    cycle_id: str = "cycle-1",
    as_of: datetime = EQ_AS_OF,
    methodology_version: str = EQ_DEFAULT_METHODOLOGY_VERSION,
) -> EntryQualification:
    return EntryQualification(
        instrument_id=instrument_id, session_date=DAY, as_of=as_of,
        run_id=run_id, cycle_id=cycle_id, decision_id=decision_id,
        decision_type=decision_type, state=state,
        evidence_finality=EntryEvidenceFinality.NO_DECISIVE_PROVISIONAL_M5_DEPENDENCY,
        confirmation=EntryQualificationConfirmation.CONFIRMED_BY_POLICY,
        reason_codes=(), evidence_refs=(), methodology_version=methodology_version,
        config_snapshot_id=None, explanation="qualified test",
    )


def _candle(
    *,
    close: Decimal = Decimal("100.00"),
    ts_open: datetime = EQ_AS_OF - timedelta(minutes=5),
    instrument_id: str = IID,
    timeframe: Timeframe = Timeframe.M5,
    open_: Decimal | None = None,
    high: Decimal | None = None,
    low: Decimal | None = None,
) -> Candle:
    open_ = open_ if open_ is not None else close
    high = high if high is not None else max(open_, close) + Decimal("0.50")
    low = low if low is not None else min(open_, close) - Decimal("0.50")
    return Candle(
        instrument_id=instrument_id, timeframe=timeframe, ts_open=ts_open,
        open=open_, high=high, low=low, close=close, volume=1000, source="test",
    )


def _or15(
    *,
    status: OpeningRangeFormationStatus = OpeningRangeFormationStatus.COMPLETE,
    low: Decimal | None = Decimal("97.00"),
    high: Decimal | None = Decimal("101.50"),
    instrument_id: str = IID,
    session_date: date = DAY,
    as_of: datetime = EQ_AS_OF,
) -> OpeningRangeEvidence:
    formation = OpeningRangeFormation(
        window=OpeningRangeWindow.OR15,
        range_start=EQ_AS_OF - timedelta(minutes=20), range_end=EQ_AS_OF - timedelta(minutes=5),
        high=high, low=low,
        high_ts=EQ_AS_OF - timedelta(minutes=10) if high is not None else None,
        low_ts=EQ_AS_OF - timedelta(minutes=15) if low is not None else None,
        range_width=(high - low) if (high is not None and low is not None) else None,
        range_width_pct=None, volume=5000, bars_expected=3, bars_present=3,
        status=status, explanation="OR15 test formation",
    )
    return OpeningRangeEvidence(
        instrument_id=instrument_id, session_date=session_date, as_of=as_of, formation=formation,
        relation=OpeningRangeRelation.INSIDE_RANGE, breakout_event=BreakoutEvent.NOT_OBSERVED,
        first_breakout_ts=None, bars_since_breakout=None,
        max_extension_from_range_pct=None, current_extension_pct=None,
        returned_inside_range=None, explanation="OR15 test evidence",
    )


_UNSET = object()


def _evidence(
    *,
    completed_m5_close: Candle | None = None,
    session_vwap: Decimal | None = Decimal("99.00"),
    session_vwap_as_of=_UNSET,
    opening_range_15: OpeningRangeEvidence | None = None,
) -> EntryActionabilityMarketEvidence:
    """By default, ``session_vwap_as_of`` auto-derives to exactly the
    supplied (or default) candle's own completion instant — the coherent
    V0 checkpoint every "happy path" fixture in this file shares. Pass an
    explicit ``session_vwap_as_of`` to deliberately test provenance
    mismatches."""
    if completed_m5_close is None:
        completed_m5_close = _candle()
    if session_vwap_as_of is _UNSET:
        session_vwap_as_of = (
            completed_m5_close.ts_open + timedelta(minutes=5) if session_vwap is not None else None
        )
    return EntryActionabilityMarketEvidence(
        completed_m5_close=completed_m5_close, session_vwap=session_vwap,
        session_vwap_as_of=session_vwap_as_of, opening_range_15=opening_range_15,
    )


def _evaluate(decision, eq, evidence, **kwargs):
    return EntryActionabilityEngine().evaluate(
        decision=decision, entry_qualification=eq, market_evidence=evidence,
        evaluated_at=EVALUATED_AT, **kwargs,
    )


# --------------------------------------------------------------------------- #
# Upstream-gate matrix (item 39)
# --------------------------------------------------------------------------- #


def test_watch_non_qualified_eq_reports_both_upstream_reasons() -> None:
    result = _evaluate(
        _decision(decision_type=DecisionType.WATCH),
        _eq(decision_type=DecisionType.WATCH, state=EntryQualificationState.NOT_YET),
        _evidence(),
    )
    assert result.state is EntryActionabilityState.NOT_ACTIONABLE
    assert result.reason_codes == (
        EntryActionabilityReasonCode.UPSTREAM_DECISION_NOT_TRADE,
        EntryActionabilityReasonCode.UPSTREAM_EQ_NOT_QUALIFIED,
    )
    assert result.entry_reference is None


def test_watch_qualified_eq_reports_decision_gate_only() -> None:
    result = _evaluate(
        _decision(decision_type=DecisionType.WATCH),
        _eq(decision_type=DecisionType.WATCH, state=EntryQualificationState.QUALIFIED),
        _evidence(),
    )
    assert result.state is EntryActionabilityState.NOT_ACTIONABLE
    assert result.reason_codes == (EntryActionabilityReasonCode.UPSTREAM_DECISION_NOT_TRADE,)


@pytest.mark.parametrize(
    "eq_state",
    [
        EntryQualificationState.NOT_YET,
        EntryQualificationState.UNKNOWN,
        EntryQualificationState.EXPIRED,
        EntryQualificationState.OUT_OF_SCOPE,
        EntryQualificationState.DISQUALIFIED_FOR_SESSION,
    ],
)
def test_trade_non_qualified_eq_reports_eq_gate_only(eq_state) -> None:
    result = _evaluate(_decision(), _eq(state=eq_state), _evidence())
    assert result.state is EntryActionabilityState.NOT_ACTIONABLE
    assert result.reason_codes == (EntryActionabilityReasonCode.UPSTREAM_EQ_NOT_QUALIFIED,)


# --------------------------------------------------------------------------- #
# ID-7C.2: upstream short-circuit / evidence-validation order regression
# matrix — layer-3 evidence must be irrelevant to an upstream-ineligible
# candidate's historical methodology verdict, so it must never even be
# inspected for one.
# --------------------------------------------------------------------------- #


def test_binding_mismatch_still_raises_before_any_upstream_verdict() -> None:
    """Exact Decision/EQ identity mismatch remains an unconditional
    contract error, checked before upstream gates are even computed —
    regardless of what the Decision/EQ states would otherwise be."""
    with pytest.raises(ValueError, match="not an exact bound pair"):
        _evaluate(
            _decision(decision_id="decision-1", decision_type=DecisionType.WATCH),
            _eq(decision_id="decision-2"),
            _evidence(),
        )


def test_watch_with_wrong_instrument_m5_is_not_actionable_no_valueerror() -> None:
    wrong_instrument_candle = _candle(instrument_id="NSE:OTHER")
    result = _evaluate(
        _decision(decision_type=DecisionType.WATCH),
        _eq(decision_type=DecisionType.WATCH),
        _evidence(completed_m5_close=wrong_instrument_candle),
    )
    assert result.state is EntryActionabilityState.NOT_ACTIONABLE
    assert result.reason_codes == (EntryActionabilityReasonCode.UPSTREAM_DECISION_NOT_TRADE,)


def test_non_qualified_eq_with_future_m5_is_not_actionable_no_valueerror() -> None:
    forming_candle = _candle(ts_open=EQ_AS_OF - timedelta(minutes=1))
    result = _evaluate(
        _decision(), _eq(state=EntryQualificationState.NOT_YET),
        _evidence(completed_m5_close=forming_candle),
    )
    assert result.state is EntryActionabilityState.NOT_ACTIONABLE
    assert result.reason_codes == (EntryActionabilityReasonCode.UPSTREAM_EQ_NOT_QUALIFIED,)


def test_watch_with_future_checkpoint_relative_vwap_is_not_actionable_no_valueerror() -> None:
    future_vwap_evidence = EntryActionabilityMarketEvidence(
        completed_m5_close=None, session_vwap=Decimal("99"),
        session_vwap_as_of=EQ_AS_OF + timedelta(minutes=1), opening_range_15=None,
    )
    result = _evaluate(
        _decision(decision_type=DecisionType.WATCH),
        _eq(decision_type=DecisionType.WATCH),
        future_vwap_evidence,
    )
    assert result.state is EntryActionabilityState.NOT_ACTIONABLE
    assert result.reason_codes == (EntryActionabilityReasonCode.UPSTREAM_DECISION_NOT_TRADE,)


def test_non_qualified_eq_with_future_or15_is_not_actionable_no_valueerror() -> None:
    future_or15 = _or15(as_of=EQ_AS_OF + timedelta(minutes=1))
    result = _evaluate(
        _decision(), _eq(state=EntryQualificationState.NOT_YET),
        _evidence(opening_range_15=future_or15),
    )
    assert result.state is EntryActionabilityState.NOT_ACTIONABLE
    assert result.reason_codes == (EntryActionabilityReasonCode.UPSTREAM_EQ_NOT_QUALIFIED,)


def test_watch_with_cross_instrument_or15_is_not_actionable_no_valueerror() -> None:
    other_instrument_or15 = _or15(instrument_id="NSE:OTHER")
    result = _evaluate(
        _decision(decision_type=DecisionType.WATCH),
        _eq(decision_type=DecisionType.WATCH),
        _evidence(opening_range_15=other_instrument_or15),
    )
    assert result.state is EntryActionabilityState.NOT_ACTIONABLE
    assert result.reason_codes == (EntryActionabilityReasonCode.UPSTREAM_DECISION_NOT_TRADE,)


def test_eligible_path_still_raises_on_wrong_instrument_m5() -> None:
    wrong_instrument_candle = _candle(instrument_id="NSE:OTHER")
    with pytest.raises(ValueError, match="resolved candidate instrument"):
        _evaluate(_decision(), _eq(), _evidence(completed_m5_close=wrong_instrument_candle))


def test_eligible_path_still_raises_on_future_m5() -> None:
    forming_candle = _candle(ts_open=EQ_AS_OF - timedelta(minutes=1))
    with pytest.raises(ValueError, match="has not actually completed"):
        _evaluate(_decision(), _eq(), _evidence(completed_m5_close=forming_candle))


def test_eligible_path_still_raises_on_future_vwap() -> None:
    future_vwap_evidence = EntryActionabilityMarketEvidence(
        completed_m5_close=None, session_vwap=Decimal("99"),
        session_vwap_as_of=EQ_AS_OF + timedelta(minutes=1), opening_range_15=None,
    )
    with pytest.raises(ValueError, match="later than the.*checkpoint"):
        _evaluate(_decision(), _eq(), future_vwap_evidence)


def test_eligible_path_still_raises_on_incoherent_or15() -> None:
    other_instrument_or15 = _or15(instrument_id="NSE:OTHER")
    with pytest.raises(ValueError, match="resolved candidate instrument"):
        _evaluate(_decision(), _eq(), _evidence(opening_range_15=other_instrument_or15))
    future_or15 = _or15(as_of=EQ_AS_OF + timedelta(minutes=1))
    with pytest.raises(ValueError, match="later than the checkpoint"):
        _evaluate(_decision(), _eq(), _evidence(opening_range_15=future_or15))


def test_trade_qualified_reaches_layer_3() -> None:
    """The only combination that reaches layer-3 evidence handling — proven
    by the fact evidence absence now produces UNKNOWN, not NOT_ACTIONABLE."""
    result = _evaluate(
        _decision(), _eq(),
        EntryActionabilityMarketEvidence(
            completed_m5_close=None, session_vwap=None, session_vwap_as_of=None, opening_range_15=None,
        ),
    )
    assert result.state is EntryActionabilityState.UNKNOWN


def test_not_actionable_carries_no_value_objects_or_evidence_as_of() -> None:
    result = _evaluate(_decision(decision_type=DecisionType.WATCH), _eq(decision_type=DecisionType.WATCH), _evidence())
    assert result.entry_reference is None
    assert result.entry_location_context is None
    assert result.operative_invalidation is None
    assert result.reward is None
    assert result.opening_range_context is None
    assert result.evidence_as_of is None


# --------------------------------------------------------------------------- #
# Layer-3 evidence-failure matrix (item 40)
# --------------------------------------------------------------------------- #


def test_missing_m5_candle_is_unknown_insufficient_evidence() -> None:
    result = _evaluate(
        _decision(), _eq(),
        EntryActionabilityMarketEvidence(
            completed_m5_close=None, session_vwap=Decimal("99"), session_vwap_as_of=EQ_AS_OF,
            opening_range_15=None,
        ),
    )
    assert result.state is EntryActionabilityState.UNKNOWN
    assert result.reason_codes == (EntryActionabilityReasonCode.INSUFFICIENT_EVIDENCE,)
    assert result.evidence_as_of is None


def test_missing_vwap_is_unknown_insufficient_evidence() -> None:
    result = _evaluate(_decision(), _eq(), _evidence(session_vwap=None))
    assert result.state is EntryActionabilityState.UNKNOWN
    assert result.reason_codes == (EntryActionabilityReasonCode.INSUFFICIENT_EVIDENCE,)


def test_invalid_vwap_rejected_by_market_evidence_construction() -> None:
    """Zero/negative VWAP is malformed input, caught at the narrow evidence
    context's own construction time, before the engine ever runs."""
    with pytest.raises(ValueError, match="session_vwap must be positive"):
        EntryActionabilityMarketEvidence(
            completed_m5_close=_candle(), session_vwap=Decimal("0"), session_vwap_as_of=EQ_AS_OF,
            opening_range_15=None,
        )


def test_future_evidence_timestamp_is_a_contract_error() -> None:
    """A completed_m5_close candle that has not actually completed as of the
    checkpoint is a caller contract violation, not a methodology outcome."""
    forming_candle = _candle(ts_open=EQ_AS_OF - timedelta(minutes=1))
    with pytest.raises(ValueError, match="has not actually completed"):
        _evaluate(_decision(), _eq(), _evidence(completed_m5_close=forming_candle))


# --------------------------------------------------------------------------- #
# ID-7C.1: VWAP market-time provenance matrix (item 10)
# --------------------------------------------------------------------------- #


def test_vwap_price_present_as_of_absent_is_malformed_input() -> None:
    with pytest.raises(ValueError, match="must both be present or both be None"):
        EntryActionabilityMarketEvidence(
            completed_m5_close=_candle(), session_vwap=Decimal("99"), session_vwap_as_of=None,
            opening_range_15=None,
        )


def test_vwap_absent_as_of_present_is_malformed_input() -> None:
    with pytest.raises(ValueError, match="must both be present or both be None"):
        EntryActionabilityMarketEvidence(
            completed_m5_close=_candle(), session_vwap=None, session_vwap_as_of=EQ_AS_OF,
            opening_range_15=None,
        )


def test_naive_vwap_as_of_rejected() -> None:
    with pytest.raises(ValueError, match="session_vwap_as_of must be timezone-aware"):
        EntryActionabilityMarketEvidence(
            completed_m5_close=_candle(), session_vwap=Decimal("99"),
            session_vwap_as_of=datetime(2026, 9, 4, 9, 50), opening_range_15=None,
        )


def test_vwap_as_of_later_than_m5_completion_rejected() -> None:
    """M5 completes at EQ_AS_OF (ts_open=EQ_AS_OF-5min); VWAP as_of 2
    minutes later than that is a stale-M5/fresher-VWAP mismatch — still
    <= the checkpoint, so this proves the PIT-coherence check fires
    independently of the future-relative-to-checkpoint check."""
    with pytest.raises(ValueError, match="must equal completed_m5_close's own completion instant"):
        EntryActionabilityMarketEvidence(
            completed_m5_close=_candle(ts_open=EQ_AS_OF - timedelta(minutes=10)),
            session_vwap=Decimal("99"), session_vwap_as_of=EQ_AS_OF - timedelta(minutes=3),
            opening_range_15=None,
        )


def test_vwap_as_of_earlier_than_m5_completion_rejected() -> None:
    with pytest.raises(ValueError, match="must equal completed_m5_close's own completion instant"):
        EntryActionabilityMarketEvidence(
            completed_m5_close=_candle(ts_open=EQ_AS_OF - timedelta(minutes=5)),
            session_vwap=Decimal("99"), session_vwap_as_of=EQ_AS_OF - timedelta(minutes=1),
            opening_range_15=None,
        )


def test_vwap_as_of_equal_to_m5_completion_is_valid() -> None:
    ev = EntryActionabilityMarketEvidence(
        completed_m5_close=_candle(ts_open=EQ_AS_OF - timedelta(minutes=5)),
        session_vwap=Decimal("99"), session_vwap_as_of=EQ_AS_OF, opening_range_15=None,
    )
    result = _evaluate(_decision(), _eq(), ev)
    assert result.state is EntryActionabilityState.ACTIONABLE
    assert result.evidence_as_of == EQ_AS_OF


def test_vwap_as_of_later_than_checkpoint_rejected_when_no_m5_supplied() -> None:
    """No M5 candle is supplied (so the PIT-coherence check cannot itself
    fire), isolating the general future-relative-to-checkpoint check."""
    future_vwap_as_of = EQ_AS_OF + timedelta(minutes=1)
    ev = EntryActionabilityMarketEvidence(
        completed_m5_close=None, session_vwap=Decimal("99"), session_vwap_as_of=future_vwap_as_of,
        opening_range_15=None,
    )
    with pytest.raises(ValueError, match="later than the.*checkpoint"):
        _evaluate(_decision(), _eq(), ev)


def test_no_future_or_stale_vwap_can_produce_actionable() -> None:
    """Composite proof: every mismatched-provenance case above either
    raises at construction or at evaluation -- none of them can ever
    reach ACTIONABLE."""
    mismatched_pairs = [
        (EQ_AS_OF - timedelta(minutes=10), EQ_AS_OF - timedelta(minutes=3)),  # stale M5, fresher VWAP
        (EQ_AS_OF - timedelta(minutes=5), EQ_AS_OF - timedelta(minutes=1)),  # VWAP earlier than M5
    ]
    for m5_ts_open, vwap_as_of in mismatched_pairs:
        with pytest.raises(ValueError):
            EntryActionabilityMarketEvidence(
                completed_m5_close=_candle(ts_open=m5_ts_open), session_vwap=Decimal("99"),
                session_vwap_as_of=vwap_as_of, opening_range_15=None,
            )


def test_zero_risk_geometry_is_unknown_invalidation_unavailable() -> None:
    """entry == VWAP: geometrically invalid, mapped deterministically to
    UNKNOWN, never a raised domain ValueError escaping the engine."""
    result = _evaluate(
        _decision(direction=Direction.LONG), _eq(),
        _evidence(completed_m5_close=_candle(close=Decimal("100")), session_vwap=Decimal("100")),
    )
    assert result.state is EntryActionabilityState.UNKNOWN
    assert result.reason_codes == (EntryActionabilityReasonCode.INVALIDATION_UNAVAILABLE,)
    assert result.entry_reference is None
    assert result.evidence_as_of is not None  # evidence WAS available; only geometry failed


def test_wrong_side_long_geometry_is_unknown_invalidation_unavailable() -> None:
    """LONG requires VWAP < entry; VWAP above entry is wrong-side."""
    result = _evaluate(
        _decision(direction=Direction.LONG), _eq(),
        _evidence(completed_m5_close=_candle(close=Decimal("100")), session_vwap=Decimal("101")),
    )
    assert result.state is EntryActionabilityState.UNKNOWN
    assert result.reason_codes == (EntryActionabilityReasonCode.INVALIDATION_UNAVAILABLE,)


def test_wrong_side_short_geometry_is_unknown_invalidation_unavailable() -> None:
    """SHORT requires VWAP > entry; VWAP below entry is wrong-side."""
    result = _evaluate(
        _decision(direction=Direction.SHORT), _eq(),
        _evidence(completed_m5_close=_candle(close=Decimal("100")), session_vwap=Decimal("99")),
    )
    assert result.state is EntryActionabilityState.UNKNOWN
    assert result.reason_codes == (EntryActionabilityReasonCode.INVALIDATION_UNAVAILABLE,)


def test_valid_long_is_actionable() -> None:
    result = _evaluate(
        _decision(direction=Direction.LONG), _eq(),
        _evidence(completed_m5_close=_candle(close=Decimal("100")), session_vwap=Decimal("99")),
    )
    assert result.state is EntryActionabilityState.ACTIONABLE
    assert result.direction is Direction.LONG


def test_structural_short_is_actionable() -> None:
    """SHORT is structurally supported (direction-symmetric formulas) but
    NOT empirically validated (LONG_VALIDATED_SHORT_UNVALIDATED, ID-7B.2)
    — this test proves structural support only, never a calibration claim."""
    result = _evaluate(
        _decision(direction=Direction.SHORT), _eq(),
        _evidence(completed_m5_close=_candle(close=Decimal("100")), session_vwap=Decimal("101")),
    )
    assert result.state is EntryActionabilityState.ACTIONABLE
    assert result.direction is Direction.SHORT
    assert result.operative_invalidation.level == Decimal("101")


# --------------------------------------------------------------------------- #
# Entry reference / VWAP deviation (items 11-14)
# --------------------------------------------------------------------------- #


def test_entry_reference_is_completed_m5_close_price_only() -> None:
    result = _evaluate(
        _decision(), _eq(),
        _evidence(completed_m5_close=_candle(close=Decimal("123.45")), session_vwap=Decimal("120")),
    )
    assert result.entry_reference.price == Decimal("123.45")


def test_vwap_deviation_formula_is_signed_percentage_not_absolute() -> None:
    """(entry - vwap) / vwap * 100 — matches indicators.calculations.vwap's
    own formula exactly. Positive above VWAP, negative below — never
    absolute-valued."""
    above = _evaluate(
        _decision(direction=Direction.LONG), _eq(),
        _evidence(completed_m5_close=_candle(close=Decimal("110")), session_vwap=Decimal("100")),
    )
    assert above.entry_location_context.vwap_deviation_pct == Decimal("10")

    below = _evaluate(
        _decision(direction=Direction.SHORT), _eq(),
        _evidence(completed_m5_close=_candle(close=Decimal("90")), session_vwap=Decimal("100")),
    )
    assert below.entry_location_context.vwap_deviation_pct == Decimal("-10")


def test_vwap_deviation_not_rounded() -> None:
    result = _evaluate(
        _decision(), _eq(),
        _evidence(completed_m5_close=_candle(close=Decimal("100")), session_vwap=Decimal("99")),
    )
    # (100 - 99) / 99 * 100 -- exact Decimal division, not rounded to 2dp.
    expected = (Decimal("100") - Decimal("99")) / Decimal("99") * Decimal(100)
    assert result.entry_location_context.vwap_deviation_pct == expected


def test_evidence_as_of_is_candle_completion_instant() -> None:
    ts_open = EQ_AS_OF - timedelta(minutes=5)
    result = _evaluate(_decision(), _eq(), _evidence(completed_m5_close=_candle(ts_open=ts_open)))
    assert result.evidence_as_of == ts_open + timedelta(minutes=5)


def test_evidence_as_of_never_later_than_entry_actionability_as_of() -> None:
    """Domain invariant sanity: the produced artifact must pass
    EntryActionability.__post_init__'s own PIT ordering check naturally."""
    result = _evaluate(_decision(), _eq(), _evidence())
    assert result.evidence_as_of <= result.entry_actionability_as_of


# --------------------------------------------------------------------------- #
# ID-7C.1: OR15 binding/PIT coherence matrix (item 17)
# --------------------------------------------------------------------------- #


def test_or15_other_instrument_raises() -> None:
    other_instrument_or15 = _or15(instrument_id="NSE:OTHER")
    with pytest.raises(ValueError, match="resolved candidate instrument"):
        _evaluate(_decision(), _eq(), _evidence(opening_range_15=other_instrument_or15))


def test_or15_other_session_raises() -> None:
    other_session_or15 = _or15(session_date=date(2026, 9, 3))
    with pytest.raises(ValueError, match="EntryQualification's session"):
        _evaluate(_decision(), _eq(), _evidence(opening_range_15=other_session_or15))


def test_or15_future_as_of_raises() -> None:
    future_or15 = _or15(as_of=EQ_AS_OF + timedelta(minutes=1))
    with pytest.raises(ValueError, match="later than the checkpoint"):
        _evaluate(_decision(), _eq(), _evidence(opening_range_15=future_or15))


def test_or15_coherent_complete_attaches_context() -> None:
    result = _evaluate(_decision(), _eq(), _evidence(opening_range_15=_or15()))
    assert result.opening_range_context is not None


def test_or15_coherent_non_complete_attaches_no_context() -> None:
    result = _evaluate(
        _decision(), _eq(),
        _evidence(opening_range_15=_or15(status=OpeningRangeFormationStatus.FORMING)),
    )
    assert result.opening_range_context is None


def test_or15_coherent_absent_attaches_no_context() -> None:
    result = _evaluate(_decision(), _eq(), _evidence(opening_range_15=None))
    assert result.opening_range_context is None


def test_or15_coherence_check_leaves_invalidation_and_rr_unchanged() -> None:
    with_coherent_or15 = _evaluate(_decision(), _eq(), _evidence(opening_range_15=_or15()))
    without_or15 = _evaluate(_decision(), _eq(), _evidence(opening_range_15=None))
    assert with_coherent_or15.operative_invalidation == without_or15.operative_invalidation
    assert with_coherent_or15.reward == without_or15.reward


# --------------------------------------------------------------------------- #
# OR15 contextual handling (items 21-22, 41)
# --------------------------------------------------------------------------- #


def test_or15_complete_attaches_long_boundary_as_range_low() -> None:
    result = _evaluate(
        _decision(direction=Direction.LONG), _eq(),
        _evidence(
            completed_m5_close=_candle(close=Decimal("100")), session_vwap=Decimal("99"),
            opening_range_15=_or15(low=Decimal("97.00"), high=Decimal("101.50")),
        ),
    )
    assert result.opening_range_context is not None
    assert result.opening_range_context.level == Decimal("97.00")


def test_or15_complete_attaches_short_boundary_as_range_high() -> None:
    result = _evaluate(
        _decision(direction=Direction.SHORT), _eq(),
        _evidence(
            completed_m5_close=_candle(close=Decimal("100")), session_vwap=Decimal("101"),
            opening_range_15=_or15(low=Decimal("97.00"), high=Decimal("101.50")),
        ),
    )
    assert result.opening_range_context is not None
    assert result.opening_range_context.level == Decimal("101.50")


@pytest.mark.parametrize(
    "status",
    [
        OpeningRangeFormationStatus.FORMING,
        OpeningRangeFormationStatus.INCOMPLETE_DATA,
        OpeningRangeFormationStatus.NOT_AVAILABLE,
        OpeningRangeFormationStatus.NOT_APPLICABLE,
    ],
)
def test_or15_non_complete_status_is_absent_context(status) -> None:
    result = _evaluate(
        _decision(), _eq(),
        _evidence(
            completed_m5_close=_candle(close=Decimal("100")), session_vwap=Decimal("99"),
            opening_range_15=_or15(status=status),
        ),
    )
    assert result.state is EntryActionabilityState.ACTIONABLE
    assert result.opening_range_context is None


def test_or15_missing_is_absent_context_and_still_actionable() -> None:
    result = _evaluate(_decision(), _eq(), _evidence(opening_range_15=None))
    assert result.state is EntryActionabilityState.ACTIONABLE
    assert result.opening_range_context is None


def test_or15_absence_never_forces_unknown() -> None:
    with_or = _evaluate(_decision(), _eq(), _evidence(opening_range_15=_or15()))
    without_or = _evaluate(_decision(), _eq(), _evidence(opening_range_15=None))
    assert with_or.state is without_or.state is EntryActionabilityState.ACTIONABLE


def test_or15_never_changes_operative_invalidation_or_reward() -> None:
    with_or = _evaluate(_decision(), _eq(), _evidence(opening_range_15=_or15()))
    without_or = _evaluate(_decision(), _eq(), _evidence(opening_range_15=None))
    assert with_or.operative_invalidation == without_or.operative_invalidation
    assert with_or.reward == without_or.reward


# --------------------------------------------------------------------------- #
# Reward/RR Decimal tests (items 23-24, 42)
# --------------------------------------------------------------------------- #


def test_long_t1_t2_exact_decimal() -> None:
    result = _evaluate(
        _decision(direction=Direction.LONG), _eq(),
        _evidence(completed_m5_close=_candle(close=Decimal("100")), session_vwap=Decimal("98")),
    )
    assert result.reward.t1_price == Decimal("100") * (Decimal(1) + Decimal("0.01"))
    assert result.reward.t2_price == Decimal("100") * (Decimal(1) + Decimal("0.015"))


def test_short_t1_t2_exact_decimal() -> None:
    result = _evaluate(
        _decision(direction=Direction.SHORT), _eq(),
        _evidence(completed_m5_close=_candle(close=Decimal("100")), session_vwap=Decimal("102")),
    )
    assert result.reward.t1_price == Decimal("100") * (Decimal(1) - Decimal("0.01"))
    assert result.reward.t2_price == Decimal("100") * (Decimal(1) - Decimal("0.015"))


def test_risk_distance_and_rr_exact_decimal() -> None:
    result = _evaluate(
        _decision(direction=Direction.LONG), _eq(),
        _evidence(completed_m5_close=_candle(close=Decimal("100")), session_vwap=Decimal("98")),
    )
    risk_distance = Decimal("100") - Decimal("98")
    t1 = Decimal("100") * (Decimal(1) + Decimal("0.01"))
    t2 = Decimal("100") * (Decimal(1) + Decimal("0.015"))
    assert result.reward.reward_risk_to_t1 == (t1 - Decimal("100")) / risk_distance
    assert result.reward.reward_risk_to_t2 == (t2 - Decimal("100")) / risk_distance


def test_rr_is_informational_only_never_gates() -> None:
    """A very small RR must still be ACTIONABLE -- no minimum-RR gate."""
    result = _evaluate(
        _decision(direction=Direction.LONG), _eq(),
        _evidence(completed_m5_close=_candle(close=Decimal("100")), session_vwap=Decimal("0.01")),
    )
    assert result.state is EntryActionabilityState.ACTIONABLE
    assert result.reward.reward_risk_to_t1 is not None


# --------------------------------------------------------------------------- #
# Evidence-finality propagation (items 26, 34, 43)
# --------------------------------------------------------------------------- #


@pytest.mark.parametrize(
    "finality",
    [
        EntryEvidenceFinality.LIVE_M5_PROVISIONAL,
        EntryEvidenceFinality.UNKNOWN_PROVENANCE,
        EntryEvidenceFinality.NO_DECISIVE_PROVISIONAL_M5_DEPENDENCY,
    ],
)
def test_evidence_finality_echoed_exactly_regardless_of_state(finality) -> None:
    eq_actionable = dataclasses.replace(_eq(), evidence_finality=finality)
    eq_not_actionable = dataclasses.replace(
        _eq(decision_type=DecisionType.WATCH), evidence_finality=finality
    )
    actionable = _evaluate(_decision(), eq_actionable, _evidence())
    not_actionable = _evaluate(
        _decision(decision_type=DecisionType.WATCH), eq_not_actionable, _evidence()
    )
    assert actionable.evidence_finality is finality
    assert not_actionable.evidence_finality is finality


def test_provisional_finality_does_not_alone_prevent_actionable() -> None:
    """ID-7B explicitly allowed provisional evidence to remain usable where
    completed-M5 methodology evidence is satisfied -- finality is
    dimension C, not a methodology gate."""
    eq = dataclasses.replace(_eq(), evidence_finality=EntryEvidenceFinality.LIVE_M5_PROVISIONAL)
    result = _evaluate(_decision(), eq, _evidence())
    assert result.state is EntryActionabilityState.ACTIONABLE
    assert result.evidence_finality is EntryEvidenceFinality.LIVE_M5_PROVISIONAL


# --------------------------------------------------------------------------- #
# Determinism (item 45)
# --------------------------------------------------------------------------- #


def test_determinism_identical_inputs_identical_output_except_evaluated_at() -> None:
    decision, eq, evidence = _decision(), _eq(), _evidence()
    first = _evaluate(decision, eq, evidence)
    later = EntryActionabilityEngine().evaluate(
        decision=decision, entry_qualification=eq, market_evidence=evidence,
        evaluated_at=EVALUATED_AT + timedelta(seconds=5),
    )
    assert dataclasses.replace(first, evaluated_at=later.evaluated_at) == later


def test_determinism_actionable_full_equality_with_same_evaluated_at() -> None:
    decision, eq, evidence = _decision(), _eq(), _evidence()
    first = _evaluate(decision, eq, evidence)
    second = _evaluate(decision, eq, evidence)
    assert first == second


# --------------------------------------------------------------------------- #
# Exact upstream identity/audit-field propagation (item 27)
# --------------------------------------------------------------------------- #


def test_identity_and_audit_fields_copied_exactly() -> None:
    decision = _decision(instrument_id=IID, run_id="run-9", cycle_id="cycle-9")
    eq = _eq(as_of=EQ_AS_OF, methodology_version=EQ_DEFAULT_METHODOLOGY_VERSION, run_id="run-9", cycle_id="cycle-9")
    result = _evaluate(decision, eq, _evidence())
    assert result.instrument_id == IID
    assert result.session_date == DAY
    assert result.entry_qualification_as_of == EQ_AS_OF
    assert result.decision_id == "decision-1"
    assert result.entry_qualification_methodology_version == EQ_DEFAULT_METHODOLOGY_VERSION
    assert result.decision_type is DecisionType.TRADE
    assert result.direction is Direction.LONG
    assert result.entry_qualification_state is EntryQualificationState.QUALIFIED
    assert result.run_id == "run-9"
    assert result.cycle_id == "cycle-9"
    assert result.entry_actionability_methodology_version == EA_DEFAULT_METHODOLOGY_VERSION
    assert result.entry_actionability_as_of == EQ_AS_OF  # Option 1: same checkpoint as EQ


def test_default_methodology_version_is_the_frozen_constant() -> None:
    result = _evaluate(_decision(), _eq(), _evidence())
    assert result.entry_actionability_methodology_version == "entry-actionability-v0"


def test_policy_has_no_methodology_version_field() -> None:
    """ID-7C.1: methodology identity can no longer be caller-relabeled —
    the field was removed entirely, not merely defaulted."""
    with pytest.raises(TypeError):
        EntryActionabilityPolicy(methodology_version="entry-actionability-v0-experimental")


def test_policy_with_only_config_snapshot_id_does_not_change_methodology_version() -> None:
    policy = EntryActionabilityPolicy(config_snapshot_id="cfg-1")
    result = _evaluate(_decision(), _eq(), _evidence(), policy=policy)
    assert result.entry_actionability_methodology_version == EA_DEFAULT_METHODOLOGY_VERSION


def test_identical_v0_behavior_cannot_emit_a_different_methodology_identity() -> None:
    """Proves the spoofing gap is closed structurally: there is no input
    path through which identical V0 evaluation logic can produce an
    artifact claiming a different methodology_version."""
    default_result = _evaluate(_decision(), _eq(), _evidence())
    with_metadata_result = _evaluate(
        _decision(), _eq(), _evidence(), policy=EntryActionabilityPolicy(config_snapshot_id="cfg-1")
    )
    assert (
        default_result.entry_actionability_methodology_version
        == with_metadata_result.entry_actionability_methodology_version
        == EA_DEFAULT_METHODOLOGY_VERSION
    )


# --------------------------------------------------------------------------- #
# Exact Decision/EQ binding validation (contract errors, item 4)
# --------------------------------------------------------------------------- #


def test_mismatched_decision_id_raises() -> None:
    with pytest.raises(ValueError, match="not an exact bound pair"):
        _evaluate(_decision(decision_id="decision-1"), _eq(decision_id="decision-2"), _evidence())


def test_mismatched_decision_type_raises() -> None:
    decision = _decision(decision_type=DecisionType.WATCH)
    eq = _eq(decision_type=DecisionType.TRADE)  # eq claims TRADE, decision says WATCH
    with pytest.raises(ValueError, match="disagreeing decision_type"):
        _evaluate(decision, eq, _evidence())


def test_mismatched_run_id_raises() -> None:
    with pytest.raises(ValueError, match="disagreeing run_id"):
        _evaluate(_decision(run_id="run-1"), _eq(run_id="run-2"), _evidence())


def test_mismatched_cycle_id_raises() -> None:
    with pytest.raises(ValueError, match="disagreeing cycle_id"):
        _evaluate(_decision(cycle_id="cycle-1"), _eq(cycle_id="cycle-2"), _evidence())


def test_mismatched_instrument_id_raises() -> None:
    with pytest.raises(ValueError, match="two different instruments"):
        _evaluate(_decision(instrument_id="NSE:AAA"), _eq(instrument_id="NSE:BBB"), _evidence())


def test_decision_instrument_id_none_falls_back_to_eq_instrument_id() -> None:
    """Mirrors EntryQualificationEngine's own established fallback."""
    result = _evaluate(_decision(instrument_id=None), _eq(instrument_id=IID), _evidence())
    assert result.instrument_id == IID


def test_mismatched_candle_instrument_id_raises() -> None:
    wrong_candle = _candle(instrument_id="NSE:OTHER")
    with pytest.raises(ValueError, match="resolved candidate instrument"):
        _evaluate(_decision(), _eq(), _evidence(completed_m5_close=wrong_candle))


def test_non_m5_candle_rejected_by_market_evidence_construction() -> None:
    wrong_timeframe_candle = _candle(timeframe=Timeframe.M15)
    with pytest.raises(ValueError, match="must be an M5 candle"):
        EntryActionabilityMarketEvidence(
            completed_m5_close=wrong_timeframe_candle, session_vwap=Decimal("99"),
            session_vwap_as_of=EQ_AS_OF, opening_range_15=None,
        )


def test_non_or15_window_rejected_by_market_evidence_construction() -> None:
    or30_like = dataclasses.replace(
        _or15(), formation=dataclasses.replace(_or15().formation, window=OpeningRangeWindow.OR30)
    )
    with pytest.raises(ValueError, match="must be an OR15 window"):
        EntryActionabilityMarketEvidence(
            completed_m5_close=_candle(), session_vwap=Decimal("99"), session_vwap_as_of=EQ_AS_OF,
            opening_range_15=or30_like,
        )


def test_naive_evaluated_at_rejected() -> None:
    with pytest.raises(ValueError, match="evaluated_at must be timezone-aware"):
        EntryActionabilityEngine().evaluate(
            decision=_decision(), entry_qualification=_eq(), market_evidence=_evidence(),
            evaluated_at=datetime(2026, 9, 4, 9, 51),
        )


# --------------------------------------------------------------------------- #
# Domain-compatibility proof (item 51/44)
# --------------------------------------------------------------------------- #


def test_every_engine_output_passes_domain_construction_naturally() -> None:
    """Already implicitly proven by every other test (the engine
    constructs a real EntryActionability, which would itself raise if
    illegal) -- this test makes the intent explicit across every distinct
    branch the engine can take."""
    cases = [
        _evaluate(_decision(decision_type=DecisionType.WATCH), _eq(decision_type=DecisionType.WATCH), _evidence()),
        _evaluate(_decision(), _eq(state=EntryQualificationState.NOT_YET), _evidence()),
        _evaluate(
            _decision(), _eq(),
            EntryActionabilityMarketEvidence(
                completed_m5_close=None, session_vwap=None, session_vwap_as_of=None, opening_range_15=None,
            ),
        ),
        _evaluate(
            _decision(direction=Direction.LONG), _eq(),
            _evidence(completed_m5_close=_candle(close=Decimal("100")), session_vwap=Decimal("101")),
        ),
        _evaluate(_decision(direction=Direction.LONG), _eq(), _evidence()),
        _evaluate(_decision(direction=Direction.SHORT), _eq(), _evidence(session_vwap=Decimal("101"))),
    ]
    states = {c.state for c in cases}
    assert states == {
        EntryActionabilityState.NOT_ACTIONABLE,
        EntryActionabilityState.UNKNOWN,
        EntryActionabilityState.ACTIONABLE,
    }


# --------------------------------------------------------------------------- #
# Currentness / session-gate / persistence / latest-lookup / provider absence
# proofs (items 39-43 of the currentness family; ID-7C authorization items
# 30-34)
# --------------------------------------------------------------------------- #


def test_no_currentness_or_session_gate_logic_inside_engine() -> None:
    import inspect

    source = inspect.getsource(EntryActionabilityEngine)
    forbidden = (
        "is_currently_usable", "SESSION_CLOSED", "SessionPhase", "session_phase",
        "SESSION_NOT_ACTIONABLE", "current_decision_id",
    )
    for term in forbidden:
        assert term not in source


def test_no_persistence_or_latest_lookup_or_provider_call() -> None:
    """Scoped to the engine class's own source (not the module docstring,
    which legitimately discusses these absent concerns by name)."""
    import inspect

    class_source = inspect.getsource(EntryActionabilityEngine)
    for term in (
        "save_entry_actionability", "SqliteRepository", "evaluate_latest",
        "evaluate_for_symbol", "load_current_decision", "load_latest_eq", "WorkflowStage",
    ):
        assert term not in class_source
    lowered = class_source.lower()
    for term in ("kite", "zerodha", "requests.", "httpx."):
        assert term not in lowered
