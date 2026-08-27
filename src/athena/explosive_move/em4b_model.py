"""EM-4B: the logistic baseline model fit + frozen chronological CV
regularization selection.

Owner/Chief Architect decision, 2026-08-27 (EM-4 Modeling Contract).
``numpy``/``scikit-learn`` are used ONLY here (never in
em4b_preprocessing.py, which stays hand-rolled pure Python) -- narrowly
scoped to the actual numerical fit, per the owner's explicit dependency
approval. This module never fits its own logistic regression by hand;
it is a thin, deterministic wrapper around
``sklearn.linear_model.LogisticRegression``.

CV design (the owner's "most important correction"): regularization
(the single scalar ``C``, sklearn's inverse-regularization-strength
convention) is selected via ``em4_config.TEMPORAL_CV_FOLDS`` -- strictly
chronological, session-grouped, expanding-window -- never ordinary
k-fold. For each candidate ``C`` in ``em4_config.L2_REGULARIZATION_GRID``
and each fold: preprocessing (median/mean/std/categories/zero-variance
drops) is refit from scratch on ONLY that fold's chronologically-prior
"fit window" rows (never the eval window, never the full TRAIN
partition) -- the same leakage boundary the owner's correction exists to
enforce, applied to preprocessing as well as to the coefficients
themselves. The scoring metric is PR-AUC (average precision), evaluated
by pooling the fold's eval-window predictions and reusing this
workstream's own hand-rolled ``em4c_metrics.average_precision`` (already
tested against synthetic fixtures) rather than a second, redundant
implementation.

Tie-break rule (frozen here, v1): the ``C`` with the highest mean PR-AUC
across the 4 folds wins; an exact tie is broken by the SMALLEST ``C``
(more regularization, the more conservative/parsimonious choice) --
deterministic, documented, arbitrary only in the sense that any tie-break
rule is; ties are expected to be rare with continuous PR-AUC values.

The FINAL frozen model (persisted as the EM-4B artifact) refits
preprocessing and the logistic fit on the FULL TRAIN partition with the
CV-selected ``C`` -- TRAIN is entirely chronologically prior to
VALIDATION, so this final refit introduces no leakage the CV
procedure didn't already guard against internally.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import sklearn
from sklearn.linear_model import LogisticRegression

from athena.explosive_move.em4_config import TemporalFold
from athena.explosive_move.em4b_preprocessing import PreprocessingSpec, fit_preprocessing, transform_rows
from athena.explosive_move.em4c_metrics import average_precision

EM4B_MODEL_CONTRACT_VERSION = "em4-logistic-v1"

#: sklearn's default lbfgs solver is deterministic (no internal
#: randomness) for this L2-penalized binary case -- no random_state
#: needed for reproducibility, but max_iter is raised well above
#: sklearn's own default (100) since real TRAIN populations run into
#: the hundreds of thousands of rows across ~dozens of features.
SOLVER = "lbfgs"
MAX_ITER = 2000
TOL = 1e-4


@dataclass(frozen=True, slots=True)
class FoldEvaluation:
    fold_id: int
    c_value: float
    fit_row_count: int
    eval_row_count: int
    eval_positive_count: int
    pr_auc: float | None  # None iff the eval window had zero positives


@dataclass(frozen=True, slots=True)
class CVSelectionResult:
    selected_c: float
    mean_pr_auc_by_c: dict[float, float | None]
    fold_evaluations: tuple[FoldEvaluation, ...]


@dataclass(frozen=True, slots=True)
class LogisticModelArtifact:
    contract_version: str
    family: str
    threshold_percent: int
    sklearn_version: str
    numpy_version: str
    solver: str
    penalty: str
    c_value: float
    max_iter: int
    tol: float
    n_iter: int
    converged: bool
    feature_names: tuple[str, ...]
    coefficients: tuple[float, ...]
    intercept: float
    preprocessing: PreprocessingSpec
    train_row_count: int
    train_positive_count: int
    cv_selection: CVSelectionResult
    source_run_ids: dict[str, str]


def _fit_sklearn_logistic(X: np.ndarray, y: np.ndarray, *, c_value: float) -> LogisticRegression:
    # l1_ratio=0.0 (not penalty="l2") -- scikit-learn >=1.8 deprecates the
    # `penalty` kwarg in favor of `l1_ratio`; l1_ratio=0.0 is confirmed
    # (empirically, coefficients/intercept identical to the old
    # penalty="l2" spelling) equivalent to pure L2 on both this project's
    # floor (scikit-learn>=1.4, where l1_ratio is simply ignored under
    # the old default penalty="l2") and the currently-resolved 1.9 --
    # version-agnostic, no FutureWarning either way.
    model = LogisticRegression(
        C=c_value, l1_ratio=0.0, solver=SOLVER, max_iter=MAX_ITER, tol=TOL,
    )
    model.fit(X, y)
    return model


def _build_matrix(rows: list[dict], spec: PreprocessingSpec) -> np.ndarray:
    return np.asarray(transform_rows(rows, spec), dtype=np.float64)


def evaluate_fold(
    fold: TemporalFold,
    *,
    fit_rows: list[dict], eval_rows: list[dict], labels_by_row_fit: list[int], labels_by_row_eval: list[int],
    continuous_fields: tuple[str, ...], categorical_fields: tuple[str, ...],
    checkpoint_field: str, checkpoint_categories: tuple[str, ...],
    c_value: float,
) -> FoldEvaluation:
    """`fit_rows`/`eval_rows` must already be restricted by the caller to
    this fold's chronological fit-window/eval-window session dates."""

    spec = fit_preprocessing(
        fit_rows, continuous_fields=continuous_fields, categorical_fields=categorical_fields,
        checkpoint_field=checkpoint_field, checkpoint_categories=checkpoint_categories,
    )
    X_fit = _build_matrix(fit_rows, spec)
    y_fit = np.asarray(labels_by_row_fit, dtype=np.float64)
    model = _fit_sklearn_logistic(X_fit, y_fit, c_value=c_value)

    eval_positive = sum(labels_by_row_eval)
    if not eval_rows or eval_positive == 0:
        return FoldEvaluation(
            fold_id=fold.fold_id, c_value=c_value, fit_row_count=len(fit_rows),
            eval_row_count=len(eval_rows), eval_positive_count=eval_positive, pr_auc=None,
        )

    X_eval = _build_matrix(eval_rows, spec)
    scores = model.predict_proba(X_eval)[:, 1]
    order = sorted(range(len(scores)), key=lambda i: (-scores[i], i))
    ranked_labels = tuple(bool(labels_by_row_eval[i]) for i in order)
    pr_auc = average_precision(ranked_labels)

    return FoldEvaluation(
        fold_id=fold.fold_id, c_value=c_value, fit_row_count=len(fit_rows),
        eval_row_count=len(eval_rows), eval_positive_count=eval_positive, pr_auc=pr_auc,
    )


def select_regularization(
    fold_evaluations: tuple[FoldEvaluation, ...], *, c_grid: tuple[float, ...],
) -> CVSelectionResult:
    mean_by_c: dict[float, float | None] = {}
    for c_value in c_grid:
        scores = [fe.pr_auc for fe in fold_evaluations if fe.c_value == c_value and fe.pr_auc is not None]
        mean_by_c[c_value] = (sum(scores) / len(scores)) if scores else None

    scored = [(c, v) for c, v in mean_by_c.items() if v is not None]
    if not scored:
        raise ValueError("no candidate C achieved a defined PR-AUC on any fold -- cannot select regularization")
    best_score = max(v for _, v in scored)
    tied = [c for c, v in scored if v == best_score]
    selected = min(tied)  # tie-break: smallest C (more regularization), see module docstring

    return CVSelectionResult(
        selected_c=selected, mean_pr_auc_by_c=mean_by_c, fold_evaluations=fold_evaluations,
    )


def fit_final_model(
    *,
    train_rows: list[dict], train_labels: list[int],
    continuous_fields: tuple[str, ...], categorical_fields: tuple[str, ...],
    checkpoint_field: str, checkpoint_categories: tuple[str, ...],
    family: str, threshold_percent: int,
    cv_selection: CVSelectionResult, source_run_ids: dict[str, str],
) -> LogisticModelArtifact:
    spec = fit_preprocessing(
        train_rows, continuous_fields=continuous_fields, categorical_fields=categorical_fields,
        checkpoint_field=checkpoint_field, checkpoint_categories=checkpoint_categories,
    )
    X = _build_matrix(train_rows, spec)
    y = np.asarray(train_labels, dtype=np.float64)
    model = _fit_sklearn_logistic(X, y, c_value=cv_selection.selected_c)

    n_iter = int(model.n_iter_[0])
    return LogisticModelArtifact(
        contract_version=EM4B_MODEL_CONTRACT_VERSION, family=family, threshold_percent=threshold_percent,
        sklearn_version=sklearn.__version__, numpy_version=np.__version__,
        solver=SOLVER, penalty="l2", c_value=cv_selection.selected_c, max_iter=MAX_ITER, tol=TOL,
        n_iter=n_iter, converged=n_iter < MAX_ITER,
        feature_names=spec.feature_names, coefficients=tuple(float(c) for c in model.coef_[0]),
        intercept=float(model.intercept_[0]), preprocessing=spec,
        train_row_count=len(train_rows), train_positive_count=int(sum(train_labels)),
        cv_selection=cv_selection, source_run_ids=source_run_ids,
    )


def replay_final_model(artifact: LogisticModelArtifact, *, train_rows: list[dict], train_labels: list[int]) -> bool:
    """Refits an identical model from the same inputs and confirms
    byte-for-byte-equivalent coefficients/intercept -- the deterministic-
    reproduction check the EM-4 Modeling Contract requires before an
    artifact is trusted."""

    spec = fit_preprocessing(
        train_rows, continuous_fields=artifact.preprocessing.continuous_fields,
        categorical_fields=artifact.preprocessing.categorical_fields,
        checkpoint_field=artifact.preprocessing.checkpoint_field,
        checkpoint_categories=artifact.preprocessing.checkpoint_spec.categories[:-1],
    )
    if spec.feature_names != artifact.feature_names:
        return False
    X = _build_matrix(train_rows, spec)
    y = np.asarray(train_labels, dtype=np.float64)
    model = _fit_sklearn_logistic(X, y, c_value=artifact.c_value)
    coefficients = tuple(float(c) for c in model.coef_[0])
    intercept = float(model.intercept_[0])
    return coefficients == artifact.coefficients and intercept == artifact.intercept
