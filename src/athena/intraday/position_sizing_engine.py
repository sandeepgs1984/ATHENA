"""Position Sizing Engine (ID-9 V0) — pure, deterministic, side-effect-free.

`PositionSizingV0Engine.evaluate(...)` converts one exact, already-bound
`EntryActionability` plus an explicit `CapitalPolicy` into one immutable
`PositionSizing`. Deliberately named apart from `athena.sizing.engine
.PositionSizingEngine` (the dormant P5.3 engine — see the ID-9
implementation report §3 for the full disposition) to keep the two
architecturally and nominally distinct: no shared base class, no shared
domain model, no runtime dependency in either direction.

Mirrors `EntryActionabilityEngine`'s own established contract (ID-7C)
exactly: no repository/provider/network/clock read, O(1) per candidate,
`_validate_binding`-style upstream-identity trust (the caller supplies
one already-resolved `EntryActionability`, never re-fetched here), and
upstream-gate-then-methodology evaluation order.

V0 scope, frozen by the Owner's ID-9 core-implementation authorization:
LONG only (`LONG_VALIDATED_SHORT_UNVALIDATED`); risk-budget + max-
position-value + theoretical-deployable-capital as the only three
sizing constraints; `GOAL_BANDS_ONLY`/`RR_INFORMATIONAL_ONLY` preserved
(nothing here reads `EntryActionability.reward` at all — RR/T1/T2 play
no role in V0 sizing math); no liquidity/concentration/portfolio-risk
gate; quantity always floored to whole lots, never rounded up, never
forced to a minimum of one lot.
"""

from __future__ import annotations

from datetime import datetime
from decimal import ROUND_DOWN, Decimal

from athena.domain.enums import Direction
from athena.intraday.entry_actionability_models import (
    EntryActionability,
    EntryActionabilityState,
)
from athena.intraday.position_sizing_models import (
    DEFAULT_METHODOLOGY_VERSION,
    MONEY_PLACES,
    BindingConstraint,
    CapitalPolicy,
    PositionSizing,
    PositionSizingReasonCode,
    PositionSizingState,
)

_HUNDRED = Decimal("100")


def _floor_money(value: Decimal) -> Decimal:
    """Floor (never round up) a monetary amount to 2 decimal places — a
    budget/cap ceiling must never be inflated by rounding."""
    return value.quantize(MONEY_PLACES, rounding=ROUND_DOWN)


def _floor_to_lot(raw_quantity: Decimal, lot_size: int) -> Decimal:
    """Floor ``raw_quantity`` DOWN to the nearest whole multiple of
    ``lot_size`` — never rounds up, never forces a minimum of one lot.
    For NSE/BSE cash equities `lot_size` is always 1 today (ID-9
    discovery §14), collapsing this to a plain whole-share floor; the
    division is still performed generically so a future non-1 lot size
    (if one is ever genuinely observed) is handled correctly without
    code changes here."""
    if raw_quantity <= 0:
        return Decimal("0")
    lots = int(raw_quantity // Decimal(lot_size))
    return Decimal(lots * lot_size)


class PositionSizingV0Engine:
    """Pure V0 position-sizing evaluator. Stateless — safe to share a
    single instance across every instrument/cycle, exactly like
    `EntryActionabilityEngine`."""

    def evaluate(
        self,
        *,
        entry_actionability: EntryActionability,
        capital_policy: CapitalPolicy | None,
        instrument_lot_size: int,
        evaluated_at: datetime,
    ) -> PositionSizing:
        if evaluated_at.tzinfo is None:
            raise ValueError("PositionSizingV0Engine.evaluate: evaluated_at must be timezone-aware")
        if instrument_lot_size < 1:
            raise ValueError(
                f"PositionSizingV0Engine.evaluate: instrument_lot_size must be >= 1, "
                f"got {instrument_lot_size}"
            )

        identity = dict(
            instrument_id=entry_actionability.instrument_id,
            session_date=entry_actionability.session_date,
            entry_qualification_as_of=entry_actionability.entry_qualification_as_of,
            decision_id=entry_actionability.decision_id,
            entry_qualification_methodology_version=entry_actionability.entry_qualification_methodology_version,
            entry_actionability_as_of=entry_actionability.entry_actionability_as_of,
            entry_actionability_methodology_version=entry_actionability.entry_actionability_methodology_version,
            position_sizing_as_of=entry_actionability.entry_actionability_as_of,
            sizing_methodology_version=DEFAULT_METHODOLOGY_VERSION,
            evaluated_at=evaluated_at,
        )

        # ---- upstream eligibility: exact bound EntryActionability must
        # itself be ACTIONABLE. Checked first, before direction/policy,
        # mirroring EntryActionabilityEngine's own upstream-gates-first
        # ordering (ID-7C.2's own corrected precedent) -- no
        # candidate/policy evidence is ever inspected for an ineligible
        # upstream artifact. ----
        if entry_actionability.state is not EntryActionabilityState.ACTIONABLE:
            return self._not_sized(
                identity,
                reason_codes=(PositionSizingReasonCode.UPSTREAM_NOT_ACTIONABLE,),
                direction=None, entry_reference_price=None,
                operative_invalidation_level=None, per_share_risk=None,
                evidence_as_of=None,
                explanation=(
                    "Upstream EntryActionability is not ACTIONABLE "
                    f"(state={entry_actionability.state.value}) -- sizing not attempted."
                ),
            )

        # From here on the upstream artifact is genuinely ACTIONABLE, so
        # its value objects are guaranteed present and its own
        # `_validate_risk_geometry` invariant already guarantees
        # `operative_invalidation.level` is on the structurally-correct
        # side of `entry_reference.price` for `direction` -- this
        # engine's own per-share-risk check below is a defensive
        # re-verification, not the primary correctness guarantee.
        assert entry_actionability.entry_reference is not None
        assert entry_actionability.operative_invalidation is not None
        direction = entry_actionability.direction
        entry_price = entry_actionability.entry_reference.price
        invalidation_level = entry_actionability.operative_invalidation.level
        evidence_as_of = entry_actionability.evidence_as_of

        # ---- defensive binding check: EntryActionability's own
        # ACTIONABLE invariant already guarantees `direction` is LONG or
        # SHORT whenever `state == ACTIONABLE` -- `direction == NONE`
        # here would mean the caller handed this engine an object that
        # could never have been legally constructed. This is a contract
        # error (mirrors EntryActionabilityEngine's own
        # `_validate_binding` "reject an impossible supplied
        # combination" precedent), never a gracefully-reported
        # `PositionSizing` result -- `PositionSizing`'s own domain
        # invariant (direction must be LONG/SHORT whenever the upstream
        # artifact reached ACTIONABLE) would reject constructing one
        # anyway. ----
        if direction not in (Direction.LONG, Direction.SHORT):
            raise ValueError(
                "PositionSizingV0Engine.evaluate: entry_actionability.state is ACTIONABLE "
                f"but direction is {direction!r} -- an impossible combination "
                "(EntryActionability's own ACTIONABLE invariant requires LONG or SHORT)"
            )

        # ---- V0 direction scope: LONG only. SHORT is refused, never
        # mechanically sized-and-labeled -- LONG_VALIDATED_SHORT_UNVALIDATED
        # means ID-8's entire outcome-evidence base backing a sizing
        # recommendation has zero validated SHORT observations. ----
        if direction is not Direction.LONG:
            # direction is SHORT here (NONE already rejected above).
            # Geometry validity and direction-validation scope are
            # separate concepts (per the Owner's own instruction): the
            # correctly-signed per-share risk is still computed and
            # echoed for explainability, even though V0 refuses to size
            # SHORT. SHORT's own geometry invariant is
            # `invalidation_level > entry_price`.
            assert direction is Direction.SHORT
            per_share_risk = invalidation_level - entry_price
            return self._not_sized(
                identity,
                reason_codes=(PositionSizingReasonCode.UNVALIDATED_DIRECTION,),
                direction=direction, entry_reference_price=entry_price,
                operative_invalidation_level=invalidation_level,
                per_share_risk=per_share_risk,
                evidence_as_of=evidence_as_of,
                explanation=(
                    f"direction={direction.value} is not validated for ID-9 V0 sizing "
                    "(LONG_VALIDATED_SHORT_UNVALIDATED) -- refused, not sized."
                ),
            )

        # ---- capital policy availability ----
        if capital_policy is None:
            return self._not_sized(
                identity,
                reason_codes=(PositionSizingReasonCode.CAPITAL_POLICY_UNAVAILABLE,),
                direction=direction, entry_reference_price=entry_price,
                operative_invalidation_level=invalidation_level,
                per_share_risk=entry_price - invalidation_level,
                evidence_as_of=evidence_as_of,
                explanation="No CapitalPolicy supplied -- sizing requires an explicit Owner-approved policy.",
            )

        # ---- per-share risk geometry (defensive; structurally
        # guaranteed by EntryActionability's own ACTIONABLE invariant
        # for LONG: invalidation_level < entry_price) ----
        per_share_risk = entry_price - invalidation_level
        if per_share_risk <= 0:
            return self._not_sized(
                identity,
                reason_codes=(PositionSizingReasonCode.INVALID_RISK_GEOMETRY,),
                direction=direction, entry_reference_price=entry_price,
                operative_invalidation_level=invalidation_level,
                per_share_risk=per_share_risk,
                evidence_as_of=evidence_as_of,
                explanation=(
                    f"per_share_risk={per_share_risk} is not strictly positive for LONG -- "
                    "sizing refused (defensive check; should be structurally unreachable "
                    "given EntryActionability's own ACTIONABLE risk-geometry invariant)."
                ),
            )

        # ---- the three V0 constraints, independently computed, never
        # algebraically merged ----
        risk_budget_amount = _floor_money(
            capital_policy.total_deployable_capital * capital_policy.risk_budget_per_trade_pct / _HUNDRED
        )
        max_position_value = _floor_money(
            capital_policy.total_deployable_capital * capital_policy.max_position_value_pct / _HUNDRED
        )
        theoretical_available_capital = capital_policy.total_deployable_capital

        risk_quantity = _floor_to_lot(risk_budget_amount / per_share_risk, instrument_lot_size)
        max_value_quantity = _floor_to_lot(max_position_value / entry_price, instrument_lot_size)
        theoretical_capital_quantity = _floor_to_lot(
            theoretical_available_capital / entry_price, instrument_lot_size
        )

        candidates: tuple[tuple[BindingConstraint, Decimal], ...] = (
            (BindingConstraint.RISK_BUDGET, risk_quantity),
            (BindingConstraint.MAX_POSITION_VALUE, max_value_quantity),
            (BindingConstraint.THEORETICAL_CAPITAL, theoretical_capital_quantity),
        )
        min_quantity = min(q for _, q in candidates)
        # Declaration-order-stable tie report -- never an arbitrary
        # single "winner" when two or more constraints exactly co-bind.
        binding_constraints = tuple(name for name, q in candidates if q == min_quantity)

        common = dict(
            **identity,
            direction=direction, entry_reference_price=entry_price,
            operative_invalidation_level=invalidation_level, per_share_risk=per_share_risk,
            policy_version=capital_policy.policy_version,
            risk_budget_amount=risk_budget_amount, max_position_value=max_position_value,
            theoretical_available_capital=theoretical_available_capital,
            risk_quantity=risk_quantity, max_value_quantity=max_value_quantity,
            theoretical_capital_quantity=theoretical_capital_quantity,
            binding_constraints=binding_constraints,
            evidence_as_of=evidence_as_of,
        )

        if min_quantity <= 0:
            return PositionSizing(
                **common,
                state=PositionSizingState.ZERO_QUANTITY_UNDER_POLICY,
                reason_codes=(PositionSizingReasonCode.ZERO_QUANTITY_UNDER_POLICY,),
                recommended_quantity=Decimal("0"),
                recommended_position_value=Decimal("0.00"),
                capital_at_risk=Decimal("0.00"),
                explanation=(
                    "Every applicable constraint floors below one valid lot "
                    f"(lot_size={instrument_lot_size}) -- binding: "
                    f"{[c.value for c in binding_constraints]}. No quantity is recommended; "
                    "never forced to a minimum of one lot."
                ),
            )

        recommended_position_value = _floor_money(min_quantity * entry_price)
        capital_at_risk = _floor_money(min_quantity * per_share_risk)
        return PositionSizing(
            **common,
            state=PositionSizingState.SIZED,
            reason_codes=(),
            recommended_quantity=min_quantity,
            recommended_position_value=recommended_position_value,
            capital_at_risk=capital_at_risk,
            explanation=(
                f"Sized {min_quantity} units at {entry_price} (position value "
                f"{recommended_position_value}, capital at risk {capital_at_risk}) -- binding: "
                f"{[c.value for c in binding_constraints]}."
            ),
        )

    @staticmethod
    def _not_sized(
        identity: dict[str, object],
        *,
        reason_codes: tuple[PositionSizingReasonCode, ...],
        direction: Direction | None,
        entry_reference_price: Decimal | None,
        operative_invalidation_level: Decimal | None,
        per_share_risk: Decimal | None,
        evidence_as_of: datetime | None,
        explanation: str,
    ) -> PositionSizing:
        return PositionSizing(
            **identity,
            state=PositionSizingState.NOT_SIZED,
            reason_codes=reason_codes,
            direction=direction, entry_reference_price=entry_reference_price,
            operative_invalidation_level=operative_invalidation_level,
            per_share_risk=per_share_risk,
            policy_version=None, risk_budget_amount=None, max_position_value=None,
            theoretical_available_capital=None, risk_quantity=None, max_value_quantity=None,
            theoretical_capital_quantity=None,
            recommended_quantity=None, recommended_position_value=None, capital_at_risk=None,
            binding_constraints=(),
            evidence_as_of=evidence_as_of,
            explanation=explanation,
        )
