"""Execute production filter handlers with isolated DOM/render dependencies."""

import shutil
import subprocess
from pathlib import Path

import pytest


def test_filters_update_in_place_and_navigation_is_explicit() -> None:
    node = shutil.which("node")
    if not node:
        pytest.skip("Node is required for dashboard behavior checks")
    static = Path(__file__).resolve().parents[3] / "src/athena/api/static"
    source = (static / "js/08b-my-portfolio.js").read_text()
    start = source.index("    function setMyPortfolioQueueView(")
    end = source.index("    function myPortfolioSyncFailureSummary(", start)
    predicates = source[
        source.index("    function myPortfolioRowMatchesSmartGroup("):
        source.index("    function myPortfolioRowVisible(")
    ]
    binding = next(
        line for line in source.splitlines()
        if '"my-portfolio-view-holdings")?.addEventListener' in line
    )
    harness = r"""
const assert = require('node:assert/strict');
let scrolls = 0, renders = 0;
const rows = [{ matches: true }, { matches: false }];
const elements = new Map();
const document = {
    getElementById(id) {
        if (!elements.has(id)) elements.set(id, {
            textContent: '', hidden: false, disabled: false,
            addEventListener(event, fn) { this.click = fn; }
        });
        return elements.get(id);
    },
    querySelectorAll() { return []; }
};
const myPortfolioState = { triageFiltersExpanded: true };
function resetMyPortfolioTriageState() {
    myPortfolioState.triage = { queueView: false, attention: [], smart: {} };
}
resetMyPortfolioTriageState();
const MY_PORTFOLIO_ATTENTION_FILTERS = ['stale'];
const myPortfolioSourceRows = () => rows;
const renderMyPortfolioHoldings = () => { renders++; };
const scrollMyPortfolioHoldingsIntoView = () => { scrolls++; };
const setMyPortfolioTriageFiltersExpanded = value => { myPortfolioState.triageFiltersExpanded = value; };
const myPortfolioTriageCounts = () => ({});
const myPortfolioSmartFilterCount = () => 0;
const renderMyPortfolioTriageFiltersDisclosure = () => {};
const myPortfolioQueueAll = null, myPortfolioQueueOnly = null;
const myPortfolioHoldingsScopeBadge = null, myPortfolioMiniTriage = null;
const myPortfolioTriageLead = null, myPortfolioCommandDashboard = null;
const myPortfolioTriageClear = {};
const myPortfolioTriageSummary = {};
const myPortfolioHasActiveTriage = () => true;
const myPortfolioTriageContext = () => ({});
const myPortfolioRowVisible = row => row.matches;
const myPortfolioDailyStatus = row => row.daily;
const myPortfolioTrendParts = row => row;
const formatMyPortfolioNumber = value => String(value);
"""
    checks = r"""
setMyPortfolioQueueView(true);
toggleMyPortfolioAttentionFilter('needs_review');
toggleMyPortfolioAttentionFilter('stale');
toggleMyPortfolioSmartFilter('status', 'HEALTHY');
clearMyPortfolioTriage();
assert.equal(renders, 5);
assert.equal(scrolls, 0);
assert.equal(myPortfolioState.triageFiltersExpanded, true);
toggleMyPortfolioAttentionFilter('near_trigger');
assert.equal(renders, 5);
renderMyPortfolioTriage(2, 1);
assert.equal(myPortfolioTriageSummary.textContent, '1 of 2 holdings match.');
const jump = elements.get('my-portfolio-view-holdings');
assert.equal(jump.disabled, false);
assert.equal(elements.get('my-portfolio-view-holdings-count').textContent, '1');
jump.click();
assert.equal(scrolls, 1);
rows[0].matches = false;
renderMyPortfolioTriage(2, 0);
assert.equal(myPortfolioTriageSummary.textContent, 'No matching holdings.');
assert.equal(jump.disabled, true);
assert.equal(myPortfolioTriageClear.hidden, false);
renderMyPortfolioTriage(2, 1);
assert.match(myPortfolioTriageSummary.textContent, /1 pinned holding remains visible/);
assert.equal(jump.disabled, false);
assert.equal(scrolls, 1);
myPortfolioState.triageFiltersExpanded = false;
toggleMyPortfolioSmartFilter('status', 'STRONG');
assert.equal(myPortfolioState.triageFiltersExpanded, false);
toggleMyPortfolioSmartFilter('currentness', 'CURRENT');
assert.equal(myPortfolioState.triageFiltersExpanded, false);
toggleMyPortfolioSmartFilter('trend', 'UPTREND');
assert.equal(myPortfolioState.triageFiltersExpanded, true);
assert.equal(myPortfolioRowMatchesSmartGroup(
    { daily: 'REVIEW_HOLD_TIGHT' }, 'daily_review', ['REVIEW_HOLD_TIGHT'], {}
), true);
myPortfolioState.triage.smart = { trend: ['UPTREND'], setup: ['BREAKOUT'] };
assert.equal(myPortfolioRowMatchesSmartFilters({ trend: 'UPTREND', setup: 'BREAKOUT' }, {}), true);
assert.equal(myPortfolioRowMatchesSmartFilters({ trend: 'UPTREND', setup: 'BREAKDOWN' }, {}), false);
"""
    subprocess.run(
        [node, "-e", harness + predicates + source[start:end] + binding + checks],
        check=True, capture_output=True, text=True,
    )
    html = (static / "index.html").read_text()
    assert 'id="my-portfolio-triage-summary" role="status" aria-live="polite"' in html
    assert 'id="my-portfolio-view-holdings"' in html
    assert html.count('id="my-portfolio-view-holdings"') == 1
    quick = html.split('class="my-portfolio-triage-quick-filters"')[1].split(
        '<div id="my-portfolio-smart-filters-panel"'
    )[0]
    assert 'data-smart-group="status"' in quick
    assert 'data-smart-group="currentness"' in quick
    assert 'data-smart-group="setup" data-smart-value="BREAKDOWN"' in html
    assert 'id="my-portfolio-view-holdings" class="btn btn-primary btn-sm"' in html
    assert 'data-smart-group="daily_review" data-smart-value="REVIEW_HOLD_TIGHT"' in html
    assert '<span>Trend</span>' in html
    assert '<span>Setup</span>' in html
