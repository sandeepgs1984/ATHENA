"""Security architecture components (P8.2)."""

from __future__ import annotations

from athena.api.security.dependencies import (
    RequirePermission,
    get_current_user,
)
from athena.api.security.exceptions import (
    AuthenticationError,
    ExpiredTokenError,
    InvalidAPIKeyError,
    InvalidCredentialsError,
    InvalidTokenError,
    PermissionDeniedError,
    SecurityError,
    SessionRevokedError,
)
from athena.api.security.models import (
    APIKeyMetadata,
    APIKeySecret,
    AuthenticatedPrincipal,
    Permission,
    Role,
    TokenClaims,
)

__all__ = [
    "APIKeyMetadata",
    "APIKeySecret",
    "AuthenticatedPrincipal",
    "AuthenticationError",
    "ExpiredTokenError",
    "InvalidAPIKeyError",
    "InvalidCredentialsError",
    "InvalidTokenError",
    "Permission",
    "PermissionDeniedError",
    "RequirePermission",
    "Role",
    "SecurityError",
    "SessionRevokedError",
    "TokenClaims",
    "get_current_user",
]
