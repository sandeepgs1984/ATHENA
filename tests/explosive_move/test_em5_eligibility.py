"""EM-5 candidate eligibility -- hard vs. contextual per the frozen
contract's Section 4 table. Every hard gate is checked in priority
order; contextual inputs (price-band UNKNOWN) never hard-exclude."""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from zoneinfo import ZoneInfo

from athena.domain.enums import SessionType
from athena.explosive_move.live.eligibility import (
    SCANNABLE_SESSION_TYPES,
    EligibilityResult,
    Feasibility,
    HardIneligibilityReason,
    PriceBand,
    evaluate_candidate_eligibility,
    session_is_scannable,
)

IST = ZoneInfo("Asia/Kolkata")


def _t(h, m):
    return datetime(2026, 8, 28, h, m, tzinfo=IST)


def _base_kwargs(**overrides):
    defaults = {
        "in_universe": True,
        "most_recent_candle_ts": _t(11, 58),
        "as_of": _t(12, 0),
        "max_staleness_minutes": 10.0,
        "has_checkpoint_reference_price": True,
    }
    defaults.update(overrides)
    return defaults


def test_eligible_candidate_with_no_price_band_source_is_feasibility_unknown():
    result = evaluate_candidate_eligibility(**_base_kwargs())
    assert result == EligibilityResult(True, None, Feasibility.FEASIBILITY_UNKNOWN)


def test_not_in_universe_is_hard_ineligible():
    result = evaluate_candidate_eligibility(**_base_kwargs(in_universe=False))
    assert result.hard_eligible is False
    assert result.hard_ineligible_reason == HardIneligibilityReason.NOT_IN_UNIVERSE


def test_no_candle_at_all_is_stale_data():
    result = evaluate_candidate_eligibility(**_base_kwargs(most_recent_candle_ts=None))
    assert result.hard_ineligible_reason == HardIneligibilityReason.STALE_DATA


def test_candle_older_than_max_staleness_is_stale_data():
    result = evaluate_candidate_eligibility(**_base_kwargs(most_recent_candle_ts=_t(11, 45)))
    assert result.hard_ineligible_reason == HardIneligibilityReason.STALE_DATA


def test_candle_within_max_staleness_is_not_stale():
    result = evaluate_candidate_eligibility(**_base_kwargs(most_recent_candle_ts=_t(11, 51)))
    assert result.hard_eligible is True


def test_missing_checkpoint_reference_price_is_hard_ineligible():
    result = evaluate_candidate_eligibility(**_base_kwargs(has_checkpoint_reference_price=False))
    assert result.hard_ineligible_reason == HardIneligibilityReason.NO_OBSERVABLE_PRICE_AT_CHECKPOINT


def test_known_and_conclusive_price_band_excludes():
    band = PriceBand(lower_limit=Decimal("90"), upper_limit=Decimal("110"))
    result = evaluate_candidate_eligibility(
        **_base_kwargs(price_band=band, target_price=Decimal("120"))
    )
    assert result.hard_eligible is False
    assert result.hard_ineligible_reason == HardIneligibilityReason.PRICE_BAND_IMPOSSIBLE
    assert result.feasibility == Feasibility.PRICE_BAND_IMPOSSIBLE


def test_known_and_reachable_price_band_is_feasible_and_eligible():
    band = PriceBand(lower_limit=Decimal("90"), upper_limit=Decimal("110"))
    result = evaluate_candidate_eligibility(
        **_base_kwargs(price_band=band, target_price=Decimal("105"))
    )
    assert result.hard_eligible is True
    assert result.feasibility == Feasibility.FEASIBLE


def test_price_band_unknown_never_hard_excludes():
    result = evaluate_candidate_eligibility(**_base_kwargs(price_band=None, target_price=Decimal("120")))
    assert result.hard_eligible is True
    assert result.feasibility == Feasibility.FEASIBILITY_UNKNOWN


def test_universe_check_takes_priority_over_staleness():
    result = evaluate_candidate_eligibility(
        **_base_kwargs(in_universe=False, most_recent_candle_ts=None)
    )
    assert result.hard_ineligible_reason == HardIneligibilityReason.NOT_IN_UNIVERSE


def test_scannable_session_types_are_normal_and_special_only():
    assert {SessionType.NORMAL, SessionType.SPECIAL} == SCANNABLE_SESSION_TYPES
    assert session_is_scannable(SessionType.NORMAL) is True
    assert session_is_scannable(SessionType.SPECIAL) is True
    assert session_is_scannable(SessionType.MUHURAT) is False
    assert session_is_scannable(SessionType.HOLIDAY) is False
    assert session_is_scannable(SessionType.WEEKEND) is False
    assert session_is_scannable(SessionType.KNOWN_UNSUPPORTED_SPECIAL_SESSION) is False
