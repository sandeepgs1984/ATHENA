"""PS-P10B Daily Chart Portfolio Review evidence foundation tests."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from decimal import Decimal
from zoneinfo import ZoneInfo

import pytest

from athena.domain.enums import Timeframe
from athena.domain.market import Candle
from athena.indicators.calculations import rsi, volume_ma
from athena.portfolio.daily_chart_evidence import (
    RSI_REVIEW_PERIOD,
    SUPERTREND_ATR_PERIOD,
    VOLUME_MA_PERIOD,
    DailyChartEvidenceEngine,
    DailyChartEvidenceReason,
    SuperTrendDirection,
)

AS_OF = datetime(2026, 9, 4, 0, 0, tzinfo=timezone.utc)
TZ = ZoneInfo("UTC")


def _candle(
    index: int,
    close: Decimal | int | str,
    *,
    instrument_id: str = "NSE:CHENNPETRO",
    timeframe: Timeframe = Timeframe.D1,
    high: Decimal | int | str | None = None,
    low: Decimal | int | str | None = None,
    volume: int = 1000,
    adjusted: bool = True,
) -> Candle:
    close_value = Decimal(close)
    high_value = Decimal(high) if high is not None else close_value + Decimal("1")
    low_value = Decimal(low) if low is not None else close_value - Decimal("1")
    return Candle(
        instrument_id=instrument_id,
        timeframe=timeframe,
        ts_open=AS_OF - timedelta(days=49 - index),
        open=close_value,
        high=high_value,
        low=low_value,
        close=close_value,
        volume=volume,
        source="test",
        adjusted=adjusted,
    )


def _candles(
    closes: list[Decimal | int | str],
    *,
    instrument_id: str = "NSE:CHENNPETRO",
    timeframe: Timeframe = Timeframe.D1,
    volumes: list[int] | None = None,
    adjusted: bool = True,
) -> list[Candle]:
    start = 50 - len(closes)
    return [
        _candle(
            start + index,
            close,
            instrument_id=instrument_id,
            timeframe=timeframe,
            volume=volumes[index] if volumes is not None else 1000 + index,
            adjusted=adjusted,
        )
        for index, close in enumerate(closes)
    ]


def _with_future(candles: list[Candle], close: Decimal | int | str) -> list[Candle]:
    future = _candle(50, close)
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
            adjusted=future.adjusted,
        ),
    ]


def _engine() -> DailyChartEvidenceEngine:
    return DailyChartEvidenceEngine()


def test_supertrend_requires_period_plus_one_candles_and_reports_warmup() -> None:
    short = _candles([100] * SUPERTREND_ATR_PERIOD)
    ready = _candles([100] * (SUPERTREND_ATR_PERIOD + 1))

    short_result = _engine().supertrend_10_3(
        instrument_id="NSE:CHENNPETRO",
        candles=short,
        accepted_price_as_of=AS_OF,
        expected_analysis_as_of=AS_OF,
        market_timezone=TZ,
    )
    ready_result = _engine().supertrend_10_3(
        instrument_id="NSE:CHENNPETRO",
        candles=ready,
        accepted_price_as_of=AS_OF,
        expected_analysis_as_of=AS_OF,
        market_timezone=TZ,
    )

    assert short_result.reason is DailyChartEvidenceReason.INSUFFICIENT_HISTORY
    assert short_result.direction is None
    assert ready_result.reason is DailyChartEvidenceReason.OK
    assert ready_result.direction is SuperTrendDirection.BULLISH
    assert ready_result.atr_period == 10
    assert ready_result.multiplier == Decimal("3")


def test_supertrend_is_deterministic_and_ignores_future_d1_candles() -> None:
    candles = _candles([100] * 20 + [105, 106, 108, 110, 112])
    first = _engine().supertrend_10_3(
        instrument_id="NSE:CHENNPETRO",
        candles=candles,
        accepted_price_as_of=AS_OF,
        expected_analysis_as_of=AS_OF,
        market_timezone=TZ,
    )
    second = _engine().supertrend_10_3(
        instrument_id="NSE:CHENNPETRO",
        candles=_with_future(candles, 1),
        accepted_price_as_of=AS_OF,
        expected_analysis_as_of=AS_OF,
        market_timezone=TZ,
    )

    assert second.direction == first.direction
    assert second.supertrend == first.supertrend
    assert second.final_upper_band == first.final_upper_band
    assert second.final_lower_band == first.final_lower_band
    assert second.atr == first.atr
    assert first.provenance.source_count == len(candles)
    assert second.provenance.source_count == len(candles) + 1
    assert second.provenance.candles_used == len(candles)


def test_supertrend_reports_latest_flip_without_mapping_it_to_actions() -> None:
    candles = _candles([100] * 11 + [80])

    result = _engine().supertrend_10_3(
        instrument_id="NSE:CHENNPETRO",
        candles=candles,
        accepted_price_as_of=AS_OF,
        expected_analysis_as_of=AS_OF,
        market_timezone=TZ,
    )

    assert result.direction is SuperTrendDirection.BEARISH
    assert result.flipped_on_latest is True
    assert result.reason is DailyChartEvidenceReason.OK


def test_wrong_instrument_and_wrong_timeframe_are_incoherent() -> None:
    wrong_instrument = _candles([100] * 20, instrument_id="NSE:RAINBOW")
    wrong_timeframe = _candles([100] * 20, timeframe=Timeframe.M5)

    for candles in (wrong_instrument, wrong_timeframe):
        result = _engine().rsi14(
            instrument_id="NSE:CHENNPETRO",
            candles=candles,
            accepted_price_as_of=AS_OF,
            expected_analysis_as_of=AS_OF,
            market_timezone=TZ,
        )
        assert result.reason is DailyChartEvidenceReason.D1_EVIDENCE_INCOHERENT
        assert result.is_coherent is False


def test_latest_d1_session_must_match_accepted_and_expected_sessions() -> None:
    stale = [
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
            adjusted=c.adjusted,
        )
        for c in _candles([100] * 20)
    ]

    accepted = _engine().rsi14(
        instrument_id="NSE:CHENNPETRO",
        candles=stale,
        accepted_price_as_of=AS_OF,
        expected_analysis_as_of=AS_OF,
        market_timezone=TZ,
    )
    expected = _engine().rsi14(
        instrument_id="NSE:CHENNPETRO",
        candles=_candles([100] * 20),
        accepted_price_as_of=AS_OF,
        expected_analysis_as_of=AS_OF + timedelta(days=1),
        market_timezone=TZ,
    )

    assert accepted.reason is DailyChartEvidenceReason.ACCEPTED_SESSION_MISMATCH
    assert expected.reason is DailyChartEvidenceReason.EXPECTED_SESSION_MISMATCH


def test_rsi14_reuses_existing_rsi_calculation() -> None:
    candles = _candles([100, 102, 101, 104, 106, 105, 108, 109, 107, 110, 112, 111, 113, 115, 116])

    result = _engine().rsi14(
        instrument_id="NSE:CHENNPETRO",
        candles=candles,
        accepted_price_as_of=AS_OF,
        expected_analysis_as_of=AS_OF,
        market_timezone=TZ,
    )

    assert result.reason is DailyChartEvidenceReason.OK
    assert result.period == RSI_REVIEW_PERIOD
    assert result.value == rsi([candle.close for candle in candles], RSI_REVIEW_PERIOD)


def test_volume_evidence_exposes_measurements_without_expansion_classification() -> None:
    volumes = [0] * 19 + [4000]
    candles = _candles([100] * 20, volumes=volumes)

    result = _engine().volume_review(
        instrument_id="NSE:CHENNPETRO",
        candles=candles,
        accepted_price_as_of=AS_OF,
        expected_analysis_as_of=AS_OF,
        market_timezone=TZ,
    )

    assert result.reason is DailyChartEvidenceReason.OK
    assert result.latest_volume == 4000
    assert result.volume_ma == volume_ma(volumes, VOLUME_MA_PERIOD)
    assert not hasattr(result, "classification")


def test_ath_relationship_distinguishes_available_history_from_rolling_high() -> None:
    candles = _candles([100, 105, 103, 107, 110, 108, 112])

    result = _engine().ath_rolling_high(
        instrument_id="NSE:CHENNPETRO",
        candles=candles,
        accepted_price_as_of=AS_OF,
        expected_analysis_as_of=AS_OF,
        market_timezone=TZ,
        rolling_sessions=4,
    )

    assert result.reason is DailyChartEvidenceReason.OK
    assert result.prior_available_history_high == Decimal("111")
    assert result.latest_high == Decimal("113")
    assert result.latest_high_exceeds_prior_history is True
    assert result.latest_close_above_prior_history_high is True
    assert result.prior_rolling_high == Decimal("111")
    assert result.latest_high_exceeds_prior_rolling is True
    assert result.adjusted_history is True


def test_structural_level_candidates_are_typed_but_not_extracted_before_freeze() -> None:
    result = _engine().structural_level_candidates(
        instrument_id="NSE:CHENNPETRO",
        candles=_candles([100] * 20),
        accepted_price_as_of=AS_OF,
        expected_analysis_as_of=AS_OF,
        market_timezone=TZ,
    )

    assert result.candidates == ()
    assert (
        result.reason
        is DailyChartEvidenceReason.STRUCTURAL_LEVEL_METHODOLOGY_NOT_FROZEN
    )
    assert result.is_coherent is True


def test_rolling_window_requires_at_least_two_sessions_when_supplied() -> None:
    with pytest.raises(ValueError, match="rolling_sessions must be >= 2"):
        _engine().ath_rolling_high(
            instrument_id="NSE:CHENNPETRO",
            candles=_candles([100] * 20),
            accepted_price_as_of=AS_OF,
            expected_analysis_as_of=AS_OF,
            market_timezone=TZ,
            rolling_sessions=1,
        )
