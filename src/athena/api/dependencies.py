"""Dependency injection factories (P8.1).

FastAPI dependency providers to inject services into controllers.
Allows clean mocking of services and providers in unit tests.
"""

from __future__ import annotations

from fastapi import Request

from athena.api.v1.providers.base import (
    DecisionProvider,
    HealthProvider,
    MetricsProvider,
    PipelineRunProvider,
    PortfolioProvider,
    SchedulerHistoryProvider,
    WorkspaceProvider,
)
from athena.api.v1.providers.in_memory import (
    InMemoryDecisionProvider,
    InMemoryPipelineRunProvider,
    InMemoryPortfolioProvider,
    InMemorySchedulerHistoryProvider,
    InMemoryWorkspaceProvider,
    seed_sample_data,
)
from athena.api.v1.providers.observability import (
    ObservabilityHealthProvider,
    ObservabilityMetricsProvider,
)
from athena.api.v1.services.decisions_service import DecisionsService
from athena.api.v1.services.health_service import HealthService
from athena.api.v1.services.metrics_service import MetricsService
from athena.api.v1.services.pipelines_service import PipelinesService
from athena.api.v1.services.portfolio_service import PortfolioService
from athena.api.v1.services.scheduler_service import SchedulerService
from athena.api.v1.services.workspace_service import WorkspaceService

# Singletons for default health/metrics providers
_health_provider = ObservabilityHealthProvider()
_metrics_provider = ObservabilityMetricsProvider()

# Singletons for core platform providers
_decision_provider = InMemoryDecisionProvider()
_portfolio_provider = InMemoryPortfolioProvider()
_pipeline_run_provider = InMemoryPipelineRunProvider()
_scheduler_history_provider = InMemorySchedulerHistoryProvider()
_workspace_provider = InMemoryWorkspaceProvider()

# Seed sample data for Swagger / Dev runtime
seed_sample_data(
    _decision_provider,
    _portfolio_provider,
    _pipeline_run_provider,
    _scheduler_history_provider,
    _workspace_provider,
)


def get_health_provider() -> HealthProvider:
    """Dependency provider for HealthProvider."""
    return _health_provider


def get_metrics_provider() -> MetricsProvider:
    """Dependency provider for MetricsProvider."""
    return _metrics_provider


def get_decision_provider() -> DecisionProvider:
    """Dependency provider for DecisionProvider."""
    return _decision_provider


def get_portfolio_provider() -> PortfolioProvider:
    """Dependency provider for PortfolioProvider."""
    return _portfolio_provider


def get_pipeline_run_provider() -> PipelineRunProvider:
    """Dependency provider for PipelineRunProvider."""
    return _pipeline_run_provider


def get_scheduler_history_provider() -> SchedulerHistoryProvider:
    """Dependency provider for SchedulerHistoryProvider."""
    return _scheduler_history_provider


def get_workspace_provider() -> WorkspaceProvider:
    """Dependency provider for WorkspaceProvider."""
    return _workspace_provider


def get_health_service(request: Request) -> HealthService:
    """Dependency provider for HealthService.

    Injects the active HealthProvider.
    """
    provider = getattr(request.app.state, "health_provider", _health_provider)
    return HealthService(provider)


def get_metrics_service(request: Request) -> MetricsService:
    """Dependency provider for MetricsService.

    Injects the active MetricsProvider.
    """
    provider = getattr(request.app.state, "metrics_provider", _metrics_provider)
    return MetricsService(provider)


def get_decisions_service(request: Request) -> DecisionsService:
    """Dependency provider for DecisionsService."""
    provider = getattr(request.app.state, "decision_provider", _decision_provider)
    return DecisionsService(provider)


def get_portfolio_service(request: Request) -> PortfolioService:
    """Dependency provider for PortfolioService."""
    provider = getattr(
        request.app.state, "portfolio_provider", _portfolio_provider
    )
    return PortfolioService(provider)


def get_pipelines_service(request: Request) -> PipelinesService:
    """Dependency provider for PipelinesService."""
    provider = getattr(
        request.app.state, "pipeline_run_provider", _pipeline_run_provider
    )
    return PipelinesService(provider)


def get_scheduler_service(request: Request) -> SchedulerService:
    """Dependency provider for SchedulerService."""
    provider = getattr(
        request.app.state,
        "scheduler_history_provider",
        _scheduler_history_provider,
    )
    pipelines_serv = get_pipelines_service(request)
    return SchedulerService(provider, pipelines_serv)


def get_workspace_service(request: Request) -> WorkspaceService:
    """Dependency provider for WorkspaceService."""
    provider = getattr(request.app.state, "workspace_provider", _workspace_provider)
    return WorkspaceService(provider)
