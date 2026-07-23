"""Integration tests for P9.5 Strategies & Backtests APIs."""

from __future__ import annotations

from datetime import datetime, timezone
import pytest
from fastapi.testclient import TestClient

from athena.api.dependencies import get_backtest_run_provider
from athena.api.security.models import Permission, Role
from athena.backtest.models import BacktestRun, BacktestSession, BacktestStep, BacktestSummary, StrategyPerformance
from athena.runtime.models import ExecutionStatus
from tests.api.v1.test_core_apis import get_auth_headers, get_api_key_headers


@pytest.fixture(autouse=True)
def clean_backtest_provider() -> None:
    """Reset backtest runs provider before each test."""
    p = get_backtest_run_provider()
    p.runs.clear()  # type: ignore[attr-defined]


class TestStrategiesAPI:
    def test_list_profiles_requires_auth(self, client: TestClient) -> None:
        response = client.get("/api/v1/strategies/profiles")
        assert response.status_code == 401

    def test_list_profiles_success(self, client: TestClient) -> None:
        headers = get_auth_headers(client, Role.READONLY)
        response = client.get("/api/v1/strategies/profiles", headers=headers)
        assert response.status_code == 200
        
        data = response.json()
        assert data["status"] == "success"
        profiles = data["data"]
        assert len(profiles) > 0
        
        # Verify first profile fields
        p = profiles[0]
        assert "name" in p
        assert "enabled" in p
        assert "decisions" in p
        assert "description" in p


class TestBacktestsAPI:
    def test_list_runs_requires_auth(self, client: TestClient) -> None:
        response = client.get("/api/v1/backtests/runs")
        assert response.status_code == 401

    def test_list_runs_success(self, client: TestClient) -> None:
        headers = get_auth_headers(client, Role.READONLY)
        p = get_backtest_run_provider()
        
        now = datetime.now(tz=timezone.utc)
        perf = StrategyPerformance(strategy="momentum", total_matches=5, steps_with_matches=2, instruments=("SBIN",))
        summary = BacktestSummary(total_steps=1, completed_steps=1, failed_steps=0, performance=(perf,))
        step = BacktestStep(replay_date=now.date(), as_of=now, status=ExecutionStatus.COMPLETED, scan_report=None, watchlist=None, strategy_execution=None, note="test step")
        session = BacktestSession(session_id="session-1", steps=(step,), summary=summary)
        run = BacktestRun(run_id="bt-1", first_replay_date=now.date(), last_replay_date=now.date(), session=session)
        p.runs.append(run)  # type: ignore[attr-defined]

        response = client.get("/api/v1/backtests/runs", headers=headers)
        assert response.status_code == 200
        
        data = response.json()
        assert data["status"] == "success"
        runs = data["data"]
        assert len(runs) == 1
        assert runs[0]["run_id"] == "bt-1"
        assert runs[0]["total_steps"] == 1
        assert runs[0]["completed_steps"] == 1

    def test_get_run_success(self, client: TestClient) -> None:
        headers = get_auth_headers(client, Role.ANALYST)
        p = get_backtest_run_provider()
        
        now = datetime.now(tz=timezone.utc)
        perf = StrategyPerformance(strategy="momentum", total_matches=5, steps_with_matches=2, instruments=("SBIN",))
        summary = BacktestSummary(total_steps=1, completed_steps=1, failed_steps=0, performance=(perf,))
        step = BacktestStep(replay_date=now.date(), as_of=now, status=ExecutionStatus.COMPLETED, scan_report=None, watchlist=None, strategy_execution=None, note="test step")
        session = BacktestSession(session_id="session-1", steps=(step,), summary=summary)
        run = BacktestRun(run_id="bt-1", first_replay_date=now.date(), last_replay_date=now.date(), session=session)
        p.runs.append(run)  # type: ignore[attr-defined]

        response = client.get("/api/v1/backtests/runs/bt-1", headers=headers)
        assert response.status_code == 200
        
        data = response.json()["data"]
        assert data["run_id"] == "bt-1"
        assert len(data["summary"]["performance"]) == 1
        assert data["summary"]["performance"][0]["strategy"] == "momentum"
        assert len(data["steps"]) == 1
        assert data["steps"][0]["note"] == "test step"

    def test_get_run_not_found(self, client: TestClient) -> None:
        headers = get_auth_headers(client, Role.ANALYST)
        response = client.get("/api/v1/backtests/runs/bt-invalid", headers=headers)
        assert response.status_code == 404
        assert response.json()["title"] == "Backtest Run Not Found"
