"""Portfolio business service (P8.3)."""

from __future__ import annotations

from typing import TYPE_CHECKING

from athena.api.exceptions import PortfolioUnavailableError
from athena.api.v1.dtos import PortfolioDTO, PortfolioSummaryDTO, PositionDTO

if TYPE_CHECKING:
    from athena.api.v1.providers import PortfolioProvider
    from athena.domain.decision import Portfolio


class PortfolioService:
    """Orchestrates portfolio retrieval and DTO mapping."""

    def __init__(self, provider: PortfolioProvider) -> None:
        self._provider = provider

    def get_portfolio(self) -> PortfolioDTO:
        """Retrieves current portfolio details or raises PortfolioUnavailableError."""
        p = self._provider.get_portfolio()
        if not p:
            raise PortfolioUnavailableError("Current portfolio is unavailable")
        return self._map_to_dto(p)

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
