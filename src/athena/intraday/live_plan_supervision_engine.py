"""Live Plan Supervision V0 pure evidence composers + evaluator (ID-10).

Mirrors `entry_actionability_engine.py`/`position_sizing_engine.py`'s own
established contract exactly: the evidence **composers** below are pure
functions of an already-fetched candle list (never a repository/provider/
network/clock read); `LivePlanSupervisionEngine.evaluate` is a pure
function of already-composed evidence (never a candle series, never a
repository read, never a clock read). The workflow stage (`ops/
owner_validation.py`) owns every I/O concern; nothing here does.

**Two-window VWAP contract (non-negotiable, per the Owner's own frozen
correction, docs/research/ID-10-LIVE-PLAN-SUPERVISION-DISCOVERY.md §9/§12):**
`vwap()` is session-cumulative — its value at any checkpoint T is defined
over candles from the canonical session start through T. Computing it
from only the candles after a supervised `EntryActionability`'s own
`evidence_as_of` would silently produce a *different*, unvalidated
"post-entry-window VWAP", not the frozen ID-7B/ID-8 session-cumulative
VWAP. `compose_vwap_loss_evidence` therefore takes two separate
sequences and must never be called with one substituted for the other:

- ``session_completed_m5`` — the **VWAP source window**: every completed
  M5 candle from canonical session start through the current evaluation
  checkpoint. Used only to compute the correct evolving VWAP value at
  any checkpoint within it.
- ``supervised_path`` — the **supervision event window**: completed M5
  candles with ``ts_open >= entry_actionability.evidence_as_of`` (the
  first candle *opening* at-or-after the supervised checkpoint's own
  completion instant is the first eligible event candidate — never a
  candle before it, never a candle after "now"). Used only to decide
  which checkpoints may register a VWAP-loss or target-touch event for
  *this specific plan*.

**Path-dependence (non-negotiable):** invalidation and target progress
are both facts about the *entire* event window, never the current
checkpoint alone. Once a qualifying VWAP-loss candle is found
chronologically first in the window, no later, longer window (which
only ever appends candles after it) can un-find it — a later recovery
above VWAP cannot revert a prior invalidation. This falls directly out
of recomputing a deterministic fold over a time-ordered window every
call; no persisted state machine is needed or used.

**Never uses `EntryActionability.operative_invalidation.level`** for
this forward test — that field is a frozen VWAP snapshot from the
synchronous entry checkpoint (ID-9's own risk-geometry input), not a
forward-updating reference. See the discovery document's §7 for the
confirmatory source read proving this.
"""

from __future__ import annotations

from collections.abc import Sequence
from datetime import datetime, timedelta
from decimal import Decimal

from athena.domain.enums import Direction, Timeframe
from athena.domain.market import Candle
from athena.indicators.calculations import vwap
from athena.intraday.entry_actionability_currentness import (
    CurrentnessResult,
    EntryActionabilityCurrentness,
)
from athena.intraday.entry_actionability_models import (
    EntryActionability,
    EntryActionabilityState,
    RewardReference,
)
from athena.intraday.live_plan_supervision_models import (
    DEFAULT_METHODOLOGY_VERSION,
    LivePlanSupervision,
    LivePlanSupervisionReasonCode,
    LivePlanSupervisionState,
    TargetProgress,
    TargetProgressEvidence,
    VwapLossEvidence,
)
from athena.session.engine import completed_candles

#: Matches `entry_actionability_engine.py`'s own private constant --
#: independently defined here (never imported across module-private
#: boundaries) since both modules need the identical M5 bar duration for
#: the identical reason (a completed M5 bar's own completion instant).
_M5_BAR_DURATION = timedelta(minutes=5)


def compose_vwap_loss_evidence(
    session_completed_m5: Sequence[Candle],
    supervised_path: Sequence[Candle],
    direction: Direction,
) -> VwapLossEvidence:
    """Pure. Walks ``supervised_path`` (the supervision event window)
    chronologically; at each candle, recomputes the evolving
    session-cumulative VWAP from ``session_completed_m5`` (the VWAP
    source window) truncated to that candle's own completion instant,
    via the exact same `session.completed_candles` + `indicators.
    calculations.vwap` combination production already uses to compute
    VWAP at the current checkpoint -- never a new formula. Records the
    first chronological candle, if any, whose completed-M5 close falls
    on the wrong side of that checkpoint's own evolving VWAP.

    V0 is LONG-only -- raises if ``direction`` is not `Direction.LONG`,
    mirroring the "reject an impossible supplied combination" contract
    every evaluator in this track already uses; callers must never reach
    this composer for a non-LONG opportunity.
    """
    if direction is not Direction.LONG:
        raise ValueError(
            f"compose_vwap_loss_evidence: V0 is LONG-only, got direction={direction!r}"
        )

    ordered_session = sorted(session_completed_m5, key=lambda c: c.ts_open)
    ordered_path = sorted(supervised_path, key=lambda c: c.ts_open)

    if not ordered_path:
        return VwapLossEvidence(
            triggered=False, first_triggered_as_of=None, trigger_close=None, trigger_vwap=None,
            current_close=None, current_vwap=None, currently_above_vwap=None,
        )

    trigger: tuple[datetime, Decimal, Decimal] | None = None
    last_close: Decimal | None = None
    last_vwap: Decimal | None = None
    for candle in ordered_path:
        checkpoint = candle.ts_open + _M5_BAR_DURATION
        window = completed_candles(ordered_session, Timeframe.M5, as_of=checkpoint)
        result = vwap(window, checkpoint) if window else None
        if result is None:
            # No session evidence yet at this checkpoint -- cannot form
            # an evolving VWAP to compare against; this candle is simply
            # not evaluable, never treated as a trigger by omission.
            continue
        evolving_vwap, _deviation_pct = result
        last_close, last_vwap = candle.close, evolving_vwap
        if trigger is None and candle.close < evolving_vwap:
            trigger = (checkpoint, candle.close, evolving_vwap)

    currently_above_vwap = (last_close >= last_vwap) if last_close is not None else None
    if trigger is not None:
        first_triggered_as_of, trigger_close, trigger_vwap = trigger
        return VwapLossEvidence(
            triggered=True, first_triggered_as_of=first_triggered_as_of,
            trigger_close=trigger_close, trigger_vwap=trigger_vwap,
            current_close=last_close, current_vwap=last_vwap,
            currently_above_vwap=currently_above_vwap,
        )
    return VwapLossEvidence(
        triggered=False, first_triggered_as_of=None, trigger_close=None, trigger_vwap=None,
        current_close=last_close, current_vwap=last_vwap,
        currently_above_vwap=currently_above_vwap,
    )


def compose_target_progress_evidence(
    supervised_path: Sequence[Candle],
    reward: RewardReference,
    direction: Direction,
) -> TargetProgressEvidence:
    """Pure. Walks the identical supervision event window
    (``supervised_path`` -- no session-history prefix needed) for
    direction-aware intrabar touch against `reward.t1_price`/`t2_price`,
    reusing ID-8's own already-validated intrabar-touch convention
    (LONG: ``candle.high >= target_price``). Records the first
    chronological touch of each level independently; `T2_REACHED`
    structurally implies `T1_REACHED` (T2 is the farther goal band) even
    if a single candle's high crosses both simultaneously.
    """
    if direction is not Direction.LONG:
        raise ValueError(
            f"compose_target_progress_evidence: V0 is LONG-only, got direction={direction!r}"
        )

    ordered_path = sorted(supervised_path, key=lambda c: c.ts_open)
    t1_reached_as_of: datetime | None = None
    t2_reached_as_of: datetime | None = None
    for candle in ordered_path:
        checkpoint = candle.ts_open + _M5_BAR_DURATION
        if t1_reached_as_of is None and candle.high >= reward.t1_price:
            t1_reached_as_of = checkpoint
        if t2_reached_as_of is None and candle.high >= reward.t2_price:
            t2_reached_as_of = checkpoint

    if t2_reached_as_of is not None:
        if t1_reached_as_of is None or t1_reached_as_of > t2_reached_as_of:
            t1_reached_as_of = t2_reached_as_of
        return TargetProgressEvidence(
            status=TargetProgress.T2_REACHED,
            t1_reached_as_of=t1_reached_as_of, t2_reached_as_of=t2_reached_as_of,
        )
    if t1_reached_as_of is not None:
        return TargetProgressEvidence(
            status=TargetProgress.T1_REACHED,
            t1_reached_as_of=t1_reached_as_of, t2_reached_as_of=None,
        )
    return TargetProgressEvidence(
        status=TargetProgress.NONE_REACHED, t1_reached_as_of=None, t2_reached_as_of=None,
    )


class LivePlanSupervisionEngine:
    """Pure, deterministic V0 evaluator -- no repository/provider/network/
    clock access anywhere in this class, mirroring `EntryActionabilityEngine`/
    `PositionSizingV0Engine` exactly."""

    def evaluate(
        self,
        *,
        entry_actionability: EntryActionability,
        currentness: CurrentnessResult,
        vwap_loss_evidence: VwapLossEvidence | None,
        target_progress_evidence: TargetProgressEvidence | None,
        evaluated_at: datetime,
    ) -> LivePlanSupervision:
        if evaluated_at.tzinfo is None:
            raise ValueError("LivePlanSupervisionEngine.evaluate: evaluated_at must be timezone-aware")

        common: dict[str, object] = dict(
            instrument_id=entry_actionability.instrument_id,
            session_date=entry_actionability.session_date,
            entry_qualification_as_of=entry_actionability.entry_qualification_as_of,
            decision_id=entry_actionability.decision_id,
            entry_qualification_methodology_version=(
                entry_actionability.entry_qualification_methodology_version
            ),
            entry_actionability_as_of=entry_actionability.entry_actionability_as_of,
            entry_actionability_methodology_version=(
                entry_actionability.entry_actionability_methodology_version
            ),
            supervision_as_of=entry_actionability.entry_actionability_as_of,
            supervision_methodology_version=DEFAULT_METHODOLOGY_VERSION,
            currentness=currentness,
            evidence_as_of=entry_actionability.evidence_as_of,
            evaluated_at=evaluated_at,
        )

        def not_applicable(
            reason: LivePlanSupervisionReasonCode, *, upstream_fields_present: bool, explanation: str,
        ) -> LivePlanSupervision:
            return LivePlanSupervision(
                **common,
                state=LivePlanSupervisionState.NOT_APPLICABLE,
                reason_codes=(reason,),
                direction=entry_actionability.direction if upstream_fields_present else None,
                operative_invalidation_level=(
                    entry_actionability.operative_invalidation.level
                    if upstream_fields_present else None
                ),
                t1_price=(
                    entry_actionability.reward.t1_price if upstream_fields_present else None
                ),
                t2_price=(
                    entry_actionability.reward.t2_price if upstream_fields_present else None
                ),
                vwap_loss_evidence=None,
                target_progress_evidence=None,
                explanation=explanation,
            )

        # Gate A: upstream not ACTIONABLE.
        if entry_actionability.state is not EntryActionabilityState.ACTIONABLE:
            return not_applicable(
                LivePlanSupervisionReasonCode.UPSTREAM_NOT_ACTIONABLE,
                upstream_fields_present=False,
                explanation="NOT_APPLICABLE: upstream EntryActionability did not reach ACTIONABLE.",
            )

        # Gate B: direction not validated (V0 LONG-only,
        # LONG_VALIDATED_SHORT_UNVALIDATED) -- upstream fields still
        # echoed, mirroring PositionSizing's own UNVALIDATED_DIRECTION rule.
        if entry_actionability.direction is not Direction.LONG:
            return not_applicable(
                LivePlanSupervisionReasonCode.UNVALIDATED_DIRECTION,
                upstream_fields_present=True,
                explanation=(
                    f"NOT_APPLICABLE: direction {entry_actionability.direction.value} is outside "
                    "ID-10 V0's LONG-only scope (LONG_VALIDATED_SHORT_UNVALIDATED)."
                ),
            )

        # Gate C: currentness not CURRENT -- reused verbatim from the
        # existing, unmodified entry_actionability_currentness contract;
        # never re-implemented here. STALE/SUPERSEDED/SESSION_CLOSED are
        # explicitly NOT market invalidation -- they route through
        # NOT_APPLICABLE, never INVALIDATED.
        if currentness.status is not EntryActionabilityCurrentness.CURRENT:
            return not_applicable(
                LivePlanSupervisionReasonCode.UPSTREAM_NOT_CURRENT,
                upstream_fields_present=True,
                explanation=(
                    "NOT_APPLICABLE: bound EntryActionability is not currently usable "
                    f"({currentness.status.value}): {currentness.explanation}"
                ),
            )

        if vwap_loss_evidence is None or target_progress_evidence is None:
            raise ValueError(
                "LivePlanSupervisionEngine.evaluate: vwap_loss_evidence/target_progress_evidence "
                "are mandatory once the upstream ACTIONABLE+LONG+CURRENT gates all pass"
            )

        if vwap_loss_evidence.triggered:
            return LivePlanSupervision(
                **common,
                state=LivePlanSupervisionState.INVALIDATED,
                reason_codes=(LivePlanSupervisionReasonCode.VWAP_LOSS,),
                direction=entry_actionability.direction,
                operative_invalidation_level=entry_actionability.operative_invalidation.level,
                t1_price=entry_actionability.reward.t1_price,
                t2_price=entry_actionability.reward.t2_price,
                vwap_loss_evidence=vwap_loss_evidence,
                target_progress_evidence=target_progress_evidence,
                explanation=(
                    f"INVALIDATED: completed M5 close {vwap_loss_evidence.trigger_close} fell "
                    f"below the evolving session VWAP {vwap_loss_evidence.trigger_vwap} at "
                    f"{vwap_loss_evidence.first_triggered_as_of.isoformat() if vwap_loss_evidence.first_triggered_as_of else '?'} "
                    "-- permanent for this plan; later recovery above VWAP does not restore VALID."
                ),
            )

        return LivePlanSupervision(
            **common,
            state=LivePlanSupervisionState.VALID,
            reason_codes=(),
            direction=entry_actionability.direction,
            operative_invalidation_level=entry_actionability.operative_invalidation.level,
            t1_price=entry_actionability.reward.t1_price,
            t2_price=entry_actionability.reward.t2_price,
            vwap_loss_evidence=vwap_loss_evidence,
            target_progress_evidence=target_progress_evidence,
            explanation="VALID: no VWAP-loss event has occurred in the supervision event window.",
        )
