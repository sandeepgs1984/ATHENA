"""M1.1 proof: the contract suite runs green against a conforming provider
and catches non-conforming ones."""

from __future__ import annotations

from datetime import date

import pytest

from athena.domain.enums import HealthStatus, Timeframe
from athena.domain.interfaces import (
    MarketDataProvider,
    ProviderCapabilities,
    ProviderHealth,
)
from tests.contract.provider_contract import MarketDataProviderContract
from tests.contract.stub_provider import StubProvider


class TestStubProviderContract(MarketDataProviderContract):
    """The reference provider must pass the whole suite — this is the suite's own test."""

    @pytest.fixture()
    def provider(self):
        return StubProvider()

    @pytest.fixture()
    def known_daily_range(self):
        return ("STUB-AAA", date(2026, 2, 2), date(2026, 2, 13))


class TestSuiteCatchesViolations:
    def test_incomplete_provider_fails_protocol_check(self):
        class NotAProvider:
            name = "broken"

        assert not isinstance(NotAProvider(), MarketDataProvider)

    def test_order_method_detection(self):
        class RogueProvider(StubProvider):
            name = "rogue"

            def place_order(self, *args):  # forbidden by ADR-002
                raise RuntimeError

        contract = MarketDataProviderContract()
        with pytest.raises(AssertionError, match="forbidden order/trade methods"):
            contract.test_no_order_methods_exist(RogueProvider())

    def test_capabilities_invariants(self):
        with pytest.raises(ValueError, match="at least one timeframe"):
            ProviderCapabilities(timeframes=(), max_history_days=10,
                                 supports_quotes=False, supports_market_snapshot=False)
        with pytest.raises(ValueError, match="duplicates"):
            ProviderCapabilities(timeframes=(Timeframe.D1, Timeframe.D1), max_history_days=10,
                                 supports_quotes=False, supports_market_snapshot=False)
        with pytest.raises(ValueError, match="max_history_days"):
            ProviderCapabilities(timeframes=(Timeframe.D1,), max_history_days=0,
                                 supports_quotes=False, supports_market_snapshot=False)

    def test_provider_health_requires_detail(self):
        with pytest.raises(ValueError, match="detail is mandatory"):
            ProviderHealth(status=HealthStatus.OK, detail="")
