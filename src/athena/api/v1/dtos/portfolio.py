"""Portfolio resource DTOs (P8.3)."""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field


class PositionDTO(BaseModel):
    """Composed DTO representing open or closed trading positions."""

    model_config = ConfigDict(frozen=True)

    position_id: str
    instrument_id: str
    opened_ts: datetime
    quantity: int
    avg_price: Decimal
    closed_ts: datetime | None = None
    meta: dict[str, object] = Field(default_factory=dict)


class PortfolioSummaryDTO(BaseModel):
    """Composed DTO containing aggregated metrics and exposures."""

    model_config = ConfigDict(frozen=True)

    ts: datetime
    cash: Decimal
    exposure_by_sector: dict[str, Decimal]


class PortfolioDTO(BaseModel):
    """Composed DTO representing current balance sheet and open positions."""

    model_config = ConfigDict(frozen=True)

    summary: PortfolioSummaryDTO
    positions: list[PositionDTO]


class OpenPositionRequest(BaseModel):
    """Owner-entered open fill (manual log after Kite/Groww order)."""

    model_config = ConfigDict(frozen=True)

    instrument_id: str = Field(min_length=1, description="Stock symbol, e.g. INFY")
    quantity: int = Field(gt=0)
    avg_price: Decimal = Field(gt=0, description="Entry fill price")
    opened_ts: datetime | None = None
    decision_ref: str | None = None
    broker: str = Field(default="", description="kite | groww | other")
    notes: str = ""
    sector: str = ""


class ClosePositionRequest(BaseModel):
    """Owner-entered exit fill for an open position."""

    model_config = ConfigDict(frozen=True)

    exit_price: Decimal = Field(gt=0)
    closed_ts: datetime | None = None


class ResetPositionsRequest(BaseModel):
    """Destructive wipe of owner fill ledger rows (CONFIRM-gated)."""

    model_config = ConfigDict(frozen=True)

    confirmation: str = Field(description="Must be the exact token CONFIRM")
    scope: str = Field(description="open = open fills only; all = open + closed")


class ResetPositionsResultDTO(BaseModel):
    """Result of an owner fill ledger reset."""

    model_config = ConfigDict(frozen=True)

    scope: str
    deleted_count: int
    backup_path: str | None = None
    portfolio: PortfolioDTO
