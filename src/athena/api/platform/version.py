"""Application version and build information API router (P8.5)."""

from __future__ import annotations

from fastapi import APIRouter, Depends, Request

from athena.api.dependencies import get_build_info_provider
from athena.api.platform.providers.build_info_provider import BuildInfoDTO, BuildInfoProvider

router = APIRouter(tags=["Platform Discovery"])


@router.get(
    "/version",
    response_model=BuildInfoDTO,
    summary="Get application version information",
    response_description="Returns application version metadata and runtime engine statistics",
    operation_id="getVersion",
)
def get_version(
    request: Request,
    provider: BuildInfoProvider = Depends(get_build_info_provider),  # noqa: B008
) -> BuildInfoDTO:
    """Retrieve application identity, build numbers, compile timestamps, and python runtime environments."""
    return provider.get_build_info()
