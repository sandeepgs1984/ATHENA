"""Dashboard resource DTOs (P9.2)."""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict


class DashboardSummaryDTO(BaseModel):
    """Composed DTO representing aggregated workstation console statistics."""

    model_config = ConfigDict(frozen=True)

    portfolio_value: Decimal
    cash_available: Decimal
    cash_reserved: Decimal
    active_positions: int
    closed_positions: int
    last_scan_date: datetime | None = None
    strategies_matched: int
    regime_class: str
    health_status: str
    backup_timestamp: datetime | None = None
