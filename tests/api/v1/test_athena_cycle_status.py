"""AUX-2 full ATHENA cycle status service and API contract tests."""

from __future__ import annotations

from datetime import datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

from fastapi.testclient import TestClient

from athena.api.dependencies import get_athena_cycle_status_service
from athena.api.v1.dtos.dashboard import AthenaCycleStatusDTO
from athena.api.v1.services.athena_cycle_status_service import AthenaCycleStatusService
from athena.api.v1.services.dashboard_service import DashboardService
from athena.domain.enums import RunStatus, RunTrigger
from athena.domain.run import RunRecord

IST = ZoneInfo("Asia/Kolkata")
REPO_ROOT = Path(__file__).resolve().parents[3]


class _RunHistory:
    def __init__(self, runs: list[RunRecord]) -> None:
        self._runs = sorted(runs, key=lambda run: run.started_ts, reverse=True)
        self.requested_trigger: str | None = None

    def list_runs(self, *, trigger: str | None = None, limit: int = 100) -> list[RunRecord]:
        self.requested_trigger = trigger
        matching = [run for run in self._runs if trigger is None or run.trigger.value == trigger]
        return matching[:limit]


def _run(
    run_id: str,
    *,
    at: datetime,
    status: RunStatus = RunStatus.COMPLETED,
    trigger: RunTrigger = RunTrigger.REFRESH,
) -> RunRecord:
    return RunRecord(
        run_id=run_id,
        cycle_id=f"cycle-{run_id}",
        trigger=trigger,
        started_ts=at - timedelta(minutes=1),
        finished_ts=at if status is not RunStatus.RUNNING else None,
        status=status,
        software_version="test",
        blueprint_version="ATHENA-002",
        strategy_profile="default",
        strategy_profile_version="1",
        indicator_versions={},
        config_snapshot_id="cfg-test",
    )


def _service(runs: list[RunRecord]) -> tuple[AthenaCycleStatusService, _RunHistory]:
    history = _RunHistory(runs)
    session_service = DashboardService(None, None, None)  # type: ignore[arg-type]
    return (
        AthenaCycleStatusService(
            history,
            session_service,
            config_dir=REPO_ROOT / "config",
        ),
        history,
    )


def test_open_session_current_uses_only_full_refresh_runs() -> None:
    as_of = datetime(2026, 7, 31, 10, 0, tzinfo=IST)
    service, history = _service(
        [
            _run("full", at=as_of - timedelta(minutes=5)),
            _run(
                "fast",
                at=as_of - timedelta(minutes=1),
                trigger=RunTrigger.FAST,
            ),
        ]
    )

    result = service.get_status(as_of=as_of)

    assert (result.status, result.tone) == ("CURRENT", "GOOD")
    assert result.last_successful_run_id == "full"
    assert result.latest_attempt_status == "COMPLETED"
    assert history.requested_trigger == RunTrigger.REFRESH.value


def test_open_session_without_current_success_is_overdue() -> None:
    as_of = datetime(2026, 7, 31, 11, 0, tzinfo=IST)
    service, _ = _service([_run("old", at=datetime(2026, 7, 30, 15, 15, tzinfo=IST))])

    result = service.get_status(as_of=as_of)

    assert (result.status, result.tone) == ("OVERDUE", "DANGER")
    assert result.expected_by is not None
    assert result.expected_by < as_of


def test_latest_failed_attempt_after_success_is_failed() -> None:
    as_of = datetime(2026, 7, 31, 10, 0, tzinfo=IST)
    service, _ = _service(
        [
            _run("success", at=as_of - timedelta(minutes=10)),
            _run(
                "failure",
                at=as_of - timedelta(minutes=2),
                status=RunStatus.FAILED,
            ),
        ]
    )

    result = service.get_status(as_of=as_of)

    assert (result.status, result.tone) == ("FAILED", "DANGER")
    assert result.last_successful_run_id == "success"
    assert result.latest_attempt_status == "FAILED"


def test_closed_session_does_not_raise_overdue_warning() -> None:
    as_of = datetime(2026, 7, 31, 18, 0, tzinfo=IST)
    service, _ = _service([_run("close-review", at=datetime(2026, 7, 31, 15, 15, tzinfo=IST))])

    result = service.get_status(as_of=as_of)

    assert (result.status, result.tone) == ("CLOSED", "NEUTRAL")
    assert result.headline == "Last cycle completed"
    assert result.market_session == "CLOSED"


def test_missing_history_is_unavailable_outside_market_hours() -> None:
    service, _ = _service([])

    result = service.get_status(as_of=datetime(2026, 8, 1, 12, 0, tzinfo=IST))

    assert (result.status, result.tone) == ("UNAVAILABLE", "NEUTRAL")
    assert result.last_successful_at is None
    assert result.latest_attempt_at is None


def test_api_returns_additive_timezone_aware_cycle_contract(
    client: TestClient,
) -> None:
    expected = AthenaCycleStatusDTO(
        status="CURRENT",
        tone="GOOD",
        headline="ATHENA cycle current",
        explanation="Inside the configured cadence.",
        last_successful_at=datetime(2026, 7, 31, 10, 0, tzinfo=IST),
        last_successful_run_id="run-current",
        latest_attempt_at=datetime(2026, 7, 31, 10, 0, tzinfo=IST),
        latest_attempt_status="COMPLETED",
        expected_by=datetime(2026, 7, 31, 10, 20, tzinfo=IST),
        market_session="OPEN",
        interval_minutes=15,
        grace_minutes=5,
    )

    class _Service:
        def get_status(self, *, as_of=None):
            return expected

    client.app.dependency_overrides[get_athena_cycle_status_service] = lambda: _Service()
    try:
        response = client.get("/api/v1/dashboard/cycle-status")
    finally:
        client.app.dependency_overrides.pop(get_athena_cycle_status_service, None)

    assert response.status_code == 200
    data = response.json()["data"]
    assert data["status"] == "CURRENT"
    assert data["last_successful_run_id"] == "run-current"
    assert data["last_successful_at"].endswith("+05:30")
    assert data["expected_by"].endswith("+05:30")
