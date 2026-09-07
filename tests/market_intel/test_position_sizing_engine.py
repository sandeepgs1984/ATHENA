"""Position Sizing pure V0 deterministic evaluator (ID-9).

Direct construction of `EntryActionability` fixtures throughout (mirrors
`test_entry_actionability_engine.py`'s own established pattern) so each
test controls exactly which upstream state/direction/geometry
combination appears. Proves: LONG-only V0 scope
(`LONG_VALIDATED_SHORT_UNVALIDATED`), the three independent sizing
constraints and their binding-constraint reporting, zero-quantity-never-
forced-to-one-lot, Decimal-only arithmetic, exact upstream-provenance
preservation, determinism, and that `EntryActionability.reward`
(T1/T2/RR) is never read by V0 sizing math (`GOAL_BANDS_ONLY`/
`RR_INFORMATIONAL_ONLY` preserved).
"""

from __future__ import annotations

import ast
import inspect
from datetime import date, datetime, timezone
from decimal import Decimal

import pytest

from athena.domain.enums import DecisionType, Direction
from athena.intraday import position_sizing_engine as engine_module
from athena.intraday import position_sizing_models as models_module
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
from athena.intraday.position_sizing_engine import PositionSizingV0Engine
from athena.intraday.position_sizing_models import (
    DEFAULT_METHODOLOGY_VERSION,
    BindingConstraint,
    CapitalPolicy,
    PositionSizing,
    PositionSizingReasonCode,
    PositionSizingState,
)

IID = "NSE:TEST"
DAY = date(2026, 9, 7)
AS_OF = datetime(2026, 9, 7, 10, 0, tzinfo=timezone.utc)


def _actionable(
    *, direction: Direction = Direction.LONG,
    entry_price: Decimal = Decimal("100"),
    invalidation_level: Decimal = Decimal("98"),
) -> EntryActionability:
    return EntryActionability(
        instrument_id=IID, session_date=DAY,
        entry_qualification_as_of=AS_OF, decision_id="dec-1",
        entry_qualification_methodology_version="entry-qualification-v0",
        entry_actionability_as_of=AS_OF,
        entry_actionability_methodology_version="entry-actionability-v0",
        decision_type=DecisionType.TRADE, direction=direction,
        entry_qualification_state=EntryQualificationState.QUALIFIED,
        run_id="run-1", cycle_id="cyc-1",
        state=EntryActionabilityState.ACTIONABLE, reason_codes=(),
        evidence_finality=EntryEvidenceFinality.NO_DECISIVE_PROVISIONAL_M5_DEPENDENCY,
        evidence_as_of=AS_OF,
        entry_reference=EntryReference(price=entry_price, basis=EntryReferenceBasis.QUALIFYING_M5_CLOSE),
        entry_location_context=EntryLocationContext(vwap=Decimal("99"), vwap_deviation_pct=Decimal("1.0")),
        operative_invalidation=OperativeInvalidation(level=invalidation_level, basis=InvalidationBasis.VWAP_LOSS),
        reward=RewardReference(
            t1_price=Decimal("101"), t2_price=Decimal("101.5"), basis=RewardBasis.GOAL_BANDS_ONLY,
            reward_risk_to_t1=Decimal("999"), reward_risk_to_t2=Decimal("999"),
        ),
        opening_range_context=None,
        evaluated_at=AS_OF, explanation="test actionable",
    )


def _not_actionable(
    *, reason_codes=(EntryActionabilityReasonCode.UPSTREAM_EQ_NOT_QUALIFIED,),
) -> EntryActionability:
    return EntryActionability(
        instrument_id=IID, session_date=DAY,
        entry_qualification_as_of=AS_OF, decision_id="dec-1",
        entry_qualification_methodology_version="entry-qualification-v0",
        entry_actionability_as_of=AS_OF,
        entry_actionability_methodology_version="entry-actionability-v0",
        decision_type=DecisionType.TRADE, direction=Direction.NONE,
        entry_qualification_state=EntryQualificationState.DISQUALIFIED_FOR_SESSION,
        run_id="run-1", cycle_id="cyc-1",
        state=EntryActionabilityState.NOT_ACTIONABLE, reason_codes=reason_codes,
        evidence_finality=EntryEvidenceFinality.NO_DECISIVE_PROVISIONAL_M5_DEPENDENCY,
        evidence_as_of=None, entry_reference=None, entry_location_context=None,
        operative_invalidation=None, reward=None, opening_range_context=None,
        evaluated_at=AS_OF, explanation="test not actionable",
    )


def _illegal_actionable_direction_none() -> EntryActionability:
    """Construct an artifact `EntryActionability.__post_init__` itself
    forbids (ACTIONABLE with direction=NONE) by bypassing `__init__`
    entirely -- the only way to exercise the engine's own defensive
    NONE-direction branch, which is structurally unreachable through any
    legally-constructed `EntryActionability` (its own risk-geometry
    invariant requires LONG or SHORT whenever state=ACTIONABLE)."""
    legal = _actionable(direction=Direction.LONG)
    illegal = object.__new__(EntryActionability)
    for f in legal.__dataclass_fields__:
        object.__setattr__(illegal, f, getattr(legal, f))
    object.__setattr__(illegal, "direction", Direction.NONE)
    return illegal


def _illegal_actionable_invalid_geometry() -> EntryActionability:
    """Construct an ACTIONABLE artifact with wrong-side LONG geometry
    (invalidation above entry) -- forbidden by
    `EntryActionability._validate_risk_geometry`, bypassed the same way,
    to exercise the engine's own defensive INVALID_RISK_GEOMETRY branch."""
    legal = _actionable(direction=Direction.LONG, entry_price=Decimal("100"), invalidation_level=Decimal("98"))
    illegal = object.__new__(EntryActionability)
    for f in legal.__dataclass_fields__:
        object.__setattr__(illegal, f, getattr(legal, f))
    object.__setattr__(
        illegal, "operative_invalidation",
        OperativeInvalidation(level=Decimal("105"), basis=InvalidationBasis.VWAP_LOSS),
    )
    return illegal


def _policy(
    *, total: str = "100000", risk_pct: str = "1.0", max_value_pct: str = "10.0", version: str = "policy-v1",
) -> CapitalPolicy:
    return CapitalPolicy(
        total_deployable_capital=Decimal(total),
        risk_budget_per_trade_pct=Decimal(risk_pct),
        max_position_value_pct=Decimal(max_value_pct),
        policy_version=version,
    )


ENGINE = PositionSizingV0Engine()

#: A `CurrentnessResult` reporting CURRENT -- used by every test that is
#: not itself exercising the currentness gate (Owner correction,
#: 2026-09-07, issue 1), so those tests continue to exercise exactly the
#: same downstream behavior as before the gate was added.
_CURRENT = CurrentnessResult(status=EntryActionabilityCurrentness.CURRENT, explanation="test: current")


def _non_current(
    status: EntryActionabilityCurrentness = EntryActionabilityCurrentness.STALE,
) -> CurrentnessResult:
    return CurrentnessResult(status=status, explanation=f"test: {status.value}")


# --------------------------------------------------------------------------- #
# Core LONG sizing / binding-constraint tests
# --------------------------------------------------------------------------- #


def test_valid_long_sizing_produces_sized_result() -> None:
    r = ENGINE.evaluate(
        entry_actionability=_actionable(), currentness=_CURRENT, capital_policy=_policy(), instrument_lot_size=1, evaluated_at=AS_OF,
    )
    assert r.state is PositionSizingState.SIZED
    assert r.reason_codes == ()
    assert r.recommended_quantity is not None and r.recommended_quantity > 0
    assert r.per_share_risk == Decimal("2")


def test_risk_budget_binding() -> None:
    # risk_budget=1000, per_share_risk=2 -> risk_quantity=500 (smallest)
    # max_position_value=50000 -> max_value_quantity=500 (tie by construction avoided below)
    r = ENGINE.evaluate(
        entry_actionability=_actionable(),
        currentness=_CURRENT, capital_policy=_policy(total="100000", risk_pct="1.0", max_value_pct="90.0"),
        instrument_lot_size=1, evaluated_at=AS_OF,
    )
    assert r.state is PositionSizingState.SIZED
    assert r.binding_constraints == (BindingConstraint.RISK_BUDGET,)
    assert r.recommended_quantity == r.risk_quantity


def test_max_position_value_binding() -> None:
    r = ENGINE.evaluate(
        entry_actionability=_actionable(),
        currentness=_CURRENT, capital_policy=_policy(total="100000", risk_pct="1.0", max_value_pct="10.0"),
        instrument_lot_size=1, evaluated_at=AS_OF,
    )
    assert r.state is PositionSizingState.SIZED
    assert r.binding_constraints == (BindingConstraint.MAX_POSITION_VALUE,)
    assert r.recommended_quantity == r.max_value_quantity


def test_theoretical_capital_co_binds_with_max_value_at_full_deployment() -> None:
    # theoretical_available_capital == total_deployable_capital always,
    # and max_position_value = total * max_value_pct/100 <= total for any
    # max_value_pct <= 100% -- so theoretical_capital_quantity >=
    # max_value_quantity ALWAYS, with equality only when max_value_pct
    # == 100% (full deployment allowed). THEORETICAL_CAPITAL can
    # therefore never be the UNIQUE tightest constraint; it can only
    # co-bind with MAX_POSITION_VALUE at that boundary. risk_pct=100%
    # keeps RISK_BUDGET from binding (risk_quantity=500, well above 10).
    r = ENGINE.evaluate(
        entry_actionability=_actionable(),
        currentness=_CURRENT, capital_policy=_policy(total="1000", risk_pct="100.0", max_value_pct="100.0"),
        instrument_lot_size=1, evaluated_at=AS_OF,
    )
    assert r.state is PositionSizingState.SIZED
    assert set(r.binding_constraints) == {BindingConstraint.MAX_POSITION_VALUE, BindingConstraint.THEORETICAL_CAPITAL}
    assert r.recommended_quantity == r.theoretical_capital_quantity == r.max_value_quantity == Decimal("10")


def test_two_way_co_binding_reports_both_constraints() -> None:
    # entry=100, per_share_risk=2, total=100000.
    # risk_pct chosen so risk_quantity == max_value_quantity exactly.
    # max_value_pct=20% -> max_position_value=20000 -> max_value_quantity=200.
    # risk_pct=0.4% -> risk_budget=400 -> risk_quantity = 400/2 = 200.
    r = ENGINE.evaluate(
        entry_actionability=_actionable(),
        currentness=_CURRENT, capital_policy=_policy(total="100000", risk_pct="0.4", max_value_pct="20.0"),
        instrument_lot_size=1, evaluated_at=AS_OF,
    )
    assert r.state is PositionSizingState.SIZED
    assert r.risk_quantity == r.max_value_quantity == Decimal("200")
    assert set(r.binding_constraints) == {BindingConstraint.RISK_BUDGET, BindingConstraint.MAX_POSITION_VALUE}
    assert r.recommended_quantity == Decimal("200")


def test_lot_size_floor_rounds_down_to_whole_lots() -> None:
    # per_share_risk=2, risk_budget=1000 (1% of 100000) -> raw 500 shares;
    # with lot_size=7, floor(500/7)*7 = 71*7 = 497.
    r = ENGINE.evaluate(
        entry_actionability=_actionable(),
        currentness=_CURRENT, capital_policy=_policy(total="100000", risk_pct="1.0", max_value_pct="90.0"),
        instrument_lot_size=7, evaluated_at=AS_OF,
    )
    assert r.state is PositionSizingState.SIZED
    assert r.risk_quantity == Decimal("497")
    assert r.risk_quantity % 7 == 0


def test_zero_quantity_never_forced_to_minimum_lot() -> None:
    r = ENGINE.evaluate(
        entry_actionability=_actionable(),
        currentness=_CURRENT, capital_policy=_policy(total="50", risk_pct="1.0", max_value_pct="10.0"),
        instrument_lot_size=1, evaluated_at=AS_OF,
    )
    assert r.state is PositionSizingState.ZERO_QUANTITY_UNDER_POLICY
    assert r.reason_codes == (PositionSizingReasonCode.ZERO_QUANTITY_UNDER_POLICY,)
    assert r.recommended_quantity == Decimal("0")
    assert r.recommended_position_value == Decimal("0.00")
    assert r.capital_at_risk == Decimal("0.00")
    # Candidate quantities were still genuinely computed (not None).
    assert r.risk_quantity is not None and r.max_value_quantity is not None
    assert r.binding_constraints  # non-empty even though quantity is 0


def test_derived_value_invariants_hold_for_sized_result() -> None:
    r = ENGINE.evaluate(
        entry_actionability=_actionable(), currentness=_CURRENT, capital_policy=_policy(), instrument_lot_size=1, evaluated_at=AS_OF,
    )
    assert r.state is PositionSizingState.SIZED
    assert r.capital_at_risk <= r.risk_budget_amount
    assert r.recommended_position_value <= r.max_position_value
    assert r.recommended_position_value <= r.theoretical_available_capital


# --------------------------------------------------------------------------- #
# Direction scope
# --------------------------------------------------------------------------- #


def test_short_direction_refused_with_unvalidated_direction_reason() -> None:
    ea = _actionable(direction=Direction.SHORT, entry_price=Decimal("100"), invalidation_level=Decimal("102"))
    r = ENGINE.evaluate(entry_actionability=ea, currentness=_CURRENT, capital_policy=_policy(), instrument_lot_size=1, evaluated_at=AS_OF)
    assert r.state is PositionSizingState.NOT_SIZED
    assert r.reason_codes == (PositionSizingReasonCode.UNVALIDATED_DIRECTION,)
    assert r.recommended_quantity is None
    # Geometry is still echoed for explainability even though refused.
    assert r.direction is Direction.SHORT
    assert r.entry_reference_price == Decimal("100")
    assert r.per_share_risk == Decimal("2")


def test_none_direction_raises_contract_error_defensively() -> None:
    """`direction == NONE` while `state == ACTIONABLE` is an impossible
    combination `EntryActionability.__post_init__` itself forbids --
    the engine treats encountering one (only reachable by bypassing that
    validation, as this test does) as a contract error, never a
    gracefully-reported `PositionSizing` result, mirroring
    `EntryActionabilityEngine._validate_binding`'s own "reject an
    impossible supplied combination" precedent."""
    ea = _illegal_actionable_direction_none()
    with pytest.raises(ValueError):
        ENGINE.evaluate(entry_actionability=ea, currentness=_CURRENT, capital_policy=_policy(), instrument_lot_size=1, evaluated_at=AS_OF)


# --------------------------------------------------------------------------- #
# Currentness (Owner correction, 2026-09-07, issue 1): a persisted
# ACTIONABLE verdict is a methodology result at evaluation time, never a
# live-currentness guarantee. The engine never computes currentness
# itself (no clock/repository/provider/session read) -- it only gates on
# an already-derived `CurrentnessResult` supplied by the caller, exactly
# as produced by the real, unmodified `is_currently_usable(...)`.
# --------------------------------------------------------------------------- #


def test_current_actionable_proceeds_to_sizing() -> None:
    r = ENGINE.evaluate(
        entry_actionability=_actionable(), currentness=_CURRENT, capital_policy=_policy(),
        instrument_lot_size=1, evaluated_at=AS_OF,
    )
    assert r.state is PositionSizingState.SIZED


def test_stale_currentness_returns_not_sized_upstream_not_current() -> None:
    r = ENGINE.evaluate(
        entry_actionability=_actionable(),
        currentness=_non_current(EntryActionabilityCurrentness.STALE),
        capital_policy=_policy(), instrument_lot_size=1, evaluated_at=AS_OF,
    )
    assert r.state is PositionSizingState.NOT_SIZED
    assert r.reason_codes == (PositionSizingReasonCode.UPSTREAM_NOT_CURRENT,)
    # Geometry is still echoed for explainability even though refused.
    assert r.entry_reference_price == Decimal("100")
    assert r.per_share_risk == Decimal("2")
    # Policy was never inspected for a non-current opportunity.
    assert r.policy_version is None


def test_superseded_currentness_returns_not_sized_upstream_not_current() -> None:
    r = ENGINE.evaluate(
        entry_actionability=_actionable(),
        currentness=_non_current(EntryActionabilityCurrentness.SUPERSEDED),
        capital_policy=_policy(), instrument_lot_size=1, evaluated_at=AS_OF,
    )
    assert r.state is PositionSizingState.NOT_SIZED
    assert r.reason_codes == (PositionSizingReasonCode.UPSTREAM_NOT_CURRENT,)
    assert r.policy_version is None


def test_session_closed_currentness_returns_not_sized_upstream_not_current() -> None:
    r = ENGINE.evaluate(
        entry_actionability=_actionable(),
        currentness=_non_current(EntryActionabilityCurrentness.SESSION_CLOSED),
        capital_policy=_policy(), instrument_lot_size=1, evaluated_at=AS_OF,
    )
    assert r.state is PositionSizingState.NOT_SIZED
    assert r.reason_codes == (PositionSizingReasonCode.UPSTREAM_NOT_CURRENT,)
    assert r.policy_version is None


def test_currentness_gate_precedes_capital_policy_check() -> None:
    """A non-current opportunity with NO policy supplied at all must
    still report UPSTREAM_NOT_CURRENT, never CAPITAL_POLICY_UNAVAILABLE
    -- proving currentness is checked first (per the Owner's own
    explicit evaluation-order example list) and policy is never even
    inspected for a non-current opportunity."""
    r = ENGINE.evaluate(
        entry_actionability=_actionable(),
        currentness=_non_current(EntryActionabilityCurrentness.STALE),
        capital_policy=None, instrument_lot_size=1, evaluated_at=AS_OF,
    )
    assert r.reason_codes == (PositionSizingReasonCode.UPSTREAM_NOT_CURRENT,)


def test_methodology_not_actionable_currentness_also_refuses_sizing() -> None:
    """A caller-supplied `METHODOLOGY_NOT_ACTIONABLE` currentness verdict
    (the status `is_currently_usable` itself returns for a non-ACTIONABLE
    artifact) is still treated as "not CURRENT" by this engine's own
    generic gate -- any status other than CURRENT refuses sizing."""
    r = ENGINE.evaluate(
        entry_actionability=_actionable(),
        currentness=_non_current(EntryActionabilityCurrentness.METHODOLOGY_NOT_ACTIONABLE),
        capital_policy=_policy(), instrument_lot_size=1, evaluated_at=AS_OF,
    )
    assert r.state is PositionSizingState.NOT_SIZED
    assert r.reason_codes == (PositionSizingReasonCode.UPSTREAM_NOT_CURRENT,)


# --------------------------------------------------------------------------- #
# Policy / geometry availability
# --------------------------------------------------------------------------- #


def test_missing_capital_policy_returns_not_sized() -> None:
    r = ENGINE.evaluate(
        entry_actionability=_actionable(), currentness=_CURRENT, capital_policy=None, instrument_lot_size=1, evaluated_at=AS_OF,
    )
    assert r.state is PositionSizingState.NOT_SIZED
    assert r.reason_codes == (PositionSizingReasonCode.CAPITAL_POLICY_UNAVAILABLE,)
    assert r.policy_version is None
    assert r.risk_quantity is None
    # Geometry is still echoed even though policy is unavailable.
    assert r.per_share_risk == Decimal("2")


def test_upstream_not_actionable_returns_not_sized_without_reading_evidence() -> None:
    r = ENGINE.evaluate(
        entry_actionability=_not_actionable(), currentness=_CURRENT, capital_policy=_policy(), instrument_lot_size=1, evaluated_at=AS_OF,
    )
    assert r.state is PositionSizingState.NOT_SIZED
    assert r.reason_codes == (PositionSizingReasonCode.UPSTREAM_NOT_ACTIONABLE,)
    assert r.direction is None
    assert r.entry_reference_price is None
    assert r.per_share_risk is None
    assert r.evidence_as_of is None


def test_invalid_risk_geometry_returns_not_sized_defensively() -> None:
    ea = _illegal_actionable_invalid_geometry()
    r = ENGINE.evaluate(entry_actionability=ea, currentness=_CURRENT, capital_policy=_policy(version="policy-v3"), instrument_lot_size=1, evaluated_at=AS_OF)
    assert r.state is PositionSizingState.NOT_SIZED
    assert r.reason_codes == (PositionSizingReasonCode.INVALID_RISK_GEOMETRY,)
    assert r.per_share_risk is not None and r.per_share_risk <= 0
    # Owner correction, 2026-09-07, §2: a real CapitalPolicy was already
    # confirmed available before this defensive geometry check runs, so
    # its version genuinely participated and must be preserved, never
    # blindly erased.
    assert r.policy_version == "policy-v3"


def test_evaluate_rejects_naive_evaluated_at() -> None:
    with pytest.raises(ValueError):
        ENGINE.evaluate(
            entry_actionability=_actionable(), currentness=_CURRENT, capital_policy=_policy(),
            instrument_lot_size=1, evaluated_at=datetime(2026, 9, 7, 10, 0),
        )


def test_evaluate_rejects_lot_size_below_one() -> None:
    with pytest.raises(ValueError):
        ENGINE.evaluate(
            entry_actionability=_actionable(), currentness=_CURRENT, capital_policy=_policy(),
            instrument_lot_size=0, evaluated_at=AS_OF,
        )


# --------------------------------------------------------------------------- #
# Decimal-only arithmetic / provenance / determinism
# --------------------------------------------------------------------------- #


def test_all_numeric_fields_are_decimal_never_float() -> None:
    r = ENGINE.evaluate(
        entry_actionability=_actionable(), currentness=_CURRENT, capital_policy=_policy(), instrument_lot_size=1, evaluated_at=AS_OF,
    )
    for field in (
        "per_share_risk", "risk_budget_amount", "max_position_value",
        "theoretical_available_capital", "risk_quantity", "max_value_quantity",
        "theoretical_capital_quantity", "recommended_quantity",
        "recommended_position_value", "capital_at_risk",
    ):
        value = getattr(r, field)
        assert isinstance(value, Decimal), f"{field} is {type(value)}, not Decimal"


def test_exact_upstream_provenance_preserved() -> None:
    ea = _actionable()
    r = ENGINE.evaluate(entry_actionability=ea, currentness=_CURRENT, capital_policy=_policy(), instrument_lot_size=1, evaluated_at=AS_OF)
    assert r.instrument_id == ea.instrument_id
    assert r.session_date == ea.session_date
    assert r.entry_qualification_as_of == ea.entry_qualification_as_of
    assert r.decision_id == ea.decision_id
    assert r.entry_qualification_methodology_version == ea.entry_qualification_methodology_version
    assert r.entry_actionability_as_of == ea.entry_actionability_as_of
    assert r.entry_actionability_methodology_version == ea.entry_actionability_methodology_version
    assert r.evidence_as_of == ea.evidence_as_of
    assert r.sizing_methodology_version == DEFAULT_METHODOLOGY_VERSION


def test_capital_policy_version_echoed_in_result() -> None:
    r = ENGINE.evaluate(
        entry_actionability=_actionable(), currentness=_CURRENT, capital_policy=_policy(version="policy-v7"),
        instrument_lot_size=1, evaluated_at=AS_OF,
    )
    assert r.policy_version == "policy-v7"


# --------------------------------------------------------------------------- #
# Policy-version identity (Owner correction, 2026-09-07, issue 2): two
# sizing assertions over the exact same upstream EntryActionability
# checkpoint under two different CapitalPolicy versions are genuinely
# different assertions and must never share an identity, even though a
# policy-value change must never bump sizing_methodology_version.
# --------------------------------------------------------------------------- #


def test_identity_tuple_differs_across_policy_versions_for_same_entry_actionability() -> None:
    ea = _actionable()
    r1 = ENGINE.evaluate(
        entry_actionability=ea, currentness=_CURRENT, capital_policy=_policy(version="policy-v1"),
        instrument_lot_size=1, evaluated_at=AS_OF,
    )
    r2 = ENGINE.evaluate(
        entry_actionability=ea, currentness=_CURRENT, capital_policy=_policy(version="policy-v2"),
        instrument_lot_size=1, evaluated_at=AS_OF,
    )
    assert r1.identity_tuple() != r2.identity_tuple()
    assert r1 != r2


def test_sizing_methodology_version_unchanged_across_policy_versions() -> None:
    """A policy-value change must NOT masquerade as a methodology-version
    change -- the two dimensions remain independent even though both now
    participate in the artifact's own composite identity."""
    ea = _actionable()
    r1 = ENGINE.evaluate(
        entry_actionability=ea, currentness=_CURRENT, capital_policy=_policy(version="policy-v1"),
        instrument_lot_size=1, evaluated_at=AS_OF,
    )
    r2 = ENGINE.evaluate(
        entry_actionability=ea, currentness=_CURRENT, capital_policy=_policy(version="policy-v2"),
        instrument_lot_size=1, evaluated_at=AS_OF,
    )
    assert r1.sizing_methodology_version == r2.sizing_methodology_version == DEFAULT_METHODOLOGY_VERSION


def test_different_policy_versions_can_change_recommended_quantity() -> None:
    """The example from the Owner's own correction: the same checkpoint
    under two policy versions can genuinely produce different
    quantities -- proving the identity difference is not merely
    formal but reflects a real, different sizing assertion."""
    ea = _actionable()
    r1 = ENGINE.evaluate(
        entry_actionability=ea, currentness=_CURRENT,
        capital_policy=_policy(version="policy-v1", risk_pct="1.0", max_value_pct="90.0"),
        instrument_lot_size=1, evaluated_at=AS_OF,
    )
    r2 = ENGINE.evaluate(
        entry_actionability=ea, currentness=_CURRENT,
        capital_policy=_policy(version="policy-v2", risk_pct="0.5", max_value_pct="90.0"),
        instrument_lot_size=1, evaluated_at=AS_OF,
    )
    assert r1.recommended_quantity != r2.recommended_quantity
    assert r1.identity_tuple() != r2.identity_tuple()


def test_policy_version_none_for_upstream_not_current() -> None:
    r = ENGINE.evaluate(
        entry_actionability=_actionable(),
        currentness=_non_current(EntryActionabilityCurrentness.STALE),
        capital_policy=_policy(), instrument_lot_size=1, evaluated_at=AS_OF,
    )
    assert r.policy_version is None


def test_policy_version_none_for_upstream_not_actionable() -> None:
    r = ENGINE.evaluate(
        entry_actionability=_not_actionable(), currentness=_CURRENT, capital_policy=_policy(),
        instrument_lot_size=1, evaluated_at=AS_OF,
    )
    assert r.policy_version is None


def test_policy_version_none_for_unvalidated_direction() -> None:
    ea = _actionable(direction=Direction.SHORT, entry_price=Decimal("100"), invalidation_level=Decimal("102"))
    r = ENGINE.evaluate(
        entry_actionability=ea, currentness=_CURRENT, capital_policy=_policy(),
        instrument_lot_size=1, evaluated_at=AS_OF,
    )
    assert r.policy_version is None


def test_deterministic_repeat_produces_identical_result() -> None:
    ea = _actionable()
    policy = _policy()
    r1 = ENGINE.evaluate(entry_actionability=ea, currentness=_CURRENT, capital_policy=policy, instrument_lot_size=1, evaluated_at=AS_OF)
    r2 = ENGINE.evaluate(entry_actionability=ea, currentness=_CURRENT, capital_policy=policy, instrument_lot_size=1, evaluated_at=AS_OF)
    assert r1 == r2


# --------------------------------------------------------------------------- #
# GOAL_BANDS_ONLY / RR_INFORMATIONAL_ONLY preservation, no multiplier scaling
# --------------------------------------------------------------------------- #


def test_engine_source_never_reads_reward_t1_t2_rr() -> None:
    """No sizing multiplier may use RR/T1/T2 attractiveness -- proven
    directly by source scan of the engine's own CODE (module docstring
    excluded, since it legitimately explains this exclusion in prose),
    not merely by absence from one example's output (see also
    `test_extreme_rr_does_not_change_sizing_result`, which proves the
    same thing behaviorally)."""
    tree = ast.parse(inspect.getsource(engine_module))
    tree.body = [
        node for node in tree.body
        if not (isinstance(node, ast.Expr) and isinstance(node.value, ast.Constant))
    ]
    code_only = ast.unparse(tree)
    for forbidden in (".reward", "reward_risk_to_t1", "reward_risk_to_t2", "t1_price", "t2_price"):
        assert forbidden not in code_only, f"engine code references {forbidden!r}"


def test_engine_source_never_references_score_confidence_conviction_rs_rvol() -> None:
    src = inspect.getsource(engine_module)
    lowered = src.lower()
    for forbidden in ("score", "confidence", "conviction", "rs_pct", "rvol", "hit_rate", "kelly"):
        assert forbidden not in lowered, f"engine source references forbidden concept {forbidden!r}"


def test_extreme_rr_does_not_change_sizing_result() -> None:
    ea_normal = _actionable()
    ea_extreme_rr = EntryActionability(
        **{
            **{f: getattr(ea_normal, f) for f in ea_normal.__dataclass_fields__},
            "reward": RewardReference(
                t1_price=Decimal("200"), t2_price=Decimal("300"), basis=RewardBasis.GOAL_BANDS_ONLY,
                reward_risk_to_t1=Decimal("50"), reward_risk_to_t2=Decimal("100"),
            ),
        }
    )
    policy = _policy()
    r1 = ENGINE.evaluate(entry_actionability=ea_normal, currentness=_CURRENT, capital_policy=policy, instrument_lot_size=1, evaluated_at=AS_OF)
    r2 = ENGINE.evaluate(entry_actionability=ea_extreme_rr, currentness=_CURRENT, capital_policy=policy, instrument_lot_size=1, evaluated_at=AS_OF)
    assert r1.recommended_quantity == r2.recommended_quantity
    assert r1.binding_constraints == r2.binding_constraints


# --------------------------------------------------------------------------- #
# No provider/persistence/legacy-pipeline coupling
# --------------------------------------------------------------------------- #


def test_engine_never_calls_provider_network_or_persistence() -> None:
    src = inspect.getsource(engine_module) + inspect.getsource(models_module)
    lowered = src.lower()
    for forbidden in ("kite", "requests.", "httpx.", "urllib.request", "self._repo", "save_position_sizing", "insert into"):
        assert forbidden not in lowered


def test_engine_never_imports_dormant_legacy_sizing_pipeline() -> None:
    """ID-9 must not become a second independently-evolving canonical
    PositionSizingEngine alongside the dormant P5.2/P5.3 pipeline --
    proven by source scan that the new module imports nothing from
    `athena.allocation`/`athena.sizing`/`athena.orders`/`athena.brokers`/
    `athena.execution`."""
    src = inspect.getsource(engine_module) + inspect.getsource(models_module)
    for forbidden in (
        "from athena.allocation", "from athena.sizing", "from athena.orders",
        "from athena.brokers", "from athena.execution", "import athena.allocation",
        "import athena.sizing", "import athena.orders", "import athena.brokers",
        "import athena.execution",
    ):
        assert forbidden not in src


# --------------------------------------------------------------------------- #
# Domain model invariants (mirrors EntryActionability's own construction-
# integrity test style)
# --------------------------------------------------------------------------- #


def _sized_kwargs(**overrides) -> dict:
    base = dict(
        instrument_id=IID, session_date=DAY, entry_qualification_as_of=AS_OF,
        decision_id="dec-1", entry_qualification_methodology_version="entry-qualification-v0",
        entry_actionability_as_of=AS_OF, entry_actionability_methodology_version="entry-actionability-v0",
        position_sizing_as_of=AS_OF, sizing_methodology_version=DEFAULT_METHODOLOGY_VERSION,
        state=PositionSizingState.SIZED, reason_codes=(),
        direction=Direction.LONG, entry_reference_price=Decimal("100"),
        operative_invalidation_level=Decimal("98"), per_share_risk=Decimal("2"),
        policy_version="policy-v1", risk_budget_amount=Decimal("1000.00"),
        max_position_value=Decimal("10000.00"), theoretical_available_capital=Decimal("100000"),
        risk_quantity=Decimal("500"), max_value_quantity=Decimal("100"),
        theoretical_capital_quantity=Decimal("1000"),
        recommended_quantity=Decimal("100"), recommended_position_value=Decimal("10000.00"),
        capital_at_risk=Decimal("200.00"),
        binding_constraints=(BindingConstraint.MAX_POSITION_VALUE,),
        evidence_as_of=AS_OF, evaluated_at=AS_OF, explanation="test",
    )
    base.update(overrides)
    return base


def test_domain_rejects_sized_with_nonempty_reason_codes() -> None:
    with pytest.raises(ValueError):
        PositionSizing(**_sized_kwargs(reason_codes=(PositionSizingReasonCode.ZERO_QUANTITY_UNDER_POLICY,)))


def test_domain_rejects_sized_with_zero_quantity() -> None:
    with pytest.raises(ValueError):
        PositionSizing(**_sized_kwargs(recommended_quantity=Decimal("0")))


def test_domain_rejects_zero_quantity_state_with_positive_quantity() -> None:
    with pytest.raises(ValueError):
        PositionSizing(**_sized_kwargs(
            state=PositionSizingState.ZERO_QUANTITY_UNDER_POLICY,
            reason_codes=(PositionSizingReasonCode.ZERO_QUANTITY_UNDER_POLICY,),
        ))


def test_domain_rejects_not_sized_with_value_objects_present() -> None:
    with pytest.raises(ValueError):
        PositionSizing(**_sized_kwargs(
            state=PositionSizingState.NOT_SIZED,
            reason_codes=(PositionSizingReasonCode.CAPITAL_POLICY_UNAVAILABLE,),
        ))


def test_domain_rejects_not_sized_with_foreign_reason_code() -> None:
    kwargs = _sized_kwargs(
        state=PositionSizingState.NOT_SIZED, reason_codes=(PositionSizingReasonCode.ZERO_QUANTITY_UNDER_POLICY,),
        policy_version=None, risk_budget_amount=None, max_position_value=None,
        theoretical_available_capital=None, risk_quantity=None, max_value_quantity=None,
        theoretical_capital_quantity=None, recommended_quantity=None,
        recommended_position_value=None, capital_at_risk=None, binding_constraints=(),
    )
    with pytest.raises(ValueError):
        PositionSizing(**kwargs)


def test_domain_rejects_upstream_not_actionable_with_geometry_present() -> None:
    kwargs = _sized_kwargs(
        state=PositionSizingState.NOT_SIZED,
        reason_codes=(PositionSizingReasonCode.UPSTREAM_NOT_ACTIONABLE,),
        policy_version=None, risk_budget_amount=None, max_position_value=None,
        theoretical_available_capital=None, risk_quantity=None, max_value_quantity=None,
        theoretical_capital_quantity=None, recommended_quantity=None,
        recommended_position_value=None, capital_at_risk=None, binding_constraints=(),
    )
    with pytest.raises(ValueError):
        PositionSizing(**kwargs)  # direction/entry_reference_price/etc. still populated


def test_domain_rejects_not_sized_policy_version_when_not_participated() -> None:
    """A NOT_SIZED verdict whose reason is UPSTREAM_NOT_ACTIONABLE (policy
    never inspected) must not carry a policy_version -- proven directly
    against the domain model's own construction invariant, independent
    of the engine."""
    kwargs = _sized_kwargs(
        state=PositionSizingState.NOT_SIZED,
        reason_codes=(PositionSizingReasonCode.CAPITAL_POLICY_UNAVAILABLE,),
        risk_budget_amount=None, max_position_value=None,
        theoretical_available_capital=None, risk_quantity=None, max_value_quantity=None,
        theoretical_capital_quantity=None, recommended_quantity=None,
        recommended_position_value=None, capital_at_risk=None, binding_constraints=(),
        # policy_version left at the fixture default ("policy-v1") -- illegal here.
    )
    with pytest.raises(ValueError):
        PositionSizing(**kwargs)


def test_domain_requires_policy_version_for_invalid_risk_geometry() -> None:
    """INVALID_RISK_GEOMETRY is reached only after policy availability is
    confirmed -- the domain model must reject a construction that omits
    policy_version for this specific reason."""
    kwargs = _sized_kwargs(
        state=PositionSizingState.NOT_SIZED,
        reason_codes=(PositionSizingReasonCode.INVALID_RISK_GEOMETRY,),
        policy_version=None,
        risk_budget_amount=None, max_position_value=None,
        theoretical_available_capital=None, risk_quantity=None, max_value_quantity=None,
        theoretical_capital_quantity=None, recommended_quantity=None,
        recommended_position_value=None, capital_at_risk=None, binding_constraints=(),
    )
    with pytest.raises(ValueError):
        PositionSizing(**kwargs)


def test_domain_accepts_invalid_risk_geometry_with_policy_version_present() -> None:
    """The legal counterpart of the rejection above -- INVALID_RISK_GEOMETRY
    WITH a policy_version present constructs cleanly."""
    kwargs = _sized_kwargs(
        state=PositionSizingState.NOT_SIZED,
        reason_codes=(PositionSizingReasonCode.INVALID_RISK_GEOMETRY,),
        policy_version="policy-v1",
        risk_budget_amount=None, max_position_value=None,
        theoretical_available_capital=None, risk_quantity=None, max_value_quantity=None,
        theoretical_capital_quantity=None, recommended_quantity=None,
        recommended_position_value=None, capital_at_risk=None, binding_constraints=(),
    )
    sizing = PositionSizing(**kwargs)
    assert sizing.policy_version == "policy-v1"


def test_domain_identity_tuple_includes_policy_version() -> None:
    a = PositionSizing(**_sized_kwargs(policy_version="policy-v1"))
    b = PositionSizing(**_sized_kwargs(policy_version="policy-v2"))
    assert a.identity_tuple() != b.identity_tuple()
    # Everything else about the identity is identical -- only the last
    # tuple element (policy_version) differs.
    assert a.identity_tuple()[:-1] == b.identity_tuple()[:-1]


def test_domain_rejects_capital_at_risk_exceeding_budget() -> None:
    with pytest.raises(ValueError):
        PositionSizing(**_sized_kwargs(capital_at_risk=Decimal("999999.00")))


def test_capital_policy_rejects_non_positive_capital() -> None:
    with pytest.raises(ValueError):
        CapitalPolicy(
            total_deployable_capital=Decimal("0"), risk_budget_per_trade_pct=Decimal("1"),
            max_position_value_pct=Decimal("10"), policy_version="v1",
        )


def test_capital_policy_rejects_out_of_range_percentages() -> None:
    with pytest.raises(ValueError):
        CapitalPolicy(
            total_deployable_capital=Decimal("1000"), risk_budget_per_trade_pct=Decimal("150"),
            max_position_value_pct=Decimal("10"), policy_version="v1",
        )


def test_capital_policy_rejects_empty_version() -> None:
    with pytest.raises(ValueError):
        CapitalPolicy(
            total_deployable_capital=Decimal("1000"), risk_budget_per_trade_pct=Decimal("1"),
            max_position_value_pct=Decimal("10"), policy_version="",
        )
