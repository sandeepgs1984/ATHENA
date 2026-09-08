"""Live Plan Supervision pure evidence composers + evaluator (ID-10 V0).

Direct construction of `EntryActionability`/`Candle` fixtures throughout
(mirrors `test_position_sizing_engine.py`'s/`test_entry_actionability_engine.py`'s
own established pattern) so each test controls exactly which upstream
state/direction/currentness/candle-path combination appears. Proves the
Owner's frozen ID-10 V0 contract end to end: LONG-only scope
(`LONG_VALIDATED_SHORT_UNVALIDATED`), currentness reuse (never
re-implemented), the closed `NOT_APPLICABLE/VALID/INVALIDATED` state
model, the non-negotiable two-window VWAP contract (session-start source
window vs. post-`evidence_as_of` supervision event window), the
post-`evidence_as_of` event boundary (`ts_open >= evidence_as_of`),
path-dependence/permanence of a VWAP-loss trigger, orthogonal
non-gating target progress, that `operative_invalidation.level` is never
consulted as a forward invalidation reference, Decimal-only arithmetic,
and timezone-aware invariants.
"""

from __future__ import annotations

from datetime import date, datetime, timedelta, timezone
from decimal import Decimal

import pytest

from athena.domain.enums import DecisionType, Direction, Timeframe
from athena.domain.market import Candle
from athena.intraday.entry_actionability_currentness import (
    CurrentnessResult,
    EntryActionabilityCurrentness,
)
from athena.intraday.entry_actionability_models import (
    EntryActionability,
    EntryActionabilityReasonCode,
    EntryActionabilityState,
    EntryLocationContext,
    EntryReference,
    EntryReferenceBasis,
    InvalidationBasis,
    OperativeInvalidation,
    RewardBasis,
    RewardReference,
)
from athena.intraday.entry_qualification_models import (
    EntryEvidenceFinality,
    EntryQualificationState,
)
from athena.intraday.live_plan_supervision_engine import (
    LivePlanSupervisionEngine,
    compose_target_progress_evidence,
    compose_vwap_loss_evidence,
)
from athena.intraday.live_plan_supervision_models import (
    LivePlanSupervisionReasonCode,
    LivePlanSupervisionState,
    TargetProgress,
    TargetProgressEvidence,
    VwapLossEvidence,
)

IID = "NSE:TEST"
DAY = date(2026, 9, 8)
TZ = timezone.utc
ENGINE = LivePlanSupervisionEngine()


def _t(hh: int, mm: int) -> datetime:
    return datetime(2026, 9, 8, hh, mm, tzinfo=TZ)


def _c(ts_open: datetime, price, *, high=None, low=None, volume: int = 1000) -> Candle:
    price = Decimal(str(price))
    high = Decimal(str(high)) if high is not None else price
    low = Decimal(str(low)) if low is not None else price
    return Candle(
        instrument_id=IID, timeframe=Timeframe.M5, ts_open=ts_open,
        open=price, high=high, low=low, close=price, volume=volume, source="test",
    )


def _actionable(
    *, direction: Direction = Direction.LONG, evidence_as_of: datetime,
    invalidation_level: Decimal = Decimal("98"),
    t1_price: Decimal = Decimal("101"), t2_price: Decimal = Decimal("101.5"),
) -> EntryActionability:
    eq_as_of = evidence_as_of - timedelta(minutes=5)
    return EntryActionability(
        instrument_id=IID, session_date=DAY,
        entry_qualification_as_of=eq_as_of, decision_id="dec-1",
        entry_qualification_methodology_version="entry-qualification-v0",
        entry_actionability_as_of=evidence_as_of,
        entry_actionability_methodology_version="entry-actionability-v0",
        decision_type=DecisionType.TRADE, direction=direction,
        entry_qualification_state=EntryQualificationState.QUALIFIED,
        run_id="run-1", cycle_id="cyc-1",
        state=EntryActionabilityState.ACTIONABLE, reason_codes=(),
        evidence_finality=EntryEvidenceFinality.NO_DECISIVE_PROVISIONAL_M5_DEPENDENCY,
        evidence_as_of=evidence_as_of,
        entry_reference=EntryReference(price=Decimal("100"), basis=EntryReferenceBasis.QUALIFYING_M5_CLOSE),
        entry_location_context=EntryLocationContext(vwap=Decimal("99"), vwap_deviation_pct=Decimal("1.0")),
        operative_invalidation=OperativeInvalidation(level=invalidation_level, basis=InvalidationBasis.VWAP_LOSS),
        reward=RewardReference(
            t1_price=t1_price, t2_price=t2_price, basis=RewardBasis.GOAL_BANDS_ONLY,
            reward_risk_to_t1=Decimal("2"), reward_risk_to_t2=Decimal("3"),
        ),
        opening_range_context=None,
        evaluated_at=evidence_as_of, explanation="test actionable",
    )


def _not_actionable(evidence_as_of: datetime) -> EntryActionability:
    eq_as_of = evidence_as_of - timedelta(minutes=5)
    return EntryActionability(
        instrument_id=IID, session_date=DAY,
        entry_qualification_as_of=eq_as_of, decision_id="dec-1",
        entry_qualification_methodology_version="entry-qualification-v0",
        entry_actionability_as_of=evidence_as_of,
        entry_actionability_methodology_version="entry-actionability-v0",
        decision_type=DecisionType.TRADE, direction=Direction.NONE,
        entry_qualification_state=EntryQualificationState.DISQUALIFIED_FOR_SESSION,
        run_id="run-1", cycle_id="cyc-1",
        state=EntryActionabilityState.NOT_ACTIONABLE,
        reason_codes=(EntryActionabilityReasonCode.UPSTREAM_EQ_NOT_QUALIFIED,),
        evidence_finality=EntryEvidenceFinality.NO_DECISIVE_PROVISIONAL_M5_DEPENDENCY,
        evidence_as_of=None, entry_reference=None, entry_location_context=None,
        operative_invalidation=None, reward=None, opening_range_context=None,
        evaluated_at=evidence_as_of, explanation="test not actionable",
    )


def _currentness(
    status: EntryActionabilityCurrentness = EntryActionabilityCurrentness.CURRENT,
) -> CurrentnessResult:
    return CurrentnessResult(status=status, explanation=f"test currentness={status.value}")


# ---------------------------------------------------------------------------
# A: LONG CURRENT ACTIONABLE, no VWAP loss -> VALID
# ---------------------------------------------------------------------------


def test_a_long_current_actionable_no_vwap_loss_is_valid():
    evidence_as_of = _t(9, 30)
    session = [_c(_t(9, m), 100) for m in (15, 20, 25, 30, 35)]
    path = [c for c in session if c.ts_open >= evidence_as_of]
    ea = _actionable(evidence_as_of=evidence_as_of)

    vle = compose_vwap_loss_evidence(session, path, Direction.LONG)
    tpe = compose_target_progress_evidence(path, ea.reward, Direction.LONG)
    result = ENGINE.evaluate(
        entry_actionability=ea, currentness=_currentness(),
        vwap_loss_evidence=vle, target_progress_evidence=tpe,
        supervision_as_of=evidence_as_of + timedelta(minutes=10),
        evaluated_at=evidence_as_of + timedelta(minutes=10),
    )

    assert vle.triggered is False
    assert result.state is LivePlanSupervisionState.VALID
    assert result.reason_codes == ()


# ---------------------------------------------------------------------------
# B: current candle below evolving VWAP -> INVALIDATED/VWAP_LOSS
# ---------------------------------------------------------------------------


def test_b_current_candle_below_evolving_vwap_is_invalidated():
    evidence_as_of = _t(9, 15)
    session = [_c(_t(9, 15), 100), _c(_t(9, 20), 90)]
    path = list(session)  # both candles are >= evidence_as_of
    ea = _actionable(evidence_as_of=evidence_as_of)

    vle = compose_vwap_loss_evidence(session, path, Direction.LONG)
    tpe = compose_target_progress_evidence(path, ea.reward, Direction.LONG)
    result = ENGINE.evaluate(
        entry_actionability=ea, currentness=_currentness(),
        vwap_loss_evidence=vle, target_progress_evidence=tpe,
        supervision_as_of=_t(9, 25), evaluated_at=_t(9, 25),
    )

    assert vle.triggered is True
    assert vle.trigger_close == Decimal("90")
    # cumulative vwap after both candles = (100 + 90) / 2 = 95
    assert vle.trigger_vwap == Decimal("95")
    assert vle.first_triggered_as_of == _t(9, 25)  # 09:20 + 5m
    assert result.state is LivePlanSupervisionState.INVALIDATED
    assert result.reason_codes == (LivePlanSupervisionReasonCode.VWAP_LOSS,)


# ---------------------------------------------------------------------------
# C: earlier VWAP loss + later recovery -> remains INVALIDATED (permanence)
# ---------------------------------------------------------------------------


def test_c_earlier_vwap_loss_survives_later_recovery():
    evidence_as_of = _t(10, 0)
    session = [
        _c(_t(10, 0), 100), _c(_t(10, 5), 100),
        _c(_t(10, 10), 90),    # dip -- triggers at checkpoint 10:15
        _c(_t(10, 15), 130),   # strong recovery
        _c(_t(10, 20), 130),   # recovery holds
    ]
    path = list(session)
    ea = _actionable(evidence_as_of=evidence_as_of)

    vle = compose_vwap_loss_evidence(session, path, Direction.LONG)

    assert vle.triggered is True
    assert vle.first_triggered_as_of == _t(10, 15)
    assert vle.trigger_close == Decimal("90")
    assert vle.currently_above_vwap is True  # last candle recovered above VWAP
    result = ENGINE.evaluate(
        entry_actionability=ea, currentness=_currentness(),
        vwap_loss_evidence=vle,
        target_progress_evidence=compose_target_progress_evidence(path, ea.reward, Direction.LONG),
        supervision_as_of=_t(10, 25), evaluated_at=_t(10, 25),
    )
    assert result.state is LivePlanSupervisionState.INVALIDATED


# ---------------------------------------------------------------------------
# D: two-window correctness -- session-start VWAP != post-entry-only VWAP
# ---------------------------------------------------------------------------


def test_d_session_start_window_is_authoritative_not_post_entry_only():
    evidence_as_of = _t(9, 30)
    pre_entry = [_c(_t(9, 15), 150), _c(_t(9, 20), 150)]
    post_entry = [_c(_t(9, 30), 100), _c(_t(9, 35), 100)]
    session_completed_m5 = pre_entry + post_entry
    supervised_path = post_entry

    correct = compose_vwap_loss_evidence(session_completed_m5, supervised_path, Direction.LONG)
    # Deliberately-wrong composition: using the event window as if it were
    # also the VWAP source window (the defect the two-window contract
    # exists to prevent).
    incorrect = compose_vwap_loss_evidence(supervised_path, supervised_path, Direction.LONG)

    assert correct.triggered is True   # 100 < (150+150+100)/3 = 133.33 at 09:35
    assert incorrect.triggered is False  # 100 >= 100 using only post-entry history


# ---------------------------------------------------------------------------
# E: exact post-evidence_as_of event boundary
# ---------------------------------------------------------------------------


def test_e_event_boundary_excludes_candle_completing_at_evidence_as_of():
    evidence_as_of = _t(10, 15)
    before = _c(_t(10, 10), 100)   # completes 10:15 -- must be EXCLUDED
    at_boundary = _c(_t(10, 15), 100)  # opens 10:15 -- must be INCLUDED
    session = [before, at_boundary]

    supervised_path = [c for c in session if c.ts_open >= evidence_as_of]

    assert before not in supervised_path
    assert at_boundary in supervised_path
    assert supervised_path == [at_boundary]


# ---------------------------------------------------------------------------
# F: no future-candle leakage into an earlier checkpoint's evolving VWAP
# ---------------------------------------------------------------------------


def test_f_future_session_candle_does_not_leak_into_earlier_checkpoint():
    evidence_as_of = _t(10, 0)
    early_path = [_c(_t(10, 0), 100)]
    session_without_future = [_c(_t(10, 0), 100)]
    session_with_future = [_c(_t(10, 0), 100), _c(_t(10, 30), 1_000_000)]

    without_future = compose_vwap_loss_evidence(session_without_future, early_path, Direction.LONG)
    with_future = compose_vwap_loss_evidence(session_with_future, early_path, Direction.LONG)

    assert without_future == with_future


# ---------------------------------------------------------------------------
# G/H/I: target progress path-dependence and reachability
# ---------------------------------------------------------------------------


def test_g_t1_touched_earlier_survives_later_retracement():
    ea = _actionable(evidence_as_of=_t(9, 30), t1_price=Decimal("101"), t2_price=Decimal("105"))
    path = [
        _c(_t(9, 30), 100, high=Decimal("102")),  # touches T1
        _c(_t(9, 35), 95, high=Decimal("96")),    # retraces hard, no further touch
    ]
    tpe = compose_target_progress_evidence(path, ea.reward, Direction.LONG)
    assert tpe.status is TargetProgress.T1_REACHED
    assert tpe.t1_reached_as_of == _t(9, 35)  # 09:30 + 5m
    assert tpe.t2_reached_as_of is None


def test_h_t2_reached_implies_t1_with_correct_ordering():
    ea = _actionable(evidence_as_of=_t(9, 30), t1_price=Decimal("101"), t2_price=Decimal("103"))
    path = [_c(_t(9, 30), 100, high=Decimal("104"))]  # single candle clears both
    tpe = compose_target_progress_evidence(path, ea.reward, Direction.LONG)
    assert tpe.status is TargetProgress.T2_REACHED
    assert tpe.t1_reached_as_of == tpe.t2_reached_as_of == _t(9, 35)


def test_i_no_touch_is_none_reached():
    ea = _actionable(evidence_as_of=_t(9, 30))
    path = [_c(_t(9, 30), 100, high=Decimal("100.5"))]
    tpe = compose_target_progress_evidence(path, ea.reward, Direction.LONG)
    assert tpe.status is TargetProgress.NONE_REACHED
    assert tpe.t1_reached_as_of is None
    assert tpe.t2_reached_as_of is None


def test_j_target_progress_never_alters_valid_or_invalidated_state():
    evidence_as_of = _t(9, 30)
    ea = _actionable(evidence_as_of=evidence_as_of)
    not_reached = TargetProgressEvidence(
        status=TargetProgress.NONE_REACHED, t1_reached_as_of=None, t2_reached_as_of=None,
    )
    t2_reached = TargetProgressEvidence(
        status=TargetProgress.T2_REACHED,
        t1_reached_as_of=_t(9, 35), t2_reached_as_of=_t(9, 40),
    )
    not_triggered = VwapLossEvidence(
        triggered=False, first_triggered_as_of=None, trigger_close=None, trigger_vwap=None,
        current_close=Decimal("100"), current_vwap=Decimal("99"), currently_above_vwap=True,
    )
    triggered = VwapLossEvidence(
        triggered=True, first_triggered_as_of=_t(9, 35),
        trigger_close=Decimal("90"), trigger_vwap=Decimal("95"),
        current_close=Decimal("90"), current_vwap=Decimal("95"), currently_above_vwap=False,
    )

    for target_evidence in (not_reached, t2_reached):
        result = ENGINE.evaluate(
            entry_actionability=ea, currentness=_currentness(),
            vwap_loss_evidence=not_triggered, target_progress_evidence=target_evidence,
            supervision_as_of=_t(9, 45), evaluated_at=_t(9, 45),
        )
        assert result.state is LivePlanSupervisionState.VALID

    for target_evidence in (not_reached, t2_reached):
        result = ENGINE.evaluate(
            entry_actionability=ea, currentness=_currentness(),
            vwap_loss_evidence=triggered, target_progress_evidence=target_evidence,
            supervision_as_of=_t(9, 45), evaluated_at=_t(9, 45),
        )
        assert result.state is LivePlanSupervisionState.INVALIDATED


# ---------------------------------------------------------------------------
# K/L/M/N/O: upstream/direction/currentness gates (pure engine)
# ---------------------------------------------------------------------------


def test_k_upstream_not_actionable_is_not_applicable():
    ea = _not_actionable(_t(9, 30))
    result = ENGINE.evaluate(
        entry_actionability=ea, currentness=_currentness(),
        vwap_loss_evidence=None, target_progress_evidence=None,
        supervision_as_of=_t(9, 35), evaluated_at=_t(9, 35),
    )
    assert result.state is LivePlanSupervisionState.NOT_APPLICABLE
    assert result.reason_codes == (LivePlanSupervisionReasonCode.UPSTREAM_NOT_ACTIONABLE,)
    assert result.direction is None
    assert result.operative_invalidation_level is None
    assert result.t1_price is None
    assert result.t2_price is None


def test_l_short_direction_is_not_applicable_unvalidated_direction():
    ea = _actionable(
        direction=Direction.SHORT, evidence_as_of=_t(9, 30),
        invalidation_level=Decimal("102"),
    )
    result = ENGINE.evaluate(
        entry_actionability=ea, currentness=_currentness(),
        vwap_loss_evidence=None, target_progress_evidence=None,
        supervision_as_of=_t(9, 35), evaluated_at=_t(9, 35),
    )
    assert result.state is LivePlanSupervisionState.NOT_APPLICABLE
    assert result.reason_codes == (LivePlanSupervisionReasonCode.UNVALIDATED_DIRECTION,)
    # upstream fields still echoed for explainability, per rule 1
    assert result.direction is Direction.SHORT
    assert result.operative_invalidation_level == ea.operative_invalidation.level


@pytest.mark.parametrize(
    "status",
    [
        EntryActionabilityCurrentness.STALE,
        EntryActionabilityCurrentness.SUPERSEDED,
        EntryActionabilityCurrentness.SESSION_CLOSED,
    ],
)
def test_m_n_o_non_current_statuses_route_to_not_applicable_never_invalidated(status):
    ea = _actionable(evidence_as_of=_t(9, 30))
    result = ENGINE.evaluate(
        entry_actionability=ea, currentness=_currentness(status),
        vwap_loss_evidence=None, target_progress_evidence=None,
        supervision_as_of=_t(9, 35), evaluated_at=_t(9, 35),
    )
    assert result.state is LivePlanSupervisionState.NOT_APPLICABLE
    assert result.reason_codes == (LivePlanSupervisionReasonCode.UPSTREAM_NOT_CURRENT,)
    assert result.state is not LivePlanSupervisionState.INVALIDATED


# ---------------------------------------------------------------------------
# P: operative_invalidation.level is never used as the forward VWAP line
# ---------------------------------------------------------------------------


def test_p_frozen_operative_invalidation_level_never_used_as_forward_vwap():
    evidence_as_of = _t(9, 15)
    # Frozen entry-checkpoint VWAP level suggests price would need to fall
    # all the way to 50 to invalidate -- deliberately far from the real,
    # freshly-recomputed evolving VWAP below.
    ea = _actionable(evidence_as_of=evidence_as_of, invalidation_level=Decimal("50"))
    session = [_c(_t(9, 15), 100), _c(_t(9, 20), 90)]
    path = list(session)

    vle = compose_vwap_loss_evidence(session, path, Direction.LONG)
    result = ENGINE.evaluate(
        entry_actionability=ea, currentness=_currentness(),
        vwap_loss_evidence=vle,
        target_progress_evidence=compose_target_progress_evidence(path, ea.reward, Direction.LONG),
        supervision_as_of=_t(9, 25), evaluated_at=_t(9, 25),
    )

    # The forward decision is INVALIDATED (real evolving VWAP was
    # breached) even though the stale frozen level of 50 was never
    # breached -- proving the frozen level plays no role in the forward
    # test. It is still faithfully echoed as upstream context.
    assert result.state is LivePlanSupervisionState.INVALIDATED
    assert result.operative_invalidation_level == Decimal("50")


# ---------------------------------------------------------------------------
# Q/R: trigger provenance exactness + permanence under path extension
# ---------------------------------------------------------------------------


def test_q_first_trigger_provenance_matches_the_triggering_candle_exactly():
    session = [_c(_t(9, 15), 100), _c(_t(9, 20), 90), _c(_t(9, 25), 200)]
    path = list(session)
    vle = compose_vwap_loss_evidence(session, path, Direction.LONG)
    assert vle.triggered is True
    assert vle.first_triggered_as_of == _t(9, 25)  # 09:20 + 5m
    assert vle.trigger_close == Decimal("90")
    assert vle.trigger_vwap == Decimal("95")  # (100+90)/2 at that checkpoint


def test_r_extending_the_path_further_cannot_erase_or_move_the_trigger():
    base_session = [_c(_t(9, 15), 100), _c(_t(9, 20), 90)]
    extended_session = base_session + [
        _c(_t(9, 25), 130), _c(_t(9, 30), 140), _c(_t(9, 35), 150),
    ]

    base = compose_vwap_loss_evidence(base_session, base_session, Direction.LONG)
    extended = compose_vwap_loss_evidence(extended_session, extended_session, Direction.LONG)

    assert base.triggered is extended.triggered is True
    assert base.first_triggered_as_of == extended.first_triggered_as_of
    assert base.trigger_close == extended.trigger_close
    assert base.trigger_vwap == extended.trigger_vwap


# ---------------------------------------------------------------------------
# S: Decimal-only arithmetic
# ---------------------------------------------------------------------------


def test_s_composed_evidence_uses_decimal_throughout():
    session = [_c(_t(9, 15), 100), _c(_t(9, 20), 90)]
    vle = compose_vwap_loss_evidence(session, session, Direction.LONG)
    assert isinstance(vle.trigger_close, Decimal)
    assert isinstance(vle.trigger_vwap, Decimal)
    assert isinstance(vle.current_close, Decimal)
    assert isinstance(vle.current_vwap, Decimal)

    ea = _actionable(evidence_as_of=_t(9, 15))
    tpe = compose_target_progress_evidence(
        [_c(_t(9, 15), 100, high=Decimal("101.2"))], ea.reward, Direction.LONG,
    )
    assert tpe.status is TargetProgress.T1_REACHED


# ---------------------------------------------------------------------------
# T: timezone-aware invariants
# ---------------------------------------------------------------------------


def test_t_evaluate_rejects_naive_evaluated_at():
    ea = _actionable(evidence_as_of=_t(9, 30))
    vle = VwapLossEvidence(
        triggered=False, first_triggered_as_of=None, trigger_close=None, trigger_vwap=None,
        current_close=None, current_vwap=None, currently_above_vwap=None,
    )
    tpe = TargetProgressEvidence(status=TargetProgress.NONE_REACHED, t1_reached_as_of=None, t2_reached_as_of=None)
    with pytest.raises(ValueError, match="timezone-aware"):
        ENGINE.evaluate(
            entry_actionability=ea, currentness=_currentness(),
            vwap_loss_evidence=vle, target_progress_evidence=tpe,
            supervision_as_of=_t(9, 45),
            evaluated_at=datetime(2026, 9, 8, 9, 45),  # naive
        )


def test_t_evaluate_rejects_naive_supervision_as_of():
    ea = _actionable(evidence_as_of=_t(9, 30))
    vle = VwapLossEvidence(
        triggered=False, first_triggered_as_of=None, trigger_close=None, trigger_vwap=None,
        current_close=None, current_vwap=None, currently_above_vwap=None,
    )
    tpe = TargetProgressEvidence(status=TargetProgress.NONE_REACHED, t1_reached_as_of=None, t2_reached_as_of=None)
    with pytest.raises(ValueError, match="timezone-aware"):
        ENGINE.evaluate(
            entry_actionability=ea, currentness=_currentness(),
            vwap_loss_evidence=vle, target_progress_evidence=tpe,
            supervision_as_of=datetime(2026, 9, 8, 9, 45),  # naive
            evaluated_at=_t(9, 45),
        )


def test_t_vwap_loss_evidence_rejects_naive_first_triggered_as_of():
    with pytest.raises(ValueError, match="timezone-aware"):
        VwapLossEvidence(
            triggered=True,
            first_triggered_as_of=datetime(2026, 9, 8, 9, 25),  # naive
            trigger_close=Decimal("90"), trigger_vwap=Decimal("95"),
            current_close=Decimal("90"), current_vwap=Decimal("95"), currently_above_vwap=False,
        )


# ---------------------------------------------------------------------------
# Misuse contract: V0 composers/evaluator refuse a non-LONG direction
# ---------------------------------------------------------------------------


def test_composers_reject_non_long_direction():
    session = [_c(_t(9, 15), 100)]
    ea = _actionable(evidence_as_of=_t(9, 15))
    with pytest.raises(ValueError, match="LONG-only"):
        compose_vwap_loss_evidence(session, session, Direction.SHORT)
    with pytest.raises(ValueError, match="LONG-only"):
        compose_target_progress_evidence(session, ea.reward, Direction.SHORT)


def test_engine_raises_if_evidence_missing_past_upstream_gates():
    ea = _actionable(evidence_as_of=_t(9, 30))
    with pytest.raises(ValueError, match="mandatory"):
        ENGINE.evaluate(
            entry_actionability=ea, currentness=_currentness(),
            vwap_loss_evidence=None, target_progress_evidence=None,
            supervision_as_of=_t(9, 35), evaluated_at=_t(9, 35),
        )


# ---------------------------------------------------------------------------
# Identity regression: supervision_as_of must never collapse two
# evaluations of the identical upstream EntryActionability made at
# different supervision checkpoints (Owner source-review correction,
# 2026-09-08) -- items A-F of that correction's own required test list.
# ---------------------------------------------------------------------------


def test_identity_a_same_checkpoint_same_inputs_has_one_identity():
    """A: same EntryActionability + same methodology + supervision
    checkpoint T1 -> one stable identity (called twice, byte-identical)."""
    evidence_as_of = _t(9, 30)
    ea = _actionable(evidence_as_of=evidence_as_of)
    vle = VwapLossEvidence(
        triggered=False, first_triggered_as_of=None, trigger_close=None, trigger_vwap=None,
        current_close=Decimal("100"), current_vwap=Decimal("99"), currently_above_vwap=True,
    )
    tpe = TargetProgressEvidence(status=TargetProgress.NONE_REACHED, t1_reached_as_of=None, t2_reached_as_of=None)
    t1_checkpoint = _t(9, 40)

    first = ENGINE.evaluate(
        entry_actionability=ea, currentness=_currentness(),
        vwap_loss_evidence=vle, target_progress_evidence=tpe,
        supervision_as_of=t1_checkpoint, evaluated_at=_t(9, 41),
    )
    second = ENGINE.evaluate(
        entry_actionability=ea, currentness=_currentness(),
        vwap_loss_evidence=vle, target_progress_evidence=tpe,
        supervision_as_of=t1_checkpoint, evaluated_at=_t(9, 42),  # evaluated_at differs, identity must not
    )

    assert first.identity_tuple() == second.identity_tuple()


def test_identity_b_c_d_later_checkpoint_of_same_ea_has_different_identity():
    """B/C/D: the SAME exact EntryActionability supervised at a LATER
    checkpoint T2 gets a DIFFERENT identity, while
    `entry_actionability_as_of` (the upstream plan's own checkpoint)
    stays byte-identical between the two -- proving `supervision_as_of`
    is genuinely independent of it, never derived from it."""
    evidence_as_of = _t(9, 30)
    ea = _actionable(evidence_as_of=evidence_as_of)
    vle = VwapLossEvidence(
        triggered=False, first_triggered_as_of=None, trigger_close=None, trigger_vwap=None,
        current_close=Decimal("100"), current_vwap=Decimal("99"), currently_above_vwap=True,
    )
    tpe = TargetProgressEvidence(status=TargetProgress.NONE_REACHED, t1_reached_as_of=None, t2_reached_as_of=None)
    t1_checkpoint = _t(9, 40)
    t2_checkpoint = _t(9, 55)

    at_t1 = ENGINE.evaluate(
        entry_actionability=ea, currentness=_currentness(),
        vwap_loss_evidence=vle, target_progress_evidence=tpe,
        supervision_as_of=t1_checkpoint, evaluated_at=_t(9, 41),
    )
    at_t2 = ENGINE.evaluate(
        entry_actionability=ea, currentness=_currentness(),
        vwap_loss_evidence=vle, target_progress_evidence=tpe,
        supervision_as_of=t2_checkpoint, evaluated_at=_t(9, 56),
    )

    # B: different identity across checkpoints.
    assert at_t1.identity_tuple() != at_t2.identity_tuple()
    # C: the upstream plan's own checkpoint is unchanged between them.
    assert at_t1.entry_actionability_as_of == at_t2.entry_actionability_as_of == ea.entry_actionability_as_of
    # D: this assertion's own market checkpoint genuinely advanced.
    assert at_t1.supervision_as_of == t1_checkpoint
    assert at_t2.supervision_as_of == t2_checkpoint
    assert at_t1.supervision_as_of != at_t2.supervision_as_of


def test_identity_e_evaluated_at_is_diagnostic_never_a_substitute_for_supervision_as_of():
    """E: `evaluated_at` (wall-clock diagnostic) does not participate in
    `identity_tuple()` at all -- two evaluations sharing the SAME
    `supervision_as_of` but carrying genuinely DIFFERENT `evaluated_at`
    values must produce the identical identity tuple, and
    `supervision_as_of` (not `evaluated_at`) is the market-checkpoint
    value that actually appears in it."""
    evidence_as_of = _t(9, 30)
    ea = _actionable(evidence_as_of=evidence_as_of)
    vle = VwapLossEvidence(
        triggered=False, first_triggered_as_of=None, trigger_close=None, trigger_vwap=None,
        current_close=Decimal("100"), current_vwap=Decimal("99"), currently_above_vwap=True,
    )
    tpe = TargetProgressEvidence(status=TargetProgress.NONE_REACHED, t1_reached_as_of=None, t2_reached_as_of=None)
    shared_checkpoint = _t(9, 40)

    early_wallclock = ENGINE.evaluate(
        entry_actionability=ea, currentness=_currentness(),
        vwap_loss_evidence=vle, target_progress_evidence=tpe,
        supervision_as_of=shared_checkpoint, evaluated_at=_t(9, 41),
    )
    much_later_wallclock = ENGINE.evaluate(
        entry_actionability=ea, currentness=_currentness(),
        vwap_loss_evidence=vle, target_progress_evidence=tpe,
        supervision_as_of=shared_checkpoint, evaluated_at=_t(11, 0),
    )

    assert early_wallclock.evaluated_at != much_later_wallclock.evaluated_at
    assert early_wallclock.identity_tuple() == much_later_wallclock.identity_tuple()
    assert shared_checkpoint in early_wallclock.identity_tuple()


def test_identity_f_valid_then_invalidated_across_checkpoints_cannot_share_identity():
    """F: a VALID assertion at one supervision checkpoint and an
    INVALIDATED assertion of the identical upstream EntryActionability
    at a later checkpoint must never share an identity tuple -- proven
    with a real path-dependent VWAP-loss trigger occurring strictly
    between the two checkpoints."""
    evidence_as_of = _t(10, 0)
    ea = _actionable(evidence_as_of=evidence_as_of)

    early_session = [_c(_t(10, 0), 100), _c(_t(10, 5), 100)]
    early_path = list(early_session)
    early_checkpoint = _t(10, 10)
    early_vle = compose_vwap_loss_evidence(early_session, early_path, Direction.LONG)
    early_tpe = compose_target_progress_evidence(early_path, ea.reward, Direction.LONG)
    valid_result = ENGINE.evaluate(
        entry_actionability=ea, currentness=_currentness(),
        vwap_loss_evidence=early_vle, target_progress_evidence=early_tpe,
        supervision_as_of=early_checkpoint, evaluated_at=early_checkpoint,
    )
    assert valid_result.state is LivePlanSupervisionState.VALID

    later_session = early_session + [_c(_t(10, 10), 90)]  # dip -- triggers
    later_path = list(later_session)
    later_checkpoint = _t(10, 20)
    later_vle = compose_vwap_loss_evidence(later_session, later_path, Direction.LONG)
    later_tpe = compose_target_progress_evidence(later_path, ea.reward, Direction.LONG)
    invalidated_result = ENGINE.evaluate(
        entry_actionability=ea, currentness=_currentness(),
        vwap_loss_evidence=later_vle, target_progress_evidence=later_tpe,
        supervision_as_of=later_checkpoint, evaluated_at=later_checkpoint,
    )
    assert invalidated_result.state is LivePlanSupervisionState.INVALIDATED

    assert valid_result.identity_tuple() != invalidated_result.identity_tuple()
