"""Run provenance objects (ATHENA-002 §4) — the replayability contract (ADR-005, F-13)."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from datetime import datetime

from athena.domain.enums import RunStatus, RunTrigger


@dataclass(frozen=True, slots=True)
class ConfigurationSnapshot:
    """Frozen configuration for a run. Replay uses THIS, never current files."""

    snapshot_id: str
    content_hash: str
    payload_json: str
    created_ts: datetime

    def __post_init__(self) -> None:
        if not self.content_hash:
            raise ValueError("ConfigurationSnapshot.content_hash is mandatory")
        if not self.payload_json:
            raise ValueError("ConfigurationSnapshot.payload_json is mandatory")


@dataclass(frozen=True, slots=True)
class RunRecord:
    """One pipeline execution with its full version vector (F-13)."""

    run_id: str
    cycle_id: str
    trigger: RunTrigger
    started_ts: datetime
    status: RunStatus
    software_version: str
    blueprint_version: str
    strategy_profile: str
    strategy_profile_version: str
    indicator_versions: Mapping[str, str]
    config_snapshot_id: str
    input_digest: str = ""
    finished_ts: datetime | None = None

    def __post_init__(self) -> None:
        for name in ("run_id", "software_version", "blueprint_version", "config_snapshot_id"):
            if not getattr(self, name):
                raise ValueError(f"RunRecord.{name} is mandatory (replayability, ATHENA-000 p8)")
