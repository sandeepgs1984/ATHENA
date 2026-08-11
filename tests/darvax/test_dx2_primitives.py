"""DX-2 methodology primitives — hand-worked fixtures (ADR-010).

Every expected value below was traced by hand from the algorithm as documented
in the module under test, then asserted exactly. Where a fixture encodes a
non-obvious trace, the trace is written out in the test so a reviewer can check
the arithmetic without re-deriving it.

These tests cover measurement only. DX-2 produces no signals, so nothing here
asserts a trade decision.
"""

from __future__ import annotations

import dataclasses
import itertools
from datetime import datetime, timedelta
from decimal import Decimal
from zoneinfo import ZoneInfo

import pytest

from athena.darvax.primitives import (
    DarvaxPrimitiveError,
    RetracementZone,
    SwingKind,
    classify_retracement,
    current_box,
    darvas_boxes,
    distance_to_ath,
    fibonacci_levels,
    inside_bar,
    last_completed_swing_leg,
    range_contraction,
    volume_expansion,
    zigzag_swings,
)
from athena.domain.enums import Timeframe
from athena.domain.market import Candle

IST = ZoneInfo("Asia/Kolkata")
BASE_TS = datetime(2026, 3, 2, 9, 15, tzinfo=IST)


def _candles(
    highs: list[float],
    lows: list[float],
    *,
    volumes: list[int] | None = None,
    instrument_id: str = "NSE:SYN",
    timeframe: Timeframe = Timeframe.D1,
) -> list[Candle]:
    """Build a chronological series. open/close are pinned to the low so every
    bar is valid OHLC without the fixture having to state four numbers."""
    assert len(highs) == len(lows)
    vols = volumes if volumes is not None else [1_000] * len(highs)
    return [
        Candle(
            instrument_id=instrument_id,
            timeframe=timeframe,
            ts_open=BASE_TS + timedelta(days=i),
            open=Decimal(str(lows[i])),
            high=Decimal(str(highs[i])),
            low=Decimal(str(lows[i])),
            close=Decimal(str(lows[i])),
            volume=vols[i],
            source="test",
        )
        for i in range(len(highs))
    ]


def _flat(prices: list[float], **kw) -> list[Candle]:
    """Single-price bars (H == L), which makes swing traces trivial to verify."""
    return _candles(prices, prices, **kw)


# =========================================================================== #
# Darvas boxes
# =========================================================================== #

# Hand-worked fixture, confirmation_bars=3. Indices 0..15:
#   H: 10 11 12 11 11 11 10  9  9  9  9 10  9  9  9  9
#   L:  9 10 11 10 10 10  9  8  8  8  8  9  8  8  8  8
#
# Box 1 trace:
#   ceiling: high climbs to 12 at idx 2; idx 3,4,5 fail to exceed it, so at
#            idx 5 (5-2 == 3) the ceiling is confirmed at 12.
#   floor:   search starts idx 3 (low 10); idx 6 lows to 9, idx 7 lows to 8;
#            idx 8,9,10 fail to breach 8, so at idx 10 (10-7 == 3) the floor is
#            confirmed at 8. Box 1 = [8, 12], topmost.
# Box 2 trace (scan resumes idx 11):
#   ceiling: 10 at idx 11; idx 12,13,14 fail to exceed → confirmed at idx 14.
#   floor:   search starts idx 12 (low 8); idx 13,14,15 fail to breach → floor
#            confirmed at idx 15. Box 2 = [8, 10], NOT topmost (10 < 12).
_BOX_HIGHS = [10, 11, 12, 11, 11, 11, 10, 9, 9, 9, 9, 10, 9, 9, 9, 9]
_BOX_LOWS = [9, 10, 11, 10, 10, 10, 9, 8, 8, 8, 8, 9, 8, 8, 8, 8]


def test_darvas_box_hand_worked_two_boxes():
    boxes = darvas_boxes(_candles(_BOX_HIGHS, _BOX_LOWS), confirmation_bars=3)

    assert len(boxes) == 2

    first = boxes[0]
    assert first.top == Decimal("12")
    assert first.bottom == Decimal("8")
    assert first.top_index == 2
    assert first.bottom_index == 7
    assert first.top_confirmed_index == 5
    assert first.bottom_confirmed_index == 10
    assert first.is_topmost is True
    assert first.height == Decimal("4")
    assert first.top_ts == BASE_TS + timedelta(days=2)
    assert first.bottom_ts == BASE_TS + timedelta(days=7)

    second = boxes[1]
    assert second.top == Decimal("10")
    assert second.bottom == Decimal("8")
    assert second.top_index == 11
    assert second.bottom_index == 12
    assert second.top_confirmed_index == 14
    assert second.bottom_confirmed_index == 15
    assert second.is_topmost is False, "10 is below the earlier box's 12"


def test_current_box_returns_the_latest_completed_box():
    box = current_box(_candles(_BOX_HIGHS, _BOX_LOWS), confirmation_bars=3)
    assert box is not None
    assert (box.top, box.bottom) == (Decimal("10"), Decimal("8"))


def test_darvas_box_breakout_before_floor_confirms_yields_no_box():
    """Hand-worked: ceiling 12 confirmed at idx 4, then idx 5 highs to 15 —
    clearing the ceiling before any floor was confirmed. Per the documented
    invalidation rule that box never formed, and the remaining bars are too few
    to confirm a new one, so the result is empty."""
    highs = [10, 12, 11, 11, 11, 15, 16, 16]
    lows = [9, 11, 10, 10, 10, 14, 15, 15]
    assert darvas_boxes(_candles(highs, lows), confirmation_bars=3) == ()


def test_darvas_box_insufficient_history_returns_empty_not_error():
    """"Cannot know yet" is reported honestly rather than raising."""
    assert darvas_boxes(_candles([10, 11], [9, 10]), confirmation_bars=3) == ()
    assert current_box(_candles([10, 11], [9, 10]), confirmation_bars=3) is None


def test_darvas_box_confirmation_bars_changes_the_result():
    """Guards against the parameter being silently ignored."""
    candles = _candles(_BOX_HIGHS, _BOX_LOWS)
    assert darvas_boxes(candles, confirmation_bars=3) != darvas_boxes(
        candles, confirmation_bars=1
    )


def test_darvas_box_rejects_non_positive_confirmation_bars():
    with pytest.raises(DarvaxPrimitiveError, match="confirmation_bars"):
        darvas_boxes(_candles(_BOX_HIGHS, _BOX_LOWS), confirmation_bars=0)


# =========================================================================== #
# ZigZag swings
# =========================================================================== #


def test_zigzag_hand_worked_confirmed_pivots_only():
    """Hand-worked with single-price bars [100, 90, 95, 120, 110, 130] at 10%:

    idx 1 (90) is a 10% fall from 100 → confirms a swing HIGH at idx 0 (100).
    idx 2 (95) is only +5.6% off the 90 low → not yet a reversal.
    idx 3 (120) is +33% off 90 → confirms a swing LOW at idx 1 (90).
    idx 5 (130) becomes the running high but is never reversed from, so it is
    deliberately NOT reported — an unconfirmed extreme is not a swing.
    """
    swings = zigzag_swings(
        _flat([100, 90, 95, 120, 110, 130]), threshold_pct=Decimal("10")
    )

    assert [(s.kind, s.index, s.price) for s in swings] == [
        (SwingKind.HIGH, 0, Decimal("100")),
        (SwingKind.LOW, 1, Decimal("90")),
    ]
    assert swings[0].ts == BASE_TS
    assert all(s.price == s.price for s in swings)


def test_zigzag_alternates_kinds():
    swings = zigzag_swings(
        _flat([100, 80, 100, 80, 100, 80, 100]), threshold_pct=Decimal("10")
    )
    kinds = [s.kind for s in swings]
    assert len(kinds) >= 3
    for earlier, later in itertools.pairwise(kinds):
        assert earlier != later, f"pivots must alternate, got {kinds}"


def test_zigzag_monotonic_climb_confirms_the_starting_low_and_no_high():
    """A monotonic climb 10 -> 14 is +40% off the start, which is more than the
    10% threshold — so the opening low *is* a confirmed swing LOW. What is
    absent is a swing HIGH: price never reversed downward, so the running high
    stays unconfirmed. Asserting both halves pins the semantics in place."""
    swings = zigzag_swings(_flat([10, 11, 12, 13, 14]), threshold_pct=Decimal("10"))
    assert [(s.kind, s.index, s.price) for s in swings] == [
        (SwingKind.LOW, 0, Decimal("10"))
    ]


def test_zigzag_no_threshold_move_at_all_returns_empty():
    """Price that never travels the threshold in either direction yields no
    confirmed pivot whatsoever."""
    assert zigzag_swings(_flat([100, 101, 100, 101]), threshold_pct=Decimal("10")) == ()


def test_zigzag_threshold_is_respected():
    prices = _flat([100, 96, 100, 96, 100])
    assert zigzag_swings(prices, threshold_pct=Decimal("10")) == ()
    assert zigzag_swings(prices, threshold_pct=Decimal("3")) != ()


def test_last_completed_swing_leg():
    swings = zigzag_swings(
        _flat([100, 80, 100, 80, 100]), threshold_pct=Decimal("10")
    )
    leg = last_completed_swing_leg(swings)
    assert leg is not None
    assert leg == (swings[-2], swings[-1])
    assert last_completed_swing_leg(swings[:1]) is None
    assert last_completed_swing_leg(()) is None


# =========================================================================== #
# Fibonacci levels
# =========================================================================== #


def test_fibonacci_levels_exact_arithmetic():
    """swing 100 -> 200, height 100, so each level is 200 - pct."""
    fib = fibonacci_levels(Decimal("100"), Decimal("200"))
    assert fib.height == Decimal("100")
    assert fib.levels == (
        (Decimal("23.6"), Decimal("176.40")),
        (Decimal("38.2"), Decimal("161.80")),
        (Decimal("50.0"), Decimal("150.00")),
        (Decimal("61.8"), Decimal("138.20")),
    )


@pytest.mark.parametrize(
    ("price", "expected_pct", "expected_zone"),
    [
        (Decimal("190"), Decimal("10"), RetracementZone.SHALLOW),
        (Decimal("176.4"), Decimal("23.6"), RetracementZone.VERY_STRONG_TREND),
        (Decimal("170"), Decimal("30"), RetracementZone.VERY_STRONG_TREND),
        (Decimal("161.8"), Decimal("38.2"), RetracementZone.VERY_STRONG_TREND),
        (Decimal("155"), Decimal("45"), RetracementZone.MODERATE),
        (Decimal("150"), Decimal("50"), RetracementZone.ACCUMULATION),
        (Decimal("145"), Decimal("55"), RetracementZone.ACCUMULATION),
        (Decimal("138.2"), Decimal("61.8"), RetracementZone.ACCUMULATION),
        (Decimal("120"), Decimal("80"), RetracementZone.DEEP),
    ],
)
def test_fibonacci_retracement_zones(price, expected_pct, expected_zone):
    """Boundaries are inclusive at both ends of each named band, matching the
    deck's closed-range wording ("between 23.6 - 38.2%", "Zone 50 - 61.8%")."""
    fib = fibonacci_levels(Decimal("100"), Decimal("200"), price=price)
    assert fib.retracement_pct == expected_pct
    assert fib.zone is expected_zone


def test_fibonacci_zero_height_swing_is_undefined_not_zero():
    """Nothing to retrace, so the percentage is None rather than a fabricated 0."""
    fib = fibonacci_levels(Decimal("150"), Decimal("150"), price=Decimal("150"))
    assert fib.retracement_pct is None
    assert fib.zone is RetracementZone.UNDEFINED
    assert all(price == Decimal("150") for _, price in fib.levels)


def test_fibonacci_without_price_reports_no_zone():
    fib = fibonacci_levels(Decimal("100"), Decimal("200"))
    assert fib.price is None
    assert fib.retracement_pct is None
    assert fib.zone is RetracementZone.UNDEFINED


def test_fibonacci_rejects_inverted_swing():
    with pytest.raises(DarvaxPrimitiveError, match="must be >="):
        fibonacci_levels(Decimal("200"), Decimal("100"))


def test_classify_retracement_is_usable_standalone():
    assert classify_retracement(Decimal("0")) is RetracementZone.SHALLOW
    assert classify_retracement(Decimal("100")) is RetracementZone.DEEP


# =========================================================================== #
# Distance to observed ATH
# =========================================================================== #


def test_distance_to_ath_hand_worked():
    """highs [10, 20, 15]; last close is the last bar's low (15).
    (20 - 15) / 20 * 100 == 25%."""
    result = distance_to_ath(_candles([10, 20, 15], [9, 19, 15]))
    assert result.ath == Decimal("20")
    assert result.ath_index == 1
    assert result.ath_ts == BASE_TS + timedelta(days=1)
    assert result.close == Decimal("15")
    assert result.distance_pct == Decimal("25")
    assert result.at_ath is False
    assert result.bars_examined == 3


def test_distance_to_ath_at_the_high_is_zero_and_flagged():
    result = distance_to_ath(_candles([10, 20], [9, 20]))
    assert result.distance_pct == Decimal("0")
    assert result.at_ath is True


def test_distance_to_ath_never_reports_a_negative_distance():
    """A close above the observed ATH clamps to 0 rather than going negative."""
    candles = _candles([10, 12], [9, 12])
    result = distance_to_ath(candles)
    assert result.distance_pct >= Decimal("0")
    assert result.at_ath is True


# =========================================================================== #
# Range contraction
# =========================================================================== #


def test_range_contraction_hand_worked():
    """Ranges [5, 5, 1, 1]: recent mean 1, baseline mean 5, ratio 0.2."""
    candles = _candles([15, 15, 11, 11], [10, 10, 10, 10])
    result = range_contraction(
        candles, recent_bars=2, baseline_bars=2, max_ratio=Decimal("0.6")
    )
    assert result.recent_mean_range == Decimal("1")
    assert result.baseline_mean_range == Decimal("5")
    assert result.ratio == Decimal("0.2")
    assert result.is_contracting is True


def test_range_contraction_windows_do_not_overlap():
    """Baseline must exclude the recent window; if it overlapped, an expanding
    series would read as less expanded than it is."""
    candles = _candles([11, 11, 15, 15], [10, 10, 10, 10])
    result = range_contraction(candles, recent_bars=2, baseline_bars=2)
    assert result.recent_mean_range == Decimal("5")
    assert result.baseline_mean_range == Decimal("1")
    assert result.ratio == Decimal("5")
    assert result.is_contracting is False


def test_range_contraction_requires_both_windows_of_history():
    with pytest.raises(DarvaxPrimitiveError, match="at least 4"):
        range_contraction(
            _candles([11, 11, 11], [10, 10, 10]), recent_bars=2, baseline_bars=2
        )


def test_range_contraction_zero_baseline_fails_loudly():
    """Every baseline bar flat means the ratio is undefined — raise rather than
    return a misleading number."""
    candles = _candles([10, 10, 12, 12], [10, 10, 10, 10])
    with pytest.raises(DarvaxPrimitiveError, match="baseline mean range is 0"):
        range_contraction(candles, recent_bars=2, baseline_bars=2)


# =========================================================================== #
# Volume expansion
# =========================================================================== #


def test_volume_expansion_hand_worked():
    """Baseline mean 100, recent mean 300, ratio 3."""
    candles = _candles(
        [11, 11, 11, 11], [10, 10, 10, 10], volumes=[100, 100, 300, 300]
    )
    result = volume_expansion(
        candles, recent_bars=2, baseline_bars=2, min_ratio=Decimal("2")
    )
    assert result.recent_mean_volume == Decimal("300")
    assert result.baseline_mean_volume == Decimal("100")
    assert result.ratio == Decimal("3")
    assert result.is_expanding is True


def test_volume_expansion_below_threshold_is_not_expanding():
    candles = _candles(
        [11, 11, 11, 11], [10, 10, 10, 10], volumes=[100, 100, 150, 150]
    )
    result = volume_expansion(
        candles, recent_bars=2, baseline_bars=2, min_ratio=Decimal("2")
    )
    assert result.ratio == Decimal("1.5")
    assert result.is_expanding is False


def test_volume_expansion_zero_baseline_fails_loudly():
    candles = _candles([11, 11, 11, 11], [10, 10, 10, 10], volumes=[0, 0, 100, 100])
    with pytest.raises(DarvaxPrimitiveError, match="baseline mean volume is 0"):
        volume_expansion(candles, recent_bars=2, baseline_bars=2)


# =========================================================================== #
# Inside bar
# =========================================================================== #


def test_inside_bar_detects_containment():
    result = inside_bar(_candles([10, 9], [5, 6]))
    assert result.is_inside is True
    assert result.index == 1
    assert (result.prior_high, result.prior_low) == (Decimal("10"), Decimal("5"))


def test_inside_bar_equal_range_counts_as_inside():
    """Containment is inclusive, as documented."""
    assert inside_bar(_candles([10, 10], [5, 5])).is_inside is True


def test_inside_bar_higher_high_is_not_inside():
    assert inside_bar(_candles([10, 11], [5, 6])).is_inside is False


def test_inside_bar_lower_low_is_not_inside():
    assert inside_bar(_candles([10, 9], [5, 4])).is_inside is False


def test_inside_bar_explicit_index():
    candles = _candles([10, 9, 12], [5, 6, 4])
    assert inside_bar(candles, index=1).is_inside is True
    assert inside_bar(candles, index=2).is_inside is False


def test_inside_bar_first_bar_has_no_predecessor():
    with pytest.raises(DarvaxPrimitiveError, match="no predecessor"):
        inside_bar(_candles([10, 9], [5, 6]), index=0)


# =========================================================================== #
# Shared input guards
# =========================================================================== #


def test_newest_first_input_is_rejected_with_an_actionable_message():
    """The single most likely caller mistake: list_candles_recent() returns
    newest-first, which would invert every measurement here."""
    chronological = _candles([10, 11, 12], [9, 10, 11])
    reversed_series = list(reversed(chronological))
    with pytest.raises(DarvaxPrimitiveError, match="list_candles_recent"):
        darvas_boxes(reversed_series)


def test_mixed_instruments_are_rejected():
    series = _candles([10, 11], [9, 10]) + _candles(
        [12, 13], [11, 12], instrument_id="NSE:OTHER"
    )
    # Re-stamp timestamps so ordering is valid and instrument mixing is the
    # only defect under test.
    series = [
        dataclasses.replace(c, ts_open=BASE_TS + timedelta(days=i))
        for i, c in enumerate(series)
    ]
    with pytest.raises(DarvaxPrimitiveError, match="single instrument"):
        distance_to_ath(series)


def test_mixed_timeframes_are_rejected():
    series = _candles([10, 11], [9, 10]) + _candles(
        [12, 13], [11, 12], timeframe=Timeframe.M5
    )
    series = [
        dataclasses.replace(c, ts_open=BASE_TS + timedelta(days=i))
        for i, c in enumerate(series)
    ]
    with pytest.raises(DarvaxPrimitiveError, match="single timeframe"):
        distance_to_ath(series)


def test_duplicate_timestamps_are_rejected():
    a, b = _candles([10, 11], [9, 10])
    with pytest.raises(DarvaxPrimitiveError, match="strictly increasing"):
        distance_to_ath([a, dataclasses.replace(b, ts_open=a.ts_open)])


def test_empty_series_is_rejected():
    with pytest.raises(DarvaxPrimitiveError, match="at least 1"):
        distance_to_ath([])


# =========================================================================== #
# Cross-cutting guarantees: purity, determinism, Decimal discipline, immutability
# =========================================================================== #


def test_primitives_are_deterministic_across_repeated_calls():
    candles = _candles(_BOX_HIGHS, _BOX_LOWS, volumes=[100] * 16)
    assert darvas_boxes(candles) == darvas_boxes(candles)
    assert zigzag_swings(candles) == zigzag_swings(candles)
    assert distance_to_ath(candles) == distance_to_ath(candles)
    assert inside_bar(candles) == inside_bar(candles)
    assert range_contraction(candles, recent_bars=2, baseline_bars=2) == (
        range_contraction(candles, recent_bars=2, baseline_bars=2)
    )


def test_primitives_do_not_mutate_their_input():
    candles = _candles(_BOX_HIGHS, _BOX_LOWS, volumes=[100] * 16)
    snapshot = list(candles)
    darvas_boxes(candles)
    zigzag_swings(candles)
    distance_to_ath(candles)
    range_contraction(candles, recent_bars=2, baseline_bars=2)
    volume_expansion(candles, recent_bars=2, baseline_bars=2)
    inside_bar(candles)
    assert candles == snapshot


def test_every_numeric_result_is_decimal_never_float():
    """ATHENA's money discipline: float must not appear anywhere in results."""
    candles = _candles(_BOX_HIGHS, _BOX_LOWS, volumes=[100] * 16)

    box = current_box(candles)
    assert box is not None
    for value in (box.top, box.bottom, box.height):
        assert isinstance(value, Decimal)

    ath = distance_to_ath(candles)
    for value in (ath.ath, ath.close, ath.distance_pct):
        assert isinstance(value, Decimal)

    contraction = range_contraction(candles, recent_bars=2, baseline_bars=2)
    for value in (
        contraction.recent_mean_range,
        contraction.baseline_mean_range,
        contraction.ratio,
    ):
        assert isinstance(value, Decimal)

    expansion = volume_expansion(candles, recent_bars=2, baseline_bars=2)
    for value in (
        expansion.recent_mean_volume,
        expansion.baseline_mean_volume,
        expansion.ratio,
    ):
        assert isinstance(value, Decimal)

    fib = fibonacci_levels(Decimal("100"), Decimal("200"), price=Decimal("150"))
    assert isinstance(fib.retracement_pct, Decimal)
    assert all(
        isinstance(pct, Decimal) and isinstance(price, Decimal)
        for pct, price in fib.levels
    )


def test_results_are_immutable():
    box = current_box(_candles(_BOX_HIGHS, _BOX_LOWS))
    assert box is not None
    with pytest.raises(dataclasses.FrozenInstanceError):
        box.top = Decimal("999")  # type: ignore[misc]


def test_dx2_adds_no_signal_or_decision_surface():
    """DX-2 is measurement only. A name suggesting a verdict would mean DX-3
    logic had leaked into this milestone."""
    import athena.darvax.primitives as primitives

    forbidden = ("signal", "decision", "buy", "sell", "trade", "stop", "score",
                 "recommend", "verdict", "entry", "target")
    exported = [name for name in primitives.__all__]
    for name in exported:
        lowered = name.lower()
        for term in forbidden:
            assert term not in lowered, (
                f"primitives exports {name!r}, which looks like DX-3 territory"
            )
