"""API configuration models (P8.1).

Separates transport/deployment settings from application identity metadata.
Each model grows independently; no monolithic settings object.
"""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field


class TransportConfig(BaseModel):
    """Deployment and transport layer settings.

    Governs how the API server binds and communicates.
    Secure defaults: CORS disabled until explicitly configured.
    """

    model_config = ConfigDict(frozen=True)

    host: str = "0.0.0.0"
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


class APISettings(BaseModel):
    """Composed top-level settings.

    Constructed from defaults or explicit overrides. Each sub-config evolves
    independently: transport settings are infrastructure concerns, app metadata
    are application identity concerns.
    """

    model_config = ConfigDict(frozen=True)

    transport: TransportConfig = TransportConfig()
    app: AppMetadataConfig = AppMetadataConfig()
