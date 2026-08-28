"""EM-4D Platt-scaling calibration: Newton-fit 2-parameter logistic
regression on a frozen model's raw logit, plus the checkpoint-specific
-> pooled -> uncalibrated hierarchy. Tested against synthetic fixtures
only."""

from __future__ import annotations

import math
import random

import pytest

from athena.explosive_move.em4d_calibration import (
    CalibrationLevel,
    apply_platt_scaling,
    decide_calibration,
    fit_platt_scaling,
)


def _synthetic_pairs(n_per_class: int, *, logit_offset: float = 0.0, seed: int = 0):
    rng = random.Random(seed)
    pairs = []
    for _ in range(n_per_class):
        pairs.append((logit_offset + rng.gauss(3.0, 1.0), True))
        pairs.append((logit_offset + rng.gauss(-3.0, 1.0), False))
    return tuple(pairs)


def test_fit_platt_scaling_converges_on_separable_data():
    pairs = _synthetic_pairs(200)
    params = fit_platt_scaling(pairs)
    assert params.converged is True
    assert params.fit_n == 400
    assert params.fit_positive_k == 200


def test_fit_platt_scaling_positive_a_for_positively_correlated_logit():
    pairs = _synthetic_pairs(200)
    params = fit_platt_scaling(pairs)
    assert params.a > 0  # higher raw logit -> higher calibrated probability


def test_apply_platt_scaling_recovers_class_separation():
    pairs = _synthetic_pairs(200)
    params = fit_platt_scaling(pairs)
    assert apply_platt_scaling(5.0, params) > 0.5
    assert apply_platt_scaling(-5.0, params) < 0.5


def test_fit_platt_scaling_rejects_empty_input():
    with pytest.raises(ValueError):
        fit_platt_scaling(())


def test_fit_platt_scaling_handles_identical_logits_without_crashing():
    # degenerate: every row has the same raw logit -- Hessian may be
    # near-singular; must not raise, must return SOMETHING interpretable.
    pairs = ((1.0, True), (1.0, False), (1.0, True), (1.0, False))
    params = fit_platt_scaling(pairs)
    assert math.isfinite(params.a)
    assert math.isfinite(params.b)


def test_decide_calibration_uses_checkpoint_specific_when_it_meets_minimum():
    cp_pairs = _synthetic_pairs(500)  # 1000 rows, 500 positive -- clears n>=1000, k>=10
    pooled_pairs = cp_pairs + _synthetic_pairs(500, seed=1)
    decision = decide_calibration(checkpoint_pairs=cp_pairs, pooled_pairs=pooled_pairs)
    assert decision.level is CalibrationLevel.CHECKPOINT_SPECIFIC
    assert decision.params is not None
    assert decision.checkpoint_support_n == 1000
    assert decision.checkpoint_support_k == 500


def test_decide_calibration_falls_back_to_pooled_when_checkpoint_insufficient():
    cp_pairs = _synthetic_pairs(5)  # 10 rows -- below n>=1000
    pooled_pairs = _synthetic_pairs(600, seed=2)  # 1200 rows, 600 positive
    decision = decide_calibration(checkpoint_pairs=cp_pairs, pooled_pairs=pooled_pairs)
    assert decision.level is CalibrationLevel.POOLED_FAMILY_THRESHOLD
    assert decision.params is not None


def test_decide_calibration_uncalibrated_when_neither_meets_minimum():
    cp_pairs = _synthetic_pairs(3)
    pooled_pairs = _synthetic_pairs(10)  # 20 rows -- still below n>=1000
    decision = decide_calibration(checkpoint_pairs=cp_pairs, pooled_pairs=pooled_pairs)
    assert decision.level is CalibrationLevel.UNCALIBRATED_INSUFFICIENT_SUPPORT
    assert decision.params is None
    assert decision.isotonic_candidate is False


def test_isotonic_candidate_flag_reflects_the_bar_actually_used():
    # checkpoint-specific support clears n>=1000/k>=10 but not the
    # isotonic bar (k>=50) -- should be flagged False even though calibrated.
    cp_pairs = _synthetic_pairs(15) + tuple((f, False) for f in (0.0,) * 990)
    pooled_pairs = cp_pairs
    decision = decide_calibration(checkpoint_pairs=cp_pairs, pooled_pairs=pooled_pairs)
    assert decision.level is CalibrationLevel.CHECKPOINT_SPECIFIC
    assert decision.checkpoint_support_k == 15
    assert decision.isotonic_candidate is False


def test_isotonic_candidate_flag_true_when_support_clears_higher_bar():
    cp_pairs = _synthetic_pairs(500)  # 1000 rows, 500 positive -- clears both n>=1000 and k>=50
    decision = decide_calibration(checkpoint_pairs=cp_pairs, pooled_pairs=cp_pairs)
    assert decision.level is CalibrationLevel.CHECKPOINT_SPECIFIC
    assert decision.isotonic_candidate is True
