"""Dashboard operational service (P9.2)."""

from __future__ import annotations

import os
from datetime import datetime, timezone
from decimal import Decimal
from pathlib import Path
from typing import TYPE_CHECKING

from athena.api.v1.dtos.base import PaginationParams, QuerySpecification, SortParams
from athena.api.v1.dtos.dashboard import (
    CalendarDataDTO,
    CalendarEventDTO,
    CalendarHolidayDTO,
    CalendarSpecialSessionDTO,
    DashboardSummaryDTO,
)
from athena.api.v1.dtos.pipelines import PipelineRunFilterParams
from athena.config.loader import load_calendar_files

if TYPE_CHECKING:
    from athena.api.v1.providers.base import (
        HealthProvider,
        PipelineRunProvider,
        PortfolioProvider,
    )


class DashboardService:
    """Consolidates operational metrics for the single-page visual workstation."""

    def __init__(
        self,
        portfolio_provider: PortfolioProvider,
        pipeline_run_provider: PipelineRunProvider,
        health_provider: HealthProvider,
    ) -> None:
        self._portfolio_provider = portfolio_provider
        self._pipeline_run_provider = pipeline_run_provider
        self._health_provider = health_provider

    def _resolve_config_dir(self) -> Path:
        env_dir = os.environ.get("ATHENA_CONFIG_DIR")
        if env_dir:
            return Path(env_dir)
        current = Path(__file__).resolve().parent
        for _ in range(10):
            if (current / "config").is_dir() and (current / "src").is_dir():
                return current / "config"
            current = current.parent
        return Path("config")

    def get_calendar_data(self) -> CalendarDataDTO:
        """Loads and converts the configured exchange calendar files to DTOs."""
        config_dir = self._resolve_config_dir()
        holidays_file, expiries_file, events_file = load_calendar_files(config_dir)

        holidays = [
            CalendarHolidayDTO(date=h.date, name=h.name)
            for h in holidays_file.holidays
        ]

        special_sessions = [
            CalendarSpecialSessionDTO(
                date=s.date,
                type=s.type,
                name=s.name,
                timings_note=s.timings_note,
                open=s.open.isoformat() if s.open else None,
                close=s.close.isoformat() if s.close else None,
            )
            for s in holidays_file.special_sessions
        ]

        events = [
            CalendarEventDTO(date=e.date, kind=e.kind, name=e.name)
            for e in events_file.events
        ]

        return CalendarDataDTO(
            years=holidays_file.years,
            holidays=holidays,
            special_sessions=special_sessions,
            weekly_expiries=expiries_file.weekly,
            monthly_expiries=expiries_file.monthly,
            events=events,
        )

    def get_summary(self) -> DashboardSummaryDTO:
        """Retrieves and aggregates key workstation metrics."""
        # 1. Fetch Health Status
        health_status = "HEALTHY"
        try:
            health = self._health_provider.get_health()
            if health.status not in ("healthy", "UP"):
                health_status = "DEGRADED"
        except Exception:
            health_status = "DEGRADED"

        # 2. Fetch Portfolio stats
        portfolio_value = Decimal("0.00")
        cash_available = Decimal("0.00")
        cash_reserved = Decimal("0.00")
        active_positions = 0
        closed_positions = 0

        p = self._portfolio_provider.get_portfolio()
        if p:
            cash_available = p.cash
            # Determine reserved cash and exposures from positions/exposures
            active_positions = len([pos for pos in p.positions if not pos.closed_ts])
            closed_positions = len([pos for pos in p.positions if pos.closed_ts])

            # Simple simulation of total portfolio valuation
            portfolio_value = p.cash
            for pos in p.positions:
                if not pos.closed_ts:
                    portfolio_value += pos.quantity * pos.avg_price

        # 3. Fetch Pipeline runs details
        last_scan_date = None
        strategies_matched = 0
        regime_class = "NORMAL_BULLISH"

        try:
            # Query last run
            spec = QuerySpecification(
                filters=PipelineRunFilterParams(),
                sort=SortParams(field="as_of", direction="desc"),
                pagination=PaginationParams(page=1, page_size=1),
            )
            runs = self._pipeline_run_provider.get_runs(spec)
            if runs.items:
                latest_run = runs.items[0]
                last_scan_date = latest_run.as_of

                # Check for strategy matches in final context
                ctx = latest_run.final_context
                if ctx and hasattr(ctx, "strategy_matches"):
                    strategies_matched = len(ctx.strategy_matches)
                elif ctx and isinstance(ctx, dict) and "strategy_matches" in ctx:
                    strategies_matched = len(ctx["strategy_matches"])

                # Determine regime
                if ctx and hasattr(ctx, "regime"):
                    regime_class = str(ctx.regime)
                elif ctx and isinstance(ctx, dict) and "regime" in ctx:
                    regime_class = str(ctx["regime"])
        except Exception:
            pass

        return DashboardSummaryDTO(
            portfolio_value=portfolio_value,
            cash_available=cash_available,
            cash_reserved=cash_reserved,
            active_positions=active_positions,
            closed_positions=closed_positions,
            last_scan_date=last_scan_date,
            strategies_matched=strategies_matched,
            regime_class=regime_class,
            health_status=health_status,
            backup_timestamp=datetime.now(tz=timezone.utc),  # Mock/Seed value for dashboard status
        )
