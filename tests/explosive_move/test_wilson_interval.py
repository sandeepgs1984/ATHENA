"""Wilson score interval: standard-reference-value checks plus the
small-n/rare-event behavior EM-1c relies on."""

from __future__ import annotations

import pytest

from athena.explosive_move.wilson_interval import (
    MIN_ELIGIBLE_N,
    MIN_POSITIVE_K,
    meets_minimum_support,
    wilson_interval,
)


def test_matches_known_reference_value():
    # 40/100 successes, 95% CI -- hand-computed reference (z=1.96):
    # center=(0.4+3.8416/200)/1.038416=0.40374, half=0.094298.
    result = wilson_interval(40, 100)
    assert result.point_estimate == pytest.approx(0.40)
    assert result.lower == pytest.approx(0.30944, abs=1e-4)
    assert result.upper == pytest.approx(0.49804, abs=1e-4)


def test_zero_successes_lower_bound_is_zero():
    result = wilson_interval(0, 100)
    assert result.point_estimate == 0.0
    assert result.lower == pytest.approx(0.0, abs=1e-12)
    assert result.upper > 0.0


def test_all_successes_upper_bound_is_one():
    result = wilson_interval(100, 100)
    assert result.point_estimate == 1.0
    assert result.upper == 1.0
    assert result.lower < 1.0


def test_zero_n_returns_maximally_uncertain_interval():
    result = wilson_interval(0, 0)
    assert result.lower == 0.0
    assert result.upper == 1.0


def test_larger_n_at_same_rate_narrows_the_interval():
    small = wilson_interval(10, 1000)
    large = wilson_interval(100, 10000)
    assert small.point_estimate == pytest.approx(large.point_estimate)
    assert large.half_width < small.half_width


def test_rare_event_interval_stays_within_bounds_and_is_asymmetric():
    """A rare-event proportion (EM-1c's real regime: e.g. 18/355724 for
    TOUCH_20) must never leave [0, 1] and, unlike a normal approximation,
    Wilson stays asymmetric around a small point estimate rather than
    producing a negative lower bound."""
    result = wilson_interval(18, 355724)
    assert 0.0 <= result.lower <= result.point_estimate <= result.upper <= 1.0
    assert result.point_estimate - result.lower != result.upper - result.point_estimate


def test_invalid_successes_greater_than_n_raises():
    with pytest.raises(ValueError):
        wilson_interval(11, 10)


def test_invalid_negative_n_raises():
    with pytest.raises(ValueError):
        wilson_interval(0, -1)


def test_minimum_support_frozen_thresholds():
    assert MIN_ELIGIBLE_N == 1000
    assert MIN_POSITIVE_K == 10


def test_meets_minimum_support_requires_both_bounds():
    assert meets_minimum_support(eligible_n=1000, positive_k=10)
    assert not meets_minimum_support(eligible_n=999, positive_k=10)
    assert not meets_minimum_support(eligible_n=1000, positive_k=9)
    assert not meets_minimum_support(eligible_n=50000, positive_k=1)
    assert not meets_minimum_support(eligible_n=10, positive_k=10)
