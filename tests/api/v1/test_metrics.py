"""Metrics endpoint integration tests (P8.1)."""

from __future__ import annotations

from datetime import datetime, timezone

from fastapi.testclient import TestClient

from athena.api.v1.dtos.common import MetricsResponse


class MockMetricsProvider:
    """Mock MetricsProvider for injection testing."""

    def __init__(self, pipeline_runs: int = 42, uptime: float = 123.45) -> None:
        self.pipeline_runs = pipeline_runs
        self.uptime = uptime

    def get_metrics(self) -> MetricsResponse:
        return MetricsResponse(
            pipeline_runs_total=self.pipeline_runs,
            pipeline_runs_succeeded=self.pipeline_runs,
            pipeline_runs_failed=0,
            schedule_runs_total=0,
            schedule_runs_succeeded=0,
            schedule_runs_failed=0,
            uptime_seconds=self.uptime,
            as_of=datetime.now(tz=timezone.utc),
        )


def test_metrics_returns_200(client: TestClient) -> None:
    response = client.get("/api/v1/metrics")
    assert response.status_code == 200


def test_metrics_envelope_structure(client: TestClient) -> None:
    response = client.get("/api/v1/metrics")
    json_data = response.json()

    assert json_data["status"] == "success"
    assert "data" in json_data
    assert "meta" in json_data
    assert json_data.get("pagination") is None
    assert json_data.get("links") is None


def test_metrics_data_schema(client: TestClient) -> None:
    response = client.get("/api/v1/metrics")
    data = response.json()["data"]

    assert "pipeline_runs_total" in data
    assert "pipeline_runs_succeeded" in data
    assert "pipeline_runs_failed" in data
    assert "schedule_runs_total" in data
    assert "uptime_seconds" in data
    assert "as_of" in data


def test_metrics_meta_contains_request_id(client: TestClient) -> None:
    response = client.get("/api/v1/metrics")
    meta = response.json()["meta"]
    assert "request_id" in meta
    assert len(meta["request_id"]) > 0


def test_metrics_accepts_injected_provider(client: TestClient) -> None:
    mock_provider = MockMetricsProvider(pipeline_runs=99, uptime=999.9)
    client.app.state.metrics_provider = mock_provider  # type: ignore[attr-defined]

    response = client.get("/api/v1/metrics")
    assert response.status_code == 200
    data = response.json()["data"]

    assert data["pipeline_runs_total"] == 99
    assert data["pipeline_runs_succeeded"] == 99
    assert data["uptime_seconds"] == 999.9

    del client.app.state.metrics_provider  # type: ignore[attr-defined]
