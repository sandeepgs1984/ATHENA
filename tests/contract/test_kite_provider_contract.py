"""KiteProvider must pass the frozen provider contract UNCHANGED (R4)."""

from __future__ import annotations

from datetime import date

import pytest
from tests.contract.provider_contract import MarketDataProviderContract
from tests.data_layer.test_kite_provider import FakeKiteTransport, _config

from athena.data.providers.kite_provider import KiteProvider


class TestKiteProviderContract(MarketDataProviderContract):
    @pytest.fixture()
    def provider(self) -> KiteProvider:
        return KiteProvider(_config(), FakeKiteTransport())

    @pytest.fixture()
    def known_daily_range(self):
        return ("NSE:INFY", date(2026, 2, 10), date(2026, 2, 12))
