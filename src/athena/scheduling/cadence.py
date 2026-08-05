"""Schedule cadence evaluation (M10.2 + R6).

Pure functions over injected ``as_of`` and last-run markers — no wall clock,
no cron library. Determines whether PREMARKET / REFRESH / CLOSING dry-run
cycles are due per Blueprint §8 and ``SchedulingConfig``.
"""

from __future__ import annotations

from datetime import date, datetime, time, timedelta

from athena.config.models import SchedulingConfig, SessionsConfig
from athena.domain.enums import RunTrigger


def refresh_interval_minutes(config: SchedulingConfig, base_interval: int) -> int:
    """Effective refresh interval: scheduling override or base.json value."""
    override = config.refresh.interval_minutes
    return int(override if override is not None else base_interval)


def is_premarket_due(
    as_of: datetime,
    *,
    sessions: SessionsConfig,
    config: SchedulingConfig,
    last_premarket_date: date | None,
    is_trading_day: bool = True,
) -> bool:
    """True once per calendar day at/after ``premarket.run_at``, before open."""
    if as_of.tzinfo is None:
        raise ValueError("as_of must be timezone-aware")
    if not is_trading_day:
        return False
    if not config.premarket.enabled:
        return False
    local = as_of
    if last_premarket_date is not None and last_premarket_date >= local.date():
        return False
    clock = local.time()
    run_at: time = config.premarket.run_at
    if clock < run_at:
        return False
    return clock < sessions.open


def is_refresh_due(
    as_of: datetime,
    *,
    sessions: SessionsConfig,
    config: SchedulingConfig,
    base_interval_minutes: int,
    last_refresh_ts: datetime | None,
    is_trading_day: bool = True,
) -> bool:
    """True every N minutes while the regular session is open (inclusive open,
    exclusive close)."""
    if as_of.tzinfo is None:
        raise ValueError("as_of must be timezone-aware")
    if not is_trading_day:
        return False
    if not config.refresh.enabled:
        return False
    clock = as_of.time()
    if clock < sessions.open or clock >= sessions.close:
        return False
    interval = refresh_interval_minutes(config, base_interval_minutes)
    if last_refresh_ts is None:
        return True
    if last_refresh_ts.tzinfo is None:
        raise ValueError("last_refresh_ts must be timezone-aware")
    return as_of - last_refresh_ts >= timedelta(minutes=interval)


def is_fast_due(
    as_of: datetime,
    *,
    sessions: SessionsConfig,
    config: SchedulingConfig,
    last_fast_ts: datetime | None,
    is_trading_day: bool = True,
) -> bool:
    """True every ``fast.interval_minutes`` while the regular session is open
    (same session-hours gating as REFRESH). Milestone B (2026-08-04): keeps
    decision-list symbols' quotes/intraday candles/decisions fresher than
    the full-universe cadence, between full REFRESH cycles."""
    if as_of.tzinfo is None:
        raise ValueError("as_of must be timezone-aware")
    if not is_trading_day:
        return False
    if not config.fast.enabled:
        return False
    clock = as_of.time()
    if clock < sessions.open or clock >= sessions.close:
        return False
    if last_fast_ts is None:
        return True
    if last_fast_ts.tzinfo is None:
        raise ValueError("last_fast_ts must be timezone-aware")
    return as_of - last_fast_ts >= timedelta(minutes=config.fast.interval_minutes)


def is_closing_due(
    as_of: datetime,
    *,
    sessions: SessionsConfig,
    config: SchedulingConfig,
    last_closing_date: date | None,
    is_trading_day: bool = True,
) -> bool:
    """True once per calendar day at/after session close and ``closing.run_at``."""
    if as_of.tzinfo is None:
        raise ValueError("as_of must be timezone-aware")
    if not is_trading_day:
        return False
    if not config.closing.enabled:
        return False
    local = as_of
    if last_closing_date is not None and last_closing_date >= local.date():
        return False
    clock = local.time()
    # Closing requires the regular session to have ended.
    if clock < sessions.close:
        return False
    run_at: time = config.closing.run_at
    effective = run_at if run_at >= sessions.close else sessions.close
    return clock >= effective


def due_triggers(
    as_of: datetime,
    *,
    sessions: SessionsConfig,
    config: SchedulingConfig,
    base_interval_minutes: int,
    last_premarket_date: date | None = None,
    last_refresh_ts: datetime | None = None,
    last_closing_date: date | None = None,
    last_fast_ts: datetime | None = None,
    is_trading_day: bool = True,
) -> tuple[RunTrigger, ...]:
    """Ordered triggers due at ``as_of`` (premarket → refresh → closing → fast).

    Owner-reported (2026-08-01): on a weekend/holiday, Kite's quotes are
    legitimately frozen at the last real session's close — every REFRESH/
    CLOSING cycle the host cron fired anyway failed the ingestion freshness
    check, all day, for as long as the market stayed shut. These functions
    only ever checked wall-clock time-of-day against configured session
    hours; nothing here knew the difference between "market is briefly
    outside hours" and "the exchange isn't open at all today." ``is_trading_day``
    is an explicit, caller-resolved input (this module stays a pure function
    of its arguments, per its own docstring — no hidden clock, no calendar
    import) so a caller with calendar access (``CalendarEngine.context_for``)
    can suppress every trigger type in one place. Defaults to ``True`` so
    every existing caller that doesn't pass it keeps its exact prior
    behavior.
    """
    if not is_trading_day:
        return ()
    due: list[RunTrigger] = []
    if is_premarket_due(
        as_of, sessions=sessions, config=config, last_premarket_date=last_premarket_date,
        is_trading_day=is_trading_day,
    ):
        due.append(RunTrigger.PREMARKET)
    if is_refresh_due(
        as_of, sessions=sessions, config=config,
        base_interval_minutes=base_interval_minutes, last_refresh_ts=last_refresh_ts,
        is_trading_day=is_trading_day,
    ):
        due.append(RunTrigger.REFRESH)
    if is_closing_due(
        as_of, sessions=sessions, config=config, last_closing_date=last_closing_date,
        is_trading_day=is_trading_day,
    ):
        due.append(RunTrigger.CLOSING)
    # Checked last: if a full REFRESH is also due this same tick, it already
    # covers every decision-list symbol more comprehensively — FAST still
    # runs (simplest, and harmless — just a redundant top-up that tick), but
    # ordering it last means the comprehensive cycle's data lands first.
    if is_fast_due(
        as_of, sessions=sessions, config=config, last_fast_ts=last_fast_ts,
        is_trading_day=is_trading_day,
    ):
        due.append(RunTrigger.FAST)
    return tuple(due)
