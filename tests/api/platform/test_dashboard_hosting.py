"""Integration tests for Phase 9.1 Dashboard Static Asset Hosting & SPA Routing.
"""

from __future__ import annotations

from fastapi.testclient import TestClient


def test_dashboard_static_hosting_and_fallback(client: TestClient) -> None:
    """Verify static assets are correctly served and client routes fallback to index.html."""
    # 1. Test index.html retrieval
    resp_index = client.get("/dashboard/")
    assert resp_index.status_code == 200
    assert "ATHENA" in resp_index.text
    assert "<aside" in resp_index.text

    # 2. Test CSS loading
    resp_css = client.get("/dashboard/dashboard.css")
    assert resp_css.status_code == 200
    assert "background-color" in resp_css.text

    # 3. Test JS loading
    resp_js = client.get("/dashboard/dashboard.js")
    assert resp_js.status_code == 200
    assert "state" in resp_js.text

    # 4. Test client-side routing fallback (non-existent path starts with /dashboard)
    resp_fallback = client.get("/dashboard/portfolio")
    assert resp_fallback.status_code == 200
    assert "ATHENA" in resp_fallback.text
    assert "<aside" in resp_fallback.text
