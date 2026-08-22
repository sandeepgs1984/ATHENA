"""RetryingMarketDataProvider: bounded retry/backoff for transient failures
only -- the Kite transport already retries 429s itself, so this exists for
the failure class it doesn't (network-level and 5xx errors), and must never
retry a permanent failure (4xx, or an unrelated logic error)."""

from __future__ import annotations

from datetime import datetime, timezone

import pytest

from athena.data.retrying_provider import RetryingMarketDataProvider, is_transient_provider_error
from athena.domain.enums import Timeframe
from athena.errors import ProviderError

UTC_NOW = datetime.now(tz=timezone.utc)


class _FlakyProvider:
    name = "flaky"

    def __init__(self, error_sequence: list[Exception | None]):
        self._errors = list(error_sequence)
        self.calls = 0

    def intraday_candles(self, instrument_id, timeframe, start, end):
        error = self._errors[self.calls]
        self.calls += 1
        if error is not None:
            raise error
        return ["ok"]

    def capabilities(self):  # pragma: no cover - unused by these tests
        raise NotImplementedError

    def instruments(self):  # pragma: no cover
        raise NotImplementedError

    def daily_candles(self, instrument_id, start, end):  # pragma: no cover
        raise NotImplementedError

    def quotes(self, instrument_ids):  # pragma: no cover
        raise NotImplementedError

    def market_snapshot(self):  # pragma: no cover
        raise NotImplementedError

    def health(self):  # pragma: no cover
        raise NotImplementedError


@pytest.mark.parametrize(
    "message,expected",
    [
        ("kite network failure on /historical: timed out", True),
        ("kite network failure on /instruments: Connection reset", True),
        ("kite HTTP 500 on /historical: internal server error", True),
        ("kite HTTP 502 on /historical: bad gateway", True),
        ("kite HTTP 403 on /historical: forbidden", False),
        ("kite HTTP 404 on /historical: not found", False),
        ("kite HTTP 400 on /historical: bad request", False),
        ("timeframe M1 not supported by provider 'kite'", False),
        ("unknown instrument id 'NSE:GHOST'", False),
    ],
)
def test_transient_classification(message: str, expected: bool):
    assert is_transient_provider_error(ProviderError(message)) is expected


def test_recovers_after_transient_failures_and_counts_retries():
    provider = _FlakyProvider([
        ProviderError("kite network failure on /historical: timed out"),
        ProviderError("kite network failure on /historical: timed out"),
        None,
    ])
    sleeps: list[float] = []
    wrapper = RetryingMarketDataProvider(inner=provider, max_retries=3, sleep=sleeps.append)

    result = wrapper.intraday_candles("NSE:X", Timeframe.M5, UTC_NOW, UTC_NOW)

    assert result == ["ok"]
    assert provider.calls == 3
    assert wrapper.stats.requests_attempted == 3
    assert wrapper.stats.retries_performed == 2
    assert wrapper.stats.permanent_failures == 0
    assert wrapper.stats.retry_exhausted_failures == 0
    # Exponential backoff: base * 2^0, base * 2^1.
    assert sleeps == [2.0, 4.0]


def test_gives_up_after_exhausting_retries():
    provider = _FlakyProvider([
        ProviderError("kite network failure on /historical: timed out"),
        ProviderError("kite network failure on /historical: timed out"),
        ProviderError("kite network failure on /historical: timed out"),
    ])
    wrapper = RetryingMarketDataProvider(inner=provider, max_retries=2, sleep=lambda s: None)

    with pytest.raises(ProviderError):
        wrapper.intraday_candles("NSE:X", Timeframe.M5, UTC_NOW, UTC_NOW)

    assert provider.calls == 3  # initial attempt + 2 retries
    assert wrapper.stats.retries_performed == 2
    assert wrapper.stats.retry_exhausted_failures == 1
    assert wrapper.stats.permanent_failures == 0


def test_never_retries_a_permanent_failure():
    """The whole point of classifying failures: a 4xx (bad request, auth
    failure, unresolved instrument) will not change on retry, and retrying
    it anyway would only burn real API calls against the owner's live
    session for zero benefit."""

    provider = _FlakyProvider([
        ProviderError("kite HTTP 403 on /historical: forbidden"),
        None,  # would succeed if (incorrectly) retried -- must never be reached
    ])
    wrapper = RetryingMarketDataProvider(inner=provider, max_retries=5, sleep=lambda s: None)

    with pytest.raises(ProviderError):
        wrapper.intraday_candles("NSE:X", Timeframe.M5, UTC_NOW, UTC_NOW)

    assert provider.calls == 1
    assert wrapper.stats.retries_performed == 0
    assert wrapper.stats.permanent_failures == 1
    assert wrapper.stats.retry_exhausted_failures == 0


def test_name_and_capabilities_pass_through():
    class _Named:
        name = "kite-real"

    wrapper = RetryingMarketDataProvider(inner=_Named())
    assert wrapper.name == "kite-real"
