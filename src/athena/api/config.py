"""API configuration models (P8.1).

Separates transport/deployment settings from application identity metadata.
Each model grows independently; no monolithic settings object.
"""

from __future__ import annotations

import hashlib
import os

from pydantic import BaseModel, ConfigDict, Field


class TransportConfig(BaseModel):
    """Deployment and transport layer settings.

    Governs how the API server binds and communicates.
    Secure defaults: CORS disabled until explicitly configured.
    """

    model_config = ConfigDict(frozen=True)

    host: str = "127.0.0.1"
    port: int = Field(default=8000, ge=1, le=65535)
    debug: bool = False
    cors_origins: list[str] = []              # Secure default: no origins allowed
    cors_allow_credentials: bool = False
    cors_allow_methods: list[str] = ["GET"]
    cors_allow_headers: list[str] = ["*"]


class AppMetadataConfig(BaseModel):
    """Application identity and OpenAPI documentation metadata.

    Governs how the application presents itself in documentation and headers.
    """

    model_config = ConfigDict(frozen=True)

    title: str = "ATHENA Platform API"
    description: str = "Production REST API for ATHENA Decision Intelligence Platform"
    version: str = "0.1.0"
    api_prefix: str = "/api"
    docs_url: str = "/api/docs"
    redoc_url: str = "/api/redoc"
    openapi_url: str = "/api/openapi.json"


class SecurityConfig(BaseModel):
    """Cryptographic and expiry configuration parameters."""

    model_config = ConfigDict(frozen=True)

    # ≥32 UTF-8 bytes required for HS256 (PyJWT); keep the label clearly non-production.
    jwt_secret: str = "secret-change-in-prod-seeding!!!"
    jwt_algorithm: str = "HS256"
    jwt_issuer: str = "athena-platform"
    jwt_audience: str = "athena-dashboard"
    access_token_expiry_minutes: int = 15
    refresh_token_expiry_days: int = 7
    bcrypt_rounds: int = 12
    login_max_failures: int = Field(default=5, ge=1, le=20)
    login_failure_window_minutes: int = Field(default=10, ge=1, le=1440)
    login_lockout_minutes: int = Field(default=15, ge=1, le=1440)


class APISettings(BaseModel):
    """Composed top-level settings.

    Constructed from defaults or explicit overrides. Each sub-config evolves
    independently: transport settings are infrastructure concerns, app metadata
    are application identity concerns, and security contains crypto secrets/expiry settings.
    """

    model_config = ConfigDict(frozen=True)

    transport: TransportConfig = TransportConfig()
    app: AppMetadataConfig = AppMetadataConfig()
    security: SecurityConfig = SecurityConfig()


def api_settings_from_env() -> APISettings:
    """Build production settings from `.env` without exposing secrets in config files.

    An explicit ``ATHENA_JWT_SECRET`` wins. For existing single-owner installs,
    a stable SHA-256 key is derived from the bcrypt owner hash so the known
    development JWT secret is never used once owner unlock is configured.
    """
    default = SecurityConfig()
    explicit_secret = (os.environ.get("ATHENA_JWT_SECRET") or "").strip()
    owner_hash = (os.environ.get("ATHENA_OWNER_PASSWORD_HASH") or "").strip()
    if explicit_secret:
        jwt_secret = explicit_secret
    elif owner_hash:
        jwt_secret = hashlib.sha256(
            f"athena-owner-jwt:{owner_hash}".encode()
        ).hexdigest()
    else:
        jwt_secret = default.jwt_secret

    security = SecurityConfig(
        jwt_secret=jwt_secret,
        login_max_failures=int(
            os.environ.get(
                "ATHENA_LOGIN_MAX_FAILURES", str(default.login_max_failures)
            )
        ),
        login_failure_window_minutes=int(
            os.environ.get(
                "ATHENA_LOGIN_FAILURE_WINDOW_MINUTES",
                str(default.login_failure_window_minutes),
            )
        ),
        login_lockout_minutes=int(
            os.environ.get(
                "ATHENA_LOGIN_LOCKOUT_MINUTES",
                str(default.login_lockout_minutes),
            )
        ),
    )
    return APISettings(security=security)
