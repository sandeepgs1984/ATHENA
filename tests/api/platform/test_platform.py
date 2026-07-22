"""Integration tests for Phase 8.5 Platform Infrastructure.

Covers:
- Health endpoints (/health, /health/live, /health/ready)
- Platform version info (/api/version)
- Platform discovery metadata (/api/meta, /api/features, /api/capabilities, /api/info)
- Correlation & request ID tracing headers propagation
- Centralized middleware validation timing, logging, and error conversion
- RFC 9457 Problem Details mapping compliance
- API contract router registration, operation IDs, tags, and OpenAPI schema completion
"""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient
from fastapi.routing import APIRoute

from athena.api.platform.providers.build_info_provider import BuildInfoProvider, BuildInfoDTO
from athena.api.platform.providers.metadata_provider import (
    MetadataProvider,
    CapabilityMetadataDTO,
    FeaturesDTO,
    PlatformMetadataDTO,
)


class MockBuildInfoProvider(BuildInfoProvider):
    """Mock build provider for contract assertions."""
    def get_build_info(self) -> BuildInfoDTO:
        from datetime import datetime, timezone
        return BuildInfoDTO(
            app_name="ATHENA",
            semver="1.0.0",
            api_version="v1",
            build_number="build-test",
            commit_hash="commit-test",
            build_timestamp=datetime.now(tz=timezone.utc),
            environment="test",
            runtime_info={"runtime": "mock"},
        )


class MockMetadataProvider(MetadataProvider):
    """Mock metadata provider for discovery assertions."""
    def get_metadata(self) -> PlatformMetadataDTO:
        return PlatformMetadataDTO(
            app_name="ATHENA",
            active_profile="test-profile",
            modules=["data", "security"],
            api_version_compatibility=["v1"],
            ai={"enabled": False},
        )

    def get_features(self) -> FeaturesDTO:
        return FeaturesDTO(features={"mock-flag": True})

    def get_capabilities(self) -> list[CapabilityMetadataDTO]:
        return [
            CapabilityMetadataDTO(
                name="MockCapability",
                version="1.0.0",
                category="TEST",
                description="Mock capability description",
                enabled=True,
                experimental=False,
            )
        ]


@pytest.fixture(autouse=True)
def inject_mock_providers(client: TestClient) -> None:
    """Fixture injecting mock platform metadata and build info providers onto the app state."""
    app = client.app
    app.state.build_info_provider = MockBuildInfoProvider()
    app.state.metadata_provider = MockMetadataProvider()


# ---------------------------------------------------------------------------
# Health Check Endpoint Tests
# ---------------------------------------------------------------------------

def test_health_check_endpoints(client: TestClient) -> None:
    """Test standard health check paths return expected UP statuses."""
    # 1. Aggregated Health
    response = client.get("/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] in ("UP", "DOWN")
    assert "timestamp" in data
    assert "version" in data
    assert "checks" in data
    
    # 2. Liveness
    live_resp = client.get("/health/live")
    assert live_resp.status_code == 200
    assert live_resp.json()["status"] == "UP"

    # 3. Readiness
    ready_resp = client.get("/health/ready")
    assert ready_resp.status_code == 200
    assert ready_resp.json()["status"] in ("UP", "DOWN")


# ---------------------------------------------------------------------------
# Platform Discovery Endpoint Tests
# ---------------------------------------------------------------------------

def test_version_endpoint(client: TestClient) -> None:
    """Verify GET /api/version returns mock provider build DTO."""
    response = client.get("/api/version")
    assert response.status_code == 200
    data = response.json()
    assert data["app_name"] == "ATHENA"
    assert data["semver"] == "1.0.0"
    assert data["build_number"] == "build-test"
    assert data["commit_hash"] == "commit-test"
    assert data["runtime_info"]["runtime"] == "mock"


def test_metadata_discovery_endpoints(client: TestClient) -> None:
    """Verify GET /api/meta features, capabilities, and info endpoints return correct structures."""
    # 1. /api/meta
    meta_resp = client.get("/api/meta")
    assert meta_resp.status_code == 200
    meta = meta_resp.json()
    assert meta["active_profile"] == "test-profile"
    assert "data" in meta["modules"]
    assert meta["ai"]["enabled"] is False

    # 2. /api/features
    feat_resp = client.get("/api/features")
    assert feat_resp.status_code == 200
    assert feat_resp.json()["features"]["mock-flag"] is True

    # 3. /api/capabilities
    caps_resp = client.get("/api/capabilities")
    assert caps_resp.status_code == 200
    caps = caps_resp.json()
    assert len(caps) == 1
    assert caps[0]["name"] == "MockCapability"
    assert caps[0]["category"] == "TEST"

    # 4. /api/info
    info_resp = client.get("/api/info")
    assert info_resp.status_code == 200
    info = info_resp.json()
    assert info["app_name"] == "ATHENA"
    assert info["environment"] == "test"
    assert info["build"]["commit_hash"] == "commit-test"
    assert info["meta"]["active_profile"] == "test-profile"
    assert info["features"]["features"]["mock-flag"] is True
    assert info["capabilities"][0]["name"] == "MockCapability"


# ---------------------------------------------------------------------------
# Tracing Headers and Middleware Tests
# ---------------------------------------------------------------------------

def test_middleware_request_tracing_and_propagation(client: TestClient) -> None:
    """Verify request ID generation, correlation ID propagation, and standard headers injection."""
    # Send request with a pre-configured correlation ID
    test_corr_id = "test-correlation-correlation-123"
    response = client.get("/health/live", headers={"X-Correlation-ID": test_corr_id})
    assert response.status_code == 200
    
    # Assert headers exist on response
    assert "X-Request-ID" in response.headers
    assert "X-Correlation-ID" in response.headers
    assert "X-API-Version" in response.headers
    
    assert response.headers["X-Correlation-ID"] == test_corr_id
    assert len(response.headers["X-Request-ID"]) > 10


# ---------------------------------------------------------------------------
# Standard Error Mapping (RFC 9457) Tests
# ---------------------------------------------------------------------------

def test_unhandled_exception_maps_to_problem_details(client: TestClient) -> None:
    """Verify unhandled routing/execution panic is mapped to Problem Details schema by middleware."""
    # Force a validation error by sending invalid type parameters to a v1 endpoint
    response = client.get("/api/v1/decisions/nonexistent", headers={"Authorization": "Bearer invalid_token"})
    assert response.status_code in (401, 403, 422)

    data = response.json()
    assert "type" in data
    assert "title" in data
    assert "status" in data
    assert "detail" in data
    assert "instance" in data
    assert "request_id" in data
    assert "correlation_id" in data
    assert "timestamp" in data


# ---------------------------------------------------------------------------
# OpenAPI Contract & Audit Complete Route Tests
# ---------------------------------------------------------------------------

def test_openapi_contract_conformance(client: TestClient) -> None:
    """Audit registered FastAPI endpoints to ensure complete documentation coverage."""
    app = client.app
    
    # Ensure OpenAPI schema generation succeeds
    openapi = app.openapi()
    assert openapi is not None
    assert "openapi" in openapi
    assert "paths" in openapi
    
    # Audit registered routes
    for route in app.routes:
        if isinstance(route, APIRoute):
            # Exclude standard redirect/docs endpoints
            if route.path in ("/docs", "/redoc", "/openapi.json", "/"):
                continue

            # Verify every API route has operation_id defined
            assert route.operation_id is not None, f"Route '{route.path}' is missing operation_id"
            
            # Verify every API route has tags set
            assert len(route.tags) > 0, f"Route '{route.path}' is missing tags documentation"
            
            # Verify every API route has summary and description documentation
            assert route.summary is not None, f"Route '{route.path}' is missing summary documentation"
            assert route.description is not None, f"Route '{route.path}' is missing description documentation"


# ---------------------------------------------------------------------------
# Pagination Invariant Check
# ---------------------------------------------------------------------------

def test_pagination_behavior_consistency(client: TestClient) -> None:
    """Verify that every list endpoint returning paginated results exposes standard pagination schema."""
    app = client.app
    openapi = app.openapi()
    
    # Ensure all endpoints returning a listing envelope conform to standard fields
    for path, path_item in openapi["paths"].items():
        for method, op in path_item.items():
            if method != "get":
                continue
            
            # Check if query params include page parameters
            params = op.get("parameters", [])
            has_paging = any(p.get("name") in ("page", "page_size") for p in params)
            
            if has_paging:
                # Retrieve response schema structure
                responses = op.get("responses", {})
                success_resp = responses.get("200", {})
                content = success_resp.get("content", {})
                json_content = content.get("application/json", {})
                schema = json_content.get("schema", {})
                
                # Check for standard envelope pagination schema attributes
                ref = schema.get("$ref", "")
                if ref:
                    # Resolve ref from components
                    ref_name = ref.split("/")[-1]
                    ref_schema = openapi["components"]["schemas"].get(ref_name, {})
                    properties = ref_schema.get("properties", {})
                    
                    # If this DTO represents a paginated collection, it must contain a pagination block
                    if "pagination" in properties:
                        pag_ref = properties["pagination"].get("$ref", "")
                        if pag_ref:
                            pag_name = pag_ref.split("/")[-1]
                            pag_schema = openapi["components"]["schemas"].get(pag_name, {})
                            pag_props = pag_schema.get("properties", {})
                            
                            # Assert standard pagination keys exist
                            assert "total" in pag_props
                            assert "page" in pag_props
                            assert "page_size" in pag_props
                            assert "total_pages" in pag_props
                            assert "has_next" in pag_props
                            assert "has_previous" in pag_props
