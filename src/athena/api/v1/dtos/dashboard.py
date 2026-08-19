"""Dashboard resource DTOs (P9.2)."""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, ConfigDict


class DashboardSummaryDTO(BaseModel):
    """Composed DTO representing aggregated workstation console statistics."""

    model_config = ConfigDict(frozen=True)

    portfolio_value: Decimal
    cash_available: Decimal
    cash_reserved: Decimal
    active_positions: int
    closed_positions: int
    exposure_by_sector: dict[str, Decimal]
    day_change_pct: Decimal | None = None
    last_scan_date: datetime | None = None
    strategies_matched: int
    regime_class: str
    health_status: str
    backup_timestamp: datetime | None = None


class CalendarHolidayDTO(BaseModel):
    """DTO representing an exchange holiday."""

    model_config = ConfigDict(frozen=True)

    date: str
    name: str


class CalendarSpecialSessionDTO(BaseModel):
    """DTO representing a special trading session (e.g. Muhurat)."""

    model_config = ConfigDict(frozen=True)

    date: str
    type: str
    name: str
    timings_note: str | None = None
    open: str | None = None
    close: str | None = None


class CalendarEventDTO(BaseModel):
    """DTO representing a scheduled market event (e.g. Budget Day)."""

    model_config = ConfigDict(frozen=True)

    date: str
    kind: str
    name: str


class CalendarDataDTO(BaseModel):
    """DTO representing consolidated exchange calendar configurations."""

    model_config = ConfigDict(frozen=True)

    years: list[int]
    holidays: list[CalendarHolidayDTO]
    special_sessions: list[CalendarSpecialSessionDTO]
    weekly_expiries: list[str]
    monthly_expiries: list[str]
    events: list[CalendarEventDTO]


class MarketSessionStatusDTO(BaseModel):
    """Current exchange-session status computed from ATHENA's Calendar Engine."""

    model_config = ConfigDict(frozen=True)

    exchange: str
    timezone: str
    as_of: datetime
    context_date: str
    session_type: str
    is_trading_session: bool
    is_market_open: bool
    phase: str
    session_open: datetime | None = None
    session_close: datetime | None = None
    next_open: datetime | None = None
    next_close: datetime | None = None
    holiday_name: str | None = None
    message: str


class AdvisoryFreshnessDTO(BaseModel):
    """Server-classified freshness of the shared dashboard market observation."""

    model_config = ConfigDict(frozen=True)

    status: Literal["CURRENT", "AGING", "STALE", "UNAVAILABLE"]
    tone: Literal["GOOD", "WARNING", "DANGER", "NEUTRAL"]
    observed_at: datetime | None = None
    age_seconds: int | None = None
    freshness_limit_seconds: int | None = None
    source: str
    headline: str
    explanation: str
    market_session: str
    next_live_at: datetime | None = None


class AthenaCycleStatusDTO(BaseModel):
    """Read-only health projection for ATHENA's full validation cadence."""

    model_config = ConfigDict(frozen=True)

    status: Literal["CURRENT", "OVERDUE", "FAILED", "CLOSED", "UNAVAILABLE"]
    tone: Literal["GOOD", "DANGER", "NEUTRAL"]
    headline: str
    explanation: str
    last_successful_at: datetime | None = None
    last_successful_run_id: str | None = None
    latest_attempt_at: datetime | None = None
    latest_attempt_status: str | None = None
    expected_by: datetime | None = None
    market_session: str
    interval_minutes: int
    grace_minutes: int
