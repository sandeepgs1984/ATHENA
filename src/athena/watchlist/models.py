"""Watchlist artifacts (M4.3).

Immutable records of which instruments deserve ongoing attention based on
ATHENA's *completed* decisions. These types record state and its history — no
analytical value is computed here, and no decision is reinterpreted.

Membership derives exclusively from completed decision outcomes surfaced by the
Daily Market Scanner (M4.2). History is append-only: past state is never
overwritten, only extended.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from datetime import datetime
from enum import Enum, unique
from types import MappingProxyType


@unique
class WatchlistChangeType(str, Enum):
    """The three ways an instrument's membership in a watchlist can change."""

    ADDED = "ADDED"       # entered the watchlist this scan
    RETAINED = "RETAINED"  # remained a member this scan
    REMOVED = "REMOVED"    # exited the watchlist this scan


@dataclass(frozen=True, slots=True)
class WatchlistEntry:
    """One instrument's membership in one named watchlist."""

    watchlist: str
    instrument_id: str
    decision_type: str
    decision_id: str
    explanation: str
    decision_ts: datetime
    scan_id: str
    entered_as_of: datetime
    last_seen_as_of: datetime

    def __post_init__(self) -> None:
        for name in ("watchlist", "instrument_id", "decision_type",
                     "decision_id", "explanation", "scan_id"):
            if not getattr(self, name):
                raise ValueError(f"WatchlistEntry.{name} is mandatory")
        if self.decision_ts.tzinfo is None:
            raise ValueError("WatchlistEntry.decision_ts must be timezone-aware")
        if self.entered_as_of.tzinfo is None or self.last_seen_as_of.tzinfo is None:
            raise ValueError("WatchlistEntry timestamps must be timezone-aware")
        if self.entered_as_of > self.last_seen_as_of:
            raise ValueError("WatchlistEntry.entered_as_of must be <= last_seen_as_of")


@dataclass(frozen=True, slots=True)
class WatchlistChange:
    """A single, explained membership change (append-only history unit)."""

    change_type: WatchlistChangeType
    watchlist: str
    instrument_id: str
    reason: str
    as_of: datetime
    scan_id: str
    decision_type: str | None = None

    def __post_init__(self) -> None:
        for name in ("watchlist", "instrument_id", "reason", "scan_id"):
            if not getattr(self, name):
                raise ValueError(f"WatchlistChange.{name} is mandatory")
        if self.as_of.tzinfo is None:
            raise ValueError("WatchlistChange.as_of must be timezone-aware")


@dataclass(frozen=True, slots=True)
class WatchlistSummary:
    """Membership counts per watchlist plus this transition's change tally."""

    counts: Mapping[str, int]
    added: int
    retained: int
    removed: int

    def __post_init__(self) -> None:
        object.__setattr__(self, "counts", MappingProxyType(dict(self.counts)))
        if min(self.added, self.retained, self.removed) < 0:
            raise ValueError("WatchlistSummary change counts must be >= 0")


@dataclass(frozen=True, slots=True)
class WatchlistSnapshot:
    """Immutable watchlist state derived from one DailyScanReport.

    ``entries`` is the complete membership across every watchlist at ``as_of``.
    ``changes`` records exactly what moved since the previous snapshot.
    ``observed_decisions`` maps each instrument scanned this cycle to its
    decision type — carried forward so the next cycle can compute trends.
    """

    snapshot_id: str
    as_of: datetime
    scan_id: str
    entries: tuple[WatchlistEntry, ...]
    changes: tuple[WatchlistChange, ...]
    observed_decisions: Mapping[str, str]
    summary: WatchlistSummary

    def __post_init__(self) -> None:
        if self.as_of.tzinfo is None:
            raise ValueError("WatchlistSnapshot.as_of must be timezone-aware")
        if not self.scan_id:
            raise ValueError("WatchlistSnapshot.scan_id is mandatory")
        object.__setattr__(self, "observed_decisions",
                           MappingProxyType(dict(self.observed_decisions)))

    def names(self) -> tuple[str, ...]:
        """Distinct watchlist names that currently have members, in order seen."""
        seen: list[str] = []
        for entry in self.entries:
            if entry.watchlist not in seen:
                seen.append(entry.watchlist)
        return tuple(seen)

    def watchlist(self, name: str) -> tuple[WatchlistEntry, ...]:
        """Entries currently in the named watchlist."""
        return tuple(e for e in self.entries if e.watchlist == name)

    def entry(self, name: str, instrument_id: str) -> WatchlistEntry | None:
        return next((e for e in self.entries
                     if e.watchlist == name and e.instrument_id == instrument_id), None)

    def to_dict(self) -> dict[str, object]:
        return {
            "snapshot_id": self.snapshot_id,
            "as_of": self.as_of.isoformat(),
            "scan_id": self.scan_id,
            "summary": {
                "counts": dict(self.summary.counts),
                "added": self.summary.added,
                "retained": self.summary.retained,
                "removed": self.summary.removed,
            },
            "entries": [
                {"watchlist": e.watchlist, "instrument_id": e.instrument_id,
                 "decision_type": e.decision_type, "decision_id": e.decision_id,
                 "explanation": e.explanation, "decision_ts": e.decision_ts.isoformat(),
                 "scan_id": e.scan_id, "entered_as_of": e.entered_as_of.isoformat(),
                 "last_seen_as_of": e.last_seen_as_of.isoformat()}
                for e in self.entries
            ],
            "changes": [
                {"change_type": c.change_type.value, "watchlist": c.watchlist,
                 "instrument_id": c.instrument_id, "reason": c.reason,
                 "as_of": c.as_of.isoformat(), "scan_id": c.scan_id,
                 "decision_type": c.decision_type}
                for c in self.changes
            ],
            "observed_decisions": dict(self.observed_decisions),
        }


@dataclass(frozen=True, slots=True)
class WatchlistHistory:
    """Append-only record of every membership change, oldest first.

    Immutable: :meth:`record` returns a new history extended with a snapshot's
    changes; existing history is never mutated or overwritten.
    """

    records: tuple[WatchlistChange, ...] = ()

    def record(self, snapshot: WatchlistSnapshot) -> WatchlistHistory:
        """Return a new history with this snapshot's changes appended."""
        return WatchlistHistory(records=self.records + snapshot.changes)

    def for_instrument(self, instrument_id: str) -> tuple[WatchlistChange, ...]:
        return tuple(c for c in self.records if c.instrument_id == instrument_id)

    def for_watchlist(self, name: str) -> tuple[WatchlistChange, ...]:
        return tuple(c for c in self.records if c.watchlist == name)

    def to_dict(self) -> dict[str, object]:
        return {
            "records": [
                {"change_type": c.change_type.value, "watchlist": c.watchlist,
                 "instrument_id": c.instrument_id, "reason": c.reason,
                 "as_of": c.as_of.isoformat(), "scan_id": c.scan_id,
                 "decision_type": c.decision_type}
                for c in self.records
            ]
        }
