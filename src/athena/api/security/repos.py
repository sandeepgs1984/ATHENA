"""Security repository layer (P8.2).

SessionStore: Tracks refresh sessions (revocation status).
UserRepository: User store seeded with default accounts.
APIKeyRepository: Stores hashed key metadata.
"""

from __future__ import annotations

from typing import Protocol

from athena.api.security.exceptions import SessionRevokedError
from athena.api.security.models import APIKeyMetadata, Session, User


class SessionStore(Protocol):
    """Abstract interface to manage active refresh sessions."""

    def save(self, session: Session) -> None:
        ...

    def find(self, session_id: str) -> Session | None:
        ...

    def revoke(self, session_id: str) -> None:
        ...


class InMemorySessionStore:
    """Default SessionStore implementation storing sessions in-memory.

    Provides a clean migration path to Redis/database storage in the future.
    """

    def __init__(self) -> None:
        self._sessions: dict[str, Session] = {}

    def save(self, session: Session) -> None:
        self._sessions[session.session_id] = session

    def find(self, session_id: str) -> Session | None:
        session = self._sessions.get(session_id)
        if session and session.is_revoked:
            raise SessionRevokedError("Session has been explicitly revoked")
        return session

    def revoke(self, session_id: str) -> None:
        session = self._sessions.get(session_id)
        if session:
            # Functional updates: replace session with a revoked version
            self._sessions[session_id] = Session(
                session_id=session.session_id,
                user_id=session.user_id,
                refresh_token_hash=session.refresh_token_hash,
                created_at=session.created_at,
                expires_at=session.expires_at,
                is_revoked=True,
            )


class UserRepository:
    """In-memory User Repository.

    Allows lookup by ID and username. Seeded with default roles for RBAC.
    """

    def __init__(self) -> None:
        self._users: dict[str, User] = {}
        self._by_username: dict[str, User] = {}

    def save(self, user: User) -> None:
        self._users[user.user_id] = user
        self._by_username[user.username.lower()] = user

    def find_by_id(self, user_id: str) -> User | None:
        return self._users.get(user_id)

    def find_by_username(self, username: str) -> User | None:
        return self._by_username.get(username.lower())


class APIKeyRepository:
    """In-memory APIKey Repository.

    Stores ONLY APIKeyMetadata (raw secrets are never saved).
    """

    def __init__(self) -> None:
        self._keys: dict[str, APIKeyMetadata] = {}

    def save(self, metadata: APIKeyMetadata) -> None:
        self._keys[metadata.key_id] = metadata

    def find_by_id(self, key_id: str) -> APIKeyMetadata | None:
        return self._keys.get(key_id)

    def revoke(self, key_id: str) -> None:
        metadata = self._keys.get(key_id)
        if metadata:
            self._keys[key_id] = APIKeyMetadata(
                key_id=metadata.key_id,
                owner_id=metadata.owner_id,
                key_hash=metadata.key_hash,
                name=metadata.name,
                created_at=metadata.created_at,
                expires_at=metadata.expires_at,
                is_active=False,
                permissions=metadata.permissions,
            )
