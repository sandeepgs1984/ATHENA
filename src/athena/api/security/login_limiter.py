"""Deterministic in-process login attempt limiter (Live Entry M-E5)."""

from __future__ import annotations

import threading
from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

from athena.api.security.exceptions import AuthenticationLockedError


@dataclass(frozen=True, slots=True)
class LoginLimitPolicy:
    """Immutable failed-login policy."""

    max_failures: int = 5
    window_minutes: int = 10
    lockout_minutes: int = 15

    def __post_init__(self) -> None:
        if self.max_failures < 1:
            raise ValueError("max_failures must be >= 1")
        if self.window_minutes < 1:
            raise ValueError("window_minutes must be >= 1")
        if self.lockout_minutes < 1:
            raise ValueError("lockout_minutes must be >= 1")


@dataclass(frozen=True, slots=True)
class _AttemptState:
    failures: int
    window_started: datetime
    locked_until: datetime | None = None


class LoginAttemptLimiter:
    """Limit failed unlocks per normalized username and local client IP."""

    def __init__(
        self,
        policy: LoginLimitPolicy,
        *,
        now_fn: Callable[[], datetime] | None = None,
    ) -> None:
        self._policy = policy
        self._now = now_fn or (lambda: datetime.now(tz=timezone.utc))
        self._states: dict[tuple[str, str], _AttemptState] = {}
        self._guard = threading.Lock()

    def check(self, *, username: str, ip_address: str) -> None:
        """Raise if this identity is currently locked."""
        key = self._key(username, ip_address)
        now = self._aware_now()
        with self._guard:
            state = self._states.get(key)
            if state is None:
                return
            if state.locked_until is not None:
                if now < state.locked_until:
                    raise AuthenticationLockedError(
                        retry_after_seconds=self._retry_seconds(
                            state.locked_until, now
                        )
                    )
                self._states.pop(key, None)
                return
            if now - state.window_started >= timedelta(
                minutes=self._policy.window_minutes
            ):
                self._states.pop(key, None)

    def record_failure(self, *, username: str, ip_address: str) -> None:
        """Record a failed login; lock and raise when threshold is reached."""
        key = self._key(username, ip_address)
        now = self._aware_now()
        window = timedelta(minutes=self._policy.window_minutes)
        with self._guard:
            previous = self._states.get(key)
            if previous is None or now - previous.window_started >= window:
                failures = 1
                window_started = now
            else:
                failures = previous.failures + 1
                window_started = previous.window_started

            if failures >= self._policy.max_failures:
                locked_until = now + timedelta(
                    minutes=self._policy.lockout_minutes
                )
                self._states[key] = _AttemptState(
                    failures=failures,
                    window_started=window_started,
                    locked_until=locked_until,
                )
                raise AuthenticationLockedError(
                    retry_after_seconds=self._retry_seconds(locked_until, now)
                )

            self._states[key] = _AttemptState(
                failures=failures,
                window_started=window_started,
            )

    def record_success(self, *, username: str, ip_address: str) -> None:
        """Clear failures after a successful unlock."""
        with self._guard:
            self._states.pop(self._key(username, ip_address), None)

    @staticmethod
    def _key(username: str, ip_address: str) -> tuple[str, str]:
        return (username.strip().casefold(), ip_address.strip() or "unknown")

    def _aware_now(self) -> datetime:
        now = self._now()
        if now.tzinfo is None:
            raise ValueError("login limiter clock must return timezone-aware datetime")
        return now

    @staticmethod
    def _retry_seconds(until: datetime, now: datetime) -> int:
        return max(1, int((until - now).total_seconds()))
