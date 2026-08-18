"""DX-9c/d: the stop-versus-ceiling comparison, and the Levels view.

The comparison is the point of the whole track. The same 10% rule lands above
the breakout level for one instrument and below it for another — measured on a
real sweep, 50 above and 65 below — which is a materially different trade that
DarvaX previously had no way to tell apart.
"""

from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal
from pathlib import Path

import pytest

from athena.darvax.screening.engine import screen_signal, stop_vs_ceiling
from athena.darvax.signals.models import (
    DarvasRule,
    DarvaxSignal,
    DarvaxSignalType,
    DarvaxStop,
    StopBasis,
)
from athena.darvax.store.repository import DarvaxRepository
from tests.darvax.test_dx4b_tab import _strip_js_comments

REPO_ROOT = Path(__file__).resolve().parents[2]
STATIC = REPO_ROOT / "src" / "athena" / "darvax" / "api" / "static"
HTML = (STATIC / "index.html").read_text(encoding="utf-8")
CSS = (STATIC / "darvax.css").read_text(encoding="utf-8")
CODE = _strip_js_comments((STATIC / "darvax.js").read_text(encoding="utf-8"))
AS_OF = datetime(2026, 8, 17, tzinfo=timezone.utc)


def signal(*, stop=None, box_top="105", state=DarvaxSignalType.BREAKOUT):
    return DarvaxSignal(
        signal_id="s", instrument_id="NSE:X", as_of=AS_OF, signal_type=state,
        darvas_rule=DarvasRule.B_BUY_ABOVE_TOPMOST_BOX, close=Decimal("100"),
        box_top=Decimal(box_top) if box_top else None, box_bottom=Decimal("90"),
        trigger_price=Decimal("101"),
        stop=(
            DarvaxStop(basis=StopBasis.CANONICAL_DARVAS_PCT, price=Decimal(stop),
                       reference_price=Decimal("110"), detail="d", pct=Decimal("10"))
            if stop else None
        ),
        explanation="e", evidence={}, methodology_digest="d", darvax_version="t",
    )


# --------------------------------------------------------------------------- #
# 1. The comparison (DX-9c)
# --------------------------------------------------------------------------- #


def test_a_stop_above_the_breakout_level_is_reported_as_such():
    delta, note = stop_vs_ceiling(signal(stop="141.30", box_top="136.9"))
    assert delta == Decimal("4.40")
    assert "above" in note and "4.40" in note


def test_a_stop_below_it_says_the_breakout_would_be_given_back():
    """The consequence a trader needs: a stop-out below the breakout level
    surrenders the entire move that triggered the entry."""
    delta, note = stop_vs_ceiling(signal(stop="60.29", box_top="75"))
    assert delta == Decimal("-14.71")
    assert "below" in note
    assert "give back the whole breakout" in note


def test_a_stop_exactly_at_the_level_is_neither():
    delta, note = stop_vs_ceiling(signal(stop="105", box_top="105"))
    assert delta == 0
    assert "exactly" in note


def test_the_comparison_is_absent_when_either_level_is_absent():
    """Only 115 of 2,191 rows on a real sweep have both. There is no stop for a
    trade nobody is in, and inventing one would be worse than a blank."""
    assert stop_vs_ceiling(signal(stop=None)) == (None, "")
    assert stop_vs_ceiling(signal(stop="90", box_top=None)) == (None, "")


def test_the_comparison_attaches_no_judgement():
    """It states where the stop landed. Whether that is acceptable is the
    owner's call, and DX-5 gives DarvaX no standing to opine."""
    for stop, top in (("141.30", "136.9"), ("60.29", "75"), ("105", "105")):
        _, note = stop_vs_ceiling(signal(stop=stop, box_top=top))
        low = note.lower()
        for verdict in ("good", "bad", "risky", "safe", "better", "worse", "prefer"):
            assert verdict not in low, f"{note!r} contains a judgement"


def test_screening_persists_the_comparison():
    result = screen_signal(signal(stop="94.5"), sweep_id="s")
    assert result.stop_vs_ceiling is not None
    assert result.stop_vs_ceiling_note


def test_it_round_trips(tmp_path: Path):
    store = DarvaxRepository(tmp_path / "d.db")
    store.initialize()
    original = screen_signal(signal(stop="94.5"), sweep_id="s")
    store.save_screen_results([original])
    back = store.list_screen_results("s")[0]
    assert back.stop_vs_ceiling == original.stop_vs_ceiling
    assert back.stop_vs_ceiling_note == original.stop_vs_ceiling_note
    store.close()


# --------------------------------------------------------------------------- #
# 2. The Levels view (DX-9d)
# --------------------------------------------------------------------------- #


@pytest.mark.parametrize(
    "element_id",
    ["levels-view", "lv-positions", "lv-buy", "lv-approaching",
     "lv-buy-ladders", "lv-appr-ladders", "lv-pos-ladders", "lv-note",
     "mode-advisor", "mode-levels", "mode-table"],
)
def test_required_containers_exist(element_id: str):
    assert f'id="{element_id}"' in HTML


def test_exactly_one_view_is_visible_per_mode():
    mode = CODE.split("function setMode")[1].split("\n  S.modeAdvisor")[0]
    for view in ("advisorView", "levelsView", "detailedView"):
        assert f"S.{view}.hidden = mode !==" in mode, view


def test_the_ladder_reads_the_persisted_comparison_rather_than_deriving_it():
    """It is the one line on the card that says something non-obvious, so it is
    exactly the line ADR-005 must keep with the engine."""
    card = CODE.split("function ladderCard")[1].split("\n  var LEVELS_APPROACHING")[0]
    assert "stop_vs_ceiling_note" in card
    assert "box_top" not in card, "the card must not recompute the comparison"


def test_every_ladder_level_is_a_persisted_field():
    levels = CODE.split("var LADDER_LEVELS")[1].split("];")[0]
    for key in ("trigger_price", "stop_price", "box_top", "box_bottom"):
        assert key in levels, key


def test_the_ladder_scale_is_per_card():
    """Prices on one sweep span ₹74 to ₹23,500; a shared axis would render most
    ladders as a flat line."""
    fn = CODE.split("function ladder(")[1].split("\n  function ")[0]
    assert "Math.min.apply" in fn and "Math.max.apply" in fn


def test_the_breakout_zone_is_drawn():
    fn = CODE.split("function ladder(")[1].split("\n  function ")[0]
    assert "lv-zone" in fn
    assert "breakout zone" in fn
    assert ".lv-zone" in CSS


def test_rows_without_levels_are_excluded_not_faked():
    """1,557 NO_ENTRY instruments have no box to draw. Showing an empty ladder
    for each would be 1,557 cards saying nothing."""
    fn = CODE.split("function renderLevels")[1].split("\n  //")[0]
    assert 'r.action === "NO_ENTRY"' in fn
    assert "no box to draw" in fn


def test_watch_rows_are_capped_and_the_cap_is_stated():
    """A silent cap reads as "these are all of them"."""
    assert "LEVELS_APPROACHING" in CODE
    fn = CODE.split("function renderLevels")[1].split("\n  //")[0]
    assert "nearest " in fn and " of " in fn


def test_a_ladder_degrades_when_there_are_too_few_levels():
    fn = CODE.split("function ladder(")[1].split("\n  function ")[0]
    assert "present.length < 2" in fn


def test_no_charting_library_is_introduced():
    """ADR-004. Four horizontal lines and a band do not need one."""
    for marker in ("chart.js", "d3", "highcharts", "plotly", "canvas"):
        assert marker not in CODE.lower(), marker


def test_colour_marks_the_kind_of_level_not_its_quality():
    """Design §7.5. A prettier screen must not become a more confident one, and
    DX-5 gives no basis for grading candidates."""
    for banned in ("lv-good", "lv-bad", "lv-strong", "lv-weak", "lv-score"):
        assert banned not in CSS, banned


def test_no_target_line_is_invented():
    fn = CODE.split("var LADDER_LEVELS")[1].split("];")[0]
    for banned in ("target", "take_profit"):
        assert banned not in fn.lower(), banned


def test_a_holdings_own_entry_and_stop_are_drawn_on_its_ladder():
    """Caught in the browser: a held card showed only ceiling/now/floor. The
    level actually protecting the position — the stop recorded with it — appeared
    as a line of text under the chart and not on it, which is precisely backwards
    for the one card where it matters most."""
    fn = CODE.split("function ladder(")[1].split("\n  function ")[0]
    assert "position.entry_price" in fn
    assert "position.stop_price" in fn
    assert "Your stop" in fn and "Your entry" in fn


def test_a_holdings_levels_are_styled_apart_from_the_methods():
    """The method's stop is prospective and moves with each screen; yours was
    frozen when you recorded the position. Same colour would let one read as the
    other."""
    assert ".lv-yourstop" in CSS
    assert ".lv-yourentry" in CSS


def test_label_de_collision_keeps_the_line_at_its_true_price():
    """Two levels 0.4% apart put their labels on top of each other. The label is
    nudged and the line is not — moving the line would make the chart lie."""
    fn = CODE.split("function ladder(")[1].split("\n  function ")[0]
    assert "lv-tag" in fn, "the label must be a separate element from the line"
    assert "translateY" in fn
    assert 'style="top:\' + truePct' in fn, "the line stays at the true position"


def test_the_minimum_label_gap_exceeds_the_label_height():
    """The gap is between label *tops*, so a value below the label height still
    overlaps. Measured at 14.7–15.5px in the browser; 14 left 16 of 488 pairs
    overlapping, which is why this is asserted rather than eyeballed."""
    import re

    gap = int(re.search(r"LABEL_MIN_GAP_PX = (\d+)", CODE).group(1))
    assert gap >= 17, f"min label gap {gap}px is under the measured label height"
