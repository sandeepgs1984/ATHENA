"""EM-3 v1: univariate, checkpoint-level, TRAIN-only conditional analysis.

Owner/Chief Architect decision, 2026-08-27: EM-3 discovers simple,
explainable conditional structure -- it does not prove a feature
predicts anything, and it never mines interactions. This module is pure
(no I/O): bin-edge derivation, deterministic bin assignment, and the
per-cell conditional-metric bundle every (feature, bin/category, event
family, threshold, checkpoint) combination reports.

Terminology is deliberately restrained per the owner's exit-semantics
requirement: a supported cell is labelled EXPLORATORY_CANDIDATE, never
VALIDATED_SIGNAL; every register entry is TRAIN-DISCOVERED / UNVALIDATED.
"""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from enum import Enum
from itertools import pairwise

from athena.explosive_move.wilson_interval import meets_minimum_support, wilson_interval

BIN_EDGE_CONTRACT_VERSION = "em3-bin-edges-v1"

#: EM-3's own UNKNOWN handling policy (owner requirement: version it,
#: state it explicitly). UNKNOWN observations are EXCLUDED from a
#: feature's bin-edge derivation and from every bin's "complement"
#: population -- the complement is "known, not-this-bin", never
#: "known-or-unknown, not-this-bin". UNKNOWN gets its own reported row,
#: classified MISSINGNESS_DIAGNOSTIC, never silently merged elsewhere.
UNKNOWN_HANDLING_POLICY = (
    "UNKNOWN_EXCLUDED_FROM_BIN_EDGES_AND_COMPLEMENT_v1: UNKNOWN values never "
    "participate in quintile-edge derivation and are never folded into a "
    "bin's complement population; UNKNOWN is reported as its own row, "
    "classified MISSINGNESS_DIAGNOSTIC, and is never itself treated as "
    "evidence of a market signal."
)


class SupportLabel(str, Enum):
    EXPLORATORY_CANDIDATE = "EXPLORATORY_CANDIDATE"
    INSUFFICIENT_SUPPORT = "INSUFFICIENT_SUPPORT"
    MISSINGNESS_DIAGNOSTIC = "MISSINGNESS_DIAGNOSTIC"


class Shape(str, Enum):
    MONOTONIC_INCREASING = "MONOTONIC_INCREASING"
    MONOTONIC_DECREASING = "MONOTONIC_DECREASING"
    U_SHAPED = "U_SHAPED"
    INVERTED_U_SHAPED = "INVERTED_U_SHAPED"
    NON_MONOTONIC = "NON_MONOTONIC"
    NOT_APPLICABLE = "NOT_APPLICABLE"  # fewer than 3 known bins, or categorical


def compute_quintile_edges(known_values: list[Decimal]) -> tuple[Decimal, ...]:
    """Deterministic quintile edges (4 cut points -> 5 bins) from a
    feature's real, known-only TRAIN value distribution. Never uses
    labels. If real quantiles collide (duplicate values at a cut point),
    the duplicate edge is dropped rather than inventing an artificial
    boundary -- this deterministically REDUCES the bin count instead of
    fabricating separation the data doesn't have."""

    if not known_values:
        return ()
    ordered = sorted(known_values)
    n = len(ordered)
    raw_edges = []
    for q in (1, 2, 3, 4):
        # nearest-rank method, deterministic, no interpolation.
        idx = min(n - 1, max(0, (q * n) // 5))
        raw_edges.append(ordered[idx])
    # drop duplicates, preserving order -- fewer real bins rather than a
    # fabricated boundary at an identical value.
    deduped: list[Decimal] = []
    for e in raw_edges:
        if not deduped or e != deduped[-1]:
            deduped.append(e)
    return tuple(deduped)


def assign_bin(value: Decimal, edges: tuple[Decimal, ...]) -> int:
    """Bin index 0..len(edges). Boundary semantics: bin i holds values
    with edges[i-1] <= value < edges[i] (edges[-1] absent for the top
    bin, which is >= the last edge) -- deterministic, no ties split
    across two bins."""

    for i, edge in enumerate(edges):
        if value < edge:
            return i
    return len(edges)


def bin_label(index: int, edges: tuple[Decimal, ...]) -> str:
    if not edges:
        return "ALL"
    if index == 0:
        return f"Q1(<{edges[0]})"
    if index == len(edges):
        return f"Q{index + 1}(>={edges[-1]})"
    return f"Q{index + 1}([{edges[index - 1]},{edges[index]}))"


@dataclass(frozen=True, slots=True)
class ConditionalCell:
    eligible_n: int
    positive_k: int
    rate: float
    wilson_95_lower: float
    wilson_95_upper: float
    baseline_rate: float
    absolute_difference: float
    lift: float | None  # None when baseline_rate == 0
    complement_n: int
    complement_k: int
    complement_rate: float
    risk_ratio: float | None  # rate / complement_rate; None when complement_rate == 0
    support_label: SupportLabel


def compute_conditional_cell(
    *, positive_k: int, negative_n: int, baseline_rate: float,
    complement_positive_k: int, complement_negative_n: int,
) -> ConditionalCell:
    n = positive_k + negative_n
    interval = wilson_interval(positive_k, n) if n else wilson_interval(0, 0)
    rate = interval.point_estimate

    complement_n = complement_positive_k + complement_negative_n
    complement_rate = complement_positive_k / complement_n if complement_n else 0.0

    supported = meets_minimum_support(eligible_n=n, positive_k=positive_k)

    return ConditionalCell(
        eligible_n=n, positive_k=positive_k, rate=rate,
        wilson_95_lower=interval.lower, wilson_95_upper=interval.upper,
        baseline_rate=baseline_rate, absolute_difference=rate - baseline_rate,
        lift=(rate / baseline_rate) if baseline_rate > 0 else None,
        complement_n=complement_n, complement_k=complement_positive_k, complement_rate=complement_rate,
        risk_ratio=(rate / complement_rate) if complement_rate > 0 else None,
        support_label=SupportLabel.EXPLORATORY_CANDIDATE if supported else SupportLabel.INSUFFICIENT_SUPPORT,
    )


def classify_shape(ordered_known_bin_rates: list[float]) -> Shape:
    """Descriptive only -- never enforced, never used to select or
    exclude a feature. Requires at least 3 known (non-UNKNOWN) bins in
    their real quintile order."""

    rates = ordered_known_bin_rates
    if len(rates) < 3:
        return Shape.NOT_APPLICABLE

    diffs = [rates[i + 1] - rates[i] for i in range(len(rates) - 1)]
    signs = [1 if d > 0 else (-1 if d < 0 else 0) for d in diffs]
    non_zero = [s for s in signs if s != 0]
    if not non_zero:
        return Shape.NON_MONOTONIC
    if all(s > 0 for s in non_zero):
        return Shape.MONOTONIC_INCREASING
    if all(s < 0 for s in non_zero):
        return Shape.MONOTONIC_DECREASING

    # single sign change: U or inverted-U; more than one -> noisy/non-monotonic
    sign_changes = sum(1 for a, b in pairwise(non_zero) if a != b)
    if sign_changes == 1:
        return Shape.U_SHAPED if non_zero[0] < 0 else Shape.INVERTED_U_SHAPED
    return Shape.NON_MONOTONIC
