"""PS-P8C Portfolio D1 Trend adapter tests."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from decimal import Decimal
from zoneinfo import ZoneInfo

from athena.data.store.repository import SqliteRepository
from athena.domain.enums import Timeframe
from athena.domain.market import Candle, Instrument
from athena.portfolio.trend_adapter import (
    PortfolioTrend,
    PortfolioTrendAdapter,
    PortfolioTrendReason,
)

AS_OF = datetime(2026, 9, 2, 0, 0, tzinfo=timezone.utc)
TZ = ZoneInfo("UTC")


def _candle(
    close: Decimal | int | str,
    index: int,
    *,
    instrument_id: str = "NSE:INFY",
    timeframe: Timeframe = Timeframe.D1,
) -> Candle:
    price = Decimal(close)
    return Candle(
        instrument_id=instrument_id,
        timeframe=timeframe,
        ts_open=AS_OF - timedelta(days=49 - index),
        open=price,
        high=price,
        low=price,
        close=price,
        volume=1000,
        source="test",
    )


def _candles(
    first_30: Decimal | int | str,
    next_19: Decimal | int | str,
    last: Decimal | int | str,
    *,
    instrument_id: str = "NSE:INFY",
    timeframe: Timeframe = Timeframe.D1,
) -> list[Candle]:
    closes = [first_30] * 30 + [next_19] * 19 + [last]
    return [
        _candle(close, index, instrument_id=instrument_id, timeframe=timeframe)
        for index, close in enumerate(closes)
    ]


def _with_future(candles: list[Candle], close: Decimal | int | str = 1) -> list[Candle]:
    future = _candle(close, 50)
    return [
        *candles,
        Candle(
            instrument_id=future.instrument_id,
            timeframe=future.timeframe,
            ts_open=AS_OF + timedelta(days=1),
            open=future.open,
            high=future.high,
            low=future.low,
            close=future.close,
            volume=future.volume,
            source=future.source,
        ),
    ]


def _adapter(tmp_path) -> PortfolioTrendAdapter:
    repo = SqliteRepository(tmp_path / "athena.db")
    repo.initialize()
    return PortfolioTrendAdapter(repo)


def _classify(tmp_path, candles: list[Candle]):
    return _adapter(tmp_path).classify_candles(
        instrument_id="NSE:INFY",
        candles=candles,
        accepted_price_as_of=AS_OF,
        expected_analysis_as_of=AS_OF,
        market_timezone=TZ,
    )


def test_uptrend_boundaries_include_close_equal_to_sma50(tmp_path) -> None:
    direct = _classify(tmp_path, _candles(90, 110, 110))
    boundary = _classify(tmp_path, _candles(49, 98, 68))

    assert direct.trend is PortfolioTrend.UPTREND
    assert boundary.trend is PortfolioTrend.UPTREND
    assert direct.reason is PortfolioTrendReason.UP_FROM_D1_SMA_STRUCTURE
    assert boundary.close == boundary.slow_sma


def test_downtrend_boundaries_include_close_equal_to_sma50(tmp_path) -> None:
    direct = _classify(tmp_path, _candles(110, 90, 90))
    boundary = _classify(tmp_path, _candles(147, 49, 109))

    assert direct.trend is PortfolioTrend.DOWNTREND
    assert boundary.trend is PortfolioTrend.DOWNTREND
    assert direct.reason is PortfolioTrendReason.DOWN_FROM_D1_SMA_STRUCTURE
    assert boundary.close == boundary.slow_sma


def test_mixed_covers_disagreeing_price_and_sma_structure_and_equal_smas(tmp_path) -> None:
    mixed_a = _classify(tmp_path, _candles(90, 110, 80))
    mixed_b = _classify(tmp_path, _candles(110, 90, 120))
    equal_smas = _classify(tmp_path, _candles(100, 100, 100))

    assert mixed_a.trend is PortfolioTrend.MIXED
    assert mixed_b.trend is PortfolioTrend.MIXED
    assert equal_smas.trend is PortfolioTrend.MIXED
    assert mixed_a.reason is PortfolioTrendReason.MIXED_FROM_D1_SMA_STRUCTURE


def test_49_candles_are_unavailable_and_50_candles_are_classifiable(tmp_path) -> None:
    unavailable = _classify(tmp_path, _candles(90, 110, 110)[:49])
    available = _classify(tmp_path, _candles(90, 110, 110))

    assert unavailable.trend is None
    assert unavailable.reason is PortfolioTrendReason.D1_EVIDENCE_UNAVAILABLE
    assert available.trend is PortfolioTrend.UPTREND


def test_classify_excludes_future_candle_before_sufficiency_check(tmp_path) -> None:
    result = _classify(tmp_path, _with_future(_candles(90, 110, 110)[:49]))

    assert result.trend is None
    assert result.reason is PortfolioTrendReason.D1_EVIDENCE_UNAVAILABLE
    assert result.candles_used == 49
    assert result.d1_session == AS_OF - timedelta(days=1)


def test_classify_ignores_future_candle_when_50_current_candles_exist(tmp_path) -> None:
    original = _classify(tmp_path, _candles(90, 110, 110))
    with_future = _classify(tmp_path, _with_future(_candles(90, 110, 110), close=1))

    assert with_future == original
    assert with_future.trend is PortfolioTrend.UPTREND
    assert with_future.candles_used == 50
    assert with_future.d1_session == AS_OF


def test_resolve_ignores_future_candles_beyond_expected_session(tmp_path) -> None:
    repo = SqliteRepository(tmp_path / "athena.db")
    repo.initialize()
    repo.upsert_instrument(
        Instrument(
            instrument_id="NSE:INFY",
            symbol="INFY",
            exchange="NSE",
            series="EQ",
        )
    )
    repo.add_candles(_candles(90, 110, 110))
    future = _candle(1, 50)
    repo.add_candles([
        Candle(
            instrument_id=future.instrument_id,
            timeframe=future.timeframe,
            ts_open=AS_OF + timedelta(days=1),
            open=future.open,
            high=future.high,
            low=future.low,
            close=future.close,
            volume=future.volume,
            source=future.source,
        )
    ])

    result = PortfolioTrendAdapter(repo).resolve(
        instrument_id="NSE:INFY",
        accepted_price_as_of=AS_OF,
        expected_analysis_as_of=AS_OF,
        market_timezone=TZ,
    )

    assert result.trend is PortfolioTrend.UPTREND
    assert result.d1_session == AS_OF


def test_latest_included_candle_must_match_accepted_and_expected_session(tmp_path) -> None:
    previous = AS_OF - timedelta(days=1)
    shifted = [
        Candle(
            instrument_id=c.instrument_id,
            timeframe=c.timeframe,
            ts_open=c.ts_open - timedelta(days=1),
            open=c.open,
            high=c.high,
            low=c.low,
            close=c.close,
            volume=c.volume,
            source=c.source,
        )
        for c in _candles(90, 110, 110)
    ]

    result = _adapter(tmp_path).classify_candles(
        instrument_id="NSE:INFY",
        candles=shifted,
        accepted_price_as_of=AS_OF,
        expected_analysis_as_of=AS_OF,
        market_timezone=TZ,
    )

    assert shifted[-1].ts_open == previous
    assert result.trend is None
    assert result.reason is PortfolioTrendReason.D1_EVIDENCE_INCOHERENT


def test_latest_included_candle_must_match_expected_session(tmp_path) -> None:
    result = _adapter(tmp_path).classify_candles(
        instrument_id="NSE:INFY",
        candles=_candles(90, 110, 110),
        accepted_price_as_of=AS_OF,
        expected_analysis_as_of=AS_OF + timedelta(days=1),
        market_timezone=TZ,
    )

    assert result.trend is None
    assert result.reason is PortfolioTrendReason.D1_EVIDENCE_INCOHERENT


def test_wrong_instrument_or_timeframe_is_incoherent(tmp_path) -> None:
    wrong_instrument = _classify(tmp_path, _candles(90, 110, 110, instrument_id="NSE:TCS"))
    wrong_timeframe = _classify(tmp_path, _candles(90, 110, 110, timeframe=Timeframe.M5))

    assert wrong_instrument.trend is None
    assert wrong_instrument.reason is PortfolioTrendReason.D1_EVIDENCE_INCOHERENT
    assert wrong_timeframe.trend is None
    assert wrong_timeframe.reason is PortfolioTrendReason.D1_EVIDENCE_INCOHERENT


def test_deterministic_for_identical_d1_inputs(tmp_path) -> None:
    candles = _candles(90, 110, 110)
    first = _classify(tmp_path, candles)
    second = _classify(tmp_path, candles)

    assert first == second
