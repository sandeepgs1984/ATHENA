"""EM-4C evaluation scaffolding: PR-AUC (average precision), Brier score,
and calibration/reliability diagnostics.

Owner/Chief Architect decision, 2026-08-27 (evaluation-scaffolding
scope). These are hand-rolled in pure Python rather than delegated to a
numpy/scikit-learn wrapper: none of them require a fitted model or a
numerical library -- PR-AUC and Brier are closed-form over a list of
(score, label) pairs, and this workstream already hand-rolls its other
statistics (see wilson_interval.py) rather than reaching for a
dependency it doesn't need. This keeps the evaluation layer usable
before the modelling environment exists and independent of it
afterward.

average_precision() matches the standard non-interpolated definition
(the same one scikit-learn's average_precision_score computes): the
precision-recall step function evaluated at each real positive's rank,
averaged. No trapezoidal interpolation (which can overstate area).

Pure: no I/O, no randomness.
"""

from __future__ import annotations

from dataclasses import dataclass

from athena.explosive_move.wilson_interval import WilsonInterval, wilson_interval

EM4C_METRICS_CONTRACT_VERSION = "em4c-metrics-v1"


def average_precision(ranked_labels: tuple[bool, ...]) -> float | None:
    """``ranked_labels`` must already be in the caller's chosen ranking
    order (score descending; see em4c_ranking.rank_observations) --
    this function is order-dependent and does no ranking itself, so the
    same deterministic tie-break is reused by construction.

    None if there are zero real positives (PR-AUC/average precision is
    undefined without at least one positive to recall)."""

    total_positives = sum(1 for label in ranked_labels if label)
    if total_positives == 0:
        return None

    running_positives = 0
    precision_sum = 0.0
    for rank, label in enumerate(ranked_labels, start=1):
        if label:
            running_positives += 1
            precision_sum += running_positives / rank
    return precision_sum / total_positives


@dataclass(frozen=True, slots=True)
class BrierResult:
    score: float | None  # mean squared error between probability and outcome; None if n == 0
    n: int


def brier_score(probability_label_pairs: tuple[tuple[float, bool], ...]) -> BrierResult:
    """Only meaningful for genuinely calibration-gated probabilities
    (per the EM-4 probability-language discipline) -- callers must not
    pass a raw deterministic-score or uncalibrated logit here."""

    n = len(probability_label_pairs)
    if n == 0:
        return BrierResult(score=None, n=0)
    total = sum((p - (1.0 if label else 0.0)) ** 2 for p, label in probability_label_pairs)
    return BrierResult(score=total / n, n=n)


@dataclass(frozen=True, slots=True)
class CalibrationBin:
    bin_index: int
    predicted_mean: float | None
    observed_rate: float | None
    n: int
    wilson_95: WilsonInterval | None


def calibration_bins(
    probability_label_pairs: tuple[tuple[float, bool], ...], *, num_bins: int,
) -> tuple[CalibrationBin, ...]:
    """Equal-width bins over [0, 1] (bin i holds predictions in
    [i/num_bins, (i+1)/num_bins), the top bin closed at 1.0 inclusive) --
    deterministic assignment, matching this workstream's existing
    boundary convention (conditional_analysis.assign_bin). Empty bins
    are still reported (n=0, predicted_mean/observed_rate/wilson_95
    None) rather than omitted, so a caller can see gaps in coverage."""

    if num_bins <= 0:
        raise ValueError(f"num_bins must be positive, got {num_bins}")

    buckets: list[list[tuple[float, bool]]] = [[] for _ in range(num_bins)]
    for p, label in probability_label_pairs:
        if not (0.0 <= p <= 1.0):
            raise ValueError(f"probability out of [0,1]: {p}")
        idx = min(num_bins - 1, int(p * num_bins))
        buckets[idx].append((p, label))

    results = []
    for i, bucket in enumerate(buckets):
        if not bucket:
            results.append(CalibrationBin(i, None, None, 0, None))
            continue
        n = len(bucket)
        predicted_mean = sum(p for p, _ in bucket) / n
        positives = sum(1 for _, label in bucket if label)
        results.append(CalibrationBin(
            bin_index=i, predicted_mean=predicted_mean, observed_rate=positives / n,
            n=n, wilson_95=wilson_interval(positives, n),
        ))
    return tuple(results)
