"""EM-4 frozen methodological config: exact fold boundaries, no gaps/
overlaps, session-grouped (whole dates only)."""

from __future__ import annotations

from datetime import date, timedelta
from itertools import pairwise

from athena.explosive_move.em4_config import (
    L2_REGULARIZATION_GRID,
    PLATT_MIN_ELIGIBLE_N,
    PLATT_MIN_POSITIVE_K,
    TEMPORAL_CV_FOLDS,
    fold_for_session,
    meets_platt_minimum,
)


def test_exactly_four_folds():
    assert len(TEMPORAL_CV_FOLDS) == 4


def test_folds_are_chronologically_non_overlapping():
    for prev, cur in pairwise(TEMPORAL_CV_FOLDS):
        assert prev.eval_end < cur.eval_start
        assert prev.fit_through < cur.fit_through


def test_base_window_session_is_not_assigned_to_any_fold():
    assert fold_for_session(date(2023, 8, 14)) is None  # TRAIN's first session
    assert fold_for_session(date(2024, 7, 9)) is None  # fold 1's own fit_through date


def test_eval_boundaries_are_inclusive():
    assert fold_for_session(date(2024, 7, 10)) == 1
    assert fold_for_session(date(2024, 9, 26)) == 1
    assert fold_for_session(date(2024, 9, 27)) == 2


def test_date_after_last_fold_is_unassigned():
    assert fold_for_session(date(2025, 5, 31)) is None  # TRAIN's last session


def test_l2_grid_is_small_and_frozen():
    assert L2_REGULARIZATION_GRID == (0.01, 0.1, 1.0, 10.0)


def test_platt_minimum_reuses_em1c_policy_exactly():
    assert PLATT_MIN_ELIGIBLE_N == 1000
    assert PLATT_MIN_POSITIVE_K == 10


def test_meets_platt_minimum_requires_both_bounds():
    assert meets_platt_minimum(eligible_n=1000, positive_k=10)
    assert not meets_platt_minimum(eligible_n=999, positive_k=10)
    assert not meets_platt_minimum(eligible_n=1000, positive_k=9)


def test_every_train_session_is_covered_exactly_once_or_is_in_the_base_window():
    """Walk every real calendar day across all 4 eval blocks plus the base
    window and confirm no date is double-assigned."""
    seen_in_fold: dict[date, int] = {}
    for fold in TEMPORAL_CV_FOLDS:
        d = fold.eval_start
        while d <= fold.eval_end:
            assert d not in seen_in_fold, f"{d} assigned to multiple folds"
            seen_in_fold[d] = fold.fold_id
            d += timedelta(days=1)
