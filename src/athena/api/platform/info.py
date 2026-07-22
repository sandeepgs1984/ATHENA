"""Consolidated application information router (P8.5)."""

from __future__ import annotations

from fastapi import APIRouter, Depends, Request
from pydantic import BaseModel, ConfigDict

from athena.api.dependencies import get_build_info_provider, get_metadata_provider
from athena.api.platform.providers.build_info_provider import BuildInfoDTO, BuildInfoProvider
from athena.api.platform.providers.metadata_provider import (
    CapabilityMetadataDTO,
    FeaturesDTO,
    MetadataProvider,
    PlatformMetadataDTO,
)

router = APIRouter(tags=["Platform Discovery"])


class PlatformInfoDTO(BaseModel):
    """Consolidated application startup and capabilities report."""

    model_config = ConfigDict(frozen=True)

    app_name: str
    environment: str
    api_version: str
    build: BuildInfoDTO
    meta: PlatformMetadataDTO
    features: FeaturesDTO
    capabilities: list[CapabilityMetadataDTO]


@router.get(
    "/info",
    response_model=PlatformInfoDTO,
    summary="Get consolidated platform information",
    response_description=(
        "Returns complete build, metadata, feature flags, "
        "and capabilities state for startup initialization"
    ),
    operation_id="getPlatformInfo",
)
def get_info(
    request: Request,
    build_p: BuildInfoProvider = Depends(get_build_info_provider),  # noqa: B008
    meta_p: MetadataProvider = Depends(get_metadata_provider),  # noqa: B008
) -> PlatformInfoDTO:
    """Retrieve combined report of versioning, modules, feature configurations, and capabilities."""
    b = build_p.get_build_info()
    m = meta_p.get_metadata()
    f = meta_p.get_features()
    c = meta_p.get_capabilities()

    return PlatformInfoDTO(
        app_name=b.app_name,
        environment=b.environment,
        api_version=b.api_version,
        build=b,
        meta=m,
        features=f,
        capabilities=c,
    )
