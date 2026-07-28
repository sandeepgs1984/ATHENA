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

    def __post_init__(self) -> None:
        if self.as_of.tzinfo is None:
            raise ValueError("IngestionResult.as_of must be timezone-aware")
