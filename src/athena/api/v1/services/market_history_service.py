"""Read-only persisted market history for dashboard charting (M-D2, UX-3b)."""

from __future__ import annotations

import threading
import time
from collections.abc import Callable
from datetime import datetime, timezone
from decimal import Decimal
from pathlib import Path
from typing import Literal
from zoneinfo import ZoneInfo

from athena.api.v1.dtos.market import (
    CandleDTO,
    CandleSeriesDTO,
    IndexConstituentContextDTO,
    IndexIntelligenceDTO,
    IndexIntelligenceItemDTO,
    InstrumentQuoteDTO,
    MarketIndexTickerDTO,
    MarketTickerDTO,
)
from athena.api.v1.providers.base import CandleHistoryProvider
from athena.config.loader import load_config, load_index_intelligence_config
from athena.config.models import IndexIntelligenceConfig, TrackedIndexConfig
from athena.data.index_constituents import load_index_constituent_snapshot
from athena.data.providers.kite_ltp import fetch_live_quote
from athena.data.store.repository import SqliteRepository
from athena.domain.decision import Decision
from athena.domain.enums import DecisionType, Timeframe
from athena.domain.market import MarketSnapshot
from athena.errors import ConfigError, ProviderError
from athena.indicators.calculations import align_trailing_series, atr_series, sma_series

# Process-local coalescing so a double-render or overlapping polls never hit
# Kite twice for the same symbol within a short window (10s UI interval ≫ TTL).
_LIVE_QUOTE_CACHE_TTL_SECONDS = 5.0
_live_quote_cache: dict[str, tuple[float, InstrumentQuoteDTO]] = {}
_live_quote_lock = threading.Lock()

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

    def index_intelligence(self) -> IndexIntelligenceDTO:
        """Configured broad-market and sector indices from persisted data.

        Catalog order is configuration-owned. A missing quote or prior close is
        represented explicitly rather than inferred from another index.
        """
        config = load_index_intelligence_config(self._config_dir)
        tracked = sorted(
            (item for item in config.tracked_indices if item.enabled),
            key=lambda item: (item.display_order, item.key),
        )
        snapshot = self._repo.get_latest_snapshot() if self._repo is not None else None
        prior_session_snapshot = (
            self._prior_session_snapshot(snapshot.ts) if snapshot is not None else None
        )
        constituent_contexts = self._index_constituent_contexts(config, tracked)

        items: list[IndexIntelligenceItemDTO] = []
        for item in tracked:
            snapshot_key = item.instrument_id.split(":", 1)[-1]
            level = snapshot.indices.get(snapshot_key) if snapshot is not None else None
            baseline = None
            if snapshot is not None and level is not None:
                baseline = self._prior_close(item.instrument_id, snapshot.ts)
                if baseline is None and prior_session_snapshot is not None:
                    baseline = prior_session_snapshot.indices.get(snapshot_key)
            change_pct = (
                (level - baseline) / baseline * Decimal(100)
                if level is not None and baseline is not None and baseline > 0
                else None
            )
            items.append(
                IndexIntelligenceItemDTO(
                    key=item.key,
                    label=item.label,
                    instrument_id=item.instrument_id,
                    family=item.family,
                    level=level,
                    change_pct=change_pct,
                    data_status="AVAILABLE" if level is not None else "NO_DATA",
                    constituents=constituent_contexts.get(item.key),
                )
            )

        return IndexIntelligenceDTO(
            indices=tuple(items),
            count=len(items),
            available_count=sum(item.data_status == "AVAILABLE" for item in items),
            as_of=snapshot.ts if snapshot is not None else None,
            source="persisted_market_snapshot",
        )

    def _index_constituent_contexts(
        self,
        config: IndexIntelligenceConfig,
        tracked: list[TrackedIndexConfig],
    ) -> dict[str, IndexConstituentContextDTO]:
        manifest_setting = config.constituent_manifest
        if not manifest_setting:
            return {}
        enabled_keys = {item.key for item in tracked}
        manifest_path = Path(str(manifest_setting))
        if not manifest_path.is_absolute():
            manifest_path = self._config_dir.parent / manifest_path
        membership = load_index_constituent_snapshot(
            manifest_path,
            expected_index_keys=enabled_keys,
        )
        now = self._now()
        if now.tzinfo is None:
            raise ValueError("market history clock must be timezone-aware")
        observed_date = now.astimezone(ZoneInfo("Asia/Kolkata")).date()
        if membership.effective_date > observed_date:
            raise ConfigError(
                "index constituent effective_date cannot be after the service clock"
            )

        instruments_by_symbol: dict[str, list[str]] = {}
        if self._repo is not None:
            for instrument in self._repo.list_instruments():
                if (
                    instrument.exchange.upper() == "NSE"
                    and instrument.series.upper() == "EQ"
                    and instrument.status.upper() == "ACTIVE"
                ):
                    instruments_by_symbol.setdefault(
                        instrument.symbol.upper(), []
                    ).append(instrument.instrument_id)
        latest_decisions = {
            decision.instrument_id: decision
            for decision in (
                self._repo.list_latest_decisions_by_instrument()
                if self._repo is not None
                else []
            )
            if decision.instrument_id is not None
        }

        contexts: dict[str, IndexConstituentContextDTO] = {}
        for index_set in membership.indices:
            resolved: dict[str, str] = {}
            unresolved: list[str] = []
            for symbol in index_set.symbols:
                matches = sorted(set(instruments_by_symbol.get(symbol, [])))
                if len(matches) == 1:
                    resolved[symbol] = matches[0]
                else:
                    unresolved.append(symbol)

            buckets: dict[str, str] = {}
            decisions_as_of: datetime | None = None
            missing_decisions: list[str] = []
            for symbol, instrument_id in resolved.items():
                decision = latest_decisions.get(instrument_id)
                bucket = self._current_board_bucket(decision, now)
                if bucket is None:
                    missing_decisions.append(symbol)
                    continue
                buckets[symbol] = bucket
                if decisions_as_of is None or decision.ts > decisions_as_of:
                    decisions_as_of = decision.ts

            if unresolved:
                breadth_status = "INCOMPLETE_INSTRUMENTS"
            elif missing_decisions:
                breadth_status = "INCOMPLETE_DECISIONS"
            else:
                breadth_status = "AVAILABLE"
            complete = breadth_status == "AVAILABLE"
            trade_count = sum(bucket == "TRADE" for bucket in buckets.values())
            watch_count = sum(bucket == "WATCH" for bucket in buckets.values())
            no_trade_count = sum(bucket == "NO_TRADE" for bucket in buckets.values())
            contexts[index_set.key] = IndexConstituentContextDTO(
                effective_date=membership.effective_date,
                membership_age_days=(observed_date - membership.effective_date).days,
                source_url=index_set.source_url,
                source_sha256=index_set.sha256,
                overlap_policy=membership.overlap_policy,
                total_members=len(index_set.symbols),
                resolved_members=len(resolved),
                unresolved_symbols=tuple(unresolved),
                decision_covered_members=len(buckets),
                missing_decision_symbols=tuple(missing_decisions),
                breadth_status=breadth_status,
                trade_count=trade_count if complete else None,
                watch_count=watch_count if complete else None,
                no_trade_count=no_trade_count if complete else None,
                trade_breadth_pct=(
                    (Decimal(trade_count) * Decimal(100) / Decimal(len(index_set.symbols))).quantize(
                        Decimal("0.1")
                    )
                    if complete and index_set.symbols
                    else None
                ),
                decisions_as_of=decisions_as_of,
            )
        return contexts

    @staticmethod
    def _current_board_bucket(decision: Decision | None, now: datetime) -> str | None:
        if decision is None:
            return None
        if decision.decision_type is DecisionType.TRADE:
            plan = decision.trade_plan
            if plan is not None and plan.valid_from <= now < plan.valid_until:
                return "TRADE"
            return None
        if decision.decision_type is DecisionType.WATCH:
            return "WATCH"
        if decision.decision_type is DecisionType.NO_TRADE:
            return "NO_TRADE"
        return None

    def instrument_quote(self, instrument_id: str) -> InstrumentQuoteDTO:
        """Live LTP for one symbol when Kite is reachable; else persisted quote.

        Load bounds: one ``/quote`` request for a single id (no instruments CSV),
        coalesced by a short process-local TTL so overlapping polls are free.
        """
        normalized = instrument_id.strip().upper()
        if not normalized:
            raise ValueError("instrument_id must be non-empty")
        if ":" not in normalized:
            normalized = f"NSE:{normalized}"

        empty = InstrumentQuoteDTO(instrument_id=normalized)

        with _live_quote_lock:
            cached = _live_quote_cache.get(normalized)
            if cached is not None:
                expires_at, dto = cached
                if time.monotonic() < expires_at:
                    return dto

        live = self._try_live_quote(normalized)
        if live is not None:
            with _live_quote_lock:
                _live_quote_cache[normalized] = (
                    time.monotonic() + _LIVE_QUOTE_CACHE_TTL_SECONDS,
                    live,
                )
            return live

        persisted = self._persisted_quote(normalized)
        if persisted is not None:
            return persisted
        return empty

    def _try_live_quote(self, instrument_id: str) -> InstrumentQuoteDTO | None:
        try:
            quote, change_pct = fetch_live_quote(
                instrument_id, config_dir=self._config_dir
            )
        except (ProviderError, ConfigError, OSError, ValueError):
            return None
        return InstrumentQuoteDTO(
            instrument_id=quote.instrument_id,
            last_price=quote.last_price,
            change_pct=change_pct,
            as_of=quote.ts,
            source="kite_live",
        )

    def _persisted_quote(self, instrument_id: str) -> InstrumentQuoteDTO | None:
        if self._repo is None:
            return None
        candidates = [instrument_id]
        if instrument_id.startswith("NSE:"):
            candidates.append(instrument_id.removeprefix("NSE:"))
        elif ":" not in instrument_id:
            candidates.append(f"NSE:{instrument_id}")
        for iid in candidates:
            quotes = self._repo.get_quotes(iid)
            if not quotes:
                continue
            latest = quotes[-1]
            if latest.last_price <= 0:
                continue
            return InstrumentQuoteDTO(
                instrument_id=latest.instrument_id,
                last_price=latest.last_price,
                change_pct=None,
                as_of=latest.ts,
                source="persisted",
            )
        return None

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

    def _prior_session_snapshot(self, snapshot_ts: datetime) -> MarketSnapshot | None:
        """Latest snapshot before the current snapshot's local trading day."""
        if self._repo is None:
            return None
        day_start = snapshot_ts.replace(hour=0, minute=0, second=0, microsecond=0)
        return self._repo.get_latest_snapshot_before(day_start)
