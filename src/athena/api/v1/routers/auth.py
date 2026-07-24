"""Authentication HTTP surface (Live Entry M-E1).

Wires existing ``AuthService`` to login / refresh / logout / me.
"""

from __future__ import annotations

from datetime import datetime, timezone

from fastapi import APIRouter, Depends, Request, status

from athena.api.config import APISettings
from athena.api.security import Permission, RequirePermission
from athena.api.security.exceptions import InvalidCredentialsError
from athena.api.security.login_limiter import LoginAttemptLimiter
from athena.api.security.models import AuthenticatedPrincipal
from athena.api.security.owner_seed import auth_required, owner_credentials_configured
from athena.api.security.service import AuthService
from athena.api.v1.dtos import AthenaResponse, ResponseMeta
from athena.api.v1.dtos.auth import (
    AuthStatusDTO,
    LoginRequest,
    PrincipalDTO,
    RefreshRequest,
    TokenPairDTO,
)

router = APIRouter(prefix="/auth", tags=["Auth"])


def _meta(request: Request) -> ResponseMeta:
    request_id = getattr(request.state, "request_id", "unknown")
    return ResponseMeta(
        request_id=request_id,
        api_version="v1",
        as_of=datetime.now(tz=timezone.utc),
    )


def _client_ip(request: Request) -> str:
    if request.client and request.client.host:
        return request.client.host
    return "unknown"


def get_auth_service(request: Request) -> AuthService:
    return request.app.state.auth_service


def get_api_settings(request: Request) -> APISettings:
    return request.app.state.api_settings


def get_login_limiter(request: Request) -> LoginAttemptLimiter:
    return request.app.state.login_limiter


@router.get(
    "/status",
    response_model=AthenaResponse[AuthStatusDTO],
    summary="Public auth mode for unlock gate",
    status_code=status.HTTP_200_OK,
    operation_id="getAuthStatus",
)
def get_auth_status(request: Request) -> AthenaResponse[AuthStatusDTO]:
    """Return whether the workstation requires unlock before API use."""
    return AthenaResponse(
        status="success",
        data=AuthStatusDTO(
            auth_required=auth_required(),
            owner_configured=owner_credentials_configured(),
        ),
        meta=_meta(request),
    )


@router.post(
    "/login",
    response_model=AthenaResponse[TokenPairDTO],
    summary="Unlock with owner credentials",
    status_code=status.HTTP_200_OK,
    operation_id="login",
)
def login(
    body: LoginRequest,
    request: Request,
    auth: AuthService = Depends(get_auth_service),  # noqa: B008
    settings: APISettings = Depends(get_api_settings),  # noqa: B008
    limiter: LoginAttemptLimiter = Depends(get_login_limiter),  # noqa: B008
) -> AthenaResponse[TokenPairDTO]:
    """Authenticate owner and issue access + refresh JWTs."""
    request_id = getattr(request.state, "request_id", "unknown")
    ip_address = _client_ip(request)
    limiter.check(username=body.username, ip_address=ip_address)
    try:
        access_token, refresh_token = auth.login(
            username=body.username,
            password=body.password,
            request_id=request_id,
            ip_address=ip_address,
        )
    except InvalidCredentialsError:
        limiter.record_failure(username=body.username, ip_address=ip_address)
        raise
    limiter.record_success(username=body.username, ip_address=ip_address)
    return AthenaResponse(
        status="success",
        data=TokenPairDTO(
            access_token=access_token,
            refresh_token=refresh_token,
            expires_in_seconds=settings.security.access_token_expiry_minutes * 60,
        ),
        meta=_meta(request),
    )


@router.post(
    "/refresh",
    response_model=AthenaResponse[TokenPairDTO],
    summary="Rotate refresh token and issue new access token",
    status_code=status.HTTP_200_OK,
    operation_id="refreshSession",
)
def refresh_session(
    body: RefreshRequest,
    request: Request,
    auth: AuthService = Depends(get_auth_service),  # noqa: B008
    settings: APISettings = Depends(get_api_settings),  # noqa: B008
) -> AthenaResponse[TokenPairDTO]:
    """Rotate refresh token; revoke the previous session."""
    request_id = getattr(request.state, "request_id", "unknown")
    access_token, refresh_token = auth.refresh(
        refresh_token=body.refresh_token,
        request_id=request_id,
        ip_address=_client_ip(request),
    )
    return AthenaResponse(
        status="success",
        data=TokenPairDTO(
            access_token=access_token,
            refresh_token=refresh_token,
            expires_in_seconds=settings.security.access_token_expiry_minutes * 60,
        ),
        meta=_meta(request),
    )


@router.post(
    "/logout",
    response_model=AthenaResponse[dict],
    summary="Revoke current session",
    status_code=status.HTTP_200_OK,
    operation_id="logout",
)
def logout(
    request: Request,
    auth: AuthService = Depends(get_auth_service),  # noqa: B008
    principal: AuthenticatedPrincipal = Depends(RequirePermission(Permission.READ)),  # noqa: B008
) -> AthenaResponse[dict]:
    """Revoke the session bound to the current access token."""
    request_id = getattr(request.state, "request_id", "unknown")
    if principal.session_id:
        auth.logout(
            session_id=principal.session_id,
            request_id=request_id,
            ip_address=_client_ip(request),
        )
    return AthenaResponse(
        status="success",
        data={"logged_out": True},
        meta=_meta(request),
    )


@router.get(
    "/me",
    response_model=AthenaResponse[PrincipalDTO],
    summary="Current authenticated principal",
    status_code=status.HTTP_200_OK,
    operation_id="getMe",
)
def get_me(
    request: Request,
    principal: AuthenticatedPrincipal = Depends(RequirePermission(Permission.READ)),  # noqa: B008
) -> AthenaResponse[PrincipalDTO]:
    """Return the unlocked owner/operator identity."""
    return AthenaResponse(
        status="success",
        data=PrincipalDTO(
            user_id=principal.user_id,
            username=principal.username,
            role=principal.role.value,
            permissions=tuple(p.value for p in principal.permissions),
        ),
        meta=_meta(request),
    )
