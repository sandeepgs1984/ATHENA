"""DX-8b: the plain advisor screen.

The DX-7c suite covers what must not regress — no "best" claim, badge from the
server, no advice derived in JS. These cover what DX-8b adds: plain vocabulary,
the trade ticket, and the fact that every control is actually wired to
something.
"""

from __future__ import annotations

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
        ("toggleDetail", "addEventListener"),
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
    """Darvas had none — he rode trends on a trailing stop."""
    for word in ("target_price", "take_profit", "profit target"):
        assert word not in CODE.lower(), f"invented {word!r}"


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
    toggle = CODE.split("S.toggleDetail.addEventListener")[1].split("});")[0]
    assert "detailedView.hidden" in toggle and "advisorView.hidden" in toggle


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
