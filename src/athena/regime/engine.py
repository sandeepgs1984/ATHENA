"""Market Regime Engine (M2.1, R-2).

Determines the current market regime from canonical market data using
deterministic rules. Descriptive, not prescriptive — it understands the market,
it does not decide what to trade. Pure and replayable: no I/O, no clock reads
(time is injected as ``as_of``), no randomness.

Three orthogonal dimensions, each always assigned a label (explicit *_UNKNOWN
when data is insufficient — never a silent omission):
- Trend      : BULL_TREND / BEAR_TREND / SIDEWAYS  (fast vs slow SMA + last close)
- Volatility : HIGH / LOW / NORMAL                 (India VIX vs configured bands)
- Gap        : GAP_UP / GAP_DOWN / NO_GAP          (latest open vs prior close)

Consumes canonical domain objects (Candle, MarketSnapshot) + RegimeConfig;
produces the frozen-domain RegimeAssessment plus a RegimeEvidence chain.
"""

from __future__ import annotations

from collections.abc import Sequence
from datetime import datetime
from decimal import Decimal

from athena.config.models import RegimeConfig
from athena.domain.market import Candle, MarketSnapshot, RegimeAssessment
from athena.regime.models import RegimeEvidence, RegimeLabel, RegimeResult


def _sma(closes: Sequence[Decimal], window: int) -> Decimal:
    subset = closes[-window:]
    return sum(subset, Decimal(0)) / Decimal(len(subset))


class RegimeEngine:
    """Deterministic, explainable market regime classification."""

    def __init__(self, config: RegimeConfig) -> None:
        self._config = config

    def assess(
        self,
        index_symbol: str,
        index_candles: Sequence[Candle],
        snapshot: MarketSnapshot | None,
        *,
        as_of: datetime,
    ) -> RegimeResult:
        assessment_id = f"regime-{index_symbol}-{as_of.isoformat()}"
        ordered = sorted(index_candles, key=lambda c: c.ts_open)

        trend = self._trend(assessment_id, ordered)
        volatility = self._volatility(assessment_id, snapshot)
        gap = self._gap(assessment_id, ordered)

        evidence = (trend, volatility, gap)
        labels = tuple(e.outcome.value for e in evidence)
        explanation = (
            f"{index_symbol}: {trend.outcome.value}, {volatility.outcome.value}, "
            f"{gap.outcome.value}"
        )
        assessment = RegimeAssessment(
            assessment_id=assessment_id,
            ts=as_of,
            labels=labels,
            evidence_ids=tuple(e.evidence_id for e in evidence),
            explanation=explanation,
        )
        return RegimeResult(assessment=assessment, evidence=evidence)

    # ------------------------------------------------------------------ trend

    def _trend(self, assessment_id: str, ordered: Sequence[Candle]) -> RegimeEvidence:
        fast_n, slow_n = self._config.trend_ma_fast, self._config.trend_ma_slow
        eid = f"{assessment_id}:trend"
        if len(ordered) < slow_n:
            return RegimeEvidence(
                evidence_id=eid, dimension="trend", outcome=RegimeLabel.TREND_UNKNOWN,
                explanation=(f"insufficient history: need {slow_n} candles for the slow SMA, "
                             f"have {len(ordered)}"),
                inputs={"candles_available": str(len(ordered)), "slow_window": str(slow_n)},
            )
        closes = [c.close for c in ordered]
        fast_sma = _sma(closes, fast_n)
        slow_sma = _sma(closes, slow_n)
        last_close = closes[-1]

        if fast_sma > slow_sma and last_close >= slow_sma:
            outcome = RegimeLabel.BULL_TREND
        elif fast_sma < slow_sma and last_close <= slow_sma:
            outcome = RegimeLabel.BEAR_TREND
        else:
            outcome = RegimeLabel.SIDEWAYS

        return RegimeEvidence(
            evidence_id=eid, dimension="trend", outcome=outcome,
            explanation=(f"fast SMA({fast_n})={fast_sma:.2f} vs slow SMA({slow_n})={slow_sma:.2f}, "
                         f"last close={last_close} → {outcome.value}"),
            inputs={"fast_sma": str(fast_sma), "slow_sma": str(slow_sma),
                    "last_close": str(last_close), "fast_window": str(fast_n),
                    "slow_window": str(slow_n)},
        )

    # ------------------------------------------------------------- volatility

    def _volatility(self, assessment_id: str, snapshot: MarketSnapshot | None) -> RegimeEvidence:
        eid = f"{assessment_id}:volatility"
        vix = snapshot.india_vix if snapshot is not None else None
        if vix is None:
            return RegimeEvidence(
                evidence_id=eid, dimension="volatility", outcome=RegimeLabel.VOLATILITY_UNKNOWN,
                explanation="India VIX unavailable in the market snapshot",
                inputs={"india_vix": "none"},
            )
        high = Decimal(str(self._config.high_volatility_vix))
        low = Decimal(str(self._config.low_volatility_vix))
        if vix >= high:
            outcome = RegimeLabel.HIGH_VOLATILITY
        elif vix <= low:
            outcome = RegimeLabel.LOW_VOLATILITY
        else:
            outcome = RegimeLabel.NORMAL_VOLATILITY
        return RegimeEvidence(
            evidence_id=eid, dimension="volatility", outcome=outcome,
            explanation=(f"India VIX={vix} vs bands [low {low}, high {high}] → {outcome.value}"),
            inputs={"india_vix": str(vix), "low_band": str(low), "high_band": str(high)},
        )

    # -------------------------------------------------------------------- gap

    def _gap(self, assessment_id: str, ordered: Sequence[Candle]) -> RegimeEvidence:
        eid = f"{assessment_id}:gap"
        if len(ordered) < 2:
            return RegimeEvidence(
                evidence_id=eid, dimension="gap", outcome=RegimeLabel.GAP_UNKNOWN,
                explanation="need at least two candles to measure an opening gap",
                inputs={"candles_available": str(len(ordered))},
            )
        prev_close = ordered[-2].close
        latest_open = ordered[-1].open
        threshold = Decimal(str(self._config.gap_pct_threshold))
        gap_pct = (latest_open - prev_close) / prev_close * Decimal(100)
        if gap_pct >= threshold:
            outcome = RegimeLabel.GAP_UP
        elif gap_pct <= -threshold:
            outcome = RegimeLabel.GAP_DOWN
        else:
            outcome = RegimeLabel.NO_GAP
        return RegimeEvidence(
            evidence_id=eid, dimension="gap", outcome=outcome,
            explanation=(f"open {latest_open} vs prior close {prev_close} = {gap_pct:.2f}% "
                         f"(threshold ±{threshold}%) → {outcome.value}"),
            inputs={"latest_open": str(latest_open), "prev_close": str(prev_close),
                    "gap_pct": f"{gap_pct:.4f}", "threshold_pct": str(threshold)},
        )
