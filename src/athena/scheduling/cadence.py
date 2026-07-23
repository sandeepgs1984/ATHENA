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
) -> bool:
    """True once per calendar day at/after ``premarket.run_at``, before open."""
    if as_of.tzinfo is None:
        raise ValueError("as_of must be timezone-aware")
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
) -> bool:
    """True every N minutes while the regular session is open (inclusive open,
    exclusive close)."""
    if as_of.tzinfo is None:
        raise ValueError("as_of must be timezone-aware")
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


def is_closing_due(
    as_of: datetime,
    *,
    sessions: SessionsConfig,
    config: SchedulingConfig,
    last_closing_date: date | None,
) -> bool:
    """True once per calendar day at/after session close and ``closing.run_at``."""
    if as_of.tzinfo is None:
        raise ValueError("as_of must be timezone-aware")
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
) -> tuple[RunTrigger, ...]:
    """Ordered triggers due at ``as_of`` (premarket → refresh → closing)."""
    due: list[RunTrigger] = []
    if is_premarket_due(
        as_of, sessions=sessions, config=config, last_premarket_date=last_premarket_date,
    ):
        due.append(RunTrigger.PREMARKET)
    if is_refresh_due(
        as_of, sessions=sessions, config=config,
        base_interval_minutes=base_interval_minutes, last_refresh_ts=last_refresh_ts,
    ):
        due.append(RunTrigger.REFRESH)
    if is_closing_due(
        as_of, sessions=sessions, config=config, last_closing_date=last_closing_date,
    ):
        due.append(RunTrigger.CLOSING)
    return tuple(due)
