"""Outcome statistics and the sufficiency gate (DX-5, ADR-010).

The gate is the point of this module. Computing an expectancy is arithmetic;
deciding whether an expectancy *means* anything is the judgement DX-5 was
created to make, and leaving it to the reader is how an unvalidated method
acquires undeserved credibility.

The DarvaX deck's own failure is instructive: it reports winners (Tarmat +36%,
BSL +65%, Adani Power +80%) with no sample size, no loss rate, and no period.
Producing a tidy expectancy from a thin sample inside ATHENA would repeat that
error with better typography. So a summary that does not clear the thresholds
below reports its numbers **and** an explicit verdict of
``EXPERIMENTAL_UNVALIDATED``, with the reasons attached.
"""

from __future__ import annotations

from collections.abc import Sequence
from decimal import Decimal

from athena.darvax.validation.models import (
    SimulatedTrade,
    ValidationSummary,
)

_PCT = Decimal("0.01")

#: Minimum closed trades before an expectancy is worth quoting. Not a
#: statistical guarantee — a breakout system's returns are fat-tailed and no
#: fixed number makes a sample representative — but below this the estimate is
#: dominated by a handful of outcomes and should not be read as an edge.
MIN_CLOSED_TRADES = 200

#: Minimum trading days the evidence must span. A breakout methodology that is
#: only ever measured in one market regime tells you about that regime, not
#: about the methodology. Roughly two years of Indian trading sessions.
MIN_TRADING_DAYS = 500


def summarise(
    trades: Sequence[SimulatedTrade],
    *,
    instruments: int,
    trading_days: int,
) -> ValidationSummary:
    """Aggregate simulated trades, then judge whether the aggregate is evidence."""
    closed = [t for t in trades if t.is_closed and t.return_pct is not None]
    open_trades = [t for t in trades if not t.is_closed]
    wins = [t for t in closed if t.return_pct > 0]
    losses = [t for t in closed if t.return_pct <= 0]

    def mean(values: list[Decimal]) -> Decimal | None:
        return (sum(values) / Decimal(len(values))).quantize(_PCT) if values else None

    gross_win = sum((t.return_pct for t in wins), Decimal(0))
    gross_loss = abs(sum((t.return_pct for t in losses), Decimal(0)))

    exits: dict[str, int] = {}
    for trade in trades:
        exits[trade.exit_reason.value] = exits.get(trade.exit_reason.value, 0) + 1

    limitations = _limitations(closed, open_trades, trading_days)
    sufficient = (
        len(closed) >= MIN_CLOSED_TRADES and trading_days >= MIN_TRADING_DAYS
    )

    return ValidationSummary(
        instruments=instruments,
        trades_closed=len(closed),
        trades_open=len(open_trades),
        wins=len(wins),
        losses=len(losses),
        win_rate=(
            (Decimal(len(wins)) / Decimal(len(closed))).quantize(Decimal("0.0001"))
            if closed
            else None
        ),
        expectancy_pct=mean([t.return_pct for t in closed]),
        avg_win_pct=mean([t.return_pct for t in wins]),
        avg_loss_pct=mean([t.return_pct for t in losses]),
        # An infinite profit factor is an artefact of a sample with no losses,
        # not an edge, so it is reported as unavailable rather than as a number.
        profit_factor=(
            (gross_win / gross_loss).quantize(_PCT) if gross_loss > 0 else None
        ),
        max_drawdown_pct=_max_drawdown(closed),
        avg_bars_held=mean([Decimal(t.bars_held) for t in closed]),
        exits_by_reason=exits,
        trading_days=trading_days,
        first_entry=min((t.entry_date for t in trades), default=None),
        last_exit=max((t.exit_date for t in closed), default=None),
        sufficient=sufficient,
        # The label only comes off on evidence. Nothing else removes it.
        verdict="VALIDATED" if sufficient else "EXPERIMENTAL_UNVALIDATED",
        limitations=limitations,
    )


def _max_drawdown(closed: Sequence[SimulatedTrade]) -> Decimal | None:
    """Deepest peak-to-trough decline of the sequential equity curve.

    Trades are compounded in exit order — the order they would actually have
    been realised in. Summing returns instead would understate drawdown, since
    a 50% loss needs a 100% gain to recover.
    """
    if not closed:
        return None
    ordered = sorted(closed, key=lambda t: (t.exit_date, t.instrument_id))
    equity = Decimal(1)
    peak = Decimal(1)
    worst = Decimal(0)
    for trade in ordered:
        equity *= Decimal(1) + trade.return_pct / Decimal(100)
        peak = max(peak, equity)
        if peak > 0:
            worst = min(worst, (equity - peak) / peak)
    return (worst * Decimal(100)).quantize(_PCT)


def _limitations(
    closed: Sequence[SimulatedTrade],
    open_trades: Sequence[SimulatedTrade],
    trading_days: int,
) -> tuple[str, ...]:
    """Every reason these numbers should not be trusted, stated up front."""
    notes: list[str] = []

    if len(closed) < MIN_CLOSED_TRADES:
        notes.append(
            f"Sample too small: {len(closed)} closed trades against a "
            f"{MIN_CLOSED_TRADES}-trade floor. An expectancy from this few "
            "outcomes is dominated by a handful of trades."
        )
    if trading_days < MIN_TRADING_DAYS:
        notes.append(
            f"Period too short: {trading_days} trading days against a "
            f"{MIN_TRADING_DAYS}-day floor. A breakout system measured in one "
            "market regime tells you about that regime, not the methodology."
        )
    if open_trades:
        share = len(open_trades) / (len(open_trades) + len(closed)) * 100
        note = (
            f"{len(open_trades)} position(s) — {share:.0f}% of all entries — were "
            "still open when the data ended and are excluded from closed-trade "
            "statistics; their eventual outcomes are unknown and could move "
            "every number here."
        )
        if share >= 20:
            # Direction matters: a breakout method cuts losers on the stop and
            # lets winners ride, so unresolved trades skew towards the winners.
            # Excluding them therefore biases the result *against* the method,
            # and reporting the exclusion without that direction would let a bad
            # number look worse than the evidence supports.
            note += (
                " At this share the exclusion is not neutral: losers exit "
                "quickly on the stop while winners stay open, so the trades "
                "dropped here are disproportionately the good ones and these "
                "figures are likely pessimistic."
            )
        notes.append(note)

    # Structural caveats that hold regardless of how much data arrives.
    notes.append(
        "Survivorship bias: the universe is the instruments in the ledger "
        "today, so names delisted during the period are absent and their "
        "outcomes — disproportionately bad — are missing."
    )
    notes.append(
        "Costs excluded: no brokerage, STT, slippage or impact. A breakout "
        "system trades often, so real returns are materially lower."
    )
    notes.append(
        "Drawdown assumes one position at a time compounding the full account, "
        "which the deck's own 'divide capital into 10 parts' rule contradicts. "
        "With a negative expectancy this compounding drives the curve towards "
        "-100% and the figure should be read as a property of that assumption, "
        "not as a realistic account outcome."
    )
    notes.append(
        "Fills are idealised: entries at the next bar's open and stops filled "
        "exactly at the stop, with no gap-through modelling."
    )
    return tuple(notes)
