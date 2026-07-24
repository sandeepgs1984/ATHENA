"""Browser-driven Kite session gate (Live Entry M-E3).

This service reuses the existing read-only Kite authentication primitives but
never prompts on stdin or opens a browser. The dashboard owns those interactions.
"""

from __future__ import annotations

import os
import threading
from dataclasses import dataclass
from pathlib import Path
from typing import Literal

from athena.config.loader import load_ingestion_config
from athena.errors import ProviderError
from athena.ops.kite_auth import (
    exchange_access_token,
    extract_request_token,
    force_inject_kite_env,
    login_url,
    upsert_env_file,
    verify_env_injection,
    verify_kite_credentials,
)

KiteConnectionState = Literal[
    "not_required",
    "missing",
    "misconfigured",
    "connected",
    "expired",
    "unavailable",
]


@dataclass(frozen=True, slots=True)
class KiteSessionStatus:
    """Safe, secret-free Kite connection status."""

    required: bool
    connected: bool
    state: KiteConnectionState
    detail: str
    user_id: str | None = None


@dataclass(frozen=True, slots=True)
class KiteAuthStart:
    """Browser login URL and safe readiness metadata."""

    login_url: str | None
    ready: bool
    detail: str


class KiteSessionService:
    """Check and complete the owner's daily Kite Connect session."""

    def __init__(self, *, repo_root: Path, config_dir: Path) -> None:
        self._repo_root = Path(repo_root)
        self._config_dir = Path(config_dir)
        self._exchange_lock = threading.Lock()

    @property
    def env_path(self) -> Path:
        return self._repo_root / ".env"

    def status(self, *, verify: bool = True) -> KiteSessionStatus:
        """Return provider-aware status, optionally verifying `/user/profile`."""
        provider = load_ingestion_config(self._config_dir).provider
        if provider != "kite":
            return KiteSessionStatus(
                required=False,
                connected=True,
                state="not_required",
                detail=f"Kite not required (ingestion provider: {provider})",
            )

        api_key = (os.environ.get("KITE_API_KEY") or "").strip()
        access_token = (os.environ.get("KITE_ACCESS_TOKEN") or "").strip()
        api_secret = (os.environ.get("KITE_API_SECRET") or "").strip()
        if not api_key or not access_token:
            return KiteSessionStatus(
                required=True,
                connected=False,
                state="missing",
                detail="Kite API key or daily access token is missing",
            )
        if not api_secret:
            return KiteSessionStatus(
                required=True,
                connected=False,
                state="misconfigured",
                detail="KITE_API_SECRET is required to renew the daily session",
            )
        if not verify:
            return KiteSessionStatus(
                required=True,
                connected=True,
                state="connected",
                detail="Kite credentials are present (not verified)",
            )

        result = verify_kite_credentials(api_key=api_key, access_token=access_token)
        if result.ok:
            return KiteSessionStatus(
                required=True,
                connected=True,
                state="connected",
                detail=result.detail,
                user_id=result.user_id,
            )
        detail_lower = result.detail.lower()
        state: KiteConnectionState = (
            "unavailable"
            if "network failure" in detail_lower
            else "expired"
        )
        return KiteSessionStatus(
            required=True,
            connected=False,
            state=state,
            detail=result.detail,
        )

    def start_auth(self) -> KiteAuthStart:
        """Return the Kite login URL without exposing API secret/token."""
        api_key = (os.environ.get("KITE_API_KEY") or "").strip()
        api_secret = (os.environ.get("KITE_API_SECRET") or "").strip()
        if not api_key:
            return KiteAuthStart(
                login_url=None,
                ready=False,
                detail="Set KITE_API_KEY in .env, then restart ATHENA",
            )
        if not api_secret:
            return KiteAuthStart(
                login_url=None,
                ready=False,
                detail="Set KITE_API_SECRET in .env, then restart ATHENA",
            )
        return KiteAuthStart(
            login_url=login_url(api_key),
            ready=True,
            detail=(
                "Open Kite, authorize ATHENA, then paste the redirect URL "
                "or request_token back into the dashboard"
            ),
        )

    def complete_auth(self, redirect_or_token: str) -> KiteSessionStatus:
        """Exchange request token, persist it, re-inject env, and verify profile."""
        api_key = (os.environ.get("KITE_API_KEY") or "").strip()
        api_secret = (os.environ.get("KITE_API_SECRET") or "").strip()
        if not api_key or not api_secret:
            raise ProviderError(
                "KITE_API_KEY and KITE_API_SECRET must be configured in .env"
            )
        request_token = extract_request_token(redirect_or_token)

        if not self._exchange_lock.acquire(blocking=False):
            raise ProviderError("Kite authentication exchange already in progress")
        try:
            access_token = exchange_access_token(
                api_key=api_key,
                api_secret=api_secret,
                request_token=request_token,
            )
            upsert_env_file(
                self.env_path,
                {
                    "KITE_API_KEY": api_key,
                    "KITE_API_SECRET": api_secret,
                    "KITE_ACCESS_TOKEN": access_token,
                },
            )
            force_inject_kite_env(self.env_path)
            result = verify_env_injection(
                self.env_path,
                expected_access_token=access_token,
            )
            if not result.ok:
                raise ProviderError(f"kite auth verify failed: {result.detail}")
            return KiteSessionStatus(
                required=True,
                connected=True,
                state="connected",
                detail=result.detail,
                user_id=result.user_id,
            )
        finally:
            self._exchange_lock.release()
