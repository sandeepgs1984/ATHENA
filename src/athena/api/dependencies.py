"""Dependency injection factories (P8.1).

FastAPI dependency providers to inject services into controllers.
Allows clean mocking of services and providers in unit tests.
"""

from __future__ import annotations

from fastapi import Request

from athena.api.platform.providers.build_info_provider import (
    BuildInfoProvider,
    DefaultBuildInfoProvider,
)
from athena.api.platform.providers.metadata_provider import (
    DefaultMetadataProvider,
    MetadataProvider,
)
from athena.api.v1.providers.base import (
    BacktestRunProvider,
    DecisionProvider,
    ExportGenerationProvider,
    ExportQueryProvider,
    HealthProvider,
    MetricsProvider,
    PerformanceAnalyticsProvider,
    PipelineRunProvider,
    PortfolioProvider,
    ReportProvider,
    SchedulerHistoryProvider,
    WorkspaceProvider,
)
from athena.api.v1.providers.in_memory import (
    InMemoryBacktestRunProvider,
    InMemoryDecisionProvider,
    InMemoryExportProvider,
    InMemoryPerformanceAnalyticsProvider,
    InMemoryPipelineRunProvider,
    InMemoryPortfolioProvider,
    InMemoryReportProvider,
    InMemorySchedulerHistoryProvider,
    InMemoryWorkspaceProvider,
    seed_sample_data,
)
from athena.api.v1.providers.observability import (
    ObservabilityHealthProvider,
    ObservabilityMetricsProvider,
)
from athena.api.v1.services.analytics_service import AnalyticsService
from athena.api.v1.services.backtests_service import BacktestsService
from athena.api.v1.services.dashboard_service import DashboardService
from athena.api.v1.services.decisions_service import DecisionsService
from athena.api.v1.services.exports_service import ExportsService
from athena.api.v1.services.health_service import HealthService
from athena.api.v1.services.metrics_service import MetricsService
from athena.api.v1.services.pipelines_service import PipelinesService
from athena.api.v1.services.portfolio_service import PortfolioService
from athena.api.v1.services.reports_service import ReportsService
from athena.api.v1.services.scheduler_service import SchedulerService
from athena.api.v1.services.strategies_service import StrategyService
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
_report_provider = InMemoryReportProvider()
_analytics_provider = InMemoryPerformanceAnalyticsProvider()
_export_provider = InMemoryExportProvider()
_backtest_run_provider = InMemoryBacktestRunProvider()

# Seed sample data for Swagger / Dev runtime
seed_sample_data(
    _decision_provider,
    _portfolio_provider,
    _pipeline_run_provider,
    _scheduler_history_provider,
    _workspace_provider,
    _report_provider,
    _analytics_provider,
    _export_provider,
    _backtest_run_provider,
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


def get_report_provider() -> ReportProvider:
    """Dependency provider for ReportProvider."""
    return _report_provider


def get_performance_analytics_provider() -> PerformanceAnalyticsProvider:
    """Dependency provider for PerformanceAnalyticsProvider."""
    return _analytics_provider


def get_export_query_provider() -> ExportQueryProvider:
    """Dependency provider for ExportQueryProvider."""
    return _export_provider


def get_export_generation_provider() -> ExportGenerationProvider:
    """Dependency provider for ExportGenerationProvider."""
    return _export_provider


def get_reports_service(request: Request) -> ReportsService:
    """Dependency provider for ReportsService."""
    provider = getattr(request.app.state, "report_provider", _report_provider)
    return ReportsService(provider)


def get_analytics_service(request: Request) -> AnalyticsService:
    """Dependency provider for AnalyticsService."""
    provider = getattr(request.app.state, "analytics_provider", _analytics_provider)
    return AnalyticsService(provider)


def get_exports_service(request: Request) -> ExportsService:
    """Dependency provider for ExportsService."""
    query_prov = getattr(request.app.state, "export_query_provider", _export_provider)
    gen_prov = getattr(request.app.state, "export_generation_provider", _export_provider)
    rep_prov = getattr(request.app.state, "report_provider", _report_provider)
    return ExportsService(query_prov, gen_prov, rep_prov)


def get_dashboard_service(request: Request) -> DashboardService:
    """Dependency provider for DashboardService."""
    port_prov = getattr(request.app.state, "portfolio_provider", _portfolio_provider)
    pipe_prov = getattr(
        request.app.state, "pipeline_run_provider", _pipeline_run_provider
    )
    health_prov = getattr(request.app.state, "health_provider", _health_provider)
    return DashboardService(port_prov, pipe_prov, health_prov)


def get_backtest_run_provider() -> BacktestRunProvider:
    """Dependency provider for BacktestRunProvider."""
    return _backtest_run_provider


def get_strategies_service() -> StrategyService:
    """Dependency provider for StrategyService."""
    return StrategyService()


def get_backtests_service(request: Request) -> BacktestsService:
    """Dependency provider for BacktestsService."""
    provider = getattr(request.app.state, "backtest_run_provider", _backtest_run_provider)
    return BacktestsService(provider)


# ---------------------------------------------------------------------------
# Platform Infrastructure Providers (P8.5)
# ---------------------------------------------------------------------------


_build_info_provider: BuildInfoProvider = DefaultBuildInfoProvider()
_metadata_provider: MetadataProvider = DefaultMetadataProvider()


def get_build_info_provider(request: Request = None) -> BuildInfoProvider:
    """Dependency provider for BuildInfoProvider."""
    if request is not None and hasattr(request.app.state, "build_info_provider"):
        return request.app.state.build_info_provider
    return _build_info_provider


def get_metadata_provider(request: Request = None) -> MetadataProvider:
    """Dependency provider for MetadataProvider."""
    if request is not None and hasattr(request.app.state, "metadata_provider"):
        return request.app.state.metadata_provider
    return _metadata_provider
