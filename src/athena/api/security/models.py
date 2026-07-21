"""Security domain models (P8.2).

Immutable security objects representing roles, permissions, principals, claims,
and session metadata. All models are frozen with slots enabled.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum, unique


@unique
class Permission(str, Enum):
    """Fine-grained resource access permissions."""

    READ = "read"
    EXECUTE = "execute"
    CONFIGURE = "configure"
    ADMIN = "admin"


@unique
class Role(str, Enum):
    """Role-based access categories."""

    ADMIN = "ADMIN"
    OPERATOR = "OPERATOR"
    ANALYST = "ANALYST"
    READONLY = "READONLY"


# Hierarchical role to permissions mappings
ROLE_PERMISSIONS: dict[Role, set[Permission]] = {
    Role.ADMIN: {
        Permission.READ,
        Permission.EXECUTE,
        Permission.CONFIGURE,
        Permission.ADMIN,
    },
    Role.OPERATOR: {Permission.READ, Permission.EXECUTE},
    Role.ANALYST: {Permission.READ},
    Role.READONLY: {Permission.READ},
}


@dataclass(frozen=True, slots=True)
class User:
    """Persistence model representing a user account in the system."""

    user_id: str
    username: str
    password_hash: str
    role: Role
    is_active: bool = True


@dataclass(frozen=True, slots=True)
class AuthenticatedPrincipal:
    """Security context representing the currently authenticated identity.

    Exposed across the API layer; decoupled from the persistence User model.
    """

    user_id: str
    username: str
    role: Role
    permissions: tuple[Permission, ...]
    session_id: str | None = None  # None for API Key invocations


@dataclass(frozen=True, slots=True)
class TokenClaims:
    """Standardized JWT claims payload."""

    sub: str
    username: str
    role: str
    iat: int
    exp: int
    iss: str
    aud: str
    token_type: str  # "access" or "refresh"
    session_id: str

    def to_dict(self) -> dict[str, object]:
        return {
            "sub": self.sub,
            "username": self.username,
            "role": self.role,
            "iat": self.iat,
            "exp": self.exp,
            "iss": self.iss,
            "aud": self.aud,
            "token_type": self.token_type,
            "session_id": self.session_id,
        }


@dataclass(frozen=True, slots=True)
class Session:
    """Active session tracking for token refresh verification."""

    session_id: str
    user_id: str
    refresh_token_hash: str
    created_at: datetime
    expires_at: datetime
    is_revoked: bool = False


@dataclass(frozen=True, slots=True)
class APIKeyMetadata:
    """Stored API key details. Only the SHA-256 hash is persisted."""

    key_id: str
    owner_id: str
    key_hash: str
    name: str
    created_at: datetime
    expires_at: datetime | None
    is_active: bool = True
    permissions: tuple[Permission, ...] = field(default_factory=tuple)


@dataclass(frozen=True, slots=True)
class APIKeySecret:
    """One-time payload returned to clients upon creation. Never persisted."""

    key_id: str
    raw_key: str
