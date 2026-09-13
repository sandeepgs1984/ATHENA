"""Symbol Intelligence API service (SI-P1)."""

from __future__ import annotations

from collections.abc import Callable
from datetime import datetime
from pathlib import Path

from athena.api.v1.dtos.symbol_intelligence import SiSearchResultDTO, SymbolIntelligenceBundleDTO
from athena.api.v1.services.decisions_service import DecisionsService
from athena.api.v1.services.my_portfolio_service import MyPortfolioService
from athena.data.store.repository import SqliteRepository
from athena.symbol_intelligence.composer import SymbolIntelligenceComposer


class SymbolIntelligenceService:
    """HTTP adapter over the SI composer (GET re-read; POST may hydrate D1)."""

    def __init__(
        self,
        repo: SqliteRepository | None,
        *,
        config_dir: Path,
        decisions_service: DecisionsService | None,
        my_portfolio_service: MyPortfolioService | None,
        now_fn: Callable[[], datetime] | None = None,
    ) -> None:
        self._composer = SymbolIntelligenceComposer(
            repo,
            config_dir=config_dir,
            decisions_service=decisions_service,
            my_portfolio_service=my_portfolio_service,
            now_fn=now_fn,
        )

    def search(self, query: str) -> SiSearchResultDTO:
        return self._composer.search(query)

    def compose(self, query: str, *, refresh_market: bool = False) -> SymbolIntelligenceBundleDTO:
        return self._composer.compose(query, refresh_market=refresh_market)
