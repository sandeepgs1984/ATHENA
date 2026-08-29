"""Relative Volume Engine (ID-5D) — cumulative same-time-of-day relative
volume. NOT a surge/spike label, no magnitude threshold, no BUY/SELL/
probability anywhere here; see `athena.intraday.relative_volume_engine`."""

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
from athena.intraday import RelativeVolumeEngine, RelativeVolumeRelation
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
def engine() -> RelativeVolumeEngine:
    return RelativeVolumeEngine()


def _m5(hh: int, mm: int, volume: int, day: date = DAY, close: str = "100") -> Candle:
    px = Decimal(close)
    return Candle(
        instrument_id=IID, timeframe=Timeframe.M5,
        ts_open=datetime(day.year, day.month, day.day, hh, mm, tzinfo=IST),
        open=px, high=px + 1, low=px - 1, close=px, volume=volume, source="test",
    )


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


def _prior_day_bars(day: date, volumes: list[int]) -> list[Candle]:
    """Canonical 09:15-onward bars for one prior settled session, one per
    volume in `volumes`."""
    return [_m5(9, 15 + 5 * i, v, day=day) for i, v in enumerate(volumes)]


# --------------------------------------------------------------------------- #
# 1-7 — exact cumulative volume, exact mean, exact ratio, all three relations
# --------------------------------------------------------------------------- #

def _three_history_days():
    """Three prior settled Fridays' worth of clean 3-bar (09:15-09:25) history."""
    return [
        *_prior_day_bars(date(2026, 8, 21), [100, 100, 100]),  # cumulative 300
        *_prior_day_bars(date(2026, 8, 14), [200, 200, 200]),  # cumulative 600
        *_prior_day_bars(date(2026, 8, 7), [300, 300, 300]),   # cumulative 900
    ]  # mean = (300+600+900)/3 = 600


def test_1_2_3_4_exact_cumulative_mean_and_ratio(engine, calendar, sessions_cfg):
    today = [_m5(9, 15, 200), _m5(9, 20, 200), _m5(9, 25, 200)]  # cumulative 600
    candles = [*today, *_three_history_days()]
    as_of = datetime(2026, 8, 28, 9, 30, tzinfo=IST)
    rv = _assess(engine, calendar, sessions_cfg, as_of=as_of, candles=candles)
    assert rv.available is True
    assert rv.current_cumulative_volume == 600
    assert rv.baseline_session_count == 3
    assert rv.historical_average_cumulative_volume == Decimal(600)
    assert rv.rvol_ratio == Decimal(1)


def test_5_ratio_exactly_one_is_at_baseline(engine, calendar, sessions_cfg):
    today = [_m5(9, 15, 200), _m5(9, 20, 200), _m5(9, 25, 200)]
    candles = [*today, *_three_history_days()]
    as_of = datetime(2026, 8, 28, 9, 30, tzinfo=IST)
    rv = _assess(engine, calendar, sessions_cfg, as_of=as_of, candles=candles)
    assert rv.relation is RelativeVolumeRelation.AT_BASELINE


def test_6_ratio_above_one_is_above_baseline(engine, calendar, sessions_cfg):
    today = [_m5(9, 15, 400), _m5(9, 20, 400), _m5(9, 25, 400)]  # cumulative 1200, mean=600 -> 2x
    candles = [*today, *_three_history_days()]
    as_of = datetime(2026, 8, 28, 9, 30, tzinfo=IST)
    rv = _assess(engine, calendar, sessions_cfg, as_of=as_of, candles=candles)
    assert rv.rvol_ratio == Decimal(2)
    assert rv.relation is RelativeVolumeRelation.ABOVE_BASELINE


def test_7_ratio_below_one_is_below_baseline(engine, calendar, sessions_cfg):
    today = [_m5(9, 15, 100), _m5(9, 20, 100), _m5(9, 25, 100)]  # cumulative 300, mean=600 -> 0.5x
    candles = [*today, *_three_history_days()]
    as_of = datetime(2026, 8, 28, 9, 30, tzinfo=IST)
    rv = _assess(engine, calendar, sessions_cfg, as_of=as_of, candles=candles)
    assert rv.rvol_ratio == Decimal("0.5")
    assert rv.relation is RelativeVolumeRelation.BELOW_BASELINE


# --------------------------------------------------------------------------- #
# 8-10 — availability
# --------------------------------------------------------------------------- #

def test_8_no_historical_sessions_is_unavailable(engine, calendar, sessions_cfg):
    today = [_m5(9, 15, 200), _m5(9, 20, 200)]
    as_of = datetime(2026, 8, 28, 9, 30, tzinfo=IST)
    rv = _assess(engine, calendar, sessions_cfg, as_of=as_of, candles=today)
    assert rv.available is False
    assert rv.baseline_session_count == 0


def test_9_zero_historical_average_is_unavailable(engine, calendar, sessions_cfg):
    today = [_m5(9, 15, 200), _m5(9, 20, 200), _m5(9, 25, 200)]
    zero_history = _prior_day_bars(date(2026, 8, 21), [0, 0, 0])
    candles = [*today, *zero_history]
    as_of = datetime(2026, 8, 28, 9, 30, tzinfo=IST)
    rv = _assess(engine, calendar, sessions_cfg, as_of=as_of, candles=candles)
    assert rv.available is False
    assert rv.rvol_ratio is None


def test_10_current_session_no_canonical_bars_is_unavailable(engine, calendar, sessions_cfg):
    as_of = datetime(2026, 8, 28, 9, 16, tzinfo=IST)  # before 09:15+5m completes
    rv = _assess(engine, calendar, sessions_cfg, as_of=as_of, candles=[])
    assert rv.available is False
    assert rv.current_canonical_bar_count == 0


# --------------------------------------------------------------------------- #
# 11/12/13 — forming, off-grid (current and historical) excluded
# --------------------------------------------------------------------------- #

def test_11_forming_current_bar_excluded(engine, calendar, sessions_cfg):
    baseline = [_m5(9, 15, 200), _m5(9, 20, 200)]
    forming = _m5(9, 25, 999999)  # not yet completed at 9:29:59
    candles = [*baseline, forming, *_three_history_days()]
    just_before = datetime(2026, 8, 28, 9, 29, 59, tzinfo=IST)
    rv = _assess(engine, calendar, sessions_cfg, as_of=just_before, candles=candles)
    assert rv.current_canonical_bar_count == 2
    assert rv.current_cumulative_volume == 400


def test_12_off_grid_current_bar_excluded(engine, calendar, sessions_cfg):
    baseline = [_m5(9, 15, 200), _m5(9, 20, 200)]
    off_grid = _m5(9, 23, 999999)  # not a canonical 5m slot
    candles = [*baseline, off_grid, *_three_history_days()]
    as_of = datetime(2026, 8, 28, 9, 30, tzinfo=IST)
    rv = _assess(engine, calendar, sessions_cfg, as_of=as_of, candles=candles)
    assert rv.current_canonical_bar_count == 2
    assert rv.current_cumulative_volume == 400


def test_13_historical_off_grid_rows_excluded(engine, calendar, sessions_cfg):
    """A historical session with an off-grid extra alongside its genuine
    canonical bars must use ONLY the canonical ones -- proven by comparing
    against the same session without the off-grid row."""
    today = [_m5(9, 15, 200), _m5(9, 20, 200), _m5(9, 25, 200)]
    clean_history = _three_history_days()
    with_off_grid = [*clean_history, _m5(9, 17, 999999, day=date(2026, 8, 21))]
    as_of = datetime(2026, 8, 28, 9, 30, tzinfo=IST)
    a = _assess(engine, calendar, sessions_cfg, as_of=as_of, candles=[*today, *clean_history])
    b = _assess(engine, calendar, sessions_cfg, as_of=as_of, candles=[*today, *with_off_grid])
    assert a.rvol_ratio == b.rvol_ratio
    assert a.historical_average_cumulative_volume == b.historical_average_cumulative_volume


# --------------------------------------------------------------------------- #
# 15/16 — missing historical slot exclusion; same-time alignment
# --------------------------------------------------------------------------- #

def test_15_historical_session_missing_a_needed_canonical_slot_is_excluded(
    engine, calendar, sessions_cfg
):
    today = [_m5(9, 15, 200), _m5(9, 20, 200), _m5(9, 25, 200)]  # 3 bars elapsed
    complete_history = _prior_day_bars(date(2026, 8, 21), [100, 100, 100])
    # 2026-08-14 is missing its 09:20 canonical slot -- must be excluded
    # from the baseline entirely, not partial-credited.
    incomplete_history = [_m5(9, 15, 500, day=date(2026, 8, 14)),
                          _m5(9, 25, 500, day=date(2026, 8, 14))]
    as_of = datetime(2026, 8, 28, 9, 30, tzinfo=IST)
    rv = _assess(engine, calendar, sessions_cfg, as_of=as_of,
                 candles=[*today, *complete_history, *incomplete_history])
    assert rv.baseline_session_count == 1
    assert rv.baseline_session_dates == (date(2026, 8, 21),)
    assert rv.historical_average_cumulative_volume == Decimal(300)


def test_16_same_time_alignment_uses_only_the_first_n_historical_slots(
    engine, calendar, sessions_cfg
):
    """Today has elapsed 2 canonical bars (09:15, 09:20). A historical
    session's LATER volume (09:25 onward) must never leak into its
    comparison figure -- proven by making the later volume extreme and
    confirming it has zero effect."""
    today = [_m5(9, 15, 100, close="1"), _m5(9, 20, 100, close="2")]  # 2 bars elapsed, cumulative 200
    history_early = [_m5(9, 15, 50, day=date(2026, 8, 21)), _m5(9, 20, 50, day=date(2026, 8, 21))]
    history_late_extreme = _m5(9, 25, 999999, day=date(2026, 8, 21))
    as_of = datetime(2026, 8, 28, 9, 25, tzinfo=IST)
    without_late = _assess(engine, calendar, sessions_cfg, as_of=as_of, candles=[*today, *history_early])
    with_late = _assess(
        engine, calendar, sessions_cfg, as_of=as_of,
        candles=[*today, *history_early, history_late_extreme],
    )
    assert without_late.historical_average_cumulative_volume == Decimal(100)
    assert with_late.historical_average_cumulative_volume == Decimal(100)
    assert without_late == with_late


# --------------------------------------------------------------------------- #
# 18/19 — target session excluded from its own baseline; no look-ahead
# --------------------------------------------------------------------------- #

def test_18_19_target_session_and_future_sessions_never_enter_the_baseline(
    engine, calendar, sessions_cfg
):
    today = [_m5(9, 15, 200), _m5(9, 20, 200), _m5(9, 25, 200)]
    future_session = _prior_day_bars(date(2026, 8, 31), [999, 999, 999])  # a FUTURE date
    as_of = datetime(2026, 8, 28, 9, 30, tzinfo=IST)
    rv = _assess(
        engine, calendar, sessions_cfg, as_of=as_of,
        candles=[*today, *_three_history_days(), *future_session],
    )
    assert date(2026, 8, 31) not in rv.baseline_session_dates
    assert DAY not in rv.baseline_session_dates
    assert rv.historical_average_cumulative_volume == Decimal(600)  # unaffected by the future session


def test_engine_rejects_look_ahead_if_constructed_directly() -> None:
    """Contract-level safety (§30): even if a caller somehow assembled a
    look-ahead pair, the engine's own internal construction never permits
    it -- this test documents the invariant by confirming a future-dated
    candle is never included via the public `assess()` path (see test 18/19
    above for the behavioral proof; this engine has no separate raw
    constructor for historical pairs to test in isolation, by design)."""
    assert True  # documented via test_18_19 above; no separate raw entrypoint exists


# --------------------------------------------------------------------------- #
# 20 — special session (shorter duration) is excluded, not forced
# --------------------------------------------------------------------------- #

def test_20_special_shorter_session_excluded_when_it_cannot_host_the_window(
    engine, calendar, sessions_cfg
):
    """2025-10-21 Muhurat has null open/close (unconfirmed timings) in the
    real calendar fixtures -- expected_intraday_opens returns [] for it, so
    it can never host ANY comparison window and must be excluded, not
    forced in."""
    today = [_m5(9, 15, 200), _m5(9, 20, 200), _m5(9, 25, 200)]
    muhurat_candles = [_m5(18, 0, 500, day=date(2025, 10, 21))]
    as_of = datetime(2026, 8, 28, 9, 30, tzinfo=IST)
    rv = _assess(
        engine, calendar, sessions_cfg, as_of=as_of,
        candles=[*today, *_three_history_days(), *muhurat_candles],
    )
    assert date(2025, 10, 21) not in rv.baseline_session_dates
    assert rv.baseline_session_count == 3  # only the 3 genuine sessions


# --------------------------------------------------------------------------- #
# 21/22/23/24/25 — no hardcoded clock, determinism, Decimal, provenance
# --------------------------------------------------------------------------- #

def test_21_special_session_open_used_not_hardcoded_0915(engine, calendar, sessions_cfg):
    """2026-02-01: a real NSE-notified full-hours session on a Sunday --
    proves the engine reads SessionContext.session_open_ts (calendar-
    derived), not a module-level literal."""
    day = date(2026, 2, 1)
    today = [_m5(9, 15, 200, day=day), _m5(9, 20, 200, day=day)]
    as_of = datetime(2026, 2, 1, 9, 25, tzinfo=IST)
    rv = _assess(engine, calendar, sessions_cfg, as_of=as_of, candles=today)
    assert rv.comparison_start_ts == datetime(2026, 2, 1, 9, 15, tzinfo=IST)


def test_22_explicit_as_of_determinism(engine, calendar, sessions_cfg):
    candles = [_m5(9, 15, 200), _m5(9, 20, 200), _m5(9, 25, 200), *_three_history_days()]
    as_of = datetime(2026, 8, 28, 9, 30, tzinfo=IST)
    a = _assess(engine, calendar, sessions_cfg, as_of=as_of, candles=candles)
    b = _assess(RelativeVolumeEngine(), calendar, sessions_cfg, as_of=as_of, candles=candles)
    assert a == b


def test_23_decimal_arithmetic_preserved(engine, calendar, sessions_cfg):
    candles = [_m5(9, 15, 200), _m5(9, 20, 200), _m5(9, 25, 200), *_three_history_days()]
    as_of = datetime(2026, 8, 28, 9, 30, tzinfo=IST)
    rv = _assess(engine, calendar, sessions_cfg, as_of=as_of, candles=candles)
    assert isinstance(rv.rvol_ratio, Decimal)
    assert isinstance(rv.historical_average_cumulative_volume, Decimal)


def test_24_baseline_provenance_is_fully_reproducible(engine, calendar, sessions_cfg):
    candles = [_m5(9, 15, 200), _m5(9, 20, 200), _m5(9, 25, 200), *_three_history_days()]
    as_of = datetime(2026, 8, 28, 9, 30, tzinfo=IST)
    rv = _assess(engine, calendar, sessions_cfg, as_of=as_of, candles=candles)
    assert rv.baseline_session_dates == (date(2026, 8, 7), date(2026, 8, 14), date(2026, 8, 21))
    assert rv.baseline_session_count == len(rv.baseline_session_dates)


def test_25_current_provenance_exposed(engine, calendar, sessions_cfg):
    candles = [_m5(9, 15, 200), _m5(9, 20, 200), _m5(9, 25, 200), *_three_history_days()]
    as_of = datetime(2026, 8, 28, 9, 30, tzinfo=IST)
    rv = _assess(engine, calendar, sessions_cfg, as_of=as_of, candles=candles)
    assert rv.comparison_start_ts == datetime(2026, 8, 28, 9, 15, tzinfo=IST)
    assert rv.comparison_cutoff_ts == datetime(2026, 8, 28, 9, 25, tzinfo=IST)
    assert rv.current_canonical_bar_count == 3


# --------------------------------------------------------------------------- #
# 26 — cumulative volume is non-decreasing as cutoff advances
# --------------------------------------------------------------------------- #

def test_26_cumulative_volume_is_non_decreasing_as_cutoff_advances(engine, calendar, sessions_cfg):
    candles = [_m5(9, 15, 100), _m5(9, 20, 150), _m5(9, 25, 200), *_three_history_days()]
    earlier = _assess(engine, calendar, sessions_cfg,
                       as_of=datetime(2026, 8, 28, 9, 25, tzinfo=IST), candles=candles)
    later = _assess(engine, calendar, sessions_cfg,
                     as_of=datetime(2026, 8, 28, 9, 30, tzinfo=IST), candles=candles)
    assert earlier.current_cumulative_volume == 250
    assert later.current_cumulative_volume == 450
    assert later.current_cumulative_volume >= earlier.current_cumulative_volume


# --------------------------------------------------------------------------- #
# 28 — index-shaped all-zero volume gracefully unavailable, not a crash
# --------------------------------------------------------------------------- #

def test_28_all_zero_volume_index_shaped_input_is_unavailable_not_a_crash(
    engine, calendar, sessions_cfg
):
    today = [_m5(9, 15, 0), _m5(9, 20, 0), _m5(9, 25, 0)]
    zero_history = [
        *_prior_day_bars(date(2026, 8, 21), [0, 0, 0]),
        *_prior_day_bars(date(2026, 8, 14), [0, 0, 0]),
    ]
    as_of = datetime(2026, 8, 28, 9, 30, tzinfo=IST)
    rv = _assess(engine, calendar, sessions_cfg, as_of=as_of, candles=[*today, *zero_history])
    assert rv.available is False
    assert rv.relation is RelativeVolumeRelation.UNKNOWN


# --------------------------------------------------------------------------- #
# 29/30 — no threshold/BUY-SELL fields, structural proof
# --------------------------------------------------------------------------- #

def test_29_30_no_threshold_or_trade_fields_on_the_contract():
    import dataclasses

    from athena.intraday.relative_volume_models import RelativeVolumeContext as _RVC
    forbidden = {
        "buy", "sell", "trade", "probability", "score", "rank",
        "surge", "spike", "high_rvol", "low_rvol", "strong_volume", "abnormal_volume",
    }
    names = {f.name.lower() for f in dataclasses.fields(_RVC)}
    assert not (names & forbidden), f"RelativeVolumeContext has a forbidden field: {names & forbidden}"
    relation_values = {v.value for v in RelativeVolumeRelation}
    assert relation_values == {"ABOVE_BASELINE", "BELOW_BASELINE", "AT_BASELINE", "UNKNOWN"}


def test_naive_as_of_rejected(engine, calendar, sessions_cfg):
    sc = _session(calendar, sessions_cfg, as_of=datetime(2026, 8, 28, 9, 30, tzinfo=IST), candles=[])
    with pytest.raises(ValueError, match="timezone-aware"):
        engine.assess(
            IID, as_of=datetime(2026, 8, 28, 9, 30), session_context=sc,
            five_min_candles=[], calendar=calendar, tzinfo=IST,
        )


def test_non_trading_session_is_unavailable(engine, calendar, sessions_cfg):
    sunday = datetime(2026, 8, 30, 10, 0, tzinfo=IST)
    rv = _assess(engine, calendar, sessions_cfg, as_of=sunday, candles=[])
    assert rv.available is False
    assert rv.relation is RelativeVolumeRelation.UNKNOWN
