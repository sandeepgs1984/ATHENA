"""Health endpoint integration tests (P8.1)."""

from __future__ import annotations

from datetime import datetime, timezone

from fastapi.testclient import TestClient

from athena.api.v1.dtos.common import ComponentHealth, HealthResponse


class MockHealthProvider:
    """Mock HealthProvider for injection testing."""

    def __init__(
        self,
        status: str = "healthy",
        version: str = "0.2.0",
        components: list[ComponentHealth] | None = None,
    ) -> None:
        self.status = status
        self.version = version
        self.components = components or [
            ComponentHealth(name="mock", status="healthy", detail="all ok")
        ]

    def get_health(self) -> HealthResponse:
        return HealthResponse(
            status=self.status,  # type: ignore[arg-type]
            version=self.version,
            components=self.components,
            as_of=datetime.now(tz=timezone.utc),
        )


def test_health_returns_200(client: TestClient) -> None:
    response = client.get("/api/v1/health")
    assert response.status_code == 200


def test_health_envelope_structure(client: TestClient) -> None:
    response = client.get("/api/v1/health")
    json_data = response.json()

    assert json_data["status"] == "success"
    assert "data" in json_data
    assert "meta" in json_data
    assert json_data.get("pagination") is None
    assert json_data.get("links") is None


def test_health_data_contains_components(client: TestClient) -> None:
    response = client.get("/api/v1/health")
    data = response.json()["data"]

    assert "components" in data
    assert len(data["components"]) > 0
    for comp in data["components"]:
        assert "name" in comp
        assert "status" in comp
        assert "detail" in comp


def test_health_data_contains_version(client: TestClient) -> None:
    response = client.get("/api/v1/health")
    data = response.json()["data"]
    assert data["version"] == "0.1.0"


def test_health_meta_contains_request_id(client: TestClient) -> None:
    response = client.get("/api/v1/health")
    meta = response.json()["meta"]
    assert "request_id" in meta
    assert isinstance(meta["request_id"], str)
    assert len(meta["request_id"]) > 0


def test_health_meta_contains_api_version(client: TestClient) -> None:
    response = client.get("/api/v1/health")
    meta = response.json()["meta"]
    assert meta["api_version"] == "v1"


def test_health_request_id_in_response_header(client: TestClient) -> None:
    response = client.get("/api/v1/health")
    assert "X-Request-ID" in response.headers
    meta_req_id = response.json()["meta"]["request_id"]
    assert response.headers["X-Request-ID"] == meta_req_id


def test_health_links_field_absent_when_not_provided(client: TestClient) -> None:
    response = client.get("/api/v1/health")
    assert response.json().get("links") is None


def test_health_accepts_injected_provider(client: TestClient) -> None:
    # Inject a mock health provider
    mock_provider = MockHealthProvider(
        status="degraded",
        version="0.9.9",
        components=[
            ComponentHealth(name="mock_db", status="degraded", detail="slow")
        ],
    )
    client.app.state.health_provider = mock_provider  # type: ignore[attr-defined]

    response = client.get("/api/v1/health")
    assert response.status_code == 200
    json_data = response.json()

    assert json_data["data"]["status"] == "degraded"
    assert json_data["data"]["version"] == "0.9.9"
    assert json_data["data"]["components"][0]["name"] == "mock_db"
    assert json_data["data"]["components"][0]["status"] == "degraded"

    # Clean up state
    del client.app.state.health_provider  # type: ignore[attr-defined]
