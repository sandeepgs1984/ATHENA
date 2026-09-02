"""PS-P2 My Portfolio import/reconciliation API tests."""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from tests.api.v1.test_core_apis import get_auth_headers

from athena.api.app import create_app
from athena.api.config import APISettings
from athena.api.security.models import Role
from athena.api.v1.services.my_portfolio_service import MyPortfolioService
from athena.data.store.repository import SqliteRepository
from athena.domain.market import Instrument

NOW = datetime(2026, 9, 2, 10, 0, tzinfo=timezone.utc)


def _instrument(instrument_id: str, symbol: str, exchange: str = "NSE") -> Instrument:
    return Instrument(instrument_id=instrument_id, symbol=symbol, exchange=exchange, series="EQ")


@pytest.fixture()
def my_portfolio_client(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> TestClient:
    monkeypatch.setenv("ATHENA_DB_PATH", str(tmp_path / "athena.db"))
    app = create_app(APISettings())
    repo = app.state.sqlite_repo
    repo.upsert_instrument(_instrument("NSE:INFY", "INFY"))
    repo.upsert_instrument(_instrument("NSE:TCS", "TCS"))
    repo.upsert_instrument(_instrument("NSE:ABC", "ABC", exchange="NSE"))
    repo.upsert_instrument(_instrument("BSE:ABC", "ABC", exchange="BSE"))
    return TestClient(app, raise_server_exceptions=False)


def _preview(client: TestClient, csv_body: bytes, filename: str = "holdings.csv") -> dict:
    headers = get_auth_headers(client, Role.OPERATOR)
    response = client.post(
        "/api/v1/my-portfolio/imports",
        params={"filename": filename},
        headers=headers,
        content=csv_body,
    )
    assert response.status_code == 201
    return response.json()["data"]


def test_import_preview_persists_rows_and_does_not_mutate_holdings(my_portfolio_client: TestClient) -> None:
    data = _preview(
        my_portfolio_client,
        b"Symbol,Qty,Avg Price\nINFY,10,1500\nUNKNOWN,2,3\nABC,1,1\n",
    )

    assert data["status"] == "PREVIEWED"
    assert data["total_rows"] == 3
    assert data["accepted_rows"] == 1
    assert data["unresolved_rows"] == 1
    assert data["ambiguous_rows"] == 1
    assert data["rows"][0]["resolved_instrument_id"] == "NSE:INFY"

    headers = get_auth_headers(my_portfolio_client, Role.READONLY, username="reader")
    holdings = my_portfolio_client.get("/api/v1/my-portfolio/holdings", headers=headers)
    assert holdings.status_code == 200
    assert holdings.json()["data"] == []

    detail = my_portfolio_client.get(
        f"/api/v1/my-portfolio/imports/{data['import_id']}",
        headers=headers,
    )
    assert detail.status_code == 200
    assert detail.json()["data"]["rows"][1]["mapping_state"] == "UNRESOLVED"


def test_clean_import_confirm_applies_holdings_and_audit_idempotently(my_portfolio_client: TestClient) -> None:
    data = _preview(my_portfolio_client, b"Symbol,Qty,Avg Price\nINFY,10,1500\n")
    headers = get_auth_headers(my_portfolio_client, Role.OPERATOR)

    first = my_portfolio_client.post(
        f"/api/v1/my-portfolio/imports/{data['import_id']}/confirm",
        headers=headers,
        json={"import_id": data["import_id"], "confirmation": "CONFIRM"},
    )
    assert first.status_code == 200
    body = first.json()["data"]
    assert body["already_confirmed"] is False
    assert body["holdings"][0]["instrument_id"] == "NSE:INFY"
    assert body["holdings"][0]["quantity"] == 10
    assert body["holdings"][0]["investment"] == "15000"
    assert body["reconciliation"][0]["action"] == "ADDED"

    second = my_portfolio_client.post(
        f"/api/v1/my-portfolio/imports/{data['import_id']}/confirm",
        headers=headers,
        json={"import_id": data["import_id"], "confirmation": "CONFIRM"},
    )
    assert second.status_code == 200
    assert second.json()["data"]["already_confirmed"] is True

    audit = my_portfolio_client.get(
        f"/api/v1/my-portfolio/imports/{data['import_id']}/reconciliations",
        headers=get_auth_headers(my_portfolio_client, Role.READONLY, username="audit"),
    )
    assert audit.status_code == 200
    assert len(audit.json()["data"]) == 1


def test_reconciliation_reports_updated_removed_and_unchanged(my_portfolio_client: TestClient) -> None:
    headers = get_auth_headers(my_portfolio_client, Role.OPERATOR)
    initial = _preview(my_portfolio_client, b"Symbol,Qty,Avg Price\nINFY,10,1500\nTCS,5,3000\n")
    my_portfolio_client.post(
        f"/api/v1/my-portfolio/imports/{initial['import_id']}/confirm",
        headers=headers,
        json={"import_id": initial["import_id"], "confirmation": "CONFIRM"},
    )

    next_preview = _preview(my_portfolio_client, b"Symbol,Qty,Avg Price\nINFY,10,1500\n")
    actions = {item["instrument_id"]: item["action"] for item in next_preview["proposed_changes"]}

    assert actions["NSE:INFY"] == "UNCHANGED"
    assert actions["NSE:TCS"] == "REMOVED"

    my_portfolio_client.post(
        f"/api/v1/my-portfolio/imports/{next_preview['import_id']}/confirm",
        headers=headers,
        json={"import_id": next_preview["import_id"], "confirmation": "CONFIRM"},
    )
    holdings = my_portfolio_client.get(
        "/api/v1/my-portfolio/holdings",
        headers=get_auth_headers(my_portfolio_client, Role.READONLY, username="holdings"),
    ).json()["data"]
    assert [holding["instrument_id"] for holding in holdings] == ["NSE:INFY"]


def test_invalid_duplicate_and_stale_previews_are_rejected(my_portfolio_client: TestClient) -> None:
    duplicate = _preview(my_portfolio_client, b"Symbol,Qty,Avg Price\nINFY,10,1500\nINFY,2,1600\n")
    assert "DUPLICATE_CANONICAL_INSTRUMENT" in duplicate["rows"][0]["validation_errors"]

    headers = get_auth_headers(my_portfolio_client, Role.OPERATOR)
    invalid_confirm = my_portfolio_client.post(
        f"/api/v1/my-portfolio/imports/{duplicate['import_id']}/confirm",
        headers=headers,
        json={"import_id": duplicate["import_id"], "confirmation": "CONFIRM"},
    )
    assert invalid_confirm.status_code == 400

    old = _preview(my_portfolio_client, b"Symbol,Qty,Avg Price\nINFY,10,1500\n")
    newer = _preview(my_portfolio_client, b"Symbol,Qty,Avg Price\nTCS,1,3000\n")
    my_portfolio_client.post(
        f"/api/v1/my-portfolio/imports/{newer['import_id']}/confirm",
        headers=headers,
        json={"import_id": newer["import_id"], "confirmation": "CONFIRM"},
    )
    stale = my_portfolio_client.post(
        f"/api/v1/my-portfolio/imports/{old['import_id']}/confirm",
        headers=headers,
        json={"import_id": old["import_id"], "confirmation": "CONFIRM"},
    )
    assert stale.status_code == 409
    assert "STALE_PREVIEW" in stale.json()["detail"]


def test_confirm_rolls_back_when_audit_insert_fails(tmp_path: Path) -> None:
    repo = SqliteRepository(tmp_path / "athena.db")
    repo.initialize()
    repo.upsert_instrument(_instrument("NSE:INFY", "INFY"))
    service = MyPortfolioService(repo)
    preview = service.preview_import(filename="holdings.csv", content=b"Symbol,Qty,Avg Price\nINFY,10,1500\n")
    repo._conn.execute(  # type: ignore[attr-defined]
        """
        CREATE TRIGGER fail_portfolio_reconciliation_insert
        AFTER INSERT ON portfolio_reconciliations
        BEGIN
            SELECT RAISE(ABORT, 'forced audit failure');
        END
        """
    )

    with pytest.raises(Exception, match="forced audit failure"):
        service.confirm_import(import_id=preview.import_id, confirmation="CONFIRM")

    assert repo.get_portfolio_import(preview.import_id)["status"] == "PREVIEWED"
    assert repo.list_portfolio_holdings() == []
    assert repo.list_portfolio_reconciliations(preview.import_id) == []
    repo.close()
