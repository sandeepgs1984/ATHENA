"""Shared PositionSizing/LivePlanSupervision composition (ID-11).

Extracted, behavior-preserving, from the canonical per-cycle
`position_sizing_stage`/`live_plan_supervision_stage` bodies
(`ops/owner_validation.py`) so the production `WorkflowStage`s and the new
ID-11 read-only API service call the exact same composition path -- no
duplicate sizing/supervision mathematics, no parallel reimplementation, and
both frozen engines (`PositionSizingV0Engine`, `LivePlanSupervisionEngine`)
are called completely unchanged.

Neither `entry_actionability` nor `entry_qualification` is fetched here --
callers resolve those themselves (a same-cycle `WorkflowContext` read in
production; a repository read plus a coherence check in the ID-11 read
service) and are responsible for their own "is there even an
EntryActionability to compose against" gate before calling either function
below. `compose_live_plan_supervision` is the one function that performs its
own I/O for the session-bounded M5 candle read ID-10's own frozen contract
requires (never a fixed N-candle lookback; see the module docstring in
`live_plan_supervision_engine.py`), via the injected `repo`/`session_tzinfo`
exactly as the production stage already does.
"""

from __future__ import annotations

from datetime import datetime
from zoneinfo import ZoneInfo

from athena.calendar.engine import CalendarEngine
from athena.config.models import SessionsConfig
from athena.data.store.repository import SqliteRepository
from athena.domain.decision import Decision
from athena.domain.enums import Direction, Timeframe
from athena.intraday import entry_actionability_currentness
from athena.intraday.entry_actionability_currentness import (
    EntryActionabilityCurrentness,
    EntryQualificationIdentity,
)
from athena.intraday.entry_actionability_models import EntryActionability, EntryActionabilityState
from athena.intraday.entry_qualification_models import EntryQualification
from athena.intraday.live_plan_supervision_engine import (
    LivePlanSupervisionEngine,
    compose_target_progress_evidence,
    compose_vwap_loss_evidence,
)
from athena.intraday.live_plan_supervision_models import LivePlanSupervision
from athena.intraday.position_sizing_engine import PositionSizingV0Engine
from athena.intraday.position_sizing_models import CapitalPolicy, PositionSizing
from athena.session.engine import classify_session_phase, completed_candles, session_day_start


def _current_entry_qualification_identity(
    entry_qualification: EntryQualification,
) -> EntryQualificationIdentity:
    return EntryQualificationIdentity(
        instrument_id=entry_qualification.instrument_id,
        session_date=entry_qualification.session_date,
        as_of=entry_qualification.as_of,
        decision_id=entry_qualification.decision_id,
        methodology_version=entry_qualification.methodology_version,
    )


def compose_position_sizing(
    *,
    decision: Decision,
    entry_actionability: EntryActionability,
    entry_qualification: EntryQualification,
    instrument_lot_size: int,
    capital_policy: CapitalPolicy | None,
    calendar: CalendarEngine,
    sessions_cfg: SessionsConfig,
    session_tzinfo: ZoneInfo,
    engine: PositionSizingV0Engine,
    now: datetime,
) -> PositionSizing:
    """One shared clock instant serves both the currentness `now` and this
    call's own `evaluated_at`, mirroring `position_sizing_stage`'s own
    `sizing_clock_instant` precedent exactly -- callers must never supply
    two independent clock reads for one sizing decision. ID-9 requires zero
    fresh market-evidence fetch (M5/VWAP/OR15/quote): every input here is
    either already resolved by the caller or a pure identity/clock/session
    computation."""
    current_session_phase = classify_session_phase(
        calendar.context_for(now.astimezone(session_tzinfo).date()),
        sessions_cfg,
        as_of=now,
        tzinfo=session_tzinfo,
    )
    currentness = entry_actionability_currentness.is_currently_usable(
        entry_actionability,
        current_decision_id=decision.decision_id,
        current_entry_qualification_identity=_current_entry_qualification_identity(
            entry_qualification
        ),
        current_session_phase=current_session_phase,
        now=now,
    )
    return engine.evaluate(
        entry_actionability=entry_actionability,
        currentness=currentness,
        capital_policy=capital_policy,
        instrument_lot_size=instrument_lot_size,
        evaluated_at=now,
    )


def compose_live_plan_supervision(
    *,
    decision: Decision,
    entry_actionability: EntryActionability,
    entry_qualification: EntryQualification,
    repo: SqliteRepository,
    calendar: CalendarEngine,
    sessions_cfg: SessionsConfig,
    session_tzinfo: ZoneInfo,
    engine: LivePlanSupervisionEngine,
    market_checkpoint: datetime,
    evaluated_at: datetime,
) -> LivePlanSupervision:
    """`market_checkpoint` and `evaluated_at` are deliberately separate
    parameters (Owner source-review correction, 2026-09-08): the former is
    the MARKET checkpoint this supervision assertion is made at (`ctx.as_of`
    in the canonical per-cycle workflow; the read service's own injected
    `now` for an on-demand API call), used for the session-bounded candle
    read AND `supervision_as_of`; the latter is the wall-clock instant used
    for the currentness `now` AND this artifact's own `evaluated_at`. The
    canonical workflow supplies genuinely different values for the two; the
    read service may supply the same instant for both -- either way, the two
    concepts are never collapsed into one parameter.

    The candle source window is session-bounded, never unbounded and never
    an arbitrary N-candle lookback: `session_day_start(market_checkpoint,
    session_tzinfo)` through `market_checkpoint`, identical in shape to
    `ind_stage`'s own VWAP evidence fetch -- a plain local
    `SqliteRepository.get_candles` read, never a provider/network call.
    """
    current_session_phase = classify_session_phase(
        calendar.context_for(evaluated_at.astimezone(session_tzinfo).date()),
        sessions_cfg,
        as_of=evaluated_at,
        tzinfo=session_tzinfo,
    )
    currentness = entry_actionability_currentness.is_currently_usable(
        entry_actionability,
        current_decision_id=decision.decision_id,
        current_entry_qualification_identity=_current_entry_qualification_identity(
            entry_qualification
        ),
        current_session_phase=current_session_phase,
        now=evaluated_at,
    )

    # Never compose bounded-path evidence (a repository read) for a row an
    # earlier deterministic gate will reject anyway -- only when upstream
    # genuinely reached ACTIONABLE+LONG+CURRENT is the session-history fetch
    # performed at all (mirrors the production stage's own discipline).
    vwap_loss_evidence = None
    target_progress_evidence = None
    if (
        entry_actionability.state is EntryActionabilityState.ACTIONABLE
        and entry_actionability.direction is Direction.LONG
        and currentness.status is EntryActionabilityCurrentness.CURRENT
    ):
        assert entry_actionability.evidence_as_of is not None  # ACTIONABLE guarantees this
        assert entry_actionability.reward is not None  # ACTIONABLE guarantees this
        session_candles = repo.get_candles(
            entry_actionability.instrument_id,
            Timeframe.M5,
            session_day_start(market_checkpoint, session_tzinfo),
            market_checkpoint,
        )
        session_completed_m5 = completed_candles(
            session_candles, Timeframe.M5, as_of=market_checkpoint
        )
        supervised_path = [
            c for c in session_completed_m5 if c.ts_open >= entry_actionability.evidence_as_of
        ]
        vwap_loss_evidence = compose_vwap_loss_evidence(
            session_completed_m5, supervised_path, entry_actionability.direction
        )
        target_progress_evidence = compose_target_progress_evidence(
            supervised_path, entry_actionability.reward, entry_actionability.direction
        )

    return engine.evaluate(
        entry_actionability=entry_actionability,
        currentness=currentness,
        vwap_loss_evidence=vwap_loss_evidence,
        target_progress_evidence=target_progress_evidence,
        supervision_as_of=market_checkpoint,
        evaluated_at=evaluated_at,
    )
