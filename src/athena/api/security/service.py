"""Security services coordinating authentication operations (P8.2).

AuthService: Manages password login, JWT generation, token refresh, and logout.
APIKeyService: Manages key creation (generating raw secrets and saving hashes).
"""

from __future__ import annotations

import hashlib
import secrets
import uuid
from datetime import datetime, timezone

from athena.api.security.audit import AuditSink, SecurityEvent
from athena.api.security.exceptions import (
    ExpiredTokenError,
    InvalidCredentialsError,
    InvalidTokenError,
    SessionRevokedError,
)
from athena.api.security.hashing import PasswordHasher
from athena.api.security.models import (
    ROLE_PERMISSIONS,
    APIKeyMetadata,
    APIKeySecret,
    AuthenticatedPrincipal,
    Permission,
    Session,
)
from athena.api.security.repos import (
    APIKeyRepository,
    SessionStore,
    UserRepository,
)
from athena.api.security.token import TokenClaimsFactory, TokenSigner


class AuthService:
    """Coordinates user authentication, token generation, refresh, and logout."""

    def __init__(
        self,
        user_repo: UserRepository,
        session_store: SessionStore,
        hasher: PasswordHasher,
        signer: TokenSigner,
        claims_factory: TokenClaimsFactory,
        audit_sink: AuditSink,
    ) -> None:
        self._user_repo = user_repo
        self._session_store = session_store
        self._hasher = hasher
        self._signer = signer
        self._claims_factory = claims_factory
        self._audit = audit_sink

    def login(
        self,
        username: str,
        password: str,
        request_id: str,
        ip_address: str,
    ) -> tuple[str, str]:
        """Authenticate user and establish a new session.

        Returns (access_token, refresh_token).
        """
        user = self._user_repo.find_by_username(username)
        if not user or not user.is_active:
            self._audit_record(
                request_id, ip_address, "LOGIN_FAILURE", username, "User not found or inactive"
            )
            raise InvalidCredentialsError("Invalid username or password")

        if not self._hasher.verify(password, user.password_hash):
            self._audit_record(
                request_id, ip_address, "LOGIN_FAILURE", username, "Invalid password"
            )
            raise InvalidCredentialsError("Invalid username or password")

        # Create session
        session_id = f"sess-{uuid.uuid4()}"
        now = datetime.now(tz=timezone.utc)

        # Generate refresh token claims & token
        principal = AuthenticatedPrincipal(
            user_id=user.user_id,
            username=user.username,
            role=user.role,
            permissions=tuple(ROLE_PERMISSIONS.get(user.role, set())),
            session_id=session_id,
        )

        refresh_claims = self._claims_factory.create_claims(
            principal, "refresh", session_id, now
        )
        refresh_token = self._signer.encode(refresh_claims.to_dict())

        # Hash refresh token for storage
        refresh_hash = hashlib.sha256(refresh_token.encode("utf-8")).hexdigest()

        session = Session(
            session_id=session_id,
            user_id=user.user_id,
            refresh_token_hash=refresh_hash,
            created_at=now,
            expires_at=datetime.fromtimestamp(refresh_claims.exp, tz=timezone.utc),
        )
        self._session_store.save(session)

        # Generate access token
        access_claims = self._claims_factory.create_claims(
            principal, "access", session_id, now
        )
        access_token = self._signer.encode(access_claims.to_dict())

        self._audit_record(
            request_id, ip_address, "LOGIN_SUCCESS", username, f"Session {session_id} established"
        )
        return access_token, refresh_token

    def refresh(
        self,
        refresh_token: str,
        request_id: str,
        ip_address: str,
    ) -> tuple[str, str]:
        """Verify refresh token, revoke old session, and establish a new session."""
        try:
            raw_claims = self._signer.decode(refresh_token)
            claims = self._claims_factory.parse_claims(raw_claims)
        except ExpiredTokenError as exc:
            self._audit_record(
                request_id, ip_address, "TOKEN_REFRESH_FAILURE", None, "Expired refresh token"
            )
            raise exc
        except InvalidTokenError as exc:
            self._audit_record(
                request_id, ip_address, "TOKEN_REFRESH_FAILURE", None, f"Invalid token: {exc}"
            )
            raise exc

        if claims.token_type != "refresh":
            raise InvalidTokenError("Refresh token required")

        # Lookup and verify parent session (checks revocation status)
        session = self._session_store.find(claims.session_id)
        if not session:
            raise InvalidTokenError("Session not found")

        # Verify hash match to prevent token replay/reuse from different clients
        incoming_hash = hashlib.sha256(refresh_token.encode("utf-8")).hexdigest()
        if not secrets.compare_digest(incoming_hash, session.refresh_token_hash):
            # Token reuse detected! Revoke the parent session immediately as precaution
            self._session_store.revoke(session.session_id)
            self._audit_record(
                request_id,
                ip_address,
                "TOKEN_REUSE_DETECTED",
                claims.username,
                f"Session {session.session_id} revoked due to token reuse",
            )
            raise InvalidTokenError("Refresh token has been reused")

        # Revoke the parent session
        self._session_store.revoke(session.session_id)

        # Generate new session
        user = self._user_repo.find_by_id(claims.sub)
        if not user or not user.is_active:
            raise SessionRevokedError("User account is inactive")

        new_session_id = f"sess-{uuid.uuid4()}"
        now = datetime.now(tz=timezone.utc)

        principal = AuthenticatedPrincipal(
            user_id=user.user_id,
            username=user.username,
            role=user.role,
            permissions=tuple(ROLE_PERMISSIONS.get(user.role, set())),
            session_id=new_session_id,
        )

        new_refresh_claims = self._claims_factory.create_claims(
            principal, "refresh", new_session_id, now
        )
        new_refresh_token = self._signer.encode(new_refresh_claims.to_dict())
        new_refresh_hash = hashlib.sha256(new_refresh_token.encode("utf-8")).hexdigest()

        new_session = Session(
            session_id=new_session_id,
            user_id=user.user_id,
            refresh_token_hash=new_refresh_hash,
            created_at=now,
            expires_at=datetime.fromtimestamp(new_refresh_claims.exp, tz=timezone.utc),
        )
        self._session_store.save(new_session)

        new_access_claims = self._claims_factory.create_claims(
            principal, "access", new_session_id, now
        )
        new_access_token = self._signer.encode(new_access_claims.to_dict())

        self._audit_record(
            request_id,
            ip_address,
            "TOKEN_REFRESH_SUCCESS",
            user.username,
            f"Rotated session {session.session_id} -> {new_session_id}",
        )
        return new_access_token, new_refresh_token

    def logout(
        self,
        session_id: str,
        request_id: str,
        ip_address: str,
    ) -> None:
        """Revoke the current session."""
        self._session_store.revoke(session_id)
        self._audit_record(
            request_id, ip_address, "LOGOUT", None, f"Session {session_id} revoked"
        )

    def _audit_record(
        self,
        request_id: str,
        ip_address: str,
        event_type: str,
        username: str | None,
        detail: str,
    ) -> None:
        event = SecurityEvent(
            event_id=f"evt-{uuid.uuid4()}",
            ts=datetime.now(tz=timezone.utc),
            event_type=event_type,
            username=username,
            request_id=request_id,
            ip_address=ip_address,
            detail=detail,
        )
        self._audit.record(event)


class APIKeyService:
    """Coordinates API Key creation, metadata storage, and key revocation."""

    def __init__(self, key_repo: APIKeyRepository, audit_sink: AuditSink) -> None:
        self._key_repo = key_repo
        self._audit = audit_sink

    def create_key(
        self,
        owner_id: str,
        name: str,
        permissions: tuple[Permission, ...],
        expires_at: datetime | None,
        request_id: str,
        ip_address: str,
    ) -> APIKeySecret:
        """Create a new API Key.

        Stores only the SHA-256 hash of the key metadata, returning the raw secret once.
        """
        key_id = f"key-{secrets.token_hex(8)}"
        raw_secret = secrets.token_urlsafe(32)

        # Full API Key format delivered to user: key_id.raw_secret
        full_key = f"{key_id}.{raw_secret}"

        # Hash secret for persistence verification
        key_hash = hashlib.sha256(raw_secret.encode("utf-8")).hexdigest()

        metadata = APIKeyMetadata(
            key_id=key_id,
            owner_id=owner_id,
            key_hash=key_hash,
            name=name,
            created_at=datetime.now(tz=timezone.utc),
            expires_at=expires_at,
            permissions=permissions,
        )
        self._key_repo.save(metadata)

        event = SecurityEvent(
            event_id=f"evt-{uuid.uuid4()}",
            ts=datetime.now(tz=timezone.utc),
            event_type="API_KEY_CREATED",
            username=None,
            request_id=request_id,
            ip_address=ip_address,
            detail=f"Key {key_id} ('{name}') generated for user {owner_id}",
        )
        self._audit.record(event)

        return APIKeySecret(key_id=key_id, raw_key=full_key)
