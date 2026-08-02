"""Scoring Engine (M3.3).

Transforms approved evidence and objective measurements into transparent,
explainable component scores plus a composite that retains a full breakdown.
Scores are intermediate artifacts — never recommendations, sizing, or decisions.

Consumes approved artifacts only (assessments + IndicatorResults); never raw
providers or repositories. Pure and replayable: injected ``as_of``, Decimal
math, config-driven point maps. Missing inputs → explicit UNKNOWN (no defaults).
"""

from __future__ import annotations

from collections.abc import Mapping
from datetime import datetime
from decimal import Decimal

from athena.config.models import ScoringConfig
from athena.domain.market import MarketHealthScore
from athena.indicators.models import IndicatorName, IndicatorResult, IndicatorStatus
from athena.market_health.models import MarketHealthResult
from athena.regime.models import RegimeResult
from athena.scoring.models import (
    ComponentScore,
    CompositeBreakdownItem,
    CompositeScore,
    Contribution,
    ScoreStatus,
    ScoringResult,
)
from athena.sector_health.models import SectorHealthResult

_ZERO, _HUNDRED = Decimal(0), Decimal(100)
_TWO_DP = Decimal("0.01")


def _clamp(value: Decimal) -> Decimal:
    return max(_ZERO, min(_HUNDRED, value))


def _fmt2(value: Decimal) -> str:
    """Compact 2dp rendering for owner-facing explanations (avoids long Decimal tails)."""
    return format(value.quantize(_TWO_DP), "f")


def _linear_ramp(
    x: Decimal,
    *,
    x_lo: Decimal,
    x_hi: Decimal,
    y_lo: Decimal,
    y_hi: Decimal,
) -> Decimal:
    """Piecewise-linear map of ``x`` onto ``[y_lo, y_hi]``.

    Clamps outside the input band. Reproduces ``y_lo`` at ``x_lo`` and
    ``y_hi`` at ``x_hi`` exactly (SD-4 anchor-preserving continuous scoring).
    """
    if x <= x_lo:
        return y_lo
    if x >= x_hi:
        return y_hi
    return y_lo + (y_hi - y_lo) * (x - x_lo) / (x_hi - x_lo)


def _ok(dimension, value, contributions, explanation) -> ComponentScore:
    return ComponentScore(dimension=dimension, status=ScoreStatus.OK, value=_clamp(value),
                          contributions=tuple(contributions), explanation=explanation)


def _unknown(dimension, explanation) -> ComponentScore:
    return ComponentScore(dimension=dimension, status=ScoreStatus.UNKNOWN, value=None,
                          contributions=(), explanation=explanation)


class ScoringEngine:
    """Deterministic, evidence- and indicator-driven component + composite scoring."""

    def __init__(self, config: ScoringConfig) -> None:
        self._config = config

    def score(
        self,
        instrument_id: str,
        *,
        as_of: datetime,
        indicators: Mapping[IndicatorName, IndicatorResult] | None = None,
        regime: RegimeResult | None = None,
        market_health: MarketHealthResult | None = None,
        market_health_score: MarketHealthScore | None = None,
        sector_health: SectorHealthResult | None = None,
        vwap: IndicatorResult | None = None,
    ) -> ScoringResult:
        # M-X6: vwap is intentionally its own parameter, never folded into
        # `indicators` — ConfidenceEngine._indicator_availability/_unknown_ratio
        # measure completeness as known/len(indicators), so merging a 7th,
        # data-sparse (same-session-only) indicator into that dict would
        # silently move every symbol's confidence whenever intraday history
        # happens to be thin, with no owner-reviewed impact assessment (the
        # exact risk SD-2/SD-3 treat explicitly for sector_quality). Passed
        # straight through to _technical_structure instead, exactly like
        # market_health_score/sector_health above.
        indicators = dict(indicators or {})
        components = {
            "trend": self._trend(regime, indicators),
            "momentum": self._momentum(indicators),
            "market_quality": self._market_quality(market_health, market_health_score),
            "sector_quality": self._sector_quality(sector_health),
            "liquidity": self._liquidity(indicators),
            "technical_structure": self._technical_structure(indicators, vwap),
        }
        composite = self._composite(components)
        return ScoringResult(instrument_id=instrument_id, ts=as_of,
                             components=components, composite=composite)

    # ------------------------------------------------------------- helpers

    def _label_points(self, label: str) -> int | None:
        return self._config.label_points.get(label)

    @staticmethod
    def _known_indicator(
        indicators: Mapping[IndicatorName, IndicatorResult], name: IndicatorName
    ) -> IndicatorResult | None:
        result = indicators.get(name)
        if result is None or result.status is not IndicatorStatus.OK:
            return None
        return result

    # ------------------------------------------------------------- components

    def _trend(self, regime, indicators) -> ComponentScore:
        if regime is None:
            return _unknown("trend", "no regime assessment available")
        trend_label = next(
            (e.outcome.value for e in regime.evidence if e.dimension == "trend"), None)
        base = self._label_points(trend_label) if trend_label else None
        if base is None:
            return _unknown("trend", f"regime trend not scoreable (label={trend_label})")
        value = Decimal(base)
        contribs = [Contribution("regime:trend", f"regime-{trend_label}",
                                 f"regime trend {trend_label} → {base} pts", Decimal(base))]
        adx = self._known_indicator(indicators, IndicatorName.ADX)
        if adx is not None:
            adx_val = adx.values["adx"]
            cfg = self._config.adx
            bonus = _linear_ramp(
                adx_val,
                x_lo=Decimal(str(cfg.weak)),
                x_hi=Decimal(str(cfg.strong)),
                y_lo=_ZERO,
                y_hi=Decimal(cfg.bonus),
            )
            if bonus > _ZERO:
                value += bonus
                contribs.append(Contribution(
                    "indicator:ADX", "ADX",
                    f"ADX {adx_val} → +{_fmt2(bonus)} pts "
                    f"(ramp {cfg.weak}→{cfg.strong})",
                    bonus,
                ))
        return _ok("trend", value, contribs,
                   f"trend score {_clamp(value)} from regime trend + ADX strength")

    def _momentum(self, indicators) -> ComponentScore:
        rsi = self._known_indicator(indicators, IndicatorName.RSI)
        if rsi is None:
            return _unknown("momentum", "RSI indicator unavailable")
        cfg = self._config.rsi
        rsi_val = rsi.values["value"]
        # Continuous ramp through the three configured anchors (SD-4):
        # RSI weak → weak_points, mid → mid_points, strong → strong_points.
        # The mid anchor is the arithmetic midpoint of the band when
        # mid_points sits halfway between weak_points and strong_points —
        # which the production config does (40→20, 50→50, 60→80).
        pts = _linear_ramp(
            rsi_val,
            x_lo=Decimal(str(cfg.weak)),
            x_hi=Decimal(str(cfg.strong)),
            y_lo=Decimal(cfg.weak_points),
            y_hi=Decimal(cfg.strong_points),
        )
        contribs = [Contribution(
            "indicator:RSI", "RSI",
            f"RSI {rsi_val} → {_fmt2(pts)} pts "
            f"(ramp {cfg.weak}→{cfg.strong})",
            pts,
        )]
        return _ok("momentum", pts, contribs,
                   f"momentum score {_fmt2(pts)} from RSI")

    def _market_quality(
        self,
        market_health,
        market_health_score: MarketHealthScore | None = None,
    ) -> ComponentScore:
        # F-5 / MH-2 cutover: authoritative numeric score wins when present.
        if market_health_score is not None:
            total = market_health_score.total
            contribs = [
                Contribution(
                    f"market_health_score:{name}",
                    str(pts),
                    f"{name}={pts} pts",
                    Decimal(pts),
                )
                for name, pts in sorted(market_health_score.components.items())
            ]
            return _ok(
                "market_quality",
                Decimal(total),
                contribs,
                f"market_quality {total} from MarketHealthScore.total",
            )
        if market_health is None:
            return _unknown("market_quality", "no market health assessment available")
        # Compat shim: categorical label average until a score is available.
        return self._quality_from_dimensions(
            "market_quality", "market_health", market_health.assessment.dimensions)

    def _sector_quality(self, sector_health) -> ComponentScore:
        if sector_health is None:
            return _unknown("sector_quality", "no sector health assessment available")
        return self._quality_from_dimensions(
            "sector_quality", "sector_health", sector_health.assessment.dimensions)

    def _quality_from_dimensions(self, dimension, source, dimensions) -> ComponentScore:
        contribs: list[Contribution] = []
        points: list[int] = []
        for dim, label in sorted(dimensions.items()):
            pts = self._label_points(label)
            if pts is None:
                continue  # UNKNOWN / unscoreable dimension excluded, never defaulted
            points.append(pts)
            contribs.append(Contribution(f"{source}:{dim}", label,
                                         f"{dim}={label} → {pts} pts", Decimal(pts)))
        if not points:
            return _unknown(dimension, f"no scoreable {source} dimensions")
        avg = Decimal(sum(points)) / Decimal(len(points))
        return _ok(dimension, avg, contribs,
                   f"{dimension} {_fmt2(avg)} = mean of {len(points)} scoreable dimension(s)")

    def _liquidity(self, indicators) -> ComponentScore:
        vma = self._known_indicator(indicators, IndicatorName.VOLUME_MA)
        if vma is None:
            return _unknown("liquidity", "Volume MA indicator unavailable")
        cfg = self._config.liquidity
        vma_val = vma.values["value"]
        floor = Decimal(cfg.min_volume_ma)
        # Continuous ramp (SD-4): low_points at floor_ratio * min_volume_ma,
        # ok_points at min_volume_ma. Both endpoints preserve the pre-ramp
        # anchors; anything at or above the floor still scores ok_points.
        pts = _linear_ramp(
            vma_val,
            x_lo=floor * Decimal(str(cfg.low_volume_floor_ratio)),
            x_hi=floor,
            y_lo=Decimal(cfg.low_points),
            y_hi=Decimal(cfg.ok_points),
        )
        contribs = [Contribution(
            "indicator:VOLUME_MA", "VOLUME_MA",
            f"Volume MA {vma_val} vs min {cfg.min_volume_ma} → {_fmt2(pts)} pts "
            f"(ramp {cfg.low_volume_floor_ratio}x→1.0x)",
            pts,
        )]
        return _ok("liquidity", pts, contribs,
                   f"liquidity score {_fmt2(pts)} from Volume MA")

    def _technical_structure(self, indicators, vwap: IndicatorResult | None = None) -> ComponentScore:
        sma = self._known_indicator(indicators, IndicatorName.SMA)
        if sma is None:
            return _unknown("technical_structure", "SMA indicator unavailable")
        last_close_raw = sma.evidence.inputs.get("last_close")
        if last_close_raw is None:
            return _unknown("technical_structure", "SMA evidence lacks last_close")
        cfg = self._config.technical
        last_close = Decimal(last_close_raw)
        sma_val = sma.values["value"]
        above = last_close >= sma_val
        pts = cfg.above_ma_points if above else cfg.below_ma_points
        contribs = [Contribution("indicator:SMA", "SMA",
                                 f"last close {last_close} {'>=' if above else '<'} SMA {sma_val} "
                                 f"→ {pts} pts", Decimal(pts))]
        value = Decimal(pts)
        macd = self._known_indicator(indicators, IndicatorName.MACD)
        if macd is not None and macd.values["histogram"] > _ZERO:
            bonus = Decimal(cfg.macd_pos_bonus)
            value += bonus
            contribs.append(Contribution("indicator:MACD", "MACD",
                                         f"MACD histogram {macd.values['histogram']} > 0 "
                                         f"→ +{bonus} pts", bonus))
        # M-X6: VWAP reclaim — continuous ramp (SD-4 style), 0 at/below VWAP,
        # up to vwap_max_bonus at vwap_deviation_cap_pct and beyond. Passed
        # as its own parameter (see score()'s docstring note above), not
        # read via _known_indicator/`indicators`.
        if vwap is not None and vwap.status is IndicatorStatus.OK:
            deviation_pct = vwap.values["deviation_pct"]
            vwap_bonus = _linear_ramp(
                deviation_pct,
                x_lo=_ZERO, x_hi=Decimal(str(cfg.vwap_deviation_cap_pct)),
                y_lo=_ZERO, y_hi=Decimal(cfg.vwap_max_bonus),
            )
            if vwap_bonus > _ZERO:
                value += vwap_bonus
                contribs.append(Contribution("indicator:VWAP", "VWAP",
                                             f"price {deviation_pct:.2f}% above session VWAP "
                                             f"→ +{_fmt2(vwap_bonus)} pts", vwap_bonus))
        return _ok("technical_structure", value, contribs,
                   f"technical structure {_clamp(value)} from price-vs-SMA + MACD + VWAP")

    # ------------------------------------------------------------- composite

    def _composite(self, components: Mapping[str, ComponentScore]) -> CompositeScore:
        weights = self._config.weights.model_dump()
        breakdown: list[CompositeBreakdownItem] = []
        weighted_sum = _ZERO
        known_weight = 0
        total_weight = 0
        for dim, comp in components.items():
            weight = int(weights[dim])
            total_weight += weight
            if comp.is_known and comp.value is not None:
                weighted = comp.value * Decimal(weight)
                weighted_sum += weighted
                known_weight += weight
                breakdown.append(CompositeBreakdownItem(dim, weight, comp.status, comp.value,
                                                        weighted))
            else:
                breakdown.append(CompositeBreakdownItem(dim, weight, comp.status, None, None))
        breakdown_t = tuple(breakdown)
        if known_weight == 0:
            return CompositeScore(status=ScoreStatus.UNKNOWN, value=None, completeness=_ZERO,
                                  breakdown=breakdown_t,
                                  explanation="composite UNKNOWN: no scoreable components")
        value = weighted_sum / Decimal(known_weight)
        completeness = Decimal(known_weight) / Decimal(total_weight)
        return CompositeScore(
            status=ScoreStatus.OK, value=_clamp(value), completeness=completeness,
            breakdown=breakdown_t,
            explanation=(f"composite {_fmt2(_clamp(value))} = weighted mean of known components "
                         f"(completeness {completeness:.2f})"))
