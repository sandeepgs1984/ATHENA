"""DX-6c: the screener UI.

Asset tests here are structural — they pin the contract between the API and the
page (field names, required states, the things that must never be conditional).
The *behavioural* verification was done by driving the real page in a browser
against a 528-instrument sweep on a copy of the owner's ledger, and is recorded
in the DX-6c review summary; a headless DOM stub would have proved less.

What these tests are actually for is regression: they fail if someone removes
the experimental banner, hides a required state, introduces a conviction score,
or renames an API field the page reads.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from tests.api.v1.test_core_apis import get_auth_headers

from athena.api.app import create_app
from athena.api.config import APISettings
from athena.api.darvax_mount import DARVAX_MOUNT_PATH, mount_darvax_if_enabled
from athena.api.security.models import Role
from athena.darvax.config import DarvaxConfig, methodology_digest

REPO_ROOT = Path(__file__).resolve().parents[2]
STATIC = REPO_ROOT / "src" / "athena" / "darvax" / "api" / "static"
HTML = (STATIC / "index.html").read_text(encoding="utf-8")
JS = (STATIC / "darvax.js").read_text(encoding="utf-8")
CSS = (STATIC / "darvax.css").read_text(encoding="utf-8")

#: Source with comments removed. Any "this file must not contain X" assertion
#: has to run against *code*: the comments here legitimately discuss the very
#: things the code avoids (a conviction score, `toISOString`), and matching them
#: fails the test for exactly the documentation that explains the correct
#: behaviour. Reuses the DX-4b stripper rather than growing a second copy.
from tests.darvax.test_dx4b_tab import _strip_js_comments  # noqa: E402

JS_CODE = _strip_js_comments(JS)

pytestmark = pytest.mark.usefixtures("athena_config_darvax_disabled")


# --------------------------------------------------------------------------- #
# 1. The experimental label is unconditional
# --------------------------------------------------------------------------- #


def test_banner_is_present_and_never_conditionally_hidden():
    """The label is a correctness requirement, not decoration. No view — not
    embedded mode, not the screener — may hide it."""
    assert 'class="banner"' in HTML
    assert "EXPERIMENTAL" in HTML
    for forbidden in (
        'querySelector(".banner")',
        "querySelector('.banner')",
        "banner.remove()",
        "banner.hidden",
    ):
        assert forbidden not in JS_CODE, f"darvax.js manipulates the banner: {forbidden}"


def test_the_footer_states_that_eligibility_is_not_a_score():
    assert "not a score" in HTML
    assert "no conviction index" in HTML


# --------------------------------------------------------------------------- #
# 2. No conviction score anywhere in the UI either
# --------------------------------------------------------------------------- #


def test_the_page_never_invents_a_score():
    """ADR-010 Amendment 2's central commitment, guarded on the presentation
    layer too — a UI-side composite would defeat the engine-side rule."""
    lowered = JS_CODE.lower()
    for banned in ("conviction", "confidence score", "darvax score", "grade:", "rating"):
        assert banned not in lowered, f"the UI introduces {banned!r}"
    # The HTML may *say* there is no conviction index — that disclaimer is
    # required — but must not carry a column or field for one.
    assert "no conviction index" in HTML
    assert 'id="score"' not in HTML


# --------------------------------------------------------------------------- #
# 3. Every required state from the design exists
# --------------------------------------------------------------------------- #


@pytest.mark.parametrize(
    "element_id",
    [
        "screen-empty",     # no sweep yet
        "progress",         # sweep running
        "cancel-sweep",     # cancellable
        "skipped",          # skips surfaced, never swallowed
        "sweep-meta",       # freshness / digest flags live here
        "tiers",
        "filter",
        "toggle-other",
    ],
)
def test_required_state_containers_exist(element_id: str):
    assert f'id="{element_id}"' in HTML, f"missing required element #{element_id}"


def test_partial_stale_and_digest_mismatch_states_are_implemented():
    """Three states that are easy to omit and misleading to omit."""
    assert "sweep.partial" in JS_CODE
    assert "not the latest session" in JS_CODE
    assert "methodology changed since this sweep" in JS_CODE


def test_freshness_uses_local_date_not_utc():
    """Regression guard: `toISOString()` yields the UTC date, which is a day
    behind IST for the first 5h30m of every Indian day — long enough to hide a
    stale screen every morning. Caught by live verification, not by a fixture.
    """
    assert "toISOString" not in JS_CODE, (
        "freshness must compare against the local date; toISOString is UTC"
    )
    assert "now.getFullYear()" in JS_CODE


def test_skipped_instruments_are_rendered_with_reasons():
    assert "skipped-list" in HTML
    assert "entry.reason" in JS_CODE


# --------------------------------------------------------------------------- #
# 4. The page renders persisted data and never recomputes it
# --------------------------------------------------------------------------- #


def test_the_page_renders_the_stored_explanation_verbatim():
    """ADR-005: the screener draws the engine's rationale, never its own."""
    assert "row.explanation" in JS_CODE
    # No client-side re-derivation of a tier or a distance.
    for forbidden in ("function tierFor", "computeTier", "recompute"):
        assert forbidden not in JS_CODE


def test_the_ranking_reference_is_shown_not_inferred():
    """Most WATCH rows are ranked to the box ceiling rather than a trigger, so
    the page must say which — otherwise the number is unexplained."""
    assert "breakout_reference" in JS_CODE


def test_no_framework_or_build_step_is_introduced():
    """ADR-004 keeps this dashboard framework-free and build-step-free."""
    for forbidden in ("react", "vue", "angular", "import ", "require(", "cdn."):
        assert forbidden not in JS_CODE.lower(), f"darvax.js pulls in {forbidden!r}"
    assert "<script src=\"https://" not in HTML


# --------------------------------------------------------------------------- #
# 5. The box visualisation exists and is CSS, not a library
# --------------------------------------------------------------------------- #


def test_box_range_visualisation_is_implemented_in_plain_css():
    for selector in (".viz", ".viz .range", ".viz .now", ".viz .trig"):
        assert selector in CSS, f"missing box-viz style {selector}"
    assert "function vizFor" in JS_CODE


def test_visualisation_degrades_when_there_is_no_box():
    """NO_BOX rows have no floor or ceiling; the cell must render empty rather
    than drawing a meaningless zero-width box."""
    assert "No completed box" in JS_CODE


# --------------------------------------------------------------------------- #
# 6. Asset cache-busting was bumped
# --------------------------------------------------------------------------- #


def test_both_assets_are_versioned_together():
    """Without a cache-busting bump the browser serves the previous CSS/JS and
    new markup silently renders against old code.

    Originally this pinned the literal ``dx6c`` strings, which made it fail on
    every subsequent milestone for doing the right thing — and the obvious fix
    was to edit the expectation, which is how a guard becomes a formality.
    What actually matters, and is checked here, is that **both** assets carry a
    version and carry the *same* one: bumping the JS and forgetting the CSS is
    the real-world failure, and it is invisible until something looks wrong."""
    import re

    css = re.search(r"darvax\.css\?v=([\w.\-]+)", HTML)
    js = re.search(r"darvax\.js\?v=([\w.\-]+)", HTML)
    assert css and js, "both DarvaX assets must be cache-busted"
    assert css.group(1) == js.group(1), (
        f"asset versions disagree: css={css.group(1)} js={js.group(1)}"
    )


# --------------------------------------------------------------------------- #
# 7. API contract the page depends on
# --------------------------------------------------------------------------- #


@pytest.fixture()
def client(tmp_path: Path):
    config_dir = tmp_path / "darvax-config"
    config_dir.mkdir(parents=True)
    (config_dir / "darvax.json").write_text(
        json.dumps({"enabled": True, "database": {"path": "db/darvax.db"}}),
        encoding="utf-8",
    )
    from athena.data.store.repository import SqliteRepository

    repo = SqliteRepository(tmp_path / "athena.db")
    repo.initialize()
    app = create_app(APISettings())
    app.state.sqlite_repo = repo
    assert mount_darvax_if_enabled(
        app, repo=repo, config_dir=config_dir, repo_root=tmp_path
    ) is True
    with TestClient(app, raise_server_exceptions=False) as c:
        yield c
    repo.close()


def test_latest_screen_serves_the_current_methodology_digest(client):
    """The page cannot detect a methodology mismatch without both digests, and
    a screen produced under different settings than are in force is misleading.
    """
    headers = get_auth_headers(client, Role.ADMIN)
    body = client.get(f"{DARVAX_MOUNT_PATH}/api/screen/latest", headers=headers).json()
    assert body["current_methodology_digest"] == methodology_digest(
        DarvaxConfig().methodology
    )


def test_empty_state_still_carries_the_digest(client):
    """Served even before any sweep, so the field is never absent for the page."""
    headers = get_auth_headers(client, Role.ADMIN)
    body = client.get(f"{DARVAX_MOUNT_PATH}/api/screen/latest", headers=headers).json()
    assert body["sweep"] is None
    assert body["current_methodology_digest"]


def test_every_field_the_page_reads_is_in_the_screen_payload():
    """Pins the API↔page contract: renaming any of these breaks the screen
    silently, since JavaScript reads a missing property as undefined."""
    from tests.darvax.test_dx6a_screening import make_signal

    from athena.darvax.api.routes import _screen_payload
    from athena.darvax.screening import screen_signal
    from athena.darvax.signals.models import DarvaxSignalType

    payload = _screen_payload(
        screen_signal(
            make_signal(
                "BSE", DarvaxSignalType.INSIDE_TOPMOST_BOX,
                close="100", box_top="110", box_bottom="90",
            ),
            sweep_id="swp-1",
        )
    )
    for field in (
        "symbol", "instrument_id", "signal_id", "tier", "signal_type",
        "darvas_rule", "rank", "close", "box_top", "box_bottom",
        "trigger_price", "distance_to_breakout_pct", "breakout_reference",
        "box_height_pct", "explanation", "status",
    ):
        assert field in payload, f"screen payload lost {field!r}, which the page reads"
        assert f'row.{field}' in JS or f'"{field}"' in JS or field in JS
