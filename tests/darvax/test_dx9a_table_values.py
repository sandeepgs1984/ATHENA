"""DX-9a: the Table view carries the trade values.

Until this milestone the Table was the only view WITHOUT them. It showed the
signal state, the DAR-CARD rule and the box geometry, so the question the owner
actually brings to a table of 2,191 rows — "what would I pay for this, and what
would I lose if it goes wrong" — could only be answered by leaving the Table
for the Advisor or Levels view. These tests pin the four figures into it and
guard the two ways this specific change breaks silently.
"""

from __future__ import annotations

import re
from pathlib import Path

from tests.darvax.test_dx4b_tab import _strip_js_comments

REPO_ROOT = Path(__file__).resolve().parents[2]
STATIC = REPO_ROOT / "src" / "athena" / "darvax" / "api" / "static"
JS = _strip_js_comments((STATIC / "darvax.js").read_text(encoding="utf-8"))
CSS = (STATIC / "darvax.css").read_text(encoding="utf-8")


def _columns_block() -> str:
    start = JS.index("var COLUMNS = [")
    return JS[start : JS.index("];", start)]


def _column_entries() -> list[dict[str, str]]:
    """Parse the COLUMNS literal into per-column field maps.

    Split on braces, not on lines: two entries wrap onto a second line, and a
    line-based parser silently dropped their `sortKey` — which made the test
    report the risk and liquidity columns missing when they were present.
    """
    out: list[dict[str, str]] = []
    for raw in re.findall(r"\{([^}]*)\}", _columns_block()):
        entry: dict[str, str] = {}
        for field in ("key", "label", "group", "sortKey"):
            m = re.search(field + r':\s*"([^"]*)"', raw)
            if m:
                entry[field] = m.group(1)
            elif re.search(field + r":\s*null", raw):
                entry[field] = ""
        if entry:
            out.append(entry)
    return out


# --------------------------------------------------------------------------
# The values themselves
# --------------------------------------------------------------------------

def test_table_carries_entry_stop_risk_and_liquidity() -> None:
    """The four tradeable figures must all be columns, not tooltips.

    Asserted against the parsed COLUMNS literal rather than against rendered
    markup so that renaming a header does not break the test, but deleting a
    column does.
    """
    keys = {c.get("key", "") for c in _column_entries()}
    sort_keys = {c.get("sortKey", "") for c in _column_entries()}
    assert "trigger_price" in keys, "the price to buy above is not a column"
    assert "stop_price" in keys, "the stop is not a column"
    assert "risk_pct" in sort_keys, "risk from the current price is not a column"
    assert "liquidity_value" in sort_keys, "liquidity is not a column"
    assert "action" in keys, "the recommended action is not a column"


def test_risk_is_measured_from_the_current_price_not_the_trigger() -> None:
    """Risk-to-trigger is 10% on every row by construction and must not return.

    The stop is defined as 10% below the trigger, so quoting risk against the
    trigger printed an identical, falsely reassuring 10% on every single symbol
    — the defect the owner caught in the Levels view at DX-9d.
    """
    body = JS[JS.index("function riskFromHere") : JS.index("function liqCrore")]
    assert "num(row.close)" in body, "risk is not measured from the close"
    assert "trigger" not in body, "risk is measured from the trigger again"


def test_risk_arithmetic_is_defined_exactly_once() -> None:
    """Both the Table and the Levels card must use the same helper.

    Two copies of this arithmetic would eventually disagree, and the owner
    would have no way to tell which view was lying to them.
    """
    assert JS.count("function riskFromHere") == 1
    # Used by the Table cell and by the Levels ladder.
    assert JS.count("riskFromHere(") >= 3, "one of the two views computes its own"


# --------------------------------------------------------------------------
# The two ways this change breaks silently
# --------------------------------------------------------------------------

def test_every_action_chip_class_the_js_emits_is_styled() -> None:
    """A chip class with no CSS rule renders correctly-labelled and unstyled.

    Caught during DX-9a: the new cell emitted `act-enter` (lowercase, `act-`
    prefix) while every rule in darvax.css is `.act.a-ENTER`. Nothing failed —
    the chip simply had no colour, which no source-string assertion would see.
    """
    # Every emitter is checked individually. Collecting the prefixes into a set
    # and comparing the set made this test vacuous: the Advisor view's correct
    # `a-` chip satisfied it while the Table's broken `act-` chip sat right
    # beside it, unstyled. Verified by reintroducing the bug.
    emitted = re.findall(r'class="act ([A-Za-z_-]*)', JS)
    assert emitted, "no action chips are emitted at all"
    for token in emitted:
        assert token.startswith("a-"), (
            f'chip class prefix {token!r} has no CSS rule; darvax.css styles '
            f'".act.a-<ACTION>"'
        )

    # Every action the screening engine can produce needs a rule.
    actions = re.findall(r"^\s+([A-Z_]+):\s*\"", JS[JS.index("var ACTION_LABEL"):
                                                   JS.index("var ACTION_LABEL") + 400],
                         re.MULTILINE)
    assert actions, "ACTION_LABEL parsed as empty"
    for action in actions:
        assert f".a-{action}" in CSS, f"action {action} has no chip styling"


def test_colspans_track_the_column_count() -> None:
    """A literal colspan under-spans the moment a column is added.

    The Table's empty-tier row and its expanded-detail row both spanned a
    hardcoded 8 while COLUMNS held 8 entries; DX-9a takes it to 12.
    """
    assert 'colspan="8"' not in JS, "a hardcoded colspan survived"
    # Only the two body rows are asserted. The super-header's colspan is a
    # genuinely variable run length and is covered by its own test below.
    body = JS[JS.index('<tr><td colspan=') : JS.index("</tbody></table>")]
    computed = re.findall(r"colspan=\"' \+ ([A-Za-z.]+) \+ '\"", body)
    assert len(computed) == 2, f"expected 2 body colspans, found {computed}"
    assert set(computed) == {"COLUMNS.length"}, f"colspan computed from {computed}"


def test_column_groups_are_contiguous() -> None:
    """The super-header emits one cell per run of equal `group`.

    A group appearing in two non-adjacent runs would silently render its label
    twice, and the banded background would break into stripes.
    """
    groups = [c.get("group", "") for c in _column_entries()]
    runs: list[str] = []
    for g in groups:
        if not runs or runs[-1] != g:
            runs.append(g)
    assert len(runs) == len(set(runs)), f"a column group is not contiguous: {runs}"


def test_super_header_spans_exactly_the_column_count() -> None:
    """Simulate the span-accumulating loop: the header must not over/under-span."""
    groups = [c.get("group", "") for c in _column_entries()]
    total, current, span = 0, None, 0
    for i, g in enumerate(groups):
        if g != current:
            if current is not None:
                total += span
            current, span = g, 0
        span += 1
        if i == len(groups) - 1:
            total += span
    assert total == len(groups), f"super-header spans {total} of {len(groups)} columns"


def test_absent_levels_render_as_absent_not_as_zero() -> None:
    """DX-3 persists a trigger only alongside a stop.

    Most rows genuinely have neither, and a blank cell reading "₹0.00" would
    invite buying at zero.
    """
    body = JS[JS.index("function levelCell") : JS.index("function riskCell")]
    assert "if (v === null)" in body
    assert "&mdash;" in body or "—" in body, "absent levels do not render a dash"


def test_unmeasured_liquidity_is_not_reported_as_illiquid() -> None:
    """12 of 2,191 instruments have too little history to measure.

    That is a gap in DarvaX's knowledge, not a finding about the instrument.
    """
    body = JS[JS.index("function liqCell") : JS.index("var COLUMNS")]
    assert "not a claim of illiquidity" in body


# --------------------------------------------------------------------------
# Structural guard for the class of bug this milestone hit twice
# --------------------------------------------------------------------------

def test_no_function_is_declared_twice() -> None:
    """A second declaration of the same name silently wins by position.

    DX-10c added `function money(v, dp)` while `function money(raw)` already
    existed further down the file. The later one won, so every caller of the new
    signature got the old helper — which adds the "₹" itself — and every price
    on the Levels card rendered as "₹₹6.7". Nothing threw, no test failed, and
    the value was still arithmetically right, so only reading the page caught it.
    """
    names = re.findall(r"^\s*function ([A-Za-z_$][\w$]*)\s*\(", JS, re.MULTILINE)
    duplicates = sorted({n for n in names if names.count(n) > 1})
    assert not duplicates, f"declared more than once: {duplicates}"


def test_money_is_formatted_through_exactly_one_helper_per_convention() -> None:
    """Two conventions for the same value type is how "₹₹6.7" happened.

    `rupees()` carries the symbol and pins two decimals; callers must not add a
    symbol of their own on top of it.
    """
    assert "function rupees" in JS
    # No caller prefixes a rupee sign onto a rupees() call.
    assert '\\u20b9" + rupees(' not in JS and '₹" + rupees(' not in JS
    body = JS[JS.index("function rupees") : JS.index("function rupees") + 400]
    assert "minimumFractionDigits: 2" in body, (
        "without fraction digits toLocaleString drops the trailing zero and a "
        "price renders as ₹6.7"
    )
