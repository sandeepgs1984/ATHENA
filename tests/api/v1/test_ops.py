"""Integration tests for P9.7 Live Operations APIs."""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from athena.api.app import create_app
from athena.api.config import APISettings
from athena.api.security.models import Role
from athena.data.store import SqliteRepository, create_backup
from tests.api.v1.test_core_apis import get_auth_headers


@pytest.fixture()
def ops_paths(tmp_path: Path) -> tuple[Path, Path]:
    db_path = tmp_path / "athena.db"
    backup_dir = tmp_path / "backups"
    backup_dir.mkdir(parents=True, exist_ok=True)
    repo = SqliteRepository(db_path)
    repo.initialize()
    repo.close()
    return db_path, backup_dir


@pytest.fixture()
def ops_client(api_settings: APISettings, ops_paths: tuple[Path, Path]) -> TestClient:
    db_path, backup_dir = ops_paths
    app = create_app(api_settings)
    app.state.ops_db_path = db_path
    app.state.ops_backup_dir = backup_dir
    return TestClient(app)


class TestOpsTelemetry:
    def test_telemetry_requires_auth(self, client: TestClient) -> None:
        response = client.get("/api/v1/ops/telemetry")
        assert response.status_code == 401

    def test_telemetry_success(self, client: TestClient) -> None:
        headers = get_auth_headers(client, Role.READONLY)
        response = client.get("/api/v1/ops/telemetry", headers=headers)
        assert response.status_code == 200
        body = response.json()
        assert body["status"] == "success"
        data = body["data"]
        assert "stages" in data
        assert isinstance(data["stages"], list)
        if data["stages"]:
            stage = data["stages"][0]
            assert "stage_id" in stage
            assert "status" in stage
            assert "message" in stage


class TestOpsStream:
    def test_stream_requires_auth(self, client: TestClient) -> None:
        response = client.get("/api/v1/ops/stream")
        assert response.status_code == 401

    def test_stream_emits_sse_events(self, client: TestClient) -> None:
        headers = get_auth_headers(client, Role.READONLY)
        with client.stream(
            "GET",
            "/api/v1/ops/stream?max_events=1",
            headers=headers,
        ) as response:
            assert response.status_code == 200
            assert "text/event-stream" in response.headers["content-type"]
            chunks: list[str] = []
            for chunk in response.iter_text():
                chunks.append(chunk)
                joined = "".join(chunks)
                if "event: heartbeat" in joined and "data:" in joined:
                    break
            payload = "".join(chunks)
            assert "event: heartbeat" in payload
            assert "data:" in payload


class TestOpsBackups:
    def test_list_backups_empty(self, ops_client: TestClient) -> None:
        headers = get_auth_headers(ops_client, Role.READONLY)
        response = ops_client.get("/api/v1/ops/backups", headers=headers)
        assert response.status_code == 200
        assert response.json()["data"] == []

    def test_create_backup_requires_admin(self, ops_client: TestClient) -> None:
        headers = get_auth_headers(ops_client, Role.ANALYST)
        response = ops_client.post("/api/v1/ops/backups", headers=headers)
        assert response.status_code == 403

    def test_create_and_list_backup(self, ops_client: TestClient) -> None:
        headers = get_auth_headers(ops_client, Role.ADMIN)
        create = ops_client.post("/api/v1/ops/backups", headers=headers)
        assert create.status_code == 201
        created = create.json()["data"]
        assert created["backup_id"].endswith(".db")
        assert created["integrity_ok"] is True

        listed = ops_client.get("/api/v1/ops/backups", headers=headers)
        assert listed.status_code == 200
        items = listed.json()["data"]
        assert len(items) == 1
        assert items[0]["backup_id"] == created["backup_id"]

    def test_create_backup_fails_loudly_without_db(
        self, api_settings: APISettings, tmp_path: Path
    ) -> None:
        app = create_app(api_settings)
        app.state.ops_db_path = tmp_path / "missing.db"
        app.state.ops_backup_dir = tmp_path / "backups"
        client = TestClient(app)
        headers = get_auth_headers(client, Role.ADMIN)
        response = client.post("/api/v1/ops/backups", headers=headers)
        assert response.status_code == 503
        assert response.json()["title"] == "Database Unavailable"

    def test_restore_requires_confirm_token(
        self, ops_client: TestClient, ops_paths: tuple[Path, Path]
    ) -> None:
        db_path, backup_dir = ops_paths
        # Seed a backup file via domain API
        repo = SqliteRepository(db_path)
        dest = backup_dir / "seed.bak.db"
        create_backup(repo, dest, as_of=datetime.now(tz=timezone.utc))
        repo.close()

        headers = get_auth_headers(ops_client, Role.ADMIN)
        response = ops_client.post(
            f"/api/v1/ops/backups/{dest.name}/restore",
            headers=headers,
            json={"confirmation": "nope"},
        )
        assert response.status_code == 400
        assert response.json()["title"] == "Restore Confirmation Required"

    def test_restore_with_confirm(
        self, ops_client: TestClient, ops_paths: tuple[Path, Path]
    ) -> None:
        db_path, backup_dir = ops_paths
        repo = SqliteRepository(db_path)
        dest = backup_dir / "seed-ok.db"
        create_backup(repo, dest, as_of=datetime.now(tz=timezone.utc))
        repo.close()

        headers = get_auth_headers(ops_client, Role.ADMIN)
        response = ops_client.post(
            f"/api/v1/ops/backups/{dest.name}/restore",
            headers=headers,
            json={"confirmation": "CONFIRM"},
        )
        assert response.status_code == 200
        data = response.json()["data"]
        assert data["ok"] is True
        assert data["integrity_ok"] is True
        assert Path(data["target"]).exists()

    def test_restore_unknown_backup(self, ops_client: TestClient) -> None:
        headers = get_auth_headers(ops_client, Role.ADMIN)
        response = ops_client.post(
            "/api/v1/ops/backups/does-not-exist.db/restore",
            headers=headers,
            json={"confirmation": "CONFIRM"},
        )
        assert response.status_code == 404
        assert response.json()["title"] == "Backup Not Found"
