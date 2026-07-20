"""System health objects (F-8): ATHENA knows whether it is healthy before it advises."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from athena.domain.enums import HealthStatus


@dataclass(frozen=True, slots=True)
class HealthCheck:
    """One named check with its result and human-readable detail."""

    name: str
    status: HealthStatus
    detail: str

    def __post_init__(self) -> None:
        if not self.detail:
            raise ValueError("HealthCheck.detail is mandatory — health failures name their fix")


@dataclass(frozen=True, slots=True)
class SystemHealthReport:
    """Pre-flight report (ATHENA-002 §8.0). BLOCKED ⇒ the run emits no recommendations."""

    ts: datetime
    checks: tuple[HealthCheck, ...]

    def __post_init__(self) -> None:
        if not self.checks:
            raise ValueError("SystemHealthReport must contain at least one check")

    @property
    def status(self) -> HealthStatus:
        statuses = {c.status for c in self.checks}
        if HealthStatus.BLOCKED in statuses:
            return HealthStatus.BLOCKED
        if HealthStatus.WARN in statuses:
            return HealthStatus.WARN
        return HealthStatus.OK

    @property
    def blocking_issues(self) -> tuple[HealthCheck, ...]:
        return tuple(c for c in self.checks if c.status is HealthStatus.BLOCKED)
