"""API Security dependencies (P8.2).

Provides get_current_user and RequirePermission dependencies for route controllers.
Integrates with OpenAPI security schemes (HTTPBearer and APIKeyHeader) out of the box.
"""

from __future__ import annotations

from fastapi import Depends, Request
from fastapi.security import APIKeyHeader, HTTPAuthorizationCredentials, HTTPBearer

from athena.api.security.exceptions import (
    AuthenticationError,
    PermissionDeniedError,
)
from athena.api.security.models import (
    AuthenticatedPrincipal,
    Permission,
)
from athena.api.security.providers import (
    AuthenticationProvider,
    AuthorizationProvider,
    RoleBasedAuthorizationProvider,
    TokenAndAPIKeyAuthenticationProvider,
)
from athena.api.security.repos import (
    APIKeyRepository,
    InMemorySessionStore,
    SessionStore,
    UserRepository,
)
from athena.api.security.token import TokenClaimsFactory, TokenSigner

# Declare OpenAPI security schemes
_bearer_scheme = HTTPBearer(auto_error=False)
_api_key_scheme = APIKeyHeader(name="X-API-Key", auto_error=False)

# Module-level singletons for default implementations
_user_repo = UserRepository()
_session_store = InMemorySessionStore()
_api_key_repo = APIKeyRepository()
_auth_provider: AuthenticationProvider | None = None
_auth_z_provider = RoleBasedAuthorizationProvider()


def get_user_repository() -> UserRepository:
    return _user_repo


def get_session_store() -> SessionStore:
    return _session_store


def get_api_key_repository() -> APIKeyRepository:
    return _api_key_repo


def get_authorization_provider() -> AuthorizationProvider:
    return _auth_z_provider


def get_authentication_provider(request: Request) -> AuthenticationProvider:
    """Dependency injection provider for AuthenticationProvider."""
    global _auth_provider
    if _auth_provider is None:
        # Resolve dependencies from request.app.state where create_app puts them
        token_signer: TokenSigner = request.app.state.token_signer
        claims_factory: TokenClaimsFactory = request.app.state.claims_factory
        _auth_provider = TokenAndAPIKeyAuthenticationProvider(
            user_repo=_user_repo,
            session_store=_session_store,
            api_key_repo=_api_key_repo,
            token_signer=token_signer,
            claims_factory=claims_factory,
        )
    return _auth_provider


def get_current_user(
    request: Request,
    bearer_creds: HTTPAuthorizationCredentials | None = Depends(_bearer_scheme),  # noqa: B008
    api_key: str | None = Depends(_api_key_scheme),
    auth_provider: AuthenticationProvider = Depends(get_authentication_provider),  # noqa: B008
) -> AuthenticatedPrincipal:
    """Extract credentials and authenticate principal.

    Resolves Bearer Token (JWT) or X-API-Key from incoming headers.
    """
    if bearer_creds:
        return auth_provider.authenticate_token(bearer_creds.credentials)
    if api_key:
        return auth_provider.authenticate_api_key(api_key)

    import os
    if os.environ.get("ATHENA_SINGLE_USER", "false").lower() == "true":
        from athena.api.security.models import AuthenticatedPrincipal, Role
        return AuthenticatedPrincipal(
            principal_id="usr-admin",
            username="admin",
            role=Role.ADMIN,
            meta={},
        )

    raise AuthenticationError("Authentication credentials missing or invalid")


class RequirePermission:
    """FastAPI Dependency Guard enforcing specific resource permissions."""

    def __init__(self, permission: Permission) -> None:
        self._permission = permission

    def __call__(
        self,
        principal: AuthenticatedPrincipal = Depends(get_current_user),  # noqa: B008
        auth_z: AuthorizationProvider = Depends(get_authorization_provider),  # noqa: B008
    ) -> AuthenticatedPrincipal:
        if not auth_z.has_permission(principal, self._permission):
            raise PermissionDeniedError(
                f"Lacks required permission '{self._permission.value}'"
            )
        return principal
