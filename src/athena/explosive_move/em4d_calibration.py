"""EM-4D: Platt-scaling calibration for the frozen EM-4B logistic
baselines. Owner/Chief Architect GO decision, 2026-08-28 (EM-4C
comparison approved; proceed to calibration under the frozen policy).

CALIBRATION partition data is used ONLY to fit a 2-parameter Platt
transform (A, B) on top of each frozen EM-4B model's own raw linear
score (the pre-sigmoid logit) -- the base model's coefficients and
preprocessing are never touched, never refit, never feature-selected
here. This module has no opinion on which rows constitute
"CALIBRATION"; the caller supplies exactly the (logit, label) pairs a
given fit is allowed to see.

Hierarchy (frozen, reuses em4_config.py's already-approved minimum-
support policy verbatim -- n>=1000, k>=10, never a new number):
  1. checkpoint-specific: fit Platt using only that (family, threshold,
     checkpoint)'s own real CALIBRATION rows, if they meet the minimum.
  2. pooled family x threshold: fall back to all 9 checkpoints' real
     CALIBRATION rows pooled together, if THAT meets the minimum.
  3. UNCALIBRATED / INSUFFICIENT_SUPPORT: neither meets the minimum --
     reported honestly, never silently forced through.

Isotonic regression is NOT applied here -- per the frozen policy it is
only ever a candidacy observation (positive support >= 50), reported
alongside the Platt result, never substituted in automatically or
treated as a decision made in this milestone.

Platt's own 1999 fitting procedure: a 2-parameter logistic regression
of label on the base model's raw logit, fit by Newton's method (2x2
Hessian, closed-form inverse) -- hand-rolled in pure Python, matching
this workstream's convention of hand-rolling small, well-understood
statistics (wilson_interval.py) rather than reaching for scikit-learn
for a 2-parameter fit.

Pure: no I/O, no randomness.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from enum import Enum

from athena.explosive_move.em4_config import ISOTONIC_CONSIDERATION_MIN_POSITIVE_K, meets_platt_minimum

EM4D_CALIBRATION_CONTRACT_VERSION = "em4d-calibration-v1"

#: Newton's method converges in single digits of iterations for a
#: well-posed 2-parameter fit; capped well above that for safety.
MAX_NEWTON_ITER = 100
CONVERGENCE_TOL = 1e-10


class CalibrationLevel(str, Enum):
    CHECKPOINT_SPECIFIC = "CHECKPOINT_SPECIFIC"
    POOLED_FAMILY_THRESHOLD = "POOLED_FAMILY_THRESHOLD"
    UNCALIBRATED_INSUFFICIENT_SUPPORT = "UNCALIBRATED_INSUFFICIENT_SUPPORT"


def _sigmoid(x: float) -> float:
    if x >= 0:
        z = math.exp(-x)
        return 1.0 / (1.0 + z)
    z = math.exp(x)
    return z / (1.0 + z)


@dataclass(frozen=True, slots=True)
class PlattParams:
    a: float
    b: float
    n_iter: int
    converged: bool
    fit_n: int
    fit_positive_k: int


def fit_platt_scaling(logit_label_pairs: tuple[tuple[float, bool], ...]) -> PlattParams:
    """Newton's method on the 2-parameter logistic regression
    P(y=1|f) = sigmoid(A*f + B). Initial guess A=1, B=0 (the identity
    transform -- a reasonable starting point since f is already the
    base model's own logit, not an arbitrary score).

    Uses Platt's own 1999 target-smoothing rule (t+ = (N+ + 1)/(N+ + 2),
    t- = 1/(N- + 2), the Bayesian-motivated out-of-sample estimates of
    each class's true label, in place of raw {0,1}) -- without this,
    the MLE diverges to +-infinity whenever the base model's raw logit
    already separates the two classes well on CALIBRATION, which is
    exactly the regime a genuinely useful model produces. This is not
    an approximation of Platt scaling; it is Platt scaling."""

    n = len(logit_label_pairs)
    if n == 0:
        raise ValueError("cannot fit Platt scaling on zero observations")
    positive_k = sum(1 for _, y in logit_label_pairs if y)
    negative_n = n - positive_k
    t_positive = (positive_k + 1) / (positive_k + 2) if positive_k > 0 else 0.5
    t_negative = 1 / (negative_n + 2) if negative_n > 0 else 0.5

    a, b = 1.0, 0.0
    converged = False
    n_iter = 0
    for iteration in range(1, MAX_NEWTON_ITER + 1):
        n_iter = iteration
        grad_a = grad_b = 0.0
        hess_aa = hess_bb = hess_ab = 0.0
        for f, y in logit_label_pairs:
            p = _sigmoid(a * f + b)
            target = t_positive if y else t_negative
            grad_a += (p - target) * f
            grad_b += p - target
            w = p * (1.0 - p)
            hess_aa += w * f * f
            hess_bb += w
            hess_ab += w * f

        det = hess_aa * hess_bb - hess_ab * hess_ab
        if abs(det) < 1e-12:
            break  # near-singular Hessian; stop, report what has been found so far
        delta_a = (hess_bb * grad_a - hess_ab * grad_b) / det
        delta_b = (hess_aa * grad_b - hess_ab * grad_a) / det
        a -= delta_a
        b -= delta_b
        if abs(delta_a) < CONVERGENCE_TOL and abs(delta_b) < CONVERGENCE_TOL:
            converged = True
            break

    return PlattParams(a=a, b=b, n_iter=n_iter, converged=converged, fit_n=n, fit_positive_k=positive_k)


def apply_platt_scaling(logit: float, params: PlattParams) -> float:
    return _sigmoid(params.a * logit + params.b)


@dataclass(frozen=True, slots=True)
class CalibrationDecision:
    level: CalibrationLevel
    params: PlattParams | None
    checkpoint_support_n: int
    checkpoint_support_k: int
    pooled_support_n: int
    pooled_support_k: int
    #: Descriptive only, per the frozen policy -- never auto-applied.
    #: True iff the support level actually used for this decision (or,
    #: for UNCALIBRATED, the pooled support) clears the higher isotonic
    #: candidacy bar (k>=50).
    isotonic_candidate: bool


def decide_calibration(
    *,
    checkpoint_pairs: tuple[tuple[float, bool], ...],
    pooled_pairs: tuple[tuple[float, bool], ...],
) -> CalibrationDecision:
    """``checkpoint_pairs`` is this (family, threshold, checkpoint)'s
    own real CALIBRATION (logit, label) rows; ``pooled_pairs`` is the
    same (family, threshold)'s rows pooled across all 9 checkpoints (a
    superset including ``checkpoint_pairs``)."""

    cp_n = len(checkpoint_pairs)
    cp_k = sum(1 for _, y in checkpoint_pairs if y)
    pooled_n = len(pooled_pairs)
    pooled_k = sum(1 for _, y in pooled_pairs if y)

    if meets_platt_minimum(eligible_n=cp_n, positive_k=cp_k):
        params = fit_platt_scaling(checkpoint_pairs)
        return CalibrationDecision(
            level=CalibrationLevel.CHECKPOINT_SPECIFIC, params=params,
            checkpoint_support_n=cp_n, checkpoint_support_k=cp_k,
            pooled_support_n=pooled_n, pooled_support_k=pooled_k,
            isotonic_candidate=cp_k >= ISOTONIC_CONSIDERATION_MIN_POSITIVE_K,
        )

    if meets_platt_minimum(eligible_n=pooled_n, positive_k=pooled_k):
        params = fit_platt_scaling(pooled_pairs)
        return CalibrationDecision(
            level=CalibrationLevel.POOLED_FAMILY_THRESHOLD, params=params,
            checkpoint_support_n=cp_n, checkpoint_support_k=cp_k,
            pooled_support_n=pooled_n, pooled_support_k=pooled_k,
            isotonic_candidate=pooled_k >= ISOTONIC_CONSIDERATION_MIN_POSITIVE_K,
        )

    return CalibrationDecision(
        level=CalibrationLevel.UNCALIBRATED_INSUFFICIENT_SUPPORT, params=None,
        checkpoint_support_n=cp_n, checkpoint_support_k=cp_k,
        pooled_support_n=pooled_n, pooled_support_k=pooled_k,
        isotonic_candidate=False,
    )
