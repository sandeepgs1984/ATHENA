"""Intraday Analytics Engine (ID-2, corrected ID-2.1).

Formalizes intraday evidence ATHENA's live `ScoringEngine` already consumes
(VWAP relation, 5m/15m confluence direction) into typed, explainable
artifacts — computing nothing new. This is deliberate: "one authoritative
calculation" (VWAP: `indicators.calculations.vwap`; confluence direction:
`ScoringEngine`'s own `ConfluenceInputs`, produced by `owner_validation.py`'s
`ind_stage`) means this engine reads the SAME `IndicatorResult`/
`ConfluenceInputs` objects scoring already received this cycle, rather than
recomputing them on a possibly-different candle window — recomputing would
create a second, potentially-diverging "VWAP relation" in the system.

ID-2.1 closed the one real gap this design had: `ind_stage` itself now
filters its 5m/15m candle inputs through `athena.session.completed_candles()`
(ID-1's `ts_open + duration <= as_of` rule) before computing VWAP/confluence
at all — so the formalized values here are both object-identical to what
`ScoringEngine` used AND guaranteed completed-candle-only, not merely
"whatever `ind_stage` happened to compute." `SessionContext.data_quality`
remains the honest, independent signal about whether the underlying
intraday data is trustworthy, surfaced on every `IntradaySignalSet`
alongside the (unchanged) formalized values.

ID-3 adds `OpeningRangeEvidence` (OR15/OR30,
`athena.intraday.opening_range_engine.OpeningRangeEngine`) as two more
typed evidence fields on `IntradaySignalSet` — a genuinely new computation
(not a formalization of an existing scoring input), but held to the exact
same completed-candle and "no scoring/Decision influence" rules.

ID-5D adds `relative_volume` (`RelativeVolumeContext`,
`athena.intraday.relative_volume_engine.RelativeVolumeEngine`) — computed
and passed in by the caller exactly like `relative_strength`/`gap`, never
recomputed here.

No I/O, no clock reads — as_of and every input object are injected by the
caller, exactly like `ScoringEngine`/`ConfidenceEngine`/every other engine.
"""

from __future__ import annotations

from datetime import date, datetime

from athena.domain.enums import Timeframe
from athena.indicators.models import IndicatorResult, IndicatorStatus
from athena.intraday.gap_models import GapContext
from athena.intraday.models import (
    IntradaySignalSet,
    IntradayTrendContext,
    IntradayTrendLabel,
    TimeframeTrendEvidence,
    VwapEvidence,
    VwapRelation,
)
from athena.intraday.opening_range_models import OpeningRangeEvidence
from athena.intraday.relative_strength_models import RelativeStrengthContext
from athena.intraday.relative_volume_models import RelativeVolumeContext
from athena.scoring.models import ConfluenceInputs
from athena.session.models import SessionContext


class IntradayAnalyticsEngine:
    """Deterministic, replayable formalization of existing intraday
    evidence into typed artifacts. Produces no new scoring input — nothing
    here is consumed by ScoringEngine/ConfidenceEngine/RiskEngine/
    DecisionEngine (ID-2 §10)."""

    def assess(
        self,
        instrument_id: str,
        *,
        as_of: datetime,
        session_date: date,
        session_context: SessionContext,
        vwap: IndicatorResult | None,
        confluence: ConfluenceInputs | None,
        five_min_sma_period: int,
        fifteen_min_sma_period: int,
        or15: OpeningRangeEvidence,
        or30: OpeningRangeEvidence,
        relative_strength: RelativeStrengthContext,
        gap: GapContext,
        relative_volume: RelativeVolumeContext,
    ) -> IntradaySignalSet:
        if as_of.tzinfo is None:
            raise ValueError("IntradayAnalyticsEngine.assess as_of must be timezone-aware")

        vwap_evidence = self._vwap_evidence(vwap, session_context)
        five_min = self._trend_evidence(
            Timeframe.M5,
            confluence.five_min_bullish if confluence is not None else None,
            five_min_sma_period, session_context.five_min,
        )
        fifteen_min = self._trend_evidence(
            Timeframe.M15,
            confluence.fifteen_min_bullish if confluence is not None else None,
            fifteen_min_sma_period, session_context.fifteen_min,
        )
        trend_label, trend_reason = self._aggregate_trend(five_min, fifteen_min)
        trend = IntradayTrendContext(
            instrument_id=instrument_id, session_date=session_date, as_of=as_of,
            five_min=five_min, fifteen_min=fifteen_min, trend_label=trend_label,
            explanation=f"{instrument_id} intraday trend {trend_label.value}: {trend_reason}",
        )

        return IntradaySignalSet(
            instrument_id=instrument_id, session_date=session_date, as_of=as_of,
            vwap=vwap_evidence, trend=trend, or15=or15, or30=or30,
            relative_strength=relative_strength, gap=gap,
            relative_volume=relative_volume,
            data_quality=session_context.data_quality,
            explanation=(
                f"{instrument_id} intraday evidence as of {as_of.isoformat()}: "
                f"vwap={vwap_evidence.relation.value}, trend={trend_label.value}, "
                f"or15={or15.formation.status.value}, or30={or30.formation.status.value}, "
                f"rs_stock_vs_market={relative_strength.stock_vs_market_relation.value}, "
                f"gap={gap.direction.value}, relative_volume={relative_volume.relation.value}, "
                f"session_data_quality={session_context.data_quality.value} — "
                f"analytical evidence only, not a trade signal"
            ),
        )

    # ------------------------------------------------------------- helpers

    @staticmethod
    def _vwap_evidence(vwap: IndicatorResult | None, session_context: SessionContext) -> VwapEvidence:
        if vwap is None or vwap.status is not IndicatorStatus.OK:
            return VwapEvidence(
                relation=VwapRelation.VWAP_UNAVAILABLE, deviation_pct=None,
                explanation=(
                    f"VWAP indicator unavailable this cycle "
                    f"(session 5m data quality: {session_context.five_min.quality.value} — "
                    f"{session_context.five_min.explanation})"
                ),
            )
        deviation_pct = vwap.values["deviation_pct"]
        if deviation_pct > 0:
            relation = VwapRelation.ABOVE_VWAP
        elif deviation_pct < 0:
            relation = VwapRelation.BELOW_VWAP
        else:
            relation = VwapRelation.AT_VWAP
        return VwapEvidence(
            relation=relation, deviation_pct=deviation_pct,
            explanation=(
                f"price is {relation.value} (deviation {deviation_pct}%), formalized from the "
                f"existing ScoringEngine-consumed VWAP IndicatorResult, unchanged"
            ),
        )

    @staticmethod
    def _trend_evidence(
        timeframe: Timeframe, bullish: bool | None, sma_period: int, provenance,
    ) -> TimeframeTrendEvidence:
        if bullish is None:
            return TimeframeTrendEvidence(
                timeframe=timeframe, bullish=None, sma_period=sma_period,
                explanation=(
                    f"{timeframe.value} SMA({sma_period}) direction unavailable "
                    f"(session {timeframe.value} data quality: {provenance.quality.value} — "
                    f"{provenance.explanation})"
                ),
            )
        label = "bullish (close >= SMA)" if bullish else "bearish (close < SMA)"
        return TimeframeTrendEvidence(
            timeframe=timeframe, bullish=bullish, sma_period=sma_period,
            explanation=(
                f"{timeframe.value} price is {label}, per the existing confluence "
                f"SMA({sma_period}) direction check, unchanged"
            ),
        )

    @staticmethod
    def _aggregate_trend(
        five_min: TimeframeTrendEvidence, fifteen_min: TimeframeTrendEvidence,
    ) -> tuple[IntradayTrendLabel, str]:
        if five_min.bullish is None or fifteen_min.bullish is None:
            missing = ", ".join(
                tf.timeframe.value for tf in (five_min, fifteen_min) if tf.bullish is None
            )
            return (
                IntradayTrendLabel.UNKNOWN,
                f"insufficient evidence: {missing} direction unavailable",
            )
        if five_min.bullish and fifteen_min.bullish:
            return IntradayTrendLabel.BULLISH, "5m and 15m both bullish (agree)"
        if not five_min.bullish and not fifteen_min.bullish:
            return IntradayTrendLabel.BEARISH, "5m and 15m both bearish (agree)"
        five_dir = "bullish" if five_min.bullish else "bearish"
        fifteen_dir = "bullish" if fifteen_min.bullish else "bearish"
        return (
            IntradayTrendLabel.MIXED,
            f"5m={five_dir} vs 15m={fifteen_dir} — conflicting, no forced direction",
        )
