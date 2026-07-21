"""Security exception hierarchy (P8.2).

Defines typed exceptions for authentication, authorization, session, and API key
failures, ensuring clean mapping to RFC 9457 Problem Details.
"""

from __future__ import annotations

from athena.errors import AthenaError


class SecurityError(AthenaError):
    """Base exception for all security failures."""


class AuthenticationError(SecurityError):
    """Base exception for authentication failures (HTTP 401)."""


class InvalidCredentialsError(AuthenticationError):
    """Invalid username or password."""


class InvalidTokenError(AuthenticationError):
    """Token is malformed, missing, or has invalid signature."""


class ExpiredTokenError(AuthenticationError):
    """Token expiration window has elapsed."""


class InvalidAPIKeyError(AuthenticationError):
    """API Key is invalid, inactive, or expired."""


class SessionRevokedError(AuthenticationError):
    """Associated session was explicitly logged out or invalidated."""


class PermissionDeniedError(SecurityError):
    """Subject lacks required permission for resource (HTTP 403)."""
