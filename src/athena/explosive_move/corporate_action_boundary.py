"""EM-1r5's reusable corporate-action contamination contract.

Owner decision, 2026-08-26: corporate-action contamination is
**calculation-window-dependent, not proximity-window-dependent**. A
price-dependent calculation is invalid only when it requires values from
both sides of an unadjusted corporate action's ex-date boundary -- not
merely because a session falls near one.

Derived directly from ``config/explosive_move.json``'s already-frozen
``event_contract.reference_prices``/``target_horizon`` (EM-1a):
``TOUCH`` and ``CLOSE`` reference ``previous_session_adjusted_close`` and
target the current regular session -- contaminated exactly when
``session_date`` **is** a corporate action's ``ex_date`` for that
instrument, since that is precisely when the previous session sits on the
pre-action ("cum") side and the current session already sits on the
post-action ("ex") side. Once both sides of a comparison are on the same
side of every relevant ex_date -- whether that is one session later or a
hundred -- there is no contamination from that action, regardless of
proximity. ``OPEN_TO_HIGH`` references only the current session's own
``regular_session_open`` -- open and high are always on the same side of
any boundary within a single session, so it never crosses one.

No price adjustment, no cumulative adjustment factors, no fixed +/-N-day
window. This module computes the contract's `corporate_action_in_reference_window`
input; it does not decide admission itself (that stays
``assess_symbol_day_readiness`` in ``contracts.py``, unmodified).
"""

from __future__ import annotations

from datetime import date

from athena.explosive_move.contracts import EventFamily


def corporate_action_crosses_boundary(
    *,
    event_family: EventFamily,
    session_date: date,
    action_ex_dates: frozenset[date],
) -> bool:
    """True iff this event family's reference/target price window spans an
    unadjusted corporate-action ex-date boundary for this instrument-day.

    Generalizes cleanly to multiple actions for the same instrument: any
    ex_date exactly equal to session_date crosses the boundary (today's
    "previous session" would be pre-action while today's own session is
    already post-action); an ex_date on any other date does not, because
    both the reference and target then sit on the same side.
    """

    if event_family is EventFamily.OPEN_TO_HIGH:
        return False
    return session_date in action_ex_dates


def naive_ex_date_plus_n_window_excludes(
    *,
    event_family: EventFamily,
    session_date: date,
    action_ex_dates: frozenset[date],
    trading_sessions_ordered: tuple[date, ...],
    n_sessions_after: int = 3,
) -> bool:
    """Reference implementation of the REJECTED alternative (a fixed
    ex_date + N trading-session proximity window, applied to every event
    family including OPEN_TO_HIGH) -- exists only so EM-1r5 can measure and
    report how much *unnecessary* exclusion that approach would have
    caused relative to the boundary-crossing rule actually adopted. Not
    used by any admission decision.
    """

    if session_date not in trading_sessions_ordered:
        return False
    anchored: set[date] = set()
    for ex_date in action_ex_dates:
        if ex_date not in trading_sessions_ordered:
            continue
        ex_idx = trading_sessions_ordered.index(ex_date)
        anchored.update(
            trading_sessions_ordered[ex_idx : ex_idx + 1 + n_sessions_after]
        )
    return session_date in anchored
