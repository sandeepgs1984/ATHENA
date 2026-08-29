"""Opening Range Engine (ID-3) — OR15/OR30 analytical evidence. No BUY/SELL,
no entry zone, no stop/target, no STRONG/WEAK/FAILED label anywhere here;
see `athena.intraday.opening_range_engine`."""

from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from pathlib import Path
from zoneinfo import ZoneInfo

import pytest

from athena.calendar.engine import CalendarEngine
from athena.config.loader import load_config
from athena.domain.enums import Timeframe
from athena.domain.market import Candle
from athena.intraday import (
    BreakoutEvent,
    OpeningRangeEngine,
    OpeningRangeFormationStatus,
    OpeningRangeRelation,
    OpeningRangeWindow,
)
from athena.session import SessionContextEngine

IST = ZoneInfo("Asia/Kolkata")
CONFIG_DIR = Path(__file__).resolve().parents[2] / "config"
IID = "NSE:TEST"
DAY = date(2026, 8, 28)  # a real ordinary NSE trading Friday


@pytest.fixture()
def calendar() -> CalendarEngine:
    cfg = load_config(CONFIG_DIR)
    return CalendarEngine.from_config_dir(CONFIG_DIR, cfg.market)


@pytest.fixture()
def sessions_cfg():
    return load_config(CONFIG_DIR).market.sessions


@pytest.fixture()
def engine() -> OpeningRangeEngine:
    return OpeningRangeEngine()


def _m5(hh: int, mm: int, close, day: date = DAY, high=None, low=None) -> Candle:
    px = Decimal(str(close))
    hi = Decimal(str(high)) if high is not None else px + 1
    lo = Decimal(str(low)) if low is not None else px - 1
    return Candle(instrument_id=IID, timeframe=Timeframe.M5,
                  ts_open=datetime(day.year, day.month, day.day, hh, mm, tzinfo=IST),
                  open=px, high=hi, low=lo, close=px, volume=1_000, source="test")


def _session(calendar, sessions_cfg, *, as_of, candles):
    return SessionContextEngine().assess(
        IID, as_of=as_of, exchange="NSE", calendar=calendar, sessions=sessions_cfg,
        tzinfo=IST, five_min_candles=candles, fifteen_min_candles=[], latest_quote_ts=None,
    )


def _assess(engine, calendar, sessions_cfg, *, as_of, candles):
    sc = _session(calendar, sessions_cfg, as_of=as_of, candles=candles)
    return engine.assess(
        IID, as_of=as_of, session_context=sc, five_min_candles=candles,
        calendar=calendar, tzinfo=IST,
    )


# --------------------------------------------------------------------------- #
# 1/2 — range high/low correct from completed bars
# --------------------------------------------------------------------------- #

def test_1_or15_high_low_correct(engine, calendar, sessions_cfg):
    candles = [_m5(9, 15, 100, high=101, low=99), _m5(9, 20, 105, high=106, low=104),
               _m5(9, 25, 102, high=103, low=101)]
    as_of = datetime(2026, 8, 28, 9, 30, tzinfo=IST)  # OR15 window just elapsed
    result = _assess(engine, calendar, sessions_cfg, as_of=as_of, candles=candles)
    or15 = result[OpeningRangeWindow.OR15]
    assert or15.formation.status is OpeningRangeFormationStatus.COMPLETE
    assert or15.formation.high == Decimal("106")
    assert or15.formation.low == Decimal("99")


def test_2_or30_high_low_correct(engine, calendar, sessions_cfg):
    candles = [_m5(9, 15, 100, high=101, low=99), _m5(9, 20, 105, high=106, low=104),
               _m5(9, 25, 102, high=103, low=101), _m5(9, 30, 108, high=109, low=107),
               _m5(9, 35, 95, high=96, low=94), _m5(9, 40, 100, high=101, low=99)]
    as_of = datetime(2026, 8, 28, 9, 45, tzinfo=IST)  # OR30 window just elapsed
    result = _assess(engine, calendar, sessions_cfg, as_of=as_of, candles=candles)
    or30 = result[OpeningRangeWindow.OR30]
    assert or30.formation.status is OpeningRangeFormationStatus.COMPLETE
    assert or30.formation.high == Decimal("109")
    assert or30.formation.low == Decimal("94")


# --------------------------------------------------------------------------- #
# 3/4/5/6 — FORMING vs COMPLETE, exact boundaries
# --------------------------------------------------------------------------- #

def test_3_or15_forming_before_completion(engine, calendar, sessions_cfg):
    candles = [_m5(9, 15, 100), _m5(9, 20, 101)]
    as_of = datetime(2026, 8, 28, 9, 27, tzinfo=IST)  # window (09:15-09:30) not yet elapsed
    result = _assess(engine, calendar, sessions_cfg, as_of=as_of, candles=candles)
    assert result[OpeningRangeWindow.OR15].formation.status is OpeningRangeFormationStatus.FORMING


def test_4_or15_complete_exactly_at_boundary(engine, calendar, sessions_cfg):
    candles = [_m5(9, 15, 100), _m5(9, 20, 101), _m5(9, 25, 102)]
    one_second_before = datetime(2026, 8, 28, 9, 29, 59, tzinfo=IST)
    at_boundary = datetime(2026, 8, 28, 9, 30, 0, tzinfo=IST)
    before = _assess(engine, calendar, sessions_cfg, as_of=one_second_before, candles=candles)
    at = _assess(engine, calendar, sessions_cfg, as_of=at_boundary, candles=candles)
    assert before[OpeningRangeWindow.OR15].formation.status is OpeningRangeFormationStatus.FORMING
    assert at[OpeningRangeWindow.OR15].formation.status is OpeningRangeFormationStatus.COMPLETE


def test_5_or30_forming_while_or15_already_complete(engine, calendar, sessions_cfg):
    candles = [_m5(9, 15, 100), _m5(9, 20, 101), _m5(9, 25, 102)]
    as_of = datetime(2026, 8, 28, 9, 32, tzinfo=IST)  # OR15 done, OR30 (ends 09:45) still forming
    result = _assess(engine, calendar, sessions_cfg, as_of=as_of, candles=candles)
    assert result[OpeningRangeWindow.OR15].formation.status is OpeningRangeFormationStatus.COMPLETE
    assert result[OpeningRangeWindow.OR30].formation.status is OpeningRangeFormationStatus.FORMING


def test_6_or30_complete_at_its_exact_boundary(engine, calendar, sessions_cfg):
    candles = [_m5(9, 15, 100), _m5(9, 20, 101), _m5(9, 25, 102),
               _m5(9, 30, 103), _m5(9, 35, 104), _m5(9, 40, 105)]
    one_second_before = datetime(2026, 8, 28, 9, 44, 59, tzinfo=IST)
    at_boundary = datetime(2026, 8, 28, 9, 45, 0, tzinfo=IST)
    before = _assess(engine, calendar, sessions_cfg, as_of=one_second_before, candles=candles)
    at = _assess(engine, calendar, sessions_cfg, as_of=at_boundary, candles=candles)
    assert before[OpeningRangeWindow.OR30].formation.status is OpeningRangeFormationStatus.FORMING
    assert at[OpeningRangeWindow.OR30].formation.status is OpeningRangeFormationStatus.COMPLETE


# --------------------------------------------------------------------------- #
# 7/8 — non-vacuous: a forming candle cannot alter the range
# --------------------------------------------------------------------------- #

def test_7_forming_candle_cannot_alter_or15(engine, calendar, sessions_cfg):
    """An extreme 09:25 candle, still forming at 09:29:59, must not move
    OR15's high — proven by comparing against the boundary instant where it
    legitimately becomes eligible."""
    baseline = [_m5(9, 15, 100, high=101, low=99), _m5(9, 20, 100, high=101, low=99)]
    extreme = _m5(9, 25, 500, high=501, low=499)
    just_before = datetime(2026, 8, 28, 9, 29, 59, tzinfo=IST)
    at_boundary = datetime(2026, 8, 28, 9, 30, 0, tzinfo=IST)

    with_extreme = [*baseline, extreme]
    before = _assess(engine, calendar, sessions_cfg, as_of=just_before, candles=with_extreme)
    at = _assess(engine, calendar, sessions_cfg, as_of=at_boundary, candles=with_extreme)

    # 09:25+5m=09:30 -- not yet eligible at 09:29:59 (still forming), eligible at 09:30:00.
    assert before[OpeningRangeWindow.OR15].formation.bars_present == 2
    assert before[OpeningRangeWindow.OR15].formation.high == Decimal("101")
    assert at[OpeningRangeWindow.OR15].formation.bars_present == 3
    assert at[OpeningRangeWindow.OR15].formation.high == Decimal("501")


def test_8_forming_candle_cannot_alter_or30(engine, calendar, sessions_cfg):
    baseline = [_m5(9, 15, 100, high=101, low=99), _m5(9, 20, 100, high=101, low=99),
                _m5(9, 25, 100, high=101, low=99), _m5(9, 30, 100, high=101, low=99),
                _m5(9, 35, 100, high=101, low=99)]
    extreme = _m5(9, 40, 500, high=501, low=499)
    just_before = datetime(2026, 8, 28, 9, 44, 59, tzinfo=IST)
    at_boundary = datetime(2026, 8, 28, 9, 45, 0, tzinfo=IST)

    with_extreme = [*baseline, extreme]
    before = _assess(engine, calendar, sessions_cfg, as_of=just_before, candles=with_extreme)
    at = _assess(engine, calendar, sessions_cfg, as_of=at_boundary, candles=with_extreme)

    assert before[OpeningRangeWindow.OR30].formation.bars_present == 5
    assert before[OpeningRangeWindow.OR30].formation.high == Decimal("101")
    assert at[OpeningRangeWindow.OR30].formation.bars_present == 6
    assert at[OpeningRangeWindow.OR30].formation.high == Decimal("501")


# --------------------------------------------------------------------------- #
# 9/10 — missing expected bar -> INCOMPLETE_DATA, never silently COMPLETE
# --------------------------------------------------------------------------- #

def test_9_missing_expected_or15_bar_is_incomplete_not_complete(engine, calendar, sessions_cfg):
    candles = [_m5(9, 15, 100), _m5(9, 25, 102)]  # 09:20 missing
    as_of = datetime(2026, 8, 28, 9, 30, tzinfo=IST)
    result = _assess(engine, calendar, sessions_cfg, as_of=as_of, candles=candles)
    or15 = result[OpeningRangeWindow.OR15]
    assert or15.formation.status is OpeningRangeFormationStatus.INCOMPLETE_DATA
    assert or15.formation.bars_present == 2
    assert or15.formation.bars_expected == 3
    assert or15.relation is OpeningRangeRelation.UNAVAILABLE  # never trusted as final


def test_10_missing_expected_or30_bar_is_incomplete_not_complete(engine, calendar, sessions_cfg):
    candles = [_m5(9, 15, 100), _m5(9, 20, 101), _m5(9, 25, 102),
               _m5(9, 30, 103), _m5(9, 40, 105)]  # 09:35 missing
    as_of = datetime(2026, 8, 28, 9, 45, tzinfo=IST)
    result = _assess(engine, calendar, sessions_cfg, as_of=as_of, candles=candles)
    or30 = result[OpeningRangeWindow.OR30]
    assert or30.formation.status is OpeningRangeFormationStatus.INCOMPLETE_DATA
    assert or30.formation.bars_present == 5
    assert or30.formation.bars_expected == 6


# --------------------------------------------------------------------------- #
# 11/12/13/14 — current range relation
# --------------------------------------------------------------------------- #

def _or15_fixture(post_range_close):
    """3 fixed bars form a stable OR15 range ([99, 101]); a 4th bar AFTER
    the window (09:30) carries the price under test — the range's own
    3 bars must never themselves be used as the "current price," since a
    range-forming bar's close can never legitimately exceed the range it
    itself defines."""
    return [_m5(9, 15, 100, high=101, low=99), _m5(9, 20, 100, high=101, low=99),
            _m5(9, 25, 100, high=101, low=99),
            _m5(9, 30, post_range_close,
                high=Decimal(post_range_close) + 1, low=Decimal(post_range_close) - 1)]


def test_11_above_range_relation(engine, calendar, sessions_cfg):
    result = _assess(engine, calendar, sessions_cfg,
                      as_of=datetime(2026, 8, 28, 9, 35, tzinfo=IST), candles=_or15_fixture(105))
    assert result[OpeningRangeWindow.OR15].relation is OpeningRangeRelation.ABOVE_RANGE


def test_12_below_range_relation(engine, calendar, sessions_cfg):
    result = _assess(engine, calendar, sessions_cfg,
                      as_of=datetime(2026, 8, 28, 9, 35, tzinfo=IST), candles=_or15_fixture(95))
    assert result[OpeningRangeWindow.OR15].relation is OpeningRangeRelation.BELOW_RANGE


def test_13_inside_range_relation(engine, calendar, sessions_cfg):
    result = _assess(engine, calendar, sessions_cfg,
                      as_of=datetime(2026, 8, 28, 9, 35, tzinfo=IST), candles=_or15_fixture(100))
    assert result[OpeningRangeWindow.OR15].relation is OpeningRangeRelation.INSIDE_RANGE


def test_14_exact_boundary_relation(engine, calendar, sessions_cfg):
    # range high/low both == 101/99 from the first two bars; a 4th completed
    # bar closing exactly at the high must read AT_HIGH, not ABOVE_RANGE.
    candles = [_m5(9, 15, 100, high=101, low=99), _m5(9, 20, 100, high=101, low=99),
               _m5(9, 25, 100, high=101, low=99), _m5(9, 30, 101, high=101, low=101)]
    as_of = datetime(2026, 8, 28, 9, 35, tzinfo=IST)
    result = _assess(engine, calendar, sessions_cfg, as_of=as_of, candles=candles)
    assert result[OpeningRangeWindow.OR15].relation is OpeningRangeRelation.AT_HIGH


# --------------------------------------------------------------------------- #
# 15/16/17 — breakout EVENT vs relation
# --------------------------------------------------------------------------- #

def test_15_genuine_upside_breakout_transition(engine, calendar, sessions_cfg):
    candles = [_m5(9, 15, 100, high=101, low=99), _m5(9, 20, 100, high=101, low=99),
               _m5(9, 25, 100, high=101, low=99),  # OR15 range: high=101, low=99
               _m5(9, 30, 100, high=101, low=99),  # still inside
               _m5(9, 35, 105, high=106, low=104)]  # crosses above 101
    as_of = datetime(2026, 8, 28, 9, 40, tzinfo=IST)
    result = _assess(engine, calendar, sessions_cfg, as_of=as_of, candles=candles)
    or15 = result[OpeningRangeWindow.OR15]
    assert or15.breakout_event is BreakoutEvent.UPSIDE_BREAKOUT_EVENT
    assert or15.first_breakout_ts == datetime(2026, 8, 28, 9, 35, tzinfo=IST)


def test_16_genuine_downside_breakdown_transition(engine, calendar, sessions_cfg):
    candles = [_m5(9, 15, 100, high=101, low=99), _m5(9, 20, 100, high=101, low=99),
               _m5(9, 25, 100, high=101, low=99),
               _m5(9, 30, 100, high=101, low=99),
               _m5(9, 35, 95, high=96, low=94)]  # crosses below 99
    as_of = datetime(2026, 8, 28, 9, 40, tzinfo=IST)
    result = _assess(engine, calendar, sessions_cfg, as_of=as_of, candles=candles)
    or15 = result[OpeningRangeWindow.OR15]
    assert or15.breakout_event is BreakoutEvent.DOWNSIDE_BREAKDOWN_EVENT
    assert or15.first_breakout_ts == datetime(2026, 8, 28, 9, 35, tzinfo=IST)


def test_17_sustained_extension_is_not_repeatedly_relabelled_a_new_event(engine, calendar, sessions_cfg):
    """Section 7: "a stock currently above the opening range is not
    necessarily breaking out NOW." Once a genuine transition is found (the
    range's own last completed bar, close=100 <= high=101, followed by the
    first post-range bar breaking above), every SUBSEQUENT bar that is
    merely still-above must not be relabelled as a fresh event -- the
    engine must report the ORIGINAL first_breakout_ts, not the latest bar,
    and must not claim NO_EVENT/a second event just because price never
    dipped back inside in between."""
    candles = [_m5(9, 15, 100, high=101, low=99), _m5(9, 20, 100, high=101, low=99),
               _m5(9, 25, 100, high=101, low=99),
               _m5(9, 30, 105, high=106, low=104),  # first genuine crossing
               _m5(9, 35, 106, high=107, low=105),  # still above -- not a new event
               _m5(9, 40, 107, high=108, low=106)]  # still above -- not a new event
    as_of = datetime(2026, 8, 28, 9, 45, tzinfo=IST)
    result = _assess(engine, calendar, sessions_cfg, as_of=as_of, candles=candles)
    or15 = result[OpeningRangeWindow.OR15]
    assert or15.relation is OpeningRangeRelation.ABOVE_RANGE
    assert or15.breakout_event is BreakoutEvent.UPSIDE_BREAKOUT_EVENT
    assert or15.first_breakout_ts == datetime(2026, 8, 28, 9, 30, tzinfo=IST)  # not 9:35 or 9:40
    assert or15.bars_since_breakout == 2  # 9:30 (0), 9:35 (1), 9:40 (2)


def test_17b_not_observed_with_no_post_range_bars_yet(engine, calendar, sessions_cfg):
    """The genuine NOT_OBSERVED case: the range has just completed and no
    bar exists after it yet -- there is nothing to compare against, so no
    event can be checked (distinct from `relation`, which is still
    computable from the range's own last bar)."""
    candles = [_m5(9, 15, 100, high=101, low=99), _m5(9, 20, 100, high=101, low=99),
               _m5(9, 25, 100, high=101, low=99)]
    as_of = datetime(2026, 8, 28, 9, 30, tzinfo=IST)  # OR15 just COMPLETE, nothing after it
    result = _assess(engine, calendar, sessions_cfg, as_of=as_of, candles=candles)
    or15 = result[OpeningRangeWindow.OR15]
    assert or15.formation.status is OpeningRangeFormationStatus.COMPLETE
    assert or15.relation is OpeningRangeRelation.INSIDE_RANGE
    assert or15.breakout_event is BreakoutEvent.NOT_OBSERVED


# --------------------------------------------------------------------------- #
# 18/19 — post-breakout measurements
# --------------------------------------------------------------------------- #

def test_18_returned_inside_range_measurement(engine, calendar, sessions_cfg):
    candles = [_m5(9, 15, 100, high=101, low=99), _m5(9, 20, 100, high=101, low=99),
               _m5(9, 25, 100, high=101, low=99),
               _m5(9, 30, 100, high=101, low=99),
               _m5(9, 35, 105, high=106, low=104),  # breaks out
               _m5(9, 40, 100, high=101, low=99)]  # returns inside
    as_of = datetime(2026, 8, 28, 9, 45, tzinfo=IST)
    result = _assess(engine, calendar, sessions_cfg, as_of=as_of, candles=candles)
    or15 = result[OpeningRangeWindow.OR15]
    assert or15.breakout_event is BreakoutEvent.UPSIDE_BREAKOUT_EVENT
    assert or15.returned_inside_range is True
    assert or15.bars_since_breakout == 1


def test_19_first_breakout_timestamp_deterministic(engine, calendar, sessions_cfg):
    candles = [_m5(9, 15, 100, high=101, low=99), _m5(9, 20, 100, high=101, low=99),
               _m5(9, 25, 100, high=101, low=99),
               _m5(9, 30, 100, high=101, low=99),
               _m5(9, 35, 105, high=106, low=104)]
    as_of = datetime(2026, 8, 28, 9, 40, tzinfo=IST)
    a = _assess(engine, calendar, sessions_cfg, as_of=as_of, candles=candles)
    b = OpeningRangeEngine().assess(  # fresh engine instance
        IID, as_of=as_of, session_context=_session(calendar, sessions_cfg, as_of=as_of, candles=candles),
        five_min_candles=candles, calendar=calendar, tzinfo=IST,
    )
    assert a[OpeningRangeWindow.OR15] == b[OpeningRangeWindow.OR15]


# --------------------------------------------------------------------------- #
# 20/21 — session-relative open, no hardcoded 09:15; real special session
# --------------------------------------------------------------------------- #

def test_20_and_21_special_session_open_used_not_hardcoded_0915(engine, calendar, sessions_cfg):
    """2026-02-01: a real NSE/CMTR/72349-notified full-hours session on a
    Sunday (Union Budget) -- happens to share the ordinary 09:15 open, so
    this proves the engine reads `SessionContext.session_open_ts` (which
    itself is calendar-derived) rather than a module-level literal, by
    using a real session on a day that is not, by default, a trading day
    at all (Sunday)."""
    day = date(2026, 2, 1)
    candles = [_m5(9, 15, 100, day=day, high=101, low=99),
               _m5(9, 20, 102, day=day, high=103, low=101),
               _m5(9, 25, 101, day=day, high=102, low=100)]
    as_of = datetime(2026, 2, 1, 9, 30, tzinfo=IST)
    result = _assess(engine, calendar, sessions_cfg, as_of=as_of, candles=candles)
    or15 = result[OpeningRangeWindow.OR15]
    assert or15.formation.status is OpeningRangeFormationStatus.COMPLETE
    assert or15.formation.range_start == datetime(2026, 2, 1, 9, 15, tzinfo=IST)


def test_muhurat_with_unnotified_timings_is_not_available(engine, calendar, sessions_cfg):
    """2025-10-21: a real MUHURAT date whose open/close are `null` in
    `config/calendar/holidays.json` -- must not guess NORMAL hours."""
    day = date(2025, 10, 21)
    as_of = datetime(2025, 10, 21, 18, 0, tzinfo=IST)
    candles = [_m5(18, 0, 100, day=day)]
    result = _assess(engine, calendar, sessions_cfg, as_of=as_of, candles=candles)
    assert result[OpeningRangeWindow.OR15].formation.status is OpeningRangeFormationStatus.NOT_AVAILABLE


# --------------------------------------------------------------------------- #
# 22/23 — no current-session data; non-trading session
# --------------------------------------------------------------------------- #

def test_22_no_current_session_data(engine, calendar, sessions_cfg):
    yesterday = _m5(9, 15, 100, day=date(2026, 8, 27))
    as_of = datetime(2026, 8, 28, 9, 30, tzinfo=IST)
    result = _assess(engine, calendar, sessions_cfg, as_of=as_of, candles=[yesterday])
    or15 = result[OpeningRangeWindow.OR15]
    assert or15.formation.status is OpeningRangeFormationStatus.INCOMPLETE_DATA
    assert or15.formation.bars_present == 0


def test_23_non_trading_session_is_not_applicable(engine, calendar, sessions_cfg):
    sunday = datetime(2026, 8, 30, 10, 0, tzinfo=IST)
    result = _assess(engine, calendar, sessions_cfg, as_of=sunday, candles=[])
    or15 = result[OpeningRangeWindow.OR15]
    assert or15.formation.status is OpeningRangeFormationStatus.NOT_APPLICABLE
    assert or15.relation is OpeningRangeRelation.UNAVAILABLE
    assert or15.breakout_event is BreakoutEvent.NOT_OBSERVED


# --------------------------------------------------------------------------- #
# 24 — explicit as_of determinism (repeat run, identical result)
# --------------------------------------------------------------------------- #

def test_24_deterministic_replay(engine, calendar, sessions_cfg):
    candles = [_m5(9, 15, 100, high=101, low=99), _m5(9, 20, 102, high=103, low=101)]
    as_of = datetime(2026, 8, 28, 9, 25, tzinfo=IST)
    a = _assess(engine, calendar, sessions_cfg, as_of=as_of, candles=candles)
    b = _assess(engine, calendar, sessions_cfg, as_of=as_of, candles=candles)
    assert a == b


# --------------------------------------------------------------------------- #
# ID-3.1 — canonical-slot integrity: an off-grid/unexpected timestamp must
# never substitute for a missing canonical slot, alter range high/low/volume,
# or trigger a false breakout.
# --------------------------------------------------------------------------- #

def test_25_off_grid_substitute_cannot_mask_a_genuinely_missing_slot(engine, calendar, sessions_cfg):
    """Expected OR15 canonical slots: 09:15, 09:20, 09:25. Actual persisted
    rows: 09:15, 09:16 (off-grid), 09:20 -- 09:25 genuinely missing. A raw
    row-count comparison (3 present == 3 expected) would wrongly report
    COMPLETE; the off-grid 09:16 row must not be able to stand in for the
    missing 09:25 canonical slot. This test fails against the pre-ID-3.1
    implementation (bars_present counted all in-window rows, not just
    canonical ones)."""
    candles = [_m5(9, 15, 100, high=101, low=99), _m5(9, 16, 999, high=1000, low=998),
               _m5(9, 20, 100, high=101, low=99)]  # 09:25 missing
    as_of = datetime(2026, 8, 28, 9, 30, tzinfo=IST)
    result = _assess(engine, calendar, sessions_cfg, as_of=as_of, candles=candles)
    or15 = result[OpeningRangeWindow.OR15]
    assert or15.formation.status is OpeningRangeFormationStatus.INCOMPLETE_DATA
    assert or15.formation.bars_present == 2  # only the 2 canonical bars (09:15, 09:20)
    assert or15.formation.bars_expected == 3
    assert or15.relation is OpeningRangeRelation.UNAVAILABLE


def test_26_off_grid_extreme_inside_window_cannot_alter_range_high_low_or_volume(
    engine, calendar, sessions_cfg
):
    baseline = [_m5(9, 15, 100, high=101, low=99), _m5(9, 20, 100, high=101, low=99),
                _m5(9, 25, 100, high=101, low=99)]
    off_grid_extreme = _m5(9, 17, 500, high=9_999, low=1)
    as_of = datetime(2026, 8, 28, 9, 30, tzinfo=IST)

    without = _assess(engine, calendar, sessions_cfg, as_of=as_of, candles=baseline)
    with_extra = _assess(
        engine, calendar, sessions_cfg, as_of=as_of, candles=[*baseline, off_grid_extreme]
    )
    f0, f1 = without[OpeningRangeWindow.OR15].formation, with_extra[OpeningRangeWindow.OR15].formation
    assert f1.status is OpeningRangeFormationStatus.COMPLETE
    assert f1.high == f0.high == Decimal("101")
    assert f1.low == f0.low == Decimal("99")
    assert f1.volume == f0.volume
    assert f1.bars_present == f0.bars_present == 3


def test_27_off_grid_post_range_bar_cannot_trigger_breakout_genuine_bar_can(
    engine, calendar, sessions_cfg
):
    range_bars = [_m5(9, 15, 100, high=101, low=99), _m5(9, 20, 100, high=101, low=99),
                  _m5(9, 25, 100, high=101, low=99)]  # OR15 range: high=101, low=99
    off_grid_post = _m5(9, 31, 500, high=501, low=499)  # not on the 5m grid
    as_of = datetime(2026, 8, 28, 9, 40, tzinfo=IST)

    only_off_grid = _assess(
        engine, calendar, sessions_cfg, as_of=as_of, candles=[*range_bars, off_grid_post]
    )
    or15_a = only_off_grid[OpeningRangeWindow.OR15]
    assert or15_a.breakout_event is BreakoutEvent.NOT_OBSERVED

    genuine_post = _m5(9, 35, 105, high=106, low=104)  # canonical, closes above 101
    with_genuine = _assess(
        engine, calendar, sessions_cfg, as_of=as_of,
        candles=[*range_bars, off_grid_post, genuine_post],
    )
    or15_b = with_genuine[OpeningRangeWindow.OR15]
    assert or15_b.breakout_event is BreakoutEvent.UPSIDE_BREAKOUT_EVENT
    assert or15_b.first_breakout_ts == datetime(2026, 8, 28, 9, 35, tzinfo=IST)


def test_naive_as_of_rejected(engine, calendar, sessions_cfg):
    sc = _session(calendar, sessions_cfg, as_of=datetime(2026, 8, 28, 9, 30, tzinfo=IST), candles=[])
    with pytest.raises(ValueError, match="timezone-aware"):
        engine.assess(
            IID, as_of=datetime(2026, 8, 28, 9, 30), session_context=sc,
            five_min_candles=[], calendar=calendar, tzinfo=IST,
        )
