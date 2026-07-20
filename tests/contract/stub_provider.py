"""Deterministic in-memory provider — TEST INFRASTRUCTURE ONLY.

Exists to prove the contract suite itself works (M1.1). It is NOT FileProvider
(that is M1.2) and must never be imported by src/ code. Data is generated
arithmetically — no randomness, no clock reads — so every run is identical.
"""

from __future__ import annotations

from datetime import date, datetime, time, timedelta, timezone
from decimal import Decimal

from athena.domain.enums import HealthStatus, Timeframe
from athena.domain.interfaces import ProviderCapabilities, ProviderHealth
from athena.domain.market import Candle, Instrument, MarketSnapshot, Quote
from athena.errors import ProviderError

_TZ = timezone.utc
_DATA_START = date(2026, 1, 1)
_DATA_END = date(2026, 3, 31)


class StubProvider:
    """Two instruments, weekday daily candles Jan-Mar 2026, 5m candles, quotes."""

    name = "stub"

    _INSTRUMENTS = (
        Instrument(instrument_id="STUB-AAA", symbol="AAA", exchange="NSE", series="EQ"),
        Instrument(instrument_id="STUB-BBB", symbol="BBB", exchange="NSE", series="EQ"),
    )

    def capabilities(self) -> ProviderCapabilities:
        return ProviderCapabilities(
            timeframes=(Timeframe.D1, Timeframe.M5),
            max_history_days=90,
            supports_quotes=True,
            supports_market_snapshot=True,
        )

    def instruments(self) -> list[Instrument]:
        return list(self._INSTRUMENTS)

    def _require_known(self, instrument_id: str) -> None:
        if instrument_id not in {i.instrument_id for i in self._INSTRUMENTS}:
            raise ProviderError(f"unknown instrument id: {instrument_id}")

    @staticmethod
    def _base_price(instrument_id: str, day: date) -> Decimal:
        # Deterministic arithmetic price: stable across runs, varies by day/instrument.
        seed = sum(ord(ch) for ch in instrument_id) + day.toordinal() % 50
        return Decimal(seed) + Decimal("100")

    def daily_candles(self, instrument_id: str, start: date, end: date) -> list[Candle]:
        self._require_known(instrument_id)
        candles: list[Candle] = []
        day = max(start, _DATA_START)
        last = min(end, _DATA_END)
        while day <= last:
            if day.weekday() < 5:  # weekdays only
                base = self._base_price(instrument_id, day)
                candles.append(Candle(
                    instrument_id=instrument_id,
                    timeframe=Timeframe.D1,
                    ts_open=datetime.combine(day, time(9, 15), tzinfo=_TZ),
                    open=base,
                    high=base + Decimal("2"),
                    low=base - Decimal("1"),
                    close=base + Decimal("1"),
                    volume=10_000 + day.toordinal() % 1000,
                    source=self.name,
                ))
            day += timedelta(days=1)
        return candles

    def intraday_candles(
        self, instrument_id: str, timeframe: Timeframe, start: datetime, end: datetime
    ) -> list[Candle]:
        self._require_known(instrument_id)
        if timeframe not in self.capabilities().timeframes or timeframe is Timeframe.D1:
            raise ProviderError(
                f"timeframe {timeframe.value} not supported by provider '{self.name}'"
            )
        candles: list[Candle] = []
        ts = start
        step = timedelta(minutes=5)
        while ts <= end and len(candles) < 500:
            day = ts.date()
            if _DATA_START <= day <= _DATA_END and ts.weekday() < 5:
                base = self._base_price(instrument_id, day) + Decimal(ts.minute) / Decimal(100)
                candles.append(Candle(
                    instrument_id=instrument_id,
                    timeframe=timeframe,
                    ts_open=ts,
                    open=base,
                    high=base + Decimal("0.5"),
                    low=base - Decimal("0.5"),
                    close=base,
                    volume=500,
                    source=self.name,
                ))
            ts += step
        return candles

    def quotes(self, instrument_ids: list[str]) -> list[Quote]:
        for instrument_id in instrument_ids:
            self._require_known(instrument_id)
        return [
            Quote(
                instrument_id=instrument_id,
                ts=datetime.combine(_DATA_END, time(15, 30), tzinfo=_TZ),
                last_price=self._base_price(instrument_id, _DATA_END),
                volume=42_000,
                source=self.name,
            )
            for instrument_id in instrument_ids
        ]

    def market_snapshot(self) -> MarketSnapshot:
        return MarketSnapshot(
            ts=datetime.combine(_DATA_END, time(15, 30), tzinfo=_TZ),
            indices={"NIFTY50": Decimal("25000")},
            breadth_advances=30,
            breadth_declines=20,
            india_vix=Decimal("14.5"),
        )

    def health(self) -> ProviderHealth:
        return ProviderHealth(
            status=HealthStatus.OK,
            detail="stub provider: static deterministic dataset 2026-01-01..2026-03-31",
            last_data_ts=datetime.combine(_DATA_END, time(15, 30), tzinfo=_TZ),
        )
