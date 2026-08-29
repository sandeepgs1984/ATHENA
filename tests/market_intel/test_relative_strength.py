"""Relative Strength Engine (ID-4) — point-in-time stock-vs-sector/market
comparative-performance evidence. NOT RSI, no BUY/SELL/probability/ranked
score anywhere here; see `athena.intraday.relative_strength_engine`."""

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
from athena.intraday import RelativeStrengthEngine, RelativeStrengthRelation
from athena.session import SessionContextEngine

IST = ZoneInfo("Asia/Kolkata")
CONFIG_DIR = Path(__file__).resolve().parents[2] / "config"
STOCK_ID = "NSE:TEST"
MARKET_ID = "NSE:NIFTY 50"
SECTOR_ID = "NSE:NIFTY IT"
DAY = date(2026, 8, 28)  # a real ordinary NSE trading Friday


@pytest.fixture()
def calendar() -> CalendarEngine:
    cfg = load_config(CONFIG_DIR)
    return CalendarEngine.from_config_dir(CONFIG_DIR, cfg.market)


@pytest.fixture()
def sessions_cfg():
    return load_config(CONFIG_DIR).market.sessions


@pytest.fixture()
def engine() -> RelativeStrengthEngine:
    return RelativeStrengthEngine()


def _c(instrument_id: str, hh: int, mm: int, *, open_, close, day: date = DAY) -> Candle:
    o, c = Decimal(str(open_)), Decimal(str(close))
    return Candle(
        instrument_id=instrument_id, timeframe=Timeframe.M5,
        ts_open=datetime(day.year, day.month, day.day, hh, mm, tzinfo=IST),
        open=o, high=max(o, c) + 1, low=min(o, c) - 1, close=c, volume=1_000, source="test",
    )


def _session(calendar, sessions_cfg, *, as_of, day: date = DAY):
    return SessionContextEngine().assess(
        STOCK_ID, as_of=as_of, exchange="NSE", calendar=calendar, sessions=sessions_cfg,
        tzinfo=IST, five_min_candles=[], fifteen_min_candles=[], latest_quote_ts=None,
    )


def _assess(
    engine, calendar, sessions_cfg, *, as_of,
    stock, market, sector,
    sector_name="Information Technology", sector_id=SECTOR_ID,
):
    sc = _session(calendar, sessions_cfg, as_of=as_of)
    return engine.assess(
        STOCK_ID, as_of=as_of, session_context=sc,
        sector=sector_name, market_benchmark_id=MARKET_ID,
        sector_benchmark_id=sector_id,
        stock_five_min_candles=stock, market_five_min_candles=market,
        sector_five_min_candles=sector, calendar=calendar, tzinfo=IST,
    )


# --------------------------------------------------------------------------- #
# 1-9 — session returns, exact differentials, all three relation labels
# --------------------------------------------------------------------------- #

def _clean_two_bar_scenario():
    market = [_c(MARKET_ID, 9, 15, open_=1000, close=1000), _c(MARKET_ID, 9, 20, open_=1000, close=1010)]
    sector = [_c(SECTOR_ID, 9, 15, open_=500, close=500), _c(SECTOR_ID, 9, 20, open_=500, close=505)]
    stock = [_c(STOCK_ID, 9, 15, open_=100, close=100), _c(STOCK_ID, 9, 20, open_=100, close=103)]
    return stock, market, sector


def test_1_2_3_stock_sector_market_session_returns_correct(engine, calendar, sessions_cfg):
    stock, market, sector = _clean_two_bar_scenario()
    as_of = datetime(2026, 8, 28, 9, 30, tzinfo=IST)
    rs = _assess(engine, calendar, sessions_cfg, as_of=as_of, stock=stock, market=market, sector=sector)
    assert rs.stock_return_pct == Decimal("3")
    assert rs.sector_return_pct == Decimal("1")
    assert rs.market_return_pct == Decimal("1")


def test_4_5_6_exact_subtraction_differentials(engine, calendar, sessions_cfg):
    stock, market, sector = _clean_two_bar_scenario()
    as_of = datetime(2026, 8, 28, 9, 30, tzinfo=IST)
    rs = _assess(engine, calendar, sessions_cfg, as_of=as_of, stock=stock, market=market, sector=sector)
    assert rs.stock_vs_sector_pct == Decimal("2")
    assert rs.stock_vs_market_pct == Decimal("2")
    assert rs.sector_vs_market_pct == Decimal("0")


def test_7_outperforming_relation(engine, calendar, sessions_cfg):
    stock, market, sector = _clean_two_bar_scenario()
    as_of = datetime(2026, 8, 28, 9, 30, tzinfo=IST)
    rs = _assess(engine, calendar, sessions_cfg, as_of=as_of, stock=stock, market=market, sector=sector)
    assert rs.stock_vs_market_relation is RelativeStrengthRelation.OUTPERFORMING
    assert rs.stock_vs_sector_relation is RelativeStrengthRelation.OUTPERFORMING


def test_8_underperforming_relation(engine, calendar, sessions_cfg):
    market = [_c(MARKET_ID, 9, 15, open_=1000, close=1000), _c(MARKET_ID, 9, 20, open_=1000, close=1010)]
    sector = [_c(SECTOR_ID, 9, 15, open_=500, close=500), _c(SECTOR_ID, 9, 20, open_=500, close=502)]
    stock = [_c(STOCK_ID, 9, 15, open_=100, close=100), _c(STOCK_ID, 9, 20, open_=100, close=100.5)]
    as_of = datetime(2026, 8, 28, 9, 30, tzinfo=IST)
    rs = _assess(engine, calendar, sessions_cfg, as_of=as_of, stock=stock, market=market, sector=sector)
    assert rs.stock_vs_market_relation is RelativeStrengthRelation.UNDERPERFORMING


def test_9_matching_exact_equality(engine, calendar, sessions_cfg):
    stock, market, sector = _clean_two_bar_scenario()
    as_of = datetime(2026, 8, 28, 9, 30, tzinfo=IST)
    rs = _assess(engine, calendar, sessions_cfg, as_of=as_of, stock=stock, market=market, sector=sector)
    assert rs.sector_vs_market_relation is RelativeStrengthRelation.MATCHING


# --------------------------------------------------------------------------- #
# 10-12 — partial availability: UNKNOWN != MATCHING, unavailable dims don't
# block the other, still-available differential
# --------------------------------------------------------------------------- #

def test_10_unavailable_sector_mapping_is_unknown_not_matching(engine, calendar, sessions_cfg):
    stock, market, _ = _clean_two_bar_scenario()
    as_of = datetime(2026, 8, 28, 9, 30, tzinfo=IST)
    rs = _assess(
        engine, calendar, sessions_cfg, as_of=as_of, stock=stock, market=market, sector=[],
        sector_name=None, sector_id=None,
    )
    assert rs.sector_available is False
    assert rs.sector_return_pct is None
    assert rs.stock_vs_sector_relation is RelativeStrengthRelation.UNKNOWN
    assert rs.sector_vs_market_relation is RelativeStrengthRelation.UNKNOWN
    assert rs.sector_benchmark_id is None


def test_11_market_unavailable_is_unknown_not_matching(engine, calendar, sessions_cfg):
    stock, _, sector = _clean_two_bar_scenario()
    as_of = datetime(2026, 8, 28, 9, 30, tzinfo=IST)
    rs = _assess(engine, calendar, sessions_cfg, as_of=as_of, stock=stock, market=[], sector=sector)
    assert rs.market_available is False
    assert rs.stock_vs_market_relation is RelativeStrengthRelation.UNKNOWN
    assert rs.sector_vs_market_relation is RelativeStrengthRelation.UNKNOWN


def test_12_partial_availability_preserves_the_still_available_pair(engine, calendar, sessions_cfg):
    """Sector unavailable must not prevent stock_vs_market from being
    computed from the two constituents that ARE both available."""
    stock, market, _ = _clean_two_bar_scenario()
    as_of = datetime(2026, 8, 28, 9, 30, tzinfo=IST)
    rs = _assess(
        engine, calendar, sessions_cfg, as_of=as_of, stock=stock, market=market, sector=[],
        sector_name=None, sector_id=None,
    )
    assert rs.market_available is True
    assert rs.stock_vs_market_pct == Decimal("2")
    assert rs.stock_vs_market_relation is RelativeStrengthRelation.OUTPERFORMING


# --------------------------------------------------------------------------- #
# 13-15 — common comparison window / common-cutoff semantics
# --------------------------------------------------------------------------- #

def test_13_comparison_start_is_the_single_shared_session_open(engine, calendar, sessions_cfg):
    stock, market, sector = _clean_two_bar_scenario()
    as_of = datetime(2026, 8, 28, 9, 30, tzinfo=IST)
    rs = _assess(engine, calendar, sessions_cfg, as_of=as_of, stock=stock, market=market, sector=sector)
    assert rs.comparison_start_ts == datetime(2026, 8, 28, 9, 15, tzinfo=IST)


def test_14_15_common_cutoff_is_the_slowest_constituents_latest_bar(engine, calendar, sessions_cfg):
    """Market only has bars through 09:20; sector through 09:25; stock
    through 09:30. The comparison cutoff must be 09:20 (market's own
    latest) -- and the faster stock/sector must use THEIR OWN 09:20 close,
    never their own later (09:25/09:30) bar, even though those exist."""
    market = [_c(MARKET_ID, 9, 15, open_=1000, close=1000), _c(MARKET_ID, 9, 20, open_=1000, close=1010)]
    sector = [_c(SECTOR_ID, 9, 15, open_=500, close=500), _c(SECTOR_ID, 9, 20, open_=500, close=505),
              _c(SECTOR_ID, 9, 25, open_=505, close=510)]
    stock = [_c(STOCK_ID, 9, 15, open_=100, close=100), _c(STOCK_ID, 9, 20, open_=100, close=110),
              _c(STOCK_ID, 9, 25, open_=110, close=120), _c(STOCK_ID, 9, 30, open_=120, close=130)]
    as_of = datetime(2026, 8, 28, 9, 40, tzinfo=IST)
    rs = _assess(engine, calendar, sessions_cfg, as_of=as_of, stock=stock, market=market, sector=sector)
    assert rs.comparison_cutoff_ts == datetime(2026, 8, 28, 9, 20, tzinfo=IST)
    assert rs.stock_return_pct == Decimal("10")  # (110-100)/100*100, NOT (130-100)/100*100=30
    assert rs.sector_return_pct == Decimal("1")  # (505-500)/500*100, NOT the 09:25 bar


# --------------------------------------------------------------------------- #
# 16 — non-vacuous: a still-forming candle cannot alter the return
# --------------------------------------------------------------------------- #

def test_16_forming_candle_cannot_alter_stock_return(engine, calendar, sessions_cfg):
    market = [_c(MARKET_ID, 9, 15, open_=1000, close=1000), _c(MARKET_ID, 9, 20, open_=1000, close=1010)]
    sector = [_c(SECTOR_ID, 9, 15, open_=500, close=500), _c(SECTOR_ID, 9, 20, open_=500, close=505)]
    baseline = [_c(STOCK_ID, 9, 15, open_=100, close=100), _c(STOCK_ID, 9, 20, open_=100, close=103)]
    extreme = _c(STOCK_ID, 9, 25, open_=103, close=999)
    just_before = datetime(2026, 8, 28, 9, 29, 59, tzinfo=IST)
    at_boundary = datetime(2026, 8, 28, 9, 30, 0, tzinfo=IST)

    with_extreme = [*baseline, extreme]
    before = _assess(engine, calendar, sessions_cfg, as_of=just_before, stock=with_extreme,
                      market=market, sector=sector)
    at = _assess(engine, calendar, sessions_cfg, as_of=at_boundary, stock=with_extreme,
                 market=market, sector=sector)
    # 09:25+5m=09:30 -- not yet eligible at 09:29:59, eligible at 09:30:00.
    # Cutoff is still bounded by market/sector's own latest (09:20) in both
    # cases, so the extreme 09:25 bar has zero effect on stock_return either way.
    assert before.stock_return_pct == Decimal("3")
    assert at.stock_return_pct == Decimal("3")


# --------------------------------------------------------------------------- #
# 17 — non-vacuous: off-grid candle cannot become a mismatched endpoint
# --------------------------------------------------------------------------- #

def test_17_off_grid_stock_candle_cannot_become_the_comparison_endpoint(engine, calendar, sessions_cfg):
    """Stock has only its canonical 09:15 bar plus an off-grid 09:23 bar
    with an extreme close -- 09:20/09:25/09:30 are genuinely missing for
    the stock, so it is NOT comparable (opening-only). Market/sector have
    full clean coverage through 09:30/09:25 and ARE comparable. The
    off-grid 09:23 bar must never become the stock's "latest canonical"
    endpoint (which would wrongly extend the cutoff and use its extreme
    price) -- but per ID-4.1, the stock's own non-comparability must NOT
    drag market/sector down with it either: their own genuinely valid
    comparison must survive, with only the stock honestly unavailable."""
    market = [_c(MARKET_ID, 9, 15, open_=1000, close=1000), _c(MARKET_ID, 9, 20, open_=1000, close=1010),
              _c(MARKET_ID, 9, 25, open_=1010, close=1015), _c(MARKET_ID, 9, 30, open_=1015, close=1020)]
    sector = [_c(SECTOR_ID, 9, 15, open_=500, close=500), _c(SECTOR_ID, 9, 20, open_=500, close=505),
              _c(SECTOR_ID, 9, 25, open_=505, close=510)]
    stock_gapped = [
        _c(STOCK_ID, 9, 15, open_=100, close=100),
        _c(STOCK_ID, 9, 23, open_=100, close=999),  # off-grid, extreme
    ]
    as_of = datetime(2026, 8, 28, 9, 40, tzinfo=IST)
    gapped = _assess(engine, calendar, sessions_cfg, as_of=as_of, stock=stock_gapped,
                      market=market, sector=sector)
    # Cutoff = min(sector's own latest 09:25, market's own latest 09:30) --
    # the off-grid 09:23 never enters, and the stock's non-comparability
    # doesn't cap the window for the two genuinely comparable constituents.
    assert gapped.comparison_cutoff_ts == datetime(2026, 8, 28, 9, 25, tzinfo=IST)
    assert gapped.stock_return_pct is None
    assert gapped.stock_available is False
    assert gapped.sector_return_pct == Decimal("2")  # (510-500)/500*100 through 09:25
    assert gapped.market_return_pct == Decimal("1.5")  # (1015-1000)/1000*100 through 09:25
    assert gapped.sector_vs_market_relation is RelativeStrengthRelation.OUTPERFORMING
    assert gapped.stock_vs_sector_relation is RelativeStrengthRelation.UNKNOWN
    assert gapped.stock_vs_market_relation is RelativeStrengthRelation.UNKNOWN

    # Same market/sector data, but the stock's gap is filled with genuine
    # canonical bars instead -- the stock also resolves normally.
    stock_clean = [
        _c(STOCK_ID, 9, 15, open_=100, close=100), _c(STOCK_ID, 9, 20, open_=100, close=101),
        _c(STOCK_ID, 9, 25, open_=101, close=102), _c(STOCK_ID, 9, 30, open_=102, close=103),
    ]
    clean = _assess(engine, calendar, sessions_cfg, as_of=as_of, stock=stock_clean,
                     market=market, sector=sector)
    assert clean.comparison_cutoff_ts == datetime(2026, 8, 28, 9, 25, tzinfo=IST)
    assert clean.stock_return_pct is not None


# --------------------------------------------------------------------------- #
# ID-4.1 — comparable-constituent cutoff / partial-availability correctness.
# An opening-only constituent (real production shape: an index whose
# canonical M5 coverage is just its own first bar) must never cap the
# common cutoff for OTHER, genuinely comparable constituents. This test
# block fails against the pre-ID-4.1 implementation (verified by reverting
# the fix and confirming the failures, then restoring it).
# --------------------------------------------------------------------------- #

def test_id41_1_opening_only_market_does_not_cap_stock_and_sector_cutoff(engine, calendar, sessions_cfg):
    """ID-4.1 §10's exact real-production case: market has only its
    session-opening canonical bar; stock and sector both have genuine
    later bars. Market must be unavailable WITHOUT erasing stock/sector's
    own valid comparison."""
    market = [_c(MARKET_ID, 9, 15, open_=1000, close=1000)]  # opening-only
    sector = [_c(SECTOR_ID, 9, 15, open_=500, close=500), _c(SECTOR_ID, 9, 20, open_=500, close=505)]
    stock = [_c(STOCK_ID, 9, 15, open_=100, close=100), _c(STOCK_ID, 9, 20, open_=100, close=103),
             _c(STOCK_ID, 9, 25, open_=103, close=106)]
    as_of = datetime(2026, 8, 28, 9, 40, tzinfo=IST)
    rs = _assess(engine, calendar, sessions_cfg, as_of=as_of, stock=stock, market=market, sector=sector)
    assert rs.market_available is False
    assert rs.market_return_pct is None
    assert rs.stock_available is True
    assert rs.sector_available is True
    assert rs.comparison_cutoff_ts == datetime(2026, 8, 28, 9, 20, tzinfo=IST)  # sector's own latest
    assert rs.stock_return_pct == Decimal("3")  # through stock's own 09:20 bar
    assert rs.sector_return_pct == Decimal("1")
    assert rs.stock_vs_sector_relation is RelativeStrengthRelation.OUTPERFORMING
    assert rs.stock_vs_market_relation is RelativeStrengthRelation.UNKNOWN
    assert rs.sector_vs_market_relation is RelativeStrengthRelation.UNKNOWN


def test_id41_2_opening_only_sector_does_not_cap_stock_and_market_cutoff(engine, calendar, sessions_cfg):
    sector = [_c(SECTOR_ID, 9, 15, open_=500, close=500)]  # opening-only
    market = [_c(MARKET_ID, 9, 15, open_=1000, close=1000), _c(MARKET_ID, 9, 20, open_=1000, close=1010)]
    stock = [_c(STOCK_ID, 9, 15, open_=100, close=100), _c(STOCK_ID, 9, 20, open_=100, close=103),
             _c(STOCK_ID, 9, 25, open_=103, close=106)]
    as_of = datetime(2026, 8, 28, 9, 40, tzinfo=IST)
    rs = _assess(engine, calendar, sessions_cfg, as_of=as_of, stock=stock, market=market, sector=sector)
    assert rs.sector_available is False
    assert rs.sector_return_pct is None
    assert rs.stock_available is True
    assert rs.market_available is True
    assert rs.comparison_cutoff_ts == datetime(2026, 8, 28, 9, 20, tzinfo=IST)  # market's own latest
    assert rs.stock_return_pct == Decimal("3")
    assert rs.market_return_pct == Decimal("1")
    assert rs.stock_vs_market_relation is RelativeStrengthRelation.OUTPERFORMING
    assert rs.stock_vs_sector_relation is RelativeStrengthRelation.UNKNOWN
    assert rs.sector_vs_market_relation is RelativeStrengthRelation.UNKNOWN


def test_id41_3_opening_only_market_and_sector_do_not_erase_valid_stock_return(engine, calendar, sessions_cfg):
    """ID-4.1 §11's exact case: only stock is comparable. Its own return
    must survive even though NO pairwise comparison is possible."""
    market = [_c(MARKET_ID, 9, 15, open_=1000, close=1000)]
    sector = [_c(SECTOR_ID, 9, 15, open_=500, close=500)]
    stock = [_c(STOCK_ID, 9, 15, open_=100, close=100), _c(STOCK_ID, 9, 20, open_=100, close=103),
             _c(STOCK_ID, 9, 25, open_=103, close=106)]
    as_of = datetime(2026, 8, 28, 9, 40, tzinfo=IST)
    rs = _assess(engine, calendar, sessions_cfg, as_of=as_of, stock=stock, market=market, sector=sector)
    assert rs.stock_available is True
    assert rs.stock_return_pct == Decimal("6")  # (106-100)/100*100 through stock's own latest, 09:25
    assert rs.comparison_cutoff_ts == datetime(2026, 8, 28, 9, 25, tzinfo=IST)
    assert rs.market_available is False
    assert rs.sector_available is False
    assert rs.stock_vs_sector_relation is RelativeStrengthRelation.UNKNOWN
    assert rs.stock_vs_market_relation is RelativeStrengthRelation.UNKNOWN
    assert rs.sector_vs_market_relation is RelativeStrengthRelation.UNKNOWN


def test_id41_4_market_no_candles_matches_market_opening_only_availability(engine, calendar, sessions_cfg):
    """Data presence is not return availability (§5): a market with ZERO
    rows and a market with ONLY its opening row must produce the SAME
    availability outcome for the rest of the context."""
    sector = [_c(SECTOR_ID, 9, 15, open_=500, close=500), _c(SECTOR_ID, 9, 20, open_=500, close=505)]
    stock = [_c(STOCK_ID, 9, 15, open_=100, close=100), _c(STOCK_ID, 9, 20, open_=100, close=103)]
    as_of = datetime(2026, 8, 28, 9, 30, tzinfo=IST)
    no_candles = _assess(engine, calendar, sessions_cfg, as_of=as_of, stock=stock,
                          market=[], sector=sector)
    opening_only = _assess(engine, calendar, sessions_cfg, as_of=as_of, stock=stock,
                            market=[_c(MARKET_ID, 9, 15, open_=1000, close=1000)], sector=sector)
    assert no_candles.market_available == opening_only.market_available is False
    assert no_candles.stock_return_pct == opening_only.stock_return_pct == Decimal("3")
    assert no_candles.comparison_cutoff_ts == opening_only.comparison_cutoff_ts


def test_id41_5_sector_no_candles_matches_sector_opening_only_availability(engine, calendar, sessions_cfg):
    market = [_c(MARKET_ID, 9, 15, open_=1000, close=1000), _c(MARKET_ID, 9, 20, open_=1000, close=1010)]
    stock = [_c(STOCK_ID, 9, 15, open_=100, close=100), _c(STOCK_ID, 9, 20, open_=100, close=103)]
    as_of = datetime(2026, 8, 28, 9, 30, tzinfo=IST)
    no_candles = _assess(engine, calendar, sessions_cfg, as_of=as_of, stock=stock,
                          market=market, sector=[])
    opening_only = _assess(engine, calendar, sessions_cfg, as_of=as_of, stock=stock,
                            market=market, sector=[_c(SECTOR_ID, 9, 15, open_=500, close=500)])
    assert no_candles.sector_available == opening_only.sector_available is False
    assert no_candles.stock_return_pct == opening_only.stock_return_pct == Decimal("3")
    assert no_candles.comparison_cutoff_ts == opening_only.comparison_cutoff_ts


def test_id41_6_missing_stock_opening_preserves_valid_sector_vs_market(engine, calendar, sessions_cfg):
    """ID-4.1 §12: stock has later canonical bars but no exact
    session-open candle -- its own return is unavailable, but sector-vs-
    market must not be affected."""
    stock = [_c(STOCK_ID, 9, 20, open_=100, close=103), _c(STOCK_ID, 9, 25, open_=103, close=106)]
    market = [_c(MARKET_ID, 9, 15, open_=1000, close=1000), _c(MARKET_ID, 9, 20, open_=1000, close=1010)]
    sector = [_c(SECTOR_ID, 9, 15, open_=500, close=500), _c(SECTOR_ID, 9, 20, open_=500, close=505)]
    as_of = datetime(2026, 8, 28, 9, 30, tzinfo=IST)
    rs = _assess(engine, calendar, sessions_cfg, as_of=as_of, stock=stock, market=market, sector=sector)
    assert rs.stock_available is False
    assert rs.stock_return_pct is None
    assert rs.sector_available is True
    assert rs.market_available is True
    assert rs.sector_vs_market_relation is RelativeStrengthRelation.MATCHING
    assert rs.stock_vs_sector_relation is RelativeStrengthRelation.UNKNOWN
    assert rs.stock_vs_market_relation is RelativeStrengthRelation.UNKNOWN


def test_id41_7_forming_later_bar_does_not_make_a_constituent_comparable(engine, calendar, sessions_cfg):
    """A later candle that EXISTS in the raw input but hasn't completed
    yet at as_of must not count toward comparability -- distinct from the
    off-grid case (test 17), this is a genuinely canonical timestamp that
    just isn't done forming. Market/sector are independently comparable via
    their own completed 09:15/09:20 bars (as_of=9:27 >= 09:20+5m=09:25);
    stock's 09:25 bar exists in the raw input but hasn't completed yet
    (09:25+5m=09:30 > 9:27), so stock is still opening-only."""
    market = [_c(MARKET_ID, 9, 15, open_=1000, close=1000), _c(MARKET_ID, 9, 20, open_=1000, close=1010)]
    sector = [_c(SECTOR_ID, 9, 15, open_=500, close=500), _c(SECTOR_ID, 9, 20, open_=500, close=505)]
    stock_with_forming_bar = [
        _c(STOCK_ID, 9, 15, open_=100, close=100), _c(STOCK_ID, 9, 25, open_=100, close=999),
    ]
    still_forming = datetime(2026, 8, 28, 9, 27, tzinfo=IST)
    rs = _assess(engine, calendar, sessions_cfg, as_of=still_forming,
                 stock=stock_with_forming_bar, market=market, sector=sector)
    assert rs.stock_available is False
    assert rs.comparison_cutoff_ts == datetime(2026, 8, 28, 9, 20, tzinfo=IST)  # from sector/market only


def test_id41_8_exact_completion_boundary_makes_a_constituent_comparable(engine, calendar, sessions_cfg):
    market = [_c(MARKET_ID, 9, 15, open_=1000, close=1000), _c(MARKET_ID, 9, 20, open_=1000, close=1010)]
    sector = [_c(SECTOR_ID, 9, 15, open_=500, close=500), _c(SECTOR_ID, 9, 20, open_=500, close=505)]
    stock = [_c(STOCK_ID, 9, 15, open_=100, close=100), _c(STOCK_ID, 9, 20, open_=100, close=103)]
    one_second_before = datetime(2026, 8, 28, 9, 24, 59, tzinfo=IST)
    at_boundary = datetime(2026, 8, 28, 9, 25, 0, tzinfo=IST)  # 09:20+5m=09:25 -- exact completion
    before = _assess(engine, calendar, sessions_cfg, as_of=one_second_before, stock=stock,
                      market=market, sector=sector)
    at = _assess(engine, calendar, sessions_cfg, as_of=at_boundary, stock=stock,
                 market=market, sector=sector)
    assert before.stock_available is False  # 09:20 not yet completed at 09:24:59
    assert at.stock_available is True
    assert at.stock_return_pct == Decimal("3")


# --------------------------------------------------------------------------- #
# 18 — explicit as_of determinism
# --------------------------------------------------------------------------- #

def test_18_deterministic_replay(engine, calendar, sessions_cfg):
    stock, market, sector = _clean_two_bar_scenario()
    as_of = datetime(2026, 8, 28, 9, 30, tzinfo=IST)
    a = _assess(engine, calendar, sessions_cfg, as_of=as_of, stock=stock, market=market, sector=sector)
    b = _assess(RelativeStrengthEngine(), calendar, sessions_cfg, as_of=as_of,
                stock=stock, market=market, sector=sector)
    assert a == b


# --------------------------------------------------------------------------- #
# 19/20 — session-relative open, no hardcoded 09:15; real special session
# --------------------------------------------------------------------------- #

def test_19_20_special_session_open_used_not_hardcoded_0915(engine, calendar, sessions_cfg):
    """2026-02-01: a real NSE/CMTR-notified full-hours session on a Sunday
    (Union Budget) -- happens to share the ordinary 09:15 open, so this
    proves the engine reads `SessionContext.session_open_ts` (itself
    calendar-derived) rather than a module-level literal, by using a real
    session on a day that is not, by default, a trading day at all (Sunday)."""
    day = date(2026, 2, 1)
    market = [_c(MARKET_ID, 9, 15, open_=1000, close=1000, day=day),
              _c(MARKET_ID, 9, 20, open_=1000, close=1010, day=day)]
    sector = [_c(SECTOR_ID, 9, 15, open_=500, close=500, day=day),
              _c(SECTOR_ID, 9, 20, open_=500, close=505, day=day)]
    stock = [_c(STOCK_ID, 9, 15, open_=100, close=100, day=day),
             _c(STOCK_ID, 9, 20, open_=100, close=103, day=day)]
    as_of = datetime(2026, 2, 1, 9, 30, tzinfo=IST)
    rs = _assess(engine, calendar, sessions_cfg, as_of=as_of, stock=stock, market=market, sector=sector)
    assert rs.comparison_start_ts == datetime(2026, 2, 1, 9, 15, tzinfo=IST)
    assert rs.stock_return_pct == Decimal("3")


# --------------------------------------------------------------------------- #
# Non-trading session / unconfirmed-open robustness
# --------------------------------------------------------------------------- #

def test_non_trading_session_is_fully_unavailable(engine, calendar, sessions_cfg):
    sunday = datetime(2026, 8, 30, 10, 0, tzinfo=IST)
    rs = _assess(engine, calendar, sessions_cfg, as_of=sunday, stock=[], market=[], sector=[])
    assert rs.stock_available is False
    assert rs.market_available is False
    assert rs.sector_available is False
    assert rs.comparison_start_ts is None
    assert rs.comparison_cutoff_ts is None
    assert rs.stock_vs_market_relation is RelativeStrengthRelation.UNKNOWN


def test_naive_as_of_rejected(engine, calendar, sessions_cfg):
    sc = _session(calendar, sessions_cfg, as_of=datetime(2026, 8, 28, 9, 30, tzinfo=IST))
    with pytest.raises(ValueError, match="timezone-aware"):
        engine.assess(
            STOCK_ID, as_of=datetime(2026, 8, 28, 9, 30), session_context=sc,
            sector="Information Technology", market_benchmark_id=MARKET_ID,
            sector_benchmark_id=SECTOR_ID,
            stock_five_min_candles=[], market_five_min_candles=[], sector_five_min_candles=[],
            calendar=calendar, tzinfo=IST,
        )


def test_missing_market_benchmark_id_rejected(engine, calendar, sessions_cfg):
    sc = _session(calendar, sessions_cfg, as_of=datetime(2026, 8, 28, 9, 30, tzinfo=IST))
    with pytest.raises(ValueError, match="market_benchmark_id"):
        engine.assess(
            STOCK_ID, as_of=datetime(2026, 8, 28, 9, 30, tzinfo=IST), session_context=sc,
            sector=None, market_benchmark_id="", sector_benchmark_id=None,
            stock_five_min_candles=[], market_five_min_candles=[], sector_five_min_candles=[],
            calendar=calendar, tzinfo=IST,
        )
