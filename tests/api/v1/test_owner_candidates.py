"""Owner validation candidate list API tests (D-V1)."""

from __future__ import annotations

from fastapi.testclient import TestClient

from athena.api.security.models import Role
from tests.api.v1.test_core_apis import get_auth_headers


class TestOwnerCandidatesAPI:
    def test_crud_normalize_and_list(self, client: TestClient) -> None:
        headers = get_auth_headers(client, Role.OPERATOR)
        create = client.post(
            "/api/v1/market/candidates",
            headers=headers,
            json={"symbol": "nse:infy", "notes": "core"},
        )
        assert create.status_code == 201
        assert create.json()["data"]["symbol"] == "INFY"

        listed = client.get("/api/v1/market/candidates", headers=headers)
        assert listed.status_code == 200
        body = listed.json()["data"]
        assert body["count"] == 1
        assert body["candidates"][0]["symbol"] == "INFY"

        put = client.put(
            "/api/v1/market/candidates",
            headers=headers,
            json={"symbol": "RELIANCE"},
        )
        assert put.status_code == 200
        assert put.json()["data"]["symbol"] == "RELIANCE"

        listed2 = client.get("/api/v1/market/candidates", headers=headers)
        assert listed2.json()["data"]["count"] == 2

        deleted = client.delete("/api/v1/market/candidates/INFY", headers=headers)
        assert deleted.status_code == 200
        assert deleted.json()["data"]["deleted"] is True

        listed3 = client.get("/api/v1/market/candidates", headers=headers)
        symbols = [c["symbol"] for c in listed3.json()["data"]["candidates"]]
        assert symbols == ["RELIANCE"]

    def test_delete_missing_404(self, client: TestClient) -> None:
        headers = get_auth_headers(client, Role.OPERATOR)
        resp = client.delete("/api/v1/market/candidates/NOSUCH", headers=headers)
        assert resp.status_code == 404

    def test_mutate_requires_execute(self, client: TestClient) -> None:
        headers = get_auth_headers(client, Role.READONLY)
        resp = client.post(
            "/api/v1/market/candidates",
            headers=headers,
            json={"symbol": "INFY"},
        )
        assert resp.status_code == 403
