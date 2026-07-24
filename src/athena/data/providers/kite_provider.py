"""KiteProvider — Zerodha Kite Connect read-only MarketDataProvider (R4, DD-1).

Conforms to the frozen provider contract (``tests/contract/provider_contract.py``).
Uses allowlisted GET-only HTTP (``kite_transport``) — no order methods, no
``kiteconnect`` SDK (which exposes placement APIs).

Instrument ids are ``exchange:tradingsymbol`` (e.g. ``NSE:INFY``).
Secrets: ``KITE_API_KEY``, ``KITE_ACCESS_TOKEN`` from the environment only.
"""

from __future__ import annotations

import csv
import io
import os
from datetime import date, datetime, timedelta
from decimal import Decimal, InvalidOperation
from pathlib import Path
from zoneinfo import ZoneInfo

from athena.config.models import KiteProviderConfig
from athena.data.providers.kite_transport import KiteTransport, UrllibKiteTransport
from athena.domain.enums import HealthStatus, Timeframe
from athena.domain.interfaces import ProviderCapabilities, ProviderHealth
from athena.domain.market import Candle, Instrument, MarketSnapshot, Quote
from athena.errors import ProviderError

IST = ZoneInfo("Asia/Kolkata")

_INTRADAY = {Timeframe.M1, Timeframe.M5, Timeframe.M15}

_TF_TO_KITE = {
    Timeframe.M1: "minute",
    Timeframe.M5: "5minute",
    Timeframe.M15: "15minute",
    Timeframe.D1: "day",
}

#: Max calendar span per historical request (Kite Connect limits).
_CHUNK_DAYS = {
    Timeframe.M1: 60,
    Timeframe.M5: 100,
    Timeframe.M15: 200,
    Timeframe.D1: 2000,
}


def _parse_kite_ts(raw: str) -> datetime:
    s = raw.strip().replace(" ", "T")
    if len(s) >= 5 and s[-5] in "+-" and ":" not in s[-5:]:
        s = f"{s[:-2]}:{s[-2:]}"
    try:
        ts = datetime.fromisoformat(s)
    except ValueError as exc:
        raise ProviderError(f"kite timestamp unparseable: '{raw}'") from exc
    if ts.tzinfo is None:
        return ts.replace(tzinfo=IST)
    return ts


def _decimal(value: object, field: str) -> Decimal:
    try:
        return Decimal(str(value))
    except (InvalidOperation, TypeError) as exc:
        raise ProviderError(f"kite returned invalid {field}: {value!r}") from exc


class KiteProvider:
    """A ``MarketDataProvider`` backed by Kite Connect market-data GETs."""

    def __init__(self, config: KiteProviderConfig, transport: KiteTransport) -> None:
        self.name = "kite"
        self._config = config
        self._transport = transport
        self._capabilities = ProviderCapabilities(
            timeframes=tuple(Timeframe(t) for t in config.capabilities.timeframes),
            max_history_days=config.capabilities.max_history_days,
            supports_quotes=config.capabilities.supports_quotes,
            supports_market_snapshot=config.capabilities.supports_market_snapshot,
        )
        self._instruments: dict[str, Instrument] | None = None
        self._tokens: dict[str, int] | None = None
        self._last_data_ts: datetime | None = None

    @classmethod
    def from_config_dir(
        cls,
        config_dir: Path,
        *,
        transport: KiteTransport | None = None,
        symbols: list[str] | None = None,
    ) -> KiteProvider:
        from athena.config.loader import load_kite_provider_config

        config = load_kite_provider_config(config_dir)
        if symbols is not None:
            config = config.model_copy(update={"symbols": list(symbols)})
        if transport is None:
            transport = UrllibKiteTransport(
                base_url=config.base_url,
                api_key=os.environ.get("KITE_API_KEY", ""),
                access_token=os.environ.get("KITE_ACCESS_TOKEN", ""),
            )
        return cls(config, transport)

    # ---------------------------------------------------------------- contract

    def capabilities(self) -> ProviderCapabilities:
        return self._capabilities

    def instruments(self) -> list[Instrument]:
        return list(self._ensure_catalog()[0].values())

    def daily_candles(self, instrument_id: str, start: date, end: date) -> list[Candle]:
        token = self._require_token(instrument_id)
        if start > end:
            return []
        start_dt = datetime.combine(start, datetime.min.time(), tzinfo=IST)
        end_dt = datetime.combine(end, datetime.max.time().replace(microsecond=0), tzinfo=IST)
        candles = self._historical(token, instrument_id, Timeframe.D1, start_dt, end_dt)
        return [c for c in candles if start <= c.ts_open.date() <= end]

    def intraday_candles(
        self, instrument_id: str, timeframe: Timeframe, start: datetime, end: datetime
    ) -> list[Candle]:
        token = self._require_token(instrument_id)
        if timeframe not in self._capabilities.timeframes or timeframe not in _INTRADAY:
            raise ProviderError(
                f"timeframe {timeframe.value} not supported by provider '{self.name}' "
                f"(declared: {[t.value for t in self._capabilities.timeframes]})"
            )
        if start.tzinfo is None or end.tzinfo is None:
            raise ProviderError("intraday range endpoints must be timezone-aware")
        if start > end:
            return []
        span_days = (end.date() - start.date()).days + 1
        max_days = self._capabilities.max_history_days
        if span_days > max_days:
            raise ProviderError(
                f"requested intraday history ({span_days} days) exceeds provider "
                f"'{self.name}' max_history_days={max_days} (DD-10 / accumulate live)"
            )
        return self._historical(token, instrument_id, timeframe, start, end)

    def quotes(self, instrument_ids: list[str]) -> list[Quote]:
        if not self._capabilities.supports_quotes:
            raise ProviderError(f"provider '{self.name}' does not support quotes")
        for instrument_id in instrument_ids:
            self._require_token(instrument_id)
        if not instrument_ids:
            return []

        out: dict[str, Quote] = {}
        batch = self._config.quote_batch_size
        for i in range(0, len(instrument_ids), batch):
            chunk = instrument_ids[i : i + batch]
            payload = self._transport.get_json(
                "/quote",
                [("i", iid) for iid in chunk],
            )
            data = payload.get("data") or {}
            if not isinstance(data, dict):
                raise ProviderError("kite /quote returned malformed data")
            for iid in chunk:
                row = data.get(iid)
                if row is None:
                    continue
                ts_raw = row.get("timestamp") or row.get("last_trade_time")
                if not ts_raw:
                    raise ProviderError(f"kite quote for {iid} missing timestamp")
                ts = _parse_kite_ts(str(ts_raw))
                quote = Quote(
                    instrument_id=iid,
                    ts=ts,
                    last_price=_decimal(row.get("last_price"), "last_price"),
                    volume=int(row.get("volume") or 0),
                    source=self.name,
                )
                out[iid] = quote
                self._last_data_ts = ts if self._last_data_ts is None else max(self._last_data_ts, ts)
        return list(out.values())

    def market_snapshot(self) -> MarketSnapshot:
        if not self._capabilities.supports_market_snapshot:
            raise ProviderError(f"provider '{self.name}' does not support market snapshot")
        keys = list(self._config.index_instruments)
        vix_key = self._config.india_vix_instrument.strip()
        if vix_key and vix_key not in keys:
            keys.append(vix_key)
        if not keys:
            raise ProviderError("kite index_instruments is empty; cannot build market snapshot")

        payload = self._transport.get_json("/quote", [("i", k) for k in keys])
        data = payload.get("data") or {}
        if not isinstance(data, dict):
            raise ProviderError("kite /quote returned malformed data for snapshot")

        indices: dict[str, Decimal] = {}
        india_vix: Decimal | None = None
        latest: datetime | None = None
        for key in keys:
            row = data.get(key)
            if row is None:
                continue
            price = _decimal(row.get("last_price"), "last_price")
            ts_raw = row.get("timestamp") or row.get("last_trade_time")
            if ts_raw:
                ts = _parse_kite_ts(str(ts_raw))
                latest = ts if latest is None else max(latest, ts)
            if key == vix_key:
                india_vix = price
            else:
                # Prefer tradingsymbol as index name (after exchange:).
                name = key.split(":", 1)[-1]
                indices[name] = price

        if not indices:
            raise ProviderError(
                "kite market snapshot empty: no index quotes returned "
                f"(requested {self._config.index_instruments})"
            )
        if latest is None:
            latest = datetime.now(IST)
        self._last_data_ts = latest if self._last_data_ts is None else max(self._last_data_ts, latest)
        return MarketSnapshot(
            ts=latest,
            indices=indices,
            breadth_advances=0,
            breadth_declines=0,
            india_vix=india_vix,
        )

    def health(self) -> ProviderHealth:
        try:
            self._ensure_catalog()
        except ProviderError as exc:
            return ProviderHealth(
                status=HealthStatus.BLOCKED,
                detail=f"kite provider unhealthy: {exc}",
            )
        return ProviderHealth(
            status=HealthStatus.OK,
            detail="kite provider credentials present; instrument catalog loaded",
            last_data_ts=self._last_data_ts,
        )

    # ------------------------------------------------------------------ internals

    def _ensure_catalog(self) -> tuple[dict[str, Instrument], dict[str, int]]:
        if self._instruments is not None and self._tokens is not None:
            return self._instruments, self._tokens

        exchange = self._config.exchange.strip().upper()
        text = self._transport.get_text(f"/instruments/{exchange}")
        reader = csv.DictReader(io.StringIO(text))
        if not reader.fieldnames or "instrument_token" not in reader.fieldnames:
            raise ProviderError("kite instruments CSV missing instrument_token column")

        wanted_types = {t.upper() for t in self._config.instrument_types}
        symbol_filter = {s.upper() for s in self._config.symbols}

        instruments: dict[str, Instrument] = {}
        tokens: dict[str, int] = {}

        for row in reader:
            row_exchange = (row.get("exchange") or "").strip().upper()
            if row_exchange != exchange:
                continue
            itype = (row.get("instrument_type") or "").strip().upper()
            tradingsymbol = (row.get("tradingsymbol") or "").strip()
            if not tradingsymbol:
                continue
            instrument_id = f"{row_exchange}:{tradingsymbol}"

            include = itype in wanted_types
            if symbol_filter:
                include = include and tradingsymbol.upper() in symbol_filter
            # Always index configured snapshot keys if present in dump.
            if instrument_id in self._config.index_instruments or instrument_id == self._config.india_vix_instrument:
                include = True
            if not include:
                continue

            try:
                token = int(row["instrument_token"])
            except (KeyError, ValueError) as exc:
                raise ProviderError(f"kite instruments row bad token for {instrument_id}") from exc

            series = itype or "EQ"
            try:
                tick = _decimal(row.get("tick_size") or "0.05", "tick_size")
                lot = int(row.get("lot_size") or 1)
            except (ProviderError, ValueError) as exc:
                raise ProviderError(f"kite instruments row corrupt for {instrument_id}: {exc}") from exc

            instruments[instrument_id] = Instrument(
                instrument_id=instrument_id,
                symbol=tradingsymbol,
                exchange=row_exchange,
                series=series,
                lot_size=max(lot, 1),
                tick_size=tick,
                status="ACTIVE",
            )
            tokens[instrument_id] = token

        if symbol_filter:
            have = {k.split(":", 1)[-1].upper() for k in instruments}
            missing = [sym for sym in self._config.symbols if sym.upper() not in have]
            if missing:
                raise ProviderError(f"kite symbols not found on {exchange}: {missing}")

        if not instruments:
            raise ProviderError(
                f"kite instrument catalog empty after filters "
                f"(exchange={exchange}, types={sorted(wanted_types)}, "
                f"symbols={list(symbol_filter) or 'ALL'})"
            )

        self._instruments = instruments
        self._tokens = tokens
        return instruments, tokens

    def _require_token(self, instrument_id: str) -> int:
        _, tokens = self._ensure_catalog()
        if instrument_id not in tokens:
            raise ProviderError(f"unknown instrument id: {instrument_id}")
        return tokens[instrument_id]

    def _historical(
        self,
        token: int,
        instrument_id: str,
        timeframe: Timeframe,
        start: datetime,
        end: datetime,
    ) -> list[Candle]:
        kite_interval = _TF_TO_KITE[timeframe]
        chunk_days = _CHUNK_DAYS[timeframe]
        candles: list[Candle] = []
        seen: set[datetime] = set()

        cursor = start
        while cursor <= end:
            chunk_end = min(cursor + timedelta(days=chunk_days - 1), end)
            path = f"/instruments/historical/{token}/{kite_interval}"
            params = {
                "from": cursor.astimezone(IST).strftime("%Y-%m-%d %H:%M:%S"),
                "to": chunk_end.astimezone(IST).strftime("%Y-%m-%d %H:%M:%S"),
            }
            payload = self._transport.get_json(path, params)
            data = payload.get("data") or {}
            rows = data.get("candles") if isinstance(data, dict) else None
            if rows is None:
                rows = []
            if not isinstance(rows, list):
                raise ProviderError(f"kite historical candles malformed for {instrument_id}")

            for row in rows:
                if not isinstance(row, (list, tuple)) or len(row) < 6:
                    raise ProviderError(f"kite candle row malformed for {instrument_id}: {row!r}")
                ts = _parse_kite_ts(str(row[0]))
                if ts < start or ts > end:
                    continue
                if timeframe is Timeframe.D1:
                    # Daily bars: keep if calendar date in [start.date, end.date]
                    pass
                try:
                    candle = Candle(
                        instrument_id=instrument_id,
                        timeframe=timeframe,
                        ts_open=ts,
                        open=_decimal(row[1], "open"),
                        high=_decimal(row[2], "high"),
                        low=_decimal(row[3], "low"),
                        close=_decimal(row[4], "close"),
                        volume=int(row[5]),
                        source=self.name,
                    )
                except (ValueError, ProviderError) as exc:
                    raise ProviderError(
                        f"kite candle rejected for {instrument_id} at {ts}: {exc}"
                    ) from exc
                if candle.ts_open in seen:
                    continue
                seen.add(candle.ts_open)
                candles.append(candle)
                self._last_data_ts = (
                    candle.ts_open
                    if self._last_data_ts is None
                    else max(self._last_data_ts, candle.ts_open)
                )

            cursor = chunk_end + timedelta(seconds=1)

        candles.sort(key=lambda c: c.ts_open)
        return candles
