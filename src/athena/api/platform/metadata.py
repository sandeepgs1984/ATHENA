"""Discovery metadata endpoints for features, capabilities, and registered resources (P8.5)."""

from __future__ import annotations

from fastapi import APIRouter, Depends, Request

from athena.api.dependencies import get_metadata_provider
from athena.api.platform.providers.metadata_provider import (
    CapabilityMetadataDTO,
    FeaturesDTO,
    MetadataProvider,
    PlatformMetadataDTO,
)

router = APIRouter(tags=["Platform Discovery"])


@router.get(
    "/meta",
    response_model=PlatformMetadataDTO,
    summary="Get platform metadata",
    response_description="Returns registered resources, active API modules, and compatibilities",
    operation_id="getMetadata",
)
def get_meta(
    request: Request,
    provider: MetadataProvider = Depends(get_metadata_provider),  # noqa: B008
) -> PlatformMetadataDTO:
    """Retrieve platform modules compatibility mapping and future AI block placeholders."""
    return provider.get_metadata()


@router.get(
    "/features",
    response_model=FeaturesDTO,
    summary="Get feature flags",
    response_description="Returns map of active feature flags configured in current profile",
    operation_id="getFeatures",
)
def get_features(
    request: Request,
    provider: MetadataProvider = Depends(get_metadata_provider),  # noqa: B008
) -> FeaturesDTO:
    """Retrieve active feature flags toggle map."""
    return provider.get_features()


@router.get(
    "/capabilities",
    response_model=list[CapabilityMetadataDTO],
    summary="Get capability registry",
    response_description="Returns detailed metadata for all registered system capabilities",
    operation_id="getCapabilities",
)
def get_capabilities(
    request: Request,
    provider: MetadataProvider = Depends(get_metadata_provider),  # noqa: B008
) -> list[CapabilityMetadataDTO]:
    """Retrieve structured capabilities matrix listing versions, categorías, and description contexts."""
    return provider.get_capabilities()
