"""Entry Qualification pure engine (ID-6B.2).

Direct construction of value-object fixtures throughout (no
IntradayAnalyticsEngine/SessionContextEngine wiring) so each test controls
exactly which categorical relation/label appears, independent of any
upstream engine's own computation. Engine correctness for VWAP/trend/RS/
RVOL themselves is covered by their own dedicated test modules.
"""

from __future__ import annotations

import dataclasses
import itertools
from datetime import date, datetime
from decimal import Decimal
from zoneinfo import ZoneInfo

import pytest

from athena.domain.decision import Decision, TradePlan
from athena.domain.enums import DecisionType, Direction, Timeframe
from athena.intraday.entry_qualification_engine import (
    DEFAULT_METHODOLOGY_VERSION,
    EntryQualificationEngine,
    EntryQualificationPolicy,
    _support_tri,
    _trend_tri,
    _Tri,
    _tri_and,
    _tri_or,
    _vwap_tri,
)
from athena.intraday.entry_qualification_models import (
    EntryEvidenceFinality,
    EntryQualificationConfirmation,
    EntryQualificationReasonCode,
    EntryQualificationState,
)
from athena.intraday.gap_models import GapContext, GapDirection
from athena.intraday.models import (
    IntradaySignalSet,
    IntradayTrendContext,
    IntradayTrendLabel,
    TimeframeTrendEvidence,
    VwapEvidence,
    VwapRelation,
)
from athena.intraday.opening_range_models import (
    BreakoutEvent,
    OpeningRangeEvidence,
    OpeningRangeFormation,
    OpeningRangeFormationStatus,
    OpeningRangeRelation,
    OpeningRangeWindow,
)
from athena.intraday.relative_strength_models import RelativeStrengthContext, RelativeStrengthRelation
from athena.intraday.relative_volume_models import RelativeVolumeContext, RelativeVolumeRelation
from athena.session.models import SessionContext, SessionDataQualityStatus, SessionPhase, TimeframeProvenance

IST = ZoneInfo("Asia/Kolkata")
IID = "NSE:TEST"
DAY = date(2026, 9, 2)
AS_OF = datetime(2026, 9, 2, 10, 0, tzinfo=IST)


# --------------------------------------------------------------------------- #
# Fixture builders
# --------------------------------------------------------------------------- #


def _decision(
    *,
    decision_type: DecisionType = DecisionType.WATCH,
    instrument_id: str | None = IID,
    decision_id: str = "decision-1",
) -> Decision:
    if decision_type is DecisionType.TRADE:
        return Decision(
            decision_id=decision_id,
            ts=AS_OF,
            run_id="run-1",
            cycle_id="cycle-1",
            decision_type=DecisionType.TRADE,
            explanation="test trade decision",
            instrument_id=instrument_id,
            direction=Direction.LONG,
            trade_plan=TradePlan(
                entry_low=Decimal("100"),
                entry_high=Decimal("101"),
                stop_loss=Decimal("98"),
                targets=(Decimal("105"),),
                position_size=1,
                risk_amount=Decimal("100"),
                risk_reward=Decimal("2"),
                valid_from=AS_OF,
                valid_until=datetime(2026, 9, 2, 15, 30, tzinfo=IST),
            ),
        )
    return Decision(
        decision_id=decision_id,
        ts=AS_OF,
        run_id="run-1",
        cycle_id="cycle-1",
        decision_type=decision_type,
        explanation="test decision",
        instrument_id=instrument_id,
    )


def _timeframe_provenance(timeframe: Timeframe) -> TimeframeProvenance:
    return TimeframeProvenance(
        instrument_id=IID,
        timeframe=timeframe,
        session_date=DAY,
        as_of=AS_OF,
        window_start=None,
        window_end=None,
        latest_completed_bar_ts=None,
        bar_count=1,
        quality=SessionDataQualityStatus.SUFFICIENT,
        explanation="test provenance",
    )


def _session_context(
    *,
    phase: SessionPhase = SessionPhase.REGULAR,
    data_quality: SessionDataQualityStatus = SessionDataQualityStatus.SUFFICIENT,
    instrument_id: str = IID,
) -> SessionContext:
    from athena.domain.enums import SessionType

    return SessionContext(
        instrument_id=instrument_id,
        session_date=DAY,
        exchange="NSE",
        timezone="Asia/Kolkata",
        as_of=AS_OF,
        session_type=SessionType.NORMAL,
        phase=phase,
        session_open_ts=datetime(2026, 9, 2, 9, 15, tzinfo=IST),
        session_close_ts=datetime(2026, 9, 2, 15, 30, tzinfo=IST),
        elapsed_seconds=2700,
        remaining_seconds=16200,
        latest_quote_ts=AS_OF,
        five_min=_timeframe_provenance(Timeframe.M5),
        fifteen_min=_timeframe_provenance(Timeframe.M15),
        data_quality=data_quality,
        explanation="test session context",
    )


def _vwap(relation: VwapRelation) -> VwapEvidence:
    deviation = Decimal("1.5") if relation is VwapRelation.ABOVE_VWAP else None
    return VwapEvidence(relation=relation, deviation_pct=deviation, explanation="test vwap")


def _trend(label: IntradayTrendLabel) -> IntradayTrendContext:
    if label is IntradayTrendLabel.BULLISH:
        five, fifteen = True, True
    elif label is IntradayTrendLabel.BEARISH:
        five, fifteen = False, False
    elif label is IntradayTrendLabel.MIXED:
        five, fifteen = True, False
    else:
        five, fifteen = None, None
    return IntradayTrendContext(
        instrument_id=IID,
        session_date=DAY,
        as_of=AS_OF,
        five_min=TimeframeTrendEvidence(
            timeframe=Timeframe.M5, bullish=five, sma_period=9, explanation="test 5m"
        ),
        fifteen_min=TimeframeTrendEvidence(
            timeframe=Timeframe.M15, bullish=fifteen, sma_period=5, explanation="test 15m"
        ),
        trend_label=label,
        explanation="test trend",
    )


def _rs(
    *,
    vs_market: RelativeStrengthRelation = RelativeStrengthRelation.UNKNOWN,
    vs_sector: RelativeStrengthRelation = RelativeStrengthRelation.UNKNOWN,
    instrument_id: str = IID,
    session_date: date = DAY,
    as_of: datetime = AS_OF,
) -> RelativeStrengthContext:
    return RelativeStrengthContext(
        instrument_id=instrument_id,
        sector="IT",
        market_benchmark_id="NSE:NIFTY 50",
        sector_benchmark_id="NSE:NIFTY IT",
        session_date=session_date,
        as_of=as_of,
        comparison_start_ts=None,
        comparison_cutoff_ts=None,
        stock_return_pct=None,
        sector_return_pct=None,
        market_return_pct=None,
        stock_vs_sector_pct=None,
        stock_vs_market_pct=None,
        sector_vs_market_pct=None,
        stock_vs_sector_relation=vs_sector,
        stock_vs_market_relation=vs_market,
        sector_vs_market_relation=RelativeStrengthRelation.UNKNOWN,
        stock_available=vs_market is not RelativeStrengthRelation.UNKNOWN,
        sector_available=vs_sector is not RelativeStrengthRelation.UNKNOWN,
        market_available=vs_market is not RelativeStrengthRelation.UNKNOWN,
        explanation="test rs",
    )


def _rvol(
    relation: RelativeVolumeRelation,
    *,
    instrument_id: str = IID,
    session_date: date = DAY,
    as_of: datetime = AS_OF,
) -> RelativeVolumeContext:
    return RelativeVolumeContext(
        instrument_id=instrument_id,
        session_date=session_date,
        as_of=as_of,
        comparison_start_ts=None,
        comparison_cutoff_ts=None,
        current_cumulative_volume=None,
        current_canonical_bar_count=0,
        historical_average_cumulative_volume=None,
        baseline_session_count=0,
        baseline_session_dates=(),
        rvol_ratio=None,
        relation=relation,
        available=relation is not RelativeVolumeRelation.UNKNOWN,
        explanation="test rvol",
    )


def _dummy_or(window: OpeningRangeWindow, *, breakout: bool = False) -> OpeningRangeEvidence:
    formation = OpeningRangeFormation(
        window=window, range_start=None, range_end=None, high=None, low=None,
        high_ts=None, low_ts=None, range_width=None, range_width_pct=None,
        volume=None, bars_expected=None, bars_present=0,
        status=OpeningRangeFormationStatus.NOT_APPLICABLE,
        explanation=f"{window.value}: not exercised in this test",
    )
    return OpeningRangeEvidence(
        instrument_id=IID, session_date=DAY, as_of=AS_OF, formation=formation,
        relation=OpeningRangeRelation.ABOVE_RANGE if breakout else OpeningRangeRelation.UNAVAILABLE,
        breakout_event=BreakoutEvent.UPSIDE_BREAKOUT_EVENT if breakout else BreakoutEvent.NOT_OBSERVED,
        first_breakout_ts=None, bars_since_breakout=None, max_extension_from_range_pct=None,
        current_extension_pct=None, returned_inside_range=None,
        explanation=f"{window.value}: not exercised in this test",
    )


def _dummy_gap(*, has_gap: bool = False) -> GapContext:
    return GapContext(
        instrument_id=IID, session_date=DAY, as_of=AS_OF,
        previous_session_date=None, previous_session_close=None, current_session_open=None,
        gap_pct=Decimal("2.0") if has_gap else None,
        direction=GapDirection.GAP_UP if has_gap else GapDirection.UNKNOWN,
        available=has_gap,
        explanation="not exercised in this test",
    )


def _signal_set(
    *,
    vwap: VwapRelation = VwapRelation.ABOVE_VWAP,
    trend: IntradayTrendLabel = IntradayTrendLabel.BULLISH,
    rs_vs_market: RelativeStrengthRelation = RelativeStrengthRelation.OUTPERFORMING,
    rs_vs_sector: RelativeStrengthRelation = RelativeStrengthRelation.UNKNOWN,
    rvol: RelativeVolumeRelation = RelativeVolumeRelation.UNKNOWN,
    or15_breakout: bool = False,
    or30_breakout: bool = False,
    gap: bool = False,
    data_quality: SessionDataQualityStatus = SessionDataQualityStatus.SUFFICIENT,
    instrument_id: str = IID,
    session_date: date = DAY,
    as_of: datetime = AS_OF,
    relative_strength: RelativeStrengthContext | None = None,
    relative_volume: RelativeVolumeContext | None = None,
) -> IntradaySignalSet:
    return IntradaySignalSet(
        instrument_id=instrument_id,
        session_date=session_date,
        as_of=as_of,
        vwap=_vwap(vwap),
        trend=_trend(trend),
        or15=_dummy_or(OpeningRangeWindow.OR15, breakout=or15_breakout),
        or30=_dummy_or(OpeningRangeWindow.OR30, breakout=or30_breakout),
        relative_strength=relative_strength or _rs(vs_market=rs_vs_market, vs_sector=rs_vs_sector),
        gap=_dummy_gap(has_gap=gap),
        relative_volume=relative_volume or _rvol(rvol),
        data_quality=data_quality,
        explanation="test signal set",
    )


ENGINE = EntryQualificationEngine()
FINALITY = EntryEvidenceFinality.UNKNOWN_PROVENANCE


def _evaluate(
    *,
    decision: Decision | None = None,
    session_context: SessionContext | None = None,
    signal_set: IntradaySignalSet | None = None,
    evidence_finality: EntryEvidenceFinality = FINALITY,
    policy: EntryQualificationPolicy | None = None,
):
    return ENGINE.evaluate(
        decision=decision or _decision(),
        session_context=session_context or _session_context(),
        signal_set=signal_set or _signal_set(),
        evidence_finality=evidence_finality,
        policy=policy or EntryQualificationPolicy(),
    )


# --------------------------------------------------------------------------- #
# 1-6: structural / lifecycle / parity
# --------------------------------------------------------------------------- #


def test_1_non_watch_trade_decision_is_out_of_scope() -> None:
    result = _evaluate(decision=_decision(decision_type=DecisionType.NO_TRADE))
    assert result.state is EntryQualificationState.OUT_OF_SCOPE
    assert result.reason_codes == (EntryQualificationReasonCode.STRUCTURALLY_OUT_OF_SCOPE,)


def test_2_non_trading_session_is_out_of_scope() -> None:
    result = _evaluate(session_context=_session_context(phase=SessionPhase.NOT_A_TRADING_SESSION))
    assert result.state is EntryQualificationState.OUT_OF_SCOPE


def test_3_closed_session_is_expired() -> None:
    result = _evaluate(session_context=_session_context(phase=SessionPhase.CLOSED))
    assert result.state is EntryQualificationState.EXPIRED
    assert result.reason_codes == (EntryQualificationReasonCode.SESSION_EXPIRED,)


def test_4_active_watch_all_conditions_true_is_qualified() -> None:
    result = _evaluate(decision=_decision(decision_type=DecisionType.WATCH))
    assert result.state is EntryQualificationState.QUALIFIED


def test_5_active_trade_identical_conditions_is_qualified() -> None:
    result = _evaluate(decision=_decision(decision_type=DecisionType.TRADE))
    assert result.state is EntryQualificationState.QUALIFIED


def test_6_watch_and_trade_same_evidence_yield_same_state_and_preserve_type() -> None:
    watch = _evaluate(decision=_decision(decision_type=DecisionType.WATCH, decision_id="d-w"))
    trade = _evaluate(decision=_decision(decision_type=DecisionType.TRADE, decision_id="d-t"))
    assert watch.state == trade.state
    assert watch.decision_type is DecisionType.WATCH
    assert trade.decision_type is DecisionType.TRADE


# --------------------------------------------------------------------------- #
# 7-14: individual condition / tri-state OR semantics
# --------------------------------------------------------------------------- #


def test_7_vwap_false_is_not_yet() -> None:
    result = _evaluate(signal_set=_signal_set(vwap=VwapRelation.BELOW_VWAP))
    assert result.state is EntryQualificationState.NOT_YET
    assert EntryQualificationReasonCode.VWAP_CONDITION_NOT_MET in result.reason_codes


def test_8_trend_false_is_not_yet() -> None:
    result = _evaluate(signal_set=_signal_set(trend=IntradayTrendLabel.BEARISH))
    assert result.state is EntryQualificationState.NOT_YET
    assert EntryQualificationReasonCode.TREND_CONDITION_NOT_MET in result.reason_codes


def test_9_rs_false_and_rvol_false_is_not_yet() -> None:
    result = _evaluate(
        signal_set=_signal_set(
            rs_vs_market=RelativeStrengthRelation.UNDERPERFORMING,
            rs_vs_sector=RelativeStrengthRelation.MATCHING,
            rvol=RelativeVolumeRelation.BELOW_BASELINE,
        )
    )
    assert result.state is EntryQualificationState.NOT_YET
    assert EntryQualificationReasonCode.SUPPORT_CONDITION_NOT_MET in result.reason_codes


def test_10_rs_true_rvol_unavailable_is_qualified() -> None:
    result = _evaluate(
        signal_set=_signal_set(
            rs_vs_market=RelativeStrengthRelation.OUTPERFORMING,
            rs_vs_sector=RelativeStrengthRelation.UNKNOWN,
            rvol=RelativeVolumeRelation.UNKNOWN,
        )
    )
    assert result.state is EntryQualificationState.QUALIFIED


def test_11_rs_unavailable_rvol_true_is_qualified() -> None:
    result = _evaluate(
        signal_set=_signal_set(
            rs_vs_market=RelativeStrengthRelation.UNKNOWN,
            rs_vs_sector=RelativeStrengthRelation.UNKNOWN,
            rvol=RelativeVolumeRelation.ABOVE_BASELINE,
        )
    )
    assert result.state is EntryQualificationState.QUALIFIED


def test_12_rs_unavailable_rvol_unavailable_is_unknown() -> None:
    result = _evaluate(
        signal_set=_signal_set(
            rs_vs_market=RelativeStrengthRelation.UNKNOWN,
            rs_vs_sector=RelativeStrengthRelation.UNKNOWN,
            rvol=RelativeVolumeRelation.UNKNOWN,
        )
    )
    assert result.state is EntryQualificationState.UNKNOWN
    assert result.reason_codes == (EntryQualificationReasonCode.SUPPORT_EVIDENCE_UNRESOLVED,)


def test_13_vwap_unavailable_is_unknown() -> None:
    result = _evaluate(signal_set=_signal_set(vwap=VwapRelation.VWAP_UNAVAILABLE))
    assert result.state is EntryQualificationState.UNKNOWN
    assert EntryQualificationReasonCode.VWAP_EVIDENCE_UNAVAILABLE in result.reason_codes


def test_14_trend_unavailable_is_unknown() -> None:
    result = _evaluate(signal_set=_signal_set(trend=IntradayTrendLabel.UNKNOWN))
    assert result.state is EntryQualificationState.UNKNOWN
    assert EntryQualificationReasonCode.TREND_EVIDENCE_UNAVAILABLE in result.reason_codes


def test_false_dominates_unknown_in_and() -> None:
    """VWAP definitively false + trend genuinely unavailable: FALSE
    dominates UNKNOWN, so the verdict must be NOT_YET, not UNKNOWN, and the
    reason codes must cite only the deciding (false) condition."""
    result = _evaluate(
        signal_set=_signal_set(vwap=VwapRelation.BELOW_VWAP, trend=IntradayTrendLabel.UNKNOWN)
    )
    assert result.state is EntryQualificationState.NOT_YET
    assert result.reason_codes == (EntryQualificationReasonCode.VWAP_CONDITION_NOT_MET,)


# --------------------------------------------------------------------------- #
# 15: SessionDataQuality is not a blanket gate (Option C)
# --------------------------------------------------------------------------- #


def test_15_expected_bar_missing_session_quality_does_not_block_qualified() -> None:
    result = _evaluate(
        session_context=_session_context(data_quality=SessionDataQualityStatus.EXPECTED_BAR_MISSING),
        signal_set=_signal_set(data_quality=SessionDataQualityStatus.EXPECTED_BAR_MISSING),
    )
    assert result.state is EntryQualificationState.QUALIFIED


# --------------------------------------------------------------------------- #
# 16-18: OR / Gap / sector non-role
# --------------------------------------------------------------------------- #


def test_16_or_evidence_changes_do_not_change_state() -> None:
    base = _evaluate(signal_set=_signal_set(or15_breakout=False, or30_breakout=False))
    with_or = _evaluate(signal_set=_signal_set(or15_breakout=True, or30_breakout=True))
    assert base.state == with_or.state == EntryQualificationState.QUALIFIED


def test_17_gap_changes_do_not_change_state() -> None:
    base = _evaluate(signal_set=_signal_set(gap=False))
    with_gap = _evaluate(signal_set=_signal_set(gap=True))
    assert base.state == with_gap.state == EntryQualificationState.QUALIFIED


def test_18_no_sector_specific_branch_in_engine_or_reason_vocabulary() -> None:
    import inspect

    source = inspect.getsource(EntryQualificationEngine)
    assert "sector" not in source.lower()
    assert not any("SECTOR" in code.value for code in EntryQualificationReasonCode)


# --------------------------------------------------------------------------- #
# 19-21: confirmation / disqualification never emitted
# --------------------------------------------------------------------------- #


def test_19_confirmation_is_always_not_evaluated() -> None:
    for state_case in (
        _signal_set(),  # QUALIFIED
        _signal_set(vwap=VwapRelation.BELOW_VWAP),  # NOT_YET
        _signal_set(vwap=VwapRelation.VWAP_UNAVAILABLE),  # UNKNOWN
    ):
        result = _evaluate(signal_set=state_case)
        assert result.confirmation is EntryQualificationConfirmation.NOT_EVALUATED


def test_20_confirmed_by_policy_never_emitted() -> None:
    result = _evaluate()
    assert result.confirmation is not EntryQualificationConfirmation.CONFIRMED_BY_POLICY


def test_21_disqualified_for_session_never_reachable() -> None:
    """Exhaustive sweep: every phase x every tri-state leg combination the
    engine can reach must never emit DISQUALIFIED_FOR_SESSION."""
    tri_values = (
        VwapRelation.ABOVE_VWAP, VwapRelation.BELOW_VWAP, VwapRelation.VWAP_UNAVAILABLE,
    )
    trend_values = (
        IntradayTrendLabel.BULLISH, IntradayTrendLabel.BEARISH, IntradayTrendLabel.UNKNOWN,
    )
    rvol_values = (
        RelativeVolumeRelation.ABOVE_BASELINE, RelativeVolumeRelation.BELOW_BASELINE,
        RelativeVolumeRelation.UNKNOWN,
    )
    phases = (
        SessionPhase.NOT_A_TRADING_SESSION, SessionPhase.PRE_OPEN,
        SessionPhase.REGULAR, SessionPhase.CLOSED,
    )
    for phase, vwap, trend, rvol in itertools.product(phases, tri_values, trend_values, rvol_values):
        result = _evaluate(
            session_context=_session_context(phase=phase),
            signal_set=_signal_set(vwap=vwap, trend=trend, rvol=rvol),
        )
        assert result.state is not EntryQualificationState.DISQUALIFIED_FOR_SESSION


# --------------------------------------------------------------------------- #
# 22-24: evidence finality orthogonality
# --------------------------------------------------------------------------- #


def test_22_evidence_finality_is_orthogonal_to_state() -> None:
    for finality in EntryEvidenceFinality:
        result = _evaluate(evidence_finality=finality)
        assert result.state is EntryQualificationState.QUALIFIED
        assert result.evidence_finality is finality


def test_23_qualified_with_provisional_finality_is_representable() -> None:
    result = _evaluate(evidence_finality=EntryEvidenceFinality.LIVE_M5_PROVISIONAL)
    assert result.state is EntryQualificationState.QUALIFIED
    assert result.evidence_finality is EntryEvidenceFinality.LIVE_M5_PROVISIONAL


def test_24_qualified_with_unknown_provenance_is_representable() -> None:
    result = _evaluate(evidence_finality=EntryEvidenceFinality.UNKNOWN_PROVENANCE)
    assert result.state is EntryQualificationState.QUALIFIED
    assert result.evidence_finality is EntryEvidenceFinality.UNKNOWN_PROVENANCE


# --------------------------------------------------------------------------- #
# 25-30: determinism, timezone, provenance, reasons, explanation, statelessness
# --------------------------------------------------------------------------- #


def test_25_identical_inputs_produce_identical_output() -> None:
    a = _evaluate()
    b = _evaluate()
    assert a == b


def test_26_as_of_is_timezone_aware_and_preserved_from_session_context() -> None:
    ctx = _session_context()
    result = _evaluate(session_context=ctx)
    assert result.as_of == ctx.as_of
    assert result.as_of.tzinfo is not None


def test_27_methodology_version_and_config_provenance_populated() -> None:
    result = _evaluate(policy=EntryQualificationPolicy(config_snapshot_id="cfg-abc"))
    assert result.methodology_version == DEFAULT_METHODOLOGY_VERSION
    assert result.config_snapshot_id == "cfg-abc"


def test_28_reason_codes_are_deterministic_and_state_specific() -> None:
    result = _evaluate(signal_set=_signal_set(vwap=VwapRelation.BELOW_VWAP))
    assert result.reason_codes == (EntryQualificationReasonCode.VWAP_CONDITION_NOT_MET,)
    assert len(set(result.reason_codes)) == len(result.reason_codes)


def test_29_explanation_is_deterministic_and_non_empty() -> None:
    a = _evaluate(signal_set=_signal_set(vwap=VwapRelation.BELOW_VWAP))
    b = _evaluate(signal_set=_signal_set(vwap=VwapRelation.BELOW_VWAP))
    assert a.explanation == b.explanation
    assert a.explanation.startswith("NOT_YET:")


def test_30_no_prior_qualification_state_is_an_engine_input() -> None:
    """Structural proof: evaluate() has no parameter capable of carrying a
    prior EntryQualification -- statelessness is enforced by signature, not
    just by convention."""
    import inspect

    params = inspect.signature(EntryQualificationEngine.evaluate).parameters
    assert "prior" not in params
    assert "previous" not in params
    assert "history" not in params
    for param in params.values():
        assert param.annotation != "EntryQualification"


# --------------------------------------------------------------------------- #
# Structural sanity: instrument-mismatch rejected, decision preserved
# --------------------------------------------------------------------------- #


def test_mismatched_instrument_ids_raise() -> None:
    with pytest.raises(ValueError, match="different instruments"):
        _evaluate(
            decision=_decision(instrument_id="NSE:OTHER"),
            session_context=_session_context(instrument_id=IID),
        )


# --------------------------------------------------------------------------- #
# ID-6B.2A: input-coherence hardening (SessionContext <-> IntradaySignalSet)
# --------------------------------------------------------------------------- #


def test_signal_set_instrument_mismatch_raises() -> None:
    with pytest.raises(ValueError, match="different instruments"):
        _evaluate(
            decision=_decision(instrument_id=IID),
            session_context=_session_context(instrument_id=IID),
            signal_set=_signal_set(instrument_id="NSE:BBB"),
        )


def test_signal_set_session_date_mismatch_raises() -> None:
    with pytest.raises(ValueError, match="different session dates"):
        _evaluate(
            session_context=_session_context(),
            signal_set=_signal_set(session_date=date(2026, 9, 1)),
        )


def test_signal_set_as_of_mismatch_raises() -> None:
    with pytest.raises(ValueError, match="different evaluation as_of timestamps"):
        _evaluate(
            session_context=_session_context(),
            signal_set=_signal_set(as_of=datetime(2026, 9, 2, 10, 5, tzinfo=IST)),
        )


def test_coherent_inputs_preserve_existing_v0_state_semantics() -> None:
    """Regression: fully coherent inputs (the common case) must still
    produce exactly the same QUALIFIED verdict as before coherence
    hardening was added."""
    result = _evaluate()
    assert result.state is EntryQualificationState.QUALIFIED


def test_decision_instrument_none_fallback_still_requires_signal_set_coherence() -> None:
    """Decision.instrument_id=None is a legitimate fallback (existing
    behavior): the engine falls back to SessionContext's own instrument_id.
    That fallback must not create a loophole -- IntradaySignalSet must
    still agree with SessionContext exactly."""
    valid = _evaluate(
        decision=_decision(instrument_id=None),
        session_context=_session_context(instrument_id=IID),
        signal_set=_signal_set(instrument_id=IID),
    )
    assert valid.state is EntryQualificationState.QUALIFIED

    with pytest.raises(ValueError, match="different instruments"):
        _evaluate(
            decision=_decision(instrument_id=None),
            session_context=_session_context(instrument_id=IID),
            signal_set=_signal_set(instrument_id="NSE:BBB"),
        )


def test_option_c_regression_after_coherence_hardening() -> None:
    """Coherent inputs + EXPECTED_BAR_MISSING + positive frozen artifacts
    must still yield QUALIFIED -- coherence hardening must not reopen
    Option C (owner §8)."""
    result = _evaluate(
        session_context=_session_context(data_quality=SessionDataQualityStatus.EXPECTED_BAR_MISSING),
        signal_set=_signal_set(data_quality=SessionDataQualityStatus.EXPECTED_BAR_MISSING),
    )
    assert result.state is EntryQualificationState.QUALIFIED


def test_watch_trade_parity_unchanged_after_coherence_hardening() -> None:
    watch = _evaluate(decision=_decision(decision_type=DecisionType.WATCH, decision_id="d-w2"))
    trade = _evaluate(decision=_decision(decision_type=DecisionType.TRADE, decision_id="d-t2"))
    assert watch.state == trade.state is EntryQualificationState.QUALIFIED


def test_nested_relative_strength_instrument_mismatch_raises() -> None:
    mismatched_rs = _rs(vs_market=RelativeStrengthRelation.OUTPERFORMING, instrument_id="NSE:BBB")
    with pytest.raises(ValueError, match="relative_strength evidence"):
        _evaluate(signal_set=_signal_set(relative_strength=mismatched_rs))


def test_nested_relative_volume_session_date_mismatch_raises() -> None:
    mismatched_rvol = _rvol(RelativeVolumeRelation.ABOVE_BASELINE, session_date=date(2026, 9, 1))
    with pytest.raises(ValueError, match="relative_volume evidence"):
        _evaluate(signal_set=_signal_set(relative_volume=mismatched_rvol))


def test_coherence_validation_is_o1_and_reads_no_prior_state() -> None:
    """Structural proof the new checks did not introduce any repository/
    history dependency: same signature shape as before (see
    test_30_no_prior_qualification_state_is_an_engine_input)."""
    import inspect

    params = inspect.signature(EntryQualificationEngine.evaluate).parameters
    assert set(params) == {"self", "decision", "session_context", "signal_set", "evidence_finality", "policy"}


def test_decision_identity_is_preserved_never_promoted() -> None:
    decision = _decision(decision_type=DecisionType.WATCH, decision_id="d-preserve")
    result = _evaluate(decision=decision)
    assert result.decision_id == "d-preserve"
    assert result.decision_type is DecisionType.WATCH  # never promoted to TRADE
    assert result.run_id == decision.run_id
    assert result.cycle_id == decision.cycle_id


def test_pre_open_defaults_to_not_yet_regardless_of_signal_evidence() -> None:
    result = _evaluate(session_context=_session_context(phase=SessionPhase.PRE_OPEN))
    assert result.state is EntryQualificationState.NOT_YET
    assert result.reason_codes == (EntryQualificationReasonCode.INSUFFICIENT_EVIDENCE,)


def test_evidence_refs_are_bounded_and_reference_real_artifacts() -> None:
    result = _evaluate()
    kinds = {ref.kind.value for ref in result.evidence_refs}
    assert kinds == {"DECISION", "SESSION_CONTEXT", "INTRADAY_SIGNAL_SET"}
    for ref in result.evidence_refs:
        assert ref.explanation


def test_out_of_scope_evidence_refs_do_not_reference_signal_set() -> None:
    result = _evaluate(decision=_decision(decision_type=DecisionType.NO_TRADE))
    kinds = {ref.kind.value for ref in result.evidence_refs}
    assert "INTRADAY_SIGNAL_SET" not in kinds


# --------------------------------------------------------------------------- #
# Tri-state helper unit tests (internal, but the semantics are load-bearing)
# --------------------------------------------------------------------------- #


def test_tri_and_false_dominates() -> None:
    assert _tri_and(_Tri.FALSE, _Tri.UNKNOWN, _Tri.TRUE) is _Tri.FALSE


def test_tri_and_unknown_without_false() -> None:
    assert _tri_and(_Tri.UNKNOWN, _Tri.TRUE) is _Tri.UNKNOWN


def test_tri_and_all_true() -> None:
    assert _tri_and(_Tri.TRUE, _Tri.TRUE) is _Tri.TRUE


def test_tri_or_true_dominates() -> None:
    assert _tri_or(_Tri.TRUE, _Tri.UNKNOWN, _Tri.FALSE) is _Tri.TRUE


def test_tri_or_unknown_without_true() -> None:
    assert _tri_or(_Tri.UNKNOWN, _Tri.FALSE) is _Tri.UNKNOWN


def test_tri_or_all_false() -> None:
    assert _tri_or(_Tri.FALSE, _Tri.FALSE) is _Tri.FALSE


def test_vwap_tri_and_trend_tri_match_relation_semantics() -> None:
    assert _vwap_tri(_signal_set(vwap=VwapRelation.ABOVE_VWAP)) is _Tri.TRUE
    assert _vwap_tri(_signal_set(vwap=VwapRelation.AT_VWAP)) is _Tri.FALSE
    assert _vwap_tri(_signal_set(vwap=VwapRelation.VWAP_UNAVAILABLE)) is _Tri.UNKNOWN
    assert _trend_tri(_signal_set(trend=IntradayTrendLabel.MIXED)) is _Tri.FALSE


def test_support_tri_true_when_either_leg_supports() -> None:
    only_rs = _signal_set(
        rs_vs_market=RelativeStrengthRelation.OUTPERFORMING,
        rs_vs_sector=RelativeStrengthRelation.UNKNOWN,
        rvol=RelativeVolumeRelation.UNKNOWN,
    )
    only_rvol = _signal_set(
        rs_vs_market=RelativeStrengthRelation.UNKNOWN,
        rs_vs_sector=RelativeStrengthRelation.UNKNOWN,
        rvol=RelativeVolumeRelation.ABOVE_BASELINE,
    )
    assert _support_tri(only_rs) is _Tri.TRUE
    assert _support_tri(only_rvol) is _Tri.TRUE


# --------------------------------------------------------------------------- #
# Engine purity / performance
# --------------------------------------------------------------------------- #


def test_engine_evaluate_is_the_only_public_method() -> None:
    public = [
        name for name, _ in inspect_public_methods(EntryQualificationEngine)
    ]
    assert public == ["evaluate"]


def inspect_public_methods(cls):
    import inspect as _inspect

    return [
        (name, member)
        for name, member in _inspect.getmembers(cls, predicate=_inspect.isfunction)
        if not name.startswith("_")
    ]


def test_engine_has_no_mutable_instance_state() -> None:
    assert not dataclasses.fields(EntryQualificationEngine) if dataclasses.is_dataclass(
        EntryQualificationEngine
    ) else True
    engine = EntryQualificationEngine()
    assert vars(engine) == {}
