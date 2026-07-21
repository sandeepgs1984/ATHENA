"""JWT Token signing, verification, and claims factory (P8.2).

TokenSigner: Decouples signature generation from specific algorithms (e.g., HS256, RS256).
TokenClaimsFactory: Handles claims assembly and expiry computation.
"""

from __future__ import annotations

from datetime import datetime, timedelta
from typing import Any, Protocol

import jwt

from athena.api.config import SecurityConfig
from athena.api.security.exceptions import ExpiredTokenError, InvalidTokenError
from athena.api.security.models import AuthenticatedPrincipal, TokenClaims


class TokenSigner(Protocol):
    """Protocol for cryptographic token encoding and decoding."""

    def encode(self, claims: dict[str, Any]) -> str:
        """Create a signed JWT token string from claims."""
        ...

    def decode(self, token: str) -> dict[str, Any]:
        """Decode and verify signature of the JWT token string."""
        ...


class HMAC256TokenSigner:
    """Default TokenSigner using symmetric HMAC-SHA256 (HS256)."""

    def __init__(
        self,
        secret_key: str,
        issuer: str,
        audience: str,
        algorithm: str = "HS256",
    ) -> None:
        self._secret = secret_key
        self._issuer = issuer
        self._audience = audience
        self._algorithm = algorithm

    def encode(self, claims: dict[str, Any]) -> str:
        return jwt.encode(claims, self._secret, algorithm=self._algorithm)

    def decode(self, token: str) -> dict[str, Any]:
        try:
            return jwt.decode(
                token,
                self._secret,
                algorithms=[self._algorithm],
                audience=self._audience,
                issuer=self._issuer,
            )
        except jwt.ExpiredSignatureError as exc:
            raise ExpiredTokenError("Token signature has expired") from exc
        except jwt.PyJWTError as exc:
            raise InvalidTokenError(f"Invalid token signature: {exc}") from exc


class TokenClaimsFactory:
    """Assembles and validates claims for JWT access and refresh tokens."""

    def __init__(self, config: SecurityConfig) -> None:
        self._config = config

    def create_claims(
        self,
        principal: AuthenticatedPrincipal,
        token_type: str,
        session_id: str,
        now: datetime,
    ) -> TokenClaims:
        """Assemble TokenClaims model for a principal."""
        if token_type == "access":
            expiry_delta = timedelta(
                minutes=self._config.access_token_expiry_minutes
            )
        else:
            expiry_delta = timedelta(
                days=self._config.refresh_token_expiry_days
            )

        iat = int(now.timestamp())
        exp = int((now + expiry_delta).timestamp())

        return TokenClaims(
            sub=principal.user_id,
            username=principal.username,
            role=principal.role.value,
            iat=iat,
            exp=exp,
            iss=self._config.jwt_issuer,
            aud=self._config.jwt_audience,
            token_type=token_type,
            session_id=session_id,
        )

    def parse_claims(self, claims_dict: dict[str, Any]) -> TokenClaims:
        """Parse raw dictionary into TokenClaims model."""
        try:
            return TokenClaims(
                sub=claims_dict["sub"],
                username=claims_dict["username"],
                role=claims_dict["role"],
                iat=claims_dict["iat"],
                exp=claims_dict["exp"],
                iss=claims_dict["iss"],
                aud=claims_dict["aud"],
                token_type=claims_dict["token_type"],
                session_id=claims_dict["session_id"],
            )
        except KeyError as exc:
            raise InvalidTokenError(
                f"Missing required claim: {exc}"
            ) from exc
