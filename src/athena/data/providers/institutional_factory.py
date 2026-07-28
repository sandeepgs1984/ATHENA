"""Factory for InstitutionalFlowProvider (ADR-008)."""

from __future__ import annotations

from pathlib import Path

from athena.config.loader import load_ingestion_config
from athena.domain.interfaces import InstitutionalFlowProvider
from athena.errors import ConfigError


def build_institutional_flow_provider(
    config_dir: Path,
    provider_name: str | None = None,
    *,
    base_dir: Path | None = None,
) -> InstitutionalFlowProvider:
    """Select file or nse institutional-flow adapter from ingestion config."""
    ingestion = load_ingestion_config(config_dir)
    name = provider_name or ingestion.institutional_flow_provider
    if name == "file":
        from athena.data.providers.file_institutional_provider import (
            FileInstitutionalFlowProvider,
        )

        return FileInstitutionalFlowProvider.from_config_dir(config_dir, base_dir=base_dir)
    if name == "nse":
        from athena.data.providers.nse_institutional_provider import (
            NseInstitutionalFlowProvider,
        )

        return NseInstitutionalFlowProvider.from_config_dir(config_dir)
    raise ConfigError(
        f"unknown institutional_flow_provider {name!r}; expected 'file' or 'nse'"
    )
