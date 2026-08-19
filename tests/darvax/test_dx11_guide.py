"""DX-11: the in-app "How DarvaX works" guide.

Requested by the owner directly: "add world class ux reading guide about
darvax ... complete information ... each and every minute detail."

The risk with a hand-written reference document is not that it is wrong on day
one — it is that a threshold changes in config.py, a rule's wording changes in
signals/models.py, and the guide silently keeps saying the old thing, because
nothing connects English prose to the code it describes. Every numeric or
quoted claim asserted here is cross-checked against the same source the guide
claims to describe, so a drift fails a test rather than reaching the owner.
"""

from __future__ import annotations

import re
from pathlib import Path

from athena.darvax.config import (
    DarvaxBoxConfig,
    DarvaxBreakoutConfig,
    DarvaxSwingConfig,
)
from athena.darvax.signals.models import DAR_CARD_TEXT, DarvasRule
from athena.darvax.validation.summary import MIN_CLOSED_TRADES, MIN_TRADING_DAYS
from tests.darvax.test_dx4b_tab import _strip_js_comments

REPO_ROOT = Path(__file__).resolve().parents[2]
STATIC = REPO_ROOT / "src" / "athena" / "darvax" / "api" / "static"
HTML = (STATIC / "index.html").read_text(encoding="utf-8")
JS = _strip_js_comments((STATIC / "darvax.js").read_text(encoding="utf-8"))
CSS = (STATIC / "darvax.css").read_text(encoding="utf-8")
# Bounded to the dialog's own subtree — the Screener section that follows it
# in the DOM also has a <section id="..."> and would otherwise be swept in by
# a slice that ran to end-of-file.
GUIDE_HTML = HTML[
    HTML.index('<div id="guide-backdrop"') :
    HTML.index("<!-- ===================== Screener (DX-6c)")
]


def _unescape(text: str) -> str:
    return (
        text.replace("&ldquo;", "\u201c")
        .replace("&rdquo;", "\u201d")
        .replace("&mdash;", "\u2014")
        .replace("&rsquo;", "\u2019")
    )


def _normalize_ws(text: str) -> str:
    """Collapse the whitespace introduced by wrapping long quotes across
    multiple indented lines in the HTML source. A browser collapses this the
    same way when rendering; comparing raw source text without doing the same
    would fail on formatting that changes nothing a reader sees."""
    return re.sub(r"\s+", " ", text).strip()


# --------------------------------------------------------------------------- #
# 1. The four rule quotes must be VERBATIM, not paraphrased
# --------------------------------------------------------------------------- #


def test_every_dar_card_rule_is_quoted_verbatim() -> None:
    """The guide's quotes must match DAR_CARD_TEXT exactly, character for
    character. This is the one place in the whole page a direct quotation
    appears, so a paraphrase here is not a simplification — it is a
    misattribution to Darvas of words he did not write."""
    unescaped = _normalize_ws(_unescape(GUIDE_HTML))
    for rule in DarvasRule:
        text = _normalize_ws(DAR_CARD_TEXT[rule])
        assert text in unescaped, (
            f"rule {rule.value}'s guide quote does not match DAR_CARD_TEXT "
            f"verbatim: expected {text!r} to appear"
        )


def test_all_four_rules_are_present_not_a_subset() -> None:
    for rule in DarvasRule:
        assert f'<span class="rulechip"' in GUIDE_HTML
    # Every rule letter appears as its own chip content.
    for rule in DarvasRule:
        assert f">{rule.value}<" in GUIDE_HTML, f"rule {rule.value} chip missing"


# --------------------------------------------------------------------------- #
# 2. Every numeric claim must match its config default or code constant
# --------------------------------------------------------------------------- #


def test_box_confirmation_bars_matches_config_default() -> None:
    n = DarvaxBoxConfig().confirmation_bars
    assert f"<strong>{n}</strong>" in GUIDE_HTML or f"{n} bars" in GUIDE_HTML.replace(
        "<strong>", ""
    ).replace("</strong>", "")


def test_swing_threshold_matches_config_default() -> None:
    pct = DarvaxSwingConfig().threshold_pct
    assert f"{pct:g}%" in GUIDE_HTML.replace("<strong>", "").replace("</strong>", "")


def test_retest_tolerance_matches_config_default() -> None:
    pct = DarvaxBreakoutConfig().retest_tolerance_pct
    assert f"{pct:g}%" in GUIDE_HTML.replace("<strong>", "").replace("</strong>", "")


def test_sufficiency_gate_numbers_match_the_validation_module() -> None:
    """200 closed trades and 500 trading days are load-bearing constants — a
    change to either must be a deliberate edit here, not a silent mismatch."""
    plain = GUIDE_HTML.replace("<strong>", "").replace("</strong>", "")
    assert f"{MIN_CLOSED_TRADES} closed trades" in plain
    assert f"{MIN_TRADING_DAYS} trading days" in plain


def test_liquidity_window_matches_the_engine() -> None:
    from athena.darvax.screening.liquidity import (
        LIQUIDITY_MIN_BARS,
        LIQUIDITY_WINDOW_BARS,
    )

    plain = GUIDE_HTML.replace("<strong>", "").replace("</strong>", "")
    assert f"{LIQUIDITY_WINDOW_BARS} session" in plain
    assert str(LIQUIDITY_MIN_BARS) in GUIDE_HTML


def test_stop_percentages_match_the_methodology_config() -> None:
    from athena.darvax.config import DarvaxMethodologyConfig

    cfg = DarvaxMethodologyConfig()
    plain = GUIDE_HTML.replace("<strong>", "").replace("</strong>", "")
    assert f"{cfg.canonical_stop_pct:g}%" in plain
    assert f"{cfg.tight_stop_pct:g}%" in plain


# --------------------------------------------------------------------------- #
# 3. Every action the engine can emit is documented
# --------------------------------------------------------------------------- #


def test_every_darvax_action_appears_in_the_actions_table() -> None:
    from athena.darvax.screening.models import DarvaxAction

    for action in DarvaxAction:
        assert f'class="act a-{action.value}"' in GUIDE_HTML, (
            f"action {action.value} is not documented in the guide's actions table"
        )


# --------------------------------------------------------------------------- #
# 4. Interaction: open, close, focus, escape — behaviour, not just markup
# --------------------------------------------------------------------------- #


def test_guide_starts_hidden_and_is_reachable_from_the_header() -> None:
    assert 'id="guide" class="guide"' in HTML
    assert 'hidden>' in GUIDE_HTML.split("guide-content", 1)[0] or "hidden" in HTML.split(
        'id="guide"'
    )[1].split(">")[0]
    assert 'id="guide-open"' in HTML


def test_guide_open_close_and_backdrop_are_all_wired() -> None:
    assert "S.guideOpen.addEventListener" in JS
    assert "S.guideClose.addEventListener" in JS
    assert "S.guideBackdrop.addEventListener" in JS


def test_escape_closes_the_guide() -> None:
    fn = JS.split("function onGuideKeydown")[1].split("\n  function ")[0]
    assert 'e.key === "Escape"' in fn
    assert "closeGuide" in fn


def test_focus_moves_into_the_dialog_and_returns_to_the_opener() -> None:
    """A dialog that traps focus visually but not for a keyboard user is not
    actually a dialog. Opening must move focus in; closing must give it back
    to whatever the owner was doing, not drop it on <body>."""
    open_fn = JS.split("function openGuide")[1].split("\n  function ")[0]
    assert "guideOpenerEl = document.activeElement" in open_fn
    assert "S.guide.focus()" in open_fn

    close_fn = JS.split("function closeGuide")[1].split("\n  function ")[0]
    assert "guideOpenerEl" in close_fn and ".focus()" in close_fn


def test_dialog_element_is_actually_focusable() -> None:
    """S.guide.focus() on a plain <div> with no tabindex is a silent no-op —
    the DOM does not error, it just does not move focus. Caught by reading the
    markup, not by any exception."""
    guide_tag = HTML[HTML.index('<div id="guide"') : HTML.index(">", HTML.index('<div id="guide"'))]
    assert 'tabindex="-1"' in guide_tag


def test_dialog_has_the_accessible_dialog_contract() -> None:
    guide_tag = HTML[HTML.index('<div id="guide"') : HTML.index(">", HTML.index('<div id="guide"'))]
    assert 'role="dialog"' in guide_tag
    assert 'aria-modal="true"' in guide_tag
    assert 'aria-labelledby="guide-title"' in guide_tag
    assert 'id="guide-title"' in GUIDE_HTML


# --------------------------------------------------------------------------- #
# 5. Structural: TOC actually points at sections that exist
# --------------------------------------------------------------------------- #


def test_every_toc_link_targets_a_section_that_exists() -> None:
    import re

    toc = GUIDE_HTML[GUIDE_HTML.index('class="guide-toc"') : GUIDE_HTML.index("guide-content")]
    hrefs = re.findall(r'href="#([\w-]+)"', toc)
    assert len(hrefs) >= 10, "the guide has far fewer sections than the content implies"
    for anchor in hrefs:
        assert f'id="{anchor}"' in GUIDE_HTML, f"TOC links to #{anchor}, which does not exist"


def test_every_section_has_a_toc_entry() -> None:
    """The inverse of the check above: a section with no TOC link is
    undiscoverable in a panel long enough to need one."""
    import re

    content = GUIDE_HTML[GUIDE_HTML.index("guide-content") :]
    section_ids = re.findall(r'<section id="([\w-]+)"', content)
    toc = GUIDE_HTML[GUIDE_HTML.index('class="guide-toc"') : GUIDE_HTML.index("guide-content")]
    for sid in section_ids:
        assert f'#{sid}"' in toc, f"section #{sid} has no TOC entry"


# --------------------------------------------------------------------------- #
# 6. Content honesty: the guide must not contradict standing invariants
# --------------------------------------------------------------------------- #


def test_the_guide_repeats_the_no_target_and_no_order_invariants() -> None:
    plain = _unescape(GUIDE_HTML)
    assert "no order" in plain.lower() or "never place" in plain.lower()
    assert "target" in plain.lower()  # discusses the absence of one
    assert "profit target" in plain.lower()


def test_the_guide_carries_the_experimental_badge() -> None:
    assert "EXPERIMENTAL" in GUIDE_HTML and "UNVALIDATED" in GUIDE_HTML


def test_the_svg_diagram_has_an_accessible_title() -> None:
    fig = GUIDE_HTML[GUIDE_HTML.index("<svg") : GUIDE_HTML.index("</svg>")]
    assert "role=\"img\"" in fig
    assert "<title" in fig
