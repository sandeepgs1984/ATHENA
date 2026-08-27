"""EM-4C metrics scaffolding: PR-AUC (average precision), Brier score,
calibration bins -- tested against synthetic fixtures only."""

from __future__ import annotations

import pytest

from athena.explosive_move.em4c_metrics import (
    average_precision,
    brier_score,
    calibration_bins,
)


def test_average_precision_perfect_ranking_is_one():
    # all positives ranked first
    assert average_precision((True, True, True, False, False)) == 1.0


def test_average_precision_worst_ranking_is_low():
    labels = (False, False, False, True)
    ap = average_precision(labels)
    # only positive at rank 4: precision there = 1/4
    assert ap == pytest.approx(0.25)


def test_average_precision_matches_hand_computed_example():
    # ranks: 1=+ 2=- 3=+ 4=-  -> precisions at positive ranks: 1/1, 2/3
    labels = (True, False, True, False)
    ap = average_precision(labels)
    assert ap == pytest.approx((1 / 1 + 2 / 3) / 2)


def test_average_precision_no_positives_is_none():
    assert average_precision((False, False, False)) is None


def test_average_precision_empty_is_none():
    assert average_precision(()) is None


def test_brier_score_perfect_predictions_is_zero():
    pairs = ((1.0, True), (0.0, False))
    result = brier_score(pairs)
    assert result.score == 0.0
    assert result.n == 2


def test_brier_score_worst_predictions_is_one():
    pairs = ((0.0, True), (1.0, False))
    result = brier_score(pairs)
    assert result.score == 1.0


def test_brier_score_hand_computed_example():
    pairs = ((0.8, True), (0.3, False))
    result = brier_score(pairs)
    # (0.8-1)^2 = 0.04 ; (0.3-0)^2 = 0.09 ; mean = 0.065
    assert result.score == pytest.approx(0.065)


def test_brier_score_empty_is_none():
    result = brier_score(())
    assert result.score is None
    assert result.n == 0


def test_calibration_bins_perfectly_calibrated_example():
    # 10 observations at p=0.2, 2 positive -> observed rate 0.2, matches predicted
    pairs = tuple((0.2, i < 2) for i in range(10))
    bins = calibration_bins(pairs, num_bins=5)
    # p=0.2 falls in bin index 1 ([0.2, 0.4))
    populated = [b for b in bins if b.n > 0]
    assert len(populated) == 1
    b = populated[0]
    assert b.bin_index == 1
    assert b.predicted_mean == pytest.approx(0.2)
    assert b.observed_rate == pytest.approx(0.2)
    assert b.n == 10


def test_calibration_bins_reports_empty_bins_explicitly():
    pairs = ((0.05, True),)
    bins = calibration_bins(pairs, num_bins=4)
    assert len(bins) == 4
    empties = [b for b in bins if b.n == 0]
    assert len(empties) == 3
    for b in empties:
        assert b.predicted_mean is None
        assert b.observed_rate is None
        assert b.wilson_95 is None


def test_calibration_bins_top_edge_inclusive_in_last_bin():
    pairs = ((1.0, True),)
    bins = calibration_bins(pairs, num_bins=5)
    assert bins[-1].n == 1


def test_calibration_bins_rejects_out_of_range_probability():
    with pytest.raises(ValueError):
        calibration_bins(((1.5, True),), num_bins=5)


def test_calibration_bins_rejects_nonpositive_num_bins():
    with pytest.raises(ValueError):
        calibration_bins((), num_bins=0)
