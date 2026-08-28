"""EM-4C scoring: applying an already-frozen linear model (dot product +
sigmoid) to a real observation -- pure Python, no scikit-learn needed
for inference. Tested against synthetic fixtures only."""

from __future__ import annotations

from decimal import Decimal

import pytest

from athena.explosive_move.em4b_preprocessing import fit_preprocessing
from athena.explosive_move.em4c_scoring import score_logistic, score_logit, sigmoid


def test_sigmoid_matches_hand_computed_values():
    assert sigmoid(0.0) == pytest.approx(0.5)
    assert sigmoid(100.0) == pytest.approx(1.0)
    assert sigmoid(-100.0) == pytest.approx(0.0)


def test_sigmoid_symmetric():
    assert sigmoid(2.0) + sigmoid(-2.0) == pytest.approx(1.0)


def _fixture_spec():
    rows = [
        {"rsi14": Decimal("10"), "regime_trend": "BULL_TREND", "checkpoint_ist": "09:20"},
        {"rsi14": Decimal("90"), "regime_trend": "BEAR_TREND", "checkpoint_ist": "09:30"},
    ]
    return fit_preprocessing(
        rows, continuous_fields=("rsi14",), categorical_fields=("regime_trend",),
        checkpoint_field="checkpoint_ist", checkpoint_categories=("09:20", "09:30"),
    )


def test_score_logistic_zero_coefficients_gives_sigmoid_of_intercept():
    spec = _fixture_spec()
    coefficients = tuple(0.0 for _ in spec.feature_names)
    row = {"rsi14": Decimal("50"), "regime_trend": "BULL_TREND", "checkpoint_ist": "09:20"}
    score = score_logistic(
        row, feature_names=spec.feature_names, coefficients=coefficients, intercept=1.5,
        preprocessing=spec,
    )
    assert score == pytest.approx(sigmoid(1.5))


def test_score_logistic_rejects_feature_name_mismatch():
    spec = _fixture_spec()
    row = {"rsi14": Decimal("50"), "regime_trend": "BULL_TREND", "checkpoint_ist": "09:20"}
    with pytest.raises(ValueError):
        score_logistic(
            row, feature_names=("wrong",), coefficients=(1.0,), intercept=0.0, preprocessing=spec,
        )


def test_score_logit_is_sigmoids_pre_image():
    spec = _fixture_spec()
    coefficients = tuple(0.1 * i for i in range(len(spec.feature_names)))
    row = {"rsi14": Decimal("50"), "regime_trend": "BULL_TREND", "checkpoint_ist": "09:20"}
    logit = score_logit(
        row, feature_names=spec.feature_names, coefficients=coefficients, intercept=0.2,
        preprocessing=spec,
    )
    prob = score_logistic(
        row, feature_names=spec.feature_names, coefficients=coefficients, intercept=0.2,
        preprocessing=spec,
    )
    assert prob == pytest.approx(sigmoid(logit))


def test_score_logistic_is_deterministic():
    spec = _fixture_spec()
    coefficients = tuple(0.1 * i for i in range(len(spec.feature_names)))
    row = {"rsi14": Decimal("50"), "regime_trend": "BULL_TREND", "checkpoint_ist": "09:20"}
    a = score_logistic(
        row, feature_names=spec.feature_names, coefficients=coefficients, intercept=0.2,
        preprocessing=spec,
    )
    b = score_logistic(
        row, feature_names=spec.feature_names, coefficients=coefficients, intercept=0.2,
        preprocessing=spec,
    )
    assert a == b
