"""Validation domain objects (DX-5, ADR-010).

DX-5 exists to answer one question: **does DarvaX's methodology earn the removal
of its `EXPERIMENTAL_UNVALIDATED` label?** The source deck ships no backtest
evidence at all — only cherry-picked winners and testimonial screenshots — so
until this milestone produces real expectancy, win/loss, drawdown and sample
size, the label stands.

That framing shapes every type here. A summary carries its **sample size and
its limitations alongside its numbers**, because an expectancy quoted without
them is exactly the failure mode the deck itself commits, and reproducing it
inside ATHENA would be worse than publishing nothing.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from decimal import Decimal
from enum import Enum


class ExitReason(str, Enum):
    """Why a simulated position closed."""

    STOP = "STOP"
    """Price traded through the configured stop."""
    RULE_C = "RULE_C"
    """Close fell beneath the box floor — Darvas rule C, the methodology's own
    exit. Taken at the next bar's open."""
    OPEN = "OPEN"
    """Still open when the data ran out. Excluded from closed-trade statistics
    and reported separately, because counting an unresolved position as a
    non-loss is how backtests flatter themselves."""


@dataclass(frozen=True, slots=True)
class SimulatedTrade:
    """One entry-to-exit round trip produced by replaying the DX-3 engine.

    Prices are the ones a trader could actually have transacted at: entry is the
    bar *after* the signal bar, never the signal bar's own close.
    """

    instrument_id: str
    entry_date: datetime
    entry_price: Decimal
    exit_date: datetime | None
    exit_price: Decimal | None
    exit_reason: ExitReason
    bars_held: int
    return_pct: Decimal | None
    """Realised return. ``None`` while the trade is still open."""
    stop_price: Decimal | None
    max_adverse_pct: Decimal | None = None
    """Worst intra-trade drawdown against the position, from entry."""
    max_favourable_pct: Decimal | None = None

    @property
    def is_closed(self) -> bool:
        return self.exit_reason is not ExitReason.OPEN

    @property
    def is_win(self) -> bool:
        return self.is_closed and self.return_pct is not None and self.return_pct > 0


@dataclass(frozen=True, slots=True)
class ValidationSummary:
    """Aggregate outcome statistics, inseparable from their caveats.

    ``verdict`` is deliberately part of the summary rather than left to the
    reader: a number set this small must not be presented as though it settles
    anything, and burying that in prose someone can skip is how unvalidated
    methods acquire undeserved credibility.
    """

    instruments: int
    trades_closed: int
    trades_open: int
    wins: int
    losses: int
    win_rate: Decimal | None
    """Fraction of closed trades that returned > 0. ``None`` when no trades."""
    expectancy_pct: Decimal | None
    """Mean return per closed trade, in percent."""
    avg_win_pct: Decimal | None
    avg_loss_pct: Decimal | None
    profit_factor: Decimal | None
    """Gross wins / gross losses. ``None`` when there are no losses to divide
    by — an infinite profit factor is an artefact of a tiny sample, not an edge."""
    max_drawdown_pct: Decimal | None
    """Deepest peak-to-trough decline of the sequential equity curve."""
    avg_bars_held: Decimal | None
    exits_by_reason: dict[str, int] = field(default_factory=dict)

    #: Sufficiency
    trading_days: int = 0
    first_entry: datetime | None = None
    last_exit: datetime | None = None
    sufficient: bool = False
    verdict: str = "EXPERIMENTAL_UNVALIDATED"
    limitations: tuple[str, ...] = ()
