"""Thin read-only adapter over pure Portfolio D1 calculations.

SI-P1 may run these for held and non-held symbols because they consume only
D1 candles. Holding-oriented Daily Review / Next Action / EXIT guidance is
never produced here.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from datetime import date, datetime
from decimal import Decimal
from zoneinfo import ZoneInfo

from athena.domain.market import Candle
from athena.portfolio.daily_chart_evidence import DailyChartEvidenceEngine
from athena.portfolio.structural_review import (
    PortfolioStructuralReviewEngine,
    StructuralZone,
)
from athena.portfolio.trend_adapter import PortfolioTrendAdapter, PortfolioTrendEvidence

SI_D1_ADAPTER_VERSION = "si-d1-adapter-v0"


@dataclass(frozen=True, slots=True)
class SiStructuralZone:
    lower: Decimal
    upper: Decimal
    role: str
    lineage: str = "PORTFOLIO_STRUCTURAL_REVIEW"


@dataclass(frozen=True, slots=True)
class SiD1AdapterResult:
    latest_session: datetime | None
    latest_open: Decimal | None
    latest_high: Decimal | None
    latest_low: Decimal | None
    latest_close: Decimal | None
    latest_volume: int | None
    adjusted: bool | None
    candles_used: int
    rsi_value: Decimal | None
    rsi_reason: str
    rsi_coherent: bool
    supertrend_direction: str | None
    supertrend_value: Decimal | None
    supertrend_reason: str
    supertrend_coherent: bool
    supertrend_version: str
    volume_latest: int | None
    volume_ma: Decimal | None
    volume_reason: str
    volume_coherent: bool
    available_history_high: Decimal | None
    available_history_high_session: datetime | None
    latest_high_exceeds_prior_history: bool | None
    latest_close_above_prior_history_high: bool | None
    ath_reason: str
    ath_coherent: bool
    ath_adjusted_history: bool | None
    symbol_trend: str | None
    symbol_trend_reason: str
    symbol_trend_coherent: bool
    fast_sma: Decimal | None
    slow_sma: Decimal | None
    support_1: SiStructuralZone | None
    major_support: SiStructuralZone | None
    review_trigger: SiStructuralZone | None
    target_1: SiStructuralZone | None
    target_2: SiStructuralZone | None
    target_3: SiStructuralZone | None
    structural_reason_codes: tuple[str, ...]
    structural_coherent: bool
    expected_session: date | None
    version: str = SI_D1_ADAPTER_VERSION


def _zone(value: StructuralZone | None) -> SiStructuralZone | None:
    if value is None:
        return None
    return SiStructuralZone(lower=value.lower, upper=value.upper, role=value.role.value)


class SymbolIntelligenceD1Adapter:
    """Compose reusable D1 measurements without Portfolio HOLD semantics."""

    def __init__(
        self,
        *,
        evidence_engine: DailyChartEvidenceEngine | None = None,
        structural_engine: PortfolioStructuralReviewEngine | None = None,
        trend_adapter: PortfolioTrendAdapter | None = None,
    ) -> None:
        self._evidence = evidence_engine or DailyChartEvidenceEngine()
        self._structural = structural_engine or PortfolioStructuralReviewEngine()
        self._trend = trend_adapter

    def evaluate(
        self,
        *,
        instrument_id: str,
        candles: Sequence[Candle],
        market_timezone: ZoneInfo,
        expected_session: date | None,
    ) -> SiD1AdapterResult:
        if not candles:
            return self._empty(expected_session)

        ordered = tuple(sorted(candles, key=lambda candle: candle.ts_open))
        latest = ordered[-1]
        session_as_of = latest.ts_open

        rsi = self._evidence.rsi14(
            instrument_id=instrument_id,
            candles=ordered,
            accepted_price_as_of=session_as_of,
            expected_analysis_as_of=session_as_of,
            market_timezone=market_timezone,
        )
        supertrend = self._evidence.supertrend_10_3(
            instrument_id=instrument_id,
            candles=ordered,
            accepted_price_as_of=session_as_of,
            expected_analysis_as_of=session_as_of,
            market_timezone=market_timezone,
        )
        volume = self._evidence.volume_review(
            instrument_id=instrument_id,
            candles=ordered,
            accepted_price_as_of=session_as_of,
            expected_analysis_as_of=session_as_of,
            market_timezone=market_timezone,
        )
        ath = self._evidence.ath_rolling_high(
            instrument_id=instrument_id,
            candles=ordered,
            accepted_price_as_of=session_as_of,
            expected_analysis_as_of=session_as_of,
            market_timezone=market_timezone,
        )

        trend: PortfolioTrendEvidence | None = None
        if self._trend is not None:
            trend = self._trend.classify_candles(
                instrument_id=instrument_id,
                candles=ordered,
                accepted_price_as_of=session_as_of,
                expected_analysis_as_of=session_as_of,
                market_timezone=market_timezone,
            )

        trend_label = trend.trend.value if trend is not None and trend.trend is not None else None
        structural = self._structural.resolve(
            instrument_id=instrument_id,
            candles=ordered,
            accepted_price_as_of=session_as_of,
            expected_analysis_as_of=session_as_of,
            market_timezone=market_timezone,
            supertrend=supertrend,
            current_price=latest.close,
            trend_label=trend_label,
            daily_review_status=None,
        )

        return SiD1AdapterResult(
            latest_session=latest.ts_open,
            latest_open=latest.open,
            latest_high=latest.high,
            latest_low=latest.low,
            latest_close=latest.close,
            latest_volume=latest.volume,
            adjusted=latest.adjusted,
            candles_used=len(ordered),
            rsi_value=rsi.value,
            rsi_reason=rsi.reason.value,
            rsi_coherent=rsi.is_coherent,
            supertrend_direction=(
                supertrend.direction.value if supertrend.direction is not None else None
            ),
            supertrend_value=supertrend.supertrend,
            supertrend_reason=supertrend.reason.value,
            supertrend_coherent=supertrend.is_coherent,
            supertrend_version=supertrend.version,
            volume_latest=volume.latest_volume,
            volume_ma=volume.volume_ma,
            volume_reason=volume.reason.value,
            volume_coherent=volume.is_coherent,
            available_history_high=ath.prior_available_history_high,
            available_history_high_session=ath.prior_available_history_high_session,
            latest_high_exceeds_prior_history=ath.latest_high_exceeds_prior_history,
            latest_close_above_prior_history_high=ath.latest_close_above_prior_history_high,
            ath_reason=ath.reason.value,
            ath_coherent=ath.is_coherent,
            ath_adjusted_history=ath.adjusted_history,
            symbol_trend=trend_label,
            symbol_trend_reason=trend.reason.value if trend is not None else "TREND_ADAPTER_UNAVAILABLE",
            symbol_trend_coherent=bool(trend is not None and trend.is_coherent),
            fast_sma=trend.fast_sma if trend is not None else None,
            slow_sma=trend.slow_sma if trend is not None else None,
            support_1=_zone(structural.support_1),
            major_support=_zone(structural.major_support),
            review_trigger=_zone(structural.review_trigger),
            target_1=_zone(structural.target_1),
            target_2=_zone(structural.target_2),
            target_3=_zone(structural.target_3),
            structural_reason_codes=tuple(code.value for code in structural.reason_codes),
            structural_coherent=structural.is_coherent,
            expected_session=expected_session,
        )

    def _empty(self, expected_session: date | None) -> SiD1AdapterResult:
        return SiD1AdapterResult(
            latest_session=None,
            latest_open=None,
            latest_high=None,
            latest_low=None,
            latest_close=None,
            latest_volume=None,
            adjusted=None,
            candles_used=0,
            rsi_value=None,
            rsi_reason="D1_EVIDENCE_UNAVAILABLE",
            rsi_coherent=False,
            supertrend_direction=None,
            supertrend_value=None,
            supertrend_reason="D1_EVIDENCE_UNAVAILABLE",
            supertrend_coherent=False,
            supertrend_version="supertrend-10-3-athena-v0",
            volume_latest=None,
            volume_ma=None,
            volume_reason="D1_EVIDENCE_UNAVAILABLE",
            volume_coherent=False,
            available_history_high=None,
            available_history_high_session=None,
            latest_high_exceeds_prior_history=None,
            latest_close_above_prior_history_high=None,
            ath_reason="D1_EVIDENCE_UNAVAILABLE",
            ath_coherent=False,
            ath_adjusted_history=None,
            symbol_trend=None,
            symbol_trend_reason="D1_EVIDENCE_UNAVAILABLE",
            symbol_trend_coherent=False,
            fast_sma=None,
            slow_sma=None,
            support_1=None,
            major_support=None,
            review_trigger=None,
            target_1=None,
            target_2=None,
            target_3=None,
            structural_reason_codes=("STRUCTURAL_EVIDENCE_UNAVAILABLE",),
            structural_coherent=False,
            expected_session=expected_session,
        )
