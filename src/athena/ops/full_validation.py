"""Owner-triggered full-universe validation job (ADR-007 / MI-5).

Starts a background thread that acquires ``CycleRunnerLock`` and runs the same
ingest → ``OwnerValidationPipeline`` path as ``athena cycle --trigger refresh``,
over every active candidate. Progress is process-local on ``ServeRuntime``;
the durable outcome remains the ``runs`` table.
"""

from __future__ import annotations

import logging
import os
import threading
from dataclasses import replace
from datetime import datetime, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

from athena.api.exceptions import APIResourceError
from athena.calendar.engine import CalendarEngine
from athena.config.loader import load_config, load_ingestion_config, load_validation_config
from athena.data.ingestion import LiveIngestionEngine, build_ingest_validator
from athena.data.providers import build_market_data_provider
from athena.data.store.repository import SqliteRepository
from athena.data.validation import QuarantineRegistry
from athena.domain.enums import RunTrigger
from athena.ops.owner_candidates import (
    SqliteCandidateStore,
    display_symbol,
    normalize_candidate_symbol,
)
from athena.ops.owner_validation import OwnerValidationPipeline
from athena.ops.serve_runtime import (
    CycleRunnerLock,
    FullValidationProgress,
    LastCycleSnapshot,
    ServeRuntime,
    default_cycle_lock_path,
    get_serve_runtime,
)
from athena.scheduling import DryRunCycleOrchestrator

logger = logging.getLogger(__name__)


class CycleBusyError(APIResourceError):
    """Another cycle runner (serve worker or launchd run-due) holds the lock."""


_JOB_THREAD: threading.Thread | None = None
_JOB_GUARD = threading.Lock()


def _now() -> datetime:
    return datetime.now(tz=timezone.utc)


def get_full_validation_progress() -> FullValidationProgress:
    runtime = get_serve_runtime()
    if runtime is None:
        return FullValidationProgress()
    return runtime.full_validation


def start_full_validation(
    *,
    repo_root: Path,
    config_dir: Path,
    db_path: Path,
    lock_path: Path | None = None,
) -> FullValidationProgress:
    """Kick off a single-flight full-universe validation in a daemon thread.

    Raises ``CycleBusyError`` when a job is already running or the advisory lock
    is held by ``run-due`` / the serve cycle worker.
    """
    runtime = get_serve_runtime()
    if runtime is None:
        raise CycleBusyError(
            "full validation requires athena serve (ServeRuntime is not attached)"
        )

    global _JOB_THREAD
    with _JOB_GUARD:
        current = runtime.full_validation
        if current.state == "running":
            raise CycleBusyError(
                "full-universe validation is already running "
                f"(started {current.started_at})"
            )
        if _JOB_THREAD is not None and _JOB_THREAD.is_alive():
            raise CycleBusyError(
                "full-universe validation worker is still shutting down"
            )

        resolved_lock = Path(lock_path) if lock_path else default_cycle_lock_path(repo_root)
        # Non-blocking probe: refuse immediately if launchd/serve worker holds the lock.
        probe = CycleRunnerLock(resolved_lock)
        if not probe.acquire():
            raise CycleBusyError(
                "cycle lock busy — another run-due or serve cycle worker is in progress"
            )
        probe.release()

        repo = SqliteRepository(db_path)
        repo.initialize()
        try:
            total = len(SqliteCandidateStore(repo).list_candidates(active_only=True))
        finally:
            repo.close()

        started = _now()
        runtime.set_full_validation(
            FullValidationProgress(
                state="running",
                stage="acquiring_lock",
                symbols_total=total,
                symbols_completed=0,
                started_at=started,
                finished_at=None,
                run_id=None,
                detail=None,
            )
        )

        thread = threading.Thread(
            target=_run_job,
            name="athena-full-validation",
            daemon=True,
            kwargs={
                "runtime": runtime,
                "repo_root": Path(repo_root),
                "config_dir": Path(config_dir),
                "db_path": Path(db_path),
                "lock_path": resolved_lock,
                "symbols_total": total,
            },
        )
        _JOB_THREAD = thread
        thread.start()
        return runtime.full_validation


def _set_progress(runtime: ServeRuntime, **updates: object) -> None:
    current = runtime.full_validation
    runtime.set_full_validation(replace(current, **updates))  # type: ignore[arg-type]


def _run_job(
    *,
    runtime: ServeRuntime,
    repo_root: Path,
    config_dir: Path,
    db_path: Path,
    lock_path: Path,
    symbols_total: int,
) -> None:
    lock = CycleRunnerLock(lock_path)
    if not lock.acquire():
        _set_progress(
            runtime,
            state="failed",
            stage="failed",
            finished_at=_now(),
            detail="cycle lock busy when the job thread started",
        )
        return

    repo: SqliteRepository | None = None
    try:
        # Full-universe: never inherit a smoke-test candidate cap.
        os.environ.pop("ATHENA_MAX_CANDIDATES", None)

        _set_progress(runtime, stage="seeding")
        repo = SqliteRepository(db_path)
        repo.initialize()
        cfg = load_config(config_dir)
        tz = ZoneInfo(cfg.market.timezone)
        as_of = datetime.now(tz)

        from athena.ops.candidate_seed import seed_owner_candidates
        from athena.ops.constituents import ConstituentFetchError

        try:
            seed_owner_candidates(
                repo, config_dir, as_of=as_of, repo_root=repo_root
            )
        except ConstituentFetchError as exc:
            logger.warning("candidate seed failed during full validation: %s", exc)

        _set_progress(runtime, stage="ingesting")
        ingest_engine = _build_scoped_ingest_engine(
            config_dir, cfg, repo, tz, repo_root=repo_root
        )
        pipeline = OwnerValidationPipeline(repo, config_dir)
        orchestrator = DryRunCycleOrchestrator(
            ingest_engine,
            repo,
            pipeline=pipeline,
            strategy_profile=cfg.base.active_profile,
            config_snapshot_id="cfg-full-validation",
        )

        _set_progress(runtime, stage="validating")
        result = orchestrator.run_cycle(RunTrigger.REFRESH, as_of=as_of)
        status = (
            result.run.status.value
            if hasattr(result.run.status, "value")
            else str(result.run.status)
        )
        ok = str(status).upper() in {"COMPLETED", "SUCCESS"}
        _set_progress(
            runtime,
            state="completed" if ok else "failed",
            stage="completed" if ok else "failed",
            symbols_completed=symbols_total if ok else 0,
            finished_at=_now(),
            run_id=result.run.run_id,
            detail=None if ok else f"run finished with status {status}",
        )
        runtime.record_cycle(
            LastCycleSnapshot(
                as_of=as_of,
                idle=False,
                due=("refresh",),
                status=str(status),
                run_id=result.run.run_id,
                trigger=RunTrigger.REFRESH.value,
                detail="owner-triggered full validation",
            )
        )
    except Exception as exc:
        logger.exception("full-universe validation failed")
        _set_progress(
            runtime,
            state="failed",
            stage="failed",
            finished_at=_now(),
            detail=str(exc),
        )
        runtime.record_error(f"full validation: {exc}")
    finally:
        if repo is not None:
            repo.close()
        lock.release()


def _build_scoped_ingest_engine(
    config_dir: Path,
    cfg,
    repo: SqliteRepository,
    tz: ZoneInfo,
    *,
    repo_root: Path,
):
    """Mirror CLI candidate-scoped ingest (resolve catalog, skip unknowns)."""
    ingest_cfg = load_ingestion_config(config_dir)
    store = SqliteCandidateStore(repo)
    trading_symbols = [
        normalize_candidate_symbol(c.symbol)
        for c in store.list_candidates(active_only=True)
    ]
    kite_symbols = (
        trading_symbols if ingest_cfg.provider == "kite" and trading_symbols else None
    )
    provider = build_market_data_provider(
        config_dir,
        base_dir=repo_root,
        provider_name=ingest_cfg.provider,
        kite_symbols=kite_symbols,
    )
    if trading_symbols:
        catalog = provider.instruments()
        by_symbol: dict[str, str] = {}
        for inst in catalog:
            by_symbol[inst.symbol.upper()] = inst.instrument_id
            by_symbol[display_symbol(inst.instrument_id)] = inst.instrument_id
        resolved = [by_symbol[s] for s in trading_symbols if s in by_symbol]
        if not resolved:
            from athena.errors import DataValidationError

            raise DataValidationError(
                "no owner candidates resolved against provider catalog"
            )
        ingest_cfg = ingest_cfg.model_copy(update={"instrument_ids": resolved})

    calendar = CalendarEngine.from_config_dir(config_dir, cfg.market)
    validation = load_validation_config(config_dir)
    validator = build_ingest_validator(calendar, validation, ingest_cfg, tz)
    institutional = None
    try:
        from athena.data.providers import build_institutional_flow_provider

        institutional = build_institutional_flow_provider(
            config_dir, base_dir=repo_root
        )
    except Exception:
        institutional = None
    return LiveIngestionEngine(
        provider,
        repo,
        validator,
        QuarantineRegistry(),
        ingest_cfg,
        validation,
        tzinfo=tz,
        institutional_provider=institutional,
    )
