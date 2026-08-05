"""Scheduled fast revalidation for decision-list symbols (Milestone B, 2026-08-04).

Reuses the exact scoped-ingest-then-score mechanics already proven by
symbol_validate.validate_symbols (the dashboard's "Revalidate" button) — a
scoped LiveIngestionEngine + OwnerValidationPipeline(symbols_filter=...) pair
run through the same DryRunCycleOrchestrator. The only differences: this is
triggered by cadence.is_fast_due on a timer instead of an owner click, and
scoped to whichever symbols currently have a persisted decision rather than
an owner-specified list.

Daily candles are intentionally excluded (include_daily=False) — the
15-minute REFRESH cadence already keeps them correct (LiveIngestionEngine's
today-exemption from skip_existing, fixed 2026-08-04). A 5-minute tier only
needs intraday/quote freshness to make indicators and decisions feel live;
re-fetching daily candles this often would cost ~0.334s per symbol (Kite's
historical rate limit) for no freshness benefit, and risks the fast tier's
own cycle running long enough to compete with the full-universe REFRESH
cadence for the same single-flight CycleRunnerLock.
"""

from __future__ import annotations

from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

from athena.calendar.engine import CalendarEngine
from athena.config.loader import load_config, load_ingestion_config, load_validation_config
from athena.data.ingestion import LiveIngestionEngine, build_ingest_validator
from athena.data.providers import build_market_data_provider
from athena.data.store.repository import SqliteRepository
from athena.data.validation import QuarantineRegistry
from athena.domain.enums import RunTrigger
from athena.ops.owner_candidates import normalize_candidate_symbol
from athena.ops.owner_validation import OwnerValidationPipeline
from athena.scheduling import DryRunCycleOrchestrator
from athena.scheduling.dry_run import DryRunCycleResult


def current_decision_list_instrument_ids(
    repo: SqliteRepository, *, max_symbols: int
) -> list[str]:
    """Every instrument with a persisted decision, newest-decided first,
    capped at ``max_symbols`` so a growing decision list can't make one
    fast cycle balloon past its own interval."""
    decisions = sorted(
        repo.list_latest_decisions_by_instrument(),
        key=lambda d: d.ts,
        reverse=True,
    )
    ids = [d.instrument_id for d in decisions if d.instrument_id]
    return ids[:max_symbols]


def run_fast_revalidation_cycle(
    repo: SqliteRepository,
    config_dir: Path,
    *,
    as_of: datetime,
    max_symbols: int,
    timeframes: list[str],
    repo_root: Path | None = None,
) -> DryRunCycleResult | None:
    """One FAST-trigger cycle scoped to the current decision list.

    Returns None (does nothing, no run persisted) when there are no
    decisions yet to keep fresh — a fresh install or a fully reset
    decisions table has nothing for this tier to do.
    """
    instrument_ids = current_decision_list_instrument_ids(repo, max_symbols=max_symbols)
    if not instrument_ids:
        return None

    root = Path(repo_root) if repo_root else Path.cwd()
    cfg = load_config(config_dir)
    tz = ZoneInfo(cfg.market.timezone)
    ingest_cfg = load_ingestion_config(config_dir)
    bare_symbols = [normalize_candidate_symbol(iid) for iid in instrument_ids]

    provider = build_market_data_provider(
        config_dir, base_dir=root, provider_name=ingest_cfg.provider, kite_symbols=bare_symbols,
    )
    ingest_cfg = ingest_cfg.model_copy(update={
        "instrument_ids": instrument_ids,
        "include_daily": False,
        "timeframes": list(timeframes),
        "quarantine_on_failure": True,
    })
    calendar = CalendarEngine.from_config_dir(config_dir, cfg.market)
    validation = load_validation_config(config_dir)
    validator = build_ingest_validator(calendar, validation, ingest_cfg, tz)
    # No institutional_provider: FII/DII flow is a once-a-day figure, not
    # something a 5-minute tier needs to re-check.
    engine = LiveIngestionEngine(
        provider, repo, validator, QuarantineRegistry(), ingest_cfg, validation, tzinfo=tz,
    )
    pipeline = OwnerValidationPipeline(repo, config_dir, symbols_filter=bare_symbols)
    orchestrator = DryRunCycleOrchestrator(
        engine, repo, pipeline=pipeline,
        strategy_profile=cfg.base.active_profile,
        config_snapshot_id="cfg-fast-revalidation",
    )
    return orchestrator.run_cycle(RunTrigger.FAST, as_of=as_of)
