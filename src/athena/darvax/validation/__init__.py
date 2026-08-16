"""DarvaX validation (DX-5, ADR-010).

Replays the DX-3 engine bar by bar to produce outcome statistics, and judges
whether those statistics constitute evidence. The `EXPERIMENTAL_UNVALIDATED`
label comes off only when they do.
"""

from athena.darvax.validation.models import (
    ExitReason,
    SimulatedTrade,
    ValidationSummary,
)
from athena.darvax.validation.simulator import (
    MIN_BARS_BEFORE_FIRST_SIGNAL,
    simulate_instrument,
)
from athena.darvax.validation.summary import (
    MIN_CLOSED_TRADES,
    MIN_TRADING_DAYS,
    summarise,
)

__all__ = [
    "MIN_BARS_BEFORE_FIRST_SIGNAL",
    "MIN_CLOSED_TRADES",
    "MIN_TRADING_DAYS",
    "ExitReason",
    "SimulatedTrade",
    "ValidationSummary",
    "simulate_instrument",
    "summarise",
]
