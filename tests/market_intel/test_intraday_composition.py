"""Shared PositionSizing/LivePlanSupervision composition (ID-11).

Proves `compose_position_sizing`/`compose_live_plan_supervision` — extracted
from the canonical `position_sizing_stage`/`live_plan_supervision_stage`
bodies so the production WorkflowStage and the new ID-11 read-only API
service call the exact same path — reproduce the frozen engine contracts
exactly: non-current EntryActionability yields the engines' own real
NOT_SIZED/UPSTREAM_NOT_CURRENT and NOT_APPLICABLE/UPSTREAM_NOT_CURRENT
verdicts (never a fabricated UNAVAILABLE), a genuinely current+actionable
LONG opportunity sizes/supervises correctly, and VWAP-loss invalidation is
permanent for a given EntryActionability identity.
"""

from __future__ import annotations

from datetime import date, datetime, timedelta
from decimal import Decimal
from pathlib import Path
from zoneinfo import ZoneInfo

from athena.calendar.engine import CalendarEngine
from athena.config.loader import load_config
from athena.data.store.repository import SqliteRepository
from athena.domain.decision import Decision
from athena.domain.enums import DecisionType, Direction, Timeframe
from athena.domain.decision import TradePlan
from athena.domain.market import Candle, Instrument
from athena.intraday import (
    DEFAULT_METHODOLOGY_VERSION as EQ_DEFAULT_METHODOLOGY_VERSION,
    ENTRY_ACTIONABILITY_DEFAULT_METHODOLOGY_VERSION,
    CapitalPolicy,
    EntryActionability,
    EntryActionabilityReasonCode,
    EntryActionabilityState,
    EntryEvidenceFinality,
    EntryLocationContext,
    EntryQualification,
    EntryQualificationConfirmation,
    EntryQualificationState,
    EntryReference,
    EntryReferenceBasis,
    InvalidationBasis,
    OperativeInvalidation,
    PositionSizingReasonCode,
    PositionSizingState,
    PositionSizingV0Engine,
    RewardBasis,
    RewardReference,
)
from athena.intraday.intraday_composition import (
    compose_live_plan_supervision,
    compose_position_sizing,
)
from athena.intraday.live_plan_supervision_engine import LivePlanSupervisionEngine
from athena.intraday.live_plan_supervision_models import (
    LivePlanSupervisionReasonCode,
    LivePlanSupervisionState,
    TargetProgress,
)

IST = ZoneInfo("Asia/Kolkata")
CONFIG_DIR = Path(__file__).resolve().parents[2] / "config"
DAY = date(2026, 3, 2)
IID = "NSE:TEST"
EQ_AS_OF = datetime(2026, 3, 2, 9, 40, tzinfo=IST)
EA_AS_OF = datetime(2026, 3, 2, 9, 45, tzinfo=IST)
EVIDENCE_AS_OF = datetime(2026, 3, 2, 9, 45, tzinfo=IST)
#: Within the frozen 600s currentness band of EVIDENCE_AS_OF (9:45) -- used
#: as the single `now` for PositionSizing (which has one clock param) and
#: as `evaluated_at` for LivePlanSupervision (whose `market_checkpoint` is
#: a deliberately separate, later parameter -- see compose_live_plan_supervision's
#: own docstring for why these two concepts must never collapse).
NOW = datetime(2026, 3, 2, 9, 50, tzinfo=IST)


def _calendar() -> CalendarEngine:
    cfg = load_config(CONFIG_DIR)
    return CalendarEngine.from_config_dir(CONFIG_DIR, cfg.market)


def _sessions_cfg():
    return load_config(CONFIG_DIR).market.sessions


def _repo(tmp_path: Path) -> SqliteRepository:
    r = SqliteRepository(tmp_path / "id11.db")
    r.initialize()
    r.upsert_instrument(
        Instrument(instrument_id=IID, symbol="TEST", exchange="NSE", series="EQ", status="ACTIVE")
    )
    return r


def _trade_plan() -> TradePlan:
    return TradePlan(
        entry_low=Decimal("99"), entry_high=Decimal("101"), stop_loss=Decimal("95"),
        targets=(Decimal("110"),), position_size=1, risk_amount=Decimal("500"),
        risk_reward=Decimal("2.0"),
        valid_from=EA_AS_OF, valid_until=EA_AS_OF + timedelta(hours=6),
    )


def _decision(**overrides: object) -> Decision:
    fields: dict[str, object] = dict(
        decision_id="decision-1",
        ts=EA_AS_OF,
        run_id="run-1",
        cycle_id="cycle-1",
        decision_type=DecisionType.TRADE,
        explanation="test decision",
        instrument_id=IID,
        direction=Direction.LONG,
        trade_plan=_trade_plan(),
    )
    fields.update(overrides)
    return Decision(**fields)  # type: ignore[arg-type]


def _eq(**overrides: object) -> EntryQualification:
    fields: dict[str, object] = dict(
        instrument_id=IID,
        session_date=DAY,
        as_of=EQ_AS_OF,
        run_id="run-1",
        cycle_id="cycle-1",
        decision_id="decision-1",
        decision_type=DecisionType.TRADE,
        state=EntryQualificationState.QUALIFIED,
        evidence_finality=EntryEvidenceFinality.NO_DECISIVE_PROVISIONAL_M5_DEPENDENCY,
        confirmation=EntryQualificationConfirmation.CONFIRMED_BY_POLICY,
        reason_codes=(),
        evidence_refs=(),
        methodology_version=EQ_DEFAULT_METHODOLOGY_VERSION,
        config_snapshot_id=None,
        explanation="test eq",
    )
    fields.update(overrides)
    return EntryQualification(**fields)  # type: ignore[arg-type]


def _actionable_ea(**overrides: object) -> EntryActionability:
    fields: dict[str, object] = dict(
        instrument_id=IID,
        session_date=DAY,
        entry_qualification_as_of=EQ_AS_OF,
        decision_id="decision-1",
        entry_qualification_methodology_version=EQ_DEFAULT_METHODOLOGY_VERSION,
        entry_actionability_as_of=EA_AS_OF,
        entry_actionability_methodology_version=ENTRY_ACTIONABILITY_DEFAULT_METHODOLOGY_VERSION,
        decision_type=DecisionType.TRADE,
        direction=Direction.LONG,
        entry_qualification_state=EntryQualificationState.QUALIFIED,
        run_id="run-1",
        cycle_id="cycle-1",
        state=EntryActionabilityState.ACTIONABLE,
        reason_codes=(),
        evidence_finality=EntryEvidenceFinality.NO_DECISIVE_PROVISIONAL_M5_DEPENDENCY,
        evidence_as_of=EVIDENCE_AS_OF,
        entry_reference=EntryReference(
            price=Decimal("100.00"), basis=EntryReferenceBasis.QUALIFYING_M5_CLOSE
        ),
        entry_location_context=EntryLocationContext(
            vwap=Decimal("99.50"), vwap_deviation_pct=Decimal("0.50")
        ),
        operative_invalidation=OperativeInvalidation(
            level=Decimal("98.00"), basis=InvalidationBasis.VWAP_LOSS
        ),
        reward=RewardReference(
            t1_price=Decimal("101.00"), t2_price=Decimal("101.50"), basis=RewardBasis.GOAL_BANDS_ONLY,
            reward_risk_to_t1=Decimal("0.5"), reward_risk_to_t2=Decimal("0.75"),
        ),
        opening_range_context=None,
        evaluated_at=EA_AS_OF,
        explanation="actionable test",
    )
    fields.update(overrides)
    return EntryActionability(**fields)  # type: ignore[arg-type]


def _m5(ts: datetime, *, open_: str, high: str, low: str, close: str) -> Candle:
    return Candle(
        instrument_id=IID, timeframe=Timeframe.M5, ts_open=ts,
        open=Decimal(open_), high=Decimal(high), low=Decimal(low), close=Decimal(close),
        volume=10_000, source="test",
    )


def _capital_policy() -> CapitalPolicy:
    return CapitalPolicy(
        total_deployable_capital=Decimal("100000"),
        risk_budget_per_trade_pct=Decimal("1.0"),
        max_position_value_pct=Decimal("10.0"),
        policy_version="test-policy-v1",
    )


class TestComposePositionSizing:
    def test_sized_for_current_actionable_long(self) -> None:
        decision = _decision()
        eq = _eq()
        ea = _actionable_ea()
        sizing = compose_position_sizing(
            decision=decision,
            entry_actionability=ea,
            entry_qualification=eq,
            instrument_lot_size=1,
            capital_policy=_capital_policy(),
            calendar=_calendar(),
            sessions_cfg=_sessions_cfg(),
            session_tzinfo=IST,
            engine=PositionSizingV0Engine(),
            now=NOW,
        )
        assert sizing.state is PositionSizingState.SIZED
        assert sizing.recommended_quantity is not None and sizing.recommended_quantity > 0

    def test_not_sized_upstream_not_current_for_superseded_ea(self) -> None:
        """A superseded EA (bound to a decision_id that no longer matches
        the current Decision) must reproduce the engine's own real
        NOT_SIZED/UPSTREAM_NOT_CURRENT verdict -- never a fabricated
        UNAVAILABLE (ID-11 frozen contract)."""
        decision = _decision(decision_id="decision-2")  # current Decision differs from EA's own
        eq = _eq()
        ea = _actionable_ea()
        sizing = compose_position_sizing(
            decision=decision,
            entry_actionability=ea,
            entry_qualification=eq,
            instrument_lot_size=1,
            capital_policy=_capital_policy(),
            calendar=_calendar(),
            sessions_cfg=_sessions_cfg(),
            session_tzinfo=IST,
            engine=PositionSizingV0Engine(),
            now=NOW,
        )
        assert sizing.state is PositionSizingState.NOT_SIZED
        assert sizing.reason_codes == (PositionSizingReasonCode.UPSTREAM_NOT_CURRENT,)
        # Upstream-echoed risk geometry is still present for explainability.
        assert sizing.entry_reference_price == Decimal("100.00")

    def test_not_sized_capital_policy_unavailable(self) -> None:
        decision = _decision()
        eq = _eq()
        ea = _actionable_ea()
        sizing = compose_position_sizing(
            decision=decision,
            entry_actionability=ea,
            entry_qualification=eq,
            instrument_lot_size=1,
            capital_policy=None,
            calendar=_calendar(),
            sessions_cfg=_sessions_cfg(),
            session_tzinfo=IST,
            engine=PositionSizingV0Engine(),
            now=NOW,
        )
        assert sizing.state is PositionSizingState.NOT_SIZED
        assert sizing.reason_codes == (PositionSizingReasonCode.CAPITAL_POLICY_UNAVAILABLE,)


class TestComposeLivePlanSupervision:
    def test_valid_when_no_vwap_loss(self, tmp_path: Path) -> None:
        repo = _repo(tmp_path)
        # Rising session: close stays above the evolving VWAP throughout.
        candles = [
            _m5(EVIDENCE_AS_OF, open_="100", high="100.3", low="99.8", close="100.1"),
            _m5(EVIDENCE_AS_OF + timedelta(minutes=5), open_="100.1", high="100.4", low="99.9", close="100.2"),
        ]
        repo.add_candles(candles)
        decision = _decision()
        eq = _eq()
        ea = _actionable_ea()
        supervision = compose_live_plan_supervision(
            decision=decision,
            entry_actionability=ea,
            entry_qualification=eq,
            repo=repo,
            calendar=_calendar(),
            sessions_cfg=_sessions_cfg(),
            session_tzinfo=IST,
            engine=LivePlanSupervisionEngine(),
            # market_checkpoint must be at/after the last candle's own
            # completion instant (9:50+5m) for it to count as completed;
            # evaluated_at stays close to evidence_as_of so currentness
            # reports CURRENT -- the two are deliberately decoupled.
            market_checkpoint=EVIDENCE_AS_OF + timedelta(minutes=10),
            evaluated_at=NOW,
        )
        assert supervision.state is LivePlanSupervisionState.VALID
        assert supervision.target_progress_evidence is not None
        assert supervision.target_progress_evidence.status is TargetProgress.NONE_REACHED

    def test_invalidated_on_vwap_loss_and_permanent_after_recovery(self, tmp_path: Path) -> None:
        repo = _repo(tmp_path)
        loss_ts = EVIDENCE_AS_OF + timedelta(minutes=5)
        recovery_ts = loss_ts + timedelta(minutes=5)
        candles = [
            _m5(EVIDENCE_AS_OF, open_="100", high="101", low="99.5", close="100.5"),
            # A completed candle that closes well below the evolving VWAP.
            _m5(loss_ts, open_="100.5", high="100.6", low="90", close="90.5"),
            # A later candle recovers back above VWAP.
            _m5(recovery_ts, open_="91", high="102", low="90.5", close="101.5"),
        ]
        repo.add_candles(candles)
        decision = _decision()
        eq = _eq()
        ea = _actionable_ea()

        supervision = compose_live_plan_supervision(
            decision=decision, entry_actionability=ea, entry_qualification=eq, repo=repo,
            calendar=_calendar(), sessions_cfg=_sessions_cfg(), session_tzinfo=IST,
            engine=LivePlanSupervisionEngine(),
            # market_checkpoint (session/candle-completion bound) is
            # decoupled from evaluated_at (currentness clock) -- exactly
            # the two-parameter design compose_live_plan_supervision
            # exists to support (ID-10's own frozen freshness band would
            # otherwise make a 15-minutes-later checkpoint impossible).
            market_checkpoint=recovery_ts + timedelta(minutes=5),
            evaluated_at=NOW,
        )
        assert supervision.state is LivePlanSupervisionState.INVALIDATED
        assert supervision.reason_codes == (LivePlanSupervisionReasonCode.VWAP_LOSS,)
        assert supervision.vwap_loss_evidence is not None
        assert supervision.vwap_loss_evidence.triggered is True
        # Permanence: even though the LAST candle recovered above VWAP, the
        # verdict stays INVALIDATED -- a later recovery never restores VALID.
        assert supervision.vwap_loss_evidence.currently_above_vwap is True

    def test_not_applicable_upstream_not_current_for_superseded_ea(self, tmp_path: Path) -> None:
        """Mirrors PositionSizing's own frozen contract: a superseded EA
        must reproduce NOT_APPLICABLE/UPSTREAM_NOT_CURRENT -- never a
        fabricated UNAVAILABLE."""
        repo = _repo(tmp_path)
        decision = _decision(decision_id="decision-2")
        eq = _eq()
        ea = _actionable_ea()
        supervision = compose_live_plan_supervision(
            decision=decision, entry_actionability=ea, entry_qualification=eq, repo=repo,
            calendar=_calendar(), sessions_cfg=_sessions_cfg(), session_tzinfo=IST,
            engine=LivePlanSupervisionEngine(),
            market_checkpoint=NOW, evaluated_at=NOW,
        )
        assert supervision.state is LivePlanSupervisionState.NOT_APPLICABLE
        assert supervision.reason_codes == (LivePlanSupervisionReasonCode.UPSTREAM_NOT_CURRENT,)

    def test_not_applicable_for_short_direction(self, tmp_path: Path) -> None:
        repo = _repo(tmp_path)
        decision = _decision(direction=Direction.SHORT)
        eq = _eq()
        ea = _actionable_ea(
            direction=Direction.SHORT,
            operative_invalidation=OperativeInvalidation(
                level=Decimal("102.00"), basis=InvalidationBasis.VWAP_LOSS
            ),
        )
        supervision = compose_live_plan_supervision(
            decision=decision, entry_actionability=ea, entry_qualification=eq, repo=repo,
            calendar=_calendar(), sessions_cfg=_sessions_cfg(), session_tzinfo=IST,
            engine=LivePlanSupervisionEngine(),
            market_checkpoint=NOW, evaluated_at=NOW,
        )
        assert supervision.state is LivePlanSupervisionState.NOT_APPLICABLE
        assert supervision.reason_codes == (LivePlanSupervisionReasonCode.UNVALIDATED_DIRECTION,)
        # Upstream-echoed risk geometry still present for explainability.
        assert supervision.direction is Direction.SHORT
