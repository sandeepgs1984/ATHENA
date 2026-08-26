"""Reproducible, resumable EM-1r3 production intraday-capture command.

Owner-authorized 2026-08-22: a real, resumable, rate-limited capture across
the full survivor cohort and the frozen EM-1r2/EM-1r3 study window, using the
live Kite API as the sole authoritative source (no OHLCV synthesis). Mirrors
``em1r2_materialize.py``'s CLI shape. Re-running with the same
``--checkpoint``/``--capture-run-id`` resumes: already-completed instruments
are never re-fetched.

Owner-mandated 2026-08-24, after a real ~49-hour production sweep completed
against a defective provider boundary and produced ~0% admission: every
launch (fresh or resumed) first runs a small, real-provider canary
(``em1r3_production_canary.py``) and refuses to proceed to the expensive
full-cohort loop unless it passes. See CLAUDE.md's "expensive external-data
runs" rule and ``docs/ATHENA-EMR-HANDOFF.md`` for the incident this codifies.
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import date
from pathlib import Path

from athena.calendar.engine import CalendarEngine
from athena.config.loader import load_config
from athena.data.em1r3_production_canary import run_canary
from athena.data.intraday_production_capture import ProductionIntradayCaptureRunner
from athena.data.intraday_reconstruction_ingestion import (
    IntradayReconstructionIngestionService,
)
from athena.data.providers.kite_provider import KiteProvider
from athena.data.retrying_provider import RetryingMarketDataProvider
from athena.data.store.repository import SqliteRepository
from athena.domain.enums import SessionType
from athena.explosive_move.corporate_action_coverage import build_survivor_cohort
from athena.ops.kite_auth import force_inject_kite_env

_CAPTURABLE_SESSION_TYPES = (SessionType.NORMAL, SessionType.SPECIAL)

#: The known, newly-supported full-shaped Saturday session (2025-02-01,
#: NSE/CMTR/65729) is worth an explicit canary check every launch, on top
#: of canary_dates()'s own auto-selected oldest/mid/newest -- it exercises
#: a genuinely distinct code path (SPECIAL classification) that a purely
#: date-arithmetic selection would never happen to land on.
_KNOWN_SPECIAL_SESSION_CANARY_DATE = date(2025, 2, 1)

#: A small, real subset of the cohort for the canary -- enough to be a
#: genuine multi-instrument check, cheap enough to run before every launch.
_CANARY_INSTRUMENT_COUNT = 5


def _expected_symbol_session_count(
    calendar: CalendarEngine, study_start: date, study_end: date, symbol_count: int
) -> int:
    sessions = 0
    cursor = study_start
    while cursor <= study_end:
        if calendar.context_for(cursor).session_type in _CAPTURABLE_SESSION_TYPES:
            sessions += 1
        cursor = date.fromordinal(cursor.toordinal() + 1)
    return sessions * symbol_count


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Real, resumable EM-1r3 production intraday capture."
    )
    parser.add_argument("--config-dir", type=Path, default=Path("config"))
    parser.add_argument("--db", type=Path, default=Path("db/athena.db"))
    parser.add_argument("--env-file", type=Path, default=Path(".env"))
    parser.add_argument("--evidence-root", type=Path, required=True)
    parser.add_argument("--checkpoint", type=Path, required=True)
    parser.add_argument("--universe", default="athena_core")
    parser.add_argument("--cohort-resolution-date", type=date.fromisoformat, required=True)
    parser.add_argument("--study-start", type=date.fromisoformat, required=True)
    parser.add_argument("--study-end", type=date.fromisoformat, required=True)
    parser.add_argument("--capture-run-id", required=True)
    parser.add_argument("--batch-size", type=int, default=5)
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Resolve cohort + calendar and report counts; issue zero Kite requests.",
    )
    parser.add_argument(
        "--skip-canary",
        action="store_true",
        help=(
            "Skip the mandatory pre-flight canary gate. Only for local testing against "
            "a fake/scripted provider -- never for a real Kite launch."
        ),
    )
    args = parser.parse_args()

    config = load_config(args.config_dir)
    calendar = CalendarEngine.from_config_dir(args.config_dir, config.market)

    repository = SqliteRepository(args.db)
    try:
        instruments = tuple(repository.list_instruments())
        instrument_ids = tuple(repository.list_resolved_universe(args.universe))
    finally:
        repository.close()

    known_ids = {instrument.instrument_id for instrument in instruments}
    unresolved = sorted(set(instrument_ids) - known_ids)
    if unresolved:
        raise ValueError(
            f"resolved universe '{args.universe}' contains {len(unresolved)} unknown instrument ids"
        )

    cohort = build_survivor_cohort(
        universe_name=args.universe,
        resolution_date=args.cohort_resolution_date,
        instrument_ids=instrument_ids,
        group_effective_dates=((args.universe, args.cohort_resolution_date),),
    )

    expected_session_count = _expected_symbol_session_count(
        calendar, args.study_start, args.study_end, len(cohort.instrument_ids)
    )

    if args.dry_run:
        print(
            json.dumps(
                {
                    "cohort_id": cohort.cohort_id,
                    "cohort_size": len(cohort.instrument_ids),
                    "study_start": args.study_start.isoformat(),
                    "study_end": args.study_end.isoformat(),
                    "expected_symbol_sessions": expected_session_count,
                },
                indent=2,
                sort_keys=True,
            )
        )
        return

    force_inject_kite_env(args.env_file)

    symbols = sorted({instrument_id.split(":", 1)[1] for instrument_id in cohort.instrument_ids})
    provider = KiteProvider.from_config_dir(
        args.config_dir, symbols=symbols, strict_symbol_filter=False
    )
    wrapper = RetryingMarketDataProvider(inner=provider)

    service = IntradayReconstructionIngestionService(
        calendar=calendar,
        evidence_root=args.evidence_root,
        timezone_name=config.market.timezone,
        provider=wrapper,
    )

    if not args.skip_canary:
        canary_service = IntradayReconstructionIngestionService(
            calendar=calendar,
            evidence_root=args.evidence_root.parent / "canary",
            timezone_name=config.market.timezone,
            provider=wrapper,
        )
        special_date = _KNOWN_SPECIAL_SESSION_CANARY_DATE
        extra_dates = (
            {special_date: False}
            if args.study_start <= special_date <= args.study_end
            else None
        )
        canary_result = run_canary(
            service=canary_service,
            calendar=calendar,
            instrument_ids=tuple(cohort.instrument_ids[:_CANARY_INSTRUMENT_COUNT]),
            study_start=args.study_start,
            study_end=args.study_end,
            extra_dates=extra_dates,
        )
        print("=== pre-flight canary ===", flush=True)
        print(json.dumps(canary_result.to_dict(), indent=2, sort_keys=True), flush=True)
        if not canary_result.passed:
            print(
                f"CANARY FAILED: historical admission rate "
                f"{canary_result.historical_admission_rate:.1%} is below the required "
                f"{canary_result.threshold:.0%} on genuinely-complete dates. Refusing to "
                "launch the full sweep -- this is exactly the failure mode that produced "
                "~0% admission on 2026-08-22. Diagnose the provider before retrying.",
                file=sys.stderr,
            )
            sys.exit(1)
        print("=== canary passed, proceeding to full sweep ===", flush=True)

    runner = ProductionIntradayCaptureRunner(
        service=service,
        provider_stats=wrapper,
        checkpoint_path=args.checkpoint,
        evidence_root=args.evidence_root,
        batch_size=args.batch_size,
    )

    total_symbols = len(cohort.instrument_ids)

    def on_batch_complete(batch_ids: tuple[str, ...], checkpoint) -> None:
        done = len(checkpoint.completed_instrument_ids)
        print(
            f"[{done}/{total_symbols}] batch complete: {list(batch_ids)} "
            f"(kite requests: {wrapper.stats.requests_attempted}, "
            f"retries: {wrapper.stats.retries_performed}, "
            f"permanent failures: {wrapper.stats.permanent_failures}, "
            f"retry-exhausted: {wrapper.stats.retry_exhausted_failures})",
            flush=True,
        )

    summary = runner.run(
        capture_run_id=args.capture_run_id,
        cohort=cohort,
        study_start=args.study_start,
        study_end=args.study_end,
        expected_session_count=expected_session_count,
        on_batch_complete=on_batch_complete,
    )

    print(json.dumps(summary.to_dict(), indent=2, sort_keys=True, default=str))


if __name__ == "__main__":
    main()
