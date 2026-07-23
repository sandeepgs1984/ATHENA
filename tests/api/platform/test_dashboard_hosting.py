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


def test_dashboard_modals_are_inert_outside_tab_flow(client: TestClient) -> None:
    """Inactive modals must not participate in tab document flow (P9 console hotfix)."""
    html = client.get("/dashboard/").text
    css = client.get("/dashboard/dashboard.css").text
    js = client.get("/dashboard/dashboard.js").text

    # Modals are present once each and marked inert at rest
    assert html.count('id="trace-modal"') == 1
    assert html.count('id="backtest-modal"') == 1
    assert 'id="trace-modal" class="modal-overlay" hidden' in html
    assert 'id="backtest-modal" class="modal-overlay" hidden' in html
    assert 'aria-hidden="true"' in html

    # Modals must live outside tab panes (after #app close)
    assert "Modals live outside #app" in html
    assert html.find('id="trace-modal"') > html.find("Modals live outside #app")
    assert html.find('id="backtest-modal"') > html.find("Modals live outside #app")
    assert 'id="tab-operations"' in html
    assert html.find('id="trace-modal"') > html.find('id="tab-operations"')

    # CSS fortress: inactive overlays are forced out of layout
    assert "display: none !important" in css
    assert ".modal-overlay.active" in css

    # JS exposes open/close helpers and clears loaders on failure
    assert "function openModal" in js
    assert "function closeModal" in js
    assert "Failed to load strategy profiles" in js
    assert "Failed to load decisions" in js

    # Operations console (P9.7) is live — warnings feed + backup panel, not a fake loader
    assert 'id="ops-warnings-feed"' in html
    assert 'id="ops-telemetry-chart"' in html
    assert 'id="ops-backups-body"' in html
    assert "Loading platform telemetry, logs, and triggers..." not in html
    assert "loadOperationsWorkspace" in js
    assert "startOpsStream" in js
