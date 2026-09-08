"""MP-NX5 snapshot review timeline API/service tests."""

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

NOW = datetime(2026, 9, 8, 10, 0, tzinfo=timezone.utc)
MID = datetime(2026, 9, 7, 10, 0, tzinfo=timezone.utc)
EARLIER = datetime(2026, 9, 6, 10, 0, tzinfo=timezone.utc)


def _row_payload(
    symbol: str,
    *,
    status: str,
    next_action: str,
    last_price: str = "104",
    pnl_pct: str = "4.0",
    daily_review_status: str = "HOLD",
    guidance: str | None = None,
    trend_or_setup: str = "UPTREND / -",
) -> dict[str, object]:
    instrument_id = f"NSE:{symbol}"
    freshness = {"analysis_version": "test"}
    provenance = {"instrument_id": instrument_id}
    daily_review: dict[str, object] = {
        "review_status": daily_review_status,
        "methodology_version": "portfolio-daily-review-v0",
        "supertrend_version": "supertrend-10-3-athena-v0",
    }
    if guidance is not None:
        daily_review["guidance"] = guidance
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
            "trend_or_setup": trend_or_setup,
            "pnl_pct": pnl_pct,
            "current_value": "1040",
            "last_price": last_price,
            "daily_review": daily_review,
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
    symbol: str = "INFY",
    sync_status: SyncRunStatus = SyncRunStatus.SUCCESS,
    include_row: bool = True,
    last_price: str = "104",
    pnl_pct: str = "4.0",
    daily_review_status: str = "HOLD",
    guidance: str | None = None,
    trend_or_setup: str = "UPTREND / -",
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
        status=sync_status,
        finished_at=finished_at,
        succeeded_holdings=1 if include_row else 0,
        failed_holdings=0 if include_row else 1,
    )
    if not include_row:
        # A completed run still needs a snapshot row for the list query.
        other = _row_payload("TCS", status="HEALTHY", next_action="HOLD")
        other["snapshot_id"] = f"{sync_run_id}-row-0001"
        repo.save_portfolio_analysis_snapshots(sync_run_id=sync_run_id, rows=[other])
        return
    payload = _row_payload(
        symbol,
        status=status,
        next_action=next_action,
        last_price=last_price,
        pnl_pct=pnl_pct,
        daily_review_status=daily_review_status,
        guidance=guidance,
        trend_or_setup=trend_or_setup,
    )
    payload["snapshot_id"] = f"{sync_run_id}-row-0001"
    repo.save_portfolio_analysis_snapshots(sync_run_id=sync_run_id, rows=[payload])


def test_snapshot_timeline_requires_a_completed_snapshot(tmp_path: Path) -> None:
    repo = SqliteRepository(tmp_path / "athena.db")
    repo.initialize()
    with pytest.raises(MyPortfolioSyncNotFoundError):
        MyPortfolioService(repo).snapshot_review_timeline("NSE:INFY")


def test_snapshot_timeline_endpoint_returns_404_without_snapshot(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    monkeypatch.setenv("ATHENA_DB_PATH", str(tmp_path / "athena.db"))
    client = TestClient(create_app(APISettings()), raise_server_exceptions=False)
    response = client.get(
        "/api/v1/my-portfolio/snapshot/timeline",
        params={"instrument_id": "NSE:INFY"},
        headers=get_auth_headers(client, Role.OPERATOR),
    )
    assert response.status_code == 404


def test_snapshot_timeline_needs_two_snapshots(tmp_path: Path) -> None:
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
    timeline = MyPortfolioService(repo).snapshot_review_timeline("NSE:INFY")
    assert timeline.comparison_available is False
    assert timeline.snapshot_count == 1
    assert timeline.events == []
    assert timeline.note == "Two completed snapshots are required to build a review timeline."


def test_snapshot_timeline_reports_status_and_action_history(tmp_path: Path) -> None:
    repo = SqliteRepository(tmp_path / "athena.db")
    repo.initialize()
    _seed_snapshot_run(
        repo,
        sync_run_id="sync-first",
        started_at=EARLIER,
        finished_at=EARLIER,
        status="HEALTHY",
        next_action="HOLD",
    )
    _seed_snapshot_run(
        repo,
        sync_run_id="sync-mid",
        started_at=MID,
        finished_at=MID,
        status="AT_RISK",
        next_action="EXIT",
    )
    _seed_snapshot_run(
        repo,
        sync_run_id="sync-current",
        started_at=NOW,
        finished_at=NOW,
        status="AT_RISK",
        next_action="WATCH",
    )
    timeline = MyPortfolioService(repo).snapshot_review_timeline("NSE:INFY")
    assert timeline.comparison_available is True
    assert timeline.snapshot_count == 3
    assert timeline.current_snapshot_id == "sync-current"
    assert [event.snapshot_id for event in timeline.events] == ["sync-current", "sync-mid"]
    assert "Action changed" in timeline.events[0].badges
    assert "Status changed" in timeline.events[1].badges


def test_snapshot_timeline_endpoint_returns_factual_history(
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
        "/api/v1/my-portfolio/snapshot/timeline",
        params={"instrument_id": "NSE:INFY"},
        headers=get_auth_headers(client, Role.OPERATOR),
    )
    assert response.status_code == 200
    payload = response.json()["data"]
    assert payload["comparison_available"] is True
    assert payload["symbol"] == "INFY"
    assert payload["events"][0]["presence"] == "CHANGED"
    assert "Status changed" in payload["events"][0]["badges"]
    assert "Action changed" in payload["events"][0]["badges"]


def test_snapshot_timeline_marks_partial_sync(tmp_path: Path) -> None:
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
        next_action="HOLD",
        sync_status=SyncRunStatus.PARTIAL,
    )
    timeline = MyPortfolioService(repo).snapshot_review_timeline("NSE:INFY")
    assert timeline.events[0].sync_status is SyncRunStatus.PARTIAL
    assert timeline.note == "Latest snapshot is a partial sync."


def test_snapshot_timeline_missing_holding_is_honest(tmp_path: Path) -> None:
    repo = SqliteRepository(tmp_path / "athena.db")
    repo.initialize()
    _seed_snapshot_run(
        repo,
        sync_run_id="sync-previous",
        started_at=EARLIER,
        finished_at=EARLIER,
        status="HEALTHY",
        next_action="HOLD",
        include_row=False,
    )
    _seed_snapshot_run(
        repo,
        sync_run_id="sync-current",
        started_at=NOW,
        finished_at=NOW,
        status="HEALTHY",
        next_action="HOLD",
        include_row=False,
    )
    timeline = MyPortfolioService(repo).snapshot_review_timeline("NSE:INFY")
    assert timeline.comparison_available is True
    assert timeline.events == []
    assert timeline.note == "This holding is not in the recent snapshots."
