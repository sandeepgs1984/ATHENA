"""Market Health Engine (M2.2, F-5).

Answers one question: "How healthy is the market environment?" — descriptively.
It never answers what to buy, avoid, or rank; those belong to later phases.

Four independently explainable dimensions, each always labelled (explicit
*_UNKNOWN when data is insufficient):
- Breadth        : advances vs declines participation (from MarketSnapshot)
- Trend Quality  : one-directional consistency of recent index returns
- Momentum       : rate-of-change of the index over a configured period
- Volatility     : contextual read of India VIX on overall market stability

Pure and replayable: no I/O, no clock reads (time injected as ``as_of``), no
randomness; Decimal math; thresholds from market_health.json. Regime-aware but
not regime-dependent: an optional RegimeResult enriches explanations only.
"""

from __future__ import annotations

from collections.abc import Sequence
from datetime import datetime
from decimal import Decimal

from athena.config.models import MarketHealthConfig
from athena.domain.market import Candle, MarketSnapshot
from athena.market_health.models import (
    HealthEvidence,
    MarketHealthAssessment,
    MarketHealthLabel,
    MarketHealthResult,
)
from athena.regime.models import RegimeResult


class MarketHealthEngine:
    """Deterministic, descriptive assessment of overall market condition."""

    def __init__(self, config: MarketHealthConfig) -> None:
        self._config = config

    def assess(
        self,
        index_symbol: str,
        index_candles: Sequence[Candle],
        snapshot: MarketSnapshot | None,
        *,
        as_of: datetime,
        regime: RegimeResult | None = None,
    ) -> MarketHealthResult:
        assessment_id = f"health-{index_symbol}-{as_of.isoformat()}"
        ordered = sorted(index_candles, key=lambda c: c.ts_open)

        evidence = (
            self._breadth(assessment_id, snapshot),
            self._trend_quality(assessment_id, ordered, regime),
            self._momentum(assessment_id, ordered),
            self._volatility(assessment_id, snapshot),
        )
        dimensions = {e.dimension: e.outcome.value for e in evidence}
        explanation = (
            f"{index_symbol} market health: "
            + ", ".join(f"{e.dimension}={e.outcome.value}" for e in evidence)
        )
        assessment = MarketHealthAssessment(
            assessment_id=assessment_id, ts=as_of, dimensions=dimensions,
            evidence_ids=tuple(e.evidence_id for e in evidence), explanation=explanation,
        )
        return MarketHealthResult(assessment=assessment, evidence=evidence)

    # --------------------------------------------------------------- breadth

    def _breadth(self, assessment_id: str, snapshot: MarketSnapshot | None) -> HealthEvidence:
        eid = f"{assessment_id}:breadth"
        cfg = self._config.breadth
        thresholds = {"strong_ratio": str(cfg.strong_ratio), "weak_ratio": str(cfg.weak_ratio)}
        if snapshot is None:
            return HealthEvidence(eid, "breadth", MarketHealthLabel.BREADTH_UNKNOWN,
                                  "no market snapshot available for breadth", thresholds)
        adv, dec = snapshot.breadth_advances, snapshot.breadth_declines
        total = adv + dec
        if total == 0:
            return HealthEvidence(eid, "breadth", MarketHealthLabel.BREADTH_UNKNOWN,
                                  "advances and declines both zero — breadth undeterminable",
                                  {**thresholds, "advances": str(adv), "declines": str(dec)})
        ratio = Decimal(adv) / Decimal(total)
        strong = Decimal(str(cfg.strong_ratio))
        weak = Decimal(str(cfg.weak_ratio))
        if ratio >= strong:
            outcome = MarketHealthLabel.STRONG_BREADTH
        elif ratio <= weak:
            outcome = MarketHealthLabel.WEAK_BREADTH
        else:
            outcome = MarketHealthLabel.MIXED_BREADTH
        return HealthEvidence(
            eid, "breadth", outcome,
            f"advance ratio {ratio:.3f} ({adv} adv / {dec} dec) vs bands "
            f"[weak {weak}, strong {strong}] → {outcome.value}",
            {**thresholds, "advances": str(adv), "declines": str(dec),
             "advance_ratio": f"{ratio:.4f}"},
        )

    # --------------------------------------------------------- trend quality

    def _trend_quality(
        self, assessment_id: str, ordered: Sequence[Candle], regime: RegimeResult | None
    ) -> HealthEvidence:
        eid = f"{assessment_id}:trend_quality"
        cfg = self._config.trend_quality
        thresholds = {"window": str(cfg.window),
                      "strong_consistency": str(cfg.strong_consistency),
                      "weak_consistency": str(cfg.weak_consistency)}
        if len(ordered) < cfg.window + 1:
            return HealthEvidence(
                eid, "trend_quality", MarketHealthLabel.TREND_QUALITY_UNKNOWN,
                f"need {cfg.window + 1} candles for {cfg.window} returns, have {len(ordered)}",
                thresholds)
        closes = [c.close for c in ordered][-(cfg.window + 1):]
        returns = [closes[i] - closes[i - 1] for i in range(1, len(closes))]
        ups = sum(1 for r in returns if r > 0)
        downs = sum(1 for r in returns if r < 0)
        up_fraction = Decimal(ups) / Decimal(len(returns))
        consistency = max(up_fraction, Decimal(1) - up_fraction)  # one-directionality
        strong = Decimal(str(cfg.strong_consistency))
        weak = Decimal(str(cfg.weak_consistency))
        if consistency >= strong:
            outcome = MarketHealthLabel.STRONG_TREND_QUALITY
        elif consistency <= weak:
            outcome = MarketHealthLabel.WEAK_TREND_QUALITY
        else:
            outcome = MarketHealthLabel.MIXED_TREND_QUALITY
        regime_note = ""
        if regime is not None:
            trend = next((e.outcome.value for e in regime.evidence if e.dimension == "trend"), None)
            if trend:
                regime_note = f"; regime trend={trend}"
        return HealthEvidence(
            eid, "trend_quality", outcome,
            f"directional consistency {consistency:.3f} over {len(returns)} returns "
            f"({ups} up / {downs} down) vs bands [weak {weak}, strong {strong}] → "
            f"{outcome.value}{regime_note}",
            {**thresholds, "up_days": str(ups), "down_days": str(downs),
             "consistency": f"{consistency:.4f}"},
        )

    # -------------------------------------------------------------- momentum

    def _momentum(self, assessment_id: str, ordered: Sequence[Candle]) -> HealthEvidence:
        eid = f"{assessment_id}:momentum"
        cfg = self._config.momentum
        thresholds = {"period": str(cfg.period), "healthy_pct": str(cfg.healthy_pct)}
        if len(ordered) < cfg.period + 1:
            return HealthEvidence(
                eid, "momentum", MarketHealthLabel.MOMENTUM_UNKNOWN,
                f"need {cfg.period + 1} candles for {cfg.period}-period ROC, have {len(ordered)}",
                thresholds)
        last_close = ordered[-1].close
        past_close = ordered[-(cfg.period + 1)].close
        roc = (last_close - past_close) / past_close * Decimal(100)
        healthy = Decimal(str(cfg.healthy_pct))
        if roc >= healthy:
            outcome = MarketHealthLabel.HEALTHY_MOMENTUM
        elif roc <= -healthy:
            outcome = MarketHealthLabel.WEAK_MOMENTUM
        else:
            outcome = MarketHealthLabel.FLAT_MOMENTUM
        return HealthEvidence(
            eid, "momentum", outcome,
            f"{cfg.period}-period ROC {roc:.2f}% vs ±{healthy}% → {outcome.value}",
            {**thresholds, "roc_pct": f"{roc:.4f}", "last_close": str(last_close),
             "past_close": str(past_close)},
        )

    # ------------------------------------------------------------ volatility

    def _volatility(self, assessment_id: str, snapshot: MarketSnapshot | None) -> HealthEvidence:
        eid = f"{assessment_id}:volatility"
        cfg = self._config.volatility
        thresholds = {"calm_vix": str(cfg.calm_vix), "elevated_vix": str(cfg.elevated_vix)}
        vix = snapshot.india_vix if snapshot is not None else None
        if vix is None:
            return HealthEvidence(eid, "volatility", MarketHealthLabel.VOLATILITY_UNKNOWN,
                                  "India VIX unavailable — volatility context undeterminable",
                                  thresholds)
        calm = Decimal(str(cfg.calm_vix))
        elevated = Decimal(str(cfg.elevated_vix))
        if vix <= calm:
            outcome = MarketHealthLabel.VOLATILITY_CALM
            note = "stable conditions"
        elif vix >= elevated:
            outcome = MarketHealthLabel.VOLATILITY_ELEVATED
            note = "less stable conditions, wider swings likely"
        else:
            outcome = MarketHealthLabel.VOLATILITY_NORMAL
            note = "typical conditions"
        return HealthEvidence(
            eid, "volatility", outcome,
            f"India VIX {vix} vs [calm {calm}, elevated {elevated}] → {outcome.value} ({note})",
            {**thresholds, "india_vix": str(vix)},
        )
