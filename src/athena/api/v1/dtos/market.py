"""Owner validation candidate list DTOs (Market Intelligence)."""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class OwnerCandidateDTO(BaseModel):
    model_config = ConfigDict(frozen=True)

    symbol: str
    added_ts: datetime
    notes: str = ""
    active: bool = True


class OwnerCandidateListDTO(BaseModel):
    model_config = ConfigDict(frozen=True)

    candidates: tuple[OwnerCandidateDTO, ...]
    count: int


class UpsertCandidateRequest(BaseModel):
    model_config = ConfigDict(frozen=True)

    symbol: str = Field(..., min_length=1, description="Trading symbol, e.g. INFY or NSE:INFY")
    notes: str = Field(default="", max_length=500)
    active: bool = True


class DeleteCandidateResultDTO(BaseModel):
    model_config = ConfigDict(frozen=True)

    symbol: str
    deleted: bool


class ValidateSymbolsRequest(BaseModel):
    model_config = ConfigDict(frozen=True)

    symbols: list[str] = Field(..., min_length=1, max_length=20)


class ValidateSymbolsResultDTO(BaseModel):
    model_config = ConfigDict(frozen=True)

    run_id: str
    status: str
    symbols: tuple[str, ...]
    eligible: int
    excluded: int
    decisions: int
    qualified: int
    detail: str = ""


class CandleDTO(BaseModel):
    """One provider-independent OHLCV bar for read-only charting."""

    model_config = ConfigDict(frozen=True)

    ts_open: datetime
    open: Decimal
    high: Decimal
    low: Decimal
    close: Decimal
    volume: int
    source: str
    adjusted: bool


class CandleSeriesDTO(BaseModel):
    """Chronological candle series plus explicit data-freshness state."""

    model_config = ConfigDict(frozen=True)

    instrument_id: str
    timeframe: str
    candles: tuple[CandleDTO, ...]
    count: int
    latest_ts: datetime | None
    freshness_status: Literal["FRESH", "STALE", "NO_DATA"]
    age_minutes: int | None
    freshness_threshold_minutes: int
