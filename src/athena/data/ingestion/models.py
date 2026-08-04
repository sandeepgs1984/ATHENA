"""Immutable results for one live ingest cycle (M10.1)."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime


@dataclass(frozen=True, slots=True)
class IngestionResult:
    """Outcome of a single ``run_ingest_cycle`` — counts and identity only."""

    as_of: datetime
    instruments_upserted: int
    candles_fetched: int
    candles_written: int
    quotes_fetched: int
    quotes_written: int
    datasets_validated: int
    datasets_skipped_empty: int
    snapshots_written: int = 0
    institutional_written: int = 0
    institutional_error: str | None = None
    # Owner-reported (2026-08-04): a single instrument's stale/invalid dataset
    # used to abort run_cycle entirely, discarding every other instrument's
    # already-fetched, already-valid data for that cycle too. quarantine_on_
    # failure=True (the default) now isolates and skips just the offending
    # dataset instead — this makes that visible rather than hidden, per
    # "every failure fails loudly": a cycle can report success while still
    # surfacing exactly what it had to skip and why.
    datasets_quarantined: int = 0
    quarantined_dataset_ids: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        if self.as_of.tzinfo is None:
            raise ValueError("IngestionResult.as_of must be timezone-aware")
