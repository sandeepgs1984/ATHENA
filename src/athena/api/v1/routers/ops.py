"""Live Operations endpoint router (P9.7)."""

from __future__ import annotations

from datetime import datetime, timezone

from fastapi import APIRouter, Depends, Request, status
from fastapi.responses import StreamingResponse

from athena.api.dependencies import get_ops_service
from athena.api.security import Permission, RequirePermission
from athena.api.security.models import AuthenticatedPrincipal
from athena.api.v1.dtos import AthenaResponse, ResponseMeta
from athena.api.v1.dtos.ops import (
    BackupCreateResultDTO,
    BackupInfoDTO,
    OpsTelemetryDTO,
    RestoreRequestDTO,
    RestoreResultDTO,
)
from athena.api.v1.services.ops_service import OpsService

router = APIRouter(prefix="/ops", tags=["Operations"])


def _meta(request: Request) -> ResponseMeta:
    request_id = getattr(request.state, "request_id", "unknown")
    return ResponseMeta(
        request_id=request_id,
        api_version="v1",
        as_of=datetime.now(tz=timezone.utc),
    )


@router.get(
    "/stream",
    summary="SSE live operations warning stream",
    operation_id="streamOpsEvents",
)
def stream_ops_events(
    request: Request,
    service: OpsService = Depends(get_ops_service),  # noqa: B008
    principal: AuthenticatedPrincipal = Depends(RequirePermission(Permission.READ)),  # noqa: B008
) -> StreamingResponse:
    """Server-Sent Events stream of heartbeats and derived operational warnings."""
    max_events = 0
    # TestClient / harness can request a finite stream via query param
    raw = request.query_params.get("max_events")
    if raw is not None:
        try:
            max_events = max(0, int(raw))
        except ValueError:
            max_events = 0

    generator = service.iter_sse_events(max_events=max_events or 0)
    return StreamingResponse(
        generator,
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


@router.get(
    "/telemetry",
    response_model=AthenaResponse[OpsTelemetryDTO],
    summary="Get stage telemetry for latest pipeline run",
    status_code=status.HTTP_200_OK,
    operation_id="getOpsTelemetry",
)
def get_ops_telemetry(
    request: Request,
    service: OpsService = Depends(get_ops_service),  # noqa: B008
    principal: AuthenticatedPrincipal = Depends(RequirePermission(Permission.READ)),  # noqa: B008
) -> AthenaResponse[OpsTelemetryDTO]:
    """Return stage statuses for Chart.js Operations telemetry."""
    data = service.get_telemetry()
    return AthenaResponse(status="success", data=data, meta=_meta(request))


@router.get(
    "/backups",
    response_model=AthenaResponse[list[BackupInfoDTO]],
    summary="List database backups",
    status_code=status.HTTP_200_OK,
    operation_id="listOpsBackups",
)
def list_ops_backups(
    request: Request,
    service: OpsService = Depends(get_ops_service),  # noqa: B008
    principal: AuthenticatedPrincipal = Depends(RequirePermission(Permission.READ)),  # noqa: B008
) -> AthenaResponse[list[BackupInfoDTO]]:
    """List backup artifacts under the configured backups directory."""
    data = service.list_backups()
    return AthenaResponse(status="success", data=data, meta=_meta(request))


@router.post(
    "/backups",
    response_model=AthenaResponse[BackupCreateResultDTO],
    summary="Create a database backup",
    status_code=status.HTTP_201_CREATED,
    operation_id="createOpsBackup",
)
def create_ops_backup(
    request: Request,
    service: OpsService = Depends(get_ops_service),  # noqa: B008
    principal: AuthenticatedPrincipal = Depends(RequirePermission(Permission.ADMIN)),  # noqa: B008
) -> AthenaResponse[BackupCreateResultDTO]:
    """Create an integrity-verified SQLite backup of the live database."""
    data = service.create_backup_now()
    return AthenaResponse(status="success", data=data, meta=_meta(request))


@router.post(
    "/backups/{backup_id}/restore",
    response_model=AthenaResponse[RestoreResultDTO],
    summary="Restore database from backup",
    status_code=status.HTTP_200_OK,
    operation_id="restoreOpsBackup",
)
def restore_ops_backup(
    backup_id: str,
    body: RestoreRequestDTO,
    request: Request,
    service: OpsService = Depends(get_ops_service),  # noqa: B008
    principal: AuthenticatedPrincipal = Depends(RequirePermission(Permission.ADMIN)),  # noqa: B008
) -> AthenaResponse[RestoreResultDTO]:
    """Restore live DB from backup. Requires confirmation token CONFIRM."""
    data = service.restore_backup_now(backup_id, body.confirmation)
    return AthenaResponse(status="success", data=data, meta=_meta(request))
