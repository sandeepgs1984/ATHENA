"""DX-8b: the plain advisor screen.

The DX-7c suite covers what must not regress — no "best" claim, badge from the
server, no advice derived in JS. These cover what DX-8b adds: plain vocabulary,
the trade ticket, and the fact that every control is actually wired to
something.
"""

from __future__ import annotations

import re

from pathlib import Path

import pytest

from tests.darvax.test_dx4b_tab import _strip_js_comments

REPO_ROOT = Path(__file__).resolve().parents[2]
STATIC = REPO_ROOT / "src" / "athena" / "darvax" / "api" / "static"
HTML = (STATIC / "index.html").read_text(encoding="utf-8")
JS = (STATIC / "darvax.js").read_text(encoding="utf-8")
CSS = (STATIC / "darvax.css").read_text(encoding="utf-8")
CODE = _strip_js_comments(JS)
FLAT_HTML = " ".join(HTML.split())


# --------------------------------------------------------------------------- #
# 1. Every control is wired
# --------------------------------------------------------------------------- #


@pytest.mark.parametrize(
    ("element", "handler"),
    [
        ("posAddToggle", "addEventListener"),
        ("posForm", "addEventListener"),
        ("pfCancel", "addEventListener"),
        ("sellTickets", "addEventListener"),
        ("holdTickets", "addEventListener"),
        ("modeAdvisor", "addEventListener"),
        ("modeLevels", "addEventListener"),
        ("modeTable", "addEventListener"),
    ],
)
def test_every_interactive_element_has_a_listener(element: str, handler: str):
    """Restructuring the markup at DX-8b removed the handlers along with the
    elements they were bound to: the form and both row buttons rendered
    perfectly and did nothing at all. Only one test noticed, and only
    incidentally — a screen can look complete and be inert."""
    assert f"S.{element}.{handler}" in CODE, f"{element} has no listener"


def test_no_selector_points_at_markup_that_no_longer_exists():
    """`getElementById` returns null silently, so a stale selector is a handler
    that never fires and never errors. Every id the script looks up must exist
    in the page."""
    import re

    missing = [
        el_id
        for el_id in re.findall(r'getElementById\("([^"]+)"\)', CODE)
        if f'id="{el_id}"' not in HTML
    ]
    assert missing == [], f"script looks up ids the page does not define: {missing}"


# --------------------------------------------------------------------------- #
# 2. Plain vocabulary
# --------------------------------------------------------------------------- #


def test_actions_read_as_trading_words():
    labels = CODE.split("var ACTION_LABEL")[1].split("};")[0]
    for word in ('"Buy"', '"Sell"', '"Hold"', '"Wait"', '"Skip"'):
        assert word in labels, f"missing plain label {word}"


def test_the_word_through_is_replaced_with_plain_english():
    """"through" was on the shipped screen. It means price is already past the
    level — good news — and reads like an error."""
    assert "already above the buy level" in CODE
    words = CODE.split("function distanceWords")[1].split("\n  function ")[0]
    assert '"through"' not in words


def test_the_plain_sentence_leads_and_the_technical_one_is_disclosed():
    """DX-8a persists both registers; the page must lead with the plain one and
    keep the methodology reachable rather than deleting it."""
    ticket = CODE.split("function buyTicket")[1].split("\n  function ")[0]
    assert "action_reason_plain" in ticket
    method = CODE.split("function methodologyDetails")[1].split("\n  function ")[0]
    assert "action_reason" in method and "explanation" in method
    assert "<details" in method, "the methodology must be collapsed, not removed"


# --------------------------------------------------------------------------- #
# 3. The trade ticket
# --------------------------------------------------------------------------- #


def test_a_buy_ticket_shows_entry_stop_and_risk():
    """The gap DX-8a fixed in the data must actually reach the screen: an entry
    without a stop is half a trade."""
    ticket = CODE.split("function buyTicket")[1].split("\n  function ")[0]
    assert "Buy above" in ticket
    assert "Stop loss" in ticket
    assert "stop_price" in ticket
    assert "riskLine" in ticket


def test_risk_per_share_is_subtraction_not_a_new_rule():
    risk = CODE.split("function riskLine")[1].split("\n  function ")[0]
    assert "trigger_price" in risk and "stop_price" in risk
    assert "buy - stop" in risk


def test_no_position_sizing_leaks_in():
    """Decision 3a: risk per share only. How many shares to buy is ATHENA's
    sizing/ concern and ADR-010 keeps DarvaX out of it."""
    for word in ("capital", "position_size", "shares_to_buy", "allocation"):
        assert word not in CODE.lower(), f"sizing concept {word!r} appeared"


def test_no_profit_target_is_invented():
    """Darvas had none — he rode trends on a trailing stop.

    Tightened at DX-10c. The original version banned the *substring* "profit
    target", which fired on the R-multiple label whose whole job is to say the
    method has no profit target. A keyword ban cannot tell an invention from a
    denial of one, so this now checks the two things that actually constitute
    inventing a target: a field that stores one, and prose that offers one.
    """
    # 1. No field, property or payload key holding a target price.
    for token in ("target_price", "take_profit", "targetPrice", "profit_target"):
        assert token not in CODE, f"invented a {token!r} field"

    # 2. Where the phrase appears at all, it must be negated. A future
    #    "Profit target: ₹X" would have no negator in front of it.
    for match in re.finditer(r"profit target", CODE, re.IGNORECASE):
        window = CODE[max(0, match.start() - 60) : match.start()].lower()
        assert any(neg in window for neg in ("no ", "not ", "never", "without")), (
            f"'profit target' used without negation near: "
            f"{CODE[match.start() - 40 : match.end() + 20]!r}"
        )


def test_the_r_multiple_scale_denies_being_a_target():
    """DX-10c's answer to the owner's target request.

    R-multiples are only defensible while they are explicitly labelled as a
    measurement of the risk the method defines rather than a forecast. Strip
    that label and they become the invented target this suite exists to stop.
    """
    if "function rLine" not in CODE:
        pytest.skip("R-multiple line not present")
    fn = CODE.split("function rLine")[1].split("\n  function ")[0]
    assert "not targets" in fn.lower(), "the R scale does not deny being a target"
    # R must be the method's own quantity: buy level minus stop.
    helper = CODE.split("function rMultiples")[1].split("\n  function ")[0]
    assert "trigger - stop" in helper, "R is not the method's buy-level-minus-stop"


# --------------------------------------------------------------------------- #
# 4. Layout
# --------------------------------------------------------------------------- #


def test_sell_is_grouped_before_hold():
    """Selling is the only time-critical thing on the page."""
    assert FLAT_HTML.index('id="sell-group"') < FLAT_HTML.index('id="hold-group"')


def test_holdings_are_grouped_by_the_engines_action():
    grouped = CODE.split("function renderPositions")[1].split("\n  function ")[0]
    assert 'row.action === "EXIT"' in grouped
    assert "signal_type" not in grouped, "grouping must not re-read the signal state"


def test_the_detailed_table_is_reachable_not_deleted():
    """Decision 2a. The DX-6c table keeps its sorting, filtering and the full
    universe; it just stops being the first thing you see."""
    assert 'id="detailed-view"' in HTML
    assert 'id="tiers"' in HTML
    assert "renderTiers" in CODE
    # DX-9d replaced the two-state toggle with a three-way mode switch, so the
    # assertion moved from "the toggle flips two things" to "exactly one view is
    # visible per mode" — which is the property that actually matters.
    mode = CODE.split("function setMode")[1].split("\n  S.modeAdvisor")[0]
    for view in ("advisorView", "levelsView", "detailedView"):
        assert f"S.{view}.hidden = mode !==" in mode, view


def test_the_long_tail_collapses_to_one_line():
    """2,000 rows with nothing to say is the density complaint in one number."""
    rest = CODE.split("function renderRest")[1].split("\n  function ")[0]
    assert "nothing to act on today" in rest


def test_risk_is_formatted_as_money_with_two_decimals():
    """Caught in the browser: risk per share rendered "₹6.7". The value was
    computed to two decimals and then passed through a helper that re-parses to
    a Number, where toLocaleString drops the trailing zero. Money with one
    decimal place looks like a bug in a trading screen."""
    risk = CODE.split("function riskLine")[1].split("\n  function ")[0]
    assert "minimumFractionDigits: 2" in risk
    assert "money(String(risk" not in risk


def test_every_element_the_script_uses_is_actually_looked_up():
    """The bug this exists for: DX-10b added filter controls and event listeners
    but the selectors never reached the `S` object, because a string replacement
    silently missed an anchor that had no trailing comma. `S.fStop` was therefore
    `undefined`, `S.fStop.addEventListener` threw at init, and the whole IIFE
    aborted — so the page rendered its static HTML and nothing else. No sweep
    line, no empty state, no positions: a blank screen with working dropdowns.

    Every prior test passed, because they asserted that strings appeared in the
    source rather than that the references resolved. This is the direction that
    was missing: `S.<name>` used somewhere but never assigned.

    The companion test `test_no_selector_points_at_markup_that_no_longer_exists`
    covers the opposite direction — a selector for markup that has gone."""
    import re

    block = JS.split("var S = {", 1)[1].split("\n  };", 1)[0]
    defined = set(re.findall(r"(\w+):\s*document\.getElementById", block))
    used = set(re.findall(r"\bS\.(\w+)\b", CODE))
    missing = sorted(used - defined)
    assert missing == [], (
        f"script uses S.{{{', '.join(missing)}}} but never looks them up — "
        "a TypeError at init aborts the entire script"
    )
