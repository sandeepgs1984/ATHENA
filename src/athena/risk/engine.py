"""Risk Engine (M3.5).

Answers one question: "What is the level of exposure associated with the current
evaluation?" It measures exposure and uncertainty only — independent of
opportunity, and never a recommendation or position size.

Six independently explainable dimensions, each degrading to explicit UNKNOWN:
- Volatility Risk         : regime volatility label
- Liquidity Risk          : Volume MA vs configured minimum (low volume = high risk)
- Gap Risk                : regime gap label
- Event Risk              : calendar expiries / scheduled events
- Market Environment Risk : market-health labels (weak/elevated = higher risk)
- Concentration Indicator : investable-universe breadth (narrow = higher risk)

Higher value = more risk. Pure and replayable: injected ``as_of``, Decimal math,
config-driven risk points. Consumes approved artifacts only.
"""

from __future__ import annotations

from collections.abc import Mapping
from datetime import datetime
from decimal import Decimal

from athena.config.models import RiskAssessmentConfig
from athena.domain.market import CalendarContext
from athena.indicators.models import IndicatorName, IndicatorResult, IndicatorStatus
from athena.market_health.models import MarketHealthResult
from athena.regime.models import RegimeResult
from athena.risk.models import (
    RiskAssessment,
    RiskContribution,
    RiskDimension,
    RiskLevel,
    RiskStatus,
)
from athena.universe.engine import UniverseResult

_ZERO, _HUNDRED = Decimal(0), Decimal(100)
_TWO_DP = Decimal("0.01")


def _fmt2(value: Decimal) -> str:
    """Compact 2dp rendering for owner-facing explanations (avoids long Decimal tails)."""
    return format(value.quantize(_TWO_DP), "f")


def _clamp(value: Decimal) -> Decimal:
    return max(_ZERO, min(_HUNDRED, value))


class RiskEngine:
    """Deterministic, artifact-driven exposure assessment."""

    def __init__(self, config: RiskAssessmentConfig) -> None:
        self._config = config

    def _level(self, value: Decimal) -> RiskLevel:
        if value < Decimal(self._config.levels.low_below):
            return RiskLevel.LOW
        if value >= Decimal(self._config.levels.high_at_or_above):
            return RiskLevel.HIGH
        return RiskLevel.MEDIUM

    def _ok(self, name, value, contributions, explanation) -> RiskDimension:
        v = _clamp(value)
        return RiskDimension(name=name, status=RiskStatus.OK, value=v, level=self._level(v),
                             contributions=tuple(contributions), explanation=explanation)

    @staticmethod
    def _unknown(name, explanation) -> RiskDimension:
        return RiskDimension(name=name, status=RiskStatus.UNKNOWN, value=None, level=None,
                             contributions=(), explanation=explanation)

    @staticmethod
    def _regime_label(regime: RegimeResult | None, dimension: str) -> str | None:
        if regime is None:
            return None
        return next((e.outcome.value for e in regime.evidence if e.dimension == dimension), None)

    def assess(
        self,
        instrument_id: str,
        *,
        as_of: datetime,
        regime: RegimeResult | None = None,
        market_health: MarketHealthResult | None = None,
        indicators: Mapping[IndicatorName, IndicatorResult] | None = None,
        calendar_context: CalendarContext | None = None,
        universe: UniverseResult | None = None,
    ) -> RiskAssessment:
        indicators = dict(indicators or {})
        dims = {
            "volatility_risk": self._volatility_risk(regime),
            "liquidity_risk": self._liquidity_risk(indicators),
            "gap_risk": self._gap_risk(regime),
            "event_risk": self._event_risk(calendar_context),
            "market_environment_risk": self._market_environment_risk(market_health),
            "concentration_indicator": self._concentration_indicator(universe),
        }
        unknown_stats = {"unknown_dimensions": sum(1 for d in dims.values() if not d.is_known)}
        overall = self._overall(dims)
        return RiskAssessment(
            assessment_id=f"risk-{instrument_id}-{as_of.isoformat()}", ts=as_of,
            dimensions=dims, unknown_stats=unknown_stats, **overall)

    # ------------------------------------------------------------- dimensions

    def _volatility_risk(self, regime) -> RiskDimension:
        label = self._regime_label(regime, "volatility")
        pts = self._config.volatility_points.get(label) if label else None
        if pts is None:
            return self._unknown("volatility_risk", f"regime volatility not available (label={label})")
        return self._ok("volatility_risk", Decimal(pts),
                        [RiskContribution("regime:volatility", label,
                                          f"volatility {label} → risk {pts}")],
                        f"volatility risk {pts} from regime {label}")

    def _liquidity_risk(self, indicators) -> RiskDimension:
        vma = indicators.get(IndicatorName.VOLUME_MA)
        if vma is None or vma.status is not IndicatorStatus.OK:
            return self._unknown("liquidity_risk", "Volume MA indicator unavailable")
        cfg = self._config.liquidity
        vma_val = vma.values["value"]
        risk = cfg.low_liquidity_risk if vma_val < Decimal(cfg.min_volume_ma) else cfg.ok_liquidity_risk
        return self._ok("liquidity_risk", Decimal(risk),
                        [RiskContribution("indicator:VOLUME_MA", "VOLUME_MA",
                                          f"Volume MA {vma_val} vs min {cfg.min_volume_ma} "
                                          f"→ risk {risk}")],
                        f"liquidity risk {risk} from Volume MA")

    def _gap_risk(self, regime) -> RiskDimension:
        label = self._regime_label(regime, "gap")
        pts = self._config.gap_points.get(label) if label else None
        if pts is None:
            return self._unknown("gap_risk", f"regime gap not available (label={label})")
        return self._ok("gap_risk", Decimal(pts),
                        [RiskContribution("regime:gap", label, f"gap {label} → risk {pts}")],
                        f"gap risk {pts} from regime {label}")

    def _event_risk(self, calendar_context) -> RiskDimension:
        if calendar_context is None:
            return self._unknown("event_risk", "no calendar context available")
        cfg = self._config.event
        if calendar_context.events:
            risk = cfg.event_risk
            detail = f"{len(calendar_context.events)} scheduled event(s)"
        elif calendar_context.is_weekly_expiry or calendar_context.is_monthly_expiry:
            risk = cfg.expiry_risk
            detail = "expiry session"
        else:
            risk = cfg.normal_risk
            detail = "no expiry or scheduled events"
        return self._ok("event_risk", Decimal(risk),
                        [RiskContribution("calendar", calendar_context.context_date.isoformat(),
                                          f"{detail} → risk {risk}")],
                        f"event risk {risk}: {detail}")

    def _market_environment_risk(self, market_health) -> RiskDimension:
        if market_health is None:
            return self._unknown("market_environment_risk", "no market health assessment available")
        contribs: list[RiskContribution] = []
        points: list[int] = []
        for dim, label in sorted(market_health.assessment.dimensions.items()):
            pts = self._config.market_env_points.get(label)
            if pts is None:
                continue
            points.append(pts)
            contribs.append(RiskContribution(f"market_health:{dim}", label,
                                             f"{dim}={label} → risk {pts}"))
        if not points:
            return self._unknown("market_environment_risk", "no scoreable market-health labels")
        avg = Decimal(sum(points)) / Decimal(len(points))
        return self._ok("market_environment_risk", avg, contribs,
                        f"market environment risk {_fmt2(avg)} = mean of {len(points)} label(s)")

    def _concentration_indicator(self, universe) -> RiskDimension:
        if universe is None:
            return self._unknown("concentration_indicator", "no universe result available")
        cfg = self._config.concentration
        included = int(universe.summary.get("included", 0))
        risk = cfg.concentrated_risk if included < cfg.min_universe_size else cfg.diversified_risk
        return self._ok("concentration_indicator", Decimal(risk),
                        [RiskContribution("universe", "summary",
                                          f"{included} eligible instrument(s) vs min "
                                          f"{cfg.min_universe_size} → risk {risk}")],
                        f"concentration indicator {risk} ({included} eligible instruments)")

    # ------------------------------------------------------------- aggregate

    def _overall(self, dims) -> dict:
        weights = self._config.weights.model_dump()
        weighted_sum = _ZERO
        known_weight = 0
        total_weight = sum(int(w) for w in weights.values())
        for name, dim in dims.items():
            if dim.is_known and dim.value is not None:
                w = int(weights[name])
                weighted_sum += dim.value * Decimal(w)
                known_weight += w
        if known_weight == 0:
            return dict(overall_status=RiskStatus.UNKNOWN, overall_value=None,
                        overall_level=None, completeness=_ZERO,
                        explanation="overall risk UNKNOWN: no dimension could be determined")
        value = _clamp(weighted_sum / Decimal(known_weight))
        completeness = Decimal(known_weight) / Decimal(total_weight)
        return dict(overall_status=RiskStatus.OK, overall_value=value,
                    overall_level=self._level(value), completeness=completeness,
                    explanation=(f"overall risk {_fmt2(value)} ({self._level(value).value}), "
                                 f"completeness {completeness:.2f}"))
