"""DX-5: outcome simulation, statistics, and the sufficiency gate.

The load-bearing test here is the **no-lookahead** one. Every other number in
this milestone is worthless if a signal can see a bar the trader could not, and
lookahead is the single easiest way to produce a backtest that looks excellent
and is a lie. It is asserted by instrumenting the engine and recording the
largest bar index it was ever shown.
"""

from __future__ import annotations

from datetime import datetime, timedelta
from decimal import Decimal
from zoneinfo import ZoneInfo

import pytest

from athena.darvax.validation import (
    MIN_CLOSED_TRADES,
    MIN_TRADING_DAYS,
    ExitReason,
    SimulatedTrade,
    simulate_instrument,
    summarise,
)
from athena.domain.enums import Timeframe
from athena.domain.market import Candle

IST = ZoneInfo("Asia/Kolkata")
BASE = datetime(2026, 1, 1, 9, 15, tzinfo=IST)


def bar(index: int, low: float, high: float, close: float, open_: float | None = None):
    return Candle(
        instrument_id="NSE:TEST",
        timeframe=Timeframe.D1,
        ts_open=BASE + timedelta(days=index),
        open=Decimal(str(open_ if open_ is not None else close)),
        high=Decimal(str(high)),
        low=Decimal(str(low)),
        close=Decimal(str(close)),
        volume=100_000,
        source="dx5-test",
    )


def box_then(*tail: Candle) -> list[Candle]:
    """A consolidation long enough to confirm a box, then the supplied bars."""
    base = [bar(i, 100 + (i % 4), 104 + (i % 4), 102 + (i % 4)) for i in range(24)]
    return base + list(tail)


# --------------------------------------------------------------------------- #
# 1. No lookahead — the assertion the whole milestone rests on
# --------------------------------------------------------------------------- #


def test_the_engine_is_never_shown_a_bar_beyond_the_one_being_evaluated(monkeypatch):
    """Instruments the engine and records the highest timestamp it ever sees.

    If any call received a bar later than the decision bar, the simulation would
    be trading on information the owner could not have had — and every statistic
    downstream would be fiction.
    """
    import athena.darvax.validation.simulator as sim

    seen: list[tuple[int, datetime]] = []
    real = sim.evaluate_signal

    def spy(candles, methodology=None):
        seen.append((len(candles), candles[-1].ts_open))
        return real(candles, methodology)

    monkeypatch.setattr(sim, "evaluate_signal", spy)

    candles = box_then(
        bar(24, 104, 112, 111), bar(25, 110, 114, 113), bar(26, 108, 115, 114)
    )
    simulate_instrument(candles)

    assert seen, "the engine was never called"
    for length, last_ts in seen:
        # The window must be a strict prefix, and its final bar must be the bar
        # at that index — never a later one.
        assert candles[length - 1].ts_open == last_ts
        assert length <= len(candles) - 1, (
            "the engine was shown the final bar, leaving no bar to trade at"
        )


def test_entry_is_the_next_bars_open_not_the_signal_bars_close():
    """The signal is known at the close of bar t; the first tradable price is
    the open of t+1. Filling at the signal bar's close would be lookahead."""
    breakout = bar(24, 104, 112, 111)
    entry_bar = bar(25, 110, 118, 117, open_=112.5)
    trades = simulate_instrument(box_then(breakout, entry_bar, bar(26, 115, 120, 119)))

    assert trades, "expected a breakout entry"
    assert trades[0].entry_price == Decimal("112.5")
    assert trades[0].entry_date == entry_bar.ts_open


# --------------------------------------------------------------------------- #
# 2. Exits
# --------------------------------------------------------------------------- #


def test_a_stop_is_filled_at_the_stop_not_at_the_close():
    """A stop is a resting order, so a bar that trades through it fills there —
    scoring the exit at the close would flatter or punish the trade arbitrarily.
    """
    trades = simulate_instrument(
        box_then(
            bar(24, 104, 112, 111),
            bar(25, 110, 114, 113, open_=112),
            # Collapses far below the 10% stop (112 * 0.9 = 100.8).
            bar(26, 80, 113, 82),
        )
    )
    assert trades and trades[0].exit_reason is ExitReason.STOP
    assert trades[0].exit_price == Decimal("112") * Decimal("0.9")
    assert trades[0].return_pct == Decimal("-10.0000")


def test_an_unresolved_position_is_reported_open_never_as_a_win():
    """Counting an open position as a non-loss is how backtests flatter
    themselves; it is excluded from closed statistics instead."""
    trades = simulate_instrument(
        box_then(bar(24, 104, 112, 111), bar(25, 110, 116, 115), bar(26, 113, 118, 117))
    )
    assert trades
    assert trades[-1].exit_reason is ExitReason.OPEN
    assert trades[-1].return_pct is None
    assert not trades[-1].is_closed
    assert not trades[-1].is_win


def test_no_trades_when_the_history_is_too_short():
    assert simulate_instrument([bar(i, 100, 104, 102) for i in range(5)]) == ()


# --------------------------------------------------------------------------- #
# 3. Determinism
# --------------------------------------------------------------------------- #


def test_simulating_the_same_candles_twice_gives_identical_trades():
    candles = box_then(
        bar(24, 104, 112, 111), bar(25, 110, 114, 113), bar(26, 80, 113, 82)
    )
    assert simulate_instrument(candles) == simulate_instrument(candles)


# --------------------------------------------------------------------------- #
# 4. Statistics
# --------------------------------------------------------------------------- #


def closed(return_pct: str, day: int, instrument: str = "NSE:A") -> SimulatedTrade:
    return SimulatedTrade(
        instrument_id=instrument,
        entry_date=BASE + timedelta(days=day),
        entry_price=Decimal(100),
        exit_date=BASE + timedelta(days=day + 5),
        exit_price=Decimal(100) * (Decimal(1) + Decimal(return_pct) / 100),
        exit_reason=ExitReason.RULE_C,
        bars_held=5,
        return_pct=Decimal(return_pct),
        stop_price=Decimal(90),
    )


def test_expectancy_win_rate_and_profit_factor():
    trades = [closed("10", 1), closed("-5", 2), closed("20", 3), closed("-5", 4)]
    s = summarise(trades, instruments=1, trading_days=600)

    assert s.trades_closed == 4 and s.wins == 2 and s.losses == 2
    assert s.win_rate == Decimal("0.5000")
    assert s.expectancy_pct == Decimal("5.00")
    assert s.avg_win_pct == Decimal("15.00")
    assert s.avg_loss_pct == Decimal("-5.00")
    assert s.profit_factor == Decimal("3.00")


def test_profit_factor_is_unavailable_rather_than_infinite():
    """A sample with no losses has no profit factor; reporting one would be an
    artefact of the sample, not an edge."""
    s = summarise([closed("10", 1), closed("5", 2)], instruments=1, trading_days=600)
    assert s.profit_factor is None


def test_drawdown_compounds_rather_than_summing():
    """Summing returns understates drawdown — a 50% loss needs a 100% gain to
    recover, which only compounding captures."""
    s = summarise([closed("-50", 1), closed("-50", 2)], instruments=1, trading_days=600)
    assert s.max_drawdown_pct == Decimal("-75.00")


def test_open_trades_are_excluded_from_closed_statistics():
    open_trade = SimulatedTrade(
        instrument_id="NSE:A", entry_date=BASE, entry_price=Decimal(100),
        exit_date=None, exit_price=None, exit_reason=ExitReason.OPEN,
        bars_held=3, return_pct=None, stop_price=Decimal(90),
    )
    s = summarise([closed("10", 1), open_trade], instruments=1, trading_days=600)
    assert s.trades_closed == 1 and s.trades_open == 1
    assert s.expectancy_pct == Decimal("10.00")


def test_empty_input_yields_no_statistics_rather_than_zeros():
    """Zero expectancy would read as 'measured and found flat'; None reads as
    'not measured', which is the truth."""
    s = summarise([], instruments=0, trading_days=0)
    assert s.expectancy_pct is None and s.win_rate is None
    assert s.max_drawdown_pct is None and s.profit_factor is None


# --------------------------------------------------------------------------- #
# 5. The sufficiency gate — the judgement DX-5 exists to make
# --------------------------------------------------------------------------- #


def test_a_thin_sample_is_never_declared_validated():
    s = summarise([closed("10", 1)], instruments=1, trading_days=600)
    assert s.sufficient is False
    assert s.verdict == "EXPERIMENTAL_UNVALIDATED"
    assert any("Sample too small" in note for note in s.limitations)


def test_a_short_period_is_never_declared_validated():
    """Even a large sample from one regime tells you about that regime."""
    trades = [closed("10", i) for i in range(MIN_CLOSED_TRADES + 10)]
    s = summarise(trades, instruments=100, trading_days=80)
    assert s.sufficient is False
    assert s.verdict == "EXPERIMENTAL_UNVALIDATED"
    assert any("Period too short" in note for note in s.limitations)


def test_the_label_comes_off_only_when_both_thresholds_clear():
    trades = [closed("10", i) for i in range(MIN_CLOSED_TRADES)]
    s = summarise(trades, instruments=100, trading_days=MIN_TRADING_DAYS)
    assert s.sufficient is True
    assert s.verdict == "VALIDATED"


def test_structural_limitations_are_always_reported_even_when_sufficient():
    """Survivorship, costs and idealised fills do not go away with more data,
    so they are stated regardless of the verdict."""
    trades = [closed("10", i) for i in range(MIN_CLOSED_TRADES)]
    s = summarise(trades, instruments=100, trading_days=MIN_TRADING_DAYS)
    joined = " ".join(s.limitations)
    assert "Survivorship bias" in joined
    assert "Costs excluded" in joined
    assert "idealised" in joined


def test_a_large_open_share_is_reported_with_its_direction():
    """Excluding open trades is not neutral: losers stop out and winners ride,
    so a big open share means the figures are pessimistic. Saying only that some
    were excluded would leave the reader to assume it cuts both ways."""
    open_trade = SimulatedTrade(
        instrument_id="NSE:A", entry_date=BASE, entry_price=Decimal(100),
        exit_date=None, exit_price=None, exit_reason=ExitReason.OPEN,
        bars_held=3, return_pct=None, stop_price=Decimal(90),
    )
    s = summarise(
        [closed("-5", 1), open_trade, open_trade], instruments=1, trading_days=600
    )
    note = next(n for n in s.limitations if "still open" in n)
    assert "pessimistic" in note


def test_drawdown_states_the_capital_assumption_behind_it():
    """A -100% drawdown from full-capital compounding is a property of that
    assumption, not a realistic account outcome — and the deck's own rule is to
    divide capital into ten parts."""
    s = summarise([closed("-50", 1)], instruments=1, trading_days=600)
    assert any("divide capital into 10 parts" in n for n in s.limitations)


@pytest.mark.parametrize("threshold", [MIN_CLOSED_TRADES, MIN_TRADING_DAYS])
def test_thresholds_are_documented_constants_not_magic_numbers(threshold: int):
    assert threshold > 0
