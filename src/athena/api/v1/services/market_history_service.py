"""Read-only persisted market history for dashboard charting (M-D2, UX-3b)."""

from __future__ import annotations

from collections.abc import Callable
from datetime import datetime, timezone
from pathlib import Path
from typing import Literal

from athena.api.v1.dtos.market import CandleDTO, CandleSeriesDTO
from athena.api.v1.providers.base import CandleHistoryProvider
from athena.config.loader import load_config
from athena.domain.enums import Timeframe
from athena.indicators.calculations import align_trailing_series, atr_series, sma_series


class MarketHistoryService:
    """Map persisted candles to an explicit, freshness-aware API contract."""

    def __init__(
        self,
        provider: CandleHistoryProvider,
        *,
        freshness_threshold_minutes: int,
        now_fn: Callable[[], datetime] | None = None,
        config_dir: Path | None = None,
    ) -> None:
        if freshness_threshold_minutes < 1:
            raise ValueError("freshness_threshold_minutes must be >= 1")
        self._provider = provider
        self._freshness_threshold_minutes = freshness_threshold_minutes
        self._now = now_fn or (lambda: datetime.now(tz=timezone.utc))
        self._config_dir = Path(config_dir) if config_dir else Path("config")

    def recent_candles(
        self,
        instrument_id: str,
        timeframe: Timeframe,
        *,
        limit: int,
    ) -> CandleSeriesDTO:
        normalized_id = instrument_id.strip().upper()
        if not normalized_id:
            raise ValueError("instrument_id must be non-empty")
        candles = self._provider.list_recent_candles(
            normalized_id,
            timeframe,
            limit=limit,
        )
        latest_ts = candles[-1].ts_open if candles else None
        age_minutes: int | None = None
        freshness_status: Literal["FRESH", "STALE", "NO_DATA"] = "NO_DATA"
        if latest_ts is not None:
            now = self._now()
            if now.tzinfo is None:
                raise ValueError("market history clock must be timezone-aware")
            age_minutes = max(0, int((now - latest_ts).total_seconds() // 60))
            freshness_status = (
                "FRESH"
                if age_minutes <= self._freshness_threshold_minutes
                else "STALE"
            )

        # ATR/moving-average overlay (UX-3b): same periods already used
        # elsewhere (config/indicators.json), plotted per-bar on the chart's
        # own 5m series rather than the D1 value used for TradePlan sizing.
        # None during warmup — never an invented value for bars where the
        # indicator wasn't yet computable.
        params = load_config(self._config_dir).indicators.params
        atr_period = params.get("atr", {}).get("period", 14)
        sma_period = params.get("sma", {}).get("period", 20)
        closes = [c.close for c in candles]
        atr_values = align_trailing_series(atr_series(candles, atr_period), len(candles))
        sma_values = align_trailing_series(sma_series(closes, sma_period), len(candles))

        return CandleSeriesDTO(
            instrument_id=normalized_id,
            timeframe=timeframe.value,
            candles=tuple(
                CandleDTO(
                    ts_open=candle.ts_open,
                    open=candle.open,
                    high=candle.high,
                    low=candle.low,
                    close=candle.close,
                    volume=candle.volume,
                    source=candle.source,
                    adjusted=candle.adjusted,
                    atr=atr_val,
                    moving_average=sma_val,
                )
                for candle, atr_val, sma_val in zip(candles, atr_values, sma_values, strict=True)
            ),
            count=len(candles),
            latest_ts=latest_ts,
            freshness_status=freshness_status,
            age_minutes=age_minutes,
            freshness_threshold_minutes=self._freshness_threshold_minutes,
        )
