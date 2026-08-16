"""Outcome simulation over DarvaX's own methodology (DX-5, ADR-010).

**No new methodology.** Entries and exits come from replaying the DX-3 engine
bar by bar — `evaluate_signal` on progressively longer prefixes — so what is
validated is exactly what the screener shows. A separate "backtest
interpretation" of the rules would validate something the owner never sees.

**No lookahead, by construction.** The engine only ever receives
``candles[: t + 1]``, so a signal at bar *t* cannot consult bar *t+1*. Entry is
then taken at the **open of bar t+1** — the first price a trader could actually
have transacted at after seeing the signal. This is structural rather than a
convention someone must remember: there is no code path that hands the engine a
future bar.

**Why this lives inside DarvaX.** ADR-010 pins the DarvaX→ATHENA import surface,
and a DX-4 test asserts DarvaX never imports an ATHENA analytical engine —
which `athena.backtest` is. Reusing ATHENA's backtester would therefore have
required widening that surface and coupling the satellite's validation to
ATHENA's engine. DarvaX owns its EMA, its config, its schema and its UI for the
same reason; it owns its validation too.
"""

from __future__ import annotations

from collections.abc import Sequence
from decimal import Decimal

from athena.darvax.config import DarvaxMethodologyConfig
from athena.darvax.signals.engine import evaluate_signal
from athena.darvax.signals.models import DarvaxSignalType
from athena.darvax.validation.models import ExitReason, SimulatedTrade
from athena.domain.market import Candle

_HUNDRED = Decimal(100)
_PCT = Decimal("0.0001")

#: Bars the engine needs before a box can plausibly have formed. Below this the
#: engine simply returns NO_BOX, so starting earlier wastes work without
#: changing any result.
MIN_BARS_BEFORE_FIRST_SIGNAL = 10


def _pct(numerator: Decimal, denominator: Decimal) -> Decimal | None:
    if denominator <= 0:
        return None
    return (numerator / denominator * _HUNDRED).quantize(_PCT)


def simulate_instrument(
    candles: Sequence[Candle],
    methodology: DarvaxMethodologyConfig | None = None,
) -> tuple[SimulatedTrade, ...]:
    """Replay one instrument's history and return its round trips.

    Entry: the engine reports ``BREAKOUT`` (Darvas rule B) and no position is
    open. Filled at the next bar's open.

    Exit, whichever comes first:

    * the configured stop is traded through — filled **at the stop**, not at the
      close, since the stop is an order rather than an observation;
    * the engine reports ``BELOW_BOX_BOTTOM`` (rule C, the methodology's own
      exit) — filled at the next bar's open;
    * the data ends, in which case the trade is reported ``OPEN`` and excluded
      from closed-trade statistics.

    Args:
        candles: oldest-first, one instrument, one timeframe.
    """
    config = methodology or DarvaxMethodologyConfig()
    trades: list[SimulatedTrade] = []
    if len(candles) <= MIN_BARS_BEFORE_FIRST_SIGNAL + 1:
        return ()

    position: dict | None = None

    for index in range(MIN_BARS_BEFORE_FIRST_SIGNAL, len(candles) - 1):
        # The engine sees history up to and including `index` — never beyond.
        window = candles[: index + 1]
        next_bar = candles[index + 1]

        if position is not None:
            entry_price = position["entry_price"]
            stop = position["stop_price"]
            position["bars_held"] += 1
            position["max_adverse"] = min(position["max_adverse"], next_bar.low)
            position["max_favourable"] = max(position["max_favourable"], next_bar.high)

            if stop is not None and next_bar.low <= stop:
                trades.append(_close(position, next_bar, stop, ExitReason.STOP))
                position = None
                continue

            signal = evaluate_signal(window, config)
            if signal.signal_type is DarvaxSignalType.BELOW_BOX_BOTTOM:
                # Rule C is observed at this bar's close, so the fill is the
                # next bar's open — the first tradable price after the signal.
                trades.append(
                    _close(position, next_bar, next_bar.open, ExitReason.RULE_C)
                )
                position = None
            continue

        signal = evaluate_signal(window, config)
        if signal.signal_type is not DarvaxSignalType.BREAKOUT:
            continue

        entry_price = next_bar.open
        if entry_price <= 0:
            continue
        stop_price = _stop_for(entry_price, signal, config)
        position = {
            "instrument_id": signal.instrument_id,
            "entry_date": next_bar.ts_open,
            "entry_price": entry_price,
            "stop_price": stop_price,
            "bars_held": 0,
            "max_adverse": next_bar.low,
            "max_favourable": next_bar.high,
        }

    if position is not None:
        trades.append(
            SimulatedTrade(
                instrument_id=position["instrument_id"],
                entry_date=position["entry_date"],
                entry_price=position["entry_price"],
                exit_date=None,
                exit_price=None,
                exit_reason=ExitReason.OPEN,
                bars_held=position["bars_held"],
                return_pct=None,
                stop_price=position["stop_price"],
                max_adverse_pct=_pct(
                    position["max_adverse"] - position["entry_price"],
                    position["entry_price"],
                ),
                max_favourable_pct=_pct(
                    position["max_favourable"] - position["entry_price"],
                    position["entry_price"],
                ),
            )
        )
    return tuple(trades)


def _stop_for(
    entry_price: Decimal,
    signal: object,
    config: DarvaxMethodologyConfig,
) -> Decimal | None:
    """Stop level from the configured policy, measured off the actual fill.

    Taken from the entry price rather than the signal's own stop, because the
    signal's stop references the signal bar's close while the position was
    opened at the next bar's open — using the former would score the trade
    against a level it was never protected by.
    """
    if config.stop_policy == "canonical_darvas":
        pct = config.canonical_stop_pct
    elif config.stop_policy == "darvax_tight":
        pct = config.tight_stop_pct
    else:
        # The EMA ladder is a close-below rule, not a price level knowable at
        # entry. Rule C already provides a structural exit, so an EMA-policy
        # simulation runs stopless rather than inventing a level.
        return None
    return entry_price * (Decimal(1) - pct / _HUNDRED)


def _close(
    position: dict, bar: Candle, price: Decimal, reason: ExitReason
) -> SimulatedTrade:
    entry_price = position["entry_price"]
    return SimulatedTrade(
        instrument_id=position["instrument_id"],
        entry_date=position["entry_date"],
        entry_price=entry_price,
        exit_date=bar.ts_open,
        exit_price=price,
        exit_reason=reason,
        bars_held=position["bars_held"],
        return_pct=_pct(price - entry_price, entry_price),
        stop_price=position["stop_price"],
        max_adverse_pct=_pct(position["max_adverse"] - entry_price, entry_price),
        max_favourable_pct=_pct(position["max_favourable"] - entry_price, entry_price),
    )
