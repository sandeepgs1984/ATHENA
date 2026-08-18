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
    fn = CODE.split("function levelChart")[1].split("\n  function ")[0]
    assert "Math.min.apply" in fn and "Math.max.apply" in fn


def test_risk_is_measured_from_the_current_price_not_the_trigger():
    """The stop is defined as 10% below the trigger, so risk measured to the
    trigger is the constant 10% — it printed identically on every card and told
    the reader nothing. Worse, price had already run past the trigger on every
    candidate, so it understated real exposure: BI showed 10% where buying that
    day risked 21.5%."""
    fn = CODE.split("function levelChart")[1].split("\n  function ")[0]
    assert "risk / now" in fn, "risk must be a fraction of the current price"
    assert "of entry" not in fn, "the constant 10% figure must be gone"
    assert "risk from here" in fn, "the note must say the risk is from today's price"


def test_the_zone_is_drawn_only_while_price_is_still_below_the_ceiling():
    """The zone is ground price has yet to take. Shading it for an instrument
    that already broke out covered up to 67% of the card (measured on XTRANET)
    with hatching that was largest exactly when it meant least."""
    fn = CODE.split("function levelChart")[1].split("\n  function ")[0]
    assert "lv-zone" in fn
    assert "now < top" in fn, "the zone must be conditional on price being under it"
    assert ".lv-zone" in CSS


def test_the_zone_caption_is_anchored_to_the_ceiling_that_defines_it():
    """At the bottom of the zone it landed on whichever level sat nearest the
    ceiling and read as that level's caption — on a real card it appeared to
    label the stop."""
    # Revision 2 drops the in-strip caption entirely — the strip is 34px wide
    # and a word does not fit — so the zone is explained by the rows beside it.
    assert ".lv-zone" in CSS


def test_the_figures_row_does_not_repeat_the_ladder():
    """Buy-above and stop are labelled lines a few pixels above, so printing
    them again put the same two numbers on one card twice and left risk/share
    competing with its own duplicates."""
    assert "riskRow" not in CODE, "the duplicate figures row is gone entirely"
    fn = CODE.split("function levelChart")[1].split("\n  function ")[0]
    assert "risk from here ₹" in fn


def test_level_hints_do_not_restate_the_level_name():
    levels = CODE.split("var LADDER_LEVELS")[1].split("];")[0]
    assert "top of the box" not in levels
    assert "bottom of the box" not in levels


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
    fn = CODE.split("function levelChart")[1].split("\n  function ")[0]
    assert "items.length < 2" in fn


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
    fn = CODE.split("function levelChart")[1].split("\n  function ")[0]
    assert "position.entry_price" in fn
    assert "position.stop_price" in fn
    assert "Your stop" in fn and "Your entry" in fn


def test_a_holdings_levels_are_styled_apart_from_the_methods():
    """The method's stop is prospective and moves with each screen; yours was
    frozen when you recorded the position. Same colour would let one read as the
    other."""
    assert ".lv-yourstop" in CSS
    assert ".lv-yourentry" in CSS


def test_prices_live_in_table_rows_so_they_cannot_collide():
    """Revision 1 drew price labels on the lines and nudged them apart when
    levels sat close. That detached each label from the line it named: with five
    levels inside a few percent (BI: now ₹76.81 against a ceiling of ₹75) you
    could not tell which label went with which line.

    Table rows are in normal flow, so collision is designed out rather than
    managed — and the nudging machinery is gone rather than left dormant."""
    assert "ltable" in CODE and "lt-price" in CODE
    assert "LABEL_MIN_GAP_PX" not in CODE, "the nudging mechanism must not linger"
    assert "translateY" not in CODE


def test_a_tick_ties_each_row_to_its_position_in_the_strip():
    """The table cannot show geometry and the strip cannot show numbers, so a
    colour-matched tick is what joins them."""
    fn = CODE.split("function levelChart")[1].split("\n  function ")[0]
    assert "ltick" in fn
    assert "lt-tick" in fn
    assert ".lstrip .ltick" in CSS


def test_the_distance_past_the_buy_level_shows_its_magnitude():
    """"above the buy level" without a number dropped the fact that explains the
    risk figure. BI sat 14.7% past its entry, which is precisely what turns the
    method's 10% stop into 21.5% of exposure for a buyer today — quoting the risk
    while hiding its cause leaves the reader unable to check it."""
    fn = CODE.split("function levelChart")[1].split("\n  function ")[0]
    assert "% above the buy level" in fn
    # Against the level, not against the current price. `distance_to_breakout_pct`
    # is a fraction of close, so rendering it as "X% above the buy level" gave
    # BI 12.8% where price was really 14.7% above ₹66.99 — a figure the reader
    # cannot reproduce from the two numbers on the card.
    assert "(now - ref) / ref" in fn, "the level must be the denominator"
    assert "distance_to_breakout_pct" not in fn.split("lv-now")[1][:400]


def test_the_risk_note_stays_on_one_line():
    """It wrapped, which made the stop row taller than its neighbours and broke
    the column scan the table design exists to provide."""
    fn = CODE.split("function levelChart")[1].split("\n  function ")[0]
    assert "if you buy now" not in fn
    assert "risk from here" in fn


def test_the_buy_ladder_list_is_capped_and_says_so():
    """A ladder is ~360px, so 116 of them was ~21,000px of scroll. The Advisor
    view caps its shortlist for the same reason; a silent cap would read as
    "these are all of them"."""
    assert "LEVELS_BUY_MAX" in CODE
    fn = CODE.split("function renderLevels")[1].split("\n  //")[0]
    assert "nearest " in fn and " of " in fn


def test_ladder_cards_are_wide_enough_for_their_notes():
    """Measured: at 330px the note column got 84px where the longest note needed
    170, so 153 rows wrapped and the column scan broke."""
    import re

    grid = CSS.split(".ladders {")[1].split("}")[0]
    width = int(re.search(r"minmax\((\d+)px", grid).group(1))
    assert width >= 400, f"{width}px leaves the note column too narrow"
