"""FileProvider must pass the frozen provider contract UNCHANGED (M1.2)."""

from __future__ import annotations

from datetime import date
from pathlib import Path

import pytest
from tests.contract.provider_contract import MarketDataProviderContract

from athena.config.models import FileProviderConfig, ProviderCapabilitiesConfig
from athena.data.providers.file_provider import FileProvider

SYNTHETIC = Path(__file__).resolve().parents[1] / "data" / "fileprovider"


def _config() -> FileProviderConfig:
    return FileProviderConfig(
        data_root="unused",  # data_root passed explicitly to the constructor below
        instruments_file="instruments.csv",
        daily_dir="daily",
        intraday_dir="intraday",
        quotes_file="quotes.csv",
        snapshot_file="snapshot.json",
        capabilities=ProviderCapabilitiesConfig(
            timeframes=["1d", "5m"],
            max_history_days=365,
            supports_quotes=True,
            supports_market_snapshot=True,
        ),
    )


class TestFileProviderContract(MarketDataProviderContract):
    @pytest.fixture()
    def provider(self):
        return FileProvider(_config(), SYNTHETIC)

    @pytest.fixture()
    def known_daily_range(self):
        return ("SYN-AAA", date(2026, 2, 2), date(2026, 2, 13))
