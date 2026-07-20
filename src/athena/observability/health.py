"""System-health pre-flight (F-8, ATHENA-002 §8.0).

Phase 0 checks what exists in Phase 0; checks that depend on later phases
report WARN with an honest "arrives in Phase N" detail rather than pretending.
"""

from __future__ import annotations

from datetime import date, datetime, timezone
from pathlib import Path

from athena.config.loader import load_calendar_files, load_config
from athena.domain.enums import HealthStatus
from athena.domain.health import HealthCheck, SystemHealthReport
from athena.errors import ConfigError


def _check_config(config_dir: Path) -> HealthCheck:
    try:
        load_config(config_dir)
        return HealthCheck("config", HealthStatus.OK, f"all config valid in {config_dir}")
    except ConfigError as exc:
        return HealthCheck("config", HealthStatus.BLOCKED, str(exc))


def _check_calendar(config_dir: Path, for_date: date) -> HealthCheck:
    try:
        holidays, _, _ = load_calendar_files(config_dir)
    except ConfigError as exc:
        return HealthCheck("calendar_data", HealthStatus.BLOCKED, str(exc))
    if for_date.year not in holidays.years:
        return HealthCheck(
            "calendar_data",
            HealthStatus.BLOCKED,
            f"no holiday data for {for_date.year} — update config/calendar/holidays.json",
        )
    return HealthCheck("calendar_data", HealthStatus.OK,
                       f"calendar data covers {sorted(holidays.years)}")


def _check_writable(name: str, directory: Path) -> HealthCheck:
    try:
        directory.mkdir(parents=True, exist_ok=True)
        probe = directory / ".health_probe"
        probe.write_text("ok", encoding="utf-8")
        probe.unlink()
        return HealthCheck(name, HealthStatus.OK, f"{directory} is writable")
    except OSError as exc:
        return HealthCheck(name, HealthStatus.BLOCKED, f"{directory} not writable: {exc}")


def run_system_checks(config_dir: Path, repo_root: Path,
                      for_date: date | None = None,
                      now: datetime | None = None) -> SystemHealthReport:
    """Every morning ATHENA knows whether it is healthy before recommending (F-8)."""

    today = for_date or datetime.now(timezone.utc).date()
    checks = [
        _check_config(config_dir),
        _check_calendar(config_dir, today),
        _check_writable("storage", repo_root / "db"),
        _check_writable("logs", repo_root / "logs"),
        HealthCheck("provider", HealthStatus.WARN,
                    "no market data provider configured yet (arrives in Phase 1, DD-1)"),
        HealthCheck("replay", HealthStatus.WARN,
                    "replay engine arrives in Phase 5 (ATHENA-002 §14)"),
    ]
    return SystemHealthReport(ts=now or datetime.now(timezone.utc), checks=tuple(checks))
