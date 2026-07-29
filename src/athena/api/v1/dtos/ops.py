"""Live Operations DTOs (P9.7)."""

from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class OpsWarningDTO(BaseModel):
    """A single operational warning or heartbeat event for the SSE feed."""

    model_config = ConfigDict(frozen=True)

    event_id: str
    severity: Literal["info", "warning", "critical", "heartbeat"]
    source: str
    message: str
    as_of: datetime
    details: dict[str, object] = Field(default_factory=dict)


class StageTelemetryDTO(BaseModel):
    """Stage status row for Operations telemetry charts."""

    model_config = ConfigDict(frozen=True)

    stage_id: str
    status: str
    message: str
    pipeline_run_id: str | None = None
    duration_ms: int | None = None


class OpsTelemetryDTO(BaseModel):
    """Aggregated stage telemetry for the latest system pipeline run."""

    model_config = ConfigDict(frozen=True)

    run_id: str | None
    as_of: datetime | None
    overall_status: str | None
    stages: list[StageTelemetryDTO]


class KiteStatusDTO(BaseModel):
    """Secret-free Kite session state for the workstation gate."""

    model_config = ConfigDict(frozen=True)

    required: bool
    connected: bool
    state: Literal[
        "not_required",
        "missing",
        "misconfigured",
        "connected",
        "expired",
        "unavailable",
    ]
    detail: str
    user_id: str | None = None


class KiteAuthStartDTO(BaseModel):
    """Login URL returned to the authenticated owner."""

    model_config = ConfigDict(frozen=True)

    login_url: str | None
    ready: bool
    detail: str


class KiteAuthCompleteRequestDTO(BaseModel):
    """Kite redirect URL or bare one-time request token."""

    model_config = ConfigDict(frozen=True)

    redirect_or_token: str = Field(min_length=1, max_length=4096)


class BackupInfoDTO(BaseModel):
    """Metadata for one backup artifact under the backups directory."""

    model_config = ConfigDict(frozen=True)

    backup_id: str
    filename: str
    path: str
    size_bytes: int
    modified_at: datetime
    schema_version: int | None = None
    record_counts: dict[str, int] | None = None
    created_ts: datetime | None = None


class BackupCreateResultDTO(BaseModel):
    """Result of creating a backup."""

    model_config = ConfigDict(frozen=True)

    backup_id: str
    destination: str
    schema_version: int
    record_counts: dict[str, int]
    integrity_ok: bool
    ts: datetime
    explanation: str


class RestoreRequestDTO(BaseModel):
    """Destructive restore gate — confirmation must equal CONFIRM."""

    model_config = ConfigDict(frozen=True)

    confirmation: str


class RestoreResultDTO(BaseModel):
    """Result of a restore operation."""

    model_config = ConfigDict(frozen=True)

    ok: bool
    source: str
    target: str
    schema_version: int
    record_counts: dict[str, int]
    integrity_ok: bool
    foreign_keys_ok: bool
    schema_version_ok: bool
    counts_match: bool
    ts: datetime
    explanation: str
    issues: list[str] = Field(default_factory=list)


class RestartResultDTO(BaseModel):
    """Acknowledgement that a full process restart has been scheduled
    (owner-requested "kill everything and restart fresh," 2026-07-29) —
    the process itself is about to end, so this is the last response it
    sends before doing so, not a claim that it already finished."""

    model_config = ConfigDict(frozen=True)

    restarting: bool
    detail: str
