"""Release-gate regressions for the Decision Brief chart track (CH-6).

These tests intentionally inspect the assembled static assets. ATHENA's
dashboard is a static vanilla-JS surface, so the release gate locks in the
chart's no-fabrication, nonblank-rendering, no-scroll modal, and interaction
contracts without adding a browser dependency to the test suite.
"""

from __future__ import annotations

import re

from fastapi.testclient import TestClient

_IMPORT_RE = re.compile(r'@import\s+url\("([^"]+)"\)')


def _full_css(client: TestClient) -> str:
    manifest = client.get("/dashboard/dashboard.css")
    assert manifest.status_code == 200
    parts = []
    for href in _IMPORT_RE.findall(manifest.text):
        resp = client.get(f"/dashboard/{href}")
        assert resp.status_code == 200, href
        parts.append(resp.text)
    return "\n".join(parts)


def test_chart_renderer_has_nonblank_and_empty_state_contracts(client: TestClient) -> None:
    js = client.get("/dashboard/dashboard.js").text

    assert '<svg class="decision-candlestick-chart decision-chart-svg"' in js
    assert "decision-chart-price-panel" in js
    assert "decision-chart-volume-panel" in js
    assert "decision-candle" in js
    assert "decision-chart-empty" in js
    assert "No persisted ${escapeDecisionHtml(timeframe)} candles" in js
    assert "Chart unavailable. Decision evidence and TradePlan remain unchanged." in js


def test_chart_interaction_contract_avoids_known_tap_and_keyboard_regressions(
    client: TestClient,
) -> None:
    js = client.get("/dashboard/dashboard.js").text
    css = _full_css(client)

    assert "hitArea.getBoundingClientRect()" in js
    assert "event.currentTarget.getBoundingClientRect()" not in js
    assert "document.addEventListener(\"pointerdown\"" in js
    assert "document.addEventListener(\"click\"" in js
    assert "activeInspectionHostId" in js
    assert "passiveFocus" in js
    assert 'role="slider"' not in js
    assert 'tabindex="0" role="group"' in js
    assert ".decision-chart-hit-area" in css
    assert "pointer-events: all" in css


def test_chart_modal_release_gate_prevents_internal_scroll(client: TestClient) -> None:
    html = client.get("/dashboard/").text
    css = _full_css(client)

    assert "dashboard.css?v=9.149.1" in html
    assert "dashboard.js?v=9.149.5" in html
    assert ".chart-modal-container" in css
    assert "height: 80vh" in css
    assert "width: 80vw" in css
    assert ".chart-modal-container .modal-body" in css
    assert "overflow: hidden" in css
    assert ".chart-modal-canvas .decision-chart-shell" in css
    assert "@media (max-width: 900px)" in css
    assert "width: 96vw" in css
    assert "height: 88vh" in css


def test_chart_markers_are_persisted_only_and_not_fabricated(client: TestClient) -> None:
    js = client.get("/dashboard/dashboard.js").text
    marker_fn = js[js.index("function chartPersistedEvents"):js.index("function nearestCandleIndexForTs")]

    assert "function chartPersistedEvents" in js
    assert "meta.ts" in js
    assert "activeJournalEntry.action_ts" in js
    assert "activeTradeOutcome.closed_ts" in js
    assert "nearestCandleIndexForTs" in js
    assert "return null" in js
    assert "revalidation" not in marker_fn.lower()
    assert "placeholder" not in marker_fn.lower()


def test_chart_limit_and_rendering_budget_contract(client: TestClient) -> None:
    js = client.get("/dashboard/dashboard.js").text

    assert "CHART_LIMITS = [60, 120, 300, 500]" in js
    assert "limit=${encodeURIComponent(prefs.limit)}" in js
    assert "const width = 1040" in js
    assert "const height = 440" in js
    assert "candles.map" in js
    assert "candles.forEach" in js
