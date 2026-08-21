"""AUX-8: "Scan & Validate" on Symbol 360.

Owner request: "one option where user will enter symbol and result should
be both athena validation and darvax validation after scanning the symbol
properly" -- Symbol 360's existing "Look up" (AUX-7) only ever reads
whatever each engine has already persisted. This adds a second, explicit
action that actually re-runs both engines for the current symbol: ATHENA's
existing candidate-upsert + validate pipeline (the same one
09-market-intelligence.js's validateSymbolsNow already uses), and DarvaX's
existing per-instrument scan endpoint. No new route on either side.

Design confirmed with the owner: two SEPARATE actions ("Look up" stays
free/instant; "Scan & Validate" is a second button shown once a symbol is
loaded), not one combined action -- ATHENA's half makes a real Kite ingest
call and both halves persist new data, so this must never fire silently on
every search.

Owner-caught inconsistency, fixed same day: DarvaX's existing
``POST /darvax/api/scan`` deliberately runs no classification (DX-4's own
docstring: "adding no methodology of its own") -- it only produces a raw
``DarvaxSignal``, not the tier/action-classified ``ScreenResult`` a real
universe sweep produces. Symbol 360's "Look up" and "Scan & Validate"
therefore rendered two visibly different shapes for the same symbol,
which is confusing coming from one page with one search box. Fixed by
having ``/darvax/api/scan`` additionally classify each fresh signal with
the exact same, already-tested pure function a sweep uses
(``screen_signal``), returned as a new ``screened`` field alongside the
existing ``data`` -- purely additive, no schema/persistence change, no new
methodology (the classifier already existed and is unit-tested elsewhere;
this only wires it into a second caller).
"""

from __future__ import annotations

import json
from datetime import datetime, timedelta
from decimal import Decimal
from pathlib import Path
from zoneinfo import ZoneInfo

import pytest
from fastapi.testclient import TestClient
from tests.api.v1.test_core_apis import get_auth_headers

from athena.api.app import create_app
from athena.api.config import APISettings
from athena.api.darvax_mount import DARVAX_MOUNT_PATH, mount_darvax_if_enabled
from athena.api.security.models import Role
from athena.darvax.screening.sweep import SweepRunner
from athena.domain.enums import Timeframe
from athena.domain.market import Candle, Instrument

DARVAX_STATIC = Path(__file__).resolve().parents[2] / "src" / "athena" / "darvax" / "api" / "static"
IST = ZoneInfo("Asia/Kolkata")
BASE = datetime(2026, 1, 1, 9, 15, tzinfo=IST)

pytestmark = pytest.mark.usefixtures("athena_config_darvax_disabled")

SYMBOL360_HTML = (DARVAX_STATIC / "symbol360.html").read_text(encoding="utf-8")


def _strip_js_comments(source: str) -> str:
    import re

    source = re.sub(r"/\*.*?\*/", "", source, flags=re.DOTALL)
    source = re.sub(r"(?<!:)//[^\n]*", "", source)
    return source


SYMBOL360_JS = _strip_js_comments((DARVAX_STATIC / "symbol360.js").read_text(encoding="utf-8"))


def _fn(source: str, name: str) -> str:
    start = source.index(f"function {name}(")
    try:
        end = source.index("\n  function ", start + 1)
    except ValueError:
        end = len(source)
    return source[start:end]


# --------------------------------------------------------------------------- #
# 1. The button exists, and only appears once a symbol is loaded
# --------------------------------------------------------------------------- #


def test_scan_button_is_a_separate_action_from_look_up():
    """Design decision, confirmed with the owner: two actions, not one --
    "Look up" (the <button type="submit"> in #s360-form) stays free/instant;
    "Scan & Validate" is a distinct button, living inside #s360-result so it
    is only shown once a symbol has actually been looked up."""
    assert 'id="s360-scan-btn"' in SYMBOL360_HTML
    result_start = SYMBOL360_HTML.index('id="s360-result"')
    form_start = SYMBOL360_HTML.index('id="s360-form"')
    scan_btn_start = SYMBOL360_HTML.index('id="s360-scan-btn"')
    assert form_start < result_start < scan_btn_start, (
        "the scan button must live inside #s360-result, not the search form"
    )


def test_scan_and_validate_is_a_noop_without_a_loaded_symbol():
    body = _fn(SYMBOL360_JS, "scanAndValidate")
    assert "if (!current.instrumentId) return;" in body


# --------------------------------------------------------------------------- #
# 2. ATHENA lane -- reuses the existing candidate-upsert-then-validate flow
# --------------------------------------------------------------------------- #


def test_athena_lane_upserts_the_candidate_before_validating():
    """/api/v1/market/validate 404s/422s on a symbol that isn't already a
    known candidate -- the same two-call sequence ATHENA's own dashboard
    already uses (09-market-intelligence.js's validateSymbolsNow) must be
    followed here too, not just the second call alone."""
    body = _fn(SYMBOL360_JS, "athenaValidateNow")
    candidates_pos = body.index("/api/v1/market/candidates")
    validate_pos = body.index("/api/v1/market/validate")
    assert candidates_pos < validate_pos
    assert '"POST"' in body


def test_athena_lane_reloads_the_decision_through_the_existing_reader():
    """/validate returns run counts, not the decision itself -- the fresh
    decision must be picked up by re-running loadAthenaDecision (the exact
    same reader "Look up" already uses), never by rendering /validate's own
    response shape as if it were a decision."""
    body = _fn(SYMBOL360_JS, "athenaValidateNow")
    assert "loadAthenaDecision(instrumentId)" in body


def test_athena_lane_shows_its_own_inline_error_without_touching_darvax_card():
    body = _fn(SYMBOL360_JS, "athenaValidateNow")
    assert "els.athenaCard.innerHTML" in body
    assert "els.darvaxCard" not in body


# --------------------------------------------------------------------------- #
# 3. DarvaX lane -- reuses the existing per-instrument scan endpoint
# --------------------------------------------------------------------------- #


def test_darvax_lane_calls_the_existing_scan_endpoint_with_this_instrument():
    body = _fn(SYMBOL360_JS, "darvaxScanNow")
    assert "/darvax/api/scan" in body
    assert '"POST"' in body
    assert "instrument_ids" in body


def test_darvax_lane_renders_the_scan_response_directly_without_a_refetch():
    """The /scan response already carries the fresh, classified result in its
    own response -- a second GET to /darvax/api/signals/{id} would risk a
    moment of stale data between the two calls for no benefit."""
    body = _fn(SYMBOL360_JS, "darvaxScanNow")
    assert "/darvax/api/signals/" not in body


def test_darvax_lane_prefers_the_classified_screened_result():
    """Owner-caught: an unclassified raw signal ("Buy on dip"-less SIGNAL/RULE
    shape) looked inconsistent next to "Look up"'s tier/action-classified
    result for the same symbol. /scan's own "screened" field (screen_signal
    applied server-side) must be rendered through the same row branch as
    "Look up" -- the raw signal is only a fallback if screened is empty."""
    body = _fn(SYMBOL360_JS, "darvaxScanNow")
    screened_check = body.index("payload.screened")
    row_render = body.index("renderDarvaxCard(screened[0]")
    fallback_render = body.index("renderDarvaxCard(null, signals[0]")
    assert screened_check < row_render < fallback_render, (
        "screened must be checked and rendered via the row branch before "
        "falling back to the unclassified signal"
    )


def test_darvax_lane_marks_the_result_as_freshly_scanned():
    """renderDarvaxCard's signal-only branch prints a fixed "no current sweep
    row" sentence for the passive lookup path -- a result from this button
    must say it was freshly scanned instead, not imply it's a leftover from
    some earlier ad hoc scan."""
    body = _fn(SYMBOL360_JS, "darvaxScanNow")
    assert ", true)" in body, "must pass freshlyScanned=true to renderDarvaxCard"


def test_render_darvax_card_distinguishes_freshly_scanned_from_stale_fallback():
    body = _fn(SYMBOL360_JS, "renderDarvaxCard")
    assert "Freshly scanned just now" in body
    assert "No current sweep row for this instrument" in body
    assert "freshlyScanned" in body


def test_darvax_lane_shows_its_own_inline_error_without_touching_athena_card():
    body = _fn(SYMBOL360_JS, "darvaxScanNow")
    assert "els.darvaxCard.innerHTML" in body
    assert "els.athenaCard" not in body


# --------------------------------------------------------------------------- #
# 4. Both lanes run concurrently, and can never clobber the wrong symbol
# --------------------------------------------------------------------------- #


def test_both_lanes_run_concurrently_not_sequentially():
    body = _fn(SYMBOL360_JS, "scanAndValidate")
    assert "Promise.all([" in body
    assert "athenaValidateNow(instrumentId, bareSymbol, requestId)" in body
    assert "darvaxScanNow(instrumentId, requestId)" in body


def test_stale_scan_responses_are_dropped_by_both_lanes():
    """Same out-of-order-response guard convention tab.js's checkCrossLink
    established for AUX-6 -- a request id captured at call time, checked
    against the shared counter before a response is allowed to render."""
    athena_body = _fn(SYMBOL360_JS, "athenaValidateNow")
    darvax_body = _fn(SYMBOL360_JS, "darvaxScanNow")
    for body in (athena_body, darvax_body):
        assert "requestId !== scanRequestId" in body


def test_a_new_lookup_invalidates_any_scan_still_in_flight():
    """A slow ATHENA validate call for a PREVIOUS symbol must never clobber
    the card after the owner has already searched for a different one."""
    body = _fn(SYMBOL360_JS, "lookup")
    assert "scanRequestId++" in body
    assert "els.scanBtn.disabled = false" in body


# --------------------------------------------------------------------------- #
# 5. Backend: /darvax/api/scan actually classifies, real route, real data
# --------------------------------------------------------------------------- #


class FakeMarketData:
    """Implements DarvaxMarketDataPort with one instrument that breaks out.

    Minimal version of test_dx6b_sweep.py's fixture, scoped to exactly what
    this test needs: one symbol, one clean breakout, so scan_instruments has
    a real signal to evaluate and screen_signal has something worth
    classifying as ACTIONABLE rather than everything landing in WATCH.
    """

    def list_instruments(self):
        return [Instrument(instrument_id="NSE:BRK", symbol="BRK", exchange="NSE", series="EQ", name="BRK")]

    def recent_candles(self, instrument_id, timeframe, *, limit: int):
        bars = []
        for i in range(60):
            low = Decimal(100) + Decimal(i % 20)
            bars.append(Candle(
                instrument_id=instrument_id, timeframe=Timeframe.D1,
                ts_open=BASE + timedelta(days=i), open=low + Decimal("0.5"),
                high=low + Decimal(2), low=low, close=low + Decimal(1),
                volume=100_000 + i, source="aux8-test",
            ))
        top = max(b.high for b in bars)
        bars.append(Candle(
            instrument_id=instrument_id, timeframe=Timeframe.D1,
            ts_open=BASE + timedelta(days=60), open=top + Decimal(1),
            high=top + Decimal(6), low=top, close=top + Decimal(5),
            volume=400_000, source="aux8-test",
        ))
        return bars[-limit:] if limit else bars

    def candles_between(self, instrument_id, timeframe, start, end):  # pragma: no cover
        return self.recent_candles(instrument_id, timeframe, limit=60)


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
    assert mount_darvax_if_enabled(app, repo=repo, config_dir=config_dir, repo_root=tmp_path) is True
    darvax_app = next(r.app for r in app.routes if getattr(r, "path", "") == DARVAX_MOUNT_PATH)
    market = FakeMarketData()
    darvax_app.state.darvax_market_data = market
    darvax_app.state.darvax_sweep_runner = SweepRunner(
        market_data=market, store=darvax_app.state.darvax_store,
        config=darvax_app.state.darvax_config, darvax_version="0.1.0",
    )
    with TestClient(app, raise_server_exceptions=False) as c:
        yield c
    repo.close()


def test_scan_route_returns_a_classified_screened_result(client: TestClient):
    """The actual wiring, not a source-level grep: hitting the real route
    over real (fake-market-data) candles must come back with a `screened`
    entry carrying the same tier/action/buy-above/stop-loss shape
    /screen/latest's rows already carry -- proving screen_signal is really
    being applied, not just imported."""
    headers = get_auth_headers(client, Role.ADMIN)
    res = client.post(
        f"{DARVAX_MOUNT_PATH}/api/scan",
        json={"instrument_ids": ["NSE:BRK"]},
        headers=headers,
    )
    assert res.status_code == 200
    body = res.json()
    assert len(body["data"]) == 1, "the unclassified signal must still be present"
    screened = body["screened"]
    assert len(screened) == 1
    row = screened[0]
    assert row["instrument_id"] == "NSE:BRK"
    assert row["tier"] in ("ACTIONABLE", "WATCH", "EXIT_RELEVANT", "NO_BOX")
    assert row["action"] is not None
    # This fixture's clean breakout must classify as an entry, with a real
    # buy-above level -- otherwise the test would pass vacuously against a
    # WAIT/NO_ENTRY row with every trade field null.
    assert row["tier"] == "ACTIONABLE"
    assert row["action"] in ("ENTER", "ENTER_ON_RETEST")
    assert row["trigger_price"] is not None


def test_scan_route_never_persists_the_classification_as_a_real_sweep(client: TestClient):
    """screen_signal's sweep_id here is a placeholder, never a real sweep --
    /screen/latest (which only reads persisted ScreenResult rows from an
    actual sweep) must NOT see this instrument afterward."""
    headers = get_auth_headers(client, Role.ADMIN)
    client.post(
        f"{DARVAX_MOUNT_PATH}/api/scan",
        json={"instrument_ids": ["NSE:BRK"]},
        headers=headers,
    )
    latest = client.get(f"{DARVAX_MOUNT_PATH}/api/screen/latest?limit=5000", headers=headers)
    assert latest.status_code == 200
    ids = [r["instrument_id"] for r in latest.json()["data"]]
    assert "NSE:BRK" not in ids
