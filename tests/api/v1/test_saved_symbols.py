"""Owner-curated "Saved Symbols" watch list API tests (UX-9b)."""

from __future__ import annotations

from fastapi.testclient import TestClient
from tests.api.v1.test_core_apis import get_auth_headers

from athena.api.security.models import Role


class TestSavedSymbolsAPI:
    def test_add_normalize_list_and_remove(self, client: TestClient) -> None:
        headers = get_auth_headers(client, Role.OPERATOR)
        added = client.post(
            "/api/v1/saved-symbols",
            headers=headers,
            json={"symbol": "nse:infy", "notes": "core holding"},
        )
        assert added.status_code == 201
        assert added.json()["data"]["symbol"] == "INFY"

        listed = client.get("/api/v1/saved-symbols", headers=headers)
        assert listed.status_code == 200
        body = listed.json()["data"]
        assert body["count"] == 1
        assert body["symbols"][0]["symbol"] == "INFY"
        assert body["symbols"][0]["notes"] == "core holding"

        added2 = client.post(
            "/api/v1/saved-symbols",
            headers=headers,
            json={"symbol": "RELIANCE"},
        )
        assert added2.status_code == 201

        listed2 = client.get("/api/v1/saved-symbols", headers=headers)
        assert listed2.json()["data"]["count"] == 2

        deleted = client.delete("/api/v1/saved-symbols/INFY", headers=headers)
        assert deleted.status_code == 200
        assert deleted.json()["data"]["deleted"] is True

        listed3 = client.get("/api/v1/saved-symbols", headers=headers)
        symbols = [s["symbol"] for s in listed3.json()["data"]["symbols"]]
        assert symbols == ["RELIANCE"]

    def test_re_adding_same_symbol_updates_in_place_not_duplicates(
        self, client: TestClient
    ) -> None:
        headers = get_auth_headers(client, Role.OPERATOR)
        client.post("/api/v1/saved-symbols", headers=headers, json={"symbol": "INFY"})
        client.post(
            "/api/v1/saved-symbols",
            headers=headers,
            json={"symbol": "infy", "notes": "updated note"},
        )
        listed = client.get("/api/v1/saved-symbols", headers=headers)
        body = listed.json()["data"]
        assert body["count"] == 1
        assert body["symbols"][0]["notes"] == "updated note"

    def test_delete_missing_404(self, client: TestClient) -> None:
        headers = get_auth_headers(client, Role.OPERATOR)
        resp = client.delete("/api/v1/saved-symbols/NOSUCH", headers=headers)
        assert resp.status_code == 404

    def test_mutate_requires_execute(self, client: TestClient) -> None:
        headers = get_auth_headers(client, Role.READONLY)
        resp = client.post(
            "/api/v1/saved-symbols",
            headers=headers,
            json={"symbol": "INFY"},
        )
        assert resp.status_code == 403

    def test_list_requires_read(self, client: TestClient) -> None:
        # No auth header at all — unauthenticated request must be rejected,
        # never silently returned as an empty list.
        resp = client.get("/api/v1/saved-symbols")
        assert resp.status_code in (401, 403)

    def test_saved_symbols_independent_of_owner_candidates(
        self, client: TestClient
    ) -> None:
        """Saving a symbol must not add it to (or remove it from) the
        unrelated owner-candidates validation list, and vice versa —
        the two lists are deliberately independent domains."""
        headers = get_auth_headers(client, Role.OPERATOR)
        client.post("/api/v1/saved-symbols", headers=headers, json={"symbol": "TCS"})
        client.post(
            "/api/v1/market/candidates", headers=headers, json={"symbol": "WIPRO"}
        )

        saved = client.get("/api/v1/saved-symbols", headers=headers).json()["data"]
        candidates = client.get("/api/v1/market/candidates", headers=headers).json()["data"]

        saved_symbols = [s["symbol"] for s in saved["symbols"]]
        candidate_symbols = [c["symbol"] for c in candidates["candidates"]]
        assert saved_symbols == ["TCS"]
        assert "WIPRO" not in saved_symbols
        assert "TCS" not in candidate_symbols
