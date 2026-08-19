"""Read-only health projection for ATHENA's persisted full-cycle history."""

from __future__ import annotations

from collections.abc import Callable
from datetime import datetime, timedelta, timezone
from pathlib import Path

from athena.api.v1.dtos.dashboard import AthenaCycleStatusDTO
from athena.api.v1.providers.base import CycleRunHistoryProvider
from athena.api.v1.services.dashboard_service import DashboardService
from athena.config.loader import load_config, load_scheduling_config
from athena.domain.enums import RunStatus, RunTrigger
from athena.domain.run import RunRecord
from athena.scheduling.cadence import refresh_interval_minutes


class AthenaCycleStatusService:
    """Classify full REFRESH cadence without mutating runtime state."""

    def __init__(
        self,
        history: CycleRunHistoryProvider | None,
        session_service: DashboardService,
        *,
        config_dir: Path,
        now_fn: Callable[[], datetime] | None = None,
    ) -> None:
        self._history = history
        self._session_service = session_service
        self._config_dir = Path(config_dir)
        self._now = now_fn or (lambda: datetime.now(tz=timezone.utc))

    def get_status(self, *, as_of: datetime | None = None) -> AthenaCycleStatusDTO:
        now = as_of or self._now()
        if now.tzinfo is None:
            raise ValueError("ATHENA cycle status reference time must be timezone-aware")

        base = load_config(self._config_dir).base
        scheduling = load_scheduling_config(self._config_dir)
        interval = refresh_interval_minutes(scheduling, base.refresh_interval_minutes)
        grace = scheduling.refresh.overdue_grace_minutes
        session = self._session_service.get_market_session_status(as_of=now)
        runs = self._history.list_runs(trigger=RunTrigger.REFRESH.value, limit=100) if self._history is not None else []
        latest = runs[0] if runs else None
        success = next((run for run in runs if run.status == RunStatus.COMPLETED), None)
        latest_at = self._event_time(latest)
        success_at = self._event_time(success)
        expected_by = self._expected_by(
            success_at=success_at,
            session_open=session.session_open,
            interval=interval,
            grace=grace,
        )

        common = {
            "last_successful_at": success_at,
            "last_successful_run_id": success.run_id if success else None,
            "latest_attempt_at": latest_at,
            "latest_attempt_status": latest.status.value if latest else None,
            "expected_by": expected_by,
            "market_session": session.phase,
            "interval_minutes": interval,
            "grace_minutes": grace,
        }

        latest_failed = bool(
            latest
            and latest.status in {RunStatus.FAILED, RunStatus.BLOCKED, RunStatus.DEGRADED}
            and (success_at is None or latest_at is None or latest_at > success_at)
        )
        if latest_failed:
            return AthenaCycleStatusDTO(
                status="FAILED",
                tone="DANGER",
                headline="ATHENA cycle failed",
                explanation=(
                    "The latest full validation cycle did not complete successfully. "
                    "Review its run evidence before relying on the board."
                ),
                **common,
            )

        if not session.is_market_open:
            if latest is None:
                return AthenaCycleStatusDTO(
                    status="UNAVAILABLE",
                    tone="NEUTRAL",
                    headline="Cycle history unavailable",
                    explanation="No persisted full validation cycle is available yet.",
                    **common,
                )
            return AthenaCycleStatusDTO(
                status="CLOSED",
                tone="NEUTRAL",
                headline="Last cycle completed",
                explanation=(
                    "The market is closed. ATHENA will evaluate the full-cycle "
                    "cadence again during the next live session."
                ),
                **common,
            )

        if expected_by is None or now > expected_by:
            return AthenaCycleStatusDTO(
                status="OVERDUE",
                tone="DANGER",
                headline="ATHENA cycle overdue",
                explanation=(
                    "A successful full validation cycle is later than the configured "
                    "cadence. Treat the board as potentially stale until it completes."
                ),
                **common,
            )

        running = latest is not None and latest.status == RunStatus.RUNNING
        return AthenaCycleStatusDTO(
            status="CURRENT",
            tone="GOOD",
            headline="ATHENA cycle running" if running else "ATHENA cycle current",
            explanation=(
                "A full validation cycle is currently running; the last successful cycle remains visible below."
                if running
                else "The latest successful full validation cycle is inside the configured cadence."
            ),
            **common,
        )

    @staticmethod
    def _event_time(run: RunRecord | None) -> datetime | None:
        if run is None:
            return None
        return run.finished_ts or run.started_ts

    @staticmethod
    def _expected_by(
        *,
        success_at: datetime | None,
        session_open: datetime | None,
        interval: int,
        grace: int,
    ) -> datetime | None:
        anchor = success_at
        if session_open is not None and (anchor is None or anchor < session_open):
            anchor = session_open
        if anchor is None:
            return None
        return anchor + timedelta(minutes=interval + grace)
