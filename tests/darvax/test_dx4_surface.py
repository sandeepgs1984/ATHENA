"""DX-4: DarvaX's own `/darvax/` API and UI surface (ADR-010).

Three things this file exists to prove:

1. The surface **requires authentication** on every data endpoint. DX-1 shipped
   an unauthenticated ``/status`` probe and recorded that "DX-4 must apply an
   auth posture before any real endpoint ships" — these tests hold that promise.
2. The surface is **labelled experimental everywhere**, because the source
   methodology ships no validation evidence.
3. The UI is **DarvaX's own**: it does not enter ATHENA's DASHBOARD_JS_PARTS,
   modify ``index.html``, or touch ``dashboard.js``/``dashboard.css``.
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

from athena.api.app import DASHBOARD_JS_PARTS, create_app
from athena.api.config import APISettings
from athena.api.darvax_mount import (
    _SHARED_AUTH_STATE,
    DARVAX_MOUNT_PATH,
    mount_darvax_if_enabled,
)
from athena.api.security.models import Role
from athena.darvax.api.routes import EXPERIMENTAL_STATUS
from athena.data.store.repository import SqliteRepository
from athena.domain.enums import Timeframe
from athena.domain.market import Candle, Instrument

IST = ZoneInfo("Asia/Kolkata")
BASE_TS = datetime(2026, 3, 2, 9, 15, tzinfo=IST)
REPO_ROOT = Path(__file__).resolve().parents[2]
DARVAX_STATIC = REPO_ROOT / "src" / "athena" / "darvax" / "api" / "static"

# The DX-2/DX-3 fixture: a topmost box of [8, 12].
_H = [10, 11, 12, 11, 11, 11, 10, 9, 9, 9, 9]
_L = [9, 10, 11, 10, 10, 10, 9, 8, 8, 8, 8]


def _seed_athena(db_path: Path, instrument_id: str = "NSE:SYN") -> SqliteRepository:
    repo = SqliteRepository(db_path)
    repo.initialize()
    repo.upsert_instrument(
        Instrument(
            instrument_id=instrument_id,
            symbol=instrument_id.split(":")[-1],
            exchange="NSE",
            series="EQ",
            status="ACTIVE",
        )
    )
    repo.add_candles(
        [
            Candle(
                instrument_id=instrument_id,
                timeframe=Timeframe.D1,
                ts_open=BASE_TS + timedelta(days=i),
                open=Decimal(str(_L[i])),
                high=Decimal(str(_H[i])),
                low=Decimal(str(_L[i])),
                close=Decimal(str(_L[i])),
                volume=1_000,
                source="test",
            )
            for i in range(len(_H))
        ]
    )
    return repo


@pytest.fixture()
def darvax_client(tmp_path: Path):
    """An ATHENA app with DarvaX mounted and enabled, over a seeded temp ledger."""
    config_dir = tmp_path / "config"
    config_dir.mkdir(parents=True)
    (config_dir / "darvax.json").write_text(
        json.dumps({"enabled": True, "database": {"path": "db/darvax.db"}}),
        encoding="utf-8",
    )
    repo = _seed_athena(tmp_path / "athena.db")
    app = create_app(APISettings())
    app.state.sqlite_repo = repo
    assert mount_darvax_if_enabled(
        app, repo=repo, config_dir=config_dir, repo_root=tmp_path
    ) is True
    with TestClient(app, raise_server_exceptions=False) as client:
        yield client
    repo.close()


# =========================================================================== #
# Authentication — the DX-1 promise this milestone had to keep
# =========================================================================== #


@pytest.mark.parametrize(
    ("method", "path", "body"),
    [
        ("GET", f"{DARVAX_MOUNT_PATH}/api/signals", None),
        ("GET", f"{DARVAX_MOUNT_PATH}/api/signals/NSE:SYN", None),
        ("POST", f"{DARVAX_MOUNT_PATH}/api/scan", {"instrument_ids": ["NSE:SYN"]}),
    ],
)
def test_every_data_endpoint_rejects_unauthenticated_requests(
    darvax_client: TestClient, method: str, path: str, body: dict | None
):
    response = darvax_client.request(method, path, json=body)
    assert response.status_code in (401, 403), (
        f"{method} {path} must not serve data without authentication, "
        f"got {response.status_code}"
    )


def test_status_probe_stays_open_but_carries_no_market_data(
    darvax_client: TestClient,
):
    """``/status`` is deliberately unauthenticated, mirroring ATHENA's own
    ``/health``. That is only defensible because it exposes no market data and no
    signal — asserted here so it stays that way."""
    response = darvax_client.get(f"{DARVAX_MOUNT_PATH}/status")
    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == EXPERIMENTAL_STATUS
    for leak in ("signals", "close", "box_top", "explanation", "instrument_id"):
        assert leak not in payload


def test_seam_shares_only_the_two_auth_objects():
    """DarvaX delegates auth to ATHENA. That delegation must not become a
    general-purpose state bridge."""
    assert _SHARED_AUTH_STATE == ("token_signer", "claims_factory")


def test_darvax_subapp_receives_the_shared_auth_state(darvax_client: TestClient):
    darvax_app = next(
        route.app
        for route in darvax_client.app.routes
        if getattr(route, "path", "") == DARVAX_MOUNT_PATH
    )
    for attribute in _SHARED_AUTH_STATE:
        assert hasattr(darvax_app.state, attribute)
    # And nothing beyond DarvaX's own wiring plus that auth delegation.
    leaked = {"decision_provider", "portfolio_provider", "candidate_store"}
    for attribute in leaked:
        assert not hasattr(darvax_app.state, attribute), (
            f"DarvaX sub-app received ATHENA state {attribute!r}"
        )


# =========================================================================== #
# Authenticated behaviour
# =========================================================================== #


def test_scan_then_list_round_trip(darvax_client: TestClient):
    headers = get_auth_headers(darvax_client, Role.ADMIN)

    scanned = darvax_client.post(
        f"{DARVAX_MOUNT_PATH}/api/scan",
        json={"instrument_ids": ["NSE:SYN"]},
        headers=headers,
    )
    assert scanned.status_code == 200, scanned.text
    body = scanned.json()
    assert body["evaluated"] == 1
    assert body["skipped"] == []
    assert body["darvax_status"] == EXPERIMENTAL_STATUS

    signal = body["data"][0]
    assert signal["symbol"] == "SYN"
    assert signal["explanation"], "the persisted explanation must be served"
    assert signal["evidence"], "the persisted evidence trace must be served"
    assert signal["status"] == EXPERIMENTAL_STATUS

    listed = darvax_client.get(
        f"{DARVAX_MOUNT_PATH}/api/signals", headers=headers
    ).json()
    assert listed["count"] == 1
    assert listed["data"][0]["signal_id"] == signal["signal_id"]

    single = darvax_client.get(
        f"{DARVAX_MOUNT_PATH}/api/signals/NSE:SYN", headers=headers
    ).json()
    assert single["data"]["signal_id"] == signal["signal_id"]


def test_unknown_instrument_returns_404_not_a_fabricated_signal(
    darvax_client: TestClient,
):
    headers = get_auth_headers(darvax_client, Role.ADMIN)
    response = darvax_client.get(
        f"{DARVAX_MOUNT_PATH}/api/signals/NSE:NOSUCH", headers=headers
    )
    assert response.status_code == 404


def test_scan_reports_skips_rather_than_silently_dropping_them(
    darvax_client: TestClient,
):
    """An instrument with no candles must be reported, not omitted — otherwise
    the caller cannot tell the difference between 'no signal' and 'not looked at'."""
    headers = get_auth_headers(darvax_client, Role.ADMIN)
    body = darvax_client.post(
        f"{DARVAX_MOUNT_PATH}/api/scan",
        json={"instrument_ids": ["NSE:SYN", "NSE:MISSING"]},
        headers=headers,
    ).json()
    assert body["requested"] == 2
    assert body["evaluated"] == 1
    assert [s["instrument_id"] for s in body["skipped"]] == ["NSE:MISSING"]
    assert "no candles" in body["skipped"][0]["reason"]


def test_scan_refuses_an_over_cap_request_instead_of_truncating(
    darvax_client: TestClient,
):
    """Silently trimming the list would return a partial answer that looks
    complete."""
    headers = get_auth_headers(darvax_client, Role.ADMIN)
    response = darvax_client.post(
        f"{DARVAX_MOUNT_PATH}/api/scan",
        json={"instrument_ids": [f"NSE:S{i}" for i in range(60)]},
        headers=headers,
    )
    assert response.status_code == 422
    assert "cap" in response.json()["detail"]


def test_scan_validates_its_payload(darvax_client: TestClient):
    headers = get_auth_headers(darvax_client, Role.ADMIN)
    assert darvax_client.post(
        f"{DARVAX_MOUNT_PATH}/api/scan", json={}, headers=headers
    ).status_code == 422
    assert darvax_client.post(
        f"{DARVAX_MOUNT_PATH}/api/scan",
        json={"instrument_ids": ["NSE:SYN"], "timeframe": "17y"},
        headers=headers,
    ).status_code == 422


def test_every_payload_carries_the_experimental_disclaimer(darvax_client: TestClient):
    headers = get_auth_headers(darvax_client, Role.ADMIN)
    darvax_client.post(
        f"{DARVAX_MOUNT_PATH}/api/scan",
        json={"instrument_ids": ["NSE:SYN"]},
        headers=headers,
    )
    for path in (
        f"{DARVAX_MOUNT_PATH}/api/signals",
        f"{DARVAX_MOUNT_PATH}/api/signals/NSE:SYN",
    ):
        payload = darvax_client.get(path, headers=headers).json()
        assert payload["darvax_status"] == EXPERIMENTAL_STATUS
        assert "never contributes" in payload["disclaimer"]


# =========================================================================== #
# UI surface
# =========================================================================== #


def test_darvax_serves_its_own_page_and_assets(darvax_client: TestClient):
    page = darvax_client.get(f"{DARVAX_MOUNT_PATH}/")
    assert page.status_code == 200
    assert "EXPERIMENTAL" in page.text
    assert "darvax.css" in page.text and "darvax.js" in page.text

    for asset in ("darvax.css", "darvax.js"):
        served = darvax_client.get(f"{DARVAX_MOUNT_PATH}/static/{asset}")
        assert served.status_code == 200, asset


def test_page_states_the_unvalidated_status_prominently():
    """The banner is a correctness requirement, not decoration: the source deck
    ships no evidence and its own author disclaims it."""
    html = (DARVAX_STATIC / "index.html").read_text(encoding="utf-8")
    assert "EXPERIMENTAL" in html
    assert "UNVALIDATED" in html
    assert "no backtest evidence" in html
    assert "never" in html and "TradePlan" in html


def test_darvax_ui_does_not_touch_athena_dashboard_assets():
    """DarvaX's UI is its own surface, so ATHENA's asset-versioning discipline is
    unaffected by it.

    Scope note: ADR-010 Amendment 1 permits **one** DarvaX reference in
    ``index.html`` — the ``tab.js`` script tag that injects the dashboard tab, and
    which is itself the flag guard. That single exception is asserted in detail by
    ``test_dx4b_tab.py::test_01_index_html_contains_only_the_script_tag_reference``;
    this test covers everything that must still be completely DarvaX-free.
    """
    assert not any("darvax" in part.lower() for part in DASHBOARD_JS_PARTS)

    athena_static = REPO_ROOT / "src" / "athena" / "api" / "static"
    for name in ("js", "css"):
        for asset in (athena_static / name).rglob("*"):
            if asset.is_file():
                assert "darvax" not in asset.read_text(encoding="utf-8").lower(), (
                    f"ATHENA asset {asset.name} references DarvaX"
                )


def test_darvax_js_reuses_athena_session_rather_than_its_own_login():
    """DarvaX must not stand up a second credential store."""
    js = (DARVAX_STATIC / "darvax.js").read_text(encoding="utf-8")
    assert "athena.access_token" in js
    for forbidden in ("password", "/auth/login", "setItem"):
        assert forbidden not in js, (
            f"DarvaX JS contains {forbidden!r}; it must delegate auth, not own it"
        )


def test_darvax_to_athena_import_surface_is_pinned():
    """DX-4 widened the DarvaX → ATHENA import surface to delegate auth. Pin the
    whole surface so any further widening is a deliberate, visible change rather
    than something that accretes unnoticed.

    Each entry below is here for a stated reason:
      * ``athena.domain`` / ``athena.errors`` — the baseline ADR-010 allows.
      * ``athena.data.store.repository`` — DX-1's read-only market-data adapter.
      * ``athena.api.security`` — DX-4 delegates authentication to ATHENA rather
        than standing up a second credential store.
      * ``athena.api.errors`` — reuses ATHENA's status mapping so a mounted
        sub-app's error responses cannot drift from the parent's.
    """
    import ast

    allowed = {
        "athena.darvax",
        "athena.domain",
        "athena.errors",
        "athena.data.store.repository",
        "athena.api.security",
        "athena.api.errors",
    }
    pkg = REPO_ROOT / "src" / "athena" / "darvax"
    found: set[str] = set()
    for py in pkg.rglob("*.py"):
        tree = ast.parse(py.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            module = None
            if isinstance(node, ast.ImportFrom):
                module = node.module or ""
            elif isinstance(node, ast.Import):
                module = node.names[0].name
            if module and module.startswith("athena."):
                found.add(module)

    unexpected = {
        module
        for module in found
        if not any(module == a or module.startswith(a + ".") for a in allowed)
    }
    assert unexpected == set(), (
        f"DarvaX imports outside its pinned ATHENA surface: {sorted(unexpected)}"
    )


def test_darvax_never_imports_athena_analytical_engines():
    """Whatever else the surface allows, DarvaX must never reach into the engines
    that produce ATHENA's own decisions."""
    import ast

    forbidden_prefixes = (
        "athena.scoring", "athena.confidence", "athena.risk", "athena.decision",
        "athena.evidence", "athena.universe", "athena.regime", "athena.orders",
        "athena.portfolio", "athena.execution", "athena.brokers",
        "athena.market_health", "athena.sector_health", "athena.scheduling",
        "athena.orchestration",
    )
    pkg = REPO_ROOT / "src" / "athena" / "darvax"
    for py in pkg.rglob("*.py"):
        tree = ast.parse(py.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            module = None
            if isinstance(node, ast.ImportFrom):
                module = node.module or ""
            elif isinstance(node, ast.Import):
                module = node.names[0].name
            if module:
                for prefix in forbidden_prefixes:
                    assert not module.startswith(prefix), (
                        f"{py.name} imports {module!r} — DarvaX must never touch "
                        f"ATHENA's analytical engines"
                    )


def test_darvax_disabled_serves_no_ui(tmp_path: Path):
    config_dir = tmp_path / "config"
    config_dir.mkdir(parents=True)
    (config_dir / "darvax.json").write_text(
        json.dumps({"enabled": False}), encoding="utf-8"
    )
    app = create_app(APISettings())
    assert mount_darvax_if_enabled(
        app, repo=object(), config_dir=config_dir, repo_root=tmp_path
    ) is False
    with TestClient(app, raise_server_exceptions=False) as client:
        assert client.get(f"{DARVAX_MOUNT_PATH}/").status_code == 404
        assert client.get(f"{DARVAX_MOUNT_PATH}/static/darvax.js").status_code == 404
