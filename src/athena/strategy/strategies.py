"""Reference strategies (M4.4).

Five concrete selection policies driven entirely by ``StrategyRuleCfg``. Each
consumes only completed decision facts and watchlist memberships — no indicator
calculation, no engine access. The shared :class:`ConfigurableStrategy` applies
the declarative filters; each subclass fixes its identity and default rule.

A threshold set against an UNKNOWN value never matches: missing analytical
values exclude an instrument rather than being defaulted.
"""

from __future__ import annotations

from collections.abc import Sequence

from athena.config.models import StrategyRuleCfg
from athena.strategy.base import Strategy
from athena.strategy.models import InstrumentView, MatchProposal


class ConfigurableStrategy(Strategy):
    """A strategy whose selection is fully described by a StrategyRuleCfg."""

    _name = ""
    _version = "1.0"
    _description = ""

    def __init__(self, rule: StrategyRuleCfg) -> None:
        self._rule = rule

    @property
    def name(self) -> str:
        return self._name

    @property
    def version(self) -> str:
        return self._version

    @property
    def description(self) -> str:
        return self._description

    def select(self, views: Sequence[InstrumentView]) -> tuple[MatchProposal, ...]:
        proposals: list[MatchProposal] = []
        for view in sorted(views, key=lambda v: v.instrument_id):
            matched, reason = self._evaluate(view)
            if matched:
                proposals.append(MatchProposal(view=view, reason=reason))
        return tuple(proposals)

    # ------------------------------------------------------------- internals

    def _evaluate(self, view: InstrumentView) -> tuple[bool, str]:
        rule = self._rule
        clauses: list[str] = []

        if rule.decisions:
            if view.decision_type not in rule.decisions:
                return False, ""
            clauses.append(f"decision {view.decision_type}")

        if rule.direction is not None:
            if view.direction != rule.direction:
                return False, ""
            clauses.append(f"direction {view.direction}")

        if rule.watchlists_any:
            overlap = sorted(view.watchlists & set(rule.watchlists_any))
            if not overlap:
                return False, ""
            clauses.append(f"in {overlap}")

        if rule.min_score is not None:
            if view.composite_score is None or view.composite_score < rule.min_score:
                return False, ""
            clauses.append(f"score {view.composite_score}>={rule.min_score}")

        if rule.min_confidence is not None:
            if view.confidence_value is None or view.confidence_value < rule.min_confidence:
                return False, ""
            clauses.append(f"confidence {view.confidence_value}>={rule.min_confidence}")

        if rule.max_risk is not None:
            if view.risk_value is None or view.risk_value > rule.max_risk:
                return False, ""
            clauses.append(f"risk {view.risk_value}<={rule.max_risk}")

        reason = f"{self._name}: " + ("; ".join(clauses) if clauses else "no constraints")
        return True, reason


class MomentumStrategy(ConfigurableStrategy):
    _name = "momentum"
    _description = "High-conviction or improving decisions with strong composite scores."


class SwingStrategy(ConfigurableStrategy):
    _name = "swing"
    _description = "Trade/watch decisions carried by adequate confidence."


class BreakoutStrategy(ConfigurableStrategy):
    _name = "breakout"
    _description = "Long trade decisions with high composite scores."


class MeanReversionStrategy(ConfigurableStrategy):
    _name = "mean_reversion"
    _description = "Improving watch/wait decisions kept within a risk ceiling."


class SectorRotationStrategy(ConfigurableStrategy):
    _name = "sector_rotation"
    _description = "Constructive decisions surfacing in high-conviction or improving lists."


#: strategy id → concrete class, for building from StrategyConfig.
REFERENCE_STRATEGIES: dict[str, type[ConfigurableStrategy]] = {
    "momentum": MomentumStrategy,
    "swing": SwingStrategy,
    "breakout": BreakoutStrategy,
    "mean_reversion": MeanReversionStrategy,
    "sector_rotation": SectorRotationStrategy,
}
