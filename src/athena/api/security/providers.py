"""Authentication and Authorization Provider interfaces and implementations (P8.2)."""

from __future__ import annotations

import hashlib
import hmac
from datetime import datetime, timezone
from typing import Protocol

from athena.api.security.exceptions import (
    InvalidAPIKeyError,
    InvalidTokenError,
)
from athena.api.security.models import (
    ROLE_PERMISSIONS,
    AuthenticatedPrincipal,
    Permission,
    Role,
)
from athena.api.security.repos import (
    APIKeyRepository,
    SessionStore,
    UserRepository,
)
from athena.api.security.token import TokenClaimsFactory, TokenSigner


class AuthenticationProvider(Protocol):
    """Protocol for credential authentication (token or API key)."""

    def authenticate_token(self, token: str) -> AuthenticatedPrincipal:
        """Authenticate a signed JWT access token."""
        ...

    def authenticate_api_key(self, api_key: str) -> AuthenticatedPrincipal:
        """Authenticate a programmatic API key."""
        ...


class TokenAndAPIKeyAuthenticationProvider:
    """Default AuthenticationProvider implementation.

    Verifies JWT access tokens or hashed API keys, constructing an
    AuthenticatedPrincipal context upon success.
    """

    def __init__(
        self,
        user_repo: UserRepository,
        session_store: SessionStore,
        api_key_repo: APIKeyRepository,
        token_signer: TokenSigner,
        claims_factory: TokenClaimsFactory,
    ) -> None:
        self._user_repo = user_repo
        self._session_store = session_store
        self._api_key_repo = api_key_repo
        self._signer = token_signer
        self._claims_factory = claims_factory

    def authenticate_token(self, token: str) -> AuthenticatedPrincipal:
        # Decode and verify token signature/expiry via signer
        raw_claims = self._signer.decode(token)
        claims = self._claims_factory.parse_claims(raw_claims)

        # Enforce that only access tokens can be used for endpoint access
        if claims.token_type != "access":
            raise InvalidTokenError("Access token required for API access")

        # Verify session has not been revoked (checking refresh session parent state)
        session = self._session_store.find(claims.session_id)
        if session is None:
            raise InvalidTokenError("Session not found")

        # Fetch user
        user = self._user_repo.find_by_id(claims.sub)
        if not user or not user.is_active:
            raise InvalidTokenError("Authenticated user is inactive or removed")

        role = Role(claims.role)
        permissions = ROLE_PERMISSIONS.get(role, set())

        return AuthenticatedPrincipal(
            user_id=claims.sub,
            username=claims.username,
            role=role,
            permissions=tuple(permissions),
            session_id=claims.session_id,
        )

    def authenticate_api_key(self, api_key: str) -> AuthenticatedPrincipal:
        # Expected format: key_id.raw_secret
        if "." not in api_key:
            raise InvalidAPIKeyError("Invalid API key format")

        key_id, raw_secret = api_key.split(".", 1)

        # Lookup key metadata
        metadata = self._api_key_repo.find_by_id(key_id)
        if not metadata or not metadata.is_active:
            raise InvalidAPIKeyError("API key is inactive or not found")

        # Verify key has not expired
        if (
            metadata.expires_at
            and datetime.now(tz=timezone.utc) > metadata.expires_at
        ):
            raise InvalidAPIKeyError("API key has expired")

        # Constant-time comparison of hashed secret
        incoming_hash = hashlib.sha256(raw_secret.encode("utf-8")).hexdigest()
        if not hmac.compare_digest(incoming_hash, metadata.key_hash):
            raise InvalidAPIKeyError("Invalid API key secret")

        # Fetch user who owns this key
        user = self._user_repo.find_by_id(metadata.owner_id)
        if not user or not user.is_active:
            raise InvalidAPIKeyError("Owner account is inactive or removed")

        # Use either key-specific overrides or standard user role permissions
        permissions = (
            metadata.permissions
            if metadata.permissions
            else tuple(ROLE_PERMISSIONS.get(user.role, set()))
        )

        return AuthenticatedPrincipal(
            user_id=user.user_id,
            username=user.username,
            role=user.role,
            permissions=permissions,
            session_id=None,  # No active JWT session
        )


class AuthorizationProvider(Protocol):
    """Protocol for checking user/principal resource permissions."""

    def has_permission(
        self, principal: AuthenticatedPrincipal, permission: Permission
    ) -> bool:
        ...


class RoleBasedAuthorizationProvider:
    """Default AuthorizationProvider resolving permissions via ROLE_PERMISSIONS."""

    def has_permission(
        self, principal: AuthenticatedPrincipal, permission: Permission
    ) -> bool:
        # Principal holds pre-evaluated permissions list resolved at authentication time
        return permission in principal.permissions
