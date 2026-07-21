"""Integration and unit tests for P8.2 Authentication & RBAC security layer.

Covers:
- Password hashing (BcryptPasswordHasher)
- Token signing & validation (HMAC256TokenSigner, TokenClaimsFactory)
- AuthService (login, token refresh, token rotation/reuse check, logout)
- APIKeyService (creation, hashing validation, metadata/secret split)
- Endpoint protection dependencies (get_current_user, RequirePermission)
- RBAC role hierarchy mapping
- Audit logging (LoggingAuditSink)
- Custom exception handling (RFC 9457 integration)
"""

from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone

import pytest
from fastapi import APIRouter, Depends
from fastapi.testclient import TestClient

from athena.api.config import APISettings
from athena.api.security import Permission, RequirePermission, Role
from athena.api.security.audit import LoggingAuditSink, SecurityEvent
from athena.api.security.dependencies import (
    get_api_key_repository,
    get_session_store,
    get_user_repository,
)
from athena.api.security.exceptions import (
    ExpiredTokenError,
    InvalidCredentialsError,
    SessionRevokedError,
)
from athena.api.security.hashing import BcryptPasswordHasher
from athena.api.security.models import ROLE_PERMISSIONS, AuthenticatedPrincipal, User
from athena.api.security.service import APIKeyService, AuthService
from athena.api.security.token import HMAC256TokenSigner, TokenClaimsFactory

# ---------------------------------------------------------------------------
# Setup & Seeding Fixture
# ---------------------------------------------------------------------------

@pytest.fixture(autouse=True)
def seed_repositories() -> None:
    """Fixture to reset and seed repositories before each test."""
    user_repo = get_user_repository()
    # Reset internal structures
    user_repo._users.clear()
    user_repo._by_username.clear()

    session_store = get_session_store()
    session_store._sessions.clear()  # type: ignore[attr-defined]

    key_repo = get_api_key_repository()
    key_repo._keys.clear()

    # Seed users with pre-hashed passwords using BcryptPasswordHasher
    hasher = BcryptPasswordHasher(rounds=4)  # Use low rounds in tests for speed
    users = [
        User("usr-admin", "admin", hasher.hash("adminpass"), Role.ADMIN),
        User("usr-operator", "operator", hasher.hash("opepass"), Role.OPERATOR),
        User("usr-analyst", "analyst", hasher.hash("anapass"), Role.ANALYST),
        User("usr-readonly", "readonly", hasher.hash("readpass"), Role.READONLY),
        User("usr-inactive", "inactive", hasher.hash("inpass"), Role.READONLY, is_active=False),
    ]
    for u in users:
        user_repo.save(u)


@pytest.fixture()
def security_settings() -> APISettings:
    # High-speed test settings (low rounds)
    return APISettings()


@pytest.fixture()
def auth_services(security_settings) -> tuple[AuthService, APIKeyService, BcryptPasswordHasher]:
    user_repo = get_user_repository()
    session_store = get_session_store()
    api_key_repo = get_api_key_repository()

    hasher = BcryptPasswordHasher(rounds=4)
    signer = HMAC256TokenSigner(
        secret_key=security_settings.security.jwt_secret,
        issuer=security_settings.security.jwt_issuer,
        audience=security_settings.security.jwt_audience,
    )
    claims_factory = TokenClaimsFactory(security_settings.security)
    audit_sink = LoggingAuditSink()

    auth_service = AuthService(
        user_repo=user_repo,
        session_store=session_store,
        hasher=hasher,
        signer=signer,
        claims_factory=claims_factory,
        audit_sink=audit_sink,
    )

    api_key_service = APIKeyService(
        key_repo=api_key_repo,
        audit_sink=audit_sink,
    )

    return auth_service, api_key_service, hasher


# ---------------------------------------------------------------------------
# PasswordHasher Tests
# ---------------------------------------------------------------------------

def test_bcrypt_hasher_hash_and_verify() -> None:
    hasher = BcryptPasswordHasher(rounds=4)
    pwd = "super-secret-pass"
    hashed = hasher.hash(pwd)

    assert hashed != pwd
    assert hasher.verify(pwd, hashed) is True
    assert hasher.verify("wrong-pass", hashed) is False
    assert hasher.verify(pwd, "invalid-hash-string") is False


# ---------------------------------------------------------------------------
# JWT Signing & Claims Factory Tests
# ---------------------------------------------------------------------------

def test_claims_factory_and_token_signer(security_settings) -> None:
    signer = HMAC256TokenSigner(
        secret_key=security_settings.security.jwt_secret,
        issuer=security_settings.security.jwt_issuer,
        audience=security_settings.security.jwt_audience,
    )
    claims_factory = TokenClaimsFactory(security_settings.security)

    principal = AuthenticatedPrincipal(
        user_id="usr-analyst",
        username="analyst",
        role=Role.ANALYST,
        permissions=tuple(ROLE_PERMISSIONS.get(Role.ANALYST, set())),
        session_id="sess-abc123",
    )

    now = datetime.now(tz=timezone.utc)
    claims = claims_factory.create_claims(principal, "access", "sess-abc123", now)

    assert claims.sub == "usr-analyst"
    assert claims.role == "ANALYST"
    assert claims.token_type == "access"

    token = signer.encode(claims.to_dict())
    assert isinstance(token, str)

    decoded = signer.decode(token)
    parsed = claims_factory.parse_claims(decoded)

    assert parsed.sub == claims.sub
    assert parsed.username == claims.username
    assert parsed.role == claims.role
    assert parsed.session_id == claims.session_id


def test_token_signer_verifies_exp(security_settings) -> None:
    signer = HMAC256TokenSigner(
        secret_key=security_settings.security.jwt_secret,
        issuer=security_settings.security.jwt_issuer,
        audience=security_settings.security.jwt_audience,
    )
    # Token expired 1 hour ago
    expired_time = int((datetime.now(tz=timezone.utc) - timedelta(hours=1)).timestamp())
    claims = {
        "sub": "usr-1",
        "username": "user",
        "role": "ANALYST",
        "iat": expired_time - 900,
        "exp": expired_time,
        "iss": security_settings.security.jwt_issuer,
        "aud": security_settings.security.jwt_audience,
        "token_type": "access",
        "session_id": "sess-1",
    }
    token = signer.encode(claims)
    with pytest.raises(ExpiredTokenError):
        signer.decode(token)


# ---------------------------------------------------------------------------
# AuthService Tests
# ---------------------------------------------------------------------------

class TestAuthService:
    def test_login_success(self, auth_services) -> None:
        auth, _, _ = auth_services
        access_token, refresh_token = auth.login("admin", "adminpass", "req-1", "127.0.0.1")

        assert isinstance(access_token, str)
        assert isinstance(refresh_token, str)

    def test_login_invalid_password(self, auth_services) -> None:
        auth, _, _ = auth_services
        with pytest.raises(InvalidCredentialsError):
            auth.login("admin", "wrong-pass", "req-2", "127.0.0.1")

    def test_login_inactive_user(self, auth_services) -> None:
        auth, _, _ = auth_services
        with pytest.raises(InvalidCredentialsError):
            auth.login("inactive", "inpass", "req-3", "127.0.0.1")

    def test_token_refresh_and_rotation(self, auth_services) -> None:
        auth, _, _ = auth_services
        access_token, refresh_token = auth.login("admin", "adminpass", "req-1", "127.0.0.1")

        # Refresh using token
        new_access, new_refresh = auth.refresh(refresh_token, "req-refresh", "127.0.0.1")
        assert new_access != access_token
        assert new_refresh != refresh_token

        # Attempting reuse of original refresh token must raise SessionRevokedError
        with pytest.raises(SessionRevokedError):
            auth.refresh(refresh_token, "req-reuse", "127.0.0.1")

    def test_logout_revokes_session(self, auth_services, security_settings) -> None:
        auth, _, _ = auth_services
        signer = HMAC256TokenSigner(
            secret_key=security_settings.security.jwt_secret,
            issuer=security_settings.security.jwt_issuer,
            audience=security_settings.security.jwt_audience,
        )
        access_token, _refresh_token = auth.login("admin", "adminpass", "req-1", "127.0.0.1")

        claims = signer.decode(access_token)
        session_id = claims["session_id"]

        auth.logout(session_id, "req-logout", "127.0.0.1")

        # Refreshes should fail on revoked sessions
        with pytest.raises(SessionRevokedError):
            get_session_store().find(session_id)


# ---------------------------------------------------------------------------
# APIKeyService Tests
# ---------------------------------------------------------------------------

class TestAPIKeyService:
    def test_create_and_validate_key(self, auth_services) -> None:
        _, api_key_service, _ = auth_services
        secret = api_key_service.create_key(
            owner_id="usr-admin",
            name="test-key",
            permissions=(Permission.READ, Permission.EXECUTE),
            expires_at=None,
            request_id="req-key",
            ip_address="127.0.0.1",
        )

        assert secret.key_id.startswith("key-")
        assert secret.raw_key.startswith(f"{secret.key_id}.")

        # Retrieve metadata from repo (raw secret is NOT stored)
        meta = get_api_key_repository().find_by_id(secret.key_id)
        assert meta is not None
        assert meta.name == "test-key"
        assert "key-" not in meta.key_hash


# ---------------------------------------------------------------------------
# Endpoint Dependency & RBAC Tests
# ---------------------------------------------------------------------------

class TestEndpointSecurity:
    @pytest.fixture()
    def client_with_routes(self, client) -> TestClient:
        # Register test routes to verify dependencies and RBAC mappings
        router = APIRouter()

        @router.get("/test/read")
        def read_route(
            principal: AuthenticatedPrincipal = Depends(RequirePermission(Permission.READ)),  # noqa: B008
        ) -> dict:
            return {"user": principal.username, "role": principal.role.value}

        @router.get("/test/execute")
        def exec_route(
            principal: AuthenticatedPrincipal = Depends(RequirePermission(Permission.EXECUTE)),  # noqa: B008
        ) -> dict:
            return {"user": principal.username, "role": principal.role.value}

        @router.get("/test/admin")
        def admin_route(
            principal: AuthenticatedPrincipal = Depends(RequirePermission(Permission.ADMIN)),  # noqa: B008
        ) -> dict:
            return {"user": principal.username, "role": principal.role.value}

        client.app.include_router(router, prefix="/api/v1")
        return client

    def test_access_blocked_without_credentials(self, client_with_routes) -> None:
        response = client_with_routes.get("/api/v1/test/read")
        assert response.status_code == 401
        assert response.json()["title"] == "Unauthorized"

    def test_rbac_readonly_user_authorization(self, client_with_routes, auth_services) -> None:
        auth, _, _ = auth_services
        access_token, _ = auth.login("readonly", "readpass", "req-1", "127.0.0.1")

        headers = {"Authorization": f"Bearer {access_token}"}

        # Read allowed
        resp_read = client_with_routes.get("/api/v1/test/read", headers=headers)
        assert resp_read.status_code == 200

        # Execute blocked (403 Forbidden)
        resp_exec = client_with_routes.get("/api/v1/test/execute", headers=headers)
        assert resp_exec.status_code == 403
        assert resp_exec.json()["title"] == "Permission Denied"

    def test_rbac_operator_user_authorization(self, client_with_routes, auth_services) -> None:
        auth, _, _ = auth_services
        access_token, _ = auth.login("operator", "opepass", "req-1", "127.0.0.1")

        headers = {"Authorization": f"Bearer {access_token}"}

        # Read & Execute allowed
        assert client_with_routes.get("/api/v1/test/read", headers=headers).status_code == 200
        assert client_with_routes.get("/api/v1/test/execute", headers=headers).status_code == 200

        # Admin blocked (403 Forbidden)
        resp_admin = client_with_routes.get("/api/v1/test/admin", headers=headers)
        assert resp_admin.status_code == 403

    def test_rbac_admin_user_authorization(self, client_with_routes, auth_services) -> None:
        auth, _, _ = auth_services
        access_token, _ = auth.login("admin", "adminpass", "req-1", "127.0.0.1")

        headers = {"Authorization": f"Bearer {access_token}"}

        # All allowed
        assert client_with_routes.get("/api/v1/test/read", headers=headers).status_code == 200
        assert client_with_routes.get("/api/v1/test/execute", headers=headers).status_code == 200
        assert client_with_routes.get("/api/v1/test/admin", headers=headers).status_code == 200

    def test_api_key_authentication(self, client_with_routes, auth_services) -> None:
        _, api_key_service, _ = auth_services

        secret = api_key_service.create_key(
            owner_id="usr-operator",
            name="ci-key",
            permissions=(Permission.READ, Permission.EXECUTE),
            expires_at=None,
            request_id="req-1",
            ip_address="127.0.0.1",
        )

        headers = {"X-API-Key": secret.raw_key}

        # Operator Key -> Read & Execute allowed, Admin blocked
        assert client_with_routes.get("/api/v1/test/read", headers=headers).status_code == 200
        assert client_with_routes.get("/api/v1/test/execute", headers=headers).status_code == 200
        assert client_with_routes.get("/api/v1/test/admin", headers=headers).status_code == 403

    def test_invalid_api_key_rejected(self, client_with_routes) -> None:
        headers = {"X-API-Key": "key-nonexistent.secret"}
        response = client_with_routes.get("/api/v1/test/read", headers=headers)
        assert response.status_code == 401
        assert response.json()["title"] == "Invalid API Key"


# ---------------------------------------------------------------------------
# Structured Security Audit Logging & AuthProvider Tests
# ---------------------------------------------------------------------------

def test_logging_audit_sink_records_events(caplog) -> None:
    sink = LoggingAuditSink()
    event = SecurityEvent(
        event_id="evt-123",
        ts=datetime.now(tz=timezone.utc),
        event_type="TEST_EVENT",
        username="audit-user",
        request_id="req-123",
        ip_address="192.168.1.1",
        detail="testing structured audit sinks",
    )

    caplog.set_level(logging.INFO)
    sink.record(event)

    # Verify structured logs are emitted
    assert "evt-123" in caplog.text
    assert "TEST_EVENT" in caplog.text
    assert "audit-user" in caplog.text
    assert "192.168.1.1" in caplog.text
