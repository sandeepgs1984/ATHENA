"""MP-NX6 owner-authored My Portfolio holding notes API tests."""

from __future__ import annotations

from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from tests.api.v1.test_core_apis import get_auth_headers
from tests.api.v1.test_my_portfolio_import_api import (
    _confirm_holdings,
    _confirm_infy_holding,
    _instrument,
)

from athena.api.app import create_app
from athena.api.config import APISettings
from athena.api.security.models import Role


@pytest.fixture()
def my_portfolio_client(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> TestClient:
    monkeypatch.setenv("ATHENA_DB_PATH", str(tmp_path / "athena.db"))
    app = create_app(APISettings())
    repo = app.state.sqlite_repo
    repo.upsert_instrument(_instrument("NSE:INFY", "INFY"))
    repo.upsert_instrument(_instrument("NSE:TCS", "TCS"))
    return TestClient(app, raise_server_exceptions=False)


def _put_note(client: TestClient, instrument_id: str, **fields: object) -> dict:
    response = client.put(
        f"/api/v1/my-portfolio/notes/{instrument_id}",
        headers=get_auth_headers(client, Role.OPERATOR),
        json=fields,
    )
    assert response.status_code == 200, response.text
    return response.json()["data"]


def test_put_get_and_list_owner_note(my_portfolio_client: TestClient) -> None:
    _confirm_infy_holding(my_portfolio_client)
    saved = _put_note(
        my_portfolio_client,
        "NSE:INFY",
        thesis="Hold through results.",
        watch_condition="Break of 1400",
        reminder="Re-read after results week",
        review_comment="Still matches the original thesis.",
        follow_up=True,
    )

    assert saved["instrument_id"] == "NSE:INFY"
    assert saved["present"] is True
    assert saved["owner_authored"] is True
    assert saved["thesis"] == "Hold through results."
    assert saved["watch_condition"] == "Break of 1400"
    assert saved["reminder"] == "Re-read after results week"
    assert saved["review_comment"] == "Still matches the original thesis."
    assert saved["follow_up"] is True
    assert saved["provenance"] == {"authored": True, "source": "owner"}
    assert saved["created_at"]
    assert saved["updated_at"]

    reader = get_auth_headers(my_portfolio_client, Role.READONLY, username="note-reader")
    fetched = my_portfolio_client.get(
        "/api/v1/my-portfolio/notes/NSE:INFY",
        headers=reader,
    )
    assert fetched.status_code == 200
    assert fetched.json()["data"]["thesis"] == "Hold through results."
    assert fetched.json()["data"]["present"] is True

    listed = my_portfolio_client.get("/api/v1/my-portfolio/notes", headers=reader)
    assert listed.status_code == 200
    notes = listed.json()["data"]
    assert [note["instrument_id"] for note in notes] == ["NSE:INFY"]
    assert notes[0]["follow_up"] is True


def test_get_missing_note_returns_present_false(my_portfolio_client: TestClient) -> None:
    _confirm_infy_holding(my_portfolio_client)
    response = my_portfolio_client.get(
        "/api/v1/my-portfolio/notes/NSE:INFY",
        headers=get_auth_headers(my_portfolio_client, Role.READONLY, username="empty-note"),
    )

    assert response.status_code == 200
    data = response.json()["data"]
    assert data["instrument_id"] == "NSE:INFY"
    assert data["present"] is False
    assert data["owner_authored"] is True
    assert data["thesis"] == ""
    assert data["follow_up"] is False


def test_empty_put_deletes_note(my_portfolio_client: TestClient) -> None:
    repo = _confirm_infy_holding(my_portfolio_client)
    _put_note(my_portfolio_client, "NSE:INFY", thesis="Keep watching.")
    assert repo.get_portfolio_holding_note("NSE:INFY") is not None

    cleared = _put_note(my_portfolio_client, "NSE:INFY")
    assert cleared["present"] is False
    assert repo.get_portfolio_holding_note("NSE:INFY") is None
    assert repo.get_portfolio_holding("NSE:INFY") is not None


def test_delete_note_leaves_holding(my_portfolio_client: TestClient) -> None:
    repo = _confirm_infy_holding(my_portfolio_client)
    _put_note(my_portfolio_client, "NSE:INFY", reminder="Check volume.")

    response = my_portfolio_client.delete(
        "/api/v1/my-portfolio/notes/NSE:INFY",
        headers=get_auth_headers(my_portfolio_client, Role.OPERATOR),
    )
    assert response.status_code == 200
    assert response.json()["data"]["present"] is False
    assert repo.get_portfolio_holding_note("NSE:INFY") is None
    assert repo.get_portfolio_holding("NSE:INFY") is not None


def test_note_requires_existing_holding(my_portfolio_client: TestClient) -> None:
    headers = get_auth_headers(my_portfolio_client, Role.OPERATOR)

    missing_get = my_portfolio_client.get(
        "/api/v1/my-portfolio/notes/NSE:INFY",
        headers=get_auth_headers(my_portfolio_client, Role.READONLY, username="missing-holding"),
    )
    missing_put = my_portfolio_client.put(
        "/api/v1/my-portfolio/notes/NSE:INFY",
        headers=headers,
        json={"thesis": "Should not persist."},
    )
    missing_delete = my_portfolio_client.delete(
        "/api/v1/my-portfolio/notes/NSE:INFY",
        headers=headers,
    )

    assert missing_get.status_code == 404
    assert missing_put.status_code == 404
    assert missing_delete.status_code == 404
    assert "portfolio holding not found" in missing_put.json()["detail"]


def test_readonly_cannot_write_notes(my_portfolio_client: TestClient) -> None:
    _confirm_infy_holding(my_portfolio_client)
    headers = get_auth_headers(my_portfolio_client, Role.READONLY, username="note-writer")

    put_response = my_portfolio_client.put(
        "/api/v1/my-portfolio/notes/NSE:INFY",
        headers=headers,
        json={"thesis": "Forbidden."},
    )
    delete_response = my_portfolio_client.delete(
        "/api/v1/my-portfolio/notes/NSE:INFY",
        headers=headers,
    )

    assert put_response.status_code == 403
    assert delete_response.status_code == 403


def test_delete_holding_also_deletes_note(my_portfolio_client: TestClient) -> None:
    repo = _confirm_infy_holding(my_portfolio_client)
    _put_note(my_portfolio_client, "NSE:INFY", thesis="Drop with the holding.")

    response = my_portfolio_client.delete(
        "/api/v1/my-portfolio/holdings/NSE:INFY",
        headers=get_auth_headers(my_portfolio_client, Role.OPERATOR),
    )
    assert response.status_code == 200
    assert repo.get_portfolio_holding("NSE:INFY") is None
    assert repo.get_portfolio_holding_note("NSE:INFY") is None

    missing = my_portfolio_client.get(
        "/api/v1/my-portfolio/notes/NSE:INFY",
        headers=get_auth_headers(my_portfolio_client, Role.READONLY, username="after-delete"),
    )
    assert missing.status_code == 404


def test_confirm_removed_drops_note(my_portfolio_client: TestClient) -> None:
    repo = _confirm_holdings(
        my_portfolio_client,
        b"Symbol,Qty,Avg Price\nINFY,10,1500\nTCS,5,3000\n",
    )
    _put_note(my_portfolio_client, "NSE:TCS", thesis="Remove with TCS.")
    assert repo.get_portfolio_holding_note("NSE:TCS") is not None

    _confirm_holdings(my_portfolio_client, b"Symbol,Qty,Avg Price\nINFY,10,1500\n")

    assert repo.get_portfolio_holding("NSE:TCS") is None
    assert repo.get_portfolio_holding_note("NSE:TCS") is None
    assert repo.get_portfolio_holding("NSE:INFY") is not None


def test_reset_clears_notes(my_portfolio_client: TestClient) -> None:
    repo = _confirm_infy_holding(my_portfolio_client)
    _put_note(my_portfolio_client, "NSE:INFY", follow_up=True)
    assert repo.list_portfolio_holding_notes()

    response = my_portfolio_client.request(
        "DELETE",
        "/api/v1/my-portfolio",
        headers=get_auth_headers(my_portfolio_client, Role.OPERATOR),
        json={"confirmation": "RESET"},
    )

    assert response.status_code == 200
    counts = response.json()["data"]["deleted_counts"]
    assert counts["portfolio_holding_notes"] == 1
    assert counts["portfolio_holdings"] == 1
    assert repo.list_portfolio_holding_notes() == []
    assert repo.list_portfolio_holdings() == []
