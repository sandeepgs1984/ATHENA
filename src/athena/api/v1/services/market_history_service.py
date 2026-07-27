"""Read-only persisted market history for dashboard charting (M-D2, UX-3b)."""

from __future__ import annotations

from collections.abc import Callable
from datetime import datetime, timezone
from decimal import Decimal
from pathlib import Path
from typing import Literal

from athena.api.v1.dtos.market import (
    CandleDTO,
    CandleSeriesDTO,
    MarketIndexTickerDTO,
    MarketTickerDTO,
)
from athena.api.v1.providers.base import CandleHistoryProvider
from athena.config.loader import load_config
from athena.data.store.repository import SqliteRepository
from athena.domain.enums import Timeframe
from athena.indicators.calculations import align_trailing_series, atr_series, sma_series

# Fixed Kite instrument ids for the header ticker (DT-2) — the snapshot's own
# `indices` dict uses the short tradingsymbol ("NIFTY 50") as its key, but
# persisted candles use the full instrument id, so both forms are needed.
_TICKER_INDICES: tuple[tuple[str, str, str], ...] = (
    # (ticker label, snapshot "indices" key, candle instrument_id)
    ("NIFTY 50", "NIFTY 50", "NSE:NIFTY 50"),
    ("BANK NIFTY", "NIFTY BANK", "NSE:NIFTY BANK"),
)
_VIX_LABEL = "INDIA VIX"
_VIX_CANDLE_ID = "NSE:INDIA VIX"


class MarketHistoryService:
    """Map persisted candles to an explicit, freshness-aware API contract."""

    def __init__(
        self,
        provider: CandleHistoryProvider,
        *,
        freshness_threshold_minutes: int,
        now_fn: Callable[[], datetime] | None = None,
        config_dir: Path | None = None,
        repo: SqliteRepository | None = None,
    ) -> None:
        if freshness_threshold_minutes < 1:
            raise ValueError("freshness_threshold_minutes must be >= 1")
        self._provider = provider
        self._freshness_threshold_minutes = freshness_threshold_minutes
        self._now = now_fn or (lambda: datetime.now(tz=timezone.utc))
        self._config_dir = Path(config_dir) if config_dir else Path("config")
        self._repo = repo

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

    def market_ticker(self) -> MarketTickerDTO:
        """Header ticker (DT-2): NIFTY 50 / BANK NIFTY / INDIA VIX, each with
        its live level (from the latest persisted Kite snapshot) and a
        day-over-day change % derived from the most recent prior daily
        candle close — both already-persisted, real values, never a new
        calculation beyond simple arithmetic over them. Deliberately excludes
        market breadth and an overall health score (see MarketTickerDTO).
        Every field is None, not a fabricated number, when its underlying
        data isn't available yet."""
        empty = MarketTickerDTO(
            nifty=MarketIndexTickerDTO(label="NIFTY 50"),
            bank_nifty=MarketIndexTickerDTO(label="BANK NIFTY"),
            india_vix=MarketIndexTickerDTO(label=_VIX_LABEL),
        )
        if self._repo is None:
            return empty
        snapshot = self._repo.get_latest_snapshot()
        if snapshot is None:
            return empty

        index_tickers = {
            label: self._index_ticker(label, snapshot.indices.get(snapshot_key), candle_id, snapshot.ts)
            for label, snapshot_key, candle_id in _TICKER_INDICES
        }
        vix_ticker = self._index_ticker(_VIX_LABEL, snapshot.india_vix, _VIX_CANDLE_ID, snapshot.ts)

        return MarketTickerDTO(
            nifty=index_tickers["NIFTY 50"],
            bank_nifty=index_tickers["BANK NIFTY"],
            india_vix=vix_ticker,
            as_of=snapshot.ts,
        )

    def _index_ticker(
        self,
        label: str,
        level: Decimal | None,
        candle_instrument_id: str,
        snapshot_ts: datetime,
    ) -> MarketIndexTickerDTO:
        if level is None:
            return MarketIndexTickerDTO(label=label)
        baseline = self._prior_close(candle_instrument_id, snapshot_ts)
        change_pct = (
            ((level - baseline) / baseline * Decimal(100)) if baseline else None
        )
        return MarketIndexTickerDTO(label=label, level=level, change_pct=change_pct)

    def _prior_close(self, instrument_id: str, snapshot_ts: datetime) -> Decimal | None:
        """Most recent daily candle close strictly before the snapshot's own
        trading day — i.e. the prior session's close, so an intraday
        snapshot is compared against yesterday, not against today's own
        still-forming bar."""
        if self._repo is None:
            return None
        candles = self._repo.list_candles_recent(instrument_id, Timeframe.D1, limit=5)
        snapshot_date = snapshot_ts.astimezone(snapshot_ts.tzinfo).date()
        prior = [c for c in candles if c.ts_open.astimezone(snapshot_ts.tzinfo).date() < snapshot_date]
        return prior[-1].close if prior else None
