"""Tests for browser-driven Kite session gate (M-E3; no live network)."""

from __future__ import annotations

import json
import os
from pathlib import Path
from unittest.mock import patch

import pytest

from athena.ops.kite_auth import KiteVerifyResult
from athena.ops.kite_session import KiteSessionService


def _config_dir(tmp_path: Path, provider: str = "kite") -> Path:
    config_dir = tmp_path / "config"
    config_dir.mkdir()
    (config_dir / "ingestion.json").write_text(
        json.dumps(
            {
                "provider": provider,
                "timeframes": ["5m"],
                "lookback_minutes": 30,
                "lookback_days": 90,
                "include_daily": True,
                "include_quotes": True,
                "validate_gaps": False,
                "skip_existing": True,
                "quarantine_on_failure": True,
                "instrument_ids": [],
            }
        ),
        encoding="utf-8",
    )
    return config_dir


def test_status_not_required_for_file_provider(tmp_path: Path) -> None:
    service = KiteSessionService(
        repo_root=tmp_path,
        config_dir=_config_dir(tmp_path, "file"),
    )
    result = service.status()
    assert result.required is False
    assert result.connected is True
    assert result.state == "not_required"


def test_status_missing_credentials(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("KITE_API_KEY", raising=False)
    monkeypatch.delenv("KITE_ACCESS_TOKEN", raising=False)
    service = KiteSessionService(
        repo_root=tmp_path,
        config_dir=_config_dir(tmp_path),
    )
    result = service.status()
    assert result.required is True
    assert result.connected is False
    assert result.state == "missing"


def test_status_verifies_connected_session(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("KITE_API_KEY", "key")
    monkeypatch.setenv("KITE_API_SECRET", "secret")
    monkeypatch.setenv("KITE_ACCESS_TOKEN", "token")
    service = KiteSessionService(
        repo_root=tmp_path,
        config_dir=_config_dir(tmp_path),
    )
    with patch(
        "athena.ops.kite_session.verify_kite_credentials",
        return_value=KiteVerifyResult(True, "session OK", user_id="AB123"),
    ):
        result = service.status()
    assert result.connected is True
    assert result.state == "connected"
    assert result.user_id == "AB123"


def test_start_auth_returns_login_url_without_secrets(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("KITE_API_KEY", "public-key")
    monkeypatch.setenv("KITE_API_SECRET", "private-secret")
    service = KiteSessionService(
        repo_root=tmp_path,
        config_dir=_config_dir(tmp_path),
    )
    result = service.start_auth()
    assert result.ready is True
    assert result.login_url is not None
    assert "api_key=public-key" in result.login_url
    assert "private-secret" not in result.login_url


def test_complete_auth_persists_injects_and_verifies(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("KITE_API_KEY", "key")
    monkeypatch.setenv("KITE_API_SECRET", "secret")
    monkeypatch.setenv("KITE_ACCESS_TOKEN", "old")
    (tmp_path / ".env").write_text(
        "KITE_API_KEY=key\nKITE_API_SECRET=secret\nKITE_ACCESS_TOKEN=old\n",
        encoding="utf-8",
    )
    service = KiteSessionService(
        repo_root=tmp_path,
        config_dir=_config_dir(tmp_path),
    )
    with (
        patch(
            "athena.ops.kite_session.exchange_access_token",
            return_value="fresh-token",
        ),
        patch(
            "athena.ops.kite_session.verify_env_injection",
            return_value=KiteVerifyResult(True, "session OK", user_id="AB123"),
        ),
    ):
        result = service.complete_auth(
            "http://127.0.0.1/?status=success&request_token=Request123"
        )

    assert result.connected is True
    assert result.user_id == "AB123"
    assert "KITE_ACCESS_TOKEN=fresh-token" in (tmp_path / ".env").read_text(
        encoding="utf-8"
    )
    assert os.environ["KITE_ACCESS_TOKEN"] == "fresh-token"


def test_disconnect_clears_access_token(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("KITE_API_KEY", "key")
    monkeypatch.setenv("KITE_API_SECRET", "secret")
    monkeypatch.setenv("KITE_ACCESS_TOKEN", "fresh")
    (tmp_path / ".env").write_text(
        "KITE_API_KEY=key\nKITE_API_SECRET=secret\nKITE_ACCESS_TOKEN=fresh\n",
        encoding="utf-8",
    )
    service = KiteSessionService(
        repo_root=tmp_path,
        config_dir=_config_dir(tmp_path),
    )
    result = service.disconnect()
    assert result.connected is False
    assert result.state == "missing"
    assert "KITE_ACCESS_TOKEN" not in os.environ
    env_text = (tmp_path / ".env").read_text(encoding="utf-8")
    assert "KITE_API_KEY=key" in env_text
    assert "KITE_API_SECRET=secret" in env_text
    assert "KITE_ACCESS_TOKEN=fresh" not in env_text
