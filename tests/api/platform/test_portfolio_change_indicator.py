"""Compact row indicators preserve every existing, privacy-safe reason."""

import shutil
import subprocess
from pathlib import Path

import pytest


def test_change_indicator_preserves_reasons_and_privacy() -> None:
    node = shutil.which("node")
    if not node:
        pytest.skip("Node is required for dashboard behavior checks")
    static = Path(__file__).resolve().parents[3] / "src/athena/api/static"
    source = (static / "js/08b-my-portfolio.js").read_text()
    start = source.index("    function myPortfolioDisplayChangeBadge(")
    end = source.index("    function myPortfolioChangeFieldValueHtml(", start)
    harness = r"""
const assert = require('node:assert/strict');
const myPortfolioState = { valuesHidden: false };
const myPortfolioChangeForRow = row => row;
const escapeMyPortfolioHtml = text => String(text).replaceAll('&', '&amp;')
    .replaceAll('<', '&lt;').replaceAll('>', '&gt;').replaceAll('"', '&quot;');
"""
    checks = r"""
assert.equal(myPortfolioChangeBadgeChips({}), '');
assert.equal(myPortfolioChangeBadgeChips({ badges: ['Removed holding'] }), '');
assert.match(myPortfolioChangeBadgeChips({ badges: ['New holding'] }), />1 change</);
const badges = ['Status changed', 'Next action changed', 'P&L moved +12.3%', 'Review changed'];
const html = myPortfolioChangeBadgeChips({ badges });
assert.match(html, />4 changes</);
assert.equal((html.match(/my-portfolio-change-count/g) || []).length, 1);
for (const badge of badges) assert.ok(html.includes(escapeMyPortfolioHtml(badge)));
assert.ok(html.includes('title="4 changes: '));
assert.ok(html.includes('aria-label="4 changes: '));
assert.ok(html.includes('tabindex="0"'));
myPortfolioState.valuesHidden = true;
const masked = myPortfolioChangeBadgeChips({ badges });
assert.ok(!masked.includes('12.3'));
assert.ok(masked.includes('P&amp;L moved'));
assert.match(masked, />4 changes</);
const escaped = myPortfolioChangeBadgeChips({ badges: ['<img src=x "bad">'] });
assert.ok(!escaped.includes('<img'));
assert.ok(escaped.includes('&lt;img src=x &quot;bad&quot;&gt;'));
assert.deepEqual(badges, ['Status changed', 'Next action changed', 'P&L moved +12.3%', 'Review changed']);
"""
    subprocess.run(
        [node, "-e", harness + source[start:end] + checks],
        check=True, capture_output=True, text=True,
    )
    # Owner-authored badges remain separate from the sync-derived indicator.
    assert "${myPortfolioPinBadge(row)}${myPortfolioNoteBadge(row)}" in source
    assert "change.badges.map(badge =>" in source  # Full detail remains expanded.
