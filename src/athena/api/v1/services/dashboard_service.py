"""Dashboard operational service (P9.2)."""

from __future__ import annotations

import os
from datetime import datetime, time, timedelta, timezone
from decimal import ROUND_HALF_UP, Decimal
from pathlib import Path
from typing import TYPE_CHECKING
from zoneinfo import ZoneInfo

from athena.api.v1.dtos.analytics import EmptyFilterParams
from athena.api.v1.dtos.base import (
    PaginationParams,
    QuerySpecification,
    SortParams,
)
from athena.api.v1.dtos.dashboard import (
    CalendarDataDTO,
    CalendarEventDTO,
    CalendarHolidayDTO,
    MarketSessionStatusDTO,
    CalendarSpecialSessionDTO,
    DashboardSummaryDTO,
)
from athena.calendar.engine import CalendarEngine
from athena.api.v1.dtos.pipelines import PipelineRunFilterParams
from athena.config.loader import load_calendar_files, load_config
from athena.errors import CalendarError

if TYPE_CHECKING:
    from athena.api.v1.providers.base import (
        HealthProvider,
        PerformanceAnalyticsProvider,
        PipelineRunProvider,
        PortfolioProvider,
    )

_ZERO = Decimal("0.00")
_HUNDRED = Decimal("100")
_PCT_QUANTUM = Decimal("0.01")


class DashboardService:
    """Consolidates operational metrics for the single-page visual workstation."""

    def __init__(
        self,
        portfolio_provider: PortfolioProvider,
        pipeline_run_provider: PipelineRunProvider,
        health_provider: HealthProvider,
        analytics_provider: PerformanceAnalyticsProvider | None = None,
    ) -> None:
        self._portfolio_provider = portfolio_provider
        self._pipeline_run_provider = pipeline_run_provider
        self._health_provider = health_provider
        self._analytics_provider = analytics_provider

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

    def get_market_session_status(
        self,
        *,
        as_of: datetime | None = None,
    ) -> MarketSessionStatusDTO:
        """Return live/review-mode exchange status from the configured calendar.

        This is a read-only dashboard adapter over CalendarEngine + market
        session config. It does not infer holidays/weekends in JavaScript and
        does not read provider state or trading signals.
        """
        config_dir = self._resolve_config_dir()
        cfg = load_config(config_dir)
        tz = ZoneInfo(cfg.market.timezone)
        now = as_of or datetime.now(tz=timezone.utc)
        if now.tzinfo is None:
            now = now.replace(tzinfo=timezone.utc)
        local_now = now.astimezone(tz)
        calendar = CalendarEngine.from_config_dir(config_dir, cfg.market)
        ctx = calendar.context_for(local_now.date())

        session_open = self._session_dt(ctx.context_date, ctx.open_time, tz)
        session_close = self._session_dt(ctx.context_date, ctx.close_time, tz)
        is_open = bool(
            ctx.is_trading_session
            and session_open
            and session_close
            and session_open <= local_now < session_close
        )
        if is_open:
            phase = "OPEN"
        elif ctx.is_trading_session and session_open and local_now < session_open:
            phase = "PRE_OPEN"
        elif ctx.is_trading_session:
            phase = "CLOSED"
        else:
            phase = "NO_SESSION"

        next_open, next_close = self._next_market_session(calendar, local_now, tz)
        message = self._session_message(
            ctx.session_type.value,
            is_open=is_open,
            phase=phase,
            next_open=next_open,
            holiday_name=ctx.holiday_name,
        )

        return MarketSessionStatusDTO(
            exchange=ctx.exchange,
            timezone=ctx.timezone,
            as_of=local_now,
            context_date=ctx.context_date.isoformat(),
            session_type=ctx.session_type.value,
            is_trading_session=ctx.is_trading_session,
            is_market_open=is_open,
            phase=phase,
            session_open=session_open,
            session_close=session_close,
            next_open=next_open,
            next_close=next_close,
            holiday_name=ctx.holiday_name,
            message=message,
        )

    @staticmethod
    def _session_dt(day, clock: time | None, tz) -> datetime | None:
        if clock is None:
            return None
        return datetime.combine(day, clock, tzinfo=tz)

    def _next_market_session(
        self,
        calendar: CalendarEngine,
        local_now: datetime,
        tz,
    ) -> tuple[datetime | None, datetime | None]:
        for offset in range(0, 370):
            day = local_now.date() + timedelta(days=offset)
            try:
                ctx = calendar.context_for(day)
            except CalendarError:
                break
            open_dt = self._session_dt(ctx.context_date, ctx.open_time, tz)
            close_dt = self._session_dt(ctx.context_date, ctx.close_time, tz)
            if not ctx.is_trading_session or open_dt is None or close_dt is None:
                continue
            if close_dt <= local_now:
                continue
            if open_dt <= local_now < close_dt:
                return open_dt, close_dt
            if local_now < open_dt:
                return open_dt, close_dt
        return None, None

    @staticmethod
    def _session_message(
        session_type: str,
        *,
        is_open: bool,
        phase: str,
        next_open: datetime | None,
        holiday_name: str | None,
    ) -> str:
        if is_open:
            return "Market live"
        if phase == "PRE_OPEN" and next_open:
            return f"Market opens at {next_open.strftime('%d %b, %I:%M %p IST')}"
        if next_open:
            reason = holiday_name if session_type == "HOLIDAY" and holiday_name else "Market closed"
            return f"{reason} · next live {next_open.strftime('%d %b, %I:%M %p IST')}"
        return "Market closed · next live session unavailable"

    def _build_exposure_map(
        self,
        *,
        sector_exposure: dict[str, Decimal],
        cash_available: Decimal,
    ) -> dict[str, Decimal]:
        """Compose absolute ₹ exposure slices (sectors + cash) for the console donut."""
        exposure: dict[str, Decimal] = {
            str(sector): Decimal(str(amount))
            for sector, amount in sector_exposure.items()
            if Decimal(str(amount)) > _ZERO
        }
        if cash_available > _ZERO:
            exposure["Cash"] = cash_available
        return exposure

    def _compute_day_change_pct(self) -> Decimal | None:
        """Percent change between the two most recent NAV snapshots, if available."""
        if self._analytics_provider is None:
            return None
        try:
            spec = QuerySpecification(
                filters=EmptyFilterParams(),
                sort=SortParams(sort_by="as_of", sort_dir="desc"),
                pagination=PaginationParams(page=1, page_size=50),
            )
            result = self._analytics_provider.get_snapshots(spec)
            items = list(result.items)
        except Exception:
            return None

        if len(items) < 2:
            return None

        ordered = sorted(items, key=lambda snap: snap.as_of)
        previous = ordered[-2].portfolio_performance.portfolio_value
        latest = ordered[-1].portfolio_performance.portfolio_value
        if previous <= _ZERO:
            return None

        change = ((latest - previous) / previous) * _HUNDRED
        return change.quantize(_PCT_QUANTUM, rounding=ROUND_HALF_UP)

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
        portfolio_value = _ZERO
        cash_available = _ZERO
        cash_reserved = _ZERO
        active_positions = 0
        closed_positions = 0
        sector_exposure: dict[str, Decimal] = {}

        p = self._portfolio_provider.get_portfolio()
        if p:
            cash_available = p.cash
            sector_exposure = dict(p.exposure_by_sector or {})
            # Determine reserved cash and exposures from positions/exposures
            active_positions = len([pos for pos in p.positions if not pos.closed_ts])
            closed_positions = len([pos for pos in p.positions if pos.closed_ts])

            # Total portfolio valuation: cash + marked open positions (cost if no mark)
            portfolio_value = p.cash
            for pos in p.positions:
                if not pos.closed_ts:
                    mark = pos.avg_price
                    if pos.meta and pos.meta.get("current_price") is not None:
                        mark = Decimal(str(pos.meta["current_price"]))
                    portfolio_value += Decimal(pos.quantity) * mark

        exposure_by_sector = self._build_exposure_map(
            sector_exposure=sector_exposure,
            cash_available=cash_available,
        )
        day_change_pct = self._compute_day_change_pct()

        # 3. Fetch Pipeline runs details
        last_scan_date = None
        strategies_matched = 0
        regime_class = "UNKNOWN"

        try:
            # Query last run
            spec = QuerySpecification(
                filters=PipelineRunFilterParams(),
                sort=SortParams(sort_by="as_of", sort_dir="desc"),
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

                # Determine regime from context data when present
                data = getattr(ctx, "data", None) if ctx is not None else None
                if isinstance(data, dict):
                    regime = data.get("regime_assessment")
                    if isinstance(regime, dict) and regime.get("trend"):
                        regime_class = str(regime["trend"])
                    elif "regime" in data:
                        regime_class = str(data["regime"])
                elif ctx and hasattr(ctx, "regime"):
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
            exposure_by_sector=exposure_by_sector,
            day_change_pct=day_change_pct,
            last_scan_date=last_scan_date,
            strategies_matched=strategies_matched,
            regime_class=regime_class,
            health_status=health_status,
            backup_timestamp=datetime.now(tz=timezone.utc),  # Mock/Seed value for dashboard status
        )
