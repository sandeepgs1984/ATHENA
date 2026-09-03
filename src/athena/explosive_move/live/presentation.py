"""EM-6A -- the read-only EMR presentation data contract.

Reads exclusively already-persisted `db/emr.db` records (`emr_scan_runs`,
`emr_candidates`) written by the frozen EM-5 live scanner
(`explosive_move/live/scanner.py::run_scan_cycle`, never invoked here).
Nothing in this module writes, migrates, or initializes any database, and
nothing here calls a provider/network endpoint.

Deliberately uses its own genuinely read-only SQLite connection (SQLite
URI `mode=ro` + `PRAGMA query_only=ON`) rather than `EmrRepository`'s
read-write connection -- the same pattern the ID-track's own shadow-audit
harness (`athena.data.id6e_replay_shadow_validation.run_shadow_audit`)
established, chosen here for the same reason: a presentation surface that
must be structurally incapable of mutating the database it reads, not
merely conventionally disciplined about it.

`top_candidates`/`top_touch_10_candidates` were described (never
implemented) in `docs/design/EM-5-LIVE-SCANNER-CONTRACT.md` Section 8 as
a future EM-6 seam -- this module is that implementation, built directly
against the real `emr_candidates`/`emr_scan_runs` schema (EM-5,
`EMR_SCHEMA_VERSION = 1`), not a wrapper around a function that did not
exist.

Coherence: every candidate this module returns is scoped to one explicit
`run_id`, and `run_id` always comes from this module's own
`latest_scan_snapshot()` (or a caller-supplied one) -- never from an
independent `MAX(created_ts)` over `emr_candidates` directly. This makes
mixing candidates from two different scans structurally unreachable, not
merely avoided by convention.

`EmrCandidateView.data_freshness` is the scanner's own persisted
per-candidate data-quality flag (`FRESH`/`STALE`, about the underlying
candle data at scan time) -- a different concept from
`describe_scan_freshness()`'s viewer-relative scan age, which is
deliberately a *pure* function taking an explicit `as_of` (no
`datetime.now()` anywhere in this module, mirroring the ID-track's own
injected-clock convention) so identical inputs always produce an
identical result. No FRESH/STALE *classification* of scan age is computed
here -- no owner-approved staleness threshold exists for EM-6, so only
the raw age fact is exposed; a threshold-based label is a display
decision left to EM-6B under its own future authorization.

Permanently `Experimental` -- `EXPERIMENTAL_LABEL` is the only label
constant this module defines, and no field, docstring, or default here
ever writes a term like `BUY`/`SELL`/`CONFIRMED TRADE`/`stop`/`target`/
`position size`/canonical `confidence`.
"""

from __future__ import annotations

import sqlite3
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

EXPERIMENTAL_LABEL = "Experimental research signal -- not a trade recommendation"

_SCAN_RUN_COLUMNS = (
    "run_id, session_date, checkpoint, frozen_model_version, status, "
    "started_ts, finished_ts, eligible_count, ineligible_count"
)
_CANDIDATE_COLUMNS = (
    "instrument_id, family, threshold_percent, rank, calibrated_probability, "
    "deterministic_score, probability_language, em4b_model_version, "
    "em4d_calibration_version, evidence_completeness_known, "
    "evidence_completeness_total, freshness, feasibility, feasibility_reason, "
    "state, state_reason, checkpoint_price, checkpoint_price_semantic"
)


@dataclass(frozen=True, slots=True)
class EmrScanSnapshotInfo:
    """One persisted `emr_scan_runs` row -- always `status == 'COMPLETE'`,
    since only a fully-persisted scan is ever returned by this module."""

    run_id: str
    session_date: str
    checkpoint: str
    frozen_model_version: str
    started_ts: str
    finished_ts: str | None
    eligible_count: int | None
    ineligible_count: int | None


@dataclass(frozen=True, slots=True)
class EmrCandidateView:
    """One persisted `emr_candidates` row for one (family, threshold)
    within one scan run. `rank` is `None` for an evaluated-but-unranked
    (ineligible or already-occurred) symbol -- never coerced to a
    sentinel number."""

    instrument_id: str
    family: str
    threshold_percent: int
    rank: int | None
    calibrated_probability: float | None
    deterministic_score: float | None
    probability_language: str
    em4b_model_version: str
    em4d_calibration_version: str
    evidence_completeness_known: int
    evidence_completeness_total: int
    data_freshness: str
    feasibility: str
    feasibility_reason: str | None
    state: str
    state_reason: str
    checkpoint_price: str | None
    checkpoint_price_semantic: str | None


@dataclass(frozen=True, slots=True)
class EmrCoverageView:
    """Descriptive-only summary of how many evaluated candidates for one
    (family, threshold) within one run were ranked vs. not, and why --
    never converts an `UNKNOWN`/missing reason into a numeric zero."""

    family: str
    threshold_percent: int
    evaluated_count: int
    ranked_count: int
    unranked_count: int
    unranked_reason_counts: tuple[tuple[str, int], ...]


@dataclass(frozen=True, slots=True)
class EmrScanFreshness:
    """Pure, `as_of`-explicit scan-age facts. Not a FRESH/STALE
    classification -- no owner-approved threshold exists for one."""

    age_seconds: float
    age_minutes: float
    scan_session_date: str
    scan_checkpoint: str
    as_of: str


@dataclass(frozen=True, slots=True)
class EmrExperimentalSnapshot:
    """The single coherent object a future EM-6B would render. `scan is
    None` and `touch_10 == ()` together are the well-defined empty state
    -- no scan exists yet -- never an exception, never a fabricated row."""

    label: str
    scan: EmrScanSnapshotInfo | None
    touch_10: tuple[EmrCandidateView, ...]


def _connect_read_only(db_path: str | Path) -> sqlite3.Connection | None:
    """Returns `None` (never raises) when the database file itself does
    not exist yet -- a fresh/never-scanned EMR store is a legitimate,
    expected empty state, not an error."""
    path = Path(db_path)
    if not path.exists():
        return None
    conn = sqlite3.connect(f"file:{path}?mode=ro", uri=True)
    conn.execute("PRAGMA query_only=ON")
    return conn


def _table_exists(conn: sqlite3.Connection, name: str) -> bool:
    row = conn.execute(
        "SELECT 1 FROM sqlite_master WHERE type='table' AND name=?", (name,)
    ).fetchone()
    return row is not None


def _row_to_scan(row: tuple) -> EmrScanSnapshotInfo:
    return EmrScanSnapshotInfo(
        run_id=row[0], session_date=row[1], checkpoint=row[2], frozen_model_version=row[3],
        started_ts=row[5], finished_ts=row[6], eligible_count=row[7], ineligible_count=row[8],
    )


def _row_to_candidate(row: tuple) -> EmrCandidateView:
    return EmrCandidateView(
        instrument_id=row[0], family=row[1], threshold_percent=row[2], rank=row[3],
        calibrated_probability=row[4], deterministic_score=row[5], probability_language=row[6],
        em4b_model_version=row[7], em4d_calibration_version=row[8],
        evidence_completeness_known=row[9], evidence_completeness_total=row[10],
        data_freshness=row[11], feasibility=row[12], feasibility_reason=row[13],
        state=row[14], state_reason=row[15], checkpoint_price=row[16], checkpoint_price_semantic=row[17],
    )


def latest_scan_snapshot(
    db_path: str | Path, *, session_date: str | None = None,
) -> EmrScanSnapshotInfo | None:
    """The most recently *started* `status == 'COMPLETE'` scan run,
    optionally scoped to one `session_date`. Never returns a `RUNNING`/
    `SKIPPED_SESSION_TYPE`/any other non-`COMPLETE` row -- those never
    finished persisting their full candidate set. `None` means no
    completed scan exists yet (empty state), not an error."""
    conn = _connect_read_only(db_path)
    if conn is None:
        return None
    try:
        if not _table_exists(conn, "emr_scan_runs"):
            return None
        if session_date is not None:
            row = conn.execute(
                f"SELECT {_SCAN_RUN_COLUMNS} FROM emr_scan_runs "
                "WHERE status='COMPLETE' AND session_date=? ORDER BY started_ts DESC LIMIT 1",
                (session_date,),
            ).fetchone()
        else:
            row = conn.execute(
                f"SELECT {_SCAN_RUN_COLUMNS} FROM emr_scan_runs "
                "WHERE status='COMPLETE' ORDER BY started_ts DESC LIMIT 1",
            ).fetchone()
        return _row_to_scan(row) if row is not None else None
    finally:
        conn.close()


def top_candidates(
    db_path: str | Path, *, run_id: str, family: str, threshold_percent: int, limit: int,
) -> tuple[EmrCandidateView, ...]:
    """Deterministic top-`limit` ranked candidates for one (family,
    threshold) within exactly one scan run -- `rank IS NOT NULL` only, in
    the scanner's own already-assigned rank order (EM-4C's frozen
    score-desc/instrument_id-asc tie-break, unmodified, never
    re-derived here). `limit` is the only caller-supplied cutoff; no
    probability/score threshold is applied."""
    if limit < 0:
        raise ValueError("top_candidates limit must be >= 0")
    conn = _connect_read_only(db_path)
    if conn is None:
        return ()
    try:
        if not _table_exists(conn, "emr_candidates"):
            return ()
        rows = conn.execute(
            f"SELECT {_CANDIDATE_COLUMNS} FROM emr_candidates "
            "WHERE run_id=? AND family=? AND threshold_percent=? AND rank IS NOT NULL "
            "ORDER BY rank ASC LIMIT ?",
            (run_id, family, threshold_percent, limit),
        ).fetchall()
        return tuple(_row_to_candidate(r) for r in rows)
    finally:
        conn.close()


def top_touch_10_candidates(
    db_path: str | Path, *, run_id: str, limit: int,
) -> tuple[EmrCandidateView, ...]:
    """The flagship view (contract Section 8): `EventFamily.TOUCH` at the
    10% threshold -- exactly that (family, threshold) pair, never
    reinterpreted as "10% probability", "top 10 stocks", or a 10-minute
    target."""
    return top_candidates(db_path, run_id=run_id, family="TOUCH", threshold_percent=10, limit=limit)


def coverage_summary(
    db_path: str | Path, *, run_id: str, family: str, threshold_percent: int,
) -> EmrCoverageView:
    """How many evaluated candidates for one (family, threshold) within
    one run were ranked vs. not, and why -- from the scanner's own
    persisted `feasibility_reason`/`state_reason`, never reconstructed."""
    conn = _connect_read_only(db_path)
    if conn is None:
        return EmrCoverageView(
            family=family, threshold_percent=threshold_percent,
            evaluated_count=0, ranked_count=0, unranked_count=0, unranked_reason_counts=(),
        )
    try:
        if not _table_exists(conn, "emr_candidates"):
            return EmrCoverageView(
                family=family, threshold_percent=threshold_percent,
                evaluated_count=0, ranked_count=0, unranked_count=0, unranked_reason_counts=(),
            )
        rows = conn.execute(
            "SELECT rank, feasibility_reason, state_reason FROM emr_candidates "
            "WHERE run_id=? AND family=? AND threshold_percent=?",
            (run_id, family, threshold_percent),
        ).fetchall()
    finally:
        conn.close()
    ranked = [r for r in rows if r[0] is not None]
    unranked = [r for r in rows if r[0] is None]
    reason_counts: dict[str, int] = {}
    for _rank, feasibility_reason, state_reason in unranked:
        reason = feasibility_reason or state_reason or "UNKNOWN"
        reason_counts[reason] = reason_counts.get(reason, 0) + 1
    return EmrCoverageView(
        family=family, threshold_percent=threshold_percent,
        evaluated_count=len(rows), ranked_count=len(ranked), unranked_count=len(unranked),
        unranked_reason_counts=tuple(sorted(reason_counts.items())),
    )


def describe_scan_freshness(scan: EmrScanSnapshotInfo, *, as_of: datetime) -> EmrScanFreshness:
    """Pure -- no `datetime.now()` anywhere in this module. `as_of` is
    always caller-supplied, so repeated calls with the same inputs always
    produce an identical result. Reports elapsed age as a fact; applies
    no FRESH/STALE label (no owner-approved threshold exists)."""
    reference_raw = scan.finished_ts or scan.started_ts
    reference = datetime.fromisoformat(reference_raw)
    delta_seconds = (as_of - reference).total_seconds()
    return EmrScanFreshness(
        age_seconds=delta_seconds, age_minutes=delta_seconds / 60.0,
        scan_session_date=scan.session_date, scan_checkpoint=scan.checkpoint, as_of=as_of.isoformat(),
    )


def build_experimental_snapshot(
    db_path: str | Path, *, session_date: str | None = None, touch_10_limit: int = 10,
) -> EmrExperimentalSnapshot:
    """The single coherent read-only object a future EM-6B would render.
    Empty state (`scan is None`, `touch_10 == ()`) when no completed scan
    exists -- never an exception, never a fabricated candidate row."""
    scan = latest_scan_snapshot(db_path, session_date=session_date)
    if scan is None:
        return EmrExperimentalSnapshot(label=EXPERIMENTAL_LABEL, scan=None, touch_10=())
    touch_10 = top_touch_10_candidates(db_path, run_id=scan.run_id, limit=touch_10_limit)
    return EmrExperimentalSnapshot(label=EXPERIMENTAL_LABEL, scan=scan, touch_10=touch_10)
