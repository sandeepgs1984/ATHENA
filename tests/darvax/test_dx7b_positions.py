"""DX-7b: DarvaX's own position list, and the actions it unlocks.

Two properties under test. First, **every held-action branch is the DAR-CARD
text applied literally** — HOLD and EXIT are the deck's own words, not DarvaX's
opinion. Second, **a position's stop is frozen at entry**: changing the stop
policy later must not silently move the level an open position was actually
protected by.
"""

from __future__ import annotations

from datetime import date, datetime, timezone
from decimal import Decimal
from pathlib import Path

import pytest

from athena.darvax.config import DarvaxConfig, DarvaxMethodologyConfig
from athena.darvax.positions.models import DarvaxPosition
from athena.darvax.screening.engine import action_for_held, screen_signal, screen_signals
from athena.darvax.screening.models import RISK_BEARING_ACTIONS, DarvaxAction
from athena.darvax.signals.models import DarvasRule, DarvaxSignal, DarvaxSignalType, StopBasis
from athena.darvax.signals.stops import compute_stop
from athena.darvax.store.repository import DarvaxRepository
from athena.errors import RepositoryError

AS_OF = datetime(2026, 8, 16, 10, 0, tzinfo=timezone.utc)
REPO_ROOT = Path(__file__).resolve().parents[2]

_RULE = {
    DarvaxSignalType.BREAKOUT: DarvasRule.B_BUY_ABOVE_TOPMOST_BOX,
    DarvaxSignalType.BREAKOUT_RETEST: DarvasRule.B_BUY_ABOVE_TOPMOST_BOX,
    DarvaxSignalType.INSIDE_TOPMOST_BOX: DarvasRule.A_HOLD_WHILE_IN_TOPMOST_BOX,
    DarvaxSignalType.BELOW_BOX_BOTTOM: DarvasRule.C_SELL_BELOW_NEW_BOX_BOTTOM,
    DarvaxSignalType.NOT_IN_TOPMOST_BOX: DarvasRule.D_NO_REASON_OUTSIDE_TOPMOST_BOX,
    DarvaxSignalType.NO_BOX: DarvasRule.D_NO_REASON_OUTSIDE_TOPMOST_BOX,
}


def signal(state: DarvaxSignalType, *, symbol="AAA", close="100") -> DarvaxSignal:
    return DarvaxSignal(
        signal_id=f"sig-{symbol}",
        instrument_id=f"NSE:{symbol}",
        as_of=AS_OF,
        signal_type=state,
        darvas_rule=_RULE[state],
        close=Decimal(close),
        box_top=Decimal("105"),
        box_bottom=Decimal("95"),
        trigger_price=None,
        explanation="from DX-3",
        evidence={},
        methodology_digest="digest",
        darvax_version="test",
    )


def position(**kw) -> DarvaxPosition:
    base = dict(
        position_id="pos-1",
        instrument_id="NSE:AAA",
        quantity=10,
        entry_price=Decimal("100"),
        entry_date=date(2026, 8, 1),
        opened_at=AS_OF,
        stop_price=Decimal("90"),
        stop_basis=StopBasis.CANONICAL_DARVAS_PCT,
    )
    base.update(kw)
    return DarvaxPosition(**base)


@pytest.fixture()
def store(tmp_path: Path) -> DarvaxRepository:
    r = DarvaxRepository(tmp_path / "darvax.db")
    r.initialize()
    yield r
    r.close()


# --------------------------------------------------------------------------- #
# 1. The held-action rules — the DAR-CARD, applied literally
# --------------------------------------------------------------------------- #


def test_inside_the_topmost_box_is_a_hold():
    """Rule A verbatim: "…its price fluctuations should be ignored and the stock
    is a HOLD.\"""" ""
    action, reason = action_for_held(
        signal(DarvaxSignalType.INSIDE_TOPMOST_BOX), stop_price=Decimal("90")
    )
    assert action is DarvaxAction.HOLD
    assert "rule A" in reason


def test_below_the_box_floor_is_an_exit_when_held():
    action, reason = action_for_held(
        signal(DarvaxSignalType.BELOW_BOX_BOTTOM), stop_price=Decimal("90")
    )
    assert action is DarvaxAction.EXIT
    assert "rule C" in reason


@pytest.mark.parametrize(
    "state", [DarvaxSignalType.NOT_IN_TOPMOST_BOX, DarvaxSignalType.NO_BOX]
)
def test_falling_out_of_the_topmost_box_is_an_exit_not_a_wait(state):
    """Rule D says "There is no reason to HOLD or BUY a stock that is not in its
    topmost box" — so for a *held* instrument that is an exit. Reading it as
    "wait" would keep the owner in a position the methodology has abandoned."""
    action, reason = action_for_held(signal(state), stop_price=None)
    assert action is DarvaxAction.EXIT
    assert "rule D" in reason


def test_a_breached_stop_wins_over_every_box_state():
    """Rule B mandates the stop, so it outranks the box: an instrument still
    sitting inside its topmost box but under its stop is an exit."""
    action, reason = action_for_held(
        signal(DarvaxSignalType.INSIDE_TOPMOST_BOX, close="89"),
        stop_price=Decimal("90"),
    )
    assert action is DarvaxAction.EXIT
    assert "stop" in reason.lower()


def test_the_stop_is_breached_at_the_stop_not_only_below_it():
    """A close exactly at the stop is a breach — a stop order at that level
    would have filled."""
    action, _ = action_for_held(
        signal(DarvaxSignalType.INSIDE_TOPMOST_BOX, close="90"),
        stop_price=Decimal("90"),
    )
    assert action is DarvaxAction.EXIT


def test_a_breakout_on_something_already_held_stays_a_hold():
    """Darvas pyramided into new boxes, but the DAR-CARD does not say so.
    Emitting ENTER here would advise adding to a position on DarvaX's own
    initiative — methodology the deck never states (ADR-010)."""
    action, reason = action_for_held(
        signal(DarvaxSignalType.BREAKOUT, close="110"), stop_price=Decimal("90")
    )
    assert action is DarvaxAction.HOLD
    assert "already held" in reason


def test_every_held_branch_names_a_rule_and_leaks_no_none():
    for state in DarvaxSignalType:
        for stop in (None, Decimal("90")):
            _, reason = action_for_held(signal(state), stop_price=stop)
            assert reason.strip() and "None" not in reason, (state, stop, reason)


def test_hold_and_exit_are_not_marked_risk_bearing():
    """The badge marks advice to *put money at risk*. HOLD proposes no new
    exposure and EXIT reduces it (design decision 3b)."""
    assert DarvaxAction.HOLD not in RISK_BEARING_ACTIONS
    assert DarvaxAction.EXIT not in RISK_BEARING_ACTIONS


# --------------------------------------------------------------------------- #
# 2. Screening with and without a position
# --------------------------------------------------------------------------- #


def test_the_same_signal_reads_differently_held_and_unheld():
    """The whole point of DX-7b, in one assertion."""
    sig = signal(DarvaxSignalType.BELOW_BOX_BOTTOM)
    unheld = screen_signal(sig, sweep_id="s", position=None)
    held = screen_signal(sig, sweep_id="s", position=position())
    assert unheld.action is DarvaxAction.EXIT_IF_HELD
    assert held.action is DarvaxAction.EXIT


def test_a_closed_position_does_not_count_as_held():
    closed = position(closed_at=AS_OF)
    result = screen_signal(
        signal(DarvaxSignalType.INSIDE_TOPMOST_BOX), sweep_id="s", position=closed
    )
    assert result.action is DarvaxAction.WAIT


def test_screen_signals_applies_positions_by_instrument():
    results = {
        r.instrument_id: r
        for r in screen_signals(
            [
                signal(DarvaxSignalType.INSIDE_TOPMOST_BOX, symbol="AAA"),
                signal(DarvaxSignalType.INSIDE_TOPMOST_BOX, symbol="BBB"),
            ],
            sweep_id="s",
            positions={"NSE:AAA": position()},
        )
    }
    assert results["NSE:AAA"].action is DarvaxAction.HOLD
    assert results["NSE:BBB"].action is DarvaxAction.WAIT


def test_omitting_positions_preserves_pre_dx7b_behaviour():
    """Every existing caller passes no positions; none of them may change."""
    results = screen_signals(
        [signal(DarvaxSignalType.INSIDE_TOPMOST_BOX)], sweep_id="s"
    )
    assert results[0].action is DarvaxAction.WAIT


def test_the_screening_engine_still_performs_no_lookups():
    """Purity is the reason positions are passed in rather than fetched. An
    import of the store here would give the screen hidden state and stop it
    being replayable from its inputs.

    Checked against the import graph, not the file text: the module docstring
    legitimately discusses the position *store* while explaining why it does not
    touch one, and a substring check flagged that prose."""
    import ast

    tree = ast.parse(
        (REPO_ROOT / "src/athena/darvax/screening/engine.py").read_text(
            encoding="utf-8"
        )
    )
    imported: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imported.extend(a.name for a in node.names)
        elif isinstance(node, ast.ImportFrom):
            imported.append(node.module or "")
            imported.extend(a.name for a in node.names)
    forbidden = [n for n in imported if "store" in n or "Repository" in n]
    assert forbidden == [], f"screening engine must not reach storage: {forbidden}"


# --------------------------------------------------------------------------- #
# 3. Persistence
# --------------------------------------------------------------------------- #


def test_a_position_round_trips(store: DarvaxRepository):
    store.upsert_position(position(note="first darvas trade"))
    back = store.list_positions()
    assert len(back) == 1
    assert back[0].entry_price == Decimal("100")
    assert back[0].stop_basis is StopBasis.CANONICAL_DARVAS_PCT
    assert back[0].note == "first darvas trade"
    assert back[0].is_open


def test_two_open_positions_in_one_instrument_are_refused(store: DarvaxRepository):
    """"Am I holding this?" is asked on every sweep and must have one answer."""
    store.upsert_position(position(position_id="pos-1"))
    with pytest.raises(RepositoryError, match="already exists"):
        store.upsert_position(position(position_id="pos-2"))


def test_reentering_after_closing_is_allowed_and_keeps_history(store: DarvaxRepository):
    store.upsert_position(position(position_id="pos-1"))
    assert store.close_position("pos-1", closed_at=AS_OF)
    store.upsert_position(position(position_id="pos-2"))

    assert len(store.list_positions(open_only=True)) == 1
    assert len(store.list_positions(open_only=False)) == 2, (
        "closing must preserve the completed round trip, not erase it"
    )


def test_closing_an_already_closed_position_reports_nothing_to_do(
    store: DarvaxRepository,
):
    store.upsert_position(position())
    assert store.close_position("pos-1", closed_at=AS_OF) is True
    assert store.close_position("pos-1", closed_at=AS_OF) is False


def test_delete_removes_a_mistake_while_close_preserves_a_trade(
    store: DarvaxRepository,
):
    store.upsert_position(position(position_id="typo"))
    assert store.delete_position("typo") is True
    assert store.list_positions(open_only=False) == []
    assert store.delete_position("typo") is False


def test_open_positions_are_keyed_for_the_sweep(store: DarvaxRepository):
    store.upsert_position(position(position_id="p1", instrument_id="NSE:AAA"))
    store.upsert_position(position(position_id="p2", instrument_id="NSE:BBB"))
    store.close_position("p2", closed_at=AS_OF)
    keyed = store.open_positions_by_instrument()
    assert set(keyed) == {"NSE:AAA"}


# --------------------------------------------------------------------------- #
# 4. The stop is frozen at entry
# --------------------------------------------------------------------------- #


def test_the_derived_stop_matches_the_canonical_ten_percent_rule():
    stop = compute_stop(
        [], DarvaxMethodologyConfig(stop_policy="canonical_darvas"),
        reference_price=Decimal("200"),
    )
    assert stop is not None
    assert stop.price == Decimal("180")
    assert stop.basis is StopBasis.CANONICAL_DARVAS_PCT


def test_a_stored_stop_does_not_move_when_the_policy_changes(store: DarvaxRepository):
    """The reason the stop is a column rather than a computed property: an open
    position keeps the level it was actually protected by, exactly as a stored
    signal keeps its methodology_digest."""
    store.upsert_position(position(stop_price=Decimal("90")))
    tight = compute_stop(
        [], DarvaxMethodologyConfig(stop_policy="darvax_tight"),
        reference_price=Decimal("100"),
    )
    assert tight is not None and tight.price == Decimal("99")

    back = store.list_positions()[0]
    assert back.stop_price == Decimal("90"), (
        "changing the policy must not retroactively move an open position's stop"
    )


def test_schema_version_advanced_for_the_positions_table(store: DarvaxRepository):
    from athena.darvax.store import DARVAX_SCHEMA_VERSION

    assert store.schema_version() == DARVAX_SCHEMA_VERSION


# --------------------------------------------------------------------------- #
# 5. Advisory only
# --------------------------------------------------------------------------- #


def test_positions_never_become_orders():
    """ATHENA's hardest invariant. Recording a holding must not drift into
    routing one."""
    banned = ("place_order", "submit_order", "order_id", "buy(", "sell(")
    for path in (
        REPO_ROOT / "src/athena/darvax/positions/models.py",
        REPO_ROOT / "src/athena/darvax/api/routes.py",
    ):
        source = path.read_text(encoding="utf-8")
        for word in banned:
            assert word not in source, f"{path.name} contains {word!r}"


# --------------------------------------------------------------------------- #
# 6. The write API
# --------------------------------------------------------------------------- #


@pytest.fixture()
def client(tmp_path: Path):
    import json

    from fastapi.testclient import TestClient

    from athena.api.app import create_app
    from athena.api.darvax_mount import DARVAX_MOUNT_PATH, mount_darvax_if_enabled
    from athena.api.config import APISettings
    from athena.data.store.repository import SqliteRepository

    config_dir = tmp_path / "darvax-config"
    config_dir.mkdir(parents=True)
    (config_dir / "darvax.json").write_text(
        json.dumps({"enabled": True, "database": {"path": "db/darvax.db"}}),
        encoding="utf-8",
    )
    repo = SqliteRepository(tmp_path / "athena.db")
    repo.initialize()
    app = create_app(APISettings())
    app.state.sqlite_repo = repo
    assert (
        mount_darvax_if_enabled(
            app, repo=repo, config_dir=config_dir, repo_root=tmp_path
        )
        is True
    )
    with TestClient(app, raise_server_exceptions=False) as c:
        c.base = DARVAX_MOUNT_PATH  # type: ignore[attr-defined]
        yield c
    repo.close()


def _headers(client):
    from athena.api.security import Role
    from tests.api.v1.test_core_apis import get_auth_headers

    return get_auth_headers(client, Role.ADMIN)


def _open(client, headers, **over):
    body = {
        "instrument_id": "NSE:AAA",
        "quantity": 10,
        "entry_price": "100",
        "entry_date": "2026-08-01",
    }
    body.update(over)
    return client.post(f"{client.base}/api/positions", json=body, headers=headers)


def test_recording_a_position_derives_and_freezes_its_stop(client):
    headers = _headers(client)
    created = _open(client, headers)
    assert created.status_code == 200, created.text
    data = created.json()["data"]
    assert data["stop_price"] == "90.00"
    assert data["stop_basis"] == "CANONICAL_DARVAS_PCT"
    assert data["methodology_digest"], "the settings that produced the stop are recorded"
    assert data["is_open"] is True


def test_an_owner_supplied_stop_is_not_attributed_to_darvas(client):
    headers = _headers(client)
    data = _open(client, headers, stop_price="95").json()["data"]
    assert data["stop_price"] == "95"
    assert data["stop_basis"] is None, (
        "a level the owner chose must not be reported as a documented Darvas rule"
    )


def test_a_second_open_position_in_one_instrument_is_refused(client):
    headers = _headers(client)
    assert _open(client, headers).status_code == 200
    assert _open(client, headers).status_code == 409


@pytest.mark.parametrize(
    "bad",
    [
        {"quantity": 0},
        {"quantity": -5},
        {"entry_price": "0"},
        {"entry_price": "-1"},
        {"instrument_id": "  "},
        {"entry_date": "not-a-date"},
        {"entry_price": "abc"},
    ],
)
def test_malformed_positions_are_rejected(client, bad):
    assert _open(client, _headers(client), **bad).status_code == 422


def test_a_missing_field_is_rejected_rather_than_defaulted(client):
    headers = _headers(client)
    got = client.post(
        f"{client.base}/api/positions", json={"instrument_id": "NSE:AAA"}, headers=headers
    )
    assert got.status_code == 422


def test_close_preserves_the_record_and_delete_removes_it(client):
    headers = _headers(client)
    pid = _open(client, headers).json()["data"]["position_id"]

    closed = client.post(f"{client.base}/api/positions/{pid}/close", headers=headers)
    assert closed.status_code == 200
    assert client.get(
        f"{client.base}/api/positions", headers=headers
    ).json()["data"] == []
    kept = client.get(
        f"{client.base}/api/positions?open_only=false", headers=headers
    ).json()["data"]
    assert len(kept) == 1 and kept[0]["is_open"] is False

    assert client.delete(
        f"{client.base}/api/positions/{pid}", headers=headers
    ).status_code == 200
    assert client.get(
        f"{client.base}/api/positions?open_only=false", headers=headers
    ).json()["data"] == []


def test_closing_or_deleting_something_absent_is_404(client):
    headers = _headers(client)
    assert client.post(
        f"{client.base}/api/positions/nope/close", headers=headers
    ).status_code == 404
    assert client.delete(
        f"{client.base}/api/positions/nope", headers=headers
    ).status_code == 404


def test_position_responses_carry_the_experimental_label(client):
    headers = _headers(client)
    _open(client, headers)
    body = client.get(f"{client.base}/api/positions", headers=headers).json()
    assert body["darvax_status"] == "EXPERIMENTAL_UNVALIDATED"
    assert body["data"][0]["status"] == "EXPERIMENTAL_UNVALIDATED"


def test_writing_a_position_requires_more_than_read_permission(client):
    """Recording a holding changes what the advisor says on every future sweep,
    so it is an EXECUTE operation, not a READ one."""
    unauthenticated = client.post(
        f"{client.base}/api/positions",
        json={
            "instrument_id": "NSE:AAA",
            "quantity": 1,
            "entry_price": "1",
            "entry_date": "2026-08-01",
        },
    )
    assert unauthenticated.status_code in (401, 403)
