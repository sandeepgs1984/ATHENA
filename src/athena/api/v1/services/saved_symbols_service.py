"""Owner-curated "Saved Symbols" watch list service (UX-9b)."""

from __future__ import annotations

from athena.api.exceptions import ResourceNotFoundError
from athena.api.v1.dtos.saved_symbols import (
    AddSavedSymbolRequest,
    RemoveSavedSymbolResultDTO,
    SavedSymbolDTO,
    SavedSymbolListDTO,
)
from athena.ops.saved_symbols import SavedSymbolStore, normalize_saved_symbol


class SavedSymbolNotFoundError(ResourceNotFoundError):
    pass


class SavedSymbolsService:
    def __init__(self, store: SavedSymbolStore) -> None:
        self._store = store

    def list_saved_symbols(self) -> SavedSymbolListDTO:
        rows = self._store.list_saved_symbols()
        dtos = tuple(
            SavedSymbolDTO(symbol=s.symbol, added_ts=s.added_ts, notes=s.notes)
            for s in rows
        )
        return SavedSymbolListDTO(symbols=dtos, count=len(dtos))

    def add_saved_symbol(self, body: AddSavedSymbolRequest) -> SavedSymbolDTO:
        row = self._store.add_saved_symbol(symbol=body.symbol, notes=body.notes)
        return SavedSymbolDTO(symbol=row.symbol, added_ts=row.added_ts, notes=row.notes)

    def remove_saved_symbol(self, symbol: str) -> RemoveSavedSymbolResultDTO:
        bare = normalize_saved_symbol(symbol)
        deleted = self._store.remove_saved_symbol(bare)
        if not deleted:
            raise SavedSymbolNotFoundError(f"Saved symbol '{bare}' not found")
        return RemoveSavedSymbolResultDTO(symbol=bare, deleted=True)
