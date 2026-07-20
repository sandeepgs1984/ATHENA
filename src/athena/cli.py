"""ATHENA command-line interface.

Phase 0 commands: ``athena today``, ``athena health``, ``athena version``.
Later phases add: ingest, premarket, refresh, replay, simulate.
"""

from __future__ import annotations

import argparse
import os
import sys
from datetime import date, datetime
from pathlib import Path
from zoneinfo import ZoneInfo

from athena import BLUEPRINT_VERSION, __version__
from athena.calendar.engine import CalendarEngine
from athena.config.loader import load_config
from athena.domain.enums import HealthStatus
from athena.errors import AthenaError
from athena.observability.health import run_system_checks

_STATUS_MARK = {HealthStatus.OK: "[OK]     ", HealthStatus.WARN: "[WARN]   ",
                HealthStatus.BLOCKED: "[BLOCKED]"}


def _config_dir() -> Path:
    return Path(os.environ.get("ATHENA_CONFIG_DIR", "config"))


def _repo_root() -> Path:
    return _config_dir().resolve().parent


def _cmd_today(args: argparse.Namespace) -> int:
    config = load_config(_config_dir())
    engine = CalendarEngine.from_config_dir(_config_dir(), config.market)

    if args.date:  # noqa: SIM108 - explicit block reads clearer than a long ternary
        target = date.fromisoformat(args.date)
    else:
        target = datetime.now(ZoneInfo(config.market.timezone)).date()

    ctx = engine.context_for(target)
    print(f"date            : {ctx.context_date} ({ctx.context_date.strftime('%A')})")
    print(f"exchange        : {ctx.exchange} ({ctx.timezone})")
    print(f"session         : {ctx.session_type.value}")
    if ctx.holiday_name:
        print(f"occasion        : {ctx.holiday_name}")
    if ctx.is_trading_session:
        open_s = ctx.open_time.strftime("%H:%M") if ctx.open_time else "TBD (see NSE circular)"
        close_s = ctx.close_time.strftime("%H:%M") if ctx.close_time else "TBD (see NSE circular)"
        print(f"timings         : {open_s} - {close_s}")
    print(f"weekly expiry   : {'YES' if ctx.is_weekly_expiry else 'no'}")
    print(f"monthly expiry  : {'YES' if ctx.is_monthly_expiry else 'no'}")
    for event in ctx.events:
        print(f"event           : [{event.kind}] {event.name}")
    return 0


def _cmd_health(args: argparse.Namespace) -> int:
    for_date = date.fromisoformat(args.date) if args.date else None
    report = run_system_checks(_config_dir(), _repo_root(), for_date=for_date)
    print(f"ATHENA system health @ {report.ts.isoformat()}")
    for check in report.checks:
        print(f"  {_STATUS_MARK[check.status]} {check.name}: {check.detail}")
    print(f"overall: {report.status.value}")
    return 0 if report.status is not HealthStatus.BLOCKED else 2


def _cmd_version(_: argparse.Namespace) -> int:
    print(f"athena {__version__} ({BLUEPRINT_VERSION})")
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="athena",
        description="ATHENA — decision intelligence for NSE intraday trading. Never places orders.",
    )
    sub = parser.add_subparsers(dest="command", required=True)

    p_today = sub.add_parser("today", help="Show the CalendarContext for today (or --date)")
    p_today.add_argument("--date", help="ISO date, e.g. 2026-01-26")
    p_today.set_defaults(func=_cmd_today)

    p_health = sub.add_parser("health", help="Run the system-health pre-flight (F-8)")
    p_health.add_argument("--date", help="ISO date to check calendar coverage for")
    p_health.set_defaults(func=_cmd_health)

    p_version = sub.add_parser("version", help="Show software + blueprint versions")
    p_version.set_defaults(func=_cmd_version)

    args = parser.parse_args(argv)
    try:
        return int(args.func(args))
    except AthenaError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
