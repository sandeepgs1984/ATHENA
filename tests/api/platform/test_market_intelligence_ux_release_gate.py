"""Release-gate regressions for the Market Intelligence UX track (MI-UX-1
through MI-UX-4, see docs/design/ATHENA-MARKET-INTELLIGENCE-UX-ROADMAP.md).

These tests intentionally inspect the assembled static assets, matching the
existing convention (test_decision_chart_release_gate.py) for this
vanilla-JS dashboard: they lock in each fixed regression without adding a
browser dependency to the test suite.
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


def test_top_opportunities_never_renders_a_partial_card(client: TestClient) -> None:
    """MI-UX-1, corrected same-day: the first fix capped to a flat row count,
    which never engaged on a wide monitor where all cards resolve to one
    row. The real contract is measuring genuine remaining space against the
    actual clipping ancestor, not guessing a row count."""
    js = client.get("/dashboard/dashboard.js").text

    assert "function constrainTopOpportunitiesCards(cardsEl)" in js
    assert 'cardsEl.closest(".market-summary-band")' in js
    # The flawed first attempt's signature/approach must not come back.
    assert "function constrainTopOpportunitiesCards(cardsEl, maxRows)" not in js
    assert "top-opportunities-expand-btn" in js


def test_shared_freshness_phrase_used_everywhere(client: TestClient) -> None:
    """MI-UX-2: Market Summary, Index Leadership, Top Opportunities, and
    Validation Pipeline all render the same "As of" phrase — no more
    "Observed"/"Updated"/"Last Updated:" variants for the identical
    snapshot-freshness concept."""
    js = client.get("/dashboard/dashboard.js").text

    assert 'As of ${formatDecisionTime(asOf)}' in js  # Index Leadership
    assert 'As of ${formatDecisionTime(payload.as_of)}' in js  # Top Opportunities
    assert 'As of ${formatDecisionTime(funnel.as_of)}' in js  # Validation Pipeline
    assert 'As of ${formatDecisionTime(summary.as_of)}' in js  # Market Summary
    assert "Observed ${formatDecisionTime" not in js
    assert "Last Updated: ${formatDecisionTime" not in js


def test_failed_run_gets_real_alert_treatment(client: TestClient) -> None:
    """MI-UX-2: a FAILED validation run must visually interrupt (left-border
    accent, tinted background, icon), not blend into the same muted
    register as routine metadata."""
    js = client.get("/dashboard/dashboard.js").text
    css = _full_css(client)

    assert 'summary.classList.toggle("is-failed-run"' in js
    assert "validation-workbench-alert-icon" in js
    assert ".validation-workbench-summary.is-failed-run" in css
    assert "var(--tone-bad-solid)" in css


def test_one_metric_tile_idiom_for_categorical_indicators(client: TestClient) -> None:
    """MI-UX-3: Momentum, Trend Quality, and Volatility Quality all
    visualize the same 0-4 categorical level and must share one visual
    idiom — the historical bar/dot split must not come back."""
    js = client.get("/dashboard/dashboard.js").text
    html = client.get("/dashboard/").text
    css = _full_css(client)

    assert 'id="market-momentum-indicator" class="market-dot-indicator"' in html
    assert ".market-dot-indicator" in css
    assert ".market-bar-indicator" not in css
    assert "market-bar-indicator" not in js
    # Sparklines/rings are deliberately untouched — they show information
    # (a trend, a percentage) the shared dot idiom can't.
    assert ".market-mini-sparkline" in css
    assert ".market-ring" in css


def test_universe_defaults_to_eligible_not_excluded_noise(client: TestClient) -> None:
    """MI-UX-3: opening Universe must lead with actionable (Eligible)
    symbols — Excluded stays available, but as an explicit choice via the
    same filter, not the default."""
    html = client.get("/dashboard/").text

    assert '<option value="ELIGIBLE" selected>Eligible</option>' in html
    assert '<option value="all">All statuses</option>' in html
    assert '<option value="EXCLUDED">Excluded</option>' in html


def test_header_groups_status_separately_from_actions(client: TestClient) -> None:
    """MI-UX-3: Kite/System-Health status and the diagnostics/refresh/
    guide/restart action icons must render as two distinguishable groups,
    not one undifferentiated row."""
    html = client.get("/dashboard/").text
    css = _full_css(client)

    assert 'class="header-status-group"' in html
    assert 'class="header-action-group"' in html
    assert 'class="header-actions-divider"' in html
    assert ".header-status-group" in css
    assert ".header-action-group" in css
    assert ".header-actions-divider" in css
    # Same elements/ids — grouping must not have dropped any control.
    assert 'id="kite-status-btn"' in html
    assert 'id="system-health-indicator"' in html
    assert 'id="header-diagnostics-toggle"' in html
    assert 'id="refresh-trigger"' in html
    assert 'id="intraday-sop-trigger"' in html
    assert 'id="restart-server-trigger"' in html


def test_relative_strength_label_is_spelled_out(client: TestClient) -> None:
    """MI-UX-4 (owner-reported): "RS" alone reads ambiguously as Rupees at
    a glance; spelled out, it can't."""
    js = client.get("/dashboard/dashboard.js").text

    assert ">Rel Str ${relative}</span>" in js
    assert ">RS ${relative}</span>" not in js


def test_quick_actions_completion_does_not_duplicate_recent_activity(
    client: TestClient,
) -> None:
    """MI-UX-4: a completed full validation was announced three times (a
    toast, Recent Activity, and this persistent line) — the persistent line
    was the redundant one; the toast (ephemeral) and Recent Activity
    (persisted record) already cover it."""
    js = client.get("/dashboard/dashboard.js").text

    assert "`Full validation completed`" not in js
    # The running/failed states remain — they carry information (live
    # progress, error detail) neither the toast nor Recent Activity shows.
    assert "Running full validation" in js
    assert "Full validation failed" in js


def test_evidence_attribution_has_visual_weight_and_does_not_truncate(
    client: TestClient,
) -> None:
    """MI-UX-4: the single most decision-relevant sentence on the screen
    (why the regime/score is what it is, per ADR-005) must not be visually
    subordinate to the decorative summary tiles, and must never silently
    truncate via ellipsis."""
    css = _full_css(client)

    assert "border-left: 3px solid var(--accent)" in css
    match = re.search(r"\.regime-explanation p\s*\{([^}]*)\}", css)
    assert match, ".regime-explanation p rule not found in assembled CSS"
    rule_body = match.group(1)
    assert "white-space: normal" in rule_body
    # The old silent-truncation contract (this exact selector used to
    # nowrap+ellipsis, cutting the explanation off) must not come back.
    # ellipsis is legitimately used elsewhere in this file for other
    # elements, so the check must be scoped to this one rule.
    assert "ellipsis" not in rule_body
