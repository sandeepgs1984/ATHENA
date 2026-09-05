"""Entry Actionability pure V0 deterministic evaluator (ID-7C).

Implements — and implements ONLY — the frozen V0 methodology ID-7B/
ID-7B.1/ID-7B.2/ID-7B.2.1 calibrated and ID-7A's domain model encodes:
given one exact canonical `Decision`, one exact bound `EntryQualification`,
and already-computed point-in-time layer-3 market evidence, what was the
`EntryActionability` methodology verdict at that checkpoint?

This is a PURE engine, mirroring `EntryQualificationEngine`'s own
established contract exactly (ID-6B.2): deterministic, side-effect-free,
repository/provider/database/wall-clock/workflow independent. Every input
is explicit; the same immutable inputs always produce the exact same
methodology content (only the injected `evaluated_at` diagnostic
timestamp may legitimately differ between two calls with otherwise
identical inputs). No persistence (`save_entry_actionability` lives on
`SqliteRepository`, ID-7A), no "latest Decision/EQ" resolution (that is a
caller/workflow responsibility, ID-7E), no currentness evaluation (that
is `entry_actionability_currentness.is_currently_usable`, ID-7A), no
`WorkflowStage` wiring (ID-7E), no provider/network call.

Evaluation-time session eligibility is never re-invented here: the bound
`EntryQualification` already carries session eligibility semantics (it
cannot be `QUALIFIED` outside `REGULAR`, ID-6B.1B) — if session made EQ
non-`QUALIFIED`, the result is `NOT_ACTIONABLE` + `UPSTREAM_EQ_NOT_QUALIFIED`,
never a separately invented `SESSION_NOT_ACTIONABLE` reason (ID-7B.2.1
already rejected that code).

Frozen evaluation structure (ID-7A.2's own domain-level invariant,
mirrored here at the point that actually produces it):

    UPSTREAM ELIGIBILITY (Decision == TRADE AND exact EQ == QUALIFIED)
        -> then LAYER-3 EVIDENCE SUFFICIENCY (completed M5 close + VWAP)
            -> then RISK GEOMETRY (VWAP-loss vs. M5-close, direction-aware)
                -> ACTIONABLE

Mandatory V0 layer-3 evidence is deliberately minimal (ID-7B2.1 §14): a
completed M5 checkpoint candle and the session VWAP price. No D1 ATR, no
RS/RVOL/Gap gate, no extension cutoff, no generic support/resistance, no
DarvaX. `IntradaySignalSet.vwap` (`VwapEvidence`, ID-2) deliberately
carries only the categorical relation + `deviation_pct` it was formalized
for — not the raw VWAP price V0's `EntryLocationContext`/
`OperativeInvalidation` value objects need — so this module defines its
own narrow `EntryActionabilityMarketEvidence` input context carrying the
raw price directly (`indicators.calculations.vwap`'s own first return
value) rather than re-deriving it from a wider indicator object, per the
ID-7C authorization's "smallest representation after source audit" and
"no parallel market-data domain" instructions.

Option 1 (canonical-cycle synchronous, ADR-015): V0 sets
`entry_actionability_as_of = entry_qualification.as_of` unconditionally —
the same checkpoint the bound EQ was itself evaluated at. This does NOT
exercise ADR-015's future same-EQ re-evaluation capability (a strictly
later `entry_actionability_as_of` remains structurally valid in the
domain model, ID-7A.1) — V0's methodology has no use for it yet; a later
milestone may introduce a genuine re-evaluation caller without any domain
or engine change required to support it.

Contract-error vs. methodology-UNKNOWN boundary (ID-7C authorization item
37): a Decision/EQ identity mismatch, a malformed input object, or
evidence timestamped after the checkpoint is a programmer/caller
contract violation — this engine raises `ValueError` deterministically,
exactly like `EntryQualificationEngine`'s own `_validate_input_coherence`.
Genuinely missing or geometrically invalid market evidence is a real
methodology outcome (`UNKNOWN`), never converted into a raised exception.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta
from decimal import Decimal

from athena.domain.decision import Decision
from athena.domain.enums import DecisionType, Direction, Timeframe
from athena.domain.market import Candle
from athena.intraday.entry_actionability_models import (
    DEFAULT_METHODOLOGY_VERSION,
    T1_GOAL_BAND_PCT,
    T2_GOAL_BAND_PCT,
    EntryActionability,
    EntryActionabilityReasonCode,
    EntryActionabilityState,
    EntryLocationContext,
    EntryReference,
    EntryReferenceBasis,
    InvalidationBasis,
    OpeningRangeContextBasis,
    OpeningRangeContextReference,
    OperativeInvalidation,
    RewardBasis,
    RewardReference,
)
from athena.intraday.entry_qualification_models import EntryQualification, EntryQualificationState
from athena.intraday.opening_range_models import (
    OpeningRangeEvidence,
    OpeningRangeFormationStatus,
    OpeningRangeWindow,
)
from athena.session.engine import is_candle_completed

#: M5 bar duration. A small, local constant rather than importing
#: `session.engine`'s module-private `_TIMEFRAME_MINUTES` — mirrors that
#: module's own stated rationale (duplicating a 1-entry unit fact is
#: preferable to reaching into another module's private state).
_M5_BAR_DURATION = timedelta(minutes=5)


@dataclass(frozen=True, slots=True)
class EntryActionabilityMarketEvidence:
    """Narrow ID-7C evaluation-input context — exactly the layer-3 market
    evidence the frozen V0 methodology consumes, nothing more (ID-7C
    authorization items 35/36: no parallel market-data domain, no
    over-denormalization). Reuses canonical `Candle`/`OpeningRangeEvidence`
    directly rather than re-modeling them; RS/RVOL/Gap/M15-trend/D1-ATR/
    generic-S-R/other-OR-lifecycle-events are deliberately absent — none
    of them are part of the frozen V0 contract.

    ``completed_m5_close`` must be the exact, already-selected completed
    M5 checkpoint candle — never a forming bar, never a different
    timeframe, never resolved by this engine from a wider series (no
    repository/provider access exists here; the caller is responsible for
    candle selection, e.g. via `athena.session.engine.latest_completed_candle`).
    ``None`` means "no completed M5 checkpoint candle was supplied" — a
    legitimate real-world case (`INSUFFICIENT_EVIDENCE`), not a contract
    error.

    ``session_vwap`` is the raw session VWAP price
    (`indicators.calculations.vwap`'s own first return value) as of the
    same checkpoint. ``None`` means "VWAP could not be computed this
    cycle" — also legitimate (`INSUFFICIENT_EVIDENCE`).

    ``opening_range_15`` is the full canonical `OpeningRangeEvidence`
    (OR15 window only) — always-optional, purely contextual (ID-7B.2.1
    §14): its absence, or a non-`COMPLETE` formation, never forces
    `UNKNOWN` and is never substituted for the operative VWAP-loss
    invalidation.
    """

    completed_m5_close: Candle | None
    session_vwap: Decimal | None
    opening_range_15: OpeningRangeEvidence | None

    def __post_init__(self) -> None:
        if (
            self.completed_m5_close is not None
            and self.completed_m5_close.timeframe is not Timeframe.M5
        ):
            raise ValueError(
                "EntryActionabilityMarketEvidence.completed_m5_close must be an M5 "
                f"candle, got {self.completed_m5_close.timeframe.value}"
            )
        if self.session_vwap is not None and self.session_vwap <= 0:
            raise ValueError("EntryActionabilityMarketEvidence.session_vwap must be positive")
        if (
            self.opening_range_15 is not None
            and self.opening_range_15.formation.window is not OpeningRangeWindow.OR15
        ):
            raise ValueError(
                "EntryActionabilityMarketEvidence.opening_range_15 must be an OR15 "
                f"window, got {self.opening_range_15.formation.window.value}"
            )


@dataclass(frozen=True, slots=True)
class EntryActionabilityPolicy:
    """Immutable identity of the methodology to apply — mirrors
    `EntryQualificationPolicy`'s exact pattern (ID-6B.2). Carries no
    numeric thresholds of its own beyond the frozen module-level
    constants this engine already imports; the default methodology
    version must remain the frozen constant unless a caller has a
    genuine, deliberate reason to evaluate under a different (still
    already-existing) methodology version."""

    methodology_version: str = DEFAULT_METHODOLOGY_VERSION
    config_snapshot_id: str | None = None

    def __post_init__(self) -> None:
        if not self.methodology_version:
            raise ValueError("EntryActionabilityPolicy.methodology_version is mandatory")
        if self.config_snapshot_id is not None and not self.config_snapshot_id:
            raise ValueError("EntryActionabilityPolicy.config_snapshot_id cannot be empty")


class EntryActionabilityEngine:
    """Deterministic, side-effect-free V0 methodology evaluator.

    O(1) per candidate: no candle-series iteration, no repository access,
    no provider/network call, no history scan, no lookup of any prior
    `EntryActionability`. `evaluate()` is the only public method.
    """

    def evaluate(
        self,
        *,
        decision: Decision,
        entry_qualification: EntryQualification,
        market_evidence: EntryActionabilityMarketEvidence,
        evaluated_at: datetime,
        policy: EntryActionabilityPolicy | None = None,
    ) -> EntryActionability:
        policy = policy if policy is not None else EntryActionabilityPolicy()
        if evaluated_at.tzinfo is None:
            raise ValueError("EntryActionabilityEngine.evaluate evaluated_at must be timezone-aware")

        instrument_id = _validate_binding(decision, entry_qualification)
        entry_actionability_as_of = entry_qualification.as_of  # Option 1: same checkpoint as EQ.

        if market_evidence.completed_m5_close is not None:
            _validate_candle_coherence(
                market_evidence.completed_m5_close, instrument_id, entry_actionability_as_of
            )

        reasons: list[EntryActionabilityReasonCode] = []
        if decision.decision_type is not DecisionType.TRADE:
            reasons.append(EntryActionabilityReasonCode.UPSTREAM_DECISION_NOT_TRADE)
        if entry_qualification.state is not EntryQualificationState.QUALIFIED:
            reasons.append(EntryActionabilityReasonCode.UPSTREAM_EQ_NOT_QUALIFIED)

        if reasons:
            return self._emit(
                decision, entry_qualification, instrument_id, entry_actionability_as_of,
                evaluated_at, policy,
                state=EntryActionabilityState.NOT_ACTIONABLE,
                reason_codes=tuple(reasons),
                evidence_as_of=None,
                entry_reference=None, entry_location_context=None,
                operative_invalidation=None, reward=None, opening_range_context=None,
                explanation=_upstream_gate_explanation(decision, entry_qualification, reasons),
            )

        # Upstream eligibility satisfied: Decision == TRADE, exact EQ ==
        # QUALIFIED. Layer-3 evidence sufficiency may now be evaluated —
        # never before this point (ID-7A.2's own frozen invariant).
        candle = market_evidence.completed_m5_close
        vwap = market_evidence.session_vwap
        if candle is None or vwap is None:
            missing = _describe_missing_evidence(candle, vwap)
            return self._emit(
                decision, entry_qualification, instrument_id, entry_actionability_as_of,
                evaluated_at, policy,
                state=EntryActionabilityState.UNKNOWN,
                reason_codes=(EntryActionabilityReasonCode.INSUFFICIENT_EVIDENCE,),
                evidence_as_of=None,
                entry_reference=None, entry_location_context=None,
                operative_invalidation=None, reward=None, opening_range_context=None,
                explanation=(
                    "UNKNOWN: upstream eligible (TRADE + QUALIFIED) but required V0 "
                    f"checkpoint evidence is unavailable — {missing}."
                ),
            )

        entry_price = candle.close
        evidence_as_of = candle.ts_open + _M5_BAR_DURATION
        entry_reference = EntryReference(
            price=entry_price, basis=EntryReferenceBasis.QUALIFYING_M5_CLOSE
        )
        deviation_pct = (entry_price - vwap) / vwap * Decimal(100)
        entry_location_context = EntryLocationContext(
            vwap=vwap, vwap_deviation_pct=deviation_pct
        )

        if not _geometry_valid(decision.direction, entry_price, vwap):
            return self._emit(
                decision, entry_qualification, instrument_id, entry_actionability_as_of,
                evaluated_at, policy,
                state=EntryActionabilityState.UNKNOWN,
                reason_codes=(EntryActionabilityReasonCode.INVALIDATION_UNAVAILABLE,),
                evidence_as_of=evidence_as_of,
                entry_reference=None, entry_location_context=None,
                operative_invalidation=None, reward=None, opening_range_context=None,
                explanation=(
                    "UNKNOWN: upstream eligible and checkpoint evidence available, but the "
                    f"VWAP-loss operative invalidation is not valid for direction "
                    f"{decision.direction.value} (VWAP={vwap}, entry={entry_price})."
                ),
            )

        operative_invalidation = OperativeInvalidation(level=vwap, basis=InvalidationBasis.VWAP_LOSS)
        reward = _reward_reference(decision.direction, entry_price, vwap)
        opening_range_context = _opening_range_context(
            decision.direction, market_evidence.opening_range_15
        )

        return self._emit(
            decision, entry_qualification, instrument_id, entry_actionability_as_of,
            evaluated_at, policy,
            state=EntryActionabilityState.ACTIONABLE,
            reason_codes=(),
            evidence_as_of=evidence_as_of,
            entry_reference=entry_reference,
            entry_location_context=entry_location_context,
            operative_invalidation=operative_invalidation,
            reward=reward,
            opening_range_context=opening_range_context,
            explanation=(
                f"ACTIONABLE: TRADE + QUALIFIED; entry={entry_price} (completed M5 close); "
                f"VWAP-loss invalidation={vwap}; T1={reward.t1_price}, T2={reward.t2_price} "
                "goal bands (informational RR)."
            ),
        )

    @staticmethod
    def _emit(
        decision: Decision,
        entry_qualification: EntryQualification,
        instrument_id: str,
        entry_actionability_as_of: datetime,
        evaluated_at: datetime,
        policy: EntryActionabilityPolicy,
        *,
        state: EntryActionabilityState,
        reason_codes: tuple[EntryActionabilityReasonCode, ...],
        evidence_as_of: datetime | None,
        entry_reference: EntryReference | None,
        entry_location_context: EntryLocationContext | None,
        operative_invalidation: OperativeInvalidation | None,
        reward: RewardReference | None,
        opening_range_context: OpeningRangeContextReference | None,
        explanation: str,
    ) -> EntryActionability:
        return EntryActionability(
            instrument_id=instrument_id,
            session_date=entry_qualification.session_date,
            entry_qualification_as_of=entry_qualification.as_of,
            decision_id=entry_qualification.decision_id,
            entry_qualification_methodology_version=entry_qualification.methodology_version,
            entry_actionability_as_of=entry_actionability_as_of,
            entry_actionability_methodology_version=policy.methodology_version,
            decision_type=decision.decision_type,
            direction=decision.direction,
            entry_qualification_state=entry_qualification.state,
            run_id=decision.run_id,
            cycle_id=decision.cycle_id,
            state=state,
            reason_codes=reason_codes,
            evidence_finality=entry_qualification.evidence_finality,
            evidence_as_of=evidence_as_of,
            entry_reference=entry_reference,
            entry_location_context=entry_location_context,
            operative_invalidation=operative_invalidation,
            reward=reward,
            opening_range_context=opening_range_context,
            evaluated_at=evaluated_at,
            explanation=explanation,
        )


def _validate_binding(decision: Decision, eq: EntryQualification) -> str:
    """Prove ``decision``/``eq`` describe ONE exact, coherent candidate
    before any methodology evaluation — mirrors
    `EntryQualificationEngine`'s own `_validate_input_coherence` and the
    repository's own `_validate_entry_actionability_decision_binding`/
    `_validate_entry_actionability_eq_binding` (ID-7A), applied here at
    evaluation time instead of persistence time. A mismatch is a
    programmer/input-contract error — never a methodology UNKNOWN — and
    is never silently repaired. Returns the resolved instrument_id
    (mirrors `EntryQualificationEngine`'s own `_resolve_instrument_id`
    fallback when `Decision.instrument_id` is `None`)."""
    if eq.decision_id != decision.decision_id:
        raise ValueError(
            "EntryActionabilityEngine received an EntryQualification bound to "
            f"decision_id={eq.decision_id!r} but a Decision with "
            f"decision_id={decision.decision_id!r} — not an exact bound pair"
        )
    if eq.decision_type != decision.decision_type:
        raise ValueError(
            "EntryActionabilityEngine received a Decision/EntryQualification pair "
            f"with disagreeing decision_type (Decision={decision.decision_type.value!r}, "
            f"EntryQualification={eq.decision_type.value!r})"
        )
    if eq.run_id != decision.run_id:
        raise ValueError(
            "EntryActionabilityEngine received a Decision/EntryQualification pair "
            f"with disagreeing run_id (Decision={decision.run_id!r}, "
            f"EntryQualification={eq.run_id!r})"
        )
    if eq.cycle_id != decision.cycle_id:
        raise ValueError(
            "EntryActionabilityEngine received a Decision/EntryQualification pair "
            f"with disagreeing cycle_id (Decision={decision.cycle_id!r}, "
            f"EntryQualification={eq.cycle_id!r})"
        )
    if decision.instrument_id is None:
        return eq.instrument_id
    if decision.instrument_id != eq.instrument_id:
        raise ValueError(
            "EntryActionabilityEngine received a Decision "
            f"({decision.instrument_id!r}) and EntryQualification "
            f"({eq.instrument_id!r}) for two different instruments"
        )
    return decision.instrument_id


def _validate_candle_coherence(candle: Candle, instrument_id: str, checkpoint: datetime) -> None:
    if candle.instrument_id != instrument_id:
        raise ValueError(
            "EntryActionabilityEngine received a completed_m5_close candle for "
            f"{candle.instrument_id!r}, but the resolved candidate instrument is "
            f"{instrument_id!r}"
        )
    if not is_candle_completed(candle, as_of=checkpoint):
        raise ValueError(
            "EntryActionabilityEngine received a completed_m5_close candle "
            f"(ts_open={candle.ts_open.isoformat()}) that has not actually completed as of "
            f"the checkpoint ({checkpoint.isoformat()}) — future evidence relative to the "
            "checkpoint is a contract error, not a methodology outcome"
        )


def _describe_missing_evidence(candle: Candle | None, vwap: Decimal | None) -> str:
    missing = []
    if candle is None:
        missing.append("no completed M5 checkpoint candle")
    if vwap is None:
        missing.append("no session VWAP")
    return ", ".join(missing)


def _upstream_gate_explanation(
    decision: Decision, eq: EntryQualification, reasons: list[EntryActionabilityReasonCode]
) -> str:
    parts = []
    if EntryActionabilityReasonCode.UPSTREAM_DECISION_NOT_TRADE in reasons:
        parts.append(f"Decision is {decision.decision_type.value}, not TRADE")
    if EntryActionabilityReasonCode.UPSTREAM_EQ_NOT_QUALIFIED in reasons:
        parts.append(f"bound EntryQualification is {eq.state.value}, not QUALIFIED")
    return "NOT_ACTIONABLE: " + "; ".join(parts) + "."


def _geometry_valid(direction: Direction, entry_price: Decimal, invalidation_level: Decimal) -> bool:
    """Mirrors `EntryActionability._validate_risk_geometry`'s exact
    structural rule — checked here BEFORE domain construction so a
    geometrically invalid checkpoint maps deterministically to
    `UNKNOWN`/`INVALIDATION_UNAVAILABLE` (ID-7C authorization item 19),
    never a raised domain `ValueError` escaping as an unexpected
    programming error. `Decision.__post_init__` already guarantees
    `direction` is `LONG` or `SHORT` whenever `decision_type == TRADE`
    (the only branch that reaches this function), so `Direction.NONE`
    is structurally unreachable here."""
    if direction is Direction.LONG:
        return invalidation_level < entry_price
    if direction is Direction.SHORT:
        return invalidation_level > entry_price
    raise ValueError(
        f"EntryActionabilityEngine cannot evaluate risk geometry for direction {direction.value} "
        "— a TRADE Decision must be LONG or SHORT (Decision.__post_init__ already guarantees this)"
    )


def _reward_reference(direction: Direction, entry_price: Decimal, invalidation_level: Decimal) -> RewardReference:
    """T1/T2 goal bands (ID-7B.2's frozen `T1_GOAL_BAND_PCT`/
    `T2_GOAL_BAND_PCT`) plus informational-only RR — exact Decimal
    arithmetic throughout, no rounding/tick-size policy (none was
    frozen)."""
    if direction is Direction.LONG:
        t1_price = entry_price * (Decimal(1) + T1_GOAL_BAND_PCT)
        t2_price = entry_price * (Decimal(1) + T2_GOAL_BAND_PCT)
    else:
        assert direction is Direction.SHORT  # guaranteed reachable-only value; see _geometry_valid
        t1_price = entry_price * (Decimal(1) - T1_GOAL_BAND_PCT)
        t2_price = entry_price * (Decimal(1) - T2_GOAL_BAND_PCT)

    risk_distance = abs(entry_price - invalidation_level)
    reward_distance_t1 = abs(t1_price - entry_price)
    reward_distance_t2 = abs(t2_price - entry_price)
    return RewardReference(
        t1_price=t1_price,
        t2_price=t2_price,
        basis=RewardBasis.GOAL_BANDS_ONLY,
        reward_risk_to_t1=reward_distance_t1 / risk_distance,
        reward_risk_to_t2=reward_distance_t2 / risk_distance,
    )


def _opening_range_context(
    direction: Direction, or15: OpeningRangeEvidence | None
) -> OpeningRangeContextReference | None:
    """Always-optional, purely contextual — absence (FORMING/INCOMPLETE_DATA/
    NOT_AVAILABLE/NOT_APPLICABLE/missing) never changes the ACTIONABLE
    verdict, never substitutes for the operative VWAP-loss invalidation,
    and never feeds RR (ID-7B.2.1 §14). The directionally coherent
    structural boundary is the range low for LONG (the level below which
    the setup's own opening structure was already violated) and the range
    high for SHORT — a price level only, never a breakout-event or
    DarvaX-style label."""
    if or15 is None or or15.formation.status is not OpeningRangeFormationStatus.COMPLETE:
        return None
    level = or15.formation.low if direction is Direction.LONG else or15.formation.high
    if level is None or level <= 0:
        return None
    return OpeningRangeContextReference(level=level, basis=OpeningRangeContextBasis.OR15_BOUNDARY)
