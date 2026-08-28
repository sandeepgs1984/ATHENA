"""M5 settlement repair -- one-off correction for the live-ingestion M5
timestamp-drift / missing-early-session defect (Owner/Chief Architect
authorization, 2026-08-28, EM-5 M5 timestamp + REL_VOLUME_C investigation).

**What this fixes.** `db/athena.db`'s live M5 history (2026-07-28 onward --
the entire window ingestion has ever covered) was captured near real-time
via `LiveIngestionEngine` with `lookback_minutes=30` and `skip_existing=true`
(`config/ingestion.json`). Investigation proved: (1) Kite's historical API
returns perfectly grid-aligned timestamps for genuinely settled dates
(confirmed directly against EM-1r3's own raw capture, e.g. `NSE:M&MFIN`
2024-12-10, all 75 slots exact); (2) `KiteProvider` applies zero
transformation to `ts_open` anywhere in the ingestion path; (3) the live
`candles` table nonetheless holds off-grid, provisional-looking timestamps
for recent sessions, and some sessions are missing their early-morning
candles entirely. Since `add_candles` upserts on the *exact* `ts_open`, a
later-settled candle at a different timestamp never overwrites the earlier
provisional one -- it only ever accumulates alongside it. This module
re-fetches the affected window from Kite's historical endpoint (now that
those dates have aged past whatever settle lag produced the drift) and
atomically replaces each (instrument, session)'s M5 slice via
`SqliteRepository.replace_candles`, leaving one canonical settled sequence.

**What this does not do.** No labels/outcomes touched, no FINAL_TEST
access, no EM-2/EM-4 formula changes, no change to canonical
`add_candles`/live ingestion behavior (this is a standalone repair path,
`skip_existing` is bypassed only here, by construction -- `replace_candles`
has no such concept at all). Today's still-open/most-recent session is
never in scope for this backfill (see `resolve_settlement_repair_dates`) --
that is Track B's separate live-M5-semantics question, deliberately out of
scope here.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, date, datetime, timedelta
from datetime import time as time_of_day
from datetime import tzinfo as tzinfo_type

from athena.data.retrying_provider import RetryingMarketDataProvider
from athena.data.store.repository import SqliteRepository
from athena.domain.enums import Timeframe
from athena.domain.interfaces import MarketDataProvider
from athena.domain.market import Candle
from athena.errors import ProviderError, RepositoryError

#: A candle is "on grid" iff it lands exactly on a 5-minute boundary with
#: zero seconds/microseconds -- the same definition EM-1r3's
#: `SessionExclusionReason.OFF_GRID_TIMESTAMP` implicitly enforces via its
#: exact-expected-slot set.
_GRID_SECONDS = 0
_GRID_MICROSECONDS = 0
_GRID_MINUTE_STEP = 5

#: The earliest checkpoint EM-5 scores at -- used only as the "does this
#: session have any early-morning coverage at all" probe for the audit
#: manifest's missing-early-session counters, not as a hard cutoff.
_EARLY_SESSION_PROBE_TIME = time_of_day(9, 20)


def _is_on_grid(ts: datetime) -> bool:
    return ts.second == _GRID_SECONDS and ts.microsecond == _GRID_MICROSECONDS and ts.minute % _GRID_MINUTE_STEP == 0


@dataclass(frozen=True, slots=True)
class SessionRepairRecord:
    instrument_id: str
    session_date: date
    rows_before: int
    off_grid_before: int
    has_early_coverage_before: bool
    first_ts_before: datetime | None
    rows_fetched: int
    rows_deleted: int
    rows_inserted: int
    off_grid_after: int
    has_early_coverage_after: bool
    first_ts_after: datetime | None
    error: str | None

    def to_dict(self) -> dict:
        return {
            "instrument_id": self.instrument_id, "session_date": self.session_date.isoformat(),
            "rows_before": self.rows_before, "off_grid_before": self.off_grid_before,
            "has_early_coverage_before": self.has_early_coverage_before,
            "first_ts_before": self.first_ts_before.isoformat() if self.first_ts_before else None,
            "rows_fetched": self.rows_fetched, "rows_deleted": self.rows_deleted,
            "rows_inserted": self.rows_inserted, "off_grid_after": self.off_grid_after,
            "has_early_coverage_after": self.has_early_coverage_after,
            "first_ts_after": self.first_ts_after.isoformat() if self.first_ts_after else None,
            "error": self.error,
        }


@dataclass(frozen=True, slots=True)
class RepairManifest:
    requested_dates: tuple[date, ...]
    instrument_ids: tuple[str, ...]
    records: tuple[SessionRepairRecord, ...]
    request_count: int
    retries_performed: int
    permanent_failures: int
    retry_exhausted_failures: int
    started_at: datetime
    finished_at: datetime

    @property
    def rows_deleted_total(self) -> int:
        return sum(r.rows_deleted for r in self.records)

    @property
    def rows_inserted_total(self) -> int:
        return sum(r.rows_inserted for r in self.records)

    @property
    def off_grid_before_total(self) -> int:
        return sum(r.off_grid_before for r in self.records)

    @property
    def off_grid_after_total(self) -> int:
        return sum(r.off_grid_after for r in self.records)

    @property
    def missing_early_session_before_count(self) -> int:
        return sum(1 for r in self.records if not r.has_early_coverage_before)

    @property
    def missing_early_session_after_count(self) -> int:
        return sum(1 for r in self.records if not r.has_early_coverage_after)

    @property
    def failure_count(self) -> int:
        return sum(1 for r in self.records if r.error is not None)

    def to_dict(self) -> dict:
        return {
            "requested_dates": [d.isoformat() for d in self.requested_dates],
            "instrument_count": len(self.instrument_ids),
            "instrument_ids": list(self.instrument_ids),
            "session_records": len(self.records),
            "rows_deleted_total": self.rows_deleted_total,
            "rows_inserted_total": self.rows_inserted_total,
            "off_grid_before_total": self.off_grid_before_total,
            "off_grid_after_total": self.off_grid_after_total,
            "missing_early_session_before_count": self.missing_early_session_before_count,
            "missing_early_session_after_count": self.missing_early_session_after_count,
            "failure_count": self.failure_count,
            "request_count": self.request_count,
            "retries_performed": self.retries_performed,
            "permanent_failures": self.permanent_failures,
            "retry_exhausted_failures": self.retry_exhausted_failures,
            "started_at": self.started_at.isoformat(),
            "finished_at": self.finished_at.isoformat(),
            "records": [r.to_dict() for r in self.records],
        }


def resolve_settlement_repair_dates(*, earliest_available: date, today: date) -> tuple[date, ...]:
    """Every calendar date with live M5 history, up to but never including
    `today` (today's session is Track B's live-semantics question, out of
    scope for a settled-history backfill by definition -- it isn't settled
    yet). Calendar dates only; the caller filters to real trading days by
    checking each instrument's own fetched data, never a hardcoded holiday
    list here."""

    if earliest_available >= today:
        return ()
    return tuple(earliest_available + timedelta(days=i) for i in range((today - earliest_available).days))


def _session_stats(
    candles: list[Candle], session_date: date, tzinfo: tzinfo_type,
) -> tuple[int, int, bool, datetime | None]:
    day_candles = sorted((c for c in candles if c.ts_open.date() == session_date), key=lambda c: c.ts_open)
    if not day_candles:
        return 0, 0, False, None
    off_grid = sum(1 for c in day_candles if not _is_on_grid(c.ts_open))
    probe = datetime.combine(session_date, _EARLY_SESSION_PROBE_TIME, tzinfo=tzinfo)
    has_early = any(c.ts_open < probe for c in day_candles)
    return len(day_candles), off_grid, has_early, day_candles[0].ts_open


def repair_instrument(
    *,
    provider: MarketDataProvider,
    repo: SqliteRepository,
    instrument_id: str,
    dates: tuple[date, ...],
    tzinfo: tzinfo_type,
) -> tuple[SessionRepairRecord, ...]:
    """One real Kite historical fetch covering the whole `dates` span for
    `instrument_id` (never one request per session), then one
    `replace_candles` transaction per session date -- each session's old
    rows (however many, however drifted) replaced atomically with exactly
    what Kite returns now that the date has settled."""

    if not dates:
        return ()
    start = datetime.combine(min(dates), time_of_day(0, 0), tzinfo=tzinfo)
    end = datetime.combine(max(dates), time_of_day(23, 59, 59), tzinfo=tzinfo)

    before_by_date: dict[date, list[Candle]] = {}
    for d in dates:
        day_start = datetime.combine(d, time_of_day(0, 0), tzinfo=tzinfo)
        day_end = datetime.combine(d, time_of_day(23, 59, 59), tzinfo=tzinfo)
        before_by_date[d] = repo.get_candles(instrument_id, Timeframe.M5, day_start, day_end)

    try:
        fetched = provider.intraday_candles(instrument_id, Timeframe.M5, start, end)
        fetch_error: str | None = None
    except ProviderError as exc:
        fetched = []
        fetch_error = str(exc)

    fetched_by_date: dict[date, list[Candle]] = {}
    for c in fetched:
        fetched_by_date.setdefault(c.ts_open.date(), []).append(c)

    records: list[SessionRepairRecord] = []
    for d in dates:
        before = before_by_date[d]
        rows_before, off_grid_before, has_early_before, first_before = _session_stats(before, d, tzinfo)
        day_fetched = fetched_by_date.get(d, [])

        if fetch_error is not None:
            records.append(SessionRepairRecord(
                instrument_id=instrument_id, session_date=d, rows_before=rows_before,
                off_grid_before=off_grid_before, has_early_coverage_before=has_early_before,
                first_ts_before=first_before, rows_fetched=0, rows_deleted=0, rows_inserted=0,
                off_grid_after=off_grid_before, has_early_coverage_after=has_early_before,
                first_ts_after=first_before, error=fetch_error,
            ))
            continue

        day_start = datetime.combine(d, time_of_day(0, 0), tzinfo=tzinfo)
        day_end = datetime.combine(d, time_of_day(23, 59, 59), tzinfo=tzinfo)
        try:
            deleted, inserted = repo.replace_candles(instrument_id, Timeframe.M5, day_start, day_end, day_fetched)
            error = None
        except (RepositoryError, ValueError) as exc:
            deleted, inserted, error = 0, 0, str(exc)

        after = repo.get_candles(instrument_id, Timeframe.M5, day_start, day_end) if error is None else before
        _rows_after, off_grid_after, has_early_after, first_after = _session_stats(after, d, tzinfo)

        records.append(SessionRepairRecord(
            instrument_id=instrument_id, session_date=d, rows_before=rows_before,
            off_grid_before=off_grid_before, has_early_coverage_before=has_early_before,
            first_ts_before=first_before, rows_fetched=len(day_fetched), rows_deleted=deleted,
            rows_inserted=inserted, off_grid_after=off_grid_after, has_early_coverage_after=has_early_after,
            first_ts_after=first_after, error=error,
        ))

    return tuple(records)


def run_settlement_repair(
    *,
    provider: RetryingMarketDataProvider,
    repo: SqliteRepository,
    instrument_ids: tuple[str, ...],
    dates: tuple[date, ...],
    tzinfo: tzinfo_type,
) -> RepairManifest:
    """Repairs every (instrument, date) pair in scope. `provider` must be a
    `RetryingMarketDataProvider` wrapping a real `KiteProvider` -- its
    `stats` after this call populate the manifest's request/retry/failure
    counts. A real, live operational script (like
    `intraday_production_capture.py`) -- reads the real clock directly for
    its own start/finish record, not an injected `now` (there is nothing
    to replay: every call here makes a real Kite request)."""

    started = datetime.now(tz=UTC)
    records: list[SessionRepairRecord] = []
    for instrument_id in instrument_ids:
        records.extend(repair_instrument(
            provider=provider, repo=repo, instrument_id=instrument_id, dates=dates, tzinfo=tzinfo,
        ))
    return RepairManifest(
        requested_dates=dates, instrument_ids=instrument_ids, records=tuple(records),
        request_count=provider.stats.requests_attempted, retries_performed=provider.stats.retries_performed,
        permanent_failures=provider.stats.permanent_failures,
        retry_exhausted_failures=provider.stats.retry_exhausted_failures,
        started_at=started, finished_at=datetime.now(tz=UTC),
    )
