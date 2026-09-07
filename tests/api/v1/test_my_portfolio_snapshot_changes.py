"""MP-NX2 snapshot-change API/service tests."""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from tests.api.v1.test_core_apis import get_auth_headers

from athena.api.app import create_app
from athena.api.config import APISettings
from athena.api.exceptions import MyPortfolioSyncNotFoundError
from athena.api.security.models import Role
from athena.api.v1.services.my_portfolio_service import MyPortfolioService
from athena.data.store.repository import SqliteRepository
from athena.portfolio.my_portfolio_contracts import SyncRunStatus

NOW = datetime(2026, 9, 7, 10, 0, tzinfo=timezone.utc)
EARLIER = datetime(2026, 9, 6, 10, 0, tzinfo=timezone.utc)


def _row_payload(symbol: str, *, status: str, next_action: str) -> dict[str, object]:
    instrument_id = f"NSE:{symbol}"
    freshness = {"analysis_version": "test"}
    provenance = {"instrument_id": instrument_id}
    return {
        "snapshot_id": f"{symbol}-row",
        "instrument_id": instrument_id,
        "symbol": symbol,
        "analyzed_at": NOW.isoformat(),
        "price_as_of": None,
        "decision_as_of": None,
        "market_data_through": None,
        "analysis_version": "test",
        "row": {
            "symbol": symbol,
            "qty": 10,
            "avg_price": "100",
            "investment": "1000",
            "status": status,
            "next_action": next_action,
            "trend_or_setup": "UPTREND / -",
            "pnl_pct": "4.0",
            "current_value": "1040",
            "last_price": "104",
            "daily_review": {
                "review_status": "HOLD",
                "methodology_version": "portfolio-daily-review-v0",
                "supertrend_version": "supertrend-10-3-athena-v0",
            },
            "freshness": freshness,
            "provenance": provenance,
        },
        "freshness": freshness,
        "provenance": provenance,
        "unavailable": [],
        "failures": [],
    }


def _seed_snapshot_run(
    repo: SqliteRepository,
    *,
    sync_run_id: str,
    started_at: datetime,
    finished_at: datetime,
    status: str,
    next_action: str,
) -> None:
    repo.create_portfolio_sync_run(
        sync_run_id=sync_run_id,
        started_at=started_at,
        total_holdings=1,
        analysis_version="test",
        status=SyncRunStatus.QUEUED,
    )
    repo.update_portfolio_sync_run(
        sync_run_id,
        status=SyncRunStatus.SUCCESS,
        finished_at=finished_at,
        succeeded_holdings=1,
        failed_holdings=0,
    )
    payload = _row_payload("INFY", status=status, next_action=next_action)
    payload["snapshot_id"] = f"{sync_run_id}-row-0001"
    repo.save_portfolio_analysis_snapshots(sync_run_id=sync_run_id, rows=[payload])


def test_snapshot_changes_require_a_completed_snapshot(tmp_path: Path) -> None:
    repo = SqliteRepository(tmp_path / "athena.db")
    repo.initialize()
    with pytest.raises(MyPortfolioSyncNotFoundError):
        MyPortfolioService(repo).snapshot_changes_since_previous()


def test_snapshot_changes_endpoint_returns_404_without_snapshot(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    monkeypatch.setenv("ATHENA_DB_PATH", str(tmp_path / "athena.db"))
    client = TestClient(create_app(APISettings()), raise_server_exceptions=False)
    response = client.get(
        "/api/v1/my-portfolio/snapshot/changes",
        headers=get_auth_headers(client, Role.OPERATOR),
    )
    assert response.status_code == 404


def test_snapshot_changes_report_no_previous_snapshot(tmp_path: Path) -> None:
    repo = SqliteRepository(tmp_path / "athena.db")
    repo.initialize()
    _seed_snapshot_run(
        repo,
        sync_run_id="sync-current",
        started_at=NOW,
        finished_at=NOW,
        status="HEALTHY",
        next_action="HOLD",
    )
    changes = MyPortfolioService(repo).snapshot_changes_since_previous()
    assert changes.comparison_available is False
    assert changes.previous_snapshot_id is None
    assert changes.note == "No previous completed snapshot to compare."
    assert changes.rows == []


def test_snapshot_changes_endpoint_returns_factual_delta(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    monkeypatch.setenv("ATHENA_DB_PATH", str(tmp_path / "athena.db"))
    client = TestClient(create_app(APISettings()), raise_server_exceptions=False)
    repo = client.app.state.sqlite_repo
    _seed_snapshot_run(
        repo,
        sync_run_id="sync-previous",
        started_at=EARLIER,
        finished_at=EARLIER,
        status="HEALTHY",
        next_action="HOLD",
    )
    _seed_snapshot_run(
        repo,
        sync_run_id="sync-current",
        started_at=NOW,
        finished_at=NOW,
        status="AT_RISK",
        next_action="EXIT",
    )
    response = client.get(
        "/api/v1/my-portfolio/snapshot/changes",
        headers=get_auth_headers(client, Role.OPERATOR),
    )
    assert response.status_code == 200
    payload = response.json()["data"]
    assert payload["comparison_available"] is True
    assert payload["previous_snapshot_id"] == "sync-previous"
    assert "Status changed" in payload["rows"][0]["badges"]
    assert "Action changed" in payload["rows"][0]["badges"]


def test_snapshot_changes_report_factual_status_and_action_delta(tmp_path: Path) -> None:
    repo = SqliteRepository(tmp_path / "athena.db")
    repo.initialize()
    _seed_snapshot_run(
        repo,
        sync_run_id="sync-previous",
        started_at=EARLIER,
        finished_at=EARLIER,
        status="HEALTHY",
        next_action="HOLD",
    )
    _seed_snapshot_run(
        repo,
        sync_run_id="sync-current",
        started_at=NOW,
        finished_at=NOW,
        status="AT_RISK",
        next_action="EXIT",
    )
    changes = MyPortfolioService(repo).snapshot_changes_since_previous()
    assert changes.comparison_available is True
    assert changes.previous_snapshot_id == "sync-previous"
    assert changes.current_snapshot_id == "sync-current"
    assert len(changes.rows) == 1
    row = changes.rows[0]
    assert row.presence == "CHANGED"
    assert "Status changed" in row.badges
    assert "Action changed" in row.badges
