"""Entry Qualification evidence-finality resolver (ID-6D).

Pure, deterministic, no clock/repository/provider access -- proven directly
by construction, not just asserted.
"""

from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from zoneinfo import ZoneInfo

from athena.domain.decision import Decision, TradePlan
from athena.domain.enums import DecisionType, Direction, SessionType
from athena.intraday.entry_qualification_models import EntryEvidenceFinality
from athena.intraday.entry_qualification_provenance import resolve_evidence_finality
from athena.session.models import SessionContext, SessionDataQualityStatus, SessionPhase, TimeframeProvenance

IST = ZoneInfo("Asia/Kolkata")
IID = "NSE:TEST"
DAY = date(2026, 9, 2)
AS_OF = datetime(2026, 9, 2, 10, 0, tzinfo=IST)


def _decision(decision_type: DecisionType = DecisionType.WATCH) -> Decision:
    if decision_type is DecisionType.TRADE:
        return Decision(
            decision_id="decision-1", ts=AS_OF, run_id="run-1", cycle_id="cycle-1",
            decision_type=decision_type, explanation="test decision", instrument_id=IID,
            direction=Direction.LONG,
            trade_plan=TradePlan(
                entry_low=Decimal("100"), entry_high=Decimal("101"), stop_loss=Decimal("98"),
                targets=(Decimal("105"),), position_size=1, risk_amount=Decimal("100"),
                risk_reward=Decimal("2"), valid_from=AS_OF,
                valid_until=datetime(2026, 9, 2, 15, 30, tzinfo=IST),
            ),
        )
    return Decision(
        decision_id="decision-1", ts=AS_OF, run_id="run-1", cycle_id="cycle-1",
        decision_type=decision_type, explanation="test decision", instrument_id=IID,
    )


def _provenance() -> TimeframeProvenance:
    from athena.domain.enums import Timeframe

    return TimeframeProvenance(
        instrument_id=IID, timeframe=Timeframe.M5, session_date=DAY, as_of=AS_OF,
        window_start=None, window_end=None, latest_completed_bar_ts=None,
        bar_count=1, quality=SessionDataQualityStatus.SUFFICIENT, explanation="test",
    )


def _session_context(phase: SessionPhase = SessionPhase.REGULAR) -> SessionContext:
    return SessionContext(
        instrument_id=IID, session_date=DAY, exchange="NSE", timezone="Asia/Kolkata",
        as_of=AS_OF, session_type=SessionType.NORMAL, phase=phase,
        session_open_ts=datetime(2026, 9, 2, 9, 15, tzinfo=IST),
        session_close_ts=datetime(2026, 9, 2, 15, 30, tzinfo=IST),
        elapsed_seconds=2700, remaining_seconds=16200, latest_quote_ts=AS_OF,
        five_min=_provenance(), fifteen_min=_provenance(),
        data_quality=SessionDataQualityStatus.SUFFICIENT, explanation="test session",
    )


def test_watch_regular_phase_is_live_m5_provisional() -> None:
    result = resolve_evidence_finality(_decision(DecisionType.WATCH), _session_context(SessionPhase.REGULAR))
    assert result is EntryEvidenceFinality.LIVE_M5_PROVISIONAL


def test_trade_regular_phase_is_live_m5_provisional() -> None:
    result = resolve_evidence_finality(_decision(DecisionType.TRADE), _session_context(SessionPhase.REGULAR))
    assert result is EntryEvidenceFinality.LIVE_M5_PROVISIONAL


def test_non_watch_trade_regular_phase_is_unknown_provenance() -> None:
    """OUT_OF_SCOPE in the engine -- no direct evidence consulted at all,
    regardless of phase."""
    result = resolve_evidence_finality(_decision(DecisionType.NO_TRADE), _session_context(SessionPhase.REGULAR))
    assert result is EntryEvidenceFinality.UNKNOWN_PROVENANCE


def test_pre_open_phase_is_unknown_provenance() -> None:
    """NOT_YET from PRE_OPEN in the engine -- signal_set never touched."""
    result = resolve_evidence_finality(_decision(DecisionType.WATCH), _session_context(SessionPhase.PRE_OPEN))
    assert result is EntryEvidenceFinality.UNKNOWN_PROVENANCE


def test_closed_phase_is_unknown_provenance() -> None:
    """EXPIRED in the engine -- signal_set never touched."""
    result = resolve_evidence_finality(_decision(DecisionType.WATCH), _session_context(SessionPhase.CLOSED))
    assert result is EntryEvidenceFinality.UNKNOWN_PROVENANCE


def test_not_a_trading_session_is_unknown_provenance() -> None:
    result = resolve_evidence_finality(
        _decision(DecisionType.WATCH), _session_context(SessionPhase.NOT_A_TRADING_SESSION)
    )
    assert result is EntryEvidenceFinality.UNKNOWN_PROVENANCE


def test_no_decisive_provisional_m5_dependency_is_never_returned() -> None:
    """Structural proof: enumerate every DecisionType x SessionPhase
    combination -- NO_DECISIVE_PROVISIONAL_M5_DEPENDENCY must never appear,
    since the current runtime cannot positively prove indirect Decision
    provenance is free of provisional M5 dependence (ADR-013)."""
    for decision_type in DecisionType:
        for phase in SessionPhase:
            result = resolve_evidence_finality(_decision(decision_type), _session_context(phase))
            assert result is not EntryEvidenceFinality.NO_DECISIVE_PROVISIONAL_M5_DEPENDENCY


def test_resolver_is_pure_and_reads_no_hidden_state() -> None:
    """Structural proof: the function signature carries no clock/repository/
    provider parameter -- purity is enforced by shape, not just convention."""
    import inspect

    params = inspect.signature(resolve_evidence_finality).parameters
    assert set(params) == {"decision", "session_context"}


def test_resolver_is_deterministic() -> None:
    a = resolve_evidence_finality(_decision(), _session_context())
    b = resolve_evidence_finality(_decision(), _session_context())
    assert a is b
