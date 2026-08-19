"""DX-8c: every honest state still reachable after the DX-8b restructure.

Restructuring a page around its states is how states get lost, and two were:
the skip report ended up inside "Detailed view", and the no-sweep message inside
the advisor view. Both rendered perfectly for anyone in the right mode and were
invisible in the other.

Ancestry is checked with a real parser. A regex over the markup got this wrong
during DX-8c — it reported elements as nested inside a container that had
already closed — and a structural test that cannot read structure is worse than
none, because it reports success.
"""

from __future__ import annotations

from html.parser import HTMLParser
from pathlib import Path

import pytest
from tests.darvax.test_dx4b_tab import _strip_js_comments

REPO_ROOT = Path(__file__).resolve().parents[2]
STATIC = REPO_ROOT / "src" / "athena" / "darvax" / "api" / "static"
HTML = (STATIC / "index.html").read_text(encoding="utf-8")
CODE = _strip_js_comments((STATIC / "darvax.js").read_text(encoding="utf-8"))

_VOID = {"br", "hr", "img", "input", "link", "meta", "source", "col"}


class _Ancestry(HTMLParser):
    """Record the open-element stack, by id, at each element with an id."""

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self._stack: list[str | None] = []
        self.ancestors: dict[str, list[str]] = {}

    def handle_starttag(self, tag, attrs):
        attr = dict(attrs)
        el_id = attr.get("id")
        if el_id:
            self.ancestors[el_id] = [a for a in self._stack if a]
        if tag not in _VOID and "/" not in (attr.get("__selfclosing__") or ""):
            self._stack.append(el_id)

    def handle_startendtag(self, tag, attrs):
        el_id = dict(attrs).get("id")
        if el_id:
            self.ancestors[el_id] = [a for a in self._stack if a]

    def handle_endtag(self, tag):
        if self._stack:
            self._stack.pop()


def _ancestry() -> dict[str, list[str]]:
    parser = _Ancestry()
    parser.feed(HTML)
    return parser.ancestors


ANCESTORS = _ancestry()


def test_the_parser_actually_reads_nesting():
    """Guards the guard. Every assertion below is worthless if ancestry is
    empty or flat, which is exactly how the regex version passed while being
    wrong."""
    assert "buy-tickets" in ANCESTORS
    assert "buy-zone" in ANCESTORS["buy-tickets"], ANCESTORS["buy-tickets"]
    assert "advisor-view" in ANCESTORS["buy-zone"]


# --------------------------------------------------------------------------- #
# 1. The two states the restructure hid
# --------------------------------------------------------------------------- #


def test_the_skip_report_is_not_buried_in_the_detailed_view():
    """DX-8b put `#skipped` inside `#detailed-view`, so a sweep that could not
    read an instrument said so **only** to someone who had opened the table.

    Skips are the "surface, never swallow" discipline: an instrument DarvaX
    could not evaluate is information the owner needs whichever view they are
    in, because it means the screen is quietly incomplete."""
    assert "skipped" in ANCESTORS
    assert "detailed-view" not in ANCESTORS["skipped"], (
        "the skip report must not require opening the detailed view"
    )


def test_the_no_sweep_message_is_not_confined_to_the_advisor_view():
    """Otherwise Detailed view with no sweep is a blank area with no
    explanation — which reads as broken rather than empty."""
    assert "screen-empty" in ANCESTORS
    assert "advisor-view" not in ANCESTORS["screen-empty"]


@pytest.mark.parametrize(
    "element_id",
    ["sweep-meta", "progress", "cancel-sweep", "screen-note", "screen-empty", "skipped"],
)
def test_state_reporting_lives_outside_both_views(element_id: str):
    """A state that only exists in one mode is a state the reader can miss.
    Everything that reports *what happened* belongs to the page; only the
    presentation of results is view-specific."""
    ancestors = ANCESTORS[element_id]
    assert "advisor-view" not in ancestors, f"{element_id} is advisor-only"
    assert "detailed-view" not in ancestors, f"{element_id} is detailed-only"


def test_only_results_are_view_specific():
    """The converse: the tier table belongs to the detailed view, the tickets to
    the advisor view. If these ever escaped, both would render at once."""
    assert "detailed-view" in ANCESTORS["tiers"]
    for el in ("buy-zone", "sell-group", "hold-group", "rest-line"):
        assert "advisor-view" in ANCESTORS[el], el


# --------------------------------------------------------------------------- #
# 2. States still wired
# --------------------------------------------------------------------------- #


@pytest.mark.parametrize(
    ("state", "marker"),
    [
        ("authoritative freshness", "payload.freshness"),
        ("integrity warnings", "freshness.warnings"),
        ("progress stage", "p-stage"),
        ("skip reasons", "skipped-list"),
    ],
)
def test_each_state_is_still_rendered_by_the_script(state: str, marker: str):
    assert marker in CODE, f"{state} is no longer rendered"


def test_a_cancelled_sweep_keeps_results_and_renders_server_warnings():
    """The API owns cancellation warnings; the browser keeps rendering rows."""
    render = CODE.split("function renderMeta")[1].split("\n  function ")[0]
    assert "freshness.warnings" in render
    assert "sweep.partial" not in render


def test_the_progress_bar_and_cancel_are_not_advisor_only():
    """DX-6d predicted these would become usable once the universe grew; a
    4-second sweep is now visible, so hiding them behind a view would matter."""
    for el in ("progress", "cancel-sweep"):
        assert "advisor-view" not in ANCESTORS[el]
        assert "detailed-view" not in ANCESTORS[el]


# --------------------------------------------------------------------------- #
# DX-10c: the sweep record and the rows can disagree in BOTH directions
# --------------------------------------------------------------------------- #


def test_a_count_smaller_than_the_rows_in_hand_is_never_quoted_as_the_count():
    """Measured on the owner's live database.

    Their most recent sweep has all 2,191 result rows persisted, but its sweep
    record still reads state="running", evaluated=0: the runner saves results
    first and the completion record second, so an auto-reload between those two
    writes leaves a finished sweep looking unstarted. The process that ran it
    still held the live figure in memory and showed 2,191; a fresh process reads
    the record and said "0 instrument(s) screened" above a table of 2,191 rows.
    """
    fn = CODE.split("function loadScreen")[1].split("\n  function ")[0]
    assert "evaluated < screen.rows.length" in fn, (
        "only the truncation direction is handled; the record can also "
        "under-report what was persisted"
    )
    assert "did not finish" in fn, "the page does not say the record is incomplete"
    # Both directions must mark the note as an error state, not a normal one.
    assert "truncated || incomplete" in fn


def test_the_page_never_states_a_count_it_cannot_support():
    """Whichever of the two figures is smaller, it must not be claimed as fact."""
    fn = CODE.split("function loadScreen")[1].split("\n  function ")[0]
    assert "incomplete ? screen.rows.length : evaluated" in fn
