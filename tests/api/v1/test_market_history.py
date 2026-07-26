"""Read-only candles API tests (M-D2)."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from decimal import Decimal

from fastapi.testclient import TestClient
from tests.api.v1.test_core_apis import get_auth_headers

from athena.api.dependencies import get_candle_history_provider
from athena.api.security.models import Role
from athena.api.v1.providers.in_memory import InMemoryCandleHistoryProvider
from athena.api.v1.services.market_history_service import MarketHistoryService
from athena.domain.enums import Timeframe
from athena.domain.market import Candle
from athena.indicators.calculations import align_trailing_series, atr_series, sma_series


def _candle(ts: datetime, close: str) -> Candle:
    value = Decimal(close)
    return Candle(
        instrument_id="NSE:INFY",
        timeframe=Timeframe.M5,
        ts_open=ts,
        open=value - Decimal("1"),
        high=value + Decimal("1"),
        low=value - Decimal("2"),
        close=value,
        volume=1000,
        source="test",
    )


def test_recent_candles_are_chronological_and_fresh(client: TestClient) -> None:
    headers = get_auth_headers(client, Role.READONLY)
    provider = get_candle_history_provider()
    now = datetime.now(tz=timezone.utc)
    provider.candles.extend(  # type: ignore[attr-defined]
        [
            _candle(now - timedelta(minutes=10), "101"),
            _candle(now - timedelta(minutes=5), "102"),
        ]
    )

    response = client.get(
        "/api/v1/market/instruments/NSE%3AINFY/candles?timeframe=5m&limit=120",
        headers=headers,
    )
    assert response.status_code == 200
    data = response.json()["data"]
    assert data["instrument_id"] == "NSE:INFY"
    assert data["timeframe"] == "5m"
    assert data["count"] == 2
    assert [row["close"] for row in data["candles"]] == ["101", "102"]
    assert data["freshness_status"] == "FRESH"
    assert data["age_minutes"] in (4, 5)
    assert data["freshness_threshold_minutes"] == 20


def test_candles_report_stale_and_no_data_states(client: TestClient) -> None:
    headers = get_auth_headers(client, Role.READONLY)
    provider = get_candle_history_provider()
    provider.candles.append(  # type: ignore[attr-defined]
        _candle(datetime.now(tz=timezone.utc) - timedelta(minutes=60), "100")
    )

    stale = client.get(
        "/api/v1/market/instruments/NSE:INFY/candles?timeframe=5m",
        headers=headers,
    )
    assert stale.status_code == 200
    assert stale.json()["data"]["freshness_status"] == "STALE"

    missing = client.get(
        "/api/v1/market/instruments/NSE:SBIN/candles?timeframe=5m",
        headers=headers,
    )
    assert missing.status_code == 200
    assert missing.json()["data"]["freshness_status"] == "NO_DATA"
    assert missing.json()["data"]["candles"] == []
    assert missing.json()["data"]["latest_ts"] is None


def test_candles_require_auth_and_validate_timeframe(client: TestClient) -> None:
    unauthenticated = client.get(
        "/api/v1/market/instruments/NSE:INFY/candles"
    )
    assert unauthenticated.status_code == 401

    headers = get_auth_headers(client, Role.READONLY)
    invalid = client.get(
        "/api/v1/market/instruments/NSE:INFY/candles?timeframe=30m",
        headers=headers,
    )
    assert invalid.status_code == 422


def test_freshness_boundary_is_deterministic() -> None:
    now = datetime(2026, 7, 24, 10, 30, tzinfo=timezone.utc)
    provider = InMemoryCandleHistoryProvider()
    provider.candles.append(_candle(now - timedelta(minutes=20), "100"))
    service = MarketHistoryService(
        provider,
        freshness_threshold_minutes=20,
        now_fn=lambda: now,
    )
    result = service.recent_candles("NSE:INFY", Timeframe.M5, limit=120)
    assert result.freshness_status == "FRESH"
    assert result.age_minutes == 20


def test_candles_carry_atr_and_moving_average_overlay() -> None:
    """UX-3b: chart overlay values are None during warmup, then exactly match
    the same atr_series/sma_series functions used by TradePlan sizing —
    never a second, independently-derived computation."""
    now = datetime(2026, 7, 24, 10, 30, tzinfo=timezone.utc)
    provider = InMemoryCandleHistoryProvider()
    candles = [
        _candle(now - timedelta(minutes=5 * (25 - i)), str(100 + i))
        for i in range(25)
    ]
    provider.candles.extend(candles)  # type: ignore[attr-defined]
    service = MarketHistoryService(
        provider,
        freshness_threshold_minutes=20,
        now_fn=lambda: now,
    )

    result = service.recent_candles("NSE:INFY", Timeframe.M5, limit=120)
    assert result.count == 25

    closes = [c.close for c in candles]
    expected_atr = align_trailing_series(atr_series(candles, 14), len(candles))
    expected_sma = align_trailing_series(sma_series(closes, 20), len(candles))

    assert [row.atr for row in result.candles] == expected_atr
    assert [row.moving_average for row in result.candles] == expected_sma
    # Warmup prefix is honestly None, never a fabricated early value
    assert result.candles[0].atr is None
    assert result.candles[0].moving_average is None
    assert result.candles[-1].atr is not None
    assert result.candles[-1].moving_average is not None
