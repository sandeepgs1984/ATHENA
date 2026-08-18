"""DX-10a/b: liquidity as a measure, and conviction filters over it.

Two properties. **Unmeasured is not zero** — a symbol with too little history to
judge must not be filtered out as though it were illiquid, and the count of such
symbols must be reported. And **no filter invents data**: there is no market-cap
filter because ATHENA holds no market-cap data.
"""

from __future__ import annotations

import re

from datetime import datetime, timedelta, timezone
from decimal import Decimal
from pathlib import Path

import pytest

from athena.darvax.screening.liquidity import (
    LIQUIDITY_MIN_BARS,
    LIQUIDITY_WINDOW_BARS,
    in_crore,
    traded_value,
)
from athena.domain.enums import Timeframe
from athena.domain.market import Candle
from tests.darvax.test_dx4b_tab import _strip_js_comments

REPO_ROOT = Path(__file__).resolve().parents[2]
STATIC = REPO_ROOT / "src" / "athena" / "darvax" / "api" / "static"
HTML = (STATIC / "index.html").read_text(encoding="utf-8")
CSS = (STATIC / "darvax.css").read_text(encoding="utf-8")
CODE = _strip_js_comments((STATIC / "darvax.js").read_text(encoding="utf-8"))
BASE = datetime(2026, 8, 1, tzinfo=timezone.utc)


def bar(price: str, volume: int, day: int = 0) -> Candle:
    return Candle(
        instrument_id="NSE:X", timeframe=Timeframe.D1,
        ts_open=BASE + timedelta(days=day),
        open=Decimal(price), high=Decimal(price), low=Decimal(price),
        close=Decimal(price), volume=volume, source="test",
    )


# --------------------------------------------------------------------------- #
# 1. The measure
# --------------------------------------------------------------------------- #


def test_traded_value_is_price_times_volume():
    value = traded_value([bar("100", 100_000, i) for i in range(20)])
    assert value == Decimal(10_000_000)
    assert in_crore(value) == Decimal("1.00")


def test_the_median_ignores_a_single_frenzied_session():
    """Mean, not median, would let one block deal promote an illiquid name into
    a liquidity filter — and the measure exists to answer "can I get out on an
    ordinary day"."""
    steady = [bar("100", 100_000, i) for i in range(19)]
    spike = steady + [bar("100", 50_000_000, 19)]
    assert traded_value(spike) == traded_value(steady + [bar("100", 100_000, 19)])


def test_too_little_history_is_unmeasured_not_zero():
    """A newly listed symbol and an untradeable one are different things, and a
    filter that conflated them would silently hide every new listing."""
    assert traded_value([bar("100", 100_000, i) for i in range(LIQUIDITY_MIN_BARS - 1)]) is None
    assert in_crore(None) is None


def test_zero_volume_sessions_do_not_count_as_trading():
    """A halted or untraded session is absent data, not a ₹0 day; averaging it in
    would understate a liquid symbol that simply did not trade one day."""
    assert traded_value([bar("100", 0, i) for i in range(20)]) is None


def test_only_the_recent_window_is_measured():
    """Liquidity describes the present. A year of history would let long-dead
    activity vouch for a symbol that has since stopped trading."""
    old = [bar("100", 10_000_000, i) for i in range(40)]
    recent = [bar("100", 100_000, 40 + i) for i in range(LIQUIDITY_WINDOW_BARS)]
    assert traded_value(old + recent) == Decimal(10_000_000)


# --------------------------------------------------------------------------- #
# 2. Purity: the engine still cannot read candles
# --------------------------------------------------------------------------- #


def test_liquidity_is_passed_into_the_engine_not_fetched_by_it():
    """The screening engine has no market-data access by design, so the sweep
    measures liquidity and hands it down — the same shape as positions."""
    import ast

    tree = ast.parse(
        (REPO_ROOT / "src/athena/darvax/screening/engine.py").read_text(encoding="utf-8")
    )
    imported: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom):
            imported.append(node.module or "")
        elif isinstance(node, ast.Import):
            imported.extend(a.name for a in node.names)
    assert not [n for n in imported if "liquidity" in n or "store" in n], imported


def test_a_read_failure_on_one_symbol_does_not_cost_the_sweep():
    source = (
        REPO_ROOT / "src/athena/darvax/screening/sweep.py"
    ).read_text(encoding="utf-8")
    fn = source.split("def _liquidity_for")[1].split("\n    def ")[0]
    assert "except Exception" in fn
    assert "continue" in fn


# --------------------------------------------------------------------------- #
# 3. The filters
# --------------------------------------------------------------------------- #


@pytest.mark.parametrize("element_id", ["f-stop", "f-liq", "f-box", "f-clear", "filter-note"])
def test_filter_controls_exist(element_id: str):
    assert f'id="{element_id}"' in HTML


def test_there_is_no_market_cap_filter():
    """ATHENA holds no capitalisation data: no market_cap column, no share count,
    and a broker dump reporting last_price = 0 for every row. A control labelled
    "market cap" would therefore be filtering on something invented."""
    lowered = HTML.lower()
    for claim in ("market cap", "marketcap", "mcap"):
        assert claim not in lowered, f"page offers a {claim!r} filter it has no data for"


def test_unmeasured_liquidity_is_reported_not_silently_dropped():
    """Excluding a symbol because its liquidity is unknown is defensible;
    excluding it *silently* makes a new listing look illiquid."""
    fn = CODE.split("function applyFilters")[1].split("\n  function ")[0]
    assert "unmeasured++" in fn
    note = CODE.split("function renderFilterNote")[1].split("\n  function ")[0]
    assert "could not be measured" in note
    assert "not because they are illiquid" in note


def test_every_filter_reads_a_persisted_field():
    fn = CODE.split("function applyFilters")[1].split("\n  function ")[0]
    for field in ("stop_vs_ceiling", "liquidity_value", "box_height_pct"):
        assert field in fn, field


def test_the_filters_narrow_all_three_views_together():
    """All three views render the same rows, so a filter inside one of them would
    make "filtered" depend on which tab was open."""
    render = CODE.split("function renderScreen")[1].split("\n  function ")[0]
    assert "applyFilters" in render and "screen.visible" in render
    for fn_name in ("renderBuy", "renderLevels", "sortedRows"):
        body = CODE.split("function " + fn_name)[1].split("\n  function ")[0]
        assert "screen.visible" in body, f"{fn_name} ignores the filters"


def test_positions_are_never_filtered_out():
    """What you hold is not a discovery question. Hiding a holding because it
    failed a liquidity threshold would hide advice you need — including a sell."""
    fn = CODE.split("function renderPositions")[1].split("\n  function ")[0]
    assert "screen.visible" not in fn
    levels = CODE.split("function renderLevels")[1].split("\n  function ")[0]
    assert "screen.rows.forEach" in levels, "position lookups must use all rows"


def test_an_active_filter_is_visibly_active():
    """A narrowed list that looks unnarrowed reads as "nothing to trade today"."""
    assert "data-empty" in CODE
    assert 'select:not([data-empty="true"])' in CSS


def test_the_stop_filter_is_grounded_in_a_measurement():
    """Chosen first because it is the one distinction this project actually
    measured: 57% of entries carry a stop below their breakout level, and those
    are materially different trades from the 43% that do not."""
    # "above"/"below" are the contract the filter logic reads; the label wording
    # is presentation and is deliberately NOT pinned. It has now been reworded
    # twice, and each time a test pinning the prose failed for no reason that
    # mattered.
    assert 'value="above"' in HTML and 'value="below"' in HTML
    stop_select = HTML.split('id="f-stop"')[1].split("</select>")[0]
    assert "breakout" in stop_select, "the labels no longer name what is compared"


def test_filtering_visibly_changes_the_shortlist():
    """Caught in the browser: filtering 117 candidates down to 14 still rendered
    exactly 10 cards, because the shortlist cap is 10. Only the subtitle and the
    filter note changed, which reads as "the filter did nothing".

    A filtered list is narrowed by intent, so it earns a larger cap."""
    fn = CODE.split("function renderBuy")[1].split("\n  function ")[0]
    assert "anyFilterActive()" in fn, "the cap must respond to filtering"
    assert "BUY_SHORTLIST_FILTERED" in fn
    import re

    plain = int(re.search(r"BUY_SHORTLIST = (\d+)", CODE).group(1))
    filtered = int(re.search(r"BUY_SHORTLIST_FILTERED = (\d+)", CODE).group(1))
    assert filtered > plain


def test_the_shortlist_still_states_how_many_it_holds_back():
    fn = CODE.split("function renderBuy")[1].split("\n  function ")[0]
    assert "showing " in fn and " of " in fn


# --------------------------------------------------------------------------- #
# DX-10c: a filter that cannot apply must say so, not return nothing
# --------------------------------------------------------------------------- #


def test_liquidity_filter_is_disabled_when_the_sweep_recorded_none():
    """Measured on the owner's live database: all 17 sweeps predating DX-10a
    carry no liquidity, because it is computed at sweep time and their server
    had not restarted. Choosing a threshold on such a sweep emptied the list
    and reported "0 of 2191 match" — true, unhelpful, and indistinguishable
    from a market with nothing in it."""
    assert "function liquidityIsAbsentFromThisSweep" in CODE
    fn = CODE.split("function syncLiquidityControl")[1].split("\n  function ")[0]
    assert "S.fLiq.disabled" in fn, "the control is not disabled"
    assert 'S.fLiq.value = ""' in fn, (
        "a disabled select still submits its value, so a threshold chosen on an "
        "earlier sweep would keep filtering invisibly"
    )
    assert "not in this sweep" in fn, "the control does not say why it is off"


def test_the_disabled_liquidity_filter_explains_the_remedy():
    """The fix is a re-sweep, and the owner has no way to know that otherwise."""
    assert "Re-run" in CODE and "Screen universe" in CODE
    assert ".bar select[disabled]" in CSS, "a disabled filter must look disabled"


def test_absent_liquidity_is_never_reported_as_illiquid():
    """A gap in DarvaX's own measurement is not a finding about the instrument."""
    assert "not because they are illiquid" in CODE


def test_the_ui_says_stop_loss_not_stop() -> None:
    """The owner had to ask whether "Stop" meant stop-loss.

    That question is the clearest possible evidence the abbreviation was not
    carrying its meaning. Every label DarvaX writes for that price now says
    "stop-loss" in full. Engine-persisted prose is exempt: it arrives from the
    API as data, and ADR-005 forbids the UI from rewording it.
    """
    stop_select = HTML.split('id="f-stop"')[1].split("</select>")[0]
    for option in re.findall(r"<option[^>]*>([^<]+)</option>", stop_select):
        assert "stop-loss" in option.lower(), (
            f"filter option {option!r} still abbreviates stop-loss"
        )

    # The table column and the ladder row label.
    assert 'label: "Stop-loss"' in CODE
    assert CODE.count('label: "Stop"') == 0, "a bare \"Stop\" label survives"
    # A held position's own level, which is the one that protects real money.
    assert "Your stop-loss" in CODE
    assert "<dt>Your stop</dt>" not in CODE
    # The entry form, where the owner types one in.
    assert "Stop-loss (optional)" in HTML


def test_the_stop_filters_meaning_is_explained_outside_the_dropdown() -> None:
    """An option is a label; a label that has become a sentence is misplaced.

    The previous wording put the consequence in the option text ("Stop keeps
    part of the breakout") and the owner reported it as *more* confusing than
    the geometry it replaced. The fact belongs in the option, the meaning in the
    note below the bar where a full sentence fits.
    """
    assert "var STOP_FILTER_PLAIN" in CODE
    block = CODE.split("var STOP_FILTER_PLAIN")[1].split("};")[0]
    for key in ("above:", "below:"):
        assert key in block, f"no plain explanation for the {key!r} case"
    # Each explanation must say what happens if the stop-loss is actually hit —
    # that is the whole reason the distinction is worth filtering on.
    assert block.lower().count("if the stop-loss is hit") == 2
    assert "whole breakout is given up" in block, (
        "the below case does not state the consequence the engine measured"
    )

    # And it must be rendered, not merely defined.
    fn = CODE.split("function renderFilterNote")[1].split("\n  function ")[0]
    assert "STOP_FILTER_PLAIN[S.fStop.value]" in fn
    # Meaning before arithmetic: a count is only useful once you know what was
    # counted.
    assert fn.index("STOP_FILTER_PLAIN") < fn.index('" of " + total')


def test_every_filter_names_what_it_measures():
    """"Box: any" never said the percentages were box HEIGHT."""
    for select_id, expected in (
        ("f-box", "box height"),
        ("f-liq", "liquidity"),
        ("f-stop", "stop"),
    ):
        block = HTML.split(f'id="{select_id}"')[1].split("</select>")[0]
        first_option = block.split("<option")[1]
        assert expected in first_option.lower(), (
            f"{select_id}'s default option does not name what it filters on"
        )


def test_box_height_says_what_it_is_not_measured_from() -> None:
    """The owner asked whether box height was measured above the buy level.

    It is not, and no fixed relationship exists to fall back on: measured on a
    real sweep of 117 rows carrying both a box and a buy level, the buy level sat
    above the ceiling on 107 (91%) and INSIDE the box on 10 (9%). So the
    explanation has to state the negative explicitly rather than trust the reader
    to infer it.
    """
    assert "var BOX_FILTER_PLAIN" in CODE
    block = CODE.split("var BOX_FILTER_PLAIN")[1].split(";")[0]
    assert "not measured from your buy level" in block, (
        "the explanation does not rule out the reading the owner actually had"
    )
    assert "floor" in block and "ceiling" in block, "it never says what is measured"
    fn = CODE.split("function renderFilterNote")[1].split("\n  function ")[0]
    assert "BOX_FILTER_PLAIN" in fn, "defined but never rendered"


def test_the_filter_note_is_built_without_markup_assembly() -> None:
    """The note now carries prose, and prose invites innerHTML.

    Every line is a `textContent` on its own element, so a future explanation
    carrying a rupee symbol, a quote or a reason string cannot become injection.
    """
    fn = CODE.split("function renderFilterNote")[1].split("\n  function ")[0]
    assert "innerHTML" not in fn
    assert "createElement" in fn and "textContent" in fn


def test_explanations_are_separate_lines_not_a_joined_run() -> None:
    """Two sentences and a count joined by "·" is the wall of text this
    rewording exists to remove."""
    fn = CODE.split("function renderFilterNote")[1].split("\n  function ")[0]
    assert 'className = "fnwhat"' in fn and 'className = "fncount"' in fn
    assert ".filternote .fnwhat" in CSS and "display: block" in CSS
