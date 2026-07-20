"""MarketDataProvider conformance suite (ATHENA-002 §7.2, M1.1).

Any provider implementation — FileProvider (M1.2), future broker adapters
(DD-1) — must pass this suite UNCHANGED. Usage in a provider's test module:

    class TestMyProviderContract(MarketDataProviderContract):
        @pytest.fixture()
        def provider(self):
            return MyProvider(...)

        @pytest.fixture()
        def known_daily_range(self):
            return ("<instrument_id>", date(...), date(...))  # range with data

The suite verifies the behavioral contract documented on the Protocol:
capability honesty, candle ordering/uniqueness/range, emptiness-is-not-error,
determinism, unknown-id failures, and the structural absence of order methods.
"""

from __future__ import annotations

from datetime import date, datetime, time, timezone

import pytest

from athena.domain.enums import Timeframe
from athena.domain.interfaces import (
    MarketDataProvider,
    ProviderCapabilities,
    ProviderHealth,
)
from athena.errors import ProviderError

#: Method-name fragments that must not exist on any provider (ADR-002).
FORBIDDEN_NAME_MARKERS = ("order", "buy", "sell", "trade", "place", "execute", "position")

#: A date range no NSE provider can have data for (pre-exchange-founding).
EMPTY_RANGE = (date(1970, 1, 6), date(1970, 1, 9))

_INTRADAY = {Timeframe.M1, Timeframe.M5, Timeframe.M15}


class MarketDataProviderContract:
    """Subclass per provider; override the `provider` and `known_daily_range` fixtures."""

    # ---------------------------------------------------------------- fixtures

    @pytest.fixture()
    def provider(self) -> MarketDataProvider:
        raise NotImplementedError("provider test class must supply a `provider` fixture")

    @pytest.fixture()
    def known_daily_range(self, provider) -> tuple[str, date, date]:
        raise NotImplementedError(
            "provider test class must supply `known_daily_range`: "
            "(instrument_id, start, end) guaranteed to contain daily data"
        )

    @pytest.fixture()
    def capabilities(self, provider) -> ProviderCapabilities:
        return provider.capabilities()

    # ------------------------------------------------------------- structural

    def test_conforms_to_protocol(self, provider):
        assert isinstance(provider, MarketDataProvider)
        assert provider.name, "provider must declare a non-empty name"

    def test_no_order_methods_exist(self, provider):
        """Order placement must be structurally impossible (ADR-002, S-1)."""
        offenders = [
            attr for attr in dir(provider)
            if not attr.startswith("_")
            and any(marker in attr.lower() for marker in FORBIDDEN_NAME_MARKERS)
        ]
        assert not offenders, (
            f"provider '{provider.name}' exposes forbidden order/trade methods: {offenders}"
        )

    def test_capabilities_are_valid(self, capabilities):
        assert isinstance(capabilities, ProviderCapabilities)
        assert Timeframe.D1 in capabilities.timeframes, (
            "every provider must serve daily candles (Phase 1 baseline)"
        )

    # ------------------------------------------------------------ instruments

    def test_instruments_nonempty_and_unique(self, provider):
        instruments = provider.instruments()
        assert instruments, "provider must serve at least one instrument"
        ids = [i.instrument_id for i in instruments]
        assert len(ids) == len(set(ids)), "instrument_ids must be unique"

    # ----------------------------------------------------------- daily candles

    def test_daily_candles_sorted_unique_and_in_range(self, provider, known_daily_range):
        instrument_id, start, end = known_daily_range
        candles = provider.daily_candles(instrument_id, start, end)
        assert candles, "known_daily_range fixture must contain data"
        stamps = [c.ts_open for c in candles]
        assert stamps == sorted(stamps), "candles must be sorted ascending by ts_open"
        assert len(stamps) == len(set(stamps)), "duplicate candle timestamps"
        for c in candles:
            assert c.instrument_id == instrument_id
            assert c.timeframe is Timeframe.D1
            assert c.ts_open.tzinfo is not None, "candle timestamps must be timezone-aware"
            assert start <= c.ts_open.date() <= end, "candle outside requested range"

    def test_daily_candles_deterministic(self, provider, known_daily_range):
        instrument_id, start, end = known_daily_range
        first = provider.daily_candles(instrument_id, start, end)
        second = provider.daily_candles(instrument_id, start, end)
        assert first == second, "identical historical requests must return identical results"

    def test_empty_range_returns_empty_list(self, provider, known_daily_range):
        instrument_id, _, _ = known_daily_range
        assert provider.daily_candles(instrument_id, *EMPTY_RANGE) == []

    def test_unknown_instrument_fails_loudly(self, provider, known_daily_range):
        _, start, end = known_daily_range
        with pytest.raises(ProviderError, match=r"NO-SUCH-INSTRUMENT"):
            provider.daily_candles("NO-SUCH-INSTRUMENT", start, end)

    # -------------------------------------------------------- intraday candles

    def test_intraday_honors_declared_timeframes(self, provider, capabilities, known_daily_range):
        instrument_id, start, end = known_daily_range
        start_dt = datetime.combine(start, time(9, 15), tzinfo=timezone.utc)
        end_dt = datetime.combine(end, time(15, 30), tzinfo=timezone.utc)

        declared = set(capabilities.timeframes) & _INTRADAY
        undeclared = _INTRADAY - set(capabilities.timeframes)

        for tf in declared:
            candles = provider.intraday_candles(instrument_id, tf, start_dt, end_dt)
            for c in candles:
                assert c.timeframe is tf
                assert c.ts_open.tzinfo is not None
                assert start_dt <= c.ts_open <= end_dt

        for tf in undeclared:
            with pytest.raises(ProviderError, match=tf.value):
                provider.intraday_candles(instrument_id, tf, start_dt, end_dt)

    # ------------------------------------------------------------------ quotes

    def test_quotes_honor_capability(self, provider, capabilities, known_daily_range):
        instrument_id, _, _ = known_daily_range
        if capabilities.supports_quotes:
            quotes = provider.quotes([instrument_id])
            assert {q.instrument_id for q in quotes} <= {instrument_id}
            assert len(quotes) <= 1, "at most one quote per requested id"
            for q in quotes:
                assert q.ts.tzinfo is not None
        else:
            with pytest.raises(ProviderError, match=r"quote"):
                provider.quotes([instrument_id])

    # --------------------------------------------------------- snapshot/health

    def test_market_snapshot_honors_capability(self, provider, capabilities):
        if capabilities.supports_market_snapshot:
            snapshot = provider.market_snapshot()
            assert snapshot.ts.tzinfo is not None
            assert snapshot.indices, "market snapshot must include at least one index"
        else:
            with pytest.raises(ProviderError, match=r"snapshot"):
                provider.market_snapshot()

    def test_health_reports(self, provider):
        health = provider.health()
        assert isinstance(health, ProviderHealth)
        assert health.detail
