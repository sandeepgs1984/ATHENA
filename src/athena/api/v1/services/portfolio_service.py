"""Portfolio business service (P8.3)."""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import TYPE_CHECKING

from athena.api.exceptions import PortfolioUnavailableError, ResourceNotFoundError
from athena.api.v1.dtos import PortfolioDTO, PortfolioSummaryDTO, PositionDTO

if TYPE_CHECKING:
    from athena.api.v1.providers import PortfolioProvider
    from athena.domain.decision import Portfolio


class PositionNotFoundError(ResourceNotFoundError):
    """Owner position not found in the fill ledger."""


class PortfolioService:
    """Orchestrates portfolio retrieval, owner fill logging, and DTO mapping."""

    def __init__(self, provider: PortfolioProvider) -> None:
        self._provider = provider

    def get_portfolio(self) -> PortfolioDTO:
        """Retrieves current portfolio details or raises PortfolioUnavailableError."""
        p = self._provider.get_portfolio()
        if not p:
            raise PortfolioUnavailableError("Current portfolio is unavailable")
        return self._map_to_dto(p)

    def open_position(
        self,
        *,
        instrument_id: str,
        quantity: int,
        avg_price: Decimal,
        opened_ts: datetime | None = None,
        decision_ref: str | None = None,
        broker: str = "",
        notes: str = "",
        sector: str = "",
    ) -> PortfolioDTO:
        opener = getattr(self._provider, "open_position", None)
        if opener is None:
            raise PortfolioUnavailableError(
                "Portfolio provider does not support owner fill logging"
            )
        opener(
            instrument_id=instrument_id,
            quantity=quantity,
            avg_price=avg_price,
            opened_ts=opened_ts,
            decision_ref=decision_ref,
            broker=broker,
            notes=notes,
            sector=sector,
        )
        return self.get_portfolio()

    def close_position(
        self,
        position_id: str,
        *,
        exit_price: Decimal,
        closed_ts: datetime | None = None,
    ) -> PortfolioDTO:
        closer = getattr(self._provider, "close_position", None)
        if closer is None:
            raise PortfolioUnavailableError(
                "Portfolio provider does not support owner fill logging"
            )
        try:
            closer(position_id, exit_price=exit_price, closed_ts=closed_ts)
        except KeyError as exc:
            raise PositionNotFoundError(str(exc)) from exc
        return self.get_portfolio()

    def _map_to_dto(self, p: Portfolio) -> PortfolioDTO:
        positions_dtos = [
            PositionDTO(
                position_id=pos.position_id,
                instrument_id=pos.instrument_id,
                opened_ts=pos.opened_ts,
                quantity=pos.quantity,
                avg_price=pos.avg_price,
                closed_ts=pos.closed_ts,
                meta=dict(pos.meta) if pos.meta else {},
            )
            for pos in p.positions
        ]

        summary = PortfolioSummaryDTO(
            ts=p.ts,
            cash=p.cash,
            exposure_by_sector=dict(p.exposure_by_sector)
            if p.exposure_by_sector
            else {},
        )

        return PortfolioDTO(summary=summary, positions=positions_dtos)
