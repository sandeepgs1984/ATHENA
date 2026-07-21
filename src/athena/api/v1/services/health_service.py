"""Health service (P8.1)."""

from __future__ import annotations

from athena.api.v1.dtos.common import HealthResponse
from athena.api.v1.providers.base import HealthProvider


class HealthService:
    """Coordinates health information retrieval.

    Contains zero HTTP knowledge. Depends only on the HealthProvider protocol.
    """

    def __init__(self, provider: HealthProvider) -> None:
        self._provider = provider

    def get_health(self) -> HealthResponse:
        """Retrieve current platform health status."""
        return self._provider.get_health()
