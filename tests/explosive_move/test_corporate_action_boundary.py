"""EM-1r5's corporate-action contamination contract (owner decision,
2026-08-26): a calculation is invalid only when it spans an unadjusted
corporate-action ex-date boundary -- not merely because it is near one.
Tests mirror the owner's own illustrative examples directly."""

from __future__ import annotations

from datetime import date, timedelta

from athena.explosive_move.contracts import EventFamily
from athena.explosive_move.corporate_action_boundary import (
    corporate_action_crosses_boundary,
    naive_ex_date_plus_n_window_excludes,
)

EX_DATE = date(2024, 3, 15)


def test_touch_crosses_boundary_exactly_on_the_ex_date_session():
    """TOUCH references previous_session_adjusted_close -- the owner's own
    example: 'previous close -> current-session high/close' straddles the
    boundary precisely when today IS the ex-date."""
    assert corporate_action_crosses_boundary(
        event_family=EventFamily.TOUCH, session_date=EX_DATE,
        action_ex_dates=frozenset({EX_DATE}),
    ) is True


def test_close_crosses_boundary_exactly_on_the_ex_date_session():
    assert corporate_action_crosses_boundary(
        event_family=EventFamily.CLOSE, session_date=EX_DATE,
        action_ex_dates=frozenset({EX_DATE}),
    ) is True


def test_touch_does_not_cross_boundary_one_two_or_three_sessions_after():
    """The owner's explicit rejection of proximity: once both reference and
    target are on the post-action side, do not exclude merely for being
    1-3 sessions after the event."""
    for offset in (1, 2, 3, 10, 100):
        later = EX_DATE + timedelta(days=offset)
        assert corporate_action_crosses_boundary(
            event_family=EventFamily.TOUCH, session_date=later,
            action_ex_dates=frozenset({EX_DATE}),
        ) is False, f"offset={offset} must not be excluded"


def test_touch_does_not_cross_boundary_before_the_ex_date():
    """A session entirely before the action is on the pre-action side for
    both reference and target -- not contaminated either."""
    earlier = EX_DATE - timedelta(days=1)
    assert corporate_action_crosses_boundary(
        event_family=EventFamily.TOUCH, session_date=earlier,
        action_ex_dates=frozenset({EX_DATE}),
    ) is False


def test_open_to_high_never_crosses_a_boundary():
    """The owner's own example: OPEN_TO_HIGH uses only same-session prices
    (regular_session_open -> session high) -- never excluded merely
    because the session happens to be an ex-date."""
    for d in (EX_DATE - timedelta(days=1), EX_DATE, EX_DATE + timedelta(days=1)):
        assert corporate_action_crosses_boundary(
            event_family=EventFamily.OPEN_TO_HIGH, session_date=d,
            action_ex_dates=frozenset({EX_DATE}),
        ) is False


def test_multiple_ex_dates_for_the_same_instrument_each_gate_their_own_session():
    ex_dates = frozenset({date(2024, 3, 15), date(2024, 9, 1)})
    assert corporate_action_crosses_boundary(
        event_family=EventFamily.CLOSE, session_date=date(2024, 3, 15),
        action_ex_dates=ex_dates,
    ) is True
    assert corporate_action_crosses_boundary(
        event_family=EventFamily.CLOSE, session_date=date(2024, 9, 1),
        action_ex_dates=ex_dates,
    ) is True
    assert corporate_action_crosses_boundary(
        event_family=EventFamily.CLOSE, session_date=date(2024, 6, 1),
        action_ex_dates=ex_dates,
    ) is False


def test_no_action_means_never_contaminated():
    assert corporate_action_crosses_boundary(
        event_family=EventFamily.CLOSE, session_date=EX_DATE,
        action_ex_dates=frozenset(),
    ) is False


# --------------------------------------------------------------------------- #
# The rejected naive alternative -- kept only so EM-1r5 can quantify how
# much unnecessary exclusion it would have caused, never used for admission.
# --------------------------------------------------------------------------- #

_SESSIONS = tuple(EX_DATE + timedelta(days=i) for i in range(-5, 10))


def test_naive_rule_excludes_sessions_the_boundary_rule_would_admit():
    """Demonstrates the actual over-exclusion: 2 sessions after ex_date is
    admissible under the boundary rule but excluded under the naive one."""
    two_after = EX_DATE + timedelta(days=2)
    assert corporate_action_crosses_boundary(
        event_family=EventFamily.TOUCH, session_date=two_after,
        action_ex_dates=frozenset({EX_DATE}),
    ) is False
    assert naive_ex_date_plus_n_window_excludes(
        event_family=EventFamily.TOUCH, session_date=two_after,
        action_ex_dates=frozenset({EX_DATE}),
        trading_sessions_ordered=_SESSIONS, n_sessions_after=3,
    ) is True


def test_naive_rule_also_wrongly_excludes_open_to_high():
    """The naive rule (unlike the boundary rule) does not distinguish
    event families -- another way it over-excludes."""
    assert naive_ex_date_plus_n_window_excludes(
        event_family=EventFamily.OPEN_TO_HIGH, session_date=EX_DATE,
        action_ex_dates=frozenset({EX_DATE}),
        trading_sessions_ordered=_SESSIONS, n_sessions_after=3,
    ) is True


def test_naive_rule_does_not_exclude_beyond_its_own_window():
    far_after = EX_DATE + timedelta(days=8)
    assert naive_ex_date_plus_n_window_excludes(
        event_family=EventFamily.TOUCH, session_date=far_after,
        action_ex_dates=frozenset({EX_DATE}),
        trading_sessions_ordered=_SESSIONS, n_sessions_after=3,
    ) is False
