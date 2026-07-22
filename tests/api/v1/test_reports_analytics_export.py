"""Integration tests for P8.4 Reports, Analytics & Export APIs.

Covers:
- Paginated/sorted reports list and detail views
- Reports error mapping and versioning metadata
- Portfolio performance snapshots query and detail views
- Analytics provenance tracking using ResourceReference links
- Batch export snapshots list, details, and artifacts retrieval
- Dynamic export format generation (JSON/CSV/Markdown/Text) jobs
- Idempotency key header acceptance
- Security checks, authentication, and RBAC permission enforcement
"""

from __future__ import annotations

import hashlib
from datetime import datetime, timedelta, timezone
from decimal import Decimal

import pytest
from fastapi.testclient import TestClient

from athena.api.dependencies import (
    get_export_query_provider,
    get_performance_analytics_provider,
    get_report_provider,
)
from athena.api.security.dependencies import (
    get_api_key_repository,
    get_session_store,
    get_user_repository,
)
from athena.api.security.models import (
    ROLE_PERMISSIONS,
    APIKeyMetadata,
    AuthenticatedPrincipal,
    Permission,
    Role,
    Session,
    User,
)
from athena.analytics.portfolio.models import (
    AnalyticsSummary,
    PerformanceSnapshot,
    PortfolioAnalyticsReferences,
    PortfolioPerformance,
    TradePerformance,
)
from athena.config.models import ExportFormat, ReportType
from athena.domain.decision import Direction
from athena.export.models import ExportArtifact, ExportReferences, ExportSnapshot, ExportSummary
from athena.reporting.models import GenericReport, ReportingReferences


def get_auth_headers(client: TestClient, role: Role, username: str = "analyst") -> dict[str, str]:
    """Helper to generate JWT bearer headers for a given role."""
    app = client.app
    user = User(user_id=f"usr-{username}", username=username, password_hash="hash", role=role)
    get_user_repository().save(user)

    session = Session(
        session_id=f"sess-test-{username}",
        user_id=user.user_id,
        refresh_token_hash="hash",
        created_at=datetime.now(tz=timezone.utc),
        expires_at=datetime.now(tz=timezone.utc) + timedelta(days=1),
        is_revoked=False,
    )
    get_session_store().save(session)

    permissions = ROLE_PERMISSIONS[role]
    principal = AuthenticatedPrincipal(
        user_id=user.user_id,
        username=user.username,
        role=user.role,
        permissions=permissions,
    )

    claims = app.state.claims_factory.create_claims(
        principal=principal,
        token_type="access",
        session_id=session.session_id,
        now=datetime.now(tz=timezone.utc),
    )
    token = app.state.token_signer.encode(claims.to_dict())
    return {"Authorization": f"Bearer {token}"}


def get_forbidden_api_key_headers(client: TestClient) -> dict[str, str]:
    """Helper to generate X-API-Key with EXECUTE only permissions to trigger 403."""
    user = User(user_id="usr-forbidden", username="forbidden", password_hash="hash", role=Role.ANALYST)
    get_user_repository().save(user)

    raw_secret = "forbidden_secret_value"
    hashed_secret = hashlib.sha256(raw_secret.encode()).hexdigest()

    key_meta = APIKeyMetadata(
        key_id="key-forbidden",
        owner_id=user.user_id,
        key_hash=hashed_secret,
        name="Forbidden Key",
        permissions=(Permission.EXECUTE,),  # Excludes READ to trigger 403
        is_active=True,
        created_at=datetime.now(tz=timezone.utc),
        expires_at=datetime.now(tz=timezone.utc) + timedelta(days=1),
    )
    get_api_key_repository().save(key_meta)
    return {"X-API-Key": f"key-forbidden.{raw_secret}"}


# ---------------------------------------------------------------------------
# Reports Endpoint Tests
# ---------------------------------------------------------------------------

def test_list_reports(client: TestClient) -> None:
    """Test retrieving paginated list of generic reports."""
    headers = get_auth_headers(client, Role.ANALYST)
    response = client.get("/api/v1/reports?page=1&page_size=10", headers=headers)
    assert response.status_code == 200

    payload = response.json()
    assert payload["status"] == "success"
    assert "data" in payload
    assert len(payload["data"]) >= 1

    # Verify summary DTO omits "content" but exposes metadata, text_summary, and references
    item = payload["data"][0]
    assert "metadata" in item
    assert "text_summary" in item
    assert "references" in item
    assert "content" not in item

    meta = item["metadata"]
    assert meta["report_id"] == "rep-sample-1"
    assert meta["report_version"] == 1
    assert "source_snapshot_reference" in meta


def test_get_report_details(client: TestClient) -> None:
    """Test retrieving complete report details including structured content."""
    headers = get_auth_headers(client, Role.ANALYST)
    response = client.get("/api/v1/reports/rep-sample-1", headers=headers)
    assert response.status_code == 200

    payload = response.json()
    assert payload["status"] == "success"
    data = payload["data"]
    assert data["metadata"]["report_id"] == "rep-sample-1"
    assert "content" in data
    assert data["content"]["cash"] == "50000.00"
    assert data["references"]["portfolio_snapshot_ref"]["id"] == "ws-sample-1"


def test_get_report_not_found(client: TestClient) -> None:
    """Test getting nonexistent report maps to RFC 9457 Problem Details (404)."""
    headers = get_auth_headers(client, Role.ANALYST)
    response = client.get("/api/v1/reports/rep-nonexistent", headers=headers)
    assert response.status_code == 404

    payload = response.json()
    assert "type" in payload
    assert payload["title"] == "Report Not Found"
    assert payload["status"] == 404
    assert "rep-nonexistent" in payload["detail"]


# ---------------------------------------------------------------------------
# Analytics Endpoint Tests
# ---------------------------------------------------------------------------

def test_list_performance_snapshots(client: TestClient) -> None:
    """Test retrieving paginated portfolio analytics performance snapshots."""
    headers = get_auth_headers(client, Role.ANALYST)
    response = client.get("/api/v1/analytics/performance/snapshots?page=1&page_size=5", headers=headers)
    assert response.status_code == 200

    payload = response.json()
    assert payload["status"] == "success"
    assert len(payload["data"]) >= 1

    item = payload["data"][0]
    assert item["snapshot_id"] == "perfsnap-sample-1"
    assert "portfolio_performance" in item
    assert "summary" in item
    assert "provenance" in item
    assert "trade_performances" not in item  # Omitted in summary listings


def test_get_performance_snapshot_details(client: TestClient) -> None:
    """Test retrieving detailed analytics snapshot containing complete trade history."""
    headers = get_auth_headers(client, Role.ANALYST)
    response = client.get("/api/v1/analytics/performance/snapshots/perfsnap-sample-1", headers=headers)
    assert response.status_code == 200

    payload = response.json()
    assert payload["status"] == "success"
    data = payload["data"]
    assert data["snapshot_id"] == "perfsnap-sample-1"
    assert len(data["trade_performances"]) == 1
    assert data["trade_performances"][0]["trade_id"] == "trd-sample-1"

    # Verify provenance references
    trade_prov = data["trade_performances"][0]["provenance"]
    assert trade_prov["decision_ref"]["id"] == "dec-sample-1"

    prov = data["provenance"]
    assert prov["decision_ref"] is None
    assert prov["portfolio_ref"]["id"] == "ws-sample-1"


def test_get_performance_snapshot_not_found(client: TestClient) -> None:
    """Test nonexistent analytics snapshot maps to HTTP 404."""
    headers = get_auth_headers(client, Role.ANALYST)
    response = client.get("/api/v1/analytics/performance/snapshots/perfsnap-nonexistent", headers=headers)
    assert response.status_code == 404

    payload = response.json()
    assert payload["title"] == "Performance Snapshot Not Found"
    assert payload["status"] == 404


# ---------------------------------------------------------------------------
# Exports Endpoint Tests
# ---------------------------------------------------------------------------

def test_list_export_snapshots(client: TestClient) -> None:
    """Test retrieving export snapshots summaries listing."""
    headers = get_auth_headers(client, Role.ANALYST)
    response = client.get("/api/v1/exports/snapshots?page=1&page_size=5", headers=headers)
    assert response.status_code == 200

    payload = response.json()
    assert payload["status"] == "success"
    assert len(payload["data"]) >= 1

    item = payload["data"][0]
    assert item["snapshot_id"] == "expsnap-sample-1"
    assert "summary" in item
    assert item["summary"]["total_exports"] == 1
    assert "exports" not in item  # Omitted in summary listing


def test_get_export_snapshot_details(client: TestClient) -> None:
    """Test retrieving export snapshot details including exports array."""
    headers = get_auth_headers(client, Role.ANALYST)
    response = client.get("/api/v1/exports/snapshots/expsnap-sample-1", headers=headers)
    assert response.status_code == 200

    payload = response.json()
    assert payload["status"] == "success"
    data = payload["data"]
    assert data["snapshot_id"] == "expsnap-sample-1"
    assert len(data["exports"]) == 1
    assert data["exports"][0]["metadata"]["artifact_id"] == "exp-sample-1"
    assert data["exports"][0]["metadata"]["format"] == "JSON"


def test_get_export_artifact(client: TestClient) -> None:
    """Test retrieving specific export artifact payload contents."""
    headers = get_auth_headers(client, Role.ANALYST)
    response = client.get("/api/v1/exports/artifacts/exp-sample-1", headers=headers)
    assert response.status_code == 200

    payload = response.json()
    assert payload["status"] == "success"
    data = payload["data"]
    assert "metadata" in data
    assert data["metadata"]["artifact_id"] == "exp-sample-1"
    assert data["metadata"]["artifact_type"] == "REPORT"
    assert "report_rep-sample-1.json" in data["metadata"]["filename"]
    assert "Sample Portfolio Status Report" in data["payload"]


def test_get_export_artifact_not_found(client: TestClient) -> None:
    """Test nonexistent export artifact returns HTTP 404."""
    headers = get_auth_headers(client, Role.ANALYST)
    response = client.get("/api/v1/exports/artifacts/exp-nonexistent", headers=headers)
    assert response.status_code == 404

    payload = response.json()
    assert payload["title"] == "Export Artifact Not Found"


def test_create_export_job(client: TestClient) -> None:
    """Test dynamic, on-demand export generation job creation."""
    headers = get_auth_headers(client, Role.ANALYST)
    req_body = {
        "source": {
            "artifact_id": "rep-sample-1",
            "artifact_type": "REPORT"
        },
        "format": "JSON",
        "options": {"options": {"pretty": True}}
    }
    
    # Send request with optional idempotency key
    response = client.post(
        "/api/v1/exports",
        json=req_body,
        headers={**headers, "X-Idempotency-Key": "idem-key-123"}
    )
    assert response.status_code == 202

    payload = response.json()
    assert payload["status"] == "success"
    data = payload["data"]
    assert "job_id" in data
    assert data["status"] == "COMPLETED"
    assert data["result_artifact_id"] is not None

    # Retrieve generated artifact to verify it exists and is queryable
    art_id = data["result_artifact_id"]
    art_resp = client.get(f"/api/v1/exports/artifacts/{art_id}", headers=headers)
    assert art_resp.status_code == 200
    art_data = art_resp.json()["data"]
    assert art_data["metadata"]["artifact_id"] == art_id
    assert art_data["metadata"]["artifact_type"] == "REPORT"
    assert art_data["metadata"]["format"] == "JSON"
    assert "Sample Portfolio Status Report" in art_data["payload"]


def test_create_export_invalid_source(client: TestClient) -> None:
    """Test exporting nonexistent report returns HTTP 404 (Report Not Found)."""
    headers = get_auth_headers(client, Role.ANALYST)
    req_body = {
        "source": {
            "artifact_id": "rep-nonexistent",
            "artifact_type": "REPORT"
        },
        "format": "CSV",
        "options": {}
    }
    response = client.post("/api/v1/exports", json=req_body, headers=headers)
    assert response.status_code == 404
    assert response.json()["title"] == "Report Not Found"


# ---------------------------------------------------------------------------
# RBAC Security Guard Tests
# ---------------------------------------------------------------------------

def test_reports_endpoints_unauthorized(client: TestClient) -> None:
    """Verify listing and detail endpoints reject requests without authorization header (401)."""
    response = client.get("/api/v1/reports")
    assert response.status_code == 401

    response = client.get("/api/v1/reports/rep-sample-1")
    assert response.status_code == 401


def test_reports_endpoints_forbidden(client: TestClient) -> None:
    """Verify endpoints enforce least privilege, rejecting keys without READ permission (403)."""
    headers = get_forbidden_api_key_headers(client)
    response = client.get("/api/v1/reports", headers=headers)
    assert response.status_code == 403

    response = client.get("/api/v1/reports/rep-sample-1", headers=headers)
    assert response.status_code == 403

    # POST route should also reject
    req_body = {
        "source": {
            "artifact_id": "rep-sample-1",
            "artifact_type": "REPORT"
        },
        "format": "JSON",
        "options": {}
    }
    response = client.post("/api/v1/exports", json=req_body, headers=headers)
    assert response.status_code == 403
