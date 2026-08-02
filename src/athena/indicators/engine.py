"""Indicator Engine (M3.2).

Answers one question: "What does the data measure?" It computes deterministic
technical indicators from canonical candle data using configuration-driven
parameters, wrapping each into an immutable IndicatorResult with calculation
evidence. Explicit UNKNOWN when history is insufficient. Measurements only — no
signals, scores, or interpretation.

Pure and replayable: injected ``as_of``, Decimal math, params from
indicators.json. Provider/repository/intelligence independent.
"""

from __future__ import annotations

from collections.abc import Sequence
from datetime import datetime

from athena.config.models import IndicatorsConfig
from athena.domain.market import Candle
from athena.errors import ConfigError
from athena.indicators import calculations as calc
from athena.indicators.models import (
    IndicatorEvidence,
    IndicatorName,
    IndicatorResult,
    IndicatorStatus,
)

_CONFIG_KEY = {
    IndicatorName.SMA: "sma",
    IndicatorName.EMA: "ema",
    IndicatorName.RSI: "rsi",
    IndicatorName.ATR: "atr",
    IndicatorName.MACD: "macd",
    IndicatorName.ADX: "adx",
    IndicatorName.VOLUME_MA: "volume_ma",
    IndicatorName.VWAP: "vwap",
}


class IndicatorEngine:
    """Deterministic technical-indicator measurement layer."""

    def __init__(self, config: IndicatorsConfig) -> None:
        self._config = config

    def _params(self, name: IndicatorName) -> dict[str, int]:
        key = _CONFIG_KEY[name]
        if key not in self._config.params:
            raise ConfigError(f"indicators.json has no params for '{key}'")
        return dict(self._config.params[key])

    def compute(
        self, name: IndicatorName, candles: Sequence[Candle], *, as_of: datetime
    ) -> IndicatorResult:
        ordered = sorted(candles, key=lambda c: c.ts_open)
        params = self._params(name)
        closes = [c.close for c in ordered]
        handler = getattr(self, f"_{name.value.lower()}")
        return handler(ordered, closes, params, as_of)

    def compute_all(
        self, names: Sequence[IndicatorName], candles: Sequence[Candle], *, as_of: datetime
    ) -> dict[IndicatorName, IndicatorResult]:
        return {name: self.compute(name, candles, as_of=as_of) for name in names}

    # ------------------------------------------------------------- builders

    def _result(self, name, params, window_used, values, formula, inputs, explanation, as_of):
        status = IndicatorStatus.OK if values else IndicatorStatus.UNKNOWN
        return IndicatorResult(
            name=name, status=status, parameters=params, window_used=window_used,
            values=values,
            evidence=IndicatorEvidence(formula=formula, inputs=inputs, explanation=explanation),
            ts=as_of)

    @staticmethod
    def _unknown_inputs(available: int, required: int) -> dict[str, str]:
        return {"candles_available": str(available), "candles_required": str(required)}

    # ------------------------------------------------------------- indicators

    def _sma(self, ordered, closes, params, as_of):
        period = params["period"]
        value = calc.sma(closes, period)
        if value is None:
            return self._result(IndicatorName.SMA, params, len(closes), {},
                                "mean(last N closes)", self._unknown_inputs(len(closes), period),
                                f"insufficient history: need {period} closes, have {len(closes)}",
                                as_of)
        return self._result(IndicatorName.SMA, params, period, {"value": value},
                            "mean(last N closes)",
                            {"period": str(period), "last_close": str(closes[-1])},
                            f"SMA({period}) = {value}", as_of)

    def _ema(self, ordered, closes, params, as_of):
        period = params["period"]
        value = calc.ema(closes, period)
        if value is None:
            return self._result(IndicatorName.EMA, params, len(closes), {},
                                "EMA seeded by SMA, k=2/(N+1)",
                                self._unknown_inputs(len(closes), period),
                                f"insufficient history: need {period} closes, have {len(closes)}",
                                as_of)
        return self._result(IndicatorName.EMA, params, len(closes), {"value": value},
                            "EMA seeded by SMA, k=2/(N+1)",
                            {"period": str(period), "last_close": str(closes[-1])},
                            f"EMA({period}) = {value}", as_of)

    def _rsi(self, ordered, closes, params, as_of):
        period = params["period"]
        value = calc.rsi(closes, period)
        if value is None:
            return self._result(IndicatorName.RSI, params, len(closes), {},
                                "Wilder RSI = 100 - 100/(1+RS)",
                                self._unknown_inputs(len(closes), period + 1),
                                f"insufficient history: need {period + 1} closes, have {len(closes)}",
                                as_of)
        return self._result(IndicatorName.RSI, params, len(closes), {"value": value},
                            "Wilder RSI = 100 - 100/(1+RS)", {"period": str(period)},
                            f"RSI({period}) = {value}", as_of)

    def _atr(self, ordered, closes, params, as_of):
        period = params["period"]
        value = calc.atr(ordered, period)
        if value is None:
            return self._result(IndicatorName.ATR, params, len(ordered), {},
                                "Wilder ATR of True Range",
                                self._unknown_inputs(len(ordered), period + 1),
                                f"insufficient history: need {period + 1} candles, have {len(ordered)}",
                                as_of)
        return self._result(IndicatorName.ATR, params, len(ordered), {"value": value},
                            "Wilder ATR of True Range", {"period": str(period)},
                            f"ATR({period}) = {value}", as_of)

    def _macd(self, ordered, closes, params, as_of):
        fast, slow, signal = params["fast"], params["slow"], params["signal"]
        result = calc.macd(closes, fast, slow, signal)
        if result is None:
            return self._result(IndicatorName.MACD, params, len(closes), {},
                                "MACD = EMA(fast)-EMA(slow); signal = EMA(signal) of MACD",
                                self._unknown_inputs(len(closes), slow + signal),
                                f"insufficient history: need {slow + signal} closes, have {len(closes)}",
                                as_of)
        macd_val, signal_val, hist = result
        return self._result(IndicatorName.MACD, params, len(closes),
                            {"macd": macd_val, "signal": signal_val, "histogram": hist},
                            "MACD = EMA(fast)-EMA(slow); signal = EMA(signal) of MACD",
                            {"fast": str(fast), "slow": str(slow), "signal": str(signal)},
                            f"MACD={macd_val}, signal={signal_val}, histogram={hist}", as_of)

    def _adx(self, ordered, closes, params, as_of):
        period = params["period"]
        result = calc.adx(ordered, period)
        if result is None:
            return self._result(IndicatorName.ADX, params, len(ordered), {},
                                "Wilder ADX of DX from +DI/-DI",
                                self._unknown_inputs(len(ordered), 2 * period + 1),
                                f"insufficient history: need {2 * period + 1} candles, "
                                f"have {len(ordered)}", as_of)
        adx_val, plus_di, minus_di = result
        return self._result(IndicatorName.ADX, params, len(ordered),
                            {"adx": adx_val, "plus_di": plus_di, "minus_di": minus_di},
                            "Wilder ADX of DX from +DI/-DI", {"period": str(period)},
                            f"ADX({period})={adx_val}, +DI={plus_di}, -DI={minus_di}", as_of)

    def _volume_ma(self, ordered, closes, params, as_of):
        period = params["period"]
        volumes = [c.volume for c in ordered]
        value = calc.volume_ma(volumes, period)
        if value is None:
            return self._result(IndicatorName.VOLUME_MA, params, len(volumes), {},
                                "mean(last N volumes)",
                                self._unknown_inputs(len(volumes), period),
                                f"insufficient history: need {period} candles, have {len(volumes)}",
                                as_of)
        return self._result(IndicatorName.VOLUME_MA, params, period, {"value": value},
                            "mean(last N volumes)", {"period": str(period)},
                            f"Volume MA({period}) = {value}", as_of)

    def _vwap(self, ordered, closes, params, as_of):
        result = calc.vwap(ordered, as_of)
        if result is None:
            session_bars = sum(1 for c in ordered if c.ts_open.date() == as_of.date())
            return self._result(IndicatorName.VWAP, params, len(ordered), {},
                                "session-cumulative sum(typical_price * volume) / cumulative volume",
                                {"candles_fetched": str(len(ordered)), "session_bars": str(session_bars)},
                                f"no candles from {as_of.date()}'s session ({session_bars} of "
                                f"{len(ordered)} fetched candles match today)", as_of)
        vwap_value, deviation_pct = result
        return self._result(IndicatorName.VWAP, params, len(ordered),
                            {"vwap": vwap_value, "deviation_pct": deviation_pct},
                            "session-cumulative sum(typical_price * volume) / cumulative volume",
                            {"last_close": str(ordered[-1].close), "session_bars": str(len(ordered))},
                            f"VWAP = {vwap_value}, last close deviates {deviation_pct:.2f}%", as_of)
