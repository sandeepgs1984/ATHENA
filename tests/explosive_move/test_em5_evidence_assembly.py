"""EM-5 live evidence assembly -- proves the assembled row has exactly
the frozen 22-`CANDIDATE_FEATURE` shape `em4b_preprocessing.transform_row`
expects, that the live checkpoint-price substitution reproduces the
frozen `price_at_checkpoint` formulas exactly via the synthetic-candle
seam (never touching `checkpoint_dynamic_evidence.py` itself), and that
the historical REL_VOLUME_C baseline only counts sessions with real
comparable-time-of-day data.
"""

from __future__ import annotations

from datetime import date, datetime, time, timedelta
from decimal import Decimal
from zoneinfo import ZoneInfo

from athena.domain.enums import Timeframe
from athena.domain.market import Candle
from athena.explosive_move.evidence_values import DailyBar
from athena.explosive_move.live.evidence_assembly import (
    CATEGORICAL_FIELDS,
    CHECKPOINT_FIELD,
    CONTINUOUS_FIELDS,
    assemble_candidate_row,
    historical_cumulative_volumes_through_checkpoint,
)

IST = ZoneInfo("Asia/Kolkata")
IID = "NSE:AAA"
SESSION_DATE = date(2026, 8, 28)
CHECKPOINT = "12:00"
CHECKPOINT_INSTANT = datetime(2026, 8, 28, 12, 0, tzinfo=IST)


def _candle(ts_open: datetime, *, open_="100", high="101", low="99", close="100", volume=1000) -> Candle:
    return Candle(instrument_id=IID, timeframe=Timeframe.M5, ts_open=ts_open,
                  open=Decimal(open_), high=Decimal(high), low=Decimal(low), close=Decimal(close),
                  volume=volume, source="kite")


def _today_session(n_candles=33) -> tuple[Candle, ...]:
    start = datetime(2026, 8, 28, 9, 15, tzinfo=IST)
    return tuple(_candle(start + timedelta(minutes=5 * i)) for i in range(n_candles))


def _daily_bars(n: int, *, before: date = SESSION_DATE) -> tuple[DailyBar, ...]:
    out = []
    for i in range(n, 0, -1):
        d = before - timedelta(days=i)
        out.append(DailyBar(session_date=d, open=Decimal("95"), high=Decimal("105"),
                            low=Decimal("90"), close=Decimal("98"), volume=50000))
    return tuple(out)


def _base_kwargs(**overrides):
    defaults = {
        "instrument_id": IID, "session_date": SESSION_DATE, "checkpoint": CHECKPOINT,
        "checkpoint_instant": CHECKPOINT_INSTANT, "daily_bars": _daily_bars(60),
        "today_m5_candles": _today_session(), "checkpoint_reference_price": Decimal("103"),
        "historical_checkpoint_volumes": tuple(range(1000, 1020)), "regime_row": None,
    }
    defaults.update(overrides)
    return defaults


def test_row_has_exactly_the_22_candidate_fields_plus_keys():
    row = assemble_candidate_row(**_base_kwargs())
    expected_keys = {"session_date", CHECKPOINT_FIELD, *CONTINUOUS_FIELDS, *CATEGORICAL_FIELDS}
    assert set(row) == expected_keys
    assert len(CONTINUOUS_FIELDS) + len(CATEGORICAL_FIELDS) == 22


def test_session_date_and_checkpoint_are_persisted_correctly():
    row = assemble_candidate_row(**_base_kwargs())
    assert row["session_date"] == "2026-08-28"
    assert row[CHECKPOINT_FIELD] == "12:00"


def test_live_price_substitution_reproduces_return_from_open_c_formula():
    row = assemble_candidate_row(**_base_kwargs(checkpoint_reference_price=Decimal("103")))
    session_open = Decimal("100")  # first candle's open, per _today_session
    assert row["return_from_open_c"] == Decimal("103") / session_open - 1


def test_live_price_substitution_reproduces_return_from_prev_close_c_formula():
    row = assemble_candidate_row(**_base_kwargs(checkpoint_reference_price=Decimal("103")))
    prev_close = Decimal("98")  # _daily_bars' fixed close
    assert row["return_from_prev_close_c"] == Decimal("103") / prev_close - 1


def test_no_checkpoint_reference_price_leaves_price_dependent_fields_unknown():
    row = assemble_candidate_row(**_base_kwargs(checkpoint_reference_price=None))
    price_dependent = (
        "dist_from_20d_high_c", "dist_from_20d_low_c", "range_position_20d_c",
        "return_from_open_c", "return_from_prev_close_c", "dist_from_high_so_far_c", "vwap_rel_c",
    )
    for name in price_dependent:
        assert row[name] is None, name


def test_no_checkpoint_reference_price_still_computes_non_price_fields():
    row = assemble_candidate_row(**_base_kwargs(checkpoint_reference_price=None))
    assert row["range_so_far_c"] is not None
    assert row["rel_volume_c"] is not None


def test_synthetic_candle_never_leaks_into_closed_candle_aggregations():
    with_price = assemble_candidate_row(**_base_kwargs(checkpoint_reference_price=Decimal("999")))
    without_price = assemble_candidate_row(**_base_kwargs(checkpoint_reference_price=None))
    # range_so_far_c depends only on HIGH/LOW_SO_FAR_C (ts_open < C) -- must be
    # identical regardless of the live price substitution at exactly C.
    assert with_price["range_so_far_c"] == without_price["range_so_far_c"]


def test_regime_row_none_yields_unknown_regime_fields():
    row = assemble_candidate_row(**_base_kwargs(regime_row=None))
    assert row["regime_trend"] is None
    assert row["regime_volatility"] is None
    assert row["regime_gap"] is None


def test_regime_row_known_populates_regime_fields():
    regime = {
        "session_date": "2026-08-28", "trend": "TREND_UP", "volatility": "VOL_NORMAL", "gap": "GAP_UP",
    }
    row = assemble_candidate_row(**_base_kwargs(regime_row=regime))
    assert row["regime_trend"] is not None


def test_insufficient_daily_bar_history_yields_unknown_sma_fields():
    row = assemble_candidate_row(**_base_kwargs(daily_bars=_daily_bars(5)))
    assert row["sma20_rel"] is None
    assert row["sma50_rel"] is None


class TestHistoricalCumulativeVolumesThroughCheckpoint:
    def test_skips_sessions_with_no_comparable_time_of_day_data(self):
        cp_time = time(12, 0)
        d1 = date(2026, 8, 20)
        d2 = date(2026, 8, 21)
        prior = {
            d1: (_candle(datetime(2026, 8, 20, 9, 15, tzinfo=IST), volume=500),),
            d2: (),  # no candles at all -- must be skipped, not counted as 0
        }
        out = historical_cumulative_volumes_through_checkpoint(checkpoint_time=cp_time, prior_sessions_m5=prior)
        assert out == (500,)

    def test_returns_oldest_first_within_the_lookback_window(self):
        cp_time = time(10, 0)
        sessions = {}
        for i, d in enumerate([date(2026, 8, d) for d in (18, 19, 20)]):
            sessions[d] = (_candle(datetime(d.year, d.month, d.day, 9, 15, tzinfo=IST), volume=100 * (i + 1)),)
        out = historical_cumulative_volumes_through_checkpoint(
            checkpoint_time=cp_time, prior_sessions_m5=sessions, lookback_sessions=20
        )
        assert out == (100, 200, 300)

    def test_caps_at_lookback_sessions(self):
        cp_time = time(10, 0)
        sessions = {
            date(2026, 8, d): (_candle(datetime(2026, 8, d, 9, 15, tzinfo=IST), volume=1),)
            for d in range(1, 26)
        }
        out = historical_cumulative_volumes_through_checkpoint(
            checkpoint_time=cp_time, prior_sessions_m5=sessions, lookback_sessions=20
        )
        assert len(out) == 20
