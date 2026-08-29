"""Session Context domain artifacts (ID-1).

Foundation only — no signals, no trading interpretation. Answers two
questions: "what trustworthy intraday data do we actually have right now?"
and "what part of the trading day is this?" Nothing here decides whether a
stock is actionable; that is EntryQualification's job, later.

Pure, immutable, explainable (ADR-005): every non-``SUFFICIENT`` data-quality
state and every ``SessionContext``/``TimeframeProvenance`` instance carries a
mandatory, non-empty explanation, exactly like every other analytical result
in this codebase (``IndicatorResult``, ``RegimeResult``, ``SectorHealthResult``, …).
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime
from enum import Enum, unique

from athena.domain.enums import SessionType, Timeframe


@unique
class SessionPhase(str, Enum):
    """Objective, calendar/config-derived phase of the trading day.

    Deliberately only what ``CalendarContext`` (per-day session type +
    open/close) and ``config/market.nse.json``'s ``sessions`` block
    (``preopen_start``/``preopen_end``/``open``/``close``) can already
    determine — no invented sub-windows (e.g. no "power hour").
    """

    #: Not a trading day at all (weekend/holiday/unsupported special session).
    NOT_A_TRADING_SESSION = "NOT_A_TRADING_SESSION"
    #: A trading day, at/after the configured pre-open start, before the
    #: configured/day-specific regular open. Covers NSE's real pre-open
    #: order-collection + matching window as one bucket — the calendar
    #: config does not distinguish those two sub-phases, so this doesn't either.
    PRE_OPEN = "PRE_OPEN"
    #: At/after the day's regular open, before its regular close.
    REGULAR = "REGULAR"
    #: Before the day's pre-open start, or at/after its regular close (or a
    #: real trading day whose exact open/close is not yet notified, e.g. an
    #: unconfirmed Muhurat session) — the exchange is not actively trading.
    CLOSED = "CLOSED"


@unique
class SessionDataQualityStatus(str, Enum):
    """One objective, code-derivable reason a caller should (or should not)
    trust the intraday data behind a ``SessionContext``/``TimeframeProvenance``.

    Ordered worst-to-best is NOT implied by declaration order; see
    ``engine.py``'s explicit priority list for how a combined status is chosen.
    """

    #: No data-quality concern found.
    SUFFICIENT = "SUFFICIENT"
    #: Today is not a trading session at all — intraday assessment does not apply.
    SESSION_NOT_ACTIVE = "SESSION_NOT_ACTIVE"
    #: Zero candles exist for this instrument+timeframe at all, on any date.
    TIMEFRAME_UNAVAILABLE = "TIMEFRAME_UNAVAILABLE"
    #: Candles exist historically for this timeframe, but none match today's
    #: session date.
    NO_CURRENT_SESSION_DATA = "NO_CURRENT_SESSION_DATA"
    #: Today's session has bars, but the calendar cannot yet state which bars
    #: should exist (a real trading day whose exact open/close time is not
    #: notified — e.g. an unconfirmed Muhurat) — completeness is honestly
    #: unassessable, never guessed either way.
    INSUFFICIENT_HISTORY = "INSUFFICIENT_HISTORY"
    #: Today's session has bars and expectations ARE computable (via the
    #: existing calendar-expectations contract, `data/validation/calendar_expectations.py`),
    #: and at least one calendar-expected, already-due bar is missing.
    EXPECTED_BAR_MISSING = "EXPECTED_BAR_MISSING"
    #: No quote exists for this instrument at all.
    QUOTE_UNAVAILABLE = "QUOTE_UNAVAILABLE"


@dataclass(frozen=True, slots=True)
class TimeframeProvenance:
    """Reusable provenance contract for any intraday-derived analytical
    result (ID-0's finding: ``IndicatorResult`` itself does not carry enough
    of this for safe multi-timeframe consumption). Generic over timeframe —
    not specific to sessions; a future intraday indicator wrapper can reuse
    this exact type instead of inventing its own.
    """

    instrument_id: str
    timeframe: Timeframe
    session_date: date
    as_of: datetime
    window_start: datetime | None
    window_end: datetime | None
    latest_completed_bar_ts: datetime | None
    bar_count: int
    quality: SessionDataQualityStatus
    explanation: str

    def __post_init__(self) -> None:
        if not self.instrument_id:
            raise ValueError("TimeframeProvenance.instrument_id is mandatory")
        if self.as_of.tzinfo is None:
            raise ValueError("TimeframeProvenance.as_of must be timezone-aware")
        if self.window_start is not None and self.window_start.tzinfo is None:
            raise ValueError("TimeframeProvenance.window_start must be timezone-aware")
        if self.window_end is not None and self.window_end.tzinfo is None:
            raise ValueError("TimeframeProvenance.window_end must be timezone-aware")
        if self.latest_completed_bar_ts is not None and self.latest_completed_bar_ts.tzinfo is None:
            raise ValueError("TimeframeProvenance.latest_completed_bar_ts must be timezone-aware")
        if self.bar_count < 0:
            raise ValueError(f"TimeframeProvenance.bar_count must be >= 0, got {self.bar_count}")
        if not self.explanation:
            raise ValueError("TimeframeProvenance.explanation is mandatory (ADR-005)")


@dataclass(frozen=True, slots=True)
class SessionContext:
    """Deterministic, explainable description of the current trading session
    for one instrument. Descriptive only — never a signal, never a gate."""

    instrument_id: str
    session_date: date
    exchange: str
    timezone: str
    as_of: datetime
    session_type: SessionType
    phase: SessionPhase
    session_open_ts: datetime | None
    session_close_ts: datetime | None
    elapsed_seconds: int | None
    remaining_seconds: int | None
    latest_quote_ts: datetime | None
    five_min: TimeframeProvenance
    fifteen_min: TimeframeProvenance
    data_quality: SessionDataQualityStatus
    explanation: str

    def __post_init__(self) -> None:
        if not self.instrument_id:
            raise ValueError("SessionContext.instrument_id is mandatory")
        if self.as_of.tzinfo is None:
            raise ValueError("SessionContext.as_of must be timezone-aware")
        if self.session_open_ts is not None and self.session_open_ts.tzinfo is None:
            raise ValueError("SessionContext.session_open_ts must be timezone-aware")
        if self.session_close_ts is not None and self.session_close_ts.tzinfo is None:
            raise ValueError("SessionContext.session_close_ts must be timezone-aware")
        if self.latest_quote_ts is not None and self.latest_quote_ts.tzinfo is None:
            raise ValueError("SessionContext.latest_quote_ts must be timezone-aware")
        if self.elapsed_seconds is not None and self.elapsed_seconds < 0:
            raise ValueError("SessionContext.elapsed_seconds must be >= 0")
        if self.remaining_seconds is not None and self.remaining_seconds < 0:
            raise ValueError("SessionContext.remaining_seconds must be >= 0")
        if not self.explanation:
            raise ValueError("SessionContext.explanation is mandatory (ADR-005)")
