"""Standard API Response Headers Constants and Helpers (P8.5)."""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from fastapi import Response

# Standard Tracing & Metadata Headers
REQUEST_ID_HEADER = "X-Request-ID"
CORRELATION_ID_HEADER = "X-Correlation-ID"
API_VERSION_HEADER = "X-API-Version"

# Version Compatibility and Deprecation Headers
DEPRECATION_HEADER = "Deprecation"
SUNSET_HEADER = "Sunset"


def inject_platform_headers(
    response: Response,
    request_id: str,
    correlation_id: str,
    api_version: str = "v1",
    deprecation: str | None = None,
    sunset: str | None = None,
) -> None:
    """Inject standard platform tracing and metadata headers into an outgoing response."""
    response.headers[REQUEST_ID_HEADER] = request_id
    response.headers[CORRELATION_ID_HEADER] = correlation_id
    response.headers[API_VERSION_HEADER] = api_version

    if deprecation is not None:
        response.headers[DEPRECATION_HEADER] = deprecation
    if sunset is not None:
        response.headers[SUNSET_HEADER] = sunset
