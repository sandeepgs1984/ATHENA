"""Sector Health Engine (M2.3, F-6).

Answers one question per sector: "What is the condition of this sector?" —
descriptively. It never ranks sectors, selects opportunities, or emits signals.

Four independently explainable dimensions, each degrading to explicit
*_UNKNOWN on insufficient data:
- Trend      : sector index fast vs slow SMA (UPTREND/DOWNTREND/SIDEWAYS)
- Breadth    : constituent participation — UNKNOWN unless constituent breadth
               is supplied (never inferred; constituent data arrives in M2.4)
- Momentum   : sector index rate-of-change over a period
- Volatility : realized volatility (stdev of returns) as a sector-specific
               context, complementing (not duplicating) Market Health

Pure and replayable: injected ``as_of``, Decimal math, thresholds from
sector_health.json. Regime-aware and Market-Health-aware but dependent on
neither (both optional, explanation-only).
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from datetime import datetime
from decimal import Decimal

from athena.config.models import SectorHealthConfig
from athena.domain.market import Candle
from athena.market_health.models import MarketHealthResult
from athena.regime.models import RegimeResult
from athena.sector_health.models import (
    SectorHealthAssessment,
    SectorHealthEvidence,
    SectorHealthLabel,
    SectorHealthResult,
)


def _sma(closes: Sequence[Decimal], window: int) -> Decimal:
    subset = closes[-window:]
    return sum(subset, Decimal(0)) / Decimal(len(subset))


def _returns_pct(closes: Sequence[Decimal]) -> list[Decimal]:
    return [(closes[i] - closes[i - 1]) / closes[i - 1] * Decimal(100)
            for i in range(1, len(closes))]


class SectorHealthEngine:
    """Deterministic, descriptive per-sector condition assessment."""

    def __init__(self, config: SectorHealthConfig) -> None:
        self._config = config

    def assess(
        self,
        sector: str,
        sector_candles: Sequence[Candle],
        *,
        as_of: datetime,
        constituent_breadth: tuple[int, int] | None = None,
        market_health: MarketHealthResult | None = None,
        regime: RegimeResult | None = None,
    ) -> SectorHealthResult:
        assessment_id = f"sector-health-{sector}-{as_of.isoformat()}"
        ordered = sorted(sector_candles, key=lambda c: c.ts_open)

        evidence = (
            self._trend(assessment_id, ordered),
            self._breadth(assessment_id, constituent_breadth),
            self._momentum(assessment_id, ordered),
            self._volatility(assessment_id, ordered, market_health),
        )
        dimensions = {e.dimension: e.outcome.value for e in evidence}
        explanation = (
            f"{sector} sector health: "
            + ", ".join(f"{e.dimension}={e.outcome.value}" for e in evidence)
        )
        assessment = SectorHealthAssessment(
            assessment_id=assessment_id, ts=as_of, sector=sector, dimensions=dimensions,
            evidence_ids=tuple(e.evidence_id for e in evidence), explanation=explanation,
        )
        return SectorHealthResult(assessment=assessment, evidence=evidence)

    def assess_many(
        self,
        sector_candles: Mapping[str, Sequence[Candle]],
        *,
        as_of: datetime,
        constituent_breadth: Mapping[str, tuple[int, int]] | None = None,
        market_health: MarketHealthResult | None = None,
        regime: RegimeResult | None = None,
    ) -> dict[str, SectorHealthResult]:
        """Assess multiple sectors deterministically (sorted by sector name)."""
        breadth = constituent_breadth or {}
        return {
            sector: self.assess(sector, sector_candles[sector], as_of=as_of,
                                constituent_breadth=breadth.get(sector),
                                market_health=market_health, regime=regime)
            for sector in sorted(sector_candles)
        }

    # ----------------------------------------------------------------- trend

    def _trend(self, assessment_id: str, ordered: Sequence[Candle]) -> SectorHealthEvidence:
        eid = f"{assessment_id}:trend"
        fast_n, slow_n = self._config.trend.ma_fast, self._config.trend.ma_slow
        thresholds = {"ma_fast": str(fast_n), "ma_slow": str(slow_n)}
        if len(ordered) < slow_n:
            return SectorHealthEvidence(
                eid, "trend", SectorHealthLabel.SECTOR_TREND_UNKNOWN,
                f"need {slow_n} candles for the slow SMA, have {len(ordered)}", thresholds)
        closes = [c.close for c in ordered]
        fast_sma, slow_sma, last_close = _sma(closes, fast_n), _sma(closes, slow_n), closes[-1]
        if fast_sma > slow_sma and last_close >= slow_sma:
            outcome = SectorHealthLabel.SECTOR_UPTREND
        elif fast_sma < slow_sma and last_close <= slow_sma:
            outcome = SectorHealthLabel.SECTOR_DOWNTREND
        else:
            outcome = SectorHealthLabel.SECTOR_SIDEWAYS
        return SectorHealthEvidence(
            eid, "trend", outcome,
            f"fast SMA({fast_n})={fast_sma} vs slow SMA({slow_n})={slow_sma}, "
            f"last close={last_close} → {outcome.value}",
            {**thresholds, "fast_sma": str(fast_sma), "slow_sma": str(slow_sma),
             "last_close": str(last_close)},
        )

    # --------------------------------------------------------------- breadth

    def _breadth(
        self, assessment_id: str, constituent_breadth: tuple[int, int] | None
    ) -> SectorHealthEvidence:
        eid = f"{assessment_id}:breadth"
        cfg = self._config.breadth
        thresholds = {"strong_ratio": str(cfg.strong_ratio), "weak_ratio": str(cfg.weak_ratio)}
        if constituent_breadth is None:
            return SectorHealthEvidence(
                eid, "breadth", SectorHealthLabel.SECTOR_BREADTH_UNKNOWN,
                "constituent-level breadth not available at this stage (arrives with the "
                "Universe Engine) — reported UNKNOWN rather than inferred", thresholds)
        adv, dec = constituent_breadth
        total = adv + dec
        if total == 0:
            return SectorHealthEvidence(
                eid, "breadth", SectorHealthLabel.SECTOR_BREADTH_UNKNOWN,
                "advances and declines both zero — breadth undeterminable",
                {**thresholds, "advances": str(adv), "declines": str(dec)})
        ratio = Decimal(adv) / Decimal(total)
        strong, weak = Decimal(str(cfg.strong_ratio)), Decimal(str(cfg.weak_ratio))
        if ratio >= strong:
            outcome = SectorHealthLabel.STRONG_SECTOR_BREADTH
        elif ratio <= weak:
            outcome = SectorHealthLabel.WEAK_SECTOR_BREADTH
        else:
            outcome = SectorHealthLabel.MIXED_SECTOR_BREADTH
        return SectorHealthEvidence(
            eid, "breadth", outcome,
            f"advance ratio {ratio:.3f} ({adv} adv / {dec} dec) vs bands "
            f"[weak {weak}, strong {strong}] → {outcome.value}",
            {**thresholds, "advances": str(adv), "declines": str(dec),
             "advance_ratio": f"{ratio:.4f}"},
        )

    # -------------------------------------------------------------- momentum

    def _momentum(self, assessment_id: str, ordered: Sequence[Candle]) -> SectorHealthEvidence:
        eid = f"{assessment_id}:momentum"
        cfg = self._config.momentum
        thresholds = {"period": str(cfg.period), "healthy_pct": str(cfg.healthy_pct)}
        if len(ordered) < cfg.period + 1:
            return SectorHealthEvidence(
                eid, "momentum", SectorHealthLabel.SECTOR_MOMENTUM_UNKNOWN,
                f"need {cfg.period + 1} candles for {cfg.period}-period ROC, have {len(ordered)}",
                thresholds)
        last_close = ordered[-1].close
        past_close = ordered[-(cfg.period + 1)].close
        roc = (last_close - past_close) / past_close * Decimal(100)
        healthy = Decimal(str(cfg.healthy_pct))
        if roc >= healthy:
            outcome = SectorHealthLabel.HEALTHY_SECTOR_MOMENTUM
        elif roc <= -healthy:
            outcome = SectorHealthLabel.WEAK_SECTOR_MOMENTUM
        else:
            outcome = SectorHealthLabel.FLAT_SECTOR_MOMENTUM
        return SectorHealthEvidence(
            eid, "momentum", outcome,
            f"{cfg.period}-period ROC {roc:.2f}% vs ±{healthy}% → {outcome.value}",
            {**thresholds, "roc_pct": f"{roc:.4f}"},
        )

    # ------------------------------------------------------------ volatility

    def _volatility(
        self, assessment_id: str, ordered: Sequence[Candle],
        market_health: MarketHealthResult | None,
    ) -> SectorHealthEvidence:
        eid = f"{assessment_id}:volatility"
        cfg = self._config.volatility
        thresholds = {"window": str(cfg.window), "calm_pct": str(cfg.calm_pct),
                      "elevated_pct": str(cfg.elevated_pct)}
        if len(ordered) < cfg.window + 1:
            return SectorHealthEvidence(
                eid, "volatility", SectorHealthLabel.SECTOR_VOLATILITY_UNKNOWN,
                f"need {cfg.window + 1} candles for {cfg.window}-return volatility, "
                f"have {len(ordered)}", thresholds)
        closes = [c.close for c in ordered][-(cfg.window + 1):]
        returns = _returns_pct(closes)
        mean = sum(returns, Decimal(0)) / Decimal(len(returns))
        variance = sum(((r - mean) ** 2 for r in returns), Decimal(0)) / Decimal(len(returns))
        stdev = variance.sqrt()
        calm, elevated = Decimal(str(cfg.calm_pct)), Decimal(str(cfg.elevated_pct))
        if stdev <= calm:
            outcome = SectorHealthLabel.SECTOR_VOLATILITY_CALM
        elif stdev >= elevated:
            outcome = SectorHealthLabel.SECTOR_VOLATILITY_ELEVATED
        else:
            outcome = SectorHealthLabel.SECTOR_VOLATILITY_NORMAL
        market_note = ""
        if market_health is not None:
            mv = market_health.assessment.dimensions.get("volatility")
            if mv:
                market_note = f"; market volatility context={mv}"
        return SectorHealthEvidence(
            eid, "volatility", outcome,
            f"realized volatility {stdev:.3f}% over {len(returns)} returns vs "
            f"[calm {calm}%, elevated {elevated}%] → {outcome.value}{market_note}",
            {**thresholds, "realized_vol_pct": f"{stdev:.4f}"},
        )
