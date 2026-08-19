"""AUX-1a advisory freshness service and API contract tests."""

from __future__ import annotations

from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

from fastapi.testclient import TestClient

from athena.api.dependencies import get_advisory_freshness_service
from athena.api.v1.dtos.dashboard import AdvisoryFreshnessDTO
from athena.api.v1.services.advisory_freshness_service import AdvisoryFreshnessService
from athena.api.v1.services.dashboard_service import DashboardService
from athena.domain.market import MarketSnapshot

IST = ZoneInfo("Asia/Kolkata")
REPO_ROOT = Path(__file__).resolve().parents[3]


class _SnapshotRepo:
    def __init__(self, observed_at: datetime | None) -> None:
        self._snapshot = (
            MarketSnapshot(ts=observed_at, indices={}) if observed_at is not None else None
        )

    def get_latest_snapshot(self) -> MarketSnapshot | None:
        return self._snapshot


def _service(observed_at: datetime | None) -> AdvisoryFreshnessService:
    session_service = DashboardService(None, None, None)  # type: ignore[arg-type]
    return AdvisoryFreshnessService(
        _SnapshotRepo(observed_at),  # type: ignore[arg-type]
        session_service,
        config_dir=REPO_ROOT / "config",
    )


def test_open_session_current_aging_stale_and_unavailable() -> None:
    as_of = datetime(2026, 7, 31, 10, 0, tzinfo=IST)

    current = _service(datetime(2026, 7, 31, 9, 50, tzinfo=IST)).get_freshness(as_of=as_of)
    aging = _service(datetime(2026, 7, 31, 9, 44, tzinfo=IST)).get_freshness(as_of=as_of)
    stale = _service(datetime(2026, 7, 31, 9, 39, tzinfo=IST)).get_freshness(as_of=as_of)
    unavailable = _service(None).get_freshness(as_of=as_of)

    assert (current.status, current.tone) == ("CURRENT", "GOOD")
    assert (aging.status, aging.tone) == ("AGING", "WARNING")
    assert (stale.status, stale.tone) == ("STALE", "DANGER")
    assert unavailable.status == "UNAVAILABLE"
    assert unavailable.observed_at is None
    assert current.freshness_limit_seconds == 1200


def test_post_close_snapshot_is_current_review_data() -> None:
    result = _service(
        datetime(2026, 7, 31, 15, 15, tzinfo=IST)
    ).get_freshness(as_of=datetime(2026, 7, 31, 18, 0, tzinfo=IST))

    assert (result.status, result.tone) == ("CURRENT", "NEUTRAL")
    assert result.market_session == "CLOSED"
    assert result.headline.startswith("Closed review")


def test_weekend_and_holiday_use_latest_completed_session() -> None:
    weekend = _service(
        datetime(2026, 7, 31, 15, 15, tzinfo=IST)
    ).get_freshness(as_of=datetime(2026, 8, 1, 12, 0, tzinfo=IST))
    holiday = _service(
        datetime(2026, 9, 11, 15, 15, tzinfo=IST)
    ).get_freshness(as_of=datetime(2026, 9, 14, 12, 0, tzinfo=IST))

    assert (weekend.status, weekend.market_session) == ("CURRENT", "NO_SESSION")
    assert (holiday.status, holiday.market_session) == ("CURRENT", "NO_SESSION")
    assert weekend.next_live_at is not None
    assert holiday.next_live_at is not None


def test_closed_market_rejects_observation_before_latest_close_window() -> None:
    result = _service(
        datetime(2026, 7, 30, 15, 30, tzinfo=IST)
    ).get_freshness(as_of=datetime(2026, 7, 31, 18, 0, tzinfo=IST))

    assert (result.status, result.tone) == ("STALE", "DANGER")


def test_api_returns_additive_timezone_aware_contract(client: TestClient) -> None:
    expected = AdvisoryFreshnessDTO(
        status="CURRENT",
        tone="GOOD",
        observed_at=datetime(2026, 7, 31, 10, 0, tzinfo=IST),
        age_seconds=30,
        freshness_limit_seconds=1200,
        source="market_snapshot",
        headline="Current · as of 10:00 AM IST",
        explanation="Inside the configured freshness window.",
        market_session="OPEN",
        next_live_at=datetime(2026, 7, 31, 9, 15, tzinfo=IST),
    )

    class _Service:
        def get_freshness(self, *, as_of=None):
            return expected

    client.app.dependency_overrides[get_advisory_freshness_service] = lambda: _Service()
    try:
        response = client.get("/api/v1/dashboard/advisory-freshness")
    finally:
        client.app.dependency_overrides.pop(get_advisory_freshness_service, None)

    assert response.status_code == 200
    data = response.json()["data"]
    assert data["status"] == "CURRENT"
    assert data["tone"] == "GOOD"
    assert data["observed_at"].endswith("+05:30")
    assert data["source"] == "market_snapshot"
