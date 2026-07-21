"""Provider protocol interfaces for health and metrics (P8.1).

Services depend only on these protocols, not on concrete implementations.
This allows future integration with Prometheus, OpenTelemetry, or cloud
monitoring without modifying controllers, services, or tests.
"""

from __future__ import annotations

from typing import Protocol, runtime_checkable

from athena.api.v1.dtos.common import HealthResponse, MetricsResponse


@runtime_checkable
class HealthProvider(Protocol):
    """Abstract health information provider.

    Default implementation: ObservabilityHealthProvider.
    Future: PrometheusHealthProvider, OpenTelemetryHealthProvider, etc.
    """

    def get_health(self) -> HealthResponse:
        ...


@runtime_checkable
class MetricsProvider(Protocol):
    """Abstract metrics information provider.

    Default implementation returns scaffold values (P8.1 scope).
    Future: aggregated from PipelineHistory, ScheduleHistory, observability platform.
    """

    def get_metrics(self) -> MetricsResponse:
        ...
