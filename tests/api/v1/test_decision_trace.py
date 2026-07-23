"""Integration tests for P9.6 Decision Trace API."""

from __future__ import annotations

from datetime import datetime, timezone
import pytest
from fastapi.testclient import TestClient

from athena.api.dependencies import get_decision_provider
from athena.api.security.models import Role
from athena.domain.decision import Decision
from athena.domain.enums import DecisionType, Direction
from tests.api.v1.test_core_apis import get_auth_headers


@pytest.fixture(autouse=True)
def clean_decision_provider() -> None:
    """Reset decisions provider before each test."""
    p = get_decision_provider()
    p.decisions.clear()  # type: ignore[attr-defined]


class TestDecisionTraceAPI:
    def test_get_trace_requires_auth(self, client: TestClient) -> None:
        response = client.get("/api/v1/decisions/dec-sample-1/trace")
        assert response.status_code == 401

    def test_get_trace_success(self, client: TestClient) -> None:
        headers = get_auth_headers(client, Role.READONLY)
        p = get_decision_provider()
        
        now = datetime.now(tz=timezone.utc)
        dec = Decision(
            decision_id="dec-1",
            ts=now,
            run_id="run-1",
            cycle_id="cycle-1",
            instrument_id="SBIN",
            direction=Direction.LONG,
            decision_type=DecisionType.WATCH,
            explanation="Volume expansion near support.",
        )
        p.decisions.append(dec)  # type: ignore[attr-defined]

        response = client.get("/api/v1/decisions/dec-1/trace", headers=headers)
        assert response.status_code == 200
        
        data = response.json()
        assert data["status"] == "success"
        trace = data["data"]
        
        assert trace["decision_id"] == "dec-1"
        assert trace["instrument_id"] == "SBIN"
        assert len(trace["stages"]) == 7
        
        # Verify stages ordering and names
        stages = trace["stages"]
        assert stages[0]["stage_id"] == "universe_ingest"
        assert stages[0]["name"] == "Universe Ingestion"
        assert stages[0]["status"] == "COMPLETED"
        assert "instrument_id" in stages[0]["details"]
        
        assert stages[2]["stage_id"] == "scoring_engine"
        assert stages[2]["name"] == "Scoring Engine"
        
        assert stages[6]["stage_id"] == "final_decision"
        assert stages[6]["name"] == "Final Recommendation"
        assert stages[6]["details"]["decision_type"] == "WATCH"

    def test_get_trace_not_found(self, client: TestClient) -> None:
        headers = get_auth_headers(client, Role.ANALYST)
        response = client.get("/api/v1/decisions/dec-invalid/trace", headers=headers)
        assert response.status_code == 404
        assert response.json()["title"] == "Decision Not Found"
