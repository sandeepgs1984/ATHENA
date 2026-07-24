"""Auth request/response DTOs (Live Entry M-E1)."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field


class LoginRequest(BaseModel):
    """Owner unlock credentials."""

    model_config = ConfigDict(frozen=True)

    username: str = Field(min_length=1, max_length=128)
    password: str = Field(min_length=1, max_length=256)


class RefreshRequest(BaseModel):
    """Refresh-token rotation request."""

    model_config = ConfigDict(frozen=True)

    refresh_token: str = Field(min_length=1)


class TokenPairDTO(BaseModel):
    """Issued JWT pair after login or refresh."""

    model_config = ConfigDict(frozen=True)

    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    expires_in_seconds: int


class AuthStatusDTO(BaseModel):
    """Public auth mode for the unlock gate."""

    model_config = ConfigDict(frozen=True)

    auth_required: bool
    owner_configured: bool


class PrincipalDTO(BaseModel):
    """Authenticated principal summary for ``/auth/me``."""

    model_config = ConfigDict(frozen=True)

    user_id: str
    username: str
    role: str
    permissions: tuple[str, ...]
