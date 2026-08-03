"""GET /market/opportunities router test (Top Opportunities Today)."""

from __future__ import annotations

from fastapi.testclient import TestClient
from tests.api.v1.test_core_apis import get_auth_headers

from athena.api.security.models import Role
from athena.data.store.repository import SqliteRepository


def test_opportunities_endpoint_requires_auth_and_returns_expected_shape(
    client: TestClient, tmp_path,
) -> None:
    repo = SqliteRepository(tmp_path / "router-opp.db")
    repo.initialize()
    client.app.state.sqlite_repo = repo

    unauthenticated = client.get("/api/v1/market/opportunities")
    assert unauthenticated.status_code == 401

    headers = get_auth_headers(client, Role.READONLY)
    ok = client.get("/api/v1/market/opportunities", headers=headers)
    assert ok.status_code == 200
    data = ok.json()["data"]
    assert "summary" in data
    assert "sectors" in data
    assert "removed" in data
    assert "as_of" in data
    assert data["sectors"] == []  # empty repo -> no qualified opportunities
    repo.close()


def test_opportunities_endpoint_accepts_count_query_params(
    client: TestClient, tmp_path,
) -> None:
    repo = SqliteRepository(tmp_path / "router-opp2.db")
    repo.initialize()
    client.app.state.sqlite_repo = repo

    headers = get_auth_headers(client, Role.READONLY)
    ok = client.get(
        "/api/v1/market/opportunities?sector_count=3&symbols_per_sector=1",
        headers=headers,
    )
    assert ok.status_code == 200

    bad = client.get("/api/v1/market/opportunities?sector_count=0", headers=headers)
    assert bad.status_code == 422
    repo.close()
