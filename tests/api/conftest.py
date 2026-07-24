"""Conftest containing pytest fixtures for API integration tests (P8.1)."""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from athena.api.app import create_app
from athena.api.config import APISettings
from athena.api.dependencies import (
    get_decision_provider,
    get_pipeline_run_provider,
    get_portfolio_provider,
)


@pytest.fixture()
def api_settings() -> APISettings:
    """Fixture for API settings with test overrides."""
    return APISettings()


@pytest.fixture()
def client(api_settings: APISettings) -> TestClient:
    """Fixture for TestClient targeting the FastAPI application.

    Tests mutate module-level in-memory providers. Override app.state so requests
    do not hit the live SQLite ledger wired by create_app.
    """
    app = create_app(api_settings)
    app.state.decision_provider = get_decision_provider()
    app.state.portfolio_provider = get_portfolio_provider()
    app.state.pipeline_run_provider = get_pipeline_run_provider()
    from athena.api.dependencies import get_candidate_store

    store = get_candidate_store()
    store.clear()
    app.state.candidate_store = store
    return TestClient(app, raise_server_exceptions=False)
