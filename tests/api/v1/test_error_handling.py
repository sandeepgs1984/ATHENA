"""Error handling and exception mapping integration tests (P8.1)."""

from __future__ import annotations

from fastapi.testclient import TestClient

from athena.api.errors import ExceptionMapping, ProblemDetail, exception_mapper
from athena.api.v1.dtos.common import HealthResponse
from athena.errors import AthenaError, DataStaleError, ProviderError


class ErrorRaisingHealthProvider:
    """Mock HealthProvider designed to raise specific exceptions for mapping tests."""

    def __init__(self, exception: Exception) -> None:
        self.exception = exception

    def get_health(self) -> HealthResponse:
        raise self.exception


def test_404_returns_problem_detail(client: TestClient) -> None:
    response = client.get("/api/v1/nonexistent-route")
    assert response.status_code == 404
    json_data = response.json()

    assert "type" in json_data
    assert "title" in json_data
    assert json_data["status"] == 404
    assert "detail" in json_data
    assert json_data["instance"] == "/api/v1/nonexistent-route"
    assert "request_id" in json_data


def test_problem_detail_schema_complete(client: TestClient) -> None:
    # Trigger a 404
    response = client.get("/api/v1/nonexistent-route")
    json_data = response.json()

    # Verify RFC 9457 fields
    assert isinstance(json_data["type"], str)
    assert isinstance(json_data["title"], str)
    assert json_data["status"] == 404
    assert isinstance(json_data["detail"], str)
    assert isinstance(json_data["instance"], str)
    assert isinstance(json_data["request_id"], str)


def test_request_id_in_error_response(client: TestClient) -> None:
    response = client.get("/api/v1/nonexistent-route")
    assert "X-Request-ID" in response.headers
    assert response.json()["request_id"] == response.headers["X-Request-ID"]


def test_500_does_not_leak_stack_trace(client: TestClient) -> None:
    # Set up provider to raise generic Exception
    client.app.state.health_provider = ErrorRaisingHealthProvider(
        RuntimeError("Database blew up with stack trace info")
    )  # type: ignore[attr-defined]

    response = client.get("/api/v1/health")
    assert response.status_code == 500
    json_data = response.json()

    assert json_data["title"] == "Unexpected Internal Error"
    # Ensure raw detail isn't displaying a traceback, just the stringified exception or title
    assert "Traceback" not in json_data["detail"]
    assert "Database blew up" in json_data["detail"]

    del client.app.state.health_provider  # type: ignore[attr-defined]


def test_validation_error_returns_422(client: TestClient) -> None:
    # Trigger a validation error by passing invalid query parameter type
    # For example page=abc (should be int) on a dummy query param if we had one.
    # We can request health with a dummy param if FastAPI accepts extra params,
    # or we can construct a dummy endpoint for validation check.
    # Let's add a quick test route to client.app for validation check.
    @client.app.get("/api/v1/test-validation")
    def dummy_route(page: int) -> dict:
        return {"page": page}

    response = client.get("/api/v1/test-validation?page=abc")
    assert response.status_code == 422
    json_data = response.json()

    assert json_data["title"] == "Validation Failed"
    assert "validation_errors" in json_data
    assert len(json_data["validation_errors"]) > 0
    assert "page" in json_data["detail"]


def test_athena_error_mapped_to_500(client: TestClient) -> None:
    client.app.state.health_provider = ErrorRaisingHealthProvider(
        AthenaError("Standard internal engine failure")
    )  # type: ignore[attr-defined]

    response = client.get("/api/v1/health")
    assert response.status_code == 500
    assert response.json()["title"] == "Internal Domain Error"

    del client.app.state.health_provider  # type: ignore[attr-defined]


def test_data_stale_error_mapped_to_503(client: TestClient) -> None:
    client.app.state.health_provider = ErrorRaisingHealthProvider(
        DataStaleError("Market feed delayed by 15 mins")
    )  # type: ignore[attr-defined]

    response = client.get("/api/v1/health")
    assert response.status_code == 503
    assert response.json()["title"] == "Data Stale"

    del client.app.state.health_provider  # type: ignore[attr-defined]


def test_provider_error_mapped_to_502(client: TestClient) -> None:
    client.app.state.health_provider = ErrorRaisingHealthProvider(
        ProviderError("NSE API rate limited")
    )  # type: ignore[attr-defined]

    response = client.get("/api/v1/health")
    assert response.status_code == 502
    assert response.json()["title"] == "Provider Unavailable"

    del client.app.state.health_provider  # type: ignore[attr-defined]


def test_value_error_mapped_to_400(client: TestClient) -> None:
    client.app.state.health_provider = ErrorRaisingHealthProvider(
        ValueError("Invalid format")
    )  # type: ignore[attr-defined]

    response = client.get("/api/v1/health")
    assert response.status_code == 400
    assert response.json()["title"] == "Bad Request"

    del client.app.state.health_provider  # type: ignore[attr-defined]


class CustomDummyError(Exception):
    pass


def test_exception_mapper_registry_extensible(client: TestClient) -> None:
    # Register custom exception mapping
    mapping = ExceptionMapping(
        CustomDummyError, 418, "teapot-error", "I am a teapot"
    )
    exception_mapper.register(mapping)

    # Classify custom exception
    detail = exception_mapper.classify(
        CustomDummyError("brewing"), "/api/v1/teapot", "req-teapot"
    )
    assert isinstance(detail, ProblemDetail)
    assert detail.status == 418
    assert detail.title == "I am a teapot"
    assert detail.type == "https://athena.internal/errors/teapot-error"
