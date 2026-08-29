"""Session Context Engine (ID-1) — deterministic intraday provenance/session
foundation. No signals, no trading interpretation; see `athena.session`."""

from __future__ import annotations

from datetime import date, datetime, timedelta
from decimal import Decimal
from pathlib import Path
from zoneinfo import ZoneInfo

import pytest

from athena.calendar.engine import CalendarEngine
from athena.config.loader import load_config
from athena.domain.enums import Timeframe
from athena.domain.market import Candle
from athena.session import (
    SessionContextEngine,
    SessionDataQualityStatus,
    SessionPhase,
    is_candle_completed,
    latest_completed_candle,
)
from athena.session.models import TimeframeProvenance

IST = ZoneInfo("Asia/Kolkata")
CONFIG_DIR = Path(__file__).resolve().parents[2] / "config"
IID = "NSE:TEST"
#: A real, ordinary NSE trading Friday (per the production calendar fixtures).
DAY = date(2026, 8, 28)


def _candle(iid: str, tf: Timeframe, ts: datetime, seed: int = 100) -> Candle:
    px = Decimal(str(seed))
    return Candle(instrument_id=iid, timeframe=tf, ts_open=ts, open=px, high=px + 1,
                  low=px - 1, close=px, volume=1_000, source="test")


def _m5(hh: int, mm: int, day: date = DAY) -> Candle:
    return _candle(IID, Timeframe.M5, datetime(day.year, day.month, day.day, hh, mm, tzinfo=IST))


def _m15(hh: int, mm: int, day: date = DAY) -> Candle:
    return _candle(IID, Timeframe.M15, datetime(day.year, day.month, day.day, hh, mm, tzinfo=IST))


@pytest.fixture()
def calendar() -> CalendarEngine:
    cfg = load_config(CONFIG_DIR)
    return CalendarEngine.from_config_dir(CONFIG_DIR, cfg.market)


@pytest.fixture()
def sessions_cfg():
    return load_config(CONFIG_DIR).market.sessions


@pytest.fixture()
def engine() -> SessionContextEngine:
    return SessionContextEngine()


def _assess(engine, calendar, sessions_cfg, *, as_of, five=(), fifteen=(), quote_ts=None):
    return engine.assess(
        IID, as_of=as_of, exchange="NSE", calendar=calendar, sessions=sessions_cfg,
        tzinfo=IST, five_min_candles=list(five), fifteen_min_candles=list(fifteen),
        latest_quote_ts=quote_ts,
    )


# --------------------------------------------------------------------------- #
# A/B — provenance and session identity are explicit
# --------------------------------------------------------------------------- #

def test_a_timeframe_provenance_is_explicit(engine, calendar, sessions_cfg):
    as_of = datetime(2026, 8, 28, 9, 32, tzinfo=IST)
    sc = _assess(engine, calendar, sessions_cfg, as_of=as_of,
                 five=[_m5(9, 15), _m5(9, 20), _m5(9, 25)], fifteen=[_m15(9, 15)])
    assert sc.five_min.timeframe is Timeframe.M5
    assert sc.fifteen_min.timeframe is Timeframe.M15
    assert sc.five_min.instrument_id == IID


def test_b_session_identity_is_explicit(engine, calendar, sessions_cfg):
    as_of = datetime(2026, 8, 28, 9, 32, tzinfo=IST)
    sc = _assess(engine, calendar, sessions_cfg, as_of=as_of)
    assert sc.session_date == DAY
    assert sc.exchange == "NSE"
    assert sc.session_type.value == "NORMAL"


# --------------------------------------------------------------------------- #
# C — timezone-aware timestamps enforced
# --------------------------------------------------------------------------- #

def test_c_naive_as_of_rejected(engine, calendar, sessions_cfg):
    with pytest.raises(ValueError, match="timezone-aware"):
        engine.assess(IID, as_of=datetime(2026, 8, 28, 9, 32), exchange="NSE",
                      calendar=calendar, sessions=sessions_cfg, tzinfo=IST,
                      five_min_candles=[], fifteen_min_candles=[], latest_quote_ts=None)


def test_c_naive_window_bound_rejected_by_domain_object():
    with pytest.raises(ValueError, match="timezone-aware"):
        TimeframeProvenance(
            instrument_id=IID, timeframe=Timeframe.M5, session_date=DAY,
            as_of=datetime(2026, 8, 28, 9, 32, tzinfo=IST),
            window_start=datetime(2026, 8, 28, 9, 15),  # naive -- must reject
            window_end=None, latest_completed_bar_ts=None, bar_count=0,
            quality=SessionDataQualityStatus.SUFFICIENT, explanation="x",
        )


def test_c_empty_explanation_rejected():
    with pytest.raises(ValueError, match="explanation is mandatory"):
        TimeframeProvenance(
            instrument_id=IID, timeframe=Timeframe.M5, session_date=DAY,
            as_of=datetime(2026, 8, 28, 9, 32, tzinfo=IST),
            window_start=None, window_end=None, latest_completed_bar_ts=None,
            bar_count=0, quality=SessionDataQualityStatus.SUFFICIENT, explanation="",
        )


# --------------------------------------------------------------------------- #
# D/E — injected as_of controls everything; no wall-clock dependence
# --------------------------------------------------------------------------- #

def test_d_as_of_alone_changes_the_result(engine, calendar, sessions_cfg):
    five = [_m5(9, 15), _m5(9, 20), _m5(9, 25), _m5(9, 30)]
    early = _assess(engine, calendar, sessions_cfg,
                     as_of=datetime(2026, 8, 28, 9, 18, tzinfo=IST), five=five)
    later = _assess(engine, calendar, sessions_cfg,
                     as_of=datetime(2026, 8, 28, 9, 40, tzinfo=IST), five=five)
    assert early.five_min.latest_completed_bar_ts != later.five_min.latest_completed_bar_ts
    assert later.five_min.latest_completed_bar_ts == datetime(2026, 8, 28, 9, 30, tzinfo=IST)


def test_e_no_wall_clock_dependence_repeated_calls_identical(engine, calendar, sessions_cfg):
    as_of = datetime(2026, 8, 28, 9, 32, tzinfo=IST)
    five = [_m5(9, 15), _m5(9, 20), _m5(9, 25), _m5(9, 30)]
    first = _assess(engine, calendar, sessions_cfg, as_of=as_of, five=five, quote_ts=as_of)
    second = _assess(engine, calendar, sessions_cfg, as_of=as_of, five=five, quote_ts=as_of)
    assert first == second


# --------------------------------------------------------------------------- #
# F/G/H — completed-candle semantics: the critical regression boundary
# --------------------------------------------------------------------------- #

def test_f_in_progress_5m_candle_cannot_leak_into_completed_analytics(engine, calendar, sessions_cfg):
    """Regression proof: reintroducing `<` instead of `<=`-based exclusion (or
    dropping the duration check entirely) would make this fail."""
    as_of = datetime(2026, 8, 28, 9, 32, tzinfo=IST)  # mid-bar for the 09:30 5m candle
    five = [_m5(9, 15), _m5(9, 20), _m5(9, 25), _m5(9, 30)]
    sc = _assess(engine, calendar, sessions_cfg, as_of=as_of, five=five)
    assert sc.five_min.latest_completed_bar_ts == datetime(2026, 8, 28, 9, 25, tzinfo=IST)
    assert sc.five_min.bar_count == 4  # raw presence count still includes the forming bar
    forming = five[-1]
    assert not is_candle_completed(forming, as_of=as_of), (
        "the actively-forming 09:30-09:35 bar must not be reported completed at 09:32"
    )


def test_g_in_progress_15m_candle_cannot_leak_into_completed_analytics(engine, calendar, sessions_cfg):
    as_of = datetime(2026, 8, 28, 9, 20, tzinfo=IST)  # mid-bar for the 09:15 15m candle (ends 09:30)
    fifteen = [_m15(9, 15)]
    sc = _assess(engine, calendar, sessions_cfg, as_of=as_of, fifteen=fifteen)
    assert sc.fifteen_min.latest_completed_bar_ts is None
    assert not is_candle_completed(fifteen[0], as_of=as_of)


def test_h_completed_candle_included_exactly_at_the_boundary():
    """Boundary proof, not just an interior example: `ts_open + duration == as_of`
    is included; one second earlier is not."""
    candle = _m5(9, 30)
    exactly_closed = datetime(2026, 8, 28, 9, 35, tzinfo=IST)
    one_second_before = exactly_closed - timedelta(seconds=1)
    assert is_candle_completed(candle, as_of=exactly_closed)
    assert not is_candle_completed(candle, as_of=one_second_before)


def test_h_latest_completed_candle_picks_the_maximum_eligible(engine):
    candles = [_m5(9, 15), _m5(9, 20), _m5(9, 25)]
    as_of = datetime(2026, 8, 28, 9, 40, tzinfo=IST)
    result = latest_completed_candle(candles, Timeframe.M5, as_of=as_of)
    assert result is not None and result.ts_open == datetime(2026, 8, 28, 9, 25, tzinfo=IST)


# --------------------------------------------------------------------------- #
# I — first-session-bar behavior
# --------------------------------------------------------------------------- #

def test_i_right_at_open_with_zero_bars_is_sufficient_not_missing(engine, calendar, sessions_cfg):
    as_of = datetime(2026, 8, 28, 9, 15, tzinfo=IST)  # exactly session open
    sc = _assess(engine, calendar, sessions_cfg, as_of=as_of, five=[], fifteen=[])
    # No candles at all -> TIMEFRAME_UNAVAILABLE (correctly distinct from a
    # genuine gap), never EXPECTED_BAR_MISSING at the very first instant.
    assert sc.five_min.quality is SessionDataQualityStatus.TIMEFRAME_UNAVAILABLE


# --------------------------------------------------------------------------- #
# J/K/L/M/N — missing/absent data produce explicit, explained non-OK evidence
# --------------------------------------------------------------------------- #

def test_j_missing_expected_bar_is_explicit_and_explained(engine, calendar, sessions_cfg):
    as_of = datetime(2026, 8, 28, 9, 32, tzinfo=IST)
    five = [_m5(9, 15), _m5(9, 25)]  # 09:20 missing
    sc = _assess(engine, calendar, sessions_cfg, as_of=as_of, five=five)
    assert sc.five_min.quality is SessionDataQualityStatus.EXPECTED_BAR_MISSING
    assert sc.five_min.explanation
    assert "09:20" in sc.five_min.explanation


def test_k_no_current_session_candles(engine, calendar, sessions_cfg):
    as_of = datetime(2026, 8, 28, 9, 32, tzinfo=IST)
    yesterday = _m5(9, 15, day=date(2026, 8, 27))
    sc = _assess(engine, calendar, sessions_cfg, as_of=as_of, five=[yesterday])
    assert sc.five_min.quality is SessionDataQualityStatus.NO_CURRENT_SESSION_DATA


def test_l_only_5m_available(engine, calendar, sessions_cfg):
    as_of = datetime(2026, 8, 28, 9, 32, tzinfo=IST)
    sc = _assess(engine, calendar, sessions_cfg, as_of=as_of, five=[_m5(9, 15)], fifteen=[])
    assert sc.five_min.quality is not SessionDataQualityStatus.TIMEFRAME_UNAVAILABLE
    assert sc.fifteen_min.quality is SessionDataQualityStatus.TIMEFRAME_UNAVAILABLE


def test_m_only_15m_available(engine, calendar, sessions_cfg):
    as_of = datetime(2026, 8, 28, 9, 32, tzinfo=IST)
    sc = _assess(engine, calendar, sessions_cfg, as_of=as_of, five=[], fifteen=[_m15(9, 15)])
    assert sc.five_min.quality is SessionDataQualityStatus.TIMEFRAME_UNAVAILABLE
    assert sc.fifteen_min.quality is not SessionDataQualityStatus.TIMEFRAME_UNAVAILABLE


def test_n_neither_timeframe_available(engine, calendar, sessions_cfg):
    as_of = datetime(2026, 8, 28, 9, 32, tzinfo=IST)
    sc = _assess(engine, calendar, sessions_cfg, as_of=as_of, five=[], fifteen=[])
    assert sc.five_min.quality is SessionDataQualityStatus.TIMEFRAME_UNAVAILABLE
    assert sc.fifteen_min.quality is SessionDataQualityStatus.TIMEFRAME_UNAVAILABLE
    assert sc.data_quality is SessionDataQualityStatus.TIMEFRAME_UNAVAILABLE


def test_quote_unavailable_surfaces_in_combined_quality(engine, calendar, sessions_cfg):
    as_of = datetime(2026, 8, 28, 9, 32, tzinfo=IST)
    five = [_m5(9, 15), _m5(9, 20), _m5(9, 25)]
    fifteen = [_m15(9, 15)]
    sc = _assess(engine, calendar, sessions_cfg, as_of=as_of, five=five, fifteen=fifteen, quote_ts=None)
    assert sc.five_min.quality is SessionDataQualityStatus.SUFFICIENT
    assert sc.fifteen_min.quality is SessionDataQualityStatus.SUFFICIENT
    assert sc.data_quality is SessionDataQualityStatus.QUOTE_UNAVAILABLE
    assert sc.latest_quote_ts is None


def test_weekend_is_session_not_active_not_fabricated_as_a_gap(engine, calendar, sessions_cfg):
    sunday = datetime(2026, 8, 30, 10, 0, tzinfo=IST)
    sc = _assess(engine, calendar, sessions_cfg, as_of=sunday, five=[], fifteen=[])
    assert sc.phase is SessionPhase.NOT_A_TRADING_SESSION
    assert sc.data_quality is SessionDataQualityStatus.SESSION_NOT_ACTIVE
    assert sc.five_min.quality is SessionDataQualityStatus.SESSION_NOT_ACTIVE
    assert sc.session_open_ts is None
    assert sc.session_close_ts is None


# --------------------------------------------------------------------------- #
# O — special/non-standard sessions, from REAL calendar fixtures (not fabricated)
# --------------------------------------------------------------------------- #

def test_o_special_full_session_on_a_sunday(engine, calendar, sessions_cfg):
    """2026-02-01: a real NSE/CMTR/72349-notified full-hours session on a
    Sunday (Union Budget) -- `config/calendar/holidays.json`'s own fixture."""
    as_of = datetime(2026, 2, 1, 9, 32, tzinfo=IST)
    sc = _assess(engine, calendar, sessions_cfg, as_of=as_of,
                 five=[_candle(IID, Timeframe.M5, datetime(2026, 2, 1, 9, 15, tzinfo=IST)),
                       _candle(IID, Timeframe.M5, datetime(2026, 2, 1, 9, 20, tzinfo=IST)),
                       _candle(IID, Timeframe.M5, datetime(2026, 2, 1, 9, 25, tzinfo=IST))])
    assert sc.session_type.value == "SPECIAL"
    assert sc.phase is SessionPhase.REGULAR
    assert sc.session_open_ts == datetime(2026, 2, 1, 9, 15, tzinfo=IST)
    assert sc.session_close_ts == datetime(2026, 2, 1, 15, 30, tzinfo=IST)


def test_o_muhurat_with_unnotified_timings_is_honestly_insufficient(engine, calendar, sessions_cfg):
    """2025-10-21: a real MUHURAT date whose `open`/`close` are `null` in
    `config/calendar/holidays.json` -- must not guess NORMAL hours."""
    as_of = datetime(2025, 10, 21, 18, 0, tzinfo=IST)  # Muhurat runs in the evening
    sc = _assess(engine, calendar, sessions_cfg, as_of=as_of,
                 five=[_candle(IID, Timeframe.M5, datetime(2025, 10, 21, 18, 0, tzinfo=IST))])
    assert sc.session_type.value == "MUHURAT"
    assert sc.session_open_ts is None
    assert sc.session_close_ts is None
    assert sc.five_min.quality is SessionDataQualityStatus.INSUFFICIENT_HISTORY
    assert sc.five_min.explanation


# --------------------------------------------------------------------------- #
# P — deterministic replay from identical inputs
# --------------------------------------------------------------------------- #

def test_p_deterministic_replay(engine, calendar, sessions_cfg):
    as_of = datetime(2026, 8, 28, 9, 32, tzinfo=IST)
    five = [_m5(9, 15), _m5(9, 20)]
    fifteen = [_m15(9, 15)]
    a = _assess(engine, calendar, sessions_cfg, as_of=as_of, five=five, fifteen=fifteen, quote_ts=as_of)
    b = SessionContextEngine().assess(  # a fresh engine instance -- no hidden shared state
        IID, as_of=as_of, exchange="NSE", calendar=calendar, sessions=sessions_cfg,
        tzinfo=IST, five_min_candles=list(five), fifteen_min_candles=list(fifteen),
        latest_quote_ts=as_of,
    )
    assert a == b


# --------------------------------------------------------------------------- #
# Elapsed/remaining session time
# --------------------------------------------------------------------------- #

def test_elapsed_and_remaining_session_seconds(engine, calendar, sessions_cfg):
    as_of = datetime(2026, 8, 28, 9, 32, tzinfo=IST)
    sc = _assess(engine, calendar, sessions_cfg, as_of=as_of)
    assert sc.elapsed_seconds == 17 * 60
    assert sc.remaining_seconds == (6 * 60 + 15) * 60 - 17 * 60


def test_preopen_phase_from_real_config_window(engine, calendar, sessions_cfg):
    as_of = datetime(2026, 8, 28, 9, 5, tzinfo=IST)  # inside real 09:00-09:08 preopen
    sc = _assess(engine, calendar, sessions_cfg, as_of=as_of)
    assert sc.phase is SessionPhase.PRE_OPEN
    assert sc.elapsed_seconds == 0


def test_closed_phase_after_regular_close(engine, calendar, sessions_cfg):
    as_of = datetime(2026, 8, 28, 15, 45, tzinfo=IST)
    sc = _assess(engine, calendar, sessions_cfg, as_of=as_of)
    assert sc.phase is SessionPhase.CLOSED
    assert sc.remaining_seconds == 0
