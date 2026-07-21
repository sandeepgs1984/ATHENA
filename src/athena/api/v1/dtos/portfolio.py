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
