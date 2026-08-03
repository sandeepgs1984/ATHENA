"""F-5 MarketHealthScore construction (MH-2).

Pure and replayable: maps MH-1 aggregates + categorical health labels to the
six F-5 component points, then a config-weighted total. Emits a score only when
every required component is present (F-5 §4) — never fabricates midpoints.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from types import MappingProxyType

from athena.config.models import MarketHealthConfig
from athena.domain.market import InstitutionalFlowSession, MarketHealthScore
from athena.market_health.aggregates import (
    GapStabilityResult,
    LiquidityAggregateResult,
    UniverseBreadthResult,
)
from athena.market_health.models import MarketHealthLabel, MarketHealthResult

F5_COMPONENTS: tuple[str, ...] = (
    "trend_quality",
    "breadth",
    "liquidity",
    "volatility",
    "institutional_strength",
    "gap_stability",
)

_TREND_POINTS = {
    MarketHealthLabel.STRONG_TREND_QUALITY.value: "strong",
    MarketHealthLabel.MIXED_TREND_QUALITY.value: "mid",
    MarketHealthLabel.WEAK_TREND_QUALITY.value: "weak",
}
_VOL_POINTS = {
    MarketHealthLabel.VOLATILITY_CALM.value: "calm",
    MarketHealthLabel.VOLATILITY_NORMAL.value: "normal",
    MarketHealthLabel.VOLATILITY_ELEVATED.value: "elevated",
}


@dataclass(frozen=True, slots=True)
class ComponentScoreDetail:
    """Per-component diagnostic — present (points) or absent (reason)."""

    name: str
    points: int | None
    band: str | None
    explanation: str
    inputs: Mapping[str, str]

    def __post_init__(self) -> None:
        object.__setattr__(self, "inputs", MappingProxyType(dict(self.inputs)))

    def to_payload(self) -> dict[str, object]:
        return {
            "name": self.name,
            "points": self.points,
            "band": self.band,
            "explanation": self.explanation,
            "inputs": dict(self.inputs),
        }


@dataclass(frozen=True, slots=True)
class MarketHealthScoreBuild:
    """Construction result: score only when all six components are present."""

    score: MarketHealthScore | None
    components: tuple[ComponentScoreDetail, ...]
    unavailable_reason: str | None

    def score_payload(self) -> dict[str, object] | None:
        if self.score is None:
            return None
        return {
            "ts": self.score.ts.isoformat(),
            "components": dict(self.score.components),
            "total": self.score.total,
            "explanation": self.score.explanation,
        }

    def to_payload(self) -> dict[str, object]:
        return {
            "score": self.score_payload(),
            "components": [c.to_payload() for c in self.components],
            "unavailable_reason": self.unavailable_reason,
        }


def construct_market_health_score(
    *,
    as_of: datetime,
    config: MarketHealthConfig,
    breadth: UniverseBreadthResult,
    liquidity: LiquidityAggregateResult,
    gap_stability: GapStabilityResult,
    institutional_flow: InstitutionalFlowSession | None,
    health_result: MarketHealthResult | None = None,
) -> MarketHealthScoreBuild:
    """Map F-5 inputs → component points → weighted total, or unavailable."""
    details = (
        _score_trend_quality(config, health_result),
        _score_breadth(config, breadth),
        _score_liquidity(config, liquidity),
        _score_volatility(config, health_result),
        _score_institutional(config, institutional_flow, as_of=as_of),
        _score_gap_stability(config, gap_stability),
    )
    missing_details = [d for d in details if d.points is None]
    if missing_details:
        # MI-UX-1 (owner-reported, 2026-08-03): the prior message only named
        # the missing component ("missing required component(s):
        # institutional_strength"), forcing the owner to go digging for why.
        # Each component's own explanation is already computed (e.g. "stale
        # (age_days=12 > max_age_sessions=3)") — surface it instead of
        # discarding it, so the reason is actionable at a glance.
        reasons = "; ".join(f"{d.name}: {d.explanation}" for d in missing_details)
        return MarketHealthScoreBuild(
            score=None,
            components=details,
            unavailable_reason=f"MarketHealthScore unavailable — {reasons}",
        )

    weights = {
        "trend_quality": config.weights.trend_quality,
        "breadth": config.weights.breadth,
        "liquidity": config.weights.liquidity,
        "volatility": config.weights.volatility,
        "institutional_strength": config.weights.institutional_strength,
        "gap_stability": config.weights.gap_stability,
    }
    weight_sum = sum(weights.values())
    if weight_sum <= 0:
        return MarketHealthScoreBuild(
            score=None,
            components=details,
            unavailable_reason="MarketHealthScore unavailable — weights sum to 0",
        )

    components = {d.name: int(d.points) for d in details if d.points is not None}
    weighted = sum(
        Decimal(components[name]) * Decimal(weights[name]) for name in F5_COMPONENTS
    )
    total = int(round(weighted / Decimal(weight_sum)))
    total = max(0, min(100, total))
    explanation = (
        f"MarketHealthScore {total}/100 = weighted mean of six F-5 components "
        + "("
        + ", ".join(f"{d.name}={d.points}[{d.band}]" for d in details)
        + ")"
    )
    score = MarketHealthScore(
        ts=as_of,
        components=components,
        total=total,
        explanation=explanation,
    )
    return MarketHealthScoreBuild(
        score=score,
        components=details,
        unavailable_reason=None,
    )


def _absent(name: str, explanation: str, inputs: Mapping[str, str]) -> ComponentScoreDetail:
    return ComponentScoreDetail(
        name=name, points=None, band=None, explanation=explanation, inputs=inputs
    )


def _present(
    name: str, points: int, band: str, explanation: str, inputs: Mapping[str, str]
) -> ComponentScoreDetail:
    return ComponentScoreDetail(
        name=name, points=points, band=band, explanation=explanation, inputs=inputs
    )


def _score_trend_quality(
    config: MarketHealthConfig, health_result: MarketHealthResult | None
) -> ComponentScoreDetail:
    pts_cfg = config.component_points.trend_quality
    if health_result is None:
        return _absent(
            "trend_quality",
            "no market health assessment for trend_quality",
            {},
        )
    label = health_result.assessment.dimensions.get("trend_quality")
    band = _TREND_POINTS.get(label or "")
    inputs = {"label": label or "missing"}
    if band is None:
        return _absent(
            "trend_quality",
            f"trend_quality label {label!r} is not scoreable",
            inputs,
        )
    points = getattr(pts_cfg, band)
    return _present(
        "trend_quality",
        points,
        band,
        f"trend_quality {label} → {points} pts",
        inputs,
    )


def _score_breadth(
    config: MarketHealthConfig, breadth: UniverseBreadthResult
) -> ComponentScoreDetail:
    pts_cfg = config.component_points.breadth
    cfg = config.breadth
    inputs = {
        "advances": str(breadth.advances),
        "declines": str(breadth.declines),
        "neutral": str(breadth.neutral),
        "coverage": str(breadth.coverage),
        "min_coverage": str(cfg.min_coverage),
        "universe_size": str(breadth.universe_size),
        "scored": str(breadth.scored),
    }
    if breadth.universe_size <= 0 or breadth.coverage < Decimal(str(cfg.min_coverage)):
        return _absent(
            "breadth",
            (
                f"breadth coverage {breadth.coverage} below min_coverage "
                f"{cfg.min_coverage}"
            ),
            inputs,
        )
    ratio = breadth.advance_ratio
    if ratio is None:
        return _absent(
            "breadth",
            "breadth undeterminable — advances+declines is zero",
            inputs,
        )
    inputs = {**inputs, "advance_ratio": str(ratio)}
    strong = Decimal(str(cfg.strong_ratio))
    weak = Decimal(str(cfg.weak_ratio))
    if ratio >= strong:
        band = "strong"
    elif ratio <= weak:
        band = "weak"
    else:
        band = "mid"
    points = getattr(pts_cfg, band)
    return _present(
        "breadth",
        points,
        band,
        f"universe advance ratio {ratio} → {band} → {points} pts",
        inputs,
    )


def _score_liquidity(
    config: MarketHealthConfig, liquidity: LiquidityAggregateResult
) -> ComponentScoreDetail:
    pts_cfg = config.component_points.liquidity
    cfg = config.liquidity
    inputs = {
        "member_count": str(liquidity.member_count),
        "min_members": str(cfg.min_members),
        "median_turnover": (
            None if liquidity.median_turnover is None else str(liquidity.median_turnover)
        ),
        "healthy_median_turnover": str(cfg.healthy_median_turnover),
        "weak_median_turnover": str(cfg.weak_median_turnover),
        "method": liquidity.method,
    }
    # JSON-friendly: drop None values that aren't strings
    inputs = {k: ("" if v is None else v) for k, v in inputs.items()}
    if (
        liquidity.median_turnover is None
        or liquidity.member_count < cfg.min_members
    ):
        return _absent(
            "liquidity",
            (
                f"insufficient liquidity members ({liquidity.member_count} "
                f"< {cfg.min_members}) or missing median"
            ),
            inputs,
        )
    median = liquidity.median_turnover
    healthy = Decimal(str(cfg.healthy_median_turnover))
    weak = Decimal(str(cfg.weak_median_turnover))
    if median >= healthy:
        band = "healthy"
    elif median <= weak:
        band = "weak"
    else:
        band = "mid"
    points = getattr(pts_cfg, band)
    return _present(
        "liquidity",
        points,
        band,
        f"median turnover {median} → {band} → {points} pts",
        inputs,
    )


def _score_volatility(
    config: MarketHealthConfig, health_result: MarketHealthResult | None
) -> ComponentScoreDetail:
    pts_cfg = config.component_points.volatility
    if health_result is None:
        return _absent(
            "volatility",
            "no market health assessment for volatility",
            {},
        )
    label = health_result.assessment.dimensions.get("volatility")
    band = _VOL_POINTS.get(label or "")
    inputs = {"label": label or "missing"}
    if band is None:
        return _absent(
            "volatility",
            f"volatility label {label!r} is not scoreable",
            inputs,
        )
    points = getattr(pts_cfg, band)
    return _present(
        "volatility",
        points,
        band,
        f"volatility {label} → {points} pts",
        inputs,
    )


def _score_institutional(
    config: MarketHealthConfig,
    flow: InstitutionalFlowSession | None,
    *,
    as_of: datetime,
) -> ComponentScoreDetail:
    pts_cfg = config.component_points.institutional_strength
    cfg = config.institutional
    if flow is None:
        return _absent(
            "institutional_strength",
            "no institutional flow session available",
            {},
        )
    age_days = (as_of.date() - flow.session_date).days
    inputs = {
        "session_date": flow.session_date.isoformat(),
        "fii_net": str(flow.fii_net),
        "dii_net": str(flow.dii_net),
        "combined_net": str(flow.fii_net + flow.dii_net),
        "provisional": str(flow.provisional),
        "source_id": flow.source_id,
        "age_days": str(age_days),
        "max_age_sessions": str(cfg.max_age_sessions),
    }
    if age_days < 0 or age_days > cfg.max_age_sessions:
        return _absent(
            "institutional_strength",
            (
                f"institutional flow session_date {flow.session_date} is stale "
                f"(age_days={age_days} > max_age_sessions={cfg.max_age_sessions})"
            ),
            inputs,
        )
    combined = flow.fii_net + flow.dii_net
    strong_buy = Decimal(str(cfg.strong_buy_cr))
    mild_buy = Decimal(str(cfg.mild_buy_cr))
    mild_sell = Decimal(str(cfg.mild_sell_cr))
    strong_sell = Decimal(str(cfg.strong_sell_cr))
    if combined >= strong_buy:
        band = "strong_buy"
    elif combined >= mild_buy:
        band = "mild_buy"
    elif combined <= strong_sell:
        band = "strong_sell"
    elif combined <= mild_sell:
        band = "mild_sell"
    else:
        band = "balanced"
    points = getattr(pts_cfg, band)
    return _present(
        "institutional_strength",
        points,
        band,
        f"combined FII+DII net {combined} ₹ Cr → {band} → {points} pts",
        inputs,
    )


def _score_gap_stability(
    config: MarketHealthConfig, gap: GapStabilityResult
) -> ComponentScoreDetail:
    pts_cfg = config.component_points.gap_stability
    cfg = config.gap_stability
    inputs = {
        "gap_days": str(gap.gap_days),
        "scored_days": str(gap.scored_days),
        "window": str(cfg.window),
        "stability_ratio": (
            "" if gap.stability_ratio is None else str(gap.stability_ratio)
        ),
        "gap_pct_threshold": str(gap.gap_pct_threshold),
    }
    if gap.stability_ratio is None or gap.scored_days < cfg.window:
        return _absent(
            "gap_stability",
            (
                f"gap stability insufficient "
                f"(scored_days={gap.scored_days} < window={cfg.window})"
            ),
            inputs,
        )
    ratio = gap.stability_ratio
    strong = Decimal(str(cfg.strong_stability))
    weak = Decimal(str(cfg.weak_stability))
    if ratio >= strong:
        band = "strong"
    elif ratio <= weak:
        band = "weak"
    else:
        band = "mid"
    points = getattr(pts_cfg, band)
    return _present(
        "gap_stability",
        points,
        band,
        f"gap stability ratio {ratio} → {band} → {points} pts",
        inputs,
    )
