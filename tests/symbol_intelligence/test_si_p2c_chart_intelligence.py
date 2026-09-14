"""SI-P2C completed-D1 chart-intelligence contracts."""

from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path

from athena.api.app import assemble_dashboard_js

STATIC = Path("src/athena/api/static")
JS = STATIC / "js/08c-symbol-intelligence.js"
CSS = STATIC / "css/15-symbol-intelligence.css"
HTML = STATIC / "index.html"


def _js() -> str:
    return JS.read_text(encoding="utf-8")


def _run_chart_helpers(checks: str) -> dict[str, object]:
    source = _js()
    finite = source[source.index("function siFiniteNumber") : source.index("function siMoney")]
    helpers = source[
        source.index("function siChartDateKey") : source.index("function renderSiD1Chart")
    ]
    node = shutil.which("node")
    assert node is not None, "Node is required for SI-P2C behavioral chart tests"
    completed = subprocess.run(
        [node, "-e", finite + helpers + checks],
        check=True,
        capture_output=True,
        text=True,
    )
    return json.loads(completed.stdout)


def test_si_p2c_sma_warmup_thresholds_and_arithmetic() -> None:
    observed = _run_chart_helpers(
        """
const seq = n => Array.from({length: n}, (_, index) => index + 1);
const result = {
  sma20At19: siChartTrailingSma(seq(19), 20).at(-1),
  sma20At20: siChartTrailingSma(seq(20), 20).at(-1),
  sma50At49: siChartTrailingSma(seq(49), 50).at(-1),
  sma50At50: siChartTrailingSma(seq(50), 50).at(-1),
  rolling20At21: siChartTrailingSma(seq(21), 20).at(-1)
};
process.stdout.write(JSON.stringify(result));
"""
    )
    assert observed == {
        "sma20At19": None,
        "sma20At20": 10.5,
        "sma50At49": None,
        "sma50At50": 25.5,
        "rolling20At21": 11.5,
    }


def test_si_p2c_completed_session_cutoff_excludes_future_and_unfinished_rows() -> None:
    observed = _run_chart_helpers(
        """
const candle = (date, close, extra = {}) => ({
  ts_open: `${date}T00:00:00+05:30`, open: close, high: close + 1,
  low: close - 1, close, volume: 1000, ...extra
});
const prepared = siPrepareD1ChartSeries({candles: [
  candle("2026-09-10", 100),
  candle("2026-09-12", 102),
  candle("2026-09-11", 101),
  candle("2026-09-09", 99, {high: 90})
]}, "2026-09-11T00:00:00+05:30");
process.stdout.write(JSON.stringify({
  dates: prepared.candles.map(item => item.date),
  excludedAfterCutoff: prepared.excludedAfterCutoff,
  invalidCount: prepared.invalidCount,
  cutoff: prepared.cutoff
}));
"""
    )
    assert observed == {
        "dates": ["2026-09-10", "2026-09-11"],
        "excludedAfterCutoff": 1,
        "invalidCount": 1,
        "cutoff": "2026-09-11",
    }


def test_si_p2c_final_smas_reconcile_at_stock_360_display_precision() -> None:
    observed = _run_chart_helpers(
        """
const candles = Array.from({length: 50}, (_, index) => {
  const close = index + 1;
  return {ts_open: `2026-07-${String(index + 1).padStart(2, "0")}T00:00:00+05:30`,
    date: `2026-07-${String(index + 1).padStart(2, "0")}`,
    open: close, high: close + 1, low: close - 0.5, close, volume: 1000};
});
const prepared = {candles, sma20: siChartTrailingSma(candles.map(c => c.close), 20),
  sma50: siChartTrailingSma(candles.map(c => c.close), 50)};
const pass = siChartReconciliation(prepared, {close: 50, fast_sma: 40.5001, slow_sma: 25.5});
const fail = siChartReconciliation(prepared, {close: 50, fast_sma: 40.52, slow_sma: 25.5});
process.stdout.write(JSON.stringify({pass, fail}));
"""
    )
    assert observed["pass"]["final20"] == 40.5  # type: ignore[index]
    assert observed["pass"]["final50"] == 25.5  # type: ignore[index]
    assert observed["pass"]["coherent"] is True  # type: ignore[index]
    assert observed["fail"]["sma20Matches"] is False  # type: ignore[index]
    assert observed["fail"]["coherent"] is False  # type: ignore[index]


def test_si_p2c_levels_require_coherence_and_approved_provenance() -> None:
    observed = _run_chart_helpers(
        """
const zone = (lower, upper, lineage = "PORTFOLIO_STRUCTURAL_REVIEW") => ({lower, upper, lineage});
const levels = siChartLevels({structural_is_coherent: true,
  support_1: zone(98, 100), major_support: zone(90, 93), review_trigger: zone(105, 107),
  target_1: zone(112, 115), target_2: zone(120, 122), target_3: zone(130, 133)});
const badLineage = siChartLevels({structural_is_coherent: true, support_1: zone(98, 100, "OTHER")});
const incoherent = siChartLevels({structural_is_coherent: false, support_1: zone(98, 100)});
process.stdout.write(JSON.stringify({levels, badLineage, incoherent}));
"""
    )
    levels = observed["levels"]
    assert isinstance(levels, list)
    assert [item["short"] for item in levels] == ["S1", "MS", "RT", "T1", "T2", "T3"]
    assert levels[0]["anchorPrice"] == 100
    assert levels[2]["anchorPrice"] == 105
    assert observed["badLineage"] == []
    assert observed["incoherent"] == []


def test_si_p2c_active_level_tag_separates_from_d1_without_moving_anchors() -> None:
    observed = _run_chart_helpers(
        """
const separated = siChartPlaceLevelTag(200, 202, 20, 280, 6);
const alreadyClear = siChartPlaceLevelTag(100, 202, 20, 280, 6);
process.stdout.write(JSON.stringify({separated, alreadyClear}));
"""
    )
    separated = observed["separated"]
    assert separated == {"naturalY": 200, "labelY": 175, "d1Y": 202}
    assert separated["labelY"] + 12 + 6 <= separated["d1Y"] - 9
    assert observed["alreadyClear"] == {"naturalY": 100, "labelY": 100, "d1Y": 202}


def test_si_p2c_persistent_level_selection_survives_transient_preview() -> None:
    observed = _run_chart_helpers(
        """
const state = siChartCreateLevelInteraction(["S1", "MS", "T1", "T2"]);
const selected = state.select("T1", "menu-selection");
const previewed = state.preview("T2", "menu-hover");
const restored = state.clearPreview("menu-hover");
const clicked = state.select("S1", "chart-click");
const afterPointerLeave = state.clearPreview("chart-hover");
const cleared = state.clearAll();
process.stdout.write(JSON.stringify({selected, previewed, restored, clicked, afterPointerLeave, cleared}));
"""
    )
    assert observed["selected"]["activeLevelId"] == "T1"
    assert observed["previewed"]["activeLevelId"] == "T2"
    assert observed["previewed"]["persistentLevelId"] == "T1"
    assert observed["restored"]["activeLevelId"] == "T1"
    assert observed["clicked"]["persistentLevelId"] == "S1"
    assert observed["afterPointerLeave"]["activeLevelId"] == "S1"
    assert observed["cleared"]["activeLevelId"] is None


def test_si_p2c_chart_contract_has_bands_legend_inspection_and_no_midpoint() -> None:
    js = _js()
    renderer = js[js.index("function renderSiD1Chart") : js.index("async function loadSiD1Chart")]
    assert "si-chart-level-band" in renderer
    assert "level.lower" in renderer and "level.upper" in renderer
    assert "(level.lower + level.upper) / 2" not in js
    assert "si-chart-level-connector" in renderer
    assert "si-chart-level-leader" not in renderer
    assert "SMA20" in renderer and "SMA50" in renderer
    assert "Completed D1" in renderer
    assert "siChartInspectionHtml" in renderer
    assert "Vol" in _js()[
        _js().index("function siChartInspectionHtml") : _js().index("function renderSiD1Chart")
    ]
    assert 'tabindex="0" role="group"' in renderer
    assert 'event.key === "ArrowLeft"' in renderer
    assert "golden cross" not in js.lower()
    assert "death cross" not in js.lower()
    assert "buy signal" not in js.lower()
    assert "sell signal" not in js.lower()


def test_si_p2c_visible_windows_slice_only_after_full_history_sma() -> None:
    observed = _run_chart_helpers(
        """
const closes = Array.from({length: 180}, (_, index) => index + 1);
const full20 = siChartTrailingSma(closes, 20);
const full50 = siChartTrailingSma(closes, 50);
const count3m = siChartWindowCount("3M", closes.length);
const count6m = siChartWindowCount("6M", closes.length);
const countAll = siChartWindowCount("ALL", closes.length);
process.stdout.write(JSON.stringify({
  count3m, count6m, countAll,
  full20Final: full20.at(-1), visible20Final: full20.slice(-count3m).at(-1),
  full50Final: full50.at(-1), visible50Final: full50.slice(-count3m).at(-1)
}));
"""
    )
    assert observed == {
        "count3m": 63,
        "count6m": 126,
        "countAll": 180,
        "full20Final": 170.5,
        "visible20Final": 170.5,
        "full50Final": 155.5,
        "visible50Final": 155.5,
    }


def test_si_p2c_date_ticks_scale_with_available_chart_width() -> None:
    observed = _run_chart_helpers(
        """
process.stdout.write(JSON.stringify({
  compact: siChartDateTickIndices(180, true, false),
  standard: siChartDateTickIndices(180, false, false),
  wide: siChartDateTickIndices(180, false, true),
  short: siChartDateTickIndices(2, false, true)
}));
"""
    )
    assert observed == {
        "compact": [0, 179],
        "standard": [0, 90, 179],
        "wide": [0, 45, 90, 134, 179],
        "short": [0, 1],
    }


def test_si_p2c_price_scale_uses_clean_ticks_without_clipping_values() -> None:
    observed = _run_chart_helpers(
        """
const scale = siChartPriceScale([167.4, 178.71, 191.34, 271.2], 4);
process.stdout.write(JSON.stringify({
  scale,
  labels: scale.ticks.map(value => siChartAxisPrice(value, scale.step))
}));
"""
    )
    scale = observed["scale"]
    assert isinstance(scale, dict)
    assert scale["min"] <= 167.4
    assert scale["max"] >= 271.2
    assert scale["min"] < 167.4 and scale["max"] > 271.2
    assert len(scale["ticks"]) in range(3, 8)
    assert all(scale["min"] <= value <= scale["max"] for value in scale["ticks"])
    assert observed["labels"] == ["₹275", "₹250", "₹225", "₹200", "₹175"]


def test_si_p2c_refined_hierarchy_keeps_all_levels_accessible() -> None:
    js = _js()
    renderer = js[js.index("function renderSiD1Chart") : js.index("async function loadSiD1Chart")]
    assert 'windowKey = "6M"' in renderer
    assert '["3M", "6M", "ALL"]' in renderer
    assert "visibleSma20 = prepared.sma20.slice(visibleStart)" in renderer
    assert "visibleSma50 = prepared.sma50.slice(visibleStart)" in renderer
    assert 'class="si-chart-level-toggle"' in renderer
    assert "<span>Levels</span><b>${levels.length}</b>" in renderer
    assert 'class="si-chart-level-menu"' in renderer
    assert 'data-si-level-choice="${level.short}"' in renderer
    assert 'tabindex="0" role="button" aria-label="${siEscape(accessible)}"' in renderer
    assert "Portfolio Structural Review" in renderer
    assert "show-level-labels" not in renderer
    assert "Hide levels" not in renderer
    assert "level.lower" in renderer and "level.upper" in renderer
    assert "d1.support_1 =" not in renderer
    assert "d1.target_1 =" not in renderer


def test_si_p2c_refined_idle_and_interaction_states_are_calm_and_non_actionable() -> None:
    js = _js()
    renderer = js[js.index("function renderSiD1Chart") : js.index("async function loadSiD1Chart")]
    css = CSS.read_text(encoding="utf-8")
    assert 'host.classList.toggle("is-candle-active", active)' in renderer
    assert 'event.key === "Escape"' in renderer
    assert 'event.key === "ArrowLeft"' in renderer
    assert ".si-chart-crosshair" in css and "opacity: 0" in css[
        css.index(".si-chart-crosshair") : css.index(".si-chart-volume-baseline")
    ]
    assert ".si-chart-level-tag" in css
    assert ".si-chart-level-tag.is-inspected" in css
    assert ".si-chart-level.is-inspected .si-chart-level-band" in css
    assert ".si-chart-level.is-inspected .si-chart-level-emphasis" in css
    assert 'state.persistentLevelId === state.activeLevelId' in renderer
    for forbidden in ("buy zone", "sell zone", "safe zone", "danger zone", "strong level"):
        assert forbidden not in renderer.lower()


def test_si_p2c_overlap_resolver_activates_exactly_one_level_by_geometry() -> None:
    observed = _run_chart_helpers(
        """
const levels = [
  {short: "S1", lower: 100, upper: 110},
  {short: "MS", lower: 105, upper: 115},
  {short: "RT", lower: 130, upper: 130}
];
const yAt = value => value;
process.stdout.write(JSON.stringify({
  overlap: siChartResolveLevelAtY(levels, 107, yAt, 8)?.short,
  nearLine: siChartResolveLevelAtY(levels, 124, yAt, 8)?.short,
  none: siChartResolveLevelAtY(levels, 150, yAt, 8)?.short ?? null,
  unchanged: levels
}));
"""
    )
    assert observed["overlap"] == "MS"
    assert observed["nearLine"] == "RT"
    assert observed["none"] is None
    assert observed["unchanged"] == [
        {"short": "S1", "lower": 100, "upper": 110},
        {"short": "MS", "lower": 105, "upper": 115},
        {"short": "RT", "lower": 130, "upper": 130},
    ]


def test_si_p2c_level_menu_and_pointer_states_never_show_a_tag_wall() -> None:
    js = _js()
    renderer = js[js.index("function renderSiD1Chart") : js.index("async function loadSiD1Chart")]
    css = CSS.read_text(encoding="utf-8")
    assert 'role="listbox" aria-label="Approved structural levels"' in renderer
    assert 'role="option" aria-selected="false"' in renderer
    assert '"is-inspected",' in renderer
    assert 'state.activeLevelId' in renderer
    assert 'state.persistentLevelId' in renderer
    assert 'clearLevelPreview("chart-hover")' in renderer
    assert 'event.pointerType === "mouse"' in renderer
    assert 'event.key === "Enter" || event.key === " "' in renderer
    assert 'event.key === "Escape"' in renderer
    assert 'selectLevel(short, "menu-selection")' in renderer
    assert 'previewLevel(short, "menu-hover")' in renderer
    assert 'clearLevelPreview("menu-hover")' in renderer
    assert 'element.classList.toggle("is-selected", selected)' in renderer
    assert "show-level-labels" not in css
    assert ".si-chart-host.is-level-active .si-chart-level:not(.is-inspected)" in css
    narrow = css[css.index("@media (max-width: 720px)") :]
    assert ".si-chart-level-tag" in narrow and "display: none" in narrow
    assert ".si-chart-level-menu" in narrow


def test_si_p2c_d1_sma_windows_and_request_remain_orthogonal_to_level_menu() -> None:
    js = _js()
    renderer = js[js.index("function renderSiD1Chart") : js.index("async function loadSiD1Chart")]
    loader = js[js.index("async function loadSiD1Chart") : js.index("function renderSymbolIntelligence")]
    assert "si-chart-close-tag" in renderer
    assert "Completed D1 close" in renderer
    assert "visibleSma20 = prepared.sma20.slice(visibleStart)" in renderer
    assert "visibleSma50 = prepared.sma50.slice(visibleStart)" in renderer
    assert '["3M", "6M", "ALL"]' in renderer
    assert loader.count("apiRequest(") == 1


def test_si_p2c_window_selection_and_level_emphasis_have_distinct_states() -> None:
    js = _js()
    renderer = js[js.index("function renderSiD1Chart") : js.index("async function loadSiD1Chart")]
    css = CSS.read_text(encoding="utf-8")
    assert 'aria-pressed="${key === windowKey ? "true" : "false"}"' in renderer
    assert 'class="${key === windowKey ? "active" : ""}"' in renderer
    assert '.si-chart-window button[aria-pressed="true"]' in css
    assert '.si-chart-window button:hover:not([aria-pressed="true"])' in css
    assert ".si-chart-window button:focus-visible" in css
    assert 'class="si-chart-level-emphasis"' in renderer
    assert 'width="52" height="24"' in renderer
    assert "font-size: 11px" in css
    assert "Math.max(6, Math.abs(lowerY - upperY))" in renderer
    assert "Math.abs(lowerY - upperY)" in renderer
    assert "siChartPlaceLevelTag(" in renderer
    assert 'selectLevel(level.short, event.pointerType === "mouse" ? "chart-click" : "touch")' in renderer
    assert 'host._siChartPersistentLevelId = state.persistentLevelId' in renderer


def test_si_p2c_preserves_one_request_and_frozen_request_lifecycle() -> None:
    js = _js()
    loader = js[js.index("async function loadSiD1Chart") : js.index("function renderSymbolIntelligence")]
    assert loader.count("apiRequest(") == 1
    assert "timeframe=1d&limit=180" in loader
    assert "sma20" not in loader.lower()
    assert "sma50" not in loader.lower()
    assert "generation !== siLoadGeneration" in loader
    assert 'method: "POST"' in js
    assembled = assemble_dashboard_js(str(STATIC))
    assert "function siPrepareD1ChartSeries" in assembled


def test_si_p2c_invalid_and_responsive_contracts_remain_safe() -> None:
    js = _js()
    chart_block = js[js.index("function siChartBlock") : js.index("function siSentence")]
    renderer = js[js.index("function renderSiD1Chart") : js.index("async function loadSiD1Chart")]
    assert "if (!identity || !identity.resolved)" in chart_block
    assert 'return "";' in chart_block
    assert "const compact = measuredWidth < 520" in renderer
    assert "Math.max(200, measuredWidth)" in renderer
    assert "right: 12" in renderer
    assert "left: width < 280 ? 32 : 40" in renderer
    assert "compact ? 350" in renderer
    assert 'style="--si-chart-height:${height}px"' in renderer
    assert "ResizeObserver" in renderer
    css = CSS.read_text(encoding="utf-8")
    assert ".si-chart {" in css
    assert "max-width: 100%" in css
    assert "touch-action: pan-y" in css
    assert ".si-chart-card" in css
    narrow = css[css.index("@media (max-width: 720px)") :]
    assert "overflow: hidden" in narrow
    assert ".si-chart-host:has(svg.si-chart)" in narrow
    assert ".si-chart-level-control" in narrow and "display: contents" in narrow
    assert "grid-column: 1 / -1" in narrow
    assert "calc(100vw - 11rem)" not in narrow


def test_si_p2c_asset_cache_pin() -> None:
    html = HTML.read_text(encoding="utf-8")
    css = (STATIC / "dashboard.css").read_text(encoding="utf-8")
    assert "dashboard.css?v=9.254.0" in html
    assert "dashboard.js?v=9.254.0" in html
    assert "css/15-symbol-intelligence.css?v=9.254.0" in css
