from __future__ import annotations

from athena.data.id6b1b_quality_adjusted_policy_baseline import (
    _dual_timeframe_evaluable,
    _dual_timeframe_match,
    _m5_only_evaluable,
    _m5_only_match,
    analyze_observations,
)


def _row(**overrides):
    base = {
        "instrument_id": "NSE:TEST",
        "session_date": "2026-08-26",
        "decision_type": "WATCH",
        "checkpoint": "09:30",
        "vwap_available": True,
        "vwap_positive": True,
        "five_min_available": True,
        "five_min_bullish": True,
        "fifteen_min_available": True,
        "fifteen_min_bullish": True,
        "trend_label": "BULLISH",
        "rs_stock_vs_market": "OUTPERFORM",
        "rs_stock_vs_sector": "UNKNOWN",
        "rvol_available": False,
        "rs_support": True,
        "rvol_support": False,
        "candidate_policy_match": True,
    }
    base.update(overrides)
    return base


def test_dual_timeframe_evaluable_requires_m15_leg() -> None:
    """§5 of the owner's spec: the dual-timeframe evaluability contract must
    require the M15 leg explicitly -- an aggregate BULLISH label alone must
    not be treated as proof it exists."""
    assert _dual_timeframe_evaluable(_row()) is True
    assert _dual_timeframe_evaluable(_row(fifteen_min_available=False)) is False


def test_dual_timeframe_evaluable_requires_vwap_and_rs_or_rvol() -> None:
    assert _dual_timeframe_evaluable(_row(vwap_available=False)) is False
    unsupported_rs_rvol = _row(
        rs_stock_vs_market="UNKNOWN", rs_stock_vs_sector="UNKNOWN", rvol_available=False
    )
    assert _dual_timeframe_evaluable(unsupported_rs_rvol) is False
    # RVOL alone is sufficient when both RS legs are UNKNOWN.
    rvol_only = _row(
        rs_stock_vs_market="UNKNOWN", rs_stock_vs_sector="UNKNOWN", rvol_available=True
    )
    assert _dual_timeframe_evaluable(rvol_only) is True


def test_m5_only_evaluable_ignores_m15() -> None:
    """The relaxed research variant (owner §7) must remain evaluable even
    when M15 -- the chronically off-grid timeframe -- is unavailable."""
    row = _row(fifteen_min_available=False, fifteen_min_bullish=None)
    assert _m5_only_evaluable(row) is True
    assert _dual_timeframe_evaluable(row) is False


def test_dual_timeframe_match_mirrors_candidate_policy_match_field() -> None:
    """By construction (aggregate BULLISH already requires both timeframes,
    verified against ``_aggregate_trend`` source), the dual-timeframe match
    predicate must equal the existing harness field exactly, not recompute
    it independently."""
    assert _dual_timeframe_match(_row(candidate_policy_match=True)) is True
    assert _dual_timeframe_match(_row(candidate_policy_match=False)) is False


def test_m5_only_match_ignores_fifteen_min_bullish_value() -> None:
    """The M5-only match must fire even when the 15m leg is bearish or
    unavailable, since the relaxed variant deliberately does not consume
    it."""
    row = _row(fifteen_min_bullish=False, fifteen_min_available=False)
    assert _m5_only_match(row) is True
    not_bullish_m5 = _row(five_min_bullish=False)
    assert _m5_only_match(not_bullish_m5) is False
    no_rs_or_rvol = _row(rs_support=False, rvol_support=False)
    assert _m5_only_match(no_rs_or_rvol) is False


def test_analyze_observations_reports_non_evaluability_reasons() -> None:
    rows = [
        _row(),
        _row(fifteen_min_available=False),
        _row(vwap_available=False, fifteen_min_available=False),
    ]
    result = analyze_observations(rows)
    assert result["total_observations"] == 3
    assert result["dual_timeframe_evaluable"] == 1
    assert result["dual_timeframe_unavailable"] == 2
    assert result["non_evaluability_reasons"] == {
        "m15_trend_unavailable": 1,
        "vwap_unavailable+m15_trend_unavailable": 1,
    }


def test_analyze_observations_flicker_detects_true_then_later_false() -> None:
    """Same instrument/session/decision_type across checkpoints; a later
    checkpoint dropping to no-match after an earlier match must be counted
    as flicker, matching ID-6B.1A's own flicker definition."""
    rows = [
        _row(checkpoint="09:30", candidate_policy_match=True),
        _row(checkpoint="09:45", candidate_policy_match=False),
        _row(checkpoint="10:00", candidate_policy_match=True),
    ]
    result = analyze_observations(rows)
    assert result["flicker_dual_evaluable_definition"]["multi_checkpoint_groups"] == 1
    assert result["flicker_dual_evaluable_definition"]["true_then_later_false"] == 1


def test_analyze_observations_by_decision_type_splits_watch_and_trade() -> None:
    rows = [
        _row(decision_type="WATCH", candidate_policy_match=True),
        _row(decision_type="TRADE", candidate_policy_match=False, five_min_bullish=False),
    ]
    result = analyze_observations(rows)
    assert result["by_decision_type"]["WATCH"]["observations"] == 1
    assert result["by_decision_type"]["TRADE"]["observations"] == 1
    assert result["by_decision_type"]["WATCH"]["candidate_match_population_rate"]["count"] == 1
    assert result["by_decision_type"]["TRADE"]["candidate_match_population_rate"]["count"] == 0
