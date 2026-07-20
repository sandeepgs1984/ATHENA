"""FileProvider — the reference MarketDataProvider (M1.2, ADR-002).

Reads market data from local files; conforms 100% to the frozen provider
contract (ATHENA-002 §7.2, tests/contract/provider_contract.py). It is the
model every future provider follows.

Design commitments:
- Deterministic: identical requests → identical results; no caching, no
  mutable global state, no clock reads, no concurrency.
- Immutable domain objects out; Decimal precision and tz-aware timestamps in.
- Loading correctness only — freshness/gap/cross-dataset validation is M1.3.
  (Duplicate timestamps within a file ARE rejected here, because the contract
  guarantees callers unique, sorted candles.)

FILE FORMATS
------------
- ``<data_root>/<instruments_file>`` (CSV): header
  ``instrument_id,symbol,exchange,series,isin,lot_size,tick_size,status,listed_date,delisted_date``
  (isin/status/dates may be empty).
- ``<data_root>/<daily_dir>/<instrument_id>.csv`` (CSV): header
  ``ts_open,open,high,low,close,volume`` — ts_open is ISO-8601 with offset.
- ``<data_root>/<intraday_dir>/<timeframe>/<instrument_id>.csv`` — same candle schema.
- ``<data_root>/<quotes_file>`` (CSV): header ``instrument_id,ts,last_price,volume``.
- ``<data_root>/<snapshot_file>`` (JSON): {ts, indices{name:price},
  breadth_advances, breadth_declines, india_vix}.
"""

from __future__ import annotations

import csv
import json
from datetime import date, datetime
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Dict, List

from athena.config.models import FileProviderConfig
from athena.domain.enums import HealthStatus, Timeframe
from athena.domain.interfaces import ProviderCapabilities, ProviderHealth
from athena.domain.market import Candle, Instrument, MarketSnapshot, Quote
from athena.errors import ProviderError

_CANDLE_HEADER = ["ts_open", "open", "high", "low", "close", "volume"]
_QUOTE_HEADER = ["instrument_id", "ts", "last_price", "volume"]
_INTRADAY_TIMEFRAMES = {Timeframe.M1, Timeframe.M5, Timeframe.M15}


def _decimal(value: str, field: str, where: str) -> Decimal:
    try:
        return Decimal(value.strip())
    except (InvalidOperation, AttributeError) as exc:
        raise ProviderError(f"corrupted data in {where}: '{value}' is not a valid {field}") from exc


def _int(value: str, field: str, where: str) -> int:
    try:
        return int(value.strip())
    except (ValueError, AttributeError) as exc:
        raise ProviderError(f"corrupted data in {where}: '{value}' is not a valid {field}") from exc


def _aware_ts(value: str, where: str) -> datetime:
    try:
        ts = datetime.fromisoformat(value.strip())
    except (ValueError, AttributeError) as exc:
        raise ProviderError(f"corrupted data in {where}: '{value}' is not an ISO timestamp") from exc
    if ts.tzinfo is None:
        raise ProviderError(f"corrupted data in {where}: timestamp '{value}' lacks a timezone")
    return ts


def _opt_date(value: str) -> date | None:
    value = (value or "").strip()
    return date.fromisoformat(value) if value else None


class FileProvider:
    """A ``MarketDataProvider`` backed by local files."""

    def __init__(self, config: FileProviderConfig, data_root: Path) -> None:
        self.name = "file"
        self._config = config
        self._data_root = Path(data_root)
        self._capabilities = ProviderCapabilities(
            timeframes=tuple(Timeframe(t) for t in config.capabilities.timeframes),
            max_history_days=config.capabilities.max_history_days,
            supports_quotes=config.capabilities.supports_quotes,
            supports_market_snapshot=config.capabilities.supports_market_snapshot,
        )

    @classmethod
    def from_config_dir(cls, config_dir: Path, base_dir: Path | None = None) -> "FileProvider":
        """Build from config/providers/file.json; data_root resolves against base_dir
        (defaults to the repo root, i.e. the config dir's parent)."""
        from athena.config.loader import load_file_provider_config

        config = load_file_provider_config(config_dir)
        base = Path(base_dir) if base_dir is not None else Path(config_dir).resolve().parent
        root = Path(config.data_root)
        data_root = root if root.is_absolute() else base / root
        return cls(config, data_root)

    # ---------------------------------------------------------------- contract

    def capabilities(self) -> ProviderCapabilities:
        return self._capabilities

    def instruments(self) -> List[Instrument]:
        return list(self._load_instruments().values())

    def daily_candles(self, instrument_id: str, start: date, end: date) -> List[Candle]:
        self._require_known(instrument_id)
        path = self._data_root / self._config.daily_dir / f"{instrument_id}.csv"
        candles = self._read_candles(path, instrument_id, Timeframe.D1)
        return [c for c in candles if start <= c.ts_open.date() <= end]

    def intraday_candles(
        self, instrument_id: str, timeframe: Timeframe, start: datetime, end: datetime
    ) -> List[Candle]:
        self._require_known(instrument_id)
        if timeframe not in self._capabilities.timeframes or timeframe not in _INTRADAY_TIMEFRAMES:
            raise ProviderError(
                f"timeframe {timeframe.value} not supported by provider '{self.name}' "
                f"(declared: {[t.value for t in self._capabilities.timeframes]})"
            )
        path = self._data_root / self._config.intraday_dir / timeframe.value / f"{instrument_id}.csv"
        candles = self._read_candles(path, instrument_id, timeframe)
        return [c for c in candles if start <= c.ts_open <= end]

    def quotes(self, instrument_ids: List[str]) -> List[Quote]:
        if not self._capabilities.supports_quotes:
            raise ProviderError(f"provider '{self.name}' does not support quotes")
        for instrument_id in instrument_ids:
            self._require_known(instrument_id)
        requested = set(instrument_ids)
        return [q for q in self._read_quotes() if q.instrument_id in requested]

    def market_snapshot(self) -> MarketSnapshot:
        if not self._capabilities.supports_market_snapshot:
            raise ProviderError(f"provider '{self.name}' does not support market snapshot")
        return self._read_snapshot()

    def health(self) -> ProviderHealth:
        if not self._data_root.is_dir():
            return ProviderHealth(
                status=HealthStatus.BLOCKED,
                detail=f"data root not found: {self._data_root}",
            )
        last_ts = None
        snapshot_path = self._data_root / self._config.snapshot_file
        if self._capabilities.supports_market_snapshot and snapshot_path.exists():
            last_ts = self._read_snapshot().ts
        return ProviderHealth(
            status=HealthStatus.OK,
            detail=f"file provider serving from {self._data_root}",
            last_data_ts=last_ts,
        )

    # ------------------------------------------------------------------ internals

    def _require_known(self, instrument_id: str) -> None:
        if instrument_id not in self._load_instruments():
            raise ProviderError(f"unknown instrument id: {instrument_id}")

    def _load_instruments(self) -> Dict[str, Instrument]:
        path = self._data_root / self._config.instruments_file
        rows = self._read_csv(path, expected_first="instrument_id")
        instruments: Dict[str, Instrument] = {}
        for line_no, row in rows:
            where = f"{path}:{line_no}"
            try:
                instrument = Instrument(
                    instrument_id=row["instrument_id"].strip(),
                    symbol=row["symbol"].strip(),
                    exchange=row["exchange"].strip(),
                    series=row["series"].strip(),
                    isin=(row.get("isin") or "").strip() or None,
                    lot_size=_int(row["lot_size"], "lot_size", where),
                    tick_size=_decimal(row["tick_size"], "tick_size", where),
                    status=(row.get("status") or "ACTIVE").strip() or "ACTIVE",
                    listed_date=_opt_date(row.get("listed_date", "")),
                    delisted_date=_opt_date(row.get("delisted_date", "")),
                )
            except (KeyError, ValueError) as exc:
                raise ProviderError(f"corrupted instrument row at {where}: {exc}") from exc
            if instrument.instrument_id in instruments:
                raise ProviderError(f"duplicate instrument id '{instrument.instrument_id}' at {where}")
            instruments[instrument.instrument_id] = instrument
        return instruments

    def _read_candles(self, path: Path, instrument_id: str, timeframe: Timeframe) -> List[Candle]:
        if not path.exists():
            return []  # a known instrument with no data for this timeframe is empty, not an error
        rows = self._read_csv(path, expected_first="ts_open")
        candles: List[Candle] = []
        seen: set[datetime] = set()
        for line_no, row in rows:
            where = f"{path}:{line_no}"
            try:
                candle = Candle(
                    instrument_id=instrument_id,
                    timeframe=timeframe,
                    ts_open=_aware_ts(row["ts_open"], where),
                    open=_decimal(row["open"], "open", where),
                    high=_decimal(row["high"], "high", where),
                    low=_decimal(row["low"], "low", where),
                    close=_decimal(row["close"], "close", where),
                    volume=_int(row["volume"], "volume", where),
                    source=self.name,
                )
            except KeyError as exc:
                raise ProviderError(f"corrupted candle row at {where}: missing column {exc}") from exc
            except ValueError as exc:
                # Candle invariants (impossible OHLC, naive ts) → corrupted data.
                raise ProviderError(f"corrupted candle at {where}: {exc}") from exc
            if candle.ts_open in seen:
                raise ProviderError(f"duplicate candle timestamp {candle.ts_open} at {where}")
            seen.add(candle.ts_open)
            candles.append(candle)
        candles.sort(key=lambda c: c.ts_open)
        return candles

    def _read_quotes(self) -> List[Quote]:
        path = self._data_root / self._config.quotes_file
        if not path.exists():
            raise ProviderError(f"missing quotes file: {path}")
        rows = self._read_csv(path, expected_first="instrument_id")
        quotes: Dict[str, Quote] = {}
        for line_no, row in rows:
            where = f"{path}:{line_no}"
            try:
                instrument_id = row["instrument_id"].strip()
                quote = Quote(
                    instrument_id=instrument_id,
                    ts=_aware_ts(row["ts"], where),
                    last_price=_decimal(row["last_price"], "last_price", where),
                    volume=_int(row["volume"], "volume", where),
                    source=self.name,
                )
            except KeyError as exc:
                raise ProviderError(f"corrupted quote row at {where}: missing column {exc}") from exc
            except ValueError as exc:
                raise ProviderError(f"corrupted quote at {where}: {exc}") from exc
            quotes[instrument_id] = quote  # last row for an id wins; at most one per id
        return list(quotes.values())

    def _read_snapshot(self) -> MarketSnapshot:
        path = self._data_root / self._config.snapshot_file
        if not path.exists():
            raise ProviderError(f"missing market snapshot file: {path}")
        try:
            with path.open(encoding="utf-8") as fh:
                data = json.load(fh)
        except json.JSONDecodeError as exc:
            raise ProviderError(f"invalid JSON in snapshot {path}: {exc}") from exc
        try:
            return MarketSnapshot(
                ts=_aware_ts(data["ts"], str(path)),
                indices={k: _decimal(str(v), "index value", str(path))
                         for k, v in data["indices"].items()},
                breadth_advances=int(data.get("breadth_advances", 0)),
                breadth_declines=int(data.get("breadth_declines", 0)),
                india_vix=(_decimal(str(data["india_vix"]), "india_vix", str(path))
                           if data.get("india_vix") is not None else None),
            )
        except (KeyError, ValueError) as exc:
            raise ProviderError(f"corrupted market snapshot {path}: {exc}") from exc

    def _read_csv(self, path: Path, expected_first: str) -> List[tuple[int, Dict[str, str]]]:
        if not path.exists():
            raise ProviderError(f"missing file: {path}")
        try:
            with path.open(encoding="utf-8", newline="") as fh:
                reader = csv.DictReader(fh)
                if reader.fieldnames is None or reader.fieldnames[0].strip() != expected_first:
                    raise ProviderError(
                        f"invalid file format in {path}: expected first column "
                        f"'{expected_first}', got {reader.fieldnames}"
                    )
                return [(i, row) for i, row in enumerate(reader, start=2)]
        except UnicodeDecodeError as exc:
            raise ProviderError(f"invalid file encoding in {path}: {exc}") from exc
