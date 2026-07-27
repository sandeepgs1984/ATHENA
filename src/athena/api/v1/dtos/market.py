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
    as_of: datetime | None = None
    as_of_mode: Literal["live", "session_close"] | None = None


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
    atr: Decimal | None = None
    moving_average: Decimal | None = None


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


class MarketIndexTickerDTO(BaseModel):
    """One index's level + day-over-day change, from already-persisted Kite
    data only (the latest market snapshot's LTP + the most recent prior
    daily candle close). Both fields are None — never a fabricated 0 or
    placeholder — when the underlying data isn't available yet (ADR-005)."""

    model_config = ConfigDict(frozen=True)

    label: str
    level: Decimal | None = None
    change_pct: Decimal | None = None


class MarketTickerDTO(BaseModel):
    """Header market ticker (DT-2, owner UX workstation refactor). Deliberately
    excludes market breadth (ADV/DEC) and an overall market-health score —
    neither exists as real data anywhere in ATHENA today (breadth is
    hardcoded 0/0 by the Kite provider; there is no aggregate health score,
    only 4 per-decision categorical dimension labels) — tracked as future
    scope rather than fabricated here."""

    model_config = ConfigDict(frozen=True)

    nifty: MarketIndexTickerDTO
    bank_nifty: MarketIndexTickerDTO
    india_vix: MarketIndexTickerDTO
    as_of: datetime | None = None
