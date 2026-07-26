"""Owner-curated "Saved Symbols" watch list — personal bookmarks only.

Source of truth: SQLite ``saved_symbols``. Symbols normalize to bare
trading symbols (``INFY``), same convention as ``owner_candidates``.

Deliberately distinct from two other, unrelated concepts:
  - ``athena.ops.owner_candidates``: the pipeline-input validation list
    (seeds ingest/scoring). Saving a symbol here does not add it to, or
    remove it from, that list.
  - ``athena.watchlist``: the fully automated M4.3 pipeline classifier
    (membership derived from completed decisions, no owner input at all).
This module has no pipeline consumers — it is a passive list for the
trader to keep an eye on, read only by the dashboard.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Protocol

from athena.data.store.repository import SqliteRepository


def normalize_saved_symbol(raw: str) -> str:
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


@dataclass(frozen=True, slots=True)
class SavedSymbol:
    symbol: str
    added_ts: datetime
    notes: str = ""


class SavedSymbolStore(Protocol):
    def list_saved_symbols(self) -> list[SavedSymbol]: ...

    def add_saved_symbol(
        self,
        *,
        symbol: str,
        notes: str = "",
        added_ts: datetime | None = None,
    ) -> SavedSymbol: ...

    def remove_saved_symbol(self, symbol: str) -> bool: ...


class SqliteSavedSymbolStore:
    """SavedSymbolStore backed by SqliteRepository (ATHENA_DB_PATH)."""

    def __init__(self, repo: SqliteRepository) -> None:
        self._repo = repo

    def list_saved_symbols(self) -> list[SavedSymbol]:
        rows = self._repo.list_saved_symbols()
        return [SavedSymbol(symbol=sym, added_ts=ts, notes=notes) for sym, ts, notes in rows]

    def add_saved_symbol(
        self,
        *,
        symbol: str,
        notes: str = "",
        added_ts: datetime | None = None,
    ) -> SavedSymbol:
        bare = normalize_saved_symbol(symbol)
        ts = added_ts or datetime.now(tz=timezone.utc)
        if ts.tzinfo is None:
            ts = ts.replace(tzinfo=timezone.utc)
        self._repo.add_saved_symbol(symbol=bare, added_ts=ts, notes=notes or "")
        return SavedSymbol(symbol=bare, added_ts=ts, notes=notes or "")

    def remove_saved_symbol(self, symbol: str) -> bool:
        bare = normalize_saved_symbol(symbol)
        return self._repo.remove_saved_symbol(bare)


class InMemorySavedSymbolStore:
    """Test / fallback store when SQLite is not wired."""

    def __init__(self) -> None:
        self._rows: dict[str, SavedSymbol] = {}

    def list_saved_symbols(self) -> list[SavedSymbol]:
        return sorted(self._rows.values(), key=lambda s: s.added_ts, reverse=True)

    def add_saved_symbol(
        self,
        *,
        symbol: str,
        notes: str = "",
        added_ts: datetime | None = None,
    ) -> SavedSymbol:
        bare = normalize_saved_symbol(symbol)
        ts = added_ts or datetime.now(tz=timezone.utc)
        if ts.tzinfo is None:
            ts = ts.replace(tzinfo=timezone.utc)
        row = SavedSymbol(symbol=bare, added_ts=ts, notes=notes or "")
        self._rows[bare] = row
        return row

    def remove_saved_symbol(self, symbol: str) -> bool:
        bare = normalize_saved_symbol(symbol)
        return self._rows.pop(bare, None) is not None

    def clear(self) -> None:
        self._rows.clear()
