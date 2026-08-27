"""EM-2 SESSION_INVARIANT evidence: the 15 fields computed once per
(symbol, session T) and shared unchanged across all 9 accepted
checkpoints -- 13 PRIOR_HISTORY fields (derived from admitted daily bars
strictly before T) plus 2 SESSION_OPEN_CONTEXT fields (need T's own open,
still invariant since it is known before the first checkpoint).

Pure: no I/O, no clock. ``daily_bars`` may span the whole acquired
history; this module does its own "strictly before T" slicing so the
leakage boundary lives in exactly one place, matching
``regime_replay.reconstruct_session_regime``'s own convention.

Reuses ``athena.indicators.calculations`` completely unmodified.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from decimal import Decimal

from athena.explosive_move.evidence_values import DailyBar, EvidenceValue
from athena.indicators.calculations import adx, atr, atr_series, macd, rsi, sma, sma_series


@dataclass(frozen=True, slots=True)
class SessionInvariantEvidence:
    sma20_rel: EvidenceValue
    sma50_rel: EvidenceValue
    sma20_slope_5: EvidenceValue
    adx14: EvidenceValue
    rsi14: EvidenceValue
    macd_hist: EvidenceValue
    return_5d: EvidenceValue
    return_20d: EvidenceValue
    atr14: EvidenceValue
    atr14_norm: EvidenceValue
    range_compression_20: EvidenceValue
    regime_trend: EvidenceValue
    regime_volatility: EvidenceValue
    gap_pct: EvidenceValue
    regime_gap: EvidenceValue


def _prior_bars(daily_bars: tuple[DailyBar, ...], session_date: date) -> tuple[DailyBar, ...]:
    return tuple(sorted(
        (b for b in daily_bars if b.session_date < session_date), key=lambda b: b.session_date,
    ))


def compute_session_invariant_evidence(
    *,
    session_date: date,
    daily_bars: tuple[DailyBar, ...],
    session_open: Decimal,
    regime: dict | None,
) -> SessionInvariantEvidence:
    """``regime`` is one row from EM-1c's regime_by_session.json for this
    session_date (or None if session_date has no regime evidence at all)."""

    before = _prior_bars(daily_bars, session_date)
    closes = [b.close for b in before]
    n = len(before)

    def unk(min_n: int) -> EvidenceValue:
        return EvidenceValue.unknown(f"fewer than {min_n} admitted daily bars strictly before T (have {n})")

    sma20 = sma(closes, 20)
    sma20_rel = EvidenceValue.known(closes[-1] / sma20 - 1) if sma20 is not None else unk(20)

    sma50 = sma(closes, 50)
    sma50_rel = EvidenceValue.known(closes[-1] / sma50 - 1) if sma50 is not None else unk(50)

    sma20_series = sma_series(closes, 20)
    sma20_slope_5 = (
        EvidenceValue.known(sma20_series[-1] / sma20_series[-6] - 1)
        if len(sma20_series) >= 6 else unk(25)
    )

    adx_result = adx(before, 14)
    adx14 = EvidenceValue.known(adx_result[0]) if adx_result is not None else unk(29)

    rsi14_val = rsi(closes, 14)
    rsi14 = EvidenceValue.known(rsi14_val) if rsi14_val is not None else unk(15)

    macd_result = macd(closes, 12, 26, 9)
    macd_hist = EvidenceValue.known(macd_result[2]) if macd_result is not None else unk(35)

    return_5d = EvidenceValue.known(closes[-1] / closes[-6] - 1) if n >= 6 else unk(6)
    return_20d = EvidenceValue.known(closes[-1] / closes[-21] - 1) if n >= 21 else unk(21)

    atr14_val = atr(before, 14)
    atr14 = EvidenceValue.known(atr14_val) if atr14_val is not None else unk(15)
    atr14_norm = EvidenceValue.known(atr14_val / closes[-1]) if atr14_val is not None else EvidenceValue.unknown(
        "ATR14 is UNKNOWN"
    )

    atr_full_series = atr_series(before, 14)
    if len(atr_full_series) >= 20:
        window = atr_full_series[-20:]
        mean_atr = sum(window, Decimal(0)) / Decimal(len(window))
        range_compression_20 = EvidenceValue.known(atr_full_series[-1] / mean_atr)
    else:
        range_compression_20 = unk(34)

    def regime_field(key: str, unknown_label: str) -> EvidenceValue:
        if regime is None or regime[key] == unknown_label:
            reason = f"EM-1c regime evidence reports {unknown_label} for {session_date.isoformat()}"
            return EvidenceValue.unknown(reason)
        return EvidenceValue.known(regime[key])

    regime_trend = regime_field("trend", "TREND_UNKNOWN")
    regime_volatility = regime_field("volatility", "VOLATILITY_UNKNOWN")
    regime_gap = regime_field("gap", "GAP_UNKNOWN")

    if before:
        gap_pct = EvidenceValue.known(session_open / before[-1].close - 1)
    else:
        gap_pct = EvidenceValue.unknown("no admitted daily bar for T-1")

    return SessionInvariantEvidence(
        sma20_rel=sma20_rel, sma50_rel=sma50_rel, sma20_slope_5=sma20_slope_5, adx14=adx14,
        rsi14=rsi14, macd_hist=macd_hist, return_5d=return_5d, return_20d=return_20d,
        atr14=atr14, atr14_norm=atr14_norm, range_compression_20=range_compression_20,
        regime_trend=regime_trend, regime_volatility=regime_volatility,
        gap_pct=gap_pct, regime_gap=regime_gap,
    )
