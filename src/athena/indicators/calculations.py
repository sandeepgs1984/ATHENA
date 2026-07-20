"""Pure indicator calculations (M3.2).

Deterministic Decimal math over canonical candle data. Each function returns the
measured value(s) or ``None`` when there is insufficient history. No I/O, no
clock, no randomness. These are objective measurements — no interpretation.

Formulas follow the standard/Wilder definitions:
- SMA: arithmetic mean of the last ``period`` closes.
- EMA: seeded with the SMA of the first ``period`` values, then
  EMA_t = (value - EMA_{t-1}) * k + EMA_{t-1}, k = 2/(period+1).
- RSI: Wilder's smoothing of average gains/losses over ``period``.
- ATR: Wilder's smoothing of True Range over ``period``.
- MACD: EMA(fast) - EMA(slow); signal = EMA(signal) of the MACD line.
- ADX: Wilder's directional movement system over ``period``.
- Volume MA: arithmetic mean of the last ``period`` volumes.
"""

from __future__ import annotations

from collections.abc import Sequence
from decimal import Decimal

from athena.domain.market import Candle


def sma(closes: Sequence[Decimal], period: int) -> Decimal | None:
    if len(closes) < period:
        return None
    window = closes[-period:]
    return sum(window, Decimal(0)) / Decimal(period)


def ema_series(values: Sequence[Decimal], period: int) -> list[Decimal]:
    """Full EMA series (length len(values) - period + 1), or [] if insufficient."""
    if len(values) < period:
        return []
    k = Decimal(2) / (Decimal(period) + Decimal(1))
    ema = sum(values[:period], Decimal(0)) / Decimal(period)
    out = [ema]
    for value in values[period:]:
        ema = (value - ema) * k + ema
        out.append(ema)
    return out


def ema(values: Sequence[Decimal], period: int) -> Decimal | None:
    series = ema_series(values, period)
    return series[-1] if series else None


def rsi(closes: Sequence[Decimal], period: int) -> Decimal | None:
    if len(closes) < period + 1:
        return None
    changes = [closes[i] - closes[i - 1] for i in range(1, len(closes))]
    gains = [c if c > 0 else Decimal(0) for c in changes]
    losses = [-c if c < 0 else Decimal(0) for c in changes]
    avg_gain = sum(gains[:period], Decimal(0)) / Decimal(period)
    avg_loss = sum(losses[:period], Decimal(0)) / Decimal(period)
    for i in range(period, len(changes)):
        avg_gain = (avg_gain * (period - 1) + gains[i]) / Decimal(period)
        avg_loss = (avg_loss * (period - 1) + losses[i]) / Decimal(period)
    if avg_loss == 0:
        return Decimal(100)
    if avg_gain == 0:
        return Decimal(0)
    rs = avg_gain / avg_loss
    return Decimal(100) - Decimal(100) / (Decimal(1) + rs)


def _true_ranges(candles: Sequence[Candle]) -> list[Decimal]:
    trs: list[Decimal] = []
    for i in range(1, len(candles)):
        high, low, prev_close = candles[i].high, candles[i].low, candles[i - 1].close
        trs.append(max(high - low, abs(high - prev_close), abs(low - prev_close)))
    return trs


def atr(candles: Sequence[Candle], period: int) -> Decimal | None:
    if len(candles) < period + 1:
        return None
    trs = _true_ranges(candles)
    value = sum(trs[:period], Decimal(0)) / Decimal(period)
    for i in range(period, len(trs)):
        value = (value * (period - 1) + trs[i]) / Decimal(period)
    return value


def macd(
    closes: Sequence[Decimal], fast: int, slow: int, signal: int
) -> tuple[Decimal, Decimal, Decimal] | None:
    if len(closes) < slow + signal:
        return None
    fast_series = ema_series(closes, fast)
    slow_series = ema_series(closes, slow)
    # Align: fast_series is longer by (slow - fast); trim its head to match slow_series.
    offset = slow - fast
    macd_line = [fast_series[offset + i] - slow_series[i] for i in range(len(slow_series))]
    signal_series = ema_series(macd_line, signal)
    if not signal_series:
        return None
    macd_val = macd_line[-1]
    signal_val = signal_series[-1]
    return macd_val, signal_val, macd_val - signal_val


def _wilder_smooth(values: Sequence[Decimal], period: int) -> list[Decimal]:
    """Wilder running sum: seed = sum(first period), then s = s - s/period + value."""
    s = sum(values[:period], Decimal(0))
    out = [s]
    for value in values[period:]:
        s = s - s / Decimal(period) + value
        out.append(s)
    return out


def adx(candles: Sequence[Candle], period: int) -> tuple[Decimal, Decimal, Decimal] | None:
    """Return (ADX, +DI, -DI) or None. Needs ~2*period+1 candles."""
    if len(candles) < 2 * period + 1:
        return None
    plus_dm: list[Decimal] = []
    minus_dm: list[Decimal] = []
    for i in range(1, len(candles)):
        up = candles[i].high - candles[i - 1].high
        down = candles[i - 1].low - candles[i].low
        plus_dm.append(up if (up > down and up > 0) else Decimal(0))
        minus_dm.append(down if (down > up and down > 0) else Decimal(0))
    trs = _true_ranges(candles)

    tr_s = _wilder_smooth(trs, period)
    pdm_s = _wilder_smooth(plus_dm, period)
    mdm_s = _wilder_smooth(minus_dm, period)

    plus_di = [Decimal(100) * p / t if t != 0 else Decimal(0)
               for p, t in zip(pdm_s, tr_s, strict=True)]
    minus_di = [Decimal(100) * m / t if t != 0 else Decimal(0)
                for m, t in zip(mdm_s, tr_s, strict=True)]
    dx = [
        Decimal(100) * abs(p - m) / (p + m) if (p + m) != 0 else Decimal(0)
        for p, m in zip(plus_di, minus_di, strict=True)
    ]
    if len(dx) < period:
        return None
    adx_val = sum(dx[:period], Decimal(0)) / Decimal(period)
    for value in dx[period:]:
        adx_val = (adx_val * (period - 1) + value) / Decimal(period)
    return adx_val, plus_di[-1], minus_di[-1]


def volume_ma(volumes: Sequence[int], period: int) -> Decimal | None:
    if len(volumes) < period:
        return None
    window = volumes[-period:]
    return Decimal(sum(window)) / Decimal(period)
