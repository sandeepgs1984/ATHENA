"""DX-12b: a trend badge on the Advisor and Levels cards.

Continuation of DX-12a (50/100 EMA trend context, Table view + filter). This
milestone is pure presentation: the data (ema_50, ema_100) and the
classification logic (trendStateFor) already exist and already ship on the
Table's filter — this badge reuses both rather than adding a second
implementation that could disagree with the filter about what "above both
EMAs" means.

Scope, per the owner's instruction: Advisor cards and the Levels view only.
No backend change, no schema change, no influence on tier/action/eligibility.
"""

from __future__ import annotations

from pathlib import Path

from tests.darvax.test_dx4b_tab import _strip_js_comments

REPO_ROOT = Path(__file__).resolve().parents[2]
STATIC = REPO_ROOT / "src" / "athena" / "darvax" / "api" / "static"
HTML = (STATIC / "index.html").read_text(encoding="utf-8")
CSS = (STATIC / "darvax.css").read_text(encoding="utf-8")
JS = _strip_js_comments((STATIC / "darvax.js").read_text(encoding="utf-8"))


def _fn(name: str) -> str:
    """Slice one function's body out of the JS source by name."""
    start = JS.index(f"function {name}(")
    # Stop at the next top-level "function " declaration.
    end = JS.index("\n  function ", start + 1)
    return JS[start:end]


# --------------------------------------------------------------------------- #
# 1. Reuse, not a second classification
# --------------------------------------------------------------------------- #


def test_trend_chip_reuses_the_existing_classification_function():
    """trendStateFor already exists (DX-12a, powers the Table filter). This
    badge must call it, not reimplement the above/below/mixed logic a second
    time — two copies of this arithmetic could eventually disagree."""
    body = _fn("trendChip")
    assert "trendStateFor(row)" in body
    assert "row.ema_50" not in body and "row.ema_100" not in body, (
        "trendChip reads ema fields directly instead of going through "
        "trendStateFor — a second, possibly diverging classification"
    )


def test_trend_state_for_is_defined_exactly_once():
    assert JS.count("function trendStateFor(") == 1


# --------------------------------------------------------------------------- #
# 2. Absence is omitted, never rendered as a fourth state
# --------------------------------------------------------------------------- #


def test_chip_is_omitted_not_a_placeholder_when_trend_is_unmeasured():
    """A row with insufficient history for one or both EMAs must render no
    badge at all — never a dash, a "no reading" label, or any other
    manufactured state standing in for absence."""
    body = _fn("trendChip")
    assert 'if (state === null) return "";' in body


def test_three_states_are_covered_above_below_mixed():
    block = JS[JS.index("var TREND_CHIP = {") : JS.index("function trendChip")]
    for state in ("above:", "below:", "mixed:"):
        assert state in block


# --------------------------------------------------------------------------- #
# 3. Wired into all three card builders, right beside the action chip
# --------------------------------------------------------------------------- #


def test_buy_ticket_renders_the_trend_chip_beside_the_action_chip():
    body = _fn("buyTicket")
    assert "actionChip(row) + trendChip(row)" in body


def test_holding_ticket_renders_the_trend_chip_only_when_a_reading_exists():
    """A holding with no current screen row (row is falsy) must not call
    trendChip on a nonexistent row."""
    body = _fn("holdingTicket")
    assert "(row ? trendChip(row) : \"\")" in body


def test_ladder_card_renders_the_trend_chip_beside_the_action_chip():
    body = _fn("ladderCard")
    assert "actionChip(row) + trendChip(row)" in body


def test_ladder_card_does_not_touch_the_price_ladder_itself():
    """The whole point of placing the badge in the header rather than the
    ladder: zero risk of reintroducing the label-collision class of bug that
    redesigned the Levels view once already. Confirm levelChart's own body has
    no reference to trend."""
    chart_body = _fn("levelChart")
    assert "trend" not in chart_body.lower()


# --------------------------------------------------------------------------- #
# 4. Honesty: the tooltip discloses this is not a Darvas rule
# --------------------------------------------------------------------------- #


def test_every_trend_chip_tooltip_discloses_its_non_darvas_origin():
    block = JS[JS.index("var TREND_CHIP = {") : JS.index("function trendChip")]
    # Each of the three state objects must carry the disclosure.
    for state in ("above", "below", "mixed"):
        entry = block[block.index(state + ":") : block.index("}", block.index(state + ":")) + 1]
        assert "not one of darvas" in entry.lower()


# --------------------------------------------------------------------------- #
# 5. Visually distinct from the action chip, not a fourth .act variant
# --------------------------------------------------------------------------- #


def test_trend_chip_css_is_not_a_dot_act_variant():
    """The badge is context riding beside the recommendation, not a second
    recommendation. It must not share the .act selector or its filled-pill
    recipe (background + uppercase + letter-spacing)."""
    assert ".trendchip {" in CSS
    block = CSS[CSS.index(".trendchip {") : CSS.index("}", CSS.index(".trendchip {")) + 1]
    assert ".act" not in block
    assert "text-transform" not in block, "trend chip copies .act's uppercase treatment"


def test_trend_chip_states_use_distinct_tones():
    assert ".trendchip.t-above" in CSS
    assert ".trendchip.t-below" in CSS
    assert ".trendchip.t-mixed" in CSS
    above = CSS[CSS.index(".trendchip.t-above"): CSS.index(";", CSS.index(".trendchip.t-above"))]
    below = CSS[CSS.index(".trendchip.t-below"): CSS.index(";", CSS.index(".trendchip.t-below"))]
    assert above != below


# --------------------------------------------------------------------------- #
# 6. No backend, no classification, no eligibility surface touched
# --------------------------------------------------------------------------- #


def test_no_python_source_changed_for_this_milestone():
    """DX-12b is presentation-only: ema_50/ema_100 and the classification
    concept already existed and were already served (DX-12a). The module's
    own docstring correctly *discusses* tier/action in prose (explaining why
    trend must never influence them) — a substring ban would misfire on that
    prose, so this instead pins the exact public surface, which must contain
    no tier/action/eligibility name and must not have grown for this
    milestone."""
    import athena.darvax.screening.trend as trend_module

    public = {n for n in dir(trend_module) if not n.startswith("_")}
    assert public == {
        "Candle", "Decimal", "Sequence", "annotations", "dataclass",
        "latest_ema", "EMA_TREND_PERIOD_MEDIUM", "EMA_TREND_PERIOD_LONG",
        "TREND_LOOKBACK_BARS", "TrendReading", "trend_reading", "trend_state",
    }
    for forbidden in ("tier", "action", "eligib"):
        assert not any(forbidden in n.lower() for n in public), (
            f"trend.py's public surface now names something {forbidden!r} — "
            "trend must stay a passenger, never influence the classification"
        )


def test_guide_documents_where_the_badge_now_appears():
    marker = '<dt>50 EMA / 100 EMA</dt>'
    section = HTML[HTML.index(marker) : HTML.index("</dd>", HTML.index(marker))]
    assert "trend badge" in section.lower()
    assert "omitted" in section.lower()
