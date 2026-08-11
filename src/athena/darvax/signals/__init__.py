"""DarvaX signal engine (DX-3, ADR-010).

Composes DX-2's measurements into a box breakout/retest state machine, attaches
the documented stop policy, and emits :class:`DarvaxSignal` records carrying
their own computed, persistable explanation and evidence trace.

A ``DarvaxSignal`` is **never** an ATHENA ``Decision`` and is never converted
into one — ADR-010 forbids that conversion explicitly, including as a
convenience for the DX-5 backtest harness. ATHENA's scoring, confidence, risk,
Decision, TradePlan, and universe machinery cannot read anything produced here.

Signals remain labelled ``EXPERIMENTAL_UNVALIDATED`` until DX-5 generates real
expectancy/win-rate/drawdown evidence: the source deck supplies none.
"""

from __future__ import annotations

from athena.darvax.signals.ema import ema_series, latest_ema
from athena.darvax.signals.engine import evaluate_signal
from athena.darvax.signals.models import (
    DAR_CARD_TEXT,
    DarvasRule,
    DarvaxSignal,
    DarvaxSignalType,
    DarvaxStop,
    SignalEvidence,
    StopBasis,
)
from athena.darvax.signals.stops import compute_stop

__all__ = [
    "DAR_CARD_TEXT",
    "DarvasRule",
    "DarvaxSignal",
    "DarvaxSignalType",
    "DarvaxStop",
    "SignalEvidence",
    "StopBasis",
    "compute_stop",
    "ema_series",
    "evaluate_signal",
    "latest_ema",
]
