"""Resolve ``MarketDataProvider`` implementations from config (R4)."""

from __future__ import annotations

from pathlib import Path

from athena.config.loader import load_ingestion_config
from athena.data.providers.file_provider import FileProvider
from athena.data.providers.kite_provider import KiteProvider
from athena.domain.interfaces import MarketDataProvider
from athena.errors import ConfigError


def build_market_data_provider(
    config_dir: Path,
    *,
    base_dir: Path | None = None,
    provider_name: str | None = None,
    kite_symbols: list[str] | None = None,
) -> MarketDataProvider:
    """Select provider by ``ingestion.provider`` (or explicit ``provider_name``).

    Default remains ``file``. ``kite`` requires ``KITE_*`` secrets in the environment.
    When ``kite_symbols`` is set, the Kite catalog is filtered to those trading symbols
    (owner validation candidates) instead of ``kite.json`` symbols alone.
    """
    name = provider_name if provider_name is not None else load_ingestion_config(config_dir).provider
    if name == "file":
        return FileProvider.from_config_dir(config_dir, base_dir=base_dir)
    if name == "kite":
        # A candidate-scope list is owner data, not configuration: one symbol the
        # exchange does not list must not abort an entire cycle. Callers that pass
        # a scope resolve it against the catalog and report the misses themselves,
        # so only kite.json's own symbols keep the strict fail-loud check.
        return KiteProvider.from_config_dir(
            config_dir,
            symbols=kite_symbols,
            strict_symbol_filter=kite_symbols is None,
        )
    raise ConfigError(
        f"ingestion.provider '{name}' is not supported; allowed: 'file', 'kite'"
    )
