"""EM-3 v1 conditional-analysis primitives: deterministic quintile
binning (dedup-reduces bin count rather than fabricating boundaries),
the forbidden VALIDATED_SIGNAL label never appearing, and shape
classification."""

from __future__ import annotations

from decimal import Decimal

from athena.explosive_move.conditional_analysis import (
    Shape,
    SupportLabel,
    assign_bin,
    bin_label,
    classify_shape,
    compute_conditional_cell,
    compute_quintile_edges,
)


def _d(values):
    return [Decimal(str(v)) for v in values]


def test_quintile_edges_on_a_uniform_distribution():
    values = _d(range(1, 101))  # 1..100, evenly spread
    edges = compute_quintile_edges(values)
    assert len(edges) == 4  # 5 real, distinct bins


def test_quintile_edges_dedup_reduces_bin_count_never_fabricates():
    """All values identical -> every quantile collides -> a single edge
    survives dedup (2 bins: <edge and >=edge), not 4 fabricated ones."""
    values = _d([50] * 100)
    edges = compute_quintile_edges(values)
    assert len(set(edges)) == len(edges)  # no duplicate edges ever
    assert len(edges) <= 1


def test_quintile_edges_empty_input():
    assert compute_quintile_edges([]) == ()


def test_assign_bin_boundary_semantics_are_half_open():
    edges = _d([10, 20, 30, 40])
    assert assign_bin(Decimal("5"), tuple(edges)) == 0
    assert assign_bin(Decimal("10"), tuple(edges)) == 1  # exactly at edge -> next bin
    assert assign_bin(Decimal("15"), tuple(edges)) == 1
    assert assign_bin(Decimal("40"), tuple(edges)) == 4  # exactly at last edge -> top bin
    assert assign_bin(Decimal("999"), tuple(edges)) == 4


def test_bin_label_all_when_no_edges():
    assert bin_label(0, ()) == "ALL"


def test_bin_label_readable_for_each_position():
    edges = _d([10, 20, 30])
    assert bin_label(0, tuple(edges)).startswith("Q1")
    assert bin_label(3, tuple(edges)).startswith("Q4")


# --------------------------------------------------------------------------- #
# ConditionalCell: exit-semantics discipline (owner item 8 -- never
# VALIDATED_SIGNAL) and the min-support-only selection gate.
# --------------------------------------------------------------------------- #

def test_supported_cell_is_labelled_exploratory_candidate_never_validated():
    cell = compute_conditional_cell(
        positive_k=50, negative_n=5000, baseline_rate=0.01,
        complement_positive_k=200, complement_negative_n=19800,
    )
    assert cell.support_label is SupportLabel.EXPLORATORY_CANDIDATE
    assert cell.support_label.value != "VALIDATED_SIGNAL"
    for label in SupportLabel:
        assert label.value != "VALIDATED_SIGNAL"


def test_unsupported_cell_is_insufficient_support():
    cell = compute_conditional_cell(
        positive_k=3, negative_n=100, baseline_rate=0.01,
        complement_positive_k=200, complement_negative_n=19800,
    )
    assert cell.support_label is SupportLabel.INSUFFICIENT_SUPPORT


def test_lift_and_absolute_difference_are_computed_against_the_given_baseline():
    cell = compute_conditional_cell(
        positive_k=100, negative_n=9900, baseline_rate=0.005,
        complement_positive_k=50, complement_negative_n=49950,
    )
    assert cell.rate == 0.01
    assert cell.absolute_difference == cell.rate - 0.005
    assert cell.lift == cell.rate / 0.005


def test_lift_is_none_when_baseline_rate_is_zero():
    cell = compute_conditional_cell(
        positive_k=10, negative_n=1000, baseline_rate=0.0,
        complement_positive_k=0, complement_negative_n=100,
    )
    assert cell.lift is None


def test_risk_ratio_is_none_when_complement_rate_is_zero():
    cell = compute_conditional_cell(
        positive_k=10, negative_n=1000, baseline_rate=0.01,
        complement_positive_k=0, complement_negative_n=500,
    )
    assert cell.risk_ratio is None


def test_complement_metrics_are_independent_of_the_bin_population():
    cell = compute_conditional_cell(
        positive_k=10, negative_n=990, baseline_rate=0.01,
        complement_positive_k=500, complement_negative_n=9500,
    )
    assert cell.complement_n == 10000
    assert cell.complement_k == 500
    assert cell.complement_rate == 0.05


# --------------------------------------------------------------------------- #
# Shape: descriptive only, never enforced.
# --------------------------------------------------------------------------- #

def test_shape_monotonic_increasing():
    assert classify_shape([0.01, 0.02, 0.03, 0.05]) is Shape.MONOTONIC_INCREASING


def test_shape_monotonic_decreasing():
    assert classify_shape([0.05, 0.03, 0.02, 0.01]) is Shape.MONOTONIC_DECREASING


def test_shape_u_shaped():
    assert classify_shape([0.05, 0.01, 0.06]) is Shape.U_SHAPED


def test_shape_inverted_u_shaped():
    assert classify_shape([0.01, 0.06, 0.01]) is Shape.INVERTED_U_SHAPED


def test_shape_non_monotonic_noisy():
    assert classify_shape([0.01, 0.05, 0.02, 0.06, 0.01]) is Shape.NON_MONOTONIC


def test_shape_not_applicable_with_fewer_than_three_bins():
    assert classify_shape([0.01]) is Shape.NOT_APPLICABLE
    assert classify_shape([0.01, 0.02]) is Shape.NOT_APPLICABLE
    assert classify_shape([]) is Shape.NOT_APPLICABLE


def test_shape_flat_series_is_non_monotonic():
    assert classify_shape([0.02, 0.02, 0.02]) is Shape.NON_MONOTONIC
