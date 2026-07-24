"""HTTP auth surface tests (Live Entry M-E1)."""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from athena.api.app import create_app
from athena.api.config import APISettings
from athena.api.security.dependencies import get_session_store, get_user_repository
from athena.api.security.hashing import BcryptPasswordHasher
from athena.api.security.models import Role
from athena.api.security.owner_seed import (
    auth_required,
    owner_credentials_configured,
    seed_owner_user,
    single_user_bypass_enabled,
)


@pytest.fixture()
def owner_hash() -> str:
    return BcryptPasswordHasher(rounds=4).hash("owner-secret")


@pytest.fixture()
def owner_env(owner_hash: str, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("ATHENA_OWNER_USER", "owner")
    monkeypatch.setenv("ATHENA_OWNER_PASSWORD_HASH", owner_hash)
    monkeypatch.setenv("ATHENA_SINGLE_USER", "true")


@pytest.fixture()
def auth_client(owner_env: None) -> TestClient:
    get_user_repository()._users.clear()
    get_user_repository()._by_username.clear()
    get_session_store()._sessions.clear()  # type: ignore[attr-defined]

    app = create_app(APISettings())
    return TestClient(app, raise_server_exceptions=False)


def test_owner_seed_helpers(owner_hash: str, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("ATHENA_OWNER_PASSWORD_HASH", raising=False)
    monkeypatch.setenv("ATHENA_SINGLE_USER", "true")
    assert owner_credentials_configured() is False
    assert single_user_bypass_enabled() is True
    assert auth_required() is False

    monkeypatch.setenv("ATHENA_OWNER_USER", "owner")
    monkeypatch.setenv("ATHENA_OWNER_PASSWORD_HASH", owner_hash)
    assert owner_credentials_configured() is True
    assert single_user_bypass_enabled() is False
    assert auth_required() is True

    repo = get_user_repository()
    repo._users.clear()
    repo._by_username.clear()
    user = seed_owner_user(repo)
    assert user is not None
    assert user.username == "owner"
    assert user.role == Role.ADMIN


def test_auth_status_requires_unlock_when_owner_configured(auth_client: TestClient) -> None:
    response = auth_client.get("/api/v1/auth/status")
    assert response.status_code == 200
    data = response.json()["data"]
    assert data["auth_required"] is True
    assert data["owner_configured"] is True


def test_login_me_logout_roundtrip(auth_client: TestClient) -> None:
    bad = auth_client.post(
        "/api/v1/auth/login",
        json={"username": "owner", "password": "wrong"},
    )
    assert bad.status_code == 401

    login = auth_client.post(
        "/api/v1/auth/login",
        json={"username": "owner", "password": "owner-secret"},
    )
    assert login.status_code == 200
    tokens = login.json()["data"]
    assert tokens["access_token"]
    assert tokens["refresh_token"]
    assert tokens["token_type"] == "bearer"

    headers = {"Authorization": f"Bearer {tokens['access_token']}"}
    me = auth_client.get("/api/v1/auth/me", headers=headers)
    assert me.status_code == 200
    principal = me.json()["data"]
    assert principal["username"] == "owner"
    assert principal["role"] == "ADMIN"

    protected = auth_client.get("/api/v1/portfolio", headers=headers)
    assert protected.status_code in (200, 503)  # 503 if portfolio provider unavailable

    logout = auth_client.post("/api/v1/auth/logout", headers=headers)
    assert logout.status_code == 200

    after = auth_client.get("/api/v1/auth/me", headers=headers)
    assert after.status_code == 401


def test_login_locks_after_repeated_failures(auth_client: TestClient) -> None:
    for _ in range(4):
        response = auth_client.post(
            "/api/v1/auth/login",
            json={"username": "owner", "password": "wrong"},
        )
        assert response.status_code == 401

    threshold = auth_client.post(
        "/api/v1/auth/login",
        json={"username": "owner", "password": "wrong"},
    )
    assert threshold.status_code == 429
    assert threshold.json()["title"] == "Unlock Temporarily Locked"
    assert int(threshold.headers["Retry-After"]) > 0

    correct_while_locked = auth_client.post(
        "/api/v1/auth/login",
        json={"username": "owner", "password": "owner-secret"},
    )
    assert correct_while_locked.status_code == 429


def test_refresh_rotates_tokens(auth_client: TestClient) -> None:
    login = auth_client.post(
        "/api/v1/auth/login",
        json={"username": "owner", "password": "owner-secret"},
    )
    tokens = login.json()["data"]

    refresh = auth_client.post(
        "/api/v1/auth/refresh",
        json={"refresh_token": tokens["refresh_token"]},
    )
    assert refresh.status_code == 200
    new_tokens = refresh.json()["data"]
    assert new_tokens["access_token"] != tokens["access_token"]
    assert new_tokens["refresh_token"] != tokens["refresh_token"]

    reuse = auth_client.post(
        "/api/v1/auth/refresh",
        json={"refresh_token": tokens["refresh_token"]},
    )
    assert reuse.status_code == 401


def test_root_redirects_to_dashboard(auth_client: TestClient) -> None:
    response = auth_client.get("/", follow_redirects=False)
    assert response.status_code == 307
    assert response.headers["location"] == "/dashboard/"


def test_set_owner_password_cli(capsys: pytest.CaptureFixture[str]) -> None:
    from athena.cli import main

    code = main(["set-owner-password", "--username", "sandeep", "--password", "tmp-pass-123"])
    assert code == 0
    out = capsys.readouterr().out
    assert "ATHENA_OWNER_USER=sandeep" in out
    assert "ATHENA_OWNER_PASSWORD_HASH='" in out
    assert out.count("$2b$") >= 1 or out.count("$2a$") >= 1 or out.count("$2y$") >= 1
