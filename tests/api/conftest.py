"""Conftest containing pytest fixtures for API integration tests (P8.1)."""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from athena.api.app import create_app
from athena.api.config import APISettings


@pytest.fixture()
def api_settings() -> APISettings:
    """Fixture for API settings with test overrides."""
    return APISettings()


@pytest.fixture()
def client(api_settings: APISettings) -> TestClient:
    """Fixture for TestClient targeting the FastAPI application."""
    app = create_app(api_settings)
    return TestClient(app, raise_server_exceptions=False)
