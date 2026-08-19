"""DX-12a: 50/100 EMA trend context in the Table view and as a filter.

Requested directly by the owner ("adding 50 and 100 ema... check this on how
we can include this"). **Not a DAR-CARD rule** — see screening/trend.py's
module docstring. These tests guard three things: the columns actually render
in the row (not just declared), the filter's plain-language note names what it
is NOT (a Darvas rule), and the guide's new claims are grounded against the
same constants the engine actually uses — the discipline test_dx11_guide.py
established, extended to this milestone's additions.
"""

from __future__ import annotations

import re
from pathlib import Path

from athena.darvax.screening.trend import EMA_TREND_PERIOD_LONG, EMA_TREND_PERIOD_MEDIUM
from tests.darvax.test_dx4b_tab import _strip_js_comments

REPO_ROOT = Path(__file__).resolve().parents[2]
STATIC = REPO_ROOT / "src" / "athena" / "darvax" / "api" / "static"
HTML = (STATIC / "index.html").read_text(encoding="utf-8")
CSS = (STATIC / "darvax.css").read_text(encoding="utf-8")
JS = _strip_js_comments((STATIC / "darvax.js").read_text(encoding="utf-8"))
GUIDE_HTML = HTML[
    HTML.index('<div id="guide-backdrop"') :
    HTML.index("<!-- ===================== Screener (DX-6c)")
]


def _columns_block():
    start = JS.index("var COLUMNS = [")
    return JS[start : JS.index("];", start)]


# --------------------------------------------------------------------------- #
# 1. The Table columns
# --------------------------------------------------------------------------- #


def test_ema_periods_match_the_engines_own_constants():
    """50 and 100 are asserted against trend.py, not retyped as literals that
    could silently drift from what the sweep actually computes."""
    assert EMA_TREND_PERIOD_MEDIUM == 50
    assert EMA_TREND_PERIOD_LONG == 100


def test_table_has_both_ema_columns_under_context():
    block = _columns_block()
    assert '{ key: "ema_50", label: "50 EMA"' in block
    assert '{ key: "ema_100", label: "100 EMA"' in block
    for key in ("ema_50", "ema_100"):
        entry = block[block.index(f'"{key}"') : block.index("},", block.index(f'"{key}"'))]
        assert 'group: "context"' in entry, f"{key} is not grouped with context"


def test_ema_column_hints_disclose_this_is_not_a_darvas_rule():
    """Every other column on the trade/context bands traces to the DAR-CARD or
    a DX-10a measurement; these two must say plainly that they don't."""
    block = _columns_block()
    for key in ("ema_50", "ema_100"):
        entry = block[block.index(f'"{key}"') : block.index("},", block.index(f'"{key}"'))]
        assert "Darvas" in entry, f"{key}'s hint does not disclose its non-Darvas origin"


def test_ema_cells_are_rendered_in_the_row_between_box_height_and_liquidity():
    """A column declared in COLUMNS but never emitted in the row-building loop
    renders a header with nothing beneath it — caught by position, not just
    presence."""
    row_fn = JS[JS.index("function renderTiers") : JS.index("function detailHtml")]
    box_idx = row_fn.index("box_height_pct")
    ema50_idx = row_fn.index("levelCell(row.ema_50")
    ema100_idx = row_fn.index("levelCell(row.ema_100")
    liq_idx = row_fn.index("liqCell(row)")
    assert box_idx < ema50_idx < ema100_idx < liq_idx, (
        "EMA cells are not emitted between box height and liquidity, where "
        "the COLUMNS declaration places their headers"
    )


def test_ema_cells_use_the_shared_rupee_formatter():
    """Same helper as Buy-above/Stop-loss — not a third money-formatting path
    (the exact class of bug that caused the doubled-₹ regression earlier this
    track)."""
    row_fn = JS[JS.index("function renderTiers") : JS.index("function detailHtml")]
    assert "levelCell(row.ema_50," in row_fn
    assert "levelCell(row.ema_100," in row_fn


def test_colspan_still_tracks_the_grown_column_count():
    assert 'colspan="8"' not in JS
    assert 'colspan="12"' not in JS  # the DX-9a literal, if anyone reintroduces one
    body = JS[JS.index('<tr><td colspan=') : JS.index("</tbody></table>")]
    computed = re.findall(r"colspan=\"' \+ ([A-Za-z.]+) \+ '\"", body)
    assert set(computed) == {"COLUMNS.length"}, computed


# --------------------------------------------------------------------------- #
# 2. The filter
# --------------------------------------------------------------------------- #


def test_trend_filter_control_exists_with_two_directional_options():
    block = HTML[HTML.index('id="f-trend"') : HTML.index("</select>", HTML.index('id="f-trend"'))]
    assert 'value="above"' in block
    assert 'value="below"' in block


def test_trend_filter_labels_do_not_claim_safety_or_quality():
    """Box height's filter avoided calling a tight box "safer"; trend must
    avoid the equivalent claim for symmetry — DarvaX makes no quality claim
    about a method labelled experimental and unvalidated."""
    block = HTML[HTML.index('id="f-trend"') : HTML.index("</select>", HTML.index('id="f-trend"'))]
    for word in ("safer", "better", "stronger buy", "quality"):
        assert word not in block.lower()


def test_trend_filters_plain_meaning_names_what_it_is_not():
    assert "var TREND_FILTER_PLAIN" in JS
    block = JS[JS.index("var TREND_FILTER_PLAIN") : JS.index("function renderFilterNote")]
    assert "not one of Darvas' own rules" in block.lower() or "not one of darvas" in block.lower()


def test_trend_state_treats_a_partial_reading_as_unmeasured_not_guessed():
    """A row with EMA(50) known and EMA(100) absent (or vice versa) cannot
    honestly be called above or below both — it must be excluded from either
    option, the same honesty rule DX-10a applies to unmeasured liquidity."""
    fn = JS[JS.index("function trendStateFor") : JS.index("function applyFilters")]
    assert "=== null" in fn or "== null" in fn
    assert "return null" in fn


def test_trend_absent_from_a_pre_dx12a_sweep_disables_the_control():
    assert "function trendIsAbsentFromThisSweep" in JS
    fn = JS[JS.index("function syncTrendControl") : JS.index("function ", JS.index("function syncTrendControl") + 10)]
    assert "S.fTrend.disabled" in fn
    assert 'S.fTrend.value = ""' in fn, (
        "a disabled trend control must clear its value too, or a threshold "
        "chosen on an earlier sweep keeps filtering invisibly"
    )


def test_clear_filters_resets_the_trend_control_too():
    clear_fn = JS[JS.index('S.fClear.addEventListener') : JS.index('});', JS.index('S.fClear.addEventListener')) + 3]
    assert "S.fTrend" in clear_fn


def test_every_filter_control_is_marked_when_active():
    """The data-empty loop must include all four controls, or the trend
    select would look inactive even while filtering."""
    fn = JS[JS.index("function renderFilterNote") : JS.index("S.fClear.hidden")]
    assert "S.fTrend" in fn


# --------------------------------------------------------------------------- #
# 3. The guide's new claims, grounded
# --------------------------------------------------------------------------- #


def test_guide_documents_the_ema_field_with_correct_periods():
    plain = GUIDE_HTML.replace("<strong>", "").replace("</strong>", "")
    assert f"{EMA_TREND_PERIOD_MEDIUM} EMA" in plain
    assert f"{EMA_TREND_PERIOD_LONG} EMA" in plain
    assert "Not a DAR-CARD rule" in plain or "not a dar-card rule" in plain.lower()


def test_guide_documents_the_trend_filter():
    plain = GUIDE_HTML.replace("<strong>", "").replace("</strong>", "")
    assert "<dt>Trend</dt>" in GUIDE_HTML
    assert "not one of darvas" in plain.lower() or "not a dar-card rule" in plain.lower()
