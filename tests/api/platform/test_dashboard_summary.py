"""Integration tests for Phase 9.2 Consolidated Dashboard Summary API.
"""

from __future__ import annotations

from decimal import Decimal

from fastapi.testclient import TestClient

from athena.api.dependencies import get_portfolio_provider
from athena.domain.decision import Portfolio, Position
from datetime import datetime, timezone


def test_dashboard_summary_endpoint_empty_ledger(client: TestClient) -> None:
    """With no seed data, summary reports zeros and no fabricated day change."""
    get_portfolio_provider().portfolio = None  # type: ignore[attr-defined]

    resp = client.get("/api/v1/dashboard/summary")
    assert resp.status_code == 200

    body = resp.json()
    assert body["status"] == "success"

    data = body["data"]
    assert "portfolio_value" in data
    assert "cash_available" in data
    assert "cash_reserved" in data
    assert "active_positions" in data
    assert "closed_positions" in data
    assert "strategies_matched" in data
    assert "regime_class" in data
    assert "health_status" in data
    assert "exposure_by_sector" in data
    assert "day_change_pct" in data

    assert float(data["portfolio_value"]) == 0.0
    assert data["active_positions"] == 0
    assert data["health_status"] == "HEALTHY"
    assert data["regime_class"] == "UNKNOWN"
    assert data["day_change_pct"] is None
    assert data["exposure_by_sector"] == {}


def test_dashboard_summary_reflects_owner_positions(client: TestClient) -> None:
    """Summary cards follow the owner-entered portfolio provider."""
    now = datetime.now(tz=timezone.utc)
    port = get_portfolio_provider()
    port.portfolio = Portfolio(  # type: ignore[attr-defined]
        ts=now,
        cash=Decimal("50000.00"),
        positions=(
            Position(
                position_id="pos-1",
                instrument_id="INFY",
                opened_ts=now,
                quantity=10,
                avg_price=Decimal("1500.00"),
                meta={"sector": "IT"},
            ),
        ),
        exposure_by_sector={"IT": Decimal("15000.00")},
    )

    resp = client.get("/api/v1/dashboard/summary")
    assert resp.status_code == 200
    data = resp.json()["data"]
    assert Decimal(str(data["cash_available"])) == Decimal("50000.00")
    assert data["active_positions"] == 1
    assert Decimal(str(data["portfolio_value"])) == Decimal("65000.00")
    assert "IT" in data["exposure_by_sector"]
    assert "Cash" in data["exposure_by_sector"]
