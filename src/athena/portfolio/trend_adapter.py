"""Portfolio D1 Trend adapter (PS-P8C).

Adapts ATHENA's approved Regime SMA20/SMA50 D1 trend rule to one holding's own
D1 candles. This module does not consume market Regime labels, Decisions,
Conviction, EntryQualification, intraday evidence, or providers.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from enum import Enum, unique
from pathlib import Path
from zoneinfo import ZoneInfo

from athena.config.loader import load_config
from athena.data.store.repository import SqliteRepository
from athena.domain.enums import Timeframe
from athena.domain.market import Candle
from athena.indicators.calculations import sma


@unique
class PortfolioTrend(str, Enum):
    UPTREND = "UPTREND"
    DOWNTREND = "DOWNTREND"
    MIXED = "MIXED"


@unique
class PortfolioTrendReason(str, Enum):
    UP_FROM_D1_SMA_STRUCTURE = "TREND_UP_FROM_D1_SMA_STRUCTURE"
    DOWN_FROM_D1_SMA_STRUCTURE = "TREND_DOWN_FROM_D1_SMA_STRUCTURE"
    MIXED_FROM_D1_SMA_STRUCTURE = "TREND_MIXED_FROM_D1_SMA_STRUCTURE"
    D1_EVIDENCE_UNAVAILABLE = "TREND_D1_EVIDENCE_UNAVAILABLE"
    D1_EVIDENCE_INCOHERENT = "TREND_D1_EVIDENCE_INCOHERENT"


@dataclass(frozen=True, slots=True)
class PortfolioTrendEvidence:
    trend: PortfolioTrend | None
    reason: PortfolioTrendReason
    instrument_id: str
    d1_session: datetime | None
    fast_sma: Decimal | None
    slow_sma: Decimal | None
    close: Decimal | None
    candles_used: int
    fast_period: int
    slow_period: int
    is_coherent: bool


class PortfolioTrendAdapter:
    """Resolve optional D1 Trend evidence for one Portfolio holding."""

    def __init__(
        self,
        repo: SqliteRepository,
        *,
        config_dir: Path | str = "config",
    ) -> None:
        self._repo = repo
        regime = load_config(Path(config_dir)).regime
        self._fast_period = regime.trend_ma_fast
        self._slow_period = regime.trend_ma_slow

    def resolve(
        self,
        *,
        instrument_id: str,
        accepted_price_as_of: datetime | None,
        expected_analysis_as_of: datetime | None,
        market_timezone: ZoneInfo,
    ) -> PortfolioTrendEvidence:
        if accepted_price_as_of is None:
            return self._unavailable(instrument_id, None, candles_used=0)
        if accepted_price_as_of.tzinfo is None:
            raise ValueError("accepted_price_as_of must be timezone-aware")
        if expected_analysis_as_of is not None and expected_analysis_as_of.tzinfo is None:
            raise ValueError("expected_analysis_as_of must be timezone-aware")

        cutoff = expected_analysis_as_of or accepted_price_as_of
        candles = self._repo.list_candles_recent(
            instrument_id,
            Timeframe.D1,
            limit=self._slow_period,
            as_of=cutoff,
        )
        return self.classify_candles(
            instrument_id=instrument_id,
            candles=candles,
            accepted_price_as_of=accepted_price_as_of,
            expected_analysis_as_of=expected_analysis_as_of,
            market_timezone=market_timezone,
        )

    def classify_candles(
        self,
        *,
        instrument_id: str,
        candles: Sequence[Candle],
        accepted_price_as_of: datetime | None,
        expected_analysis_as_of: datetime | None,
        market_timezone: ZoneInfo,
    ) -> PortfolioTrendEvidence:
        if accepted_price_as_of is None:
            return self._unavailable(instrument_id, None, candles_used=len(candles))
        if accepted_price_as_of.tzinfo is None:
            raise ValueError("accepted_price_as_of must be timezone-aware")
        if expected_analysis_as_of is not None and expected_analysis_as_of.tzinfo is None:
            raise ValueError("expected_analysis_as_of must be timezone-aware")

        cutoff_session = (expected_analysis_as_of or accepted_price_as_of).astimezone(
            market_timezone
        ).date()
        allowed = [
            candle
            for candle in candles
            if candle.ts_open.astimezone(market_timezone).date() <= cutoff_session
        ]
        ordered = sorted(allowed, key=lambda candle: candle.ts_open)

        if any(candle.instrument_id != instrument_id for candle in ordered):
            return self._incoherent(instrument_id, ordered[-1].ts_open, len(ordered))
        if any(candle.timeframe is not Timeframe.D1 for candle in ordered):
            return self._incoherent(instrument_id, ordered[-1].ts_open, len(ordered))

        if len(ordered) < self._slow_period:
            latest_ts = ordered[-1].ts_open if ordered else None
            return self._unavailable(instrument_id, latest_ts, candles_used=len(ordered))

        ordered = ordered[-self._slow_period :]
        latest = ordered[-1]
        expected_session = (expected_analysis_as_of or accepted_price_as_of).astimezone(
            market_timezone
        ).date()
        accepted_session = accepted_price_as_of.astimezone(market_timezone).date()
        latest_session = latest.ts_open.astimezone(market_timezone).date()
        if latest_session != accepted_session or latest_session != expected_session:
            return self._incoherent(instrument_id, latest.ts_open, len(ordered))

        closes = [candle.close for candle in ordered]
        fast_sma = sma(closes, self._fast_period)
        slow_sma = sma(closes, self._slow_period)
        if fast_sma is None or slow_sma is None:
            return self._unavailable(instrument_id, latest.ts_open, candles_used=len(ordered))

        close = latest.close
        if fast_sma > slow_sma and close >= slow_sma:
            trend = PortfolioTrend.UPTREND
            reason = PortfolioTrendReason.UP_FROM_D1_SMA_STRUCTURE
        elif fast_sma < slow_sma and close <= slow_sma:
            trend = PortfolioTrend.DOWNTREND
            reason = PortfolioTrendReason.DOWN_FROM_D1_SMA_STRUCTURE
        else:
            trend = PortfolioTrend.MIXED
            reason = PortfolioTrendReason.MIXED_FROM_D1_SMA_STRUCTURE

        return PortfolioTrendEvidence(
            trend=trend,
            reason=reason,
            instrument_id=instrument_id,
            d1_session=latest.ts_open,
            fast_sma=fast_sma,
            slow_sma=slow_sma,
            close=close,
            candles_used=len(ordered),
            fast_period=self._fast_period,
            slow_period=self._slow_period,
            is_coherent=True,
        )

    def _unavailable(
        self,
        instrument_id: str,
        d1_session: datetime | None,
        *,
        candles_used: int,
    ) -> PortfolioTrendEvidence:
        return PortfolioTrendEvidence(
            trend=None,
            reason=PortfolioTrendReason.D1_EVIDENCE_UNAVAILABLE,
            instrument_id=instrument_id,
            d1_session=d1_session,
            fast_sma=None,
            slow_sma=None,
            close=None,
            candles_used=candles_used,
            fast_period=self._fast_period,
            slow_period=self._slow_period,
            is_coherent=False,
        )

    def _incoherent(
        self,
        instrument_id: str,
        d1_session: datetime | None,
        candles_used: int,
    ) -> PortfolioTrendEvidence:
        return PortfolioTrendEvidence(
            trend=None,
            reason=PortfolioTrendReason.D1_EVIDENCE_INCOHERENT,
            instrument_id=instrument_id,
            d1_session=d1_session,
            fast_sma=None,
            slow_sma=None,
            close=None,
            candles_used=candles_used,
            fast_period=self._fast_period,
            slow_period=self._slow_period,
            is_coherent=False,
        )
