"""Integration tests for Phase 9.2 Consolidated Dashboard Summary API.
"""

from __future__ import annotations

from fastapi.testclient import TestClient


def test_dashboard_summary_endpoint(client: TestClient) -> None:
    """Verify the dashboard summary API resolves aggregated details correctly."""
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
    
    # Verify values type format conversions
    assert float(data["portfolio_value"]) >= 0.0
    assert isinstance(data["active_positions"], int)
    assert isinstance(data["strategies_matched"], int)
    assert data["health_status"] == "HEALTHY"
