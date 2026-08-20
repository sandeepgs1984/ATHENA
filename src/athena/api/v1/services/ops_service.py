"""Live Operations service (P9.7).

SSE warning derivation, stage telemetry aggregation, and manual DB backup/restore
orchestration. Contains zero HTTP knowledge.
"""

from __future__ import annotations

import json
import os
import time
import uuid
from collections.abc import Iterator
from datetime import datetime, timezone
from pathlib import Path
from typing import TYPE_CHECKING

from athena.api.exceptions import (
    BackupNotFoundError,
    DatabaseUnavailableError,
    RestoreConfirmationError,
)
from athena.api.v1.dtos.base import (
    PaginationParams,
    QuerySpecification,
    SortParams,
)
from athena.api.v1.dtos.ops import (
    BackupCreateResultDTO,
    BackupInfoDTO,
    OpsTelemetryDTO,
    OpsWarningDTO,
    RestoreResultDTO,
    StageTelemetryDTO,
)
from athena.api.v1.dtos.pipelines import PipelineRunFilterParams
from athena.config.loader import load_notifications_config
from athena.data.store.backup import create_backup, restore_backup
from athena.data.store.repository import SqliteRepository
from athena.errors import RepositoryError

if TYPE_CHECKING:
    from athena.api.v1.providers.base import (
        HealthProvider,
        MetricsProvider,
        PipelineRunProvider,
    )

_CONFIRM_TOKEN = "CONFIRM"
_META_SUFFIX = ".meta.json"
_SSE_INTERVAL_SEC = 2.0
_SSE_MAX_EVENTS_DEFAULT = 0  # 0 = unbounded (production); tests pass max_events


def _resolve_repo_root() -> Path:
    current = Path(__file__).resolve().parent
    for _ in range(12):
        if (current / "pyproject.toml").is_file() and (current / "src").is_dir():
            return current
        current = current.parent
    return Path.cwd()


def default_db_path() -> Path:
    env = os.environ.get("ATHENA_DB_PATH")
    if env:
        return Path(env)
    return _resolve_repo_root() / "db" / "athena.db"


def default_backup_dir() -> Path:
    env = os.environ.get("ATHENA_BACKUP_DIR")
    if env:
        return Path(env)
    return _resolve_repo_root() / "db" / "backups"


def default_briefings_dir(config_dir: Path) -> Path:
    """Resolve the daily-briefing file-notifier output dir the same way
    BriefingDispatcher itself does (DD-9 webhook+file) -- relative to repo
    root unless the configured path is already absolute."""
    output_dir = Path(load_notifications_config(config_dir).channels.file.output_dir)
    return output_dir if output_dir.is_absolute() else _resolve_repo_root() / output_dir


class OpsService:
    """Coordinates Live Operations console data and admin actions."""

    def __init__(
        self,
        health_provider: HealthProvider,
        metrics_provider: MetricsProvider,
        pipeline_run_provider: PipelineRunProvider,
        *,
        db_path: Path | None = None,
        backup_dir: Path | None = None,
    ) -> None:
        self._health_provider = health_provider
        self._metrics_provider = metrics_provider
        self._pipeline_run_provider = pipeline_run_provider
        self._db_path = Path(db_path) if db_path else default_db_path()
        self._backup_dir = Path(backup_dir) if backup_dir else default_backup_dir()

    @property
    def db_path(self) -> Path:
        return self._db_path

    @property
    def backup_dir(self) -> Path:
        return self._backup_dir

    def collect_warnings(self) -> list[OpsWarningDTO]:
        """Derive current operational warnings from health, metrics, and latest run."""
        now = datetime.now(tz=timezone.utc)
        warnings: list[OpsWarningDTO] = []

        try:
            health = self._health_provider.get_health()
            if health.status != "healthy":
                warnings.append(
                    OpsWarningDTO(
                        event_id=f"warn-health-{uuid.uuid4().hex[:8]}",
                        severity="critical" if health.status == "unavailable" else "warning",
                        source="health",
                        message=f"Platform health is {health.status.upper()}",
                        as_of=now,
                        details={"status": health.status, "version": health.version},
                    )
                )
            for component in health.components:
                if component.status != "healthy":
                    warnings.append(
                        OpsWarningDTO(
                            event_id=f"warn-comp-{uuid.uuid4().hex[:8]}",
                            severity="warning",
                            source=f"health.{component.name}",
                            message=component.detail
                            or f"Component {component.name} is {component.status}",
                            as_of=now,
                            details={"component": component.name, "status": component.status},
                        )
                    )
        except Exception as exc:  # noqa: BLE001 — surface as warning, never crash SSE
            warnings.append(
                OpsWarningDTO(
                    event_id=f"warn-health-err-{uuid.uuid4().hex[:8]}",
                    severity="critical",
                    source="health",
                    message=f"Health provider failed: {exc}",
                    as_of=now,
                    details={},
                )
            )

        try:
            metrics = self._metrics_provider.get_metrics()
            if metrics.pipeline_runs_failed > 0:
                warnings.append(
                    OpsWarningDTO(
                        event_id=f"warn-metrics-{uuid.uuid4().hex[:8]}",
                        severity="warning",
                        source="metrics",
                        message=(
                            f"{metrics.pipeline_runs_failed} pipeline run(s) failed "
                            f"(total {metrics.pipeline_runs_total})"
                        ),
                        as_of=now,
                        details={
                            "pipeline_runs_failed": metrics.pipeline_runs_failed,
                            "pipeline_runs_total": metrics.pipeline_runs_total,
                        },
                    )
                )
        except Exception as exc:  # noqa: BLE001
            warnings.append(
                OpsWarningDTO(
                    event_id=f"warn-metrics-err-{uuid.uuid4().hex[:8]}",
                    severity="warning",
                    source="metrics",
                    message=f"Metrics provider failed: {exc}",
                    as_of=now,
                    details={},
                )
            )

        telemetry = self.get_telemetry()
        for stage in telemetry.stages:
            status_u = stage.status.upper()
            if status_u in {"FAILED", "ERROR", "TIMEOUT"}:
                warnings.append(
                    OpsWarningDTO(
                        event_id=f"warn-stage-{uuid.uuid4().hex[:8]}",
                        severity="critical",
                        source=f"pipeline.{stage.stage_id}",
                        message=stage.message or f"Stage {stage.stage_id} {status_u}",
                        as_of=now,
                        details={
                            "stage_id": stage.stage_id,
                            "status": stage.status,
                            "run_id": telemetry.run_id,
                        },
                    )
                )

        if not self._db_path.exists():
            warnings.append(
                OpsWarningDTO(
                    event_id=f"warn-db-{uuid.uuid4().hex[:8]}",
                    severity="warning",
                    source="database",
                    message=f"Live database not found at {self._db_path}",
                    as_of=now,
                    details={"db_path": str(self._db_path)},
                )
            )

        return warnings

    def iter_sse_events(
        self,
        *,
        interval_sec: float = _SSE_INTERVAL_SEC,
        max_events: int = _SSE_MAX_EVENTS_DEFAULT,
    ) -> Iterator[str]:
        """Yield SSE-formatted event strings (event + data lines)."""
        emitted = 0
        while True:
            now = datetime.now(tz=timezone.utc)
            heartbeat = OpsWarningDTO(
                event_id=f"hb-{uuid.uuid4().hex[:8]}",
                severity="heartbeat",
                source="ops.stream",
                message="ops stream heartbeat",
                as_of=now,
                details={},
            )
            yield self._format_sse("heartbeat", heartbeat)

            for warning in self.collect_warnings():
                yield self._format_sse("warning", warning)

            emitted += 1
            if max_events > 0 and emitted >= max_events:
                break
            time.sleep(interval_sec)

    @staticmethod
    def _format_sse(event: str, payload: OpsWarningDTO) -> str:
        data = payload.model_dump(mode="json")
        return f"event: {event}\ndata: {json.dumps(data, default=str)}\n\n"

    def get_telemetry(self) -> OpsTelemetryDTO:
        """Return stage rows from the latest system pipeline run, if any."""
        spec = QuerySpecification(
            filters=PipelineRunFilterParams(),
            sort=SortParams(sort_by="as_of", sort_dir="desc"),
            pagination=PaginationParams(page=1, page_size=1),
        )
        result = self._pipeline_run_provider.get_runs(spec)
        if not result.items:
            return OpsTelemetryDTO(
                run_id=None,
                as_of=None,
                overall_status=None,
                stages=[],
            )

        latest = result.items[0]
        stages: list[StageTelemetryDTO] = []
        for pr in latest.pipeline_runs:
            for stage in pr.stages:
                status_str = (
                    stage.status.value
                    if hasattr(stage.status, "value")
                    else str(stage.status)
                )
                stages.append(
                    StageTelemetryDTO(
                        stage_id=stage.stage_id,
                        status=status_str,
                        message=stage.message or "",
                        pipeline_run_id=pr.pipeline_run_id,
                        duration_ms=None,
                    )
                )

        overall = (
            latest.overall_status.value
            if hasattr(latest.overall_status, "value")
            else str(latest.overall_status)
        )
        return OpsTelemetryDTO(
            run_id=latest.run_id,
            as_of=latest.as_of,
            overall_status=overall,
            stages=stages,
        )

    def list_backups(self) -> list[BackupInfoDTO]:
        """List `.db` backup artifacts in the configured backup directory."""
        if not self._backup_dir.exists():
            return []

        items: list[BackupInfoDTO] = []
        for path in sorted(self._backup_dir.glob("*.db"), key=lambda p: p.stat().st_mtime, reverse=True):
            if path.name.endswith(".restore.tmp") or path.suffix == ".tmp":
                continue
            items.append(self._backup_info(path))
        return items

    def create_backup_now(self) -> BackupCreateResultDTO:
        """Create a timestamped backup of the live database."""
        repo = self._open_live_repository()
        try:
            self._backup_dir.mkdir(parents=True, exist_ok=True)
            stamp = datetime.now(tz=timezone.utc).strftime("%Y%m%dT%H%M%SZ")
            dest = self._backup_dir / f"athena-{stamp}.db"
            as_of = datetime.now(tz=timezone.utc)
            result = create_backup(repo, dest, as_of=as_of)
            return BackupCreateResultDTO(
                backup_id=dest.name,
                destination=result.destination,
                schema_version=result.schema_version,
                record_counts=dict(result.record_counts),
                integrity_ok=result.integrity_ok,
                ts=result.ts,
                explanation=result.explanation,
            )
        finally:
            repo.close()

    def restore_backup_now(self, backup_id: str, confirmation: str) -> RestoreResultDTO:
        """Restore live DB from backup_id after typed CONFIRM gate."""
        if confirmation != _CONFIRM_TOKEN:
            raise RestoreConfirmationError(
                "Restore refused: confirmation must be the exact token CONFIRM"
            )

        backup_path = self._resolve_backup(backup_id)
        as_of = datetime.now(tz=timezone.utc)
        # Ensure parent exists; refuse if live path parent cannot be created
        self._db_path.parent.mkdir(parents=True, exist_ok=True)
        try:
            result = restore_backup(backup_path, self._db_path, as_of=as_of)
        except RepositoryError:
            raise
        return RestoreResultDTO(
            ok=result.ok,
            source=result.source,
            target=result.target,
            schema_version=result.schema_version,
            record_counts=dict(result.record_counts),
            integrity_ok=result.integrity_ok,
            foreign_keys_ok=result.foreign_keys_ok,
            schema_version_ok=result.schema_version_ok,
            counts_match=result.counts_match,
            ts=result.ts,
            explanation=result.explanation,
            issues=list(result.issues),
        )

    def _open_live_repository(self) -> SqliteRepository:
        if not self._db_path.exists():
            raise DatabaseUnavailableError(
                f"Live database not found at {self._db_path}; cannot create backup"
            )
        try:
            return SqliteRepository(self._db_path)
        except RepositoryError as exc:
            raise DatabaseUnavailableError(str(exc)) from exc

    def _resolve_backup(self, backup_id: str) -> Path:
        # Prevent path traversal — only basename under backup_dir
        safe_name = Path(backup_id).name
        if safe_name != backup_id or ".." in backup_id or "/" in backup_id or "\\" in backup_id:
            raise BackupNotFoundError(f"Backup '{backup_id}' not found")
        path = self._backup_dir / safe_name
        if not path.is_file():
            raise BackupNotFoundError(f"Backup '{backup_id}' not found")
        return path

    def _backup_info(self, path: Path) -> BackupInfoDTO:
        stat = path.stat()
        schema_version = None
        record_counts = None
        created_ts = None
        meta_path = path.with_name(path.name + _META_SUFFIX)
        if meta_path.is_file():
            try:
                meta = json.loads(meta_path.read_text(encoding="utf-8"))
                schema_version = int(meta["schema_version"]) if "schema_version" in meta else None
                if "record_counts" in meta:
                    record_counts = {k: int(v) for k, v in meta["record_counts"].items()}
                if "created_ts" in meta:
                    created_ts = datetime.fromisoformat(meta["created_ts"])
            except (OSError, ValueError, KeyError, TypeError):
                pass

        return BackupInfoDTO(
            backup_id=path.name,
            filename=path.name,
            path=str(path),
            size_bytes=stat.st_size,
            modified_at=datetime.fromtimestamp(stat.st_mtime, tz=timezone.utc),
            schema_version=schema_version,
            record_counts=record_counts,
            created_ts=created_ts,
        )
