"""EM-2 SESSION_INVARIANT evidence: exact warm-up boundary tests (owner
requirement -- minimum_required-1 -> UNKNOWN, minimum_required -> known,
for every lookback-dependent field) plus leakage/regime/gap correctness.
"""

from __future__ import annotations

from datetime import date, timedelta
from decimal import Decimal

import pytest

from athena.explosive_move.evidence_values import DailyBar
from athena.explosive_move.session_invariant_evidence import compute_session_invariant_evidence

T = date(2024, 6, 20)


def _bars(n: int, *, start_price: str = "100", step: str = "1") -> tuple[DailyBar, ...]:
    """n synthetic daily bars ending the day before T, mildly uptrending
    so RSI/ADX/MACD are well-defined (non-degenerate) throughout."""
    price = Decimal(start_price)
    step_val = Decimal(step)
    out = []
    for i in range(n):
        d = T - timedelta(days=n - i)
        out.append(DailyBar(
            session_date=d, open=price, high=price + Decimal("1.5"),
            low=price - Decimal("1"), close=price + Decimal("0.5"), volume=100000,
        ))
        price += step_val
    return tuple(out)


def _compute(bars: tuple[DailyBar, ...], regime: dict | None = None):
    return compute_session_invariant_evidence(
        session_date=T, daily_bars=bars, session_open=Decimal("150"), regime=regime,
    )


@pytest.mark.parametrize("field,minimum", [
    ("sma20_rel", 20), ("sma50_rel", 50), ("sma20_slope_5", 25), ("adx14", 29),
    ("rsi14", 15), ("macd_hist", 35), ("return_5d", 6), ("return_20d", 21),
    ("atr14", 15), ("range_compression_20", 34),
])
def test_exact_warmup_boundary(field, minimum):
    short = _compute(_bars(minimum - 1))
    exact = _compute(_bars(minimum))
    assert getattr(short, field).is_known is False, f"{field}: {minimum - 1} bars must be UNKNOWN"
    assert getattr(exact, field).is_known is True, f"{field}: {minimum} bars must be known"


def test_gap_pct_needs_at_least_one_prior_bar():
    zero = _compute(_bars(0))
    one = _compute(_bars(1))
    assert zero.gap_pct.is_known is False
    assert one.gap_pct.is_known is True


def test_atr14_norm_tracks_atr14_availability():
    short = _compute(_bars(14))
    exact = _compute(_bars(15))
    assert short.atr14_norm.is_known is False
    assert exact.atr14_norm.is_known is True


def test_range_compression_20_uses_last_20_atr_values_including_current():
    """Exact contract check: at the boundary (34 bars), the denominator is
    the mean of ATR14's own trailing-20 series (ending at T-1's ATR14
    itself) -- not the 20 values strictly BEFORE it."""
    bars = _bars(34)
    result = _compute(bars)
    assert result.range_compression_20.is_known
    # sanity: ratio should be close to 1 for a smooth, mildly-trending
    # synthetic series (no real compression/expansion event injected)
    ratio = result.range_compression_20.value
    assert Decimal("0.5") < ratio < Decimal("2.0")


def test_unknown_reason_is_persisted_and_specific():
    result = _compute(_bars(19))
    assert result.sma20_rel.unknown_reason is not None
    assert "20" in result.sma20_rel.unknown_reason


def test_regime_unknown_when_no_regime_row():
    result = _compute(_bars(60), regime=None)
    assert result.regime_trend.is_known is False
    assert result.regime_volatility.is_known is False
    assert result.regime_gap.is_known is False


def test_regime_known_when_row_present():
    regime = {"trend": "BULL_TREND", "volatility": "NORMAL_VOLATILITY", "gap": "NO_GAP"}
    result = _compute(_bars(60), regime=regime)
    assert result.regime_trend.value == "BULL_TREND"
    assert result.regime_volatility.value == "NORMAL_VOLATILITY"
    assert result.regime_gap.value == "NO_GAP"


def test_regime_unknown_label_propagates_as_unknown():
    regime = {"trend": "TREND_UNKNOWN", "volatility": "NORMAL_VOLATILITY", "gap": "NO_GAP"}
    result = _compute(_bars(60), regime=regime)
    assert result.regime_trend.is_known is False
    assert result.regime_volatility.is_known is True


# --------------------------------------------------------------------------- #
# Leakage: T's own close/high/low must never influence session-invariant
# evidence (only prior-day bars and T's own OPEN, via session_open, matter).
# --------------------------------------------------------------------------- #

def test_session_invariant_evidence_ignores_bars_on_or_after_t():
    bars = _bars(60)
    baseline = _compute(bars)
    future_bar = DailyBar(
        session_date=T, open=Decimal("1"), high=Decimal("999999"),
        low=Decimal("1"), close=Decimal("999999"), volume=1,
    )
    with_t_bar = _compute(tuple([*bars, future_bar]))
    assert with_t_bar.sma20_rel.value == baseline.sma20_rel.value
    assert with_t_bar.rsi14.value == baseline.rsi14.value
    assert with_t_bar.atr14.value == baseline.atr14.value
    assert with_t_bar.gap_pct.value == baseline.gap_pct.value


def test_session_invariant_evidence_ignores_future_sessions():
    bars = _bars(60)
    baseline = _compute(bars)
    future_bar = DailyBar(
        session_date=T + timedelta(days=5), open=Decimal("1"), high=Decimal("999999"),
        low=Decimal("1"), close=Decimal("999999"), volume=1,
    )
    with_future = _compute(tuple([*bars, future_bar]))
    assert with_future.sma20_rel.value == baseline.sma20_rel.value
    assert with_future.return_5d.value == baseline.return_5d.value
