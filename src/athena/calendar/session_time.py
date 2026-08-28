"""Remaining-session-time arithmetic -- a pure function, no hidden
clock, matching ``resolve_as_of.py``'s own established convention
(explicit datetime inputs only). Added for EM-5 (ADR-012 Section 8
requires feasibility evidence to include ``remaining_session_minutes``;
no reusable calendar helper existed for it before this).

Deliberately contains no EMR-specific policy (no probability logic, no
threshold, no feasibility verdict) -- it only answers "how much session
time is left," which callers interpret however their own domain needs.
"""

from __future__ import annotations

from datetime import datetime


def remaining_session_minutes(as_of: datetime, session_close: datetime) -> float:
    """Minutes from ``as_of`` to ``session_close`` -- negative once past
    close, which is itself meaningful information, not clamped away."""

    if as_of.tzinfo is None or session_close.tzinfo is None:
        raise ValueError("as_of and session_close must be timezone-aware")
    return (session_close - as_of).total_seconds() / 60.0
