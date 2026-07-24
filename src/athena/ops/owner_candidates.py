"""Owner validation candidate list — shared by dashboard API and CLI cycle.

Source of truth: SQLite ``owner_candidates``. Symbols normalize to bare
trading symbols (``INFY``); ingest/universe resolve to ``NSE:INFY``-style ids.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Protocol

from athena.data.store.repository import SqliteRepository

DEFAULT_EXCHANGE = "NSE"


def normalize_candidate_symbol(raw: str) -> str:
    """Normalize ``INFY`` / ``NSE:INFY`` / whitespace → bare uppercase symbol."""
    text = str(raw).strip().upper()
    if not text:
        raise ValueError("symbol must be non-empty")
    if ":" in text:
        _exchange, symbol = text.split(":", 1)
        text = symbol.strip().upper()
        if not text:
            raise ValueError("symbol must be non-empty after exchange prefix")
    return text


def to_instrument_id(symbol: str, *, exchange: str = DEFAULT_EXCHANGE) -> str:
    """Map bare candidate symbol to provider instrument id (``NSE:INFY``)."""
    bare = normalize_candidate_symbol(symbol)
    return f"{exchange.strip().upper()}:{bare}"


def display_symbol(instrument_or_symbol: str) -> str:
    """Strip exchange prefix for dashboard display."""
    text = str(instrument_or_symbol).strip().upper()
    if ":" in text:
        return text.split(":", 1)[1]
    return text


@dataclass(frozen=True, slots=True)
class OwnerCandidate:
    symbol: str
    added_ts: datetime
    notes: str = ""
    active: bool = True


class CandidateStore(Protocol):
    def list_candidates(self, *, active_only: bool = True) -> list[OwnerCandidate]: ...

    def upsert_candidate(
        self,
        *,
        symbol: str,
        notes: str = "",
        active: bool = True,
        added_ts: datetime | None = None,
    ) -> OwnerCandidate: ...

    def delete_candidate(self, symbol: str) -> bool: ...


class SqliteCandidateStore:
    """CandidateStore backed by SqliteRepository (ATHENA_DB_PATH)."""

    def __init__(self, repo: SqliteRepository) -> None:
        self._repo = repo

    def list_candidates(self, *, active_only: bool = True) -> list[OwnerCandidate]:
        rows = self._repo.list_owner_candidates(active_only=active_only)
        return [
            OwnerCandidate(symbol=sym, added_ts=ts, notes=notes, active=active)
            for sym, ts, notes, active in rows
        ]

    def upsert_candidate(
        self,
        *,
        symbol: str,
        notes: str = "",
        active: bool = True,
        added_ts: datetime | None = None,
    ) -> OwnerCandidate:
        bare = normalize_candidate_symbol(symbol)
        ts = added_ts or datetime.now(tz=timezone.utc)
        if ts.tzinfo is None:
            ts = ts.replace(tzinfo=timezone.utc)
        self._repo.upsert_owner_candidate(
            symbol=bare, added_ts=ts, notes=notes or "", active=active
        )
        return OwnerCandidate(symbol=bare, added_ts=ts, notes=notes or "", active=active)

    def delete_candidate(self, symbol: str) -> bool:
        bare = normalize_candidate_symbol(symbol)
        return self._repo.delete_owner_candidate(bare)


class InMemoryCandidateStore:
    """Test / fallback store when SQLite is not wired."""

    def __init__(self) -> None:
        self._rows: dict[str, OwnerCandidate] = {}

    def list_candidates(self, *, active_only: bool = True) -> list[OwnerCandidate]:
        items = list(self._rows.values())
        if active_only:
            items = [c for c in items if c.active]
        return sorted(items, key=lambda c: c.symbol)

    def upsert_candidate(
        self,
        *,
        symbol: str,
        notes: str = "",
        active: bool = True,
        added_ts: datetime | None = None,
    ) -> OwnerCandidate:
        bare = normalize_candidate_symbol(symbol)
        ts = added_ts or datetime.now(tz=timezone.utc)
        if ts.tzinfo is None:
            ts = ts.replace(tzinfo=timezone.utc)
        row = OwnerCandidate(symbol=bare, added_ts=ts, notes=notes or "", active=active)
        self._rows[bare] = row
        return row

    def delete_candidate(self, symbol: str) -> bool:
        bare = normalize_candidate_symbol(symbol)
        return self._rows.pop(bare, None) is not None

    def clear(self) -> None:
        self._rows.clear()


def active_instrument_ids(store: CandidateStore, *, exchange: str = DEFAULT_EXCHANGE) -> list[str]:
    """Instrument ids for ingest filter from active candidates."""
    return [to_instrument_id(c.symbol, exchange=exchange) for c in store.list_candidates(active_only=True)]


def active_trading_symbols(store: CandidateStore) -> list[str]:
    return [c.symbol for c in store.list_candidates(active_only=True)]
