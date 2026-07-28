"""Login lockout hardening tests (Live Entry M-E5)."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest

from athena.api.config import SecurityConfig, api_settings_from_env
from athena.api.security.exceptions import AuthenticationLockedError
from athena.api.security.login_limiter import LoginAttemptLimiter, LoginLimitPolicy


class MutableClock:
    def __init__(self, now: datetime) -> None:
        self.now = now

    def __call__(self) -> datetime:
        return self.now

    def advance(self, delta: timedelta) -> None:
        self.now += delta


def test_limiter_locks_at_threshold_and_unlocks_after_interval() -> None:
    clock = MutableClock(datetime(2026, 7, 24, 12, 0, tzinfo=timezone.utc))
    limiter = LoginAttemptLimiter(
        LoginLimitPolicy(max_failures=3, window_minutes=10, lockout_minutes=15),
        now_fn=clock,
    )

    limiter.record_failure(username="Owner", ip_address="127.0.0.1")
    limiter.record_failure(username="owner", ip_address="127.0.0.1")
    with pytest.raises(AuthenticationLockedError) as locked:
        limiter.record_failure(username="OWNER", ip_address="127.0.0.1")
    assert locked.value.retry_after_seconds == 900

    with pytest.raises(AuthenticationLockedError):
        limiter.check(username="owner", ip_address="127.0.0.1")

    clock.advance(timedelta(minutes=15))
    limiter.check(username="owner", ip_address="127.0.0.1")


def test_limiter_success_clears_failed_attempts() -> None:
    clock = MutableClock(datetime(2026, 7, 24, 12, 0, tzinfo=timezone.utc))
    limiter = LoginAttemptLimiter(
        LoginLimitPolicy(max_failures=2, window_minutes=10, lockout_minutes=15),
        now_fn=clock,
    )
    limiter.record_failure(username="owner", ip_address="127.0.0.1")
    limiter.record_success(username="owner", ip_address="127.0.0.1")
    limiter.record_failure(username="owner", ip_address="127.0.0.1")
    limiter.check(username="owner", ip_address="127.0.0.1")


def test_failure_window_expires_without_lockout() -> None:
    clock = MutableClock(datetime(2026, 7, 24, 12, 0, tzinfo=timezone.utc))
    limiter = LoginAttemptLimiter(
        LoginLimitPolicy(max_failures=2, window_minutes=5, lockout_minutes=15),
        now_fn=clock,
    )
    limiter.record_failure(username="owner", ip_address="127.0.0.1")
    clock.advance(timedelta(minutes=5))
    limiter.record_failure(username="owner", ip_address="127.0.0.1")
    limiter.check(username="owner", ip_address="127.0.0.1")


def test_production_settings_derive_jwt_secret_from_owner_hash(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("ATHENA_JWT_SECRET", raising=False)
    monkeypatch.setenv("ATHENA_OWNER_PASSWORD_HASH", "$2b$12$owner-hash")
    settings = api_settings_from_env()
    assert settings.security.jwt_secret != SecurityConfig().jwt_secret
    assert settings.security.jwt_secret != "$2b$12$owner-hash"
    assert len(settings.security.jwt_secret) == 64


def test_explicit_jwt_secret_wins(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("ATHENA_OWNER_PASSWORD_HASH", "$2b$12$owner-hash")
    monkeypatch.setenv("ATHENA_JWT_SECRET", "explicit-secret-at-least-32-bytes!!")
    assert (
        api_settings_from_env().security.jwt_secret
        == "explicit-secret-at-least-32-bytes!!"
    )


def test_create_app_rejects_short_jwt_secret() -> None:
    from athena.api.app import create_app
    from athena.api.config import APISettings, SecurityConfig

    short = SecurityConfig(jwt_secret="too-short-for-hs256")
    with pytest.raises(ValueError, match="at least 32 UTF-8 bytes"):
        create_app(APISettings(security=short))
