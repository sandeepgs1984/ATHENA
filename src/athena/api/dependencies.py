"""Dependency injection factories (P8.1).

FastAPI dependency providers to inject services into controllers.
Allows clean mocking of services and providers in unit tests.
"""

from __future__ import annotations

from pathlib import Path

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
    CandleHistoryProvider,
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
    InMemoryCandleHistoryProvider,
    InMemoryDecisionProvider,
    InMemoryExportProvider,
    InMemoryPerformanceAnalyticsProvider,
    InMemoryPipelineRunProvider,
    InMemoryPortfolioProvider,
    InMemoryReportProvider,
    InMemorySchedulerHistoryProvider,
    InMemoryWorkspaceProvider,
)
from athena.api.v1.providers.observability import (
    ObservabilityHealthProvider,
    ObservabilityMetricsProvider,
)
from athena.api.v1.providers.sqlite_providers import (
    SqliteCandleHistoryProvider,
    SqliteDecisionProvider,
    SqlitePipelineRunProvider,
    SqlitePortfolioProvider,
    default_db_path,
    load_starting_cash,
)
from athena.api.v1.services.analytics_service import AnalyticsService
from athena.api.v1.services.backtests_service import BacktestsService
from athena.api.v1.services.candidates_service import CandidatesService
from athena.api.v1.services.dashboard_service import DashboardService
from athena.api.v1.services.decisions_service import DecisionsService
from athena.api.v1.services.exports_service import ExportsService
from athena.api.v1.services.health_service import HealthService
from athena.api.v1.services.market_history_service import MarketHistoryService
from athena.api.v1.services.market_summary_service import MarketSummaryService
from athena.api.v1.services.metrics_service import MetricsService
from athena.api.v1.services.opportunities_service import OpportunitiesService
from athena.api.v1.services.ops_service import OpsService
from athena.api.v1.services.pipelines_service import PipelinesService
from athena.api.v1.services.portfolio_service import PortfolioService
from athena.api.v1.services.reports_service import ReportsService
from athena.api.v1.services.saved_symbols_service import SavedSymbolsService
from athena.api.v1.services.scheduler_service import SchedulerService
from athena.api.v1.services.strategies_service import StrategyService
from athena.api.v1.services.workspace_service import WorkspaceService
from athena.data.store.repository import SqliteRepository
from athena.export.engine import ExportPresentationEngine
from athena.ops.owner_candidates import InMemoryCandidateStore, SqliteCandidateStore
from athena.ops.saved_symbols import InMemorySavedSymbolStore, SqliteSavedSymbolStore

# Singletons for default health/metrics providers
_health_provider = ObservabilityHealthProvider()
_metrics_provider = ObservabilityMetricsProvider()

# Empty in-memory defaults for tests / fallback when DB is unavailable.
# Live apps attach Sqlite* providers on app.state in create_app (no seed data).
_decision_provider = InMemoryDecisionProvider()
_portfolio_provider = InMemoryPortfolioProvider()
_pipeline_run_provider = InMemoryPipelineRunProvider()
_scheduler_history_provider = InMemorySchedulerHistoryProvider()
_workspace_provider = InMemoryWorkspaceProvider()
_report_provider = InMemoryReportProvider()
_analytics_provider = InMemoryPerformanceAnalyticsProvider()
_export_provider = InMemoryExportProvider()
# Long-lived: its export_id counter must persist across requests, or every
# on-demand export collides on "exp-0001" against the artifact store above.
_export_engine = ExportPresentationEngine()
_backtest_run_provider = InMemoryBacktestRunProvider()
_candidate_store = InMemoryCandidateStore()
_saved_symbol_store = InMemorySavedSymbolStore()
_candle_history_provider = InMemoryCandleHistoryProvider()

_sqlite_repo: SqliteRepository | None = None


def wire_sqlite_providers(
    app_state: object,
    *,
    db_path: Path | None = None,
) -> SqliteRepository | None:
    """Attach SQLite-backed decision/portfolio/pipeline providers to app.state.

    Returns the open repository (caller should keep it for lifespan shutdown),
    or None if the database cannot be opened.
    """
    global _sqlite_repo
    path = Path(db_path) if db_path else default_db_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    try:
        repo = SqliteRepository(path)
        repo.initialize()
    except Exception:
        return None

    starting = load_starting_cash()
    decision_prov = SqliteDecisionProvider(repo)
    candle_history_prov = SqliteCandleHistoryProvider(repo)
    portfolio_prov = SqlitePortfolioProvider(repo, starting_cash=starting)
    pipeline_prov = SqlitePipelineRunProvider(repo)
    candidate_store = SqliteCandidateStore(repo)
    saved_symbol_store = SqliteSavedSymbolStore(repo)

    app_state.ops_db_path = path  # type: ignore[attr-defined]
    app_state.sqlite_repo = repo  # type: ignore[attr-defined]
    app_state.decision_provider = decision_prov  # type: ignore[attr-defined]
    app_state.candle_history_provider = candle_history_prov  # type: ignore[attr-defined]
    app_state.portfolio_provider = portfolio_prov  # type: ignore[attr-defined]
    app_state.pipeline_run_provider = pipeline_prov  # type: ignore[attr-defined]
    app_state.candidate_store = candidate_store  # type: ignore[attr-defined]
    app_state.saved_symbol_store = saved_symbol_store  # type: ignore[attr-defined]
    _sqlite_repo = repo
    return repo


def get_health_provider() -> HealthProvider:
    """Dependency provider for HealthProvider."""
    return _health_provider


def get_metrics_provider() -> MetricsProvider:
    """Dependency provider for MetricsProvider."""
    return _metrics_provider


def get_decision_provider() -> DecisionProvider:
    """Dependency provider for DecisionProvider."""
    return _decision_provider


def get_candle_history_provider() -> CandleHistoryProvider:
    """Module-level candle provider for deterministic API tests."""
    return _candle_history_provider


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


def _find_repo_root() -> Path:
    here = Path(__file__).resolve().parent
    repo_root = here
    for _ in range(8):
        if (repo_root / "pyproject.toml").is_file():
            break
        repo_root = repo_root.parent
    return repo_root


def get_decisions_service(request: Request) -> DecisionsService:
    """Dependency provider for DecisionsService."""
    provider = getattr(request.app.state, "decision_provider", _decision_provider)
    db_path = getattr(request.app.state, "ops_db_path", None)
    backup_dir = getattr(request.app.state, "ops_backup_dir", None)
    repo = getattr(request.app.state, "sqlite_repo", None)
    return DecisionsService(
        provider,
        config_dir=_find_repo_root() / "config",
        db_path=db_path,
        backup_dir=backup_dir,
        repo=repo,
    )


def get_market_history_service(request: Request) -> MarketHistoryService:
    """Dependency provider for freshness-aware persisted candles."""
    provider = getattr(
        request.app.state,
        "candle_history_provider",
        _candle_history_provider,
    )
    freshness_minutes = request.app.state.intraday_freshness_minutes
    repo = getattr(request.app.state, "sqlite_repo", None)
    return MarketHistoryService(
        provider,
        freshness_threshold_minutes=freshness_minutes,
        config_dir=_find_repo_root() / "config",
        repo=repo,
    )


def get_opportunities_service(request: Request) -> OpportunitiesService:
    """Dependency provider for Top Opportunities Today.

    Composes the SAME `MarketHistoryService` construction
    `get_market_history_service` already builds, rather than a second,
    divergent one — read-only, no new provider or persistence.
    """
    repo = getattr(request.app.state, "sqlite_repo", None)
    if repo is None:
        raise RuntimeError("sqlite_repo is required for top opportunities")
    market_history = get_market_history_service(request)
    return OpportunitiesService(
        repo, market_history=market_history, config_dir=_find_repo_root() / "config",
    )


def get_market_summary_service(request: Request) -> MarketSummaryService:
    """Dependency provider for Market Summary hero read model (MH-3)."""
    repo = getattr(request.app.state, "sqlite_repo", None)
    if repo is None:
        raise RuntimeError("sqlite_repo is required for market summary")
    return MarketSummaryService(repo)


def get_portfolio_service(request: Request) -> PortfolioService:
    """Dependency provider for PortfolioService."""
    provider = getattr(
        request.app.state, "portfolio_provider", _portfolio_provider
    )
    db_path = getattr(request.app.state, "ops_db_path", None)
    backup_dir = getattr(request.app.state, "ops_backup_dir", None)
    return PortfolioService(provider, db_path=db_path, backup_dir=backup_dir)


def get_candidate_store():
    """Module-level candidate store (tests override via app.state)."""
    return _candidate_store


def get_candidates_service(request: Request) -> CandidatesService:
    """Dependency provider for CandidatesService."""
    store = getattr(request.app.state, "candidate_store", _candidate_store)
    repo = getattr(request.app.state, "sqlite_repo", None)
    repo_root = _find_repo_root()
    return CandidatesService(
        store,
        repo=repo,
        config_dir=repo_root / "config",
        repo_root=repo_root,
    )


def get_saved_symbol_store():
    """Module-level saved-symbol store (tests override via app.state)."""
    return _saved_symbol_store


def get_saved_symbols_service(request: Request) -> SavedSymbolsService:
    """Dependency provider for SavedSymbolsService."""
    store = getattr(request.app.state, "saved_symbol_store", _saved_symbol_store)
    return SavedSymbolsService(store)


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
    engine = getattr(request.app.state, "export_engine", _export_engine)
    return ExportsService(
        query_prov, gen_prov, rep_prov, get_decisions_service(request), engine=engine
    )


def get_dashboard_service(request: Request) -> DashboardService:
    """Dependency provider for DashboardService."""
    port_prov = getattr(request.app.state, "portfolio_provider", _portfolio_provider)
    pipe_prov = getattr(
        request.app.state, "pipeline_run_provider", _pipeline_run_provider
    )
    health_prov = getattr(request.app.state, "health_provider", _health_provider)
    analytics_prov = getattr(
        request.app.state, "analytics_provider", _analytics_provider
    )
    return DashboardService(port_prov, pipe_prov, health_prov, analytics_prov)


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


def get_ops_service(request: Request) -> OpsService:
    """Dependency provider for OpsService (P9.7)."""
    health_prov = getattr(request.app.state, "health_provider", _health_provider)
    metrics_prov = getattr(request.app.state, "metrics_provider", _metrics_provider)
    pipe_prov = getattr(
        request.app.state, "pipeline_run_provider", _pipeline_run_provider
    )
    db_path = getattr(request.app.state, "ops_db_path", None)
    backup_dir = getattr(request.app.state, "ops_backup_dir", None)
    return OpsService(
        health_prov,
        metrics_prov,
        pipe_prov,
        db_path=db_path,
        backup_dir=backup_dir,
    )


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
