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
    KiteAuthCompleteRequestDTO,
    KiteAuthStartDTO,
    KiteStatusDTO,
    OpsTelemetryDTO,
    RestoreRequestDTO,
    RestoreResultDTO,
)
from athena.api.v1.services.ops_service import OpsService
from athena.ops.kite_session import KiteSessionService, KiteSessionStatus

router = APIRouter(prefix="/ops", tags=["Operations"])


def _meta(request: Request) -> ResponseMeta:
    request_id = getattr(request.state, "request_id", "unknown")
    return ResponseMeta(
        request_id=request_id,
        api_version="v1",
        as_of=datetime.now(tz=timezone.utc),
    )


def get_kite_session_service(request: Request) -> KiteSessionService:
    """Resolve the process-local Kite session service."""
    return request.app.state.kite_session_service


def _kite_status_dto(result: KiteSessionStatus) -> KiteStatusDTO:
    return KiteStatusDTO(
        required=result.required,
        connected=result.connected,
        state=result.state,
        detail=result.detail,
        user_id=result.user_id,
    )


@router.get(
    "/kite/status",
    response_model=AthenaResponse[KiteStatusDTO],
    summary="Verify the read-only Kite market-data session",
    status_code=status.HTTP_200_OK,
    operation_id="getKiteStatus",
)
def get_kite_status(
    request: Request,
    service: KiteSessionService = Depends(get_kite_session_service),  # noqa: B008
    principal: AuthenticatedPrincipal = Depends(RequirePermission(Permission.READ)),  # noqa: B008
) -> AthenaResponse[KiteStatusDTO]:
    """Return provider-aware, secret-free Kite session status."""
    return AthenaResponse(
        status="success",
        data=_kite_status_dto(service.status(verify=True)),
        meta=_meta(request),
    )


@router.post(
    "/kite/start-auth",
    response_model=AthenaResponse[KiteAuthStartDTO],
    summary="Start the interactive Kite login flow",
    status_code=status.HTTP_200_OK,
    operation_id="startKiteAuth",
)
def start_kite_auth(
    request: Request,
    service: KiteSessionService = Depends(get_kite_session_service),  # noqa: B008
    principal: AuthenticatedPrincipal = Depends(RequirePermission(Permission.ADMIN)),  # noqa: B008
) -> AthenaResponse[KiteAuthStartDTO]:
    """Return a Kite login URL; the browser opens it explicitly."""
    result = service.start_auth()
    return AthenaResponse(
        status="success",
        data=KiteAuthStartDTO(
            login_url=result.login_url,
            ready=result.ready,
            detail=result.detail,
        ),
        meta=_meta(request),
    )


@router.post(
    "/kite/complete-auth",
    response_model=AthenaResponse[KiteStatusDTO],
    summary="Exchange Kite request token and verify session",
    status_code=status.HTTP_200_OK,
    operation_id="completeKiteAuth",
)
def complete_kite_auth(
    body: KiteAuthCompleteRequestDTO,
    request: Request,
    service: KiteSessionService = Depends(get_kite_session_service),  # noqa: B008
    principal: AuthenticatedPrincipal = Depends(RequirePermission(Permission.ADMIN)),  # noqa: B008
) -> AthenaResponse[KiteStatusDTO]:
    """Persist and verify the daily market-data token; never places orders."""
    return AthenaResponse(
        status="success",
        data=_kite_status_dto(service.complete_auth(body.redirect_or_token)),
        meta=_meta(request),
    )


@router.post(
    "/kite/disconnect",
    response_model=AthenaResponse[KiteStatusDTO],
    summary="Clear the daily Kite access token and require reconnect",
    status_code=status.HTTP_200_OK,
    operation_id="disconnectKite",
)
def disconnect_kite(
    request: Request,
    service: KiteSessionService = Depends(get_kite_session_service),  # noqa: B008
    principal: AuthenticatedPrincipal = Depends(RequirePermission(Permission.ADMIN)),  # noqa: B008
) -> AthenaResponse[KiteStatusDTO]:
    """Drop the stored access token so the dashboard gate requires a fresh login."""
    return AthenaResponse(
        status="success",
        data=_kite_status_dto(service.disconnect()),
        meta=_meta(request),
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
