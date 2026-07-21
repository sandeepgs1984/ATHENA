"""Strategy Framework (M4.4) — deterministic selection policies over completed
decision artifacts + watchlist memberships. Coordinates evaluation only; no
analytical calculation."""

from athena.strategy.base import Strategy
from athena.strategy.framework import StrategyFramework
from athena.strategy.models import (
    InstrumentView,
    MatchProposal,
    StrategyExecution,
    StrategyMatch,
    StrategyResult,
    StrategySummary,
)
from athena.strategy.strategies import (
    REFERENCE_STRATEGIES,
    BreakoutStrategy,
    ConfigurableStrategy,
    MeanReversionStrategy,
    MomentumStrategy,
    SectorRotationStrategy,
    SwingStrategy,
)

__all__ = [
    "REFERENCE_STRATEGIES",
    "BreakoutStrategy",
    "ConfigurableStrategy",
    "InstrumentView",
    "MatchProposal",
    "MeanReversionStrategy",
    "MomentumStrategy",
    "SectorRotationStrategy",
    "Strategy",
    "StrategyExecution",
    "StrategyFramework",
    "StrategyMatch",
    "StrategyResult",
    "StrategySummary",
    "SwingStrategy",
]
