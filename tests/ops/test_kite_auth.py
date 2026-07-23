"""Unit tests for Kite daily-auth helpers (no network)."""

from __future__ import annotations

import os
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from athena.errors import ProviderError
from athena.ops.kite_auth import (
    checksum,
    extract_request_token,
    force_inject_kite_env,
    login_url,
    upsert_env_file,
    verify_env_injection,
    verify_kite_credentials,
)


def test_login_url_contains_api_key():
    url = login_url("abc123")
    assert "api_key=abc123" in url
    assert url.startswith("https://kite.zerodha.com/connect/login")


def test_checksum_stable():
    assert checksum("k", "r", "s") == checksum("k", "r", "s")
    assert checksum("k", "r", "s") != checksum("k", "r", "other")


def test_extract_request_token_from_url():
    raw = "http://127.0.0.1/?action=login&status=success&request_token=TokEn123"
    assert extract_request_token(raw) == "TokEn123"


def test_extract_request_token_from_bare():
    assert extract_request_token("TokEn123") == "TokEn123"


def test_extract_request_token_from_host_without_scheme():
    raw = "127.0.0.1/?request_token=Abc99&status=success"
    assert extract_request_token(raw) == "Abc99"


def test_extract_request_token_rejects_empty():
    with pytest.raises(ProviderError, match=r"empty"):
        extract_request_token("   ")


def test_upsert_env_preserves_other_keys(tmp_path: Path):
    path = tmp_path / ".env"
    path.write_text("ATHENA_WEBHOOK_URL=https://example\nKITE_API_KEY=old\n", encoding="utf-8")
    upsert_env_file(path, {"KITE_API_KEY": "new", "KITE_ACCESS_TOKEN": "tok"})
    text = path.read_text(encoding="utf-8")
    assert "ATHENA_WEBHOOK_URL=https://example" in text
    assert "KITE_API_KEY=new" in text
    assert "KITE_ACCESS_TOKEN=tok" in text
    assert "KITE_API_KEY=old" not in text


def test_force_inject_overwrites_process_env(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    path = tmp_path / ".env"
    path.write_text(
        "KITE_API_KEY=filekey\nKITE_ACCESS_TOKEN=filetok\nKITE_API_SECRET=sec\n",
        encoding="utf-8",
    )
    monkeypatch.setenv("KITE_API_KEY", "stale")
    monkeypatch.setenv("KITE_ACCESS_TOKEN", "stale")
    injected = force_inject_kite_env(path)
    assert injected["KITE_API_KEY"] == "filekey"
    assert injected["KITE_ACCESS_TOKEN"] == "filetok"
    assert os.environ["KITE_ACCESS_TOKEN"] == "filetok"


def test_verify_detects_token_mismatch():
    result = verify_kite_credentials(
        api_key="k",
        access_token="a",
        expected_access_token="other",
    )
    assert result.ok is False
    assert "does not match" in result.detail


def test_verify_env_injection_success(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    path = tmp_path / ".env"
    path.write_text(
        "KITE_API_KEY=k\nKITE_ACCESS_TOKEN=fresh\nKITE_API_SECRET=s\n",
        encoding="utf-8",
    )
    monkeypatch.setenv("KITE_ACCESS_TOKEN", "stale")

    payload = {"status": "success", "data": {"user_id": "AB1234", "user_shortname": "S"}}
    mock_resp = MagicMock()
    mock_resp.__enter__.return_value = mock_resp
    mock_resp.__exit__.return_value = False
    with (
        patch("athena.ops.kite_auth.urllib.request.urlopen", return_value=mock_resp),
        patch("athena.ops.kite_auth.json.load", return_value=payload),
    ):
        result = verify_env_injection(path, expected_access_token="fresh")
    assert result.ok is True
    assert result.user_id == "AB1234"
    assert "AB1234" in result.detail
