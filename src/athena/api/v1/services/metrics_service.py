"""Metrics service (P8.1)."""

from __future__ import annotations

from athena.api.v1.dtos.common import MetricsResponse
from athena.api.v1.providers.base import MetricsProvider


class MetricsService:
    """Coordinates metrics retrieval.

    Contains zero HTTP knowledge. Depends only on the MetricsProvider protocol.
    """

    def __init__(self, provider: MetricsProvider) -> None:
        self._provider = provider

    def get_metrics(self) -> MetricsResponse:
        """Retrieve current platform metrics."""
        return self._provider.get_metrics()
