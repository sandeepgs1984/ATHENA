"""Owner-curated "Saved Symbols" watch list DTOs (UX-9b)."""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class SavedSymbolDTO(BaseModel):
    model_config = ConfigDict(frozen=True)

    symbol: str
    added_ts: datetime
    notes: str = ""


class SavedSymbolListDTO(BaseModel):
    model_config = ConfigDict(frozen=True)

    symbols: tuple[SavedSymbolDTO, ...]
    count: int


class AddSavedSymbolRequest(BaseModel):
    model_config = ConfigDict(frozen=True)

    symbol: str = Field(..., min_length=1, description="Trading symbol, e.g. INFY or NSE:INFY")
    notes: str = Field(default="", max_length=500)


class RemoveSavedSymbolResultDTO(BaseModel):
    model_config = ConfigDict(frozen=True)

    symbol: str
    deleted: bool
