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
    load_host_ops_config,
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
from athena.ops.kite_auth import run_interactive_kite_auth
from athena.ops.scheduled_run import HostDueRunner
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


def _build_ingest_engine(
    config_dir: Path,
    cfg,
    repo: SqliteRepository,
    tz: ZoneInfo,
    *,
    scope_to_candidates: bool = False,
):
    from athena.ops.owner_candidates import (
        SqliteCandidateStore,
        display_symbol,
        normalize_candidate_symbol,
    )

    ingest_cfg = load_ingestion_config(config_dir)
    kite_symbols = None
    trading_symbols: list[str] = []
    if scope_to_candidates:
        store = SqliteCandidateStore(repo)
        trading_symbols = [
            normalize_candidate_symbol(c.symbol)
            for c in store.list_candidates(active_only=True)
        ]
        max_raw = os.environ.get("ATHENA_MAX_CANDIDATES", "").strip()
        if max_raw:
            try:
                cap = int(max_raw)
            except ValueError as exc:
                raise ValueError(
                    f"ATHENA_MAX_CANDIDATES must be an integer, got {max_raw!r}"
                ) from exc
            if cap < 1:
                raise ValueError("ATHENA_MAX_CANDIDATES must be >= 1")
            trading_symbols = trading_symbols[:cap]
            print(
                f"candidate cap   : ATHENA_MAX_CANDIDATES={cap} "
                f"(using {len(trading_symbols)} symbols)",
                flush=True,
            )
        if trading_symbols and ingest_cfg.provider == "kite":
            kite_symbols = trading_symbols

    calendar = CalendarEngine.from_config_dir(config_dir, cfg.market)
    validation = load_validation_config(config_dir)
    provider = build_market_data_provider(
        config_dir,
        base_dir=_repo_root(),
        provider_name=ingest_cfg.provider,
        kite_symbols=kite_symbols,
    )

    if trading_symbols:
        catalog = provider.instruments()
        by_symbol: dict[str, str] = {}
        for inst in catalog:
            by_symbol[inst.symbol.upper()] = inst.instrument_id
            by_symbol[display_symbol(inst.instrument_id)] = inst.instrument_id
        resolved: list[str] = []
        missing: list[str] = []
        for sym in trading_symbols:
            iid = by_symbol.get(sym)
            if iid is None:
                missing.append(sym)
            else:
                resolved.append(iid)
        # Always include configured index / VIX instruments for regime + snapshot
        if ingest_cfg.provider == "kite":
            try:
                from athena.config.loader import load_kite_provider_config

                kite_cfg = load_kite_provider_config(config_dir)
                catalog_ids = {i.instrument_id for i in catalog}
                for extra in [
                    *kite_cfg.index_instruments,
                    kite_cfg.india_vix_instrument,
                ]:
                    if extra and extra in catalog_ids and extra not in resolved:
                        resolved.append(extra)
            except Exception:
                pass
        if missing:
            import sys

            preview = ", ".join(missing[:25])
            more = f" (+{len(missing) - 25} more)" if len(missing) > 25 else ""
            print(
                f"WARNING: {len(missing)} owner candidates not in provider catalog "
                f"(skipped for ingest): {preview}{more}",
                file=sys.stderr,
            )
        if not resolved:
            from athena.errors import DataValidationError

            raise DataValidationError(
                "no owner candidates resolved against provider catalog "
                f"(missing examples: {', '.join(missing[:10])})"
            )
        ingest_cfg = ingest_cfg.model_copy(update={"instrument_ids": resolved})

    validator = build_ingest_validator(calendar, validation, ingest_cfg, tz)
    return LiveIngestionEngine(
        provider, repo, validator, QuarantineRegistry(), ingest_cfg, validation, tzinfo=tz,
    ), ingest_cfg


def _owner_validation_pipeline(repo: SqliteRepository, config_dir: Path):
    from athena.ops.owner_validation import OwnerValidationPipeline

    return OwnerValidationPipeline(repo, config_dir)

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
    last_closing_date = None
    with _open_repo(cfg) as repo:
        pre = repo.latest_run(RunTrigger.PREMARKET.value)
        if pre is not None:
            last_premarket_date = pre.started_ts.astimezone(tz).date()
        ref = repo.latest_run(RunTrigger.REFRESH.value)
        if ref is not None:
            last_refresh_ts = ref.started_ts
        closing = repo.latest_run(RunTrigger.CLOSING.value)
        if closing is not None:
            last_closing_date = closing.started_ts.astimezone(tz).date()

    due = due_triggers(
        as_of,
        sessions=cfg.market.sessions,
        config=sched,
        base_interval_minutes=cfg.base.refresh_interval_minutes,
        last_premarket_date=last_premarket_date,
        last_refresh_ts=last_refresh_ts,
        last_closing_date=last_closing_date,
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
        from athena.ops.candidate_seed import seed_owner_candidates
        from athena.ops.constituents import ConstituentFetchError

        try:
            seed = seed_owner_candidates(
                repo, config_dir, as_of=as_of, repo_root=_repo_root()
            )
            print(
                f"candidate seed  : {seed.status} source={seed.source} "
                f"fetched={seed.fetched} added={seed.added} present={seed.already_present}"
            )
        except ConstituentFetchError as exc:
            print(f"WARNING: candidate seed failed (continuing with existing list): {exc}")

        ingest_engine, _ = _build_ingest_engine(
            config_dir, cfg, repo, tz, scope_to_candidates=True
        )
        orchestrator = DryRunCycleOrchestrator(
            ingest_engine,
            repo,
            pipeline=_owner_validation_pipeline(repo, config_dir),
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


def _execute_run_due(
    *,
    as_of_raw: str | None = None,
    send_brief: bool | None = None,
    alert: bool = True,
):
    """Shared due-ops path for CLI ``run-due`` and ``serve --with-cycles``."""
    config_dir = _config_dir()
    cfg = load_config(config_dir)
    sched = load_scheduling_config(config_dir)
    host_ops = load_host_ops_config(config_dir)
    notify_cfg = load_notifications_config(config_dir)
    tz = ZoneInfo(cfg.market.timezone)
    as_of = _parse_as_of(as_of_raw, tz)

    with _open_repo(cfg) as repo:
        from athena.ops.candidate_seed import seed_owner_candidates
        from athena.ops.constituents import ConstituentFetchError

        try:
            seed = seed_owner_candidates(
                repo, config_dir, as_of=as_of, repo_root=_repo_root()
            )
            print(
                f"candidate seed  : {seed.status} source={seed.source} "
                f"fetched={seed.fetched} added={seed.added} present={seed.already_present}"
            )
        except ConstituentFetchError as exc:
            print(f"WARNING: candidate seed failed (continuing with existing list): {exc}")

        ingest_engine, _ = _build_ingest_engine(
            config_dir, cfg, repo, tz, scope_to_candidates=True
        )
        runner = HostDueRunner(
            cfg=cfg,
            sched=sched,
            host_ops=host_ops,
            notify_cfg=notify_cfg,
            repo=repo,
            ingest_engine=ingest_engine,
            repo_root=_repo_root(),
            tzinfo=tz,
            strategy_profile=cfg.base.active_profile,
            pipeline=_owner_validation_pipeline(repo, config_dir),
        )
        return runner.run(
            as_of=as_of,
            send_brief=send_brief,
            alert=alert,
        )


def _cmd_run_due(args: argparse.Namespace) -> int:
    """R5/R6: run due PREMARKET/REFRESH/CLOSING cycles (then optional brief); alert on hard failure."""
    from athena.ops.serve_runtime import CycleRunnerLock, default_cycle_lock_path

    send_brief = None if args.brief is None else bool(args.brief)
    lock = CycleRunnerLock(default_cycle_lock_path(_repo_root()))
    if not lock.acquire():
        print(
            "ERROR: another cycle runner holds artifacts/locks/cycle-runner.lock "
            "(athena serve --with-cycles or another run-due).",
            file=sys.stderr,
        )
        return 75  # EX_TEMPFAIL
    try:
        result = _execute_run_due(
            as_of_raw=args.as_of,
            send_brief=send_brief,
            alert=not bool(args.no_alert),
        )
    finally:
        lock.release()

    print(f"run-due as_of   : {result.as_of.isoformat()}")
    if result.idle:
        print("due             : (none)")
        print("status          : idle")
        return 0
    print(f"due             : {', '.join(t.value for t in result.due)}")
    for cycle in result.cycles:
        print(
            f"cycle           : {cycle.run.trigger.value} "
            f"{cycle.run.status.value} ({cycle.run.run_id})"
        )
    if result.briefing_id:
        print(f"briefing        : {result.briefing_id}")
    if result.alerted:
        print("alert           : sent")
    return 0


def _last_cycle_from_result(result):
    from athena.ops.serve_runtime import LastCycleSnapshot

    if result.idle:
        return LastCycleSnapshot(
            as_of=result.as_of,
            idle=True,
            due=tuple(t.value for t in result.due),
            status="idle",
            detail="no triggers due",
        )
    last = result.cycles[-1] if result.cycles else None
    if last is None:
        return LastCycleSnapshot(
            as_of=result.as_of,
            idle=False,
            due=tuple(t.value for t in result.due),
            status="empty",
            detail="due triggers but no cycle results",
        )
    return LastCycleSnapshot(
        as_of=result.as_of,
        idle=False,
        due=tuple(t.value for t in result.due),
        status=last.run.status.value,
        run_id=last.run.run_id,
        trigger=last.run.trigger.value,
    )


def _cmd_serve(args: argparse.Namespace) -> int:
    """Start localhost API (+ optional in-process due-cycle worker)."""
    import webbrowser

    import uvicorn

    from athena.ops.serve_runtime import (
        CycleWorker,
        ServeRuntime,
        default_cycle_lock_path,
        set_serve_runtime,
    )

    # Ensure DB schema exists before accepting traffic.
    cfg = load_config(_config_dir())
    with _open_repo(cfg) as repo:
        _ = repo

    host = str(args.host)
    port = int(args.port)
    ssl_certfile = (
        Path(args.ssl_certfile).expanduser().resolve()
        if args.ssl_certfile
        else None
    )
    ssl_keyfile = (
        Path(args.ssl_keyfile).expanduser().resolve()
        if args.ssl_keyfile
        else None
    )
    if (ssl_certfile is None) != (ssl_keyfile is None):
        print(
            "ERROR: --ssl-certfile and --ssl-keyfile must be provided together",
            file=sys.stderr,
        )
        return 2
    for label, path in (
        ("--ssl-certfile", ssl_certfile),
        ("--ssl-keyfile", ssl_keyfile),
    ):
        if path is not None and not path.is_file():
            print(f"ERROR: {label} does not exist: {path}", file=sys.stderr)
            return 2

    runtime = ServeRuntime(
        cycles_enabled=bool(args.with_cycles),
        host=host,
        port=port,
    )
    set_serve_runtime(runtime)

    worker: CycleWorker | None = None
    if args.with_cycles:

        def _tick():
            # Interactive serve: no failure webhooks spam; launchd path still alerts.
            result = _execute_run_due(as_of_raw=None, send_brief=None, alert=False)
            return _last_cycle_from_result(result)

        worker = CycleWorker(
            runtime=runtime,
            interval_seconds=float(args.cycle_interval),
            tick_fn=_tick,
            lock_path=default_cycle_lock_path(_repo_root()),
        )
        worker.start()

    scheme = "https" if ssl_certfile is not None else "http"
    url = f"{scheme}://{host}:{port}/dashboard/"
    print(f"ATHENA serve    : {url}")
    if args.with_cycles:
        print(f"cycles worker   : on (interval={args.cycle_interval}s)")
    else:
        print("cycles worker   : off")
    print("Unlock in browser, then use the live console.")
    print("Stop with Ctrl+C. launchd ./athena-run-due remains the unattended scheduler.")

    if args.open:
        try:
            webbrowser.open(url)
        except Exception as exc:
            print(f"WARNING: could not open browser: {exc}", file=sys.stderr)

    try:
        uvicorn.run(
            "athena.api.app:create_app",
            factory=True,
            host=host,
            port=port,
            log_level="info",
            ssl_certfile=str(ssl_certfile) if ssl_certfile is not None else None,
            ssl_keyfile=str(ssl_keyfile) if ssl_keyfile is not None else None,
        )
    finally:
        if worker is not None:
            worker.stop()
        set_serve_runtime(None)
    return 0


def _cmd_seed_candidates(args: argparse.Namespace) -> int:
    """Fetch Nifty 500 (or configured source) and merge-unique into owner_candidates."""
    config_dir = _config_dir()
    cfg = load_config(config_dir)
    tz = ZoneInfo(cfg.market.timezone)
    as_of = _parse_as_of(args.as_of, tz)
    from athena.ops.candidate_seed import seed_owner_candidates
    from athena.ops.constituents import ConstituentFetchError

    with _open_repo(cfg) as repo:
        try:
            seed = seed_owner_candidates(
                repo, config_dir, as_of=as_of, repo_root=_repo_root()
            )
        except ConstituentFetchError as exc:
            print(f"ERROR: candidate seed failed: {exc}", file=sys.stderr)
            return 1
    print(f"candidate seed  : {seed.status}")
    print(f"source          : {seed.source}")
    print(f"as_of_date      : {seed.as_of_date.isoformat()}")
    print(f"fetched         : {seed.fetched}")
    print(f"added           : {seed.added}")
    print(f"already_present : {seed.already_present}")
    if seed.url_used:
        print(f"url             : {seed.url_used}")
    if seed.detail:
        print(f"detail          : {seed.detail}")
    return 0


def _cmd_validate_symbols(args: argparse.Namespace) -> int:
    """Ingest + eligibility + decisions for one or more owner-candidate symbols."""
    config_dir = _config_dir()
    cfg = load_config(config_dir)
    tz = ZoneInfo(cfg.market.timezone)
    as_of = _parse_as_of(args.as_of, tz)
    from athena.ops.owner_candidates import SqliteCandidateStore, normalize_candidate_symbol
    from athena.ops.symbol_validate import validate_symbols

    symbols = [s.strip() for s in args.symbols if s and str(s).strip()]
    if not symbols:
        print("ERROR: provide at least one symbol", file=sys.stderr)
        return 2

    with _open_repo(cfg) as repo:
        store = SqliteCandidateStore(repo)
        known = {c.symbol for c in store.list_candidates(active_only=False)}
        for sym in symbols:
            bare = normalize_candidate_symbol(sym)
            if bare not in known:
                store.upsert_candidate(symbol=bare, notes="cli validate", active=True)
                print(f"added candidate : {bare}")
                known.add(bare)
        try:
            result = validate_symbols(
                repo,
                config_dir,
                symbols=symbols,
                as_of=as_of,
                repo_root=_repo_root(),
            )
        except Exception as exc:
            print(f"ERROR: validate failed: {exc}", file=sys.stderr)
            return 1
    print(f"run_id          : {result.run_id}")
    print(f"status          : {result.status}")
    print(f"symbols         : {', '.join(result.symbols)}")
    print(f"eligible        : {result.eligible}")
    print(f"excluded        : {result.excluded}")
    print(f"decisions       : {result.decisions}")
    print(f"qualified       : {result.qualified}")
    if result.detail:
        print(f"detail          : {result.detail}")
    return 0 if result.status == "COMPLETED" else 1


def _cmd_set_owner_password(args: argparse.Namespace) -> int:
    """Hash an owner password for ATHENA_OWNER_PASSWORD_HASH (never stores plaintext)."""
    import getpass

    from athena.api.security.hashing import BcryptPasswordHasher

    password = args.password
    if not password:
        if not sys.stdin.isatty():
            print(
                "ERROR: no TTY for password prompt. Re-run with --password, or use:\n"
                "  PYTHONPATH=src python3 -m athena.cli set-owner-password --username owner --password '…'",
                file=sys.stderr,
            )
            return 1
        print("Enter owner password (input hidden):", file=sys.stderr)
        password = getpass.getpass("Owner password: ")
        confirm = getpass.getpass("Confirm password: ")
        if password != confirm:
            print("ERROR: passwords do not match", file=sys.stderr)
            return 1
    if not password:
        print("ERROR: empty password", file=sys.stderr)
        return 1

    hasher = BcryptPasswordHasher(rounds=12)
    digest = hasher.hash(password)
    print("# Add these lines to .env (never commit .env):")
    print(f"ATHENA_OWNER_USER={args.username}")
    # Single-quote the bcrypt hash so bash `source .env` does not expand $2b$…
    print(f"ATHENA_OWNER_PASSWORD_HASH='{digest}'")
    print(
        "# Then restart the API and hard-refresh the dashboard.",
        file=sys.stderr,
    )
    return 0


def _cmd_kite_auth(args: argparse.Namespace) -> int:
    """Interactive daily Kite login → write KITE_ACCESS_TOKEN to .env → verify."""
    load_dotenv()
    from athena.ops.kite_auth import force_inject_kite_env

    run_interactive_kite_auth(
        repo_root=_repo_root(),
        open_browser=not args.no_browser,
        listen_port=args.listen,
        verify=not args.skip_verify,
    )
    if args.ingest:
        # Force-inject from .env (setdefault load_dotenv would keep a stale token).
        force_inject_kite_env(_repo_root() / ".env")
        return _cmd_ingest(args)
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
        help="Show due PREMARKET/REFRESH/CLOSING triggers at as_of (M10.2 + R6 cadence)",
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
        choices=["premarket", "refresh", "closing", "PREMARKET", "REFRESH", "CLOSING"],
        help="Cycle trigger",
    )
    p_cycle.add_argument("--as-of", help="ISO timestamp (defaults to now)")
    p_cycle.set_defaults(func=_cmd_cycle)

    p_run_due = sub.add_parser(
        "run-due",
        help="R5/R6: run due PREMARKET/REFRESH/CLOSING cycles (+ optional brief); alert on hard failure",
    )
    p_run_due.add_argument("--as-of", help="ISO timestamp (defaults to now)")
    brief_group = p_run_due.add_mutually_exclusive_group()
    brief_group.add_argument(
        "--brief",
        dest="brief",
        action="store_true",
        default=None,
        help="Force briefing after cycles (overrides host_ops.brief_after_cycles)",
    )
    brief_group.add_argument(
        "--no-brief",
        dest="brief",
        action="store_false",
        help="Skip briefing even if host_ops.brief_after_cycles is true",
    )
    p_run_due.add_argument(
        "--no-alert",
        action="store_true",
        help="Do not dispatch failure alerts (still exits non-zero on failure)",
    )
    p_run_due.set_defaults(func=_cmd_run_due)

    p_serve = sub.add_parser(
        "serve",
        help="Start localhost API (+ optional due-cycle worker) — Live Entry workstation host",
    )
    p_serve.add_argument("--host", default="127.0.0.1", help="Bind host (default 127.0.0.1)")
    p_serve.add_argument("--port", type=int, default=8000, help="Bind port (default 8000)")
    p_serve.add_argument(
        "--with-cycles",
        action="store_true",
        help="Poll due PREMARKET/REFRESH/CLOSING in-process (complements launchd)",
    )
    p_serve.add_argument(
        "--cycle-interval",
        type=float,
        default=60.0,
        metavar="SECONDS",
        help="Seconds between due checks when --with-cycles (default 60, min 5)",
    )
    p_serve.add_argument(
        "--open",
        action="store_true",
        help="Open the dashboard URL in the default browser",
    )
    p_serve.add_argument(
        "--ssl-certfile",
        metavar="PATH",
        help="Optional localhost TLS certificate (use together with --ssl-keyfile)",
    )
    p_serve.add_argument(
        "--ssl-keyfile",
        metavar="PATH",
        help="Optional localhost TLS private key (use together with --ssl-certfile)",
    )
    p_serve.set_defaults(func=_cmd_serve)

    p_seed = sub.add_parser(
        "seed-candidates",
        help="Fetch Nifty 500 constituents and merge-unique into owner_candidates",
    )
    p_seed.add_argument("--as-of", help="ISO timestamp (defaults to now)")
    p_seed.set_defaults(func=_cmd_seed_candidates)

    p_validate = sub.add_parser(
        "validate-symbols",
        help="Ingest + score one or more owner-candidate symbols (dashboard Add & validate)",
    )
    p_validate.add_argument(
        "symbols",
        nargs="+",
        help="Symbols to validate (e.g. INFY RELIANCE)",
    )
    p_validate.add_argument("--as-of", help="ISO timestamp (defaults to now)")
    p_validate.set_defaults(func=_cmd_validate_symbols)

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

    p_owner = sub.add_parser(
        "set-owner-password",
        help="Generate ATHENA_OWNER_PASSWORD_HASH for dashboard unlock (prints .env lines)",
    )
    p_owner.add_argument(
        "--username",
        default="owner",
        help="Owner username (default: owner)",
    )
    p_owner.add_argument(
        "--password",
        help="Password (omit to prompt interactively; preferred)",
    )
    p_owner.set_defaults(func=_cmd_set_owner_password)

    p_kite = sub.add_parser(
        "kite-auth",
        help="Interactive Kite login: exchange request_token → write .env access token",
    )
    p_kite.add_argument(
        "--no-browser",
        action="store_true",
        help="Do not open the login URL automatically",
    )
    p_kite.add_argument(
        "--listen",
        type=int,
        metavar="PORT",
        help="Capture redirect on http://127.0.0.1:PORT/ (must match Kite Redirect URL)",
    )
    p_kite.add_argument(
        "--skip-verify",
        action="store_true",
        help="Skip post-write .env reinjection + Kite /user/profile check",
    )
    p_kite.add_argument(
        "--ingest",
        action="store_true",
        help="After writing the token, run one ingest cycle (requires ingestion.provider=kite)",
    )
    p_kite.add_argument(
        "--as-of",
        help="Passed to ingest when --ingest is set (ISO timestamp)",
    )
    p_kite.set_defaults(func=_cmd_kite_auth)

    args = parser.parse_args(argv)
    load_dotenv()
    try:
        return int(args.func(args))
    except AthenaError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
