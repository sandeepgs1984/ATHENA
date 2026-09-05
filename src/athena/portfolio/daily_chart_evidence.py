"""Daily-chart evidence foundation for future Portfolio Review intelligence.

PS-P10B is evidence-only. These objects do not populate My Portfolio Review
Status, Review Guidance, Support/Exit, Targets, existing Status, Conviction,
Trend, Setup, Next Action, or any Decision/TradePlan output.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from enum import Enum, unique
from zoneinfo import ZoneInfo

from athena.domain.enums import Timeframe
from athena.domain.market import Candle
from athena.indicators.calculations import atr_series, rsi, volume_ma

DAILY_CHART_EVIDENCE_VERSION = "portfolio-daily-chart-evidence-v0"
SUPERTREND_VERSION = "supertrend-10-3-athena-v0"
SUPERTREND_ATR_PERIOD = 10
SUPERTREND_MULTIPLIER = Decimal("3")
RSI_REVIEW_PERIOD = 14
VOLUME_MA_PERIOD = 20


@unique
class DailyChartEvidenceReason(str, Enum):
    OK = "OK"
    D1_EVIDENCE_UNAVAILABLE = "D1_EVIDENCE_UNAVAILABLE"
    D1_EVIDENCE_INCOHERENT = "D1_EVIDENCE_INCOHERENT"
    INSUFFICIENT_HISTORY = "INSUFFICIENT_HISTORY"
    ACCEPTED_SESSION_MISMATCH = "ACCEPTED_SESSION_MISMATCH"
    EXPECTED_SESSION_MISMATCH = "EXPECTED_SESSION_MISMATCH"
    STRUCTURAL_LEVEL_METHODOLOGY_NOT_FROZEN = (
        "STRUCTURAL_LEVEL_METHODOLOGY_NOT_FROZEN"
    )


@unique
class SuperTrendDirection(str, Enum):
    BULLISH = "BULLISH"
    BEARISH = "BEARISH"


@unique
class StructuralLevelKind(str, Enum):
    SUPPORT_CANDIDATE = "SUPPORT_CANDIDATE"
    RESISTANCE_CANDIDATE = "RESISTANCE_CANDIDATE"


@dataclass(frozen=True, slots=True)
class DailyChartEvidenceProvenance:
    instrument_id: str
    timeframe: Timeframe
    as_of: datetime | None
    accepted_price_as_of: datetime | None
    expected_analysis_as_of: datetime | None
    first_d1_session: datetime | None
    latest_d1_session: datetime | None
    candles_used: int
    source_count: int
    version: str = DAILY_CHART_EVIDENCE_VERSION


@dataclass(frozen=True, slots=True)
class SuperTrendEvidence:
    direction: SuperTrendDirection | None
    reason: DailyChartEvidenceReason
    provenance: DailyChartEvidenceProvenance
    latest_close: Decimal | None
    supertrend: Decimal | None
    final_upper_band: Decimal | None
    final_lower_band: Decimal | None
    atr: Decimal | None
    atr_period: int
    multiplier: Decimal
    flipped_on_latest: bool
    is_coherent: bool
    version: str = SUPERTREND_VERSION


@dataclass(frozen=True, slots=True)
class RsiReviewEvidence:
    value: Decimal | None
    reason: DailyChartEvidenceReason
    provenance: DailyChartEvidenceProvenance
    period: int
    is_coherent: bool


@dataclass(frozen=True, slots=True)
class VolumeReviewEvidence:
    latest_volume: int | None
    volume_ma: Decimal | None
    reason: DailyChartEvidenceReason
    provenance: DailyChartEvidenceProvenance
    period: int
    is_coherent: bool


@dataclass(frozen=True, slots=True)
class AthRollingHighEvidence:
    latest_high: Decimal | None
    latest_close: Decimal | None
    prior_available_history_high: Decimal | None
    prior_available_history_high_session: datetime | None
    latest_high_exceeds_prior_history: bool | None
    latest_close_above_prior_history_high: bool | None
    rolling_sessions: int | None
    prior_rolling_high: Decimal | None
    prior_rolling_high_session: datetime | None
    latest_high_exceeds_prior_rolling: bool | None
    latest_close_above_prior_rolling_high: bool | None
    adjusted_history: bool | None
    reason: DailyChartEvidenceReason
    provenance: DailyChartEvidenceProvenance
    is_coherent: bool


@dataclass(frozen=True, slots=True)
class StructuralLevelCandidate:
    kind: StructuralLevelKind
    lower: Decimal
    upper: Decimal
    source_sessions: tuple[datetime, ...]
    method: str


@dataclass(frozen=True, slots=True)
class StructuralLevelCandidateEvidence:
    candidates: tuple[StructuralLevelCandidate, ...]
    reason: DailyChartEvidenceReason
    provenance: DailyChartEvidenceProvenance
    is_coherent: bool


@dataclass(frozen=True, slots=True)
class _PreparedD1:
    candles: tuple[Candle, ...]
    provenance: DailyChartEvidenceProvenance
    reason: DailyChartEvidenceReason
    is_coherent: bool


class DailyChartEvidenceEngine:
    """Pure D1 evidence engine for future Daily Chart Portfolio Review."""

    def supertrend_10_3(
        self,
        *,
        instrument_id: str,
        candles: Sequence[Candle],
        accepted_price_as_of: datetime | None,
        expected_analysis_as_of: datetime | None,
        market_timezone: ZoneInfo,
    ) -> SuperTrendEvidence:
        prepared = self._prepare_d1(
            instrument_id=instrument_id,
            candles=candles,
            accepted_price_as_of=accepted_price_as_of,
            expected_analysis_as_of=expected_analysis_as_of,
            market_timezone=market_timezone,
        )
        if not prepared.is_coherent:
            return self._empty_supertrend(prepared)
        if len(prepared.candles) < SUPERTREND_ATR_PERIOD + 1:
            return self._empty_supertrend(
                self._with_reason(prepared, DailyChartEvidenceReason.INSUFFICIENT_HISTORY)
            )

        states = self._supertrend_states(prepared.candles)
        if not states:
            return self._empty_supertrend(
                self._with_reason(prepared, DailyChartEvidenceReason.INSUFFICIENT_HISTORY)
            )

        latest = states[-1]
        previous = states[-2] if len(states) > 1 else None
        flipped = previous is not None and latest.direction is not previous.direction
        return SuperTrendEvidence(
            direction=latest.direction,
            reason=DailyChartEvidenceReason.OK,
            provenance=prepared.provenance,
            latest_close=prepared.candles[-1].close,
            supertrend=latest.supertrend,
            final_upper_band=latest.final_upper_band,
            final_lower_band=latest.final_lower_band,
            atr=latest.atr,
            atr_period=SUPERTREND_ATR_PERIOD,
            multiplier=SUPERTREND_MULTIPLIER,
            flipped_on_latest=flipped,
            is_coherent=True,
        )

    def rsi14(
        self,
        *,
        instrument_id: str,
        candles: Sequence[Candle],
        accepted_price_as_of: datetime | None,
        expected_analysis_as_of: datetime | None,
        market_timezone: ZoneInfo,
    ) -> RsiReviewEvidence:
        prepared = self._prepare_d1(
            instrument_id=instrument_id,
            candles=candles,
            accepted_price_as_of=accepted_price_as_of,
            expected_analysis_as_of=expected_analysis_as_of,
            market_timezone=market_timezone,
        )
        if not prepared.is_coherent:
            return RsiReviewEvidence(
                value=None,
                reason=prepared.reason,
                provenance=prepared.provenance,
                period=RSI_REVIEW_PERIOD,
                is_coherent=False,
            )
        value = rsi([candle.close for candle in prepared.candles], RSI_REVIEW_PERIOD)
        if value is None:
            return RsiReviewEvidence(
                value=None,
                reason=DailyChartEvidenceReason.INSUFFICIENT_HISTORY,
                provenance=prepared.provenance,
                period=RSI_REVIEW_PERIOD,
                is_coherent=False,
            )
        return RsiReviewEvidence(
            value=value,
            reason=DailyChartEvidenceReason.OK,
            provenance=prepared.provenance,
            period=RSI_REVIEW_PERIOD,
            is_coherent=True,
        )

    def volume_review(
        self,
        *,
        instrument_id: str,
        candles: Sequence[Candle],
        accepted_price_as_of: datetime | None,
        expected_analysis_as_of: datetime | None,
        market_timezone: ZoneInfo,
    ) -> VolumeReviewEvidence:
        prepared = self._prepare_d1(
            instrument_id=instrument_id,
            candles=candles,
            accepted_price_as_of=accepted_price_as_of,
            expected_analysis_as_of=expected_analysis_as_of,
            market_timezone=market_timezone,
        )
        if not prepared.is_coherent:
            return VolumeReviewEvidence(
                latest_volume=None,
                volume_ma=None,
                reason=prepared.reason,
                provenance=prepared.provenance,
                period=VOLUME_MA_PERIOD,
                is_coherent=False,
            )
        ma = volume_ma([candle.volume for candle in prepared.candles], VOLUME_MA_PERIOD)
        if ma is None:
            return VolumeReviewEvidence(
                latest_volume=prepared.candles[-1].volume if prepared.candles else None,
                volume_ma=None,
                reason=DailyChartEvidenceReason.INSUFFICIENT_HISTORY,
                provenance=prepared.provenance,
                period=VOLUME_MA_PERIOD,
                is_coherent=False,
            )
        return VolumeReviewEvidence(
            latest_volume=prepared.candles[-1].volume,
            volume_ma=ma,
            reason=DailyChartEvidenceReason.OK,
            provenance=prepared.provenance,
            period=VOLUME_MA_PERIOD,
            is_coherent=True,
        )

    def ath_rolling_high(
        self,
        *,
        instrument_id: str,
        candles: Sequence[Candle],
        accepted_price_as_of: datetime | None,
        expected_analysis_as_of: datetime | None,
        market_timezone: ZoneInfo,
        rolling_sessions: int | None = None,
    ) -> AthRollingHighEvidence:
        if rolling_sessions is not None and rolling_sessions < 2:
            raise ValueError("rolling_sessions must be >= 2 when supplied")
        prepared = self._prepare_d1(
            instrument_id=instrument_id,
            candles=candles,
            accepted_price_as_of=accepted_price_as_of,
            expected_analysis_as_of=expected_analysis_as_of,
            market_timezone=market_timezone,
        )
        if not prepared.is_coherent:
            return self._empty_ath(prepared, rolling_sessions)
        if len(prepared.candles) < 2:
            return self._empty_ath(
                self._with_reason(prepared, DailyChartEvidenceReason.INSUFFICIENT_HISTORY),
                rolling_sessions,
            )

        latest = prepared.candles[-1]
        prior_high_candle = max(prepared.candles[:-1], key=lambda candle: candle.high)
        rolling_high_candle: Candle | None = None
        if rolling_sessions is not None and len(prepared.candles) >= rolling_sessions:
            rolling_prior = prepared.candles[-rolling_sessions:-1]
            rolling_high_candle = max(rolling_prior, key=lambda candle: candle.high)

        prior_high = prior_high_candle.high
        rolling_high = rolling_high_candle.high if rolling_high_candle else None
        return AthRollingHighEvidence(
            latest_high=latest.high,
            latest_close=latest.close,
            prior_available_history_high=prior_high,
            prior_available_history_high_session=prior_high_candle.ts_open,
            latest_high_exceeds_prior_history=latest.high > prior_high,
            latest_close_above_prior_history_high=latest.close > prior_high,
            rolling_sessions=rolling_sessions,
            prior_rolling_high=rolling_high,
            prior_rolling_high_session=(
                rolling_high_candle.ts_open if rolling_high_candle else None
            ),
            latest_high_exceeds_prior_rolling=(
                latest.high > rolling_high if rolling_high is not None else None
            ),
            latest_close_above_prior_rolling_high=(
                latest.close > rolling_high if rolling_high is not None else None
            ),
            adjusted_history=all(candle.adjusted for candle in prepared.candles),
            reason=DailyChartEvidenceReason.OK,
            provenance=prepared.provenance,
            is_coherent=True,
        )

    def structural_level_candidates(
        self,
        *,
        instrument_id: str,
        candles: Sequence[Candle],
        accepted_price_as_of: datetime | None,
        expected_analysis_as_of: datetime | None,
        market_timezone: ZoneInfo,
    ) -> StructuralLevelCandidateEvidence:
        prepared = self._prepare_d1(
            instrument_id=instrument_id,
            candles=candles,
            accepted_price_as_of=accepted_price_as_of,
            expected_analysis_as_of=expected_analysis_as_of,
            market_timezone=market_timezone,
        )
        reason = (
            prepared.reason
            if not prepared.is_coherent
            else DailyChartEvidenceReason.STRUCTURAL_LEVEL_METHODOLOGY_NOT_FROZEN
        )
        return StructuralLevelCandidateEvidence(
            candidates=(),
            reason=reason,
            provenance=prepared.provenance,
            is_coherent=prepared.is_coherent,
        )

    def _prepare_d1(
        self,
        *,
        instrument_id: str,
        candles: Sequence[Candle],
        accepted_price_as_of: datetime | None,
        expected_analysis_as_of: datetime | None,
        market_timezone: ZoneInfo,
    ) -> _PreparedD1:
        if accepted_price_as_of is not None and accepted_price_as_of.tzinfo is None:
            raise ValueError("accepted_price_as_of must be timezone-aware")
        if expected_analysis_as_of is not None and expected_analysis_as_of.tzinfo is None:
            raise ValueError("expected_analysis_as_of must be timezone-aware")

        as_of = expected_analysis_as_of or accepted_price_as_of
        cutoff_session = as_of.astimezone(market_timezone).date() if as_of else None
        allowed = [
            candle
            for candle in candles
            if cutoff_session is None
            or candle.ts_open.astimezone(market_timezone).date() <= cutoff_session
        ]
        ordered = tuple(sorted(allowed, key=lambda candle: candle.ts_open))
        latest = ordered[-1].ts_open if ordered else None
        provenance = DailyChartEvidenceProvenance(
            instrument_id=instrument_id,
            timeframe=Timeframe.D1,
            as_of=as_of,
            accepted_price_as_of=accepted_price_as_of,
            expected_analysis_as_of=expected_analysis_as_of,
            first_d1_session=ordered[0].ts_open if ordered else None,
            latest_d1_session=latest,
            candles_used=len(ordered),
            source_count=len(candles),
        )

        if not ordered:
            return _PreparedD1(
                candles=ordered,
                provenance=provenance,
                reason=DailyChartEvidenceReason.D1_EVIDENCE_UNAVAILABLE,
                is_coherent=False,
            )
        if any(candle.instrument_id != instrument_id for candle in ordered):
            return _PreparedD1(
                candles=ordered,
                provenance=provenance,
                reason=DailyChartEvidenceReason.D1_EVIDENCE_INCOHERENT,
                is_coherent=False,
            )
        if any(candle.timeframe is not Timeframe.D1 for candle in ordered):
            return _PreparedD1(
                candles=ordered,
                provenance=provenance,
                reason=DailyChartEvidenceReason.D1_EVIDENCE_INCOHERENT,
                is_coherent=False,
            )

        latest = ordered[-1].ts_open
        latest_session = latest.astimezone(market_timezone).date()
        if accepted_price_as_of is not None:
            accepted_session = accepted_price_as_of.astimezone(market_timezone).date()
            if latest_session != accepted_session:
                return _PreparedD1(
                    candles=ordered,
                    provenance=provenance,
                    reason=DailyChartEvidenceReason.ACCEPTED_SESSION_MISMATCH,
                    is_coherent=False,
                )
        if expected_analysis_as_of is not None:
            expected_session = expected_analysis_as_of.astimezone(market_timezone).date()
            if latest_session != expected_session:
                return _PreparedD1(
                    candles=ordered,
                    provenance=provenance,
                    reason=DailyChartEvidenceReason.EXPECTED_SESSION_MISMATCH,
                    is_coherent=False,
                )

        return _PreparedD1(
            candles=ordered,
            provenance=provenance,
            reason=DailyChartEvidenceReason.OK,
            is_coherent=True,
        )

    def _empty_supertrend(self, prepared: _PreparedD1) -> SuperTrendEvidence:
        return SuperTrendEvidence(
            direction=None,
            reason=prepared.reason,
            provenance=prepared.provenance,
            latest_close=None,
            supertrend=None,
            final_upper_band=None,
            final_lower_band=None,
            atr=None,
            atr_period=SUPERTREND_ATR_PERIOD,
            multiplier=SUPERTREND_MULTIPLIER,
            flipped_on_latest=False,
            is_coherent=False,
        )

    def _empty_ath(
        self,
        prepared: _PreparedD1,
        rolling_sessions: int | None,
    ) -> AthRollingHighEvidence:
        return AthRollingHighEvidence(
            latest_high=None,
            latest_close=None,
            prior_available_history_high=None,
            prior_available_history_high_session=None,
            latest_high_exceeds_prior_history=None,
            latest_close_above_prior_history_high=None,
            rolling_sessions=rolling_sessions,
            prior_rolling_high=None,
            prior_rolling_high_session=None,
            latest_high_exceeds_prior_rolling=None,
            latest_close_above_prior_rolling_high=None,
            adjusted_history=None,
            reason=prepared.reason,
            provenance=prepared.provenance,
            is_coherent=False,
        )

    def _with_reason(
        self,
        prepared: _PreparedD1,
        reason: DailyChartEvidenceReason,
    ) -> _PreparedD1:
        return _PreparedD1(
            candles=prepared.candles,
            provenance=prepared.provenance,
            reason=reason,
            is_coherent=False,
        )

    def _supertrend_states(
        self,
        candles: Sequence[Candle],
    ) -> list[_SuperTrendState]:
        atrs = atr_series(candles, SUPERTREND_ATR_PERIOD)
        if not atrs:
            return []

        states: list[_SuperTrendState] = []
        start_index = SUPERTREND_ATR_PERIOD
        for offset, atr_value in enumerate(atrs):
            index = start_index + offset
            candle = candles[index]
            hl2 = (candle.high + candle.low) / Decimal(2)
            basic_upper = hl2 + SUPERTREND_MULTIPLIER * atr_value
            basic_lower = hl2 - SUPERTREND_MULTIPLIER * atr_value
            if not states:
                direction = (
                    SuperTrendDirection.BULLISH
                    if candle.close >= hl2
                    else SuperTrendDirection.BEARISH
                )
                final_upper = basic_upper
                final_lower = basic_lower
            else:
                previous = states[-1]
                previous_close = candles[index - 1].close
                final_upper = (
                    basic_upper
                    if basic_upper < previous.final_upper_band
                    or previous_close > previous.final_upper_band
                    else previous.final_upper_band
                )
                final_lower = (
                    basic_lower
                    if basic_lower > previous.final_lower_band
                    or previous_close < previous.final_lower_band
                    else previous.final_lower_band
                )
                if previous.direction is SuperTrendDirection.BULLISH:
                    direction = (
                        SuperTrendDirection.BEARISH
                        if candle.close < final_lower
                        else SuperTrendDirection.BULLISH
                    )
                else:
                    direction = (
                        SuperTrendDirection.BULLISH
                        if candle.close > final_upper
                        else SuperTrendDirection.BEARISH
                    )
            supertrend = (
                final_lower
                if direction is SuperTrendDirection.BULLISH
                else final_upper
            )
            states.append(
                _SuperTrendState(
                    direction=direction,
                    supertrend=supertrend,
                    final_upper_band=final_upper,
                    final_lower_band=final_lower,
                    atr=atr_value,
                )
            )
        return states


@dataclass(frozen=True, slots=True)
class _SuperTrendState:
    direction: SuperTrendDirection
    supertrend: Decimal
    final_upper_band: Decimal
    final_lower_band: Decimal
    atr: Decimal
