"""Configuration loader: files → validated AthenaConfig + ConfigurationSnapshot.

Determinism: the snapshot hash is computed over a canonical JSON serialization
(sorted keys, no whitespace variance), so identical config ⇒ identical hash,
on any machine, forever (ATHENA-000 p11/p12).
"""

from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from pydantic import ValidationError

from athena.config.models import (
    AnalyticsConfig,
    AthenaConfig,
    BacktestConfig,
    ConfidenceConfig,
    DecisionConfig,
    EventsFile,
    ExpiriesFile,
    FileProviderConfig,
    HolidaysFile,
    MarketHealthConfig,
    RiskAssessmentConfig,
    ScoringConfig,
    SectorHealthConfig,
    StrategyConfig,
    ValidationConfig,
    WatchlistConfig,
)
from athena.domain.run import ConfigurationSnapshot
from athena.errors import ConfigError

_REQUIRED_FILES = (
    "base.json",
    "market.nse.json",
    "risk.json",
    "capital.json",
    "regime.json",
    "universe.json",
    "indicators.json",
)


def _read_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        raise ConfigError(f"Missing configuration file: {path}")
    try:
        with path.open(encoding="utf-8") as fh:
            data = json.load(fh)
    except json.JSONDecodeError as exc:
        raise ConfigError(f"Invalid JSON in {path}: {exc}") from exc
    if not isinstance(data, dict):
        raise ConfigError(f"{path} must contain a JSON object at top level")
    return data


def _validation_message(name: str, exc: ValidationError) -> str:
    lines = [f"Configuration invalid in {name}:"]
    for err in exc.errors():
        location = ".".join(str(p) for p in err["loc"]) or "(root)"
        lines.append(f"  - {location}: {err['msg']}")
    return "\n".join(lines)


def load_config(config_dir: Path, profile_name: str | None = None) -> AthenaConfig:
    """Load and validate the full configuration tree. Raises ConfigError with
    a human-readable message on ANY problem — ATHENA refuses to run on bad config."""

    config_dir = Path(config_dir)
    if not config_dir.is_dir():
        raise ConfigError(f"Config directory not found: {config_dir}")

    raw = {name.split(".")[0].replace("market", "market"): _read_json(config_dir / name)
           for name in _REQUIRED_FILES}
    base_raw = raw["base"]

    profile = profile_name or base_raw.get("active_profile")
    if not profile:
        raise ConfigError("base.json must define 'active_profile'")
    profile_path = config_dir / "profiles" / f"{profile}.json"
    if not profile_path.exists():
        available = sorted(p.stem for p in (config_dir / "profiles").glob("*.json"))
        raise ConfigError(
            f"Strategy profile '{profile}' not found at {profile_path}. Available: {available}"
        )

    tree: dict[str, Any] = {
        "base": base_raw,
        "market": raw["market"],
        "risk": raw["risk"],
        "capital": raw["capital"],
        "regime": raw["regime"],
        "universe": raw["universe"],
        "indicators": raw["indicators"],
        "profile": _read_json(profile_path),
    }

    try:
        return AthenaConfig.model_validate(tree)
    except ValidationError as exc:
        raise ConfigError(_validation_message(str(config_dir), exc)) from exc


def load_calendar_files(config_dir: Path) -> tuple[HolidaysFile, ExpiriesFile, EventsFile]:
    """Load + validate calendar DATA files (consumed by the Calendar Engine)."""

    cal_dir = Path(config_dir) / "calendar"
    try:
        holidays = HolidaysFile.model_validate(_read_json(cal_dir / "holidays.json"))
        expiries = ExpiriesFile.model_validate(_read_json(cal_dir / "expiries.json"))
        events = EventsFile.model_validate(_read_json(cal_dir / "events.json"))
    except ValidationError as exc:
        raise ConfigError(_validation_message(str(cal_dir), exc)) from exc
    return holidays, expiries, events


def load_file_provider_config(config_dir: Path) -> FileProviderConfig:
    """Load + validate the FileProvider settings (config/providers/file.json)."""

    path = Path(config_dir) / "providers" / "file.json"
    try:
        return FileProviderConfig.model_validate(_read_json(path))
    except ValidationError as exc:
        raise ConfigError(_validation_message(str(path), exc)) from exc


def load_validation_config(config_dir: Path) -> ValidationConfig:
    """Load + validate the Validation Layer settings (config/validation.json)."""

    path = Path(config_dir) / "validation.json"
    try:
        return ValidationConfig.model_validate(_read_json(path))
    except ValidationError as exc:
        raise ConfigError(_validation_message(str(path), exc)) from exc


def load_market_health_config(config_dir: Path) -> MarketHealthConfig:
    """Load + validate the Market Health Engine settings (config/market_health.json)."""

    path = Path(config_dir) / "market_health.json"
    try:
        return MarketHealthConfig.model_validate(_read_json(path))
    except ValidationError as exc:
        raise ConfigError(_validation_message(str(path), exc)) from exc


def load_sector_health_config(config_dir: Path) -> SectorHealthConfig:
    """Load + validate the Sector Health Engine settings (config/sector_health.json)."""

    path = Path(config_dir) / "sector_health.json"
    try:
        return SectorHealthConfig.model_validate(_read_json(path))
    except ValidationError as exc:
        raise ConfigError(_validation_message(str(path), exc)) from exc


def load_scoring_config(config_dir: Path) -> ScoringConfig:
    """Load + validate the Scoring Engine settings (config/scoring.json)."""

    path = Path(config_dir) / "scoring.json"
    try:
        return ScoringConfig.model_validate(_read_json(path))
    except ValidationError as exc:
        raise ConfigError(_validation_message(str(path), exc)) from exc


def load_confidence_config(config_dir: Path) -> ConfidenceConfig:
    """Load + validate the Confidence Engine settings (config/confidence.json)."""

    path = Path(config_dir) / "confidence.json"
    try:
        return ConfidenceConfig.model_validate(_read_json(path))
    except ValidationError as exc:
        raise ConfigError(_validation_message(str(path), exc)) from exc


def load_risk_assessment_config(config_dir: Path) -> RiskAssessmentConfig:
    """Load + validate the Risk Engine settings (config/risk_assessment.json)."""

    path = Path(config_dir) / "risk_assessment.json"
    try:
        return RiskAssessmentConfig.model_validate(_read_json(path))
    except ValidationError as exc:
        raise ConfigError(_validation_message(str(path), exc)) from exc


def load_decision_config(config_dir: Path) -> DecisionConfig:
    """Load + validate the Decision Engine settings (config/decision.json)."""

    path = Path(config_dir) / "decision.json"
    try:
        return DecisionConfig.model_validate(_read_json(path))
    except ValidationError as exc:
        raise ConfigError(_validation_message(str(path), exc)) from exc


def load_watchlist_config(config_dir: Path) -> WatchlistConfig:
    """Load + validate the Watchlist Manager settings (config/watchlist.json)."""

    path = Path(config_dir) / "watchlist.json"
    try:
        return WatchlistConfig.model_validate(_read_json(path))
    except ValidationError as exc:
        raise ConfigError(_validation_message(str(path), exc)) from exc


def load_strategy_config(config_dir: Path) -> StrategyConfig:
    """Load + validate the Strategy Framework settings (config/strategy.json)."""

    path = Path(config_dir) / "strategy.json"
    try:
        return StrategyConfig.model_validate(_read_json(path))
    except ValidationError as exc:
        raise ConfigError(_validation_message(str(path), exc)) from exc


def load_backtest_config(config_dir: Path) -> BacktestConfig:
    """Load + validate the Backtesting Engine settings (config/backtest.json)."""

    path = Path(config_dir) / "backtest.json"
    try:
        return BacktestConfig.model_validate(_read_json(path))
    except ValidationError as exc:
        raise ConfigError(_validation_message(str(path), exc)) from exc


def load_analytics_config(config_dir: Path) -> AnalyticsConfig:
    """Load + validate the Reporting & Analytics settings (config/analytics.json)."""

    path = Path(config_dir) / "analytics.json"
    try:
        return AnalyticsConfig.model_validate(_read_json(path))
    except ValidationError as exc:
        raise ConfigError(_validation_message(str(path), exc)) from exc


def _canonical_json(config: AthenaConfig) -> str:
    return json.dumps(config.model_dump(mode="json"), sort_keys=True, separators=(",", ":"))


def snapshot_config(config: AthenaConfig, now: datetime | None = None) -> ConfigurationSnapshot:
    """Freeze the validated config for a run (F-13). Hash is content-addressed."""

    payload = _canonical_json(config)
    content_hash = hashlib.sha256(payload.encode("utf-8")).hexdigest()
    created = now or datetime.now(timezone.utc)
    return ConfigurationSnapshot(
        snapshot_id=f"cfg-{content_hash[:16]}",
        content_hash=content_hash,
        payload_json=payload,
        created_ts=created,
    )
