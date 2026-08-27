"""EM-4B logistic model fit + chronological CV regularization selection
-- tested against a small synthetic, linearly-separable-ish fixture
only (never real TRAIN/VALIDATION data). Requires the optional
emr-modeling dependency group (numpy/scikit-learn); skipped entirely
when unavailable, matching this repo's declared optional-dependency
scoping -- not a reproducibility gap the way an undeclared runtime
dependency would be."""

from __future__ import annotations

import pytest

pytest.importorskip("sklearn")

from decimal import Decimal

from athena.explosive_move.em4_config import TemporalFold
from athena.explosive_move.em4b_model import (
    evaluate_fold,
    fit_final_model,
    replay_final_model,
    select_regularization,
)

CONTINUOUS = ("rsi14",)
CATEGORICAL = ("regime_trend",)
CHECKPOINTS = ("09:20", "09:30")
C_GRID = (0.1, 1.0, 10.0)


def _row(rsi, regime, cp):
    return {"rsi14": Decimal(str(rsi)), "regime_trend": regime, "checkpoint_ist": cp}


def _synthetic_population(n_per_class: int = 60):
    """A crude but genuinely separable signal: high rsi14 + BULL_TREND
    tends POSITIVE, low rsi14 + BEAR_TREND tends NEGATIVE -- enough for
    a real (not degenerate) logistic fit and a real PR-AUC above the
    base rate."""

    rows, labels = [], []
    for i in range(n_per_class):
        rows.append(_row(80 + (i % 10), "BULL_TREND", "09:20" if i % 2 == 0 else "09:30"))
        labels.append(1)
        rows.append(_row(20 + (i % 10), "BEAR_TREND", "09:20" if i % 2 == 0 else "09:30"))
        labels.append(0)
    return rows, labels


def _fit_kwargs():
    return dict(
        continuous_fields=CONTINUOUS, categorical_fields=CATEGORICAL,
        checkpoint_field="checkpoint_ist", checkpoint_categories=CHECKPOINTS,
    )


def test_evaluate_fold_returns_defined_pr_auc_for_separable_data():
    rows, labels = _synthetic_population()
    fit_rows, fit_labels = rows[:80], labels[:80]
    eval_rows, eval_labels = rows[80:], labels[80:]
    fold = TemporalFold(1, __import__("datetime").date(2024, 1, 1),
                         __import__("datetime").date(2024, 1, 2), __import__("datetime").date(2024, 1, 3))

    result = evaluate_fold(
        fold, fit_rows=fit_rows, eval_rows=eval_rows,
        labels_by_row_fit=fit_labels, labels_by_row_eval=eval_labels,
        c_value=1.0, **_fit_kwargs(),
    )
    assert result.pr_auc is not None
    assert result.pr_auc > 0.5  # meaningfully better than a coin flip on this separable fixture


def test_evaluate_fold_none_pr_auc_when_eval_window_has_no_positives():
    rows, labels = _synthetic_population()
    fold = TemporalFold(1, __import__("datetime").date(2024, 1, 1),
                         __import__("datetime").date(2024, 1, 2), __import__("datetime").date(2024, 1, 3))
    eval_rows = [r for r, y in zip(rows, labels, strict=True) if y == 0][:5]
    eval_labels = [0] * 5

    result = evaluate_fold(
        fold, fit_rows=rows, eval_rows=eval_rows,
        labels_by_row_fit=labels, labels_by_row_eval=eval_labels,
        c_value=1.0, **_fit_kwargs(),
    )
    assert result.pr_auc is None


def test_select_regularization_picks_highest_mean_pr_auc():
    from athena.explosive_move.em4b_model import FoldEvaluation

    evaluations = (
        FoldEvaluation(1, 0.1, 10, 10, 2, 0.5),
        FoldEvaluation(2, 0.1, 10, 10, 2, 0.5),
        FoldEvaluation(1, 1.0, 10, 10, 2, 0.9),
        FoldEvaluation(2, 1.0, 10, 10, 2, 0.9),
        FoldEvaluation(1, 10.0, 10, 10, 2, 0.3),
        FoldEvaluation(2, 10.0, 10, 10, 2, 0.3),
    )
    result = select_regularization(evaluations, c_grid=C_GRID)
    assert result.selected_c == 1.0
    assert result.mean_pr_auc_by_c[1.0] == pytest.approx(0.9)


def test_select_regularization_ties_break_to_smallest_c():
    from athena.explosive_move.em4b_model import FoldEvaluation

    evaluations = (
        FoldEvaluation(1, 0.1, 10, 10, 2, 0.7),
        FoldEvaluation(1, 1.0, 10, 10, 2, 0.7),
        FoldEvaluation(1, 10.0, 10, 10, 2, 0.7),
    )
    result = select_regularization(evaluations, c_grid=C_GRID)
    assert result.selected_c == 0.1


def test_select_regularization_raises_when_no_c_has_defined_score():
    from athena.explosive_move.em4b_model import FoldEvaluation

    evaluations = (FoldEvaluation(1, 0.1, 10, 10, 0, None),)
    with pytest.raises(ValueError):
        select_regularization(evaluations, c_grid=C_GRID)


def test_fit_final_model_and_replay_are_deterministic():
    rows, labels = _synthetic_population()
    fold = TemporalFold(1, __import__("datetime").date(2024, 1, 1),
                         __import__("datetime").date(2024, 1, 2), __import__("datetime").date(2024, 1, 3))
    fold_eval = evaluate_fold(
        fold, fit_rows=rows, eval_rows=rows, labels_by_row_fit=labels, labels_by_row_eval=labels,
        c_value=1.0, **_fit_kwargs(),
    )
    cv = select_regularization((fold_eval,), c_grid=(1.0,))

    artifact = fit_final_model(
        train_rows=rows, train_labels=labels, family="TOUCH", threshold_percent=10,
        cv_selection=cv, source_run_ids={"em2": "fixture"}, **_fit_kwargs(),
    )
    assert artifact.converged is True
    assert len(artifact.coefficients) == len(artifact.feature_names)
    assert artifact.train_row_count == len(rows)
    assert artifact.train_positive_count == sum(labels)

    assert replay_final_model(artifact, train_rows=rows, train_labels=labels) is True


def test_replay_detects_a_genuinely_different_fit():
    rows, labels = _synthetic_population()
    fold = TemporalFold(1, __import__("datetime").date(2024, 1, 1),
                         __import__("datetime").date(2024, 1, 2), __import__("datetime").date(2024, 1, 3))
    fold_eval = evaluate_fold(
        fold, fit_rows=rows, eval_rows=rows, labels_by_row_fit=labels, labels_by_row_eval=labels,
        c_value=1.0, **_fit_kwargs(),
    )
    cv = select_regularization((fold_eval,), c_grid=(1.0,))
    artifact = fit_final_model(
        train_rows=rows, train_labels=labels, family="TOUCH", threshold_percent=10,
        cv_selection=cv, source_run_ids={"em2": "fixture"}, **_fit_kwargs(),
    )

    truncated_rows, truncated_labels = rows[:40], labels[:40]
    assert replay_final_model(artifact, train_rows=truncated_rows, train_labels=truncated_labels) is False
