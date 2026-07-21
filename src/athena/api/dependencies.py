"""Dependency injection factories (P8.1).

FastAPI dependency providers to inject services into controllers.
Allows clean mocking of services and providers in unit tests.
"""

from __future__ import annotations

from fastapi import Request

from athena.api.v1.providers.base import HealthProvider, MetricsProvider
from athena.api.v1.providers.observability import (
    ObservabilityHealthProvider,
    ObservabilityMetricsProvider,
)
from athena.api.v1.services.health_service import HealthService
from athena.api.v1.services.metrics_service import MetricsService

# Singletons for default providers
_health_provider = ObservabilityHealthProvider()
_metrics_provider = ObservabilityMetricsProvider()


def get_health_provider() -> HealthProvider:
    """Dependency provider for HealthProvider."""
    return _health_provider


def get_metrics_provider() -> MetricsProvider:
    """Dependency provider for MetricsProvider."""
    return _metrics_provider


def get_health_service(
    request: Request,
) -> HealthService:
    """Dependency provider for HealthService.

    Injects the active HealthProvider.
    """
    # Fetch provider from app state or fall back to default
    provider = getattr(
        request.app.state, "health_provider", _health_provider
    )
    return HealthService(provider)


def get_metrics_service(
    request: Request,
) -> MetricsService:
    """Dependency provider for MetricsService.

    Injects the active MetricsProvider.
    """
    # Fetch provider from app state or fall back to default
    provider = getattr(
        request.app.state, "metrics_provider", _metrics_provider
    )
    return MetricsService(provider)
