"""Server-authoritative advisory data freshness for the shared dashboard header."""

from __future__ import annotations

from collections.abc import Callable
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Literal
from zoneinfo import ZoneInfo

from athena.api.v1.dtos.dashboard import AdvisoryFreshnessDTO
from athena.api.v1.services.dashboard_service import DashboardService
from athena.calendar.engine import CalendarEngine
from athena.config.loader import load_config, load_validation_config
from athena.data.store.repository import SqliteRepository
from athena.errors import CalendarError

FreshnessStatus = Literal["CURRENT", "AGING", "STALE", "UNAVAILABLE"]
FreshnessTone = Literal["GOOD", "WARNING", "DANGER", "NEUTRAL"]


class AdvisoryFreshnessService:
    """Classify persisted market observations without provider-specific logic."""

    def __init__(
        self,
        repo: SqliteRepository | None,
        session_service: DashboardService,
        *,
        config_dir: Path,
        now_fn: Callable[[], datetime] | None = None,
    ) -> None:
        self._repo = repo
        self._session_service = session_service
        self._config_dir = Path(config_dir)
        self._now = now_fn or (lambda: datetime.now(tz=timezone.utc))

    def get_freshness(self, *, as_of: datetime | None = None) -> AdvisoryFreshnessDTO:
        now = as_of or self._now()
        if now.tzinfo is None:
            raise ValueError("advisory freshness reference time must be timezone-aware")

        market = load_config(self._config_dir).market
        freshness = load_validation_config(self._config_dir).freshness
        timezone_info = ZoneInfo(market.timezone)
        local_now = now.astimezone(timezone_info)
        calendar = CalendarEngine.from_config_dir(self._config_dir, market)
        session = self._session_service.get_market_session_status(as_of=local_now)
        snapshot = self._repo.get_latest_snapshot() if self._repo is not None else None
        observed_at = snapshot.ts.astimezone(timezone_info) if snapshot is not None else None
        limit_seconds = freshness.intraday_max_minutes_behind * 60

        if observed_at is None:
            return AdvisoryFreshnessDTO(
                status="UNAVAILABLE",
                tone="NEUTRAL",
                source="market_snapshot",
                headline="Freshness unavailable",
                explanation="No persisted market observation is available yet.",
                market_session=session.phase,
                next_live_at=session.next_open,
            )

        age_seconds = max(0, int((local_now - observed_at).total_seconds()))
        observed_time = observed_at.strftime("%I:%M %p IST")
        observed_label = observed_at.strftime("%d %b, %I:%M %p IST")
        status: FreshnessStatus
        tone: FreshnessTone

        if session.is_market_open:
            warning_seconds = freshness.intraday_warning_minutes_behind * 60
            if age_seconds < warning_seconds:
                status, tone = "CURRENT", "GOOD"
                headline = f"Current · as of {observed_time}"
                explanation = "The latest persisted market observation is inside the current-data window."
            elif age_seconds <= limit_seconds:
                status, tone = "AGING", "WARNING"
                headline = f"Aging · as of {observed_time}"
                explanation = "The observation is still usable but is approaching the configured freshness limit."
            else:
                status, tone = "STALE", "DANGER"
                headline = f"Stale · last observed {observed_time}"
                explanation = (
                    "The market is open and the latest persisted observation is "
                    "outside the configured freshness limit."
                )
        else:
            latest_close = self._latest_completed_session_close(calendar, local_now, timezone_info)
            close_is_covered = bool(
                latest_close
                and observed_at >= latest_close - timedelta(seconds=limit_seconds)
            )
            if close_is_covered:
                status, tone = "CURRENT", "NEUTRAL"
                headline = f"Closed review · data through {observed_label}"
                explanation = "The market is closed and the observation covers the latest completed session."
            else:
                status, tone = "STALE", "DANGER"
                headline = f"Stale · last observed {observed_label}"
                explanation = "The observation does not cover the latest completed market session."

        return AdvisoryFreshnessDTO(
            status=status,
            tone=tone,
            observed_at=observed_at,
            age_seconds=age_seconds,
            freshness_limit_seconds=limit_seconds,
            source="market_snapshot",
            headline=headline,
            explanation=explanation,
            market_session=session.phase,
            next_live_at=session.next_open,
        )

    @staticmethod
    def _latest_completed_session_close(
        calendar: CalendarEngine,
        local_now: datetime,
        timezone_info: ZoneInfo,
    ) -> datetime | None:
        for offset in range(0, 370):
            day = local_now.date() - timedelta(days=offset)
            try:
                context = calendar.context_for(day)
            except CalendarError:
                return None
            if not context.is_trading_session or context.close_time is None:
                continue
            close_at = datetime.combine(day, context.close_time, tzinfo=timezone_info)
            if close_at <= local_now:
                return close_at
        return None
