"""ATHENA command-line interface.

Phase 0: ``athena today``, ``athena health``, ``athena version``.
Phase 10: ``athena ingest`` (M10.1), ``athena cycle`` / ``athena due`` (M10.2).
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
from athena.config.env import load_dotenv
from athena.config.loader import (
    load_config,
    load_diagnostics_config,
    load_ingestion_config,
    load_notifications_config,
    load_scheduling_config,
    load_validation_config,
)
from athena.data.ingestion import LiveIngestionEngine, build_ingest_validator
from athena.data.providers import build_market_data_provider
from athena.data.store import SqliteRepository
from athena.data.validation import QuarantineRegistry
from athena.diagnostics import PlaybookDiagnosticsService
from athena.domain.enums import HealthStatus, RunTrigger
from athena.errors import AthenaError
from athena.notifications import BriefingDispatcher
from athena.notifications.decision_source import SqliteDecisionSummarySource
from athena.observability.health import run_system_checks
from athena.scheduling import DryRunCycleOrchestrator, due_triggers

_STATUS_MARK = {HealthStatus.OK: "[OK]     ", HealthStatus.WARN: "[WARN]   ",
                HealthStatus.BLOCKED: "[BLOCKED]"}


def _config_dir() -> Path:
    return Path(os.environ.get("ATHENA_CONFIG_DIR", "config"))


def _repo_root() -> Path:
    return _config_dir().resolve().parent


def _parse_as_of(raw: str | None, tz: ZoneInfo) -> datetime:
    if raw:
        as_of = datetime.fromisoformat(raw)
        if as_of.tzinfo is None:
            return as_of.replace(tzinfo=tz)
        return as_of
    return datetime.now(tz)


def _open_repo(cfg) -> SqliteRepository:
    db_env = os.environ.get("ATHENA_DB_PATH")
    db_path = Path(db_env) if db_env else (_repo_root() / cfg.base.paths.db)
    repo = SqliteRepository(db_path)
    repo.initialize()
    return repo


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


def _build_ingest_engine(config_dir: Path, cfg, repo: SqliteRepository, tz: ZoneInfo):
    ingest_cfg = load_ingestion_config(config_dir)
    calendar = CalendarEngine.from_config_dir(config_dir, cfg.market)
    validation = load_validation_config(config_dir)
    validator = build_ingest_validator(calendar, validation, ingest_cfg, tz)
    provider = build_market_data_provider(
        config_dir, base_dir=_repo_root(), provider_name=ingest_cfg.provider,
    )
    return LiveIngestionEngine(
        provider, repo, validator, QuarantineRegistry(), ingest_cfg, validation, tzinfo=tz,
    ), ingest_cfg


def _cmd_ingest(args: argparse.Namespace) -> int:
    """One live ingest cycle (M10.1 / R4): configured provider → validate → SQLite."""
    config_dir = _config_dir()
    cfg = load_config(config_dir)
    tz = ZoneInfo(cfg.market.timezone)
    as_of = _parse_as_of(args.as_of, tz)
    with _open_repo(cfg) as repo:
        engine, _ = _build_ingest_engine(config_dir, cfg, repo, tz)
        result = engine.run_cycle(as_of=as_of)

    print(f"ingest complete @ {result.as_of.isoformat()}")
    print(f"instruments     : {result.instruments_upserted}")
    print(f"candles fetched : {result.candles_fetched}  written: {result.candles_written}")
    print(f"quotes fetched  : {result.quotes_fetched}  written: {result.quotes_written}")
    print(f"datasets ok     : {result.datasets_validated}  empty skipped: {result.datasets_skipped_empty}")
    return 0


def _cmd_due(args: argparse.Namespace) -> int:
    """Show which dry-run triggers are due at as_of (M10.2 cadence)."""
    config_dir = _config_dir()
    cfg = load_config(config_dir)
    sched = load_scheduling_config(config_dir)
    tz = ZoneInfo(cfg.market.timezone)
    as_of = _parse_as_of(args.as_of, tz)

    last_premarket_date = None
    last_refresh_ts = None
    with _open_repo(cfg) as repo:
        pre = repo.latest_run(RunTrigger.PREMARKET.value)
        if pre is not None:
            last_premarket_date = pre.started_ts.astimezone(tz).date()
        ref = repo.latest_run(RunTrigger.REFRESH.value)
        if ref is not None:
            last_refresh_ts = ref.started_ts

    due = due_triggers(
        as_of,
        sessions=cfg.market.sessions,
        config=sched,
        base_interval_minutes=cfg.base.refresh_interval_minutes,
        last_premarket_date=last_premarket_date,
        last_refresh_ts=last_refresh_ts,
    )
    print(f"as_of           : {as_of.isoformat()}")
    if due:
        print(f"due             : {', '.join(t.value for t in due)}")
    else:
        print("due             : (none)")
    return 0


def _cmd_cycle(args: argparse.Namespace) -> int:
    """One scheduled dry-run cycle: ingest → run ledger (M10.2)."""
    config_dir = _config_dir()
    cfg = load_config(config_dir)
    tz = ZoneInfo(cfg.market.timezone)
    as_of = _parse_as_of(args.as_of, tz)
    trigger = RunTrigger(args.trigger.upper())

    with _open_repo(cfg) as repo:
        ingest_engine, _ = _build_ingest_engine(config_dir, cfg, repo, tz)
        orchestrator = DryRunCycleOrchestrator(
            ingest_engine,
            repo,
            strategy_profile=cfg.base.active_profile,
            config_snapshot_id="cfg-cli",
        )
        result = orchestrator.run_cycle(trigger, as_of=as_of)

    print(f"cycle complete  : {result.run.run_id}")
    print(f"trigger         : {result.run.trigger.value}")
    print(f"status          : {result.run.status.value}")
    print(f"duration_s      : {result.duration_seconds:.3f}")
    if result.ingestion is not None:
        print(
            f"ingest          : candles={result.ingestion.candles_written} "
            f"quotes={result.ingestion.quotes_written}"
        )
    print(f"pipeline mode   : {result.pipeline_detail.get('mode')}")
    return 0


def _cmd_brief(args: argparse.Namespace) -> int:
    """Assemble and dispatch the daily briefing (M10.3)."""
    config_dir = _config_dir()
    cfg = load_config(config_dir)
    notify_cfg = load_notifications_config(config_dir)
    tz = ZoneInfo(cfg.market.timezone)
    as_of = _parse_as_of(args.as_of, tz)

    with _open_repo(cfg) as repo:
        dispatcher = BriefingDispatcher(
            repo,
            notify_cfg,
            tzinfo=tz,
            repo_root=_repo_root(),
            decision_source=SqliteDecisionSummarySource(repo, tzinfo=tz),
        )
        result = dispatcher.dispatch(as_of=as_of, dry_run=bool(args.dry_run))

    print(f"briefing        : {result.briefing.briefing_id}")
    print(f"status          : {result.briefing.status.value}")
    print(f"runs            : {len(result.briefing.runs)}")
    print(f"decisions       : {len(result.briefing.decisions)}")
    if result.briefing.degradation_reasons:
        print(f"degraded        : {', '.join(result.briefing.degradation_reasons)}")
    for receipt in result.receipts:
        mark = "ok" if receipt.ok else "fail"
        print(f"notify[{mark}]     : {receipt.channel} — {receipt.detail}")
    return 0


def _cmd_diagnose(args: argparse.Namespace) -> int:
    """Playbook diagnostics — propose-only config tuning suggestions (M10.4)."""
    config_dir = _config_dir()
    cfg = load_config(config_dir)
    diag_cfg = load_diagnostics_config(config_dir)
    tz = ZoneInfo(cfg.market.timezone)
    as_of = _parse_as_of(args.as_of, tz)

    # --dry-run is accepted for CLI symmetry; diagnostics never apply config.
    _ = args.dry_run

    with _open_repo(cfg) as repo:
        service = PlaybookDiagnosticsService(
            repo,
            diag_cfg,
            tzinfo=tz,
            config_dir=config_dir,
            repo_root=_repo_root(),
        )
        report, json_path, text_path = service.run(as_of=as_of)

    print(f"diagnostics     : {report.report_id}")
    print(f"status          : {report.status.value}")
    print(f"findings        : {len(report.findings)}")
    print(
        f"proposals       : {sum(1 for p in report.proposals if not p.blocked)} actionable / "
        f"{sum(1 for p in report.proposals if p.blocked)} blocked"
    )
    if report.degradation_reasons:
        print(f"degraded        : {', '.join(report.degradation_reasons)}")
    print(f"wrote           : {json_path}")
    print(f"                : {text_path}")
    print("note            : proposals are NEVER auto-applied — human review required")
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

    p_ingest = sub.add_parser(
        "ingest",
        help="Run one live ingest cycle (M10.1): quotes/candles → validate → SQLite",
    )
    p_ingest.add_argument(
        "--as-of",
        help="ISO timestamp for freshness (injected; defaults to now in market timezone)",
    )
    p_ingest.set_defaults(func=_cmd_ingest)

    p_due = sub.add_parser(
        "due",
        help="Show due PREMARKET/REFRESH triggers at as_of (M10.2 cadence)",
    )
    p_due.add_argument("--as-of", help="ISO timestamp (defaults to now)")
    p_due.set_defaults(func=_cmd_due)

    p_cycle = sub.add_parser(
        "cycle",
        help="Run one scheduled dry-run cycle: ingest + SQLite run ledger (M10.2)",
    )
    p_cycle.add_argument(
        "--trigger",
        required=True,
        choices=["premarket", "refresh", "PREMARKET", "REFRESH"],
        help="Cycle trigger",
    )
    p_cycle.add_argument("--as-of", help="ISO timestamp (defaults to now)")
    p_cycle.set_defaults(func=_cmd_cycle)

    p_brief = sub.add_parser(
        "brief",
        help="Assemble and dispatch the daily briefing from the run ledger (M10.3)",
    )
    p_brief.add_argument("--as-of", help="ISO timestamp (defaults to now)")
    p_brief.add_argument(
        "--dry-run",
        action="store_true",
        help="Write FileNotifier artifacts only (no webhook/email)",
    )
    p_brief.set_defaults(func=_cmd_brief)

    p_diagnose = sub.add_parser(
        "diagnose",
        help="Playbook diagnostics: propose config tuning (never auto-apply) (M10.4)",
    )
    p_diagnose.add_argument("--as-of", help="ISO timestamp (defaults to now)")
    p_diagnose.add_argument(
        "--dry-run",
        action="store_true",
        help="Accepted for symmetry; diagnostics never mutate config",
    )
    p_diagnose.set_defaults(func=_cmd_diagnose)

    args = parser.parse_args(argv)
    load_dotenv()
    try:
        return int(args.func(args))
    except AthenaError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
