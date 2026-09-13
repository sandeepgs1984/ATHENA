"""SI-P1 Symbol Intelligence HTTP contract tests."""

from __future__ import annotations

from datetime import datetime, time, timedelta
from decimal import Decimal
from pathlib import Path
from zoneinfo import ZoneInfo

from fastapi.testclient import TestClient
from tests.api.v1.test_core_apis import get_auth_headers
from tests.symbol_intelligence.test_si_p1_composer import _d1_bars, _holding, _instrument

from athena.api.security.models import Role
from athena.api.v1.providers.sqlite_providers import SqliteDecisionProvider
from athena.calendar.engine import CalendarEngine
from athena.config.loader import load_config
from athena.data.store.repository import SqliteRepository
from athena.data.validation.calendar_expectations import latest_trading_day_on_or_before
from athena.domain.decision import Decision
from athena.domain.enums import DecisionType, Direction, Timeframe
from athena.domain.market import Candle

IST = ZoneInfo("Asia/Kolkata")
CONFIG = Path("config")


def test_symbol_intelligence_api_read_path(client: TestClient, tmp_path: Path) -> None:
    repo = SqliteRepository(tmp_path / "si-api.db")
    repo.initialize()
    now = datetime(2026, 9, 13, 13, 25, tzinfo=IST)
    cfg = load_config(CONFIG)
    expected = latest_trading_day_on_or_before(
        CalendarEngine.from_config_dir(CONFIG, cfg.market), now.astimezone(IST).date()
    )
    repo.upsert_instrument(_instrument("NSE:INFY", "INFY"))
    repo.add_candles(_d1_bars("NSE:INFY", expected))
    repo.save_decision(
        Decision(
            decision_id="d-api-si",
            ts=datetime.combine(expected, time(15, 30), tzinfo=IST),
            run_id="run",
            cycle_id="cycle",
            decision_type=DecisionType.WATCH,
            explanation="api watch",
            instrument_id="NSE:INFY",
            direction=Direction.NONE,
        )
    )
    _holding(repo, "NSE:INFY")
    client.app.state.sqlite_repo = repo
    client.app.state.decision_provider = SqliteDecisionProvider(repo)
    client.app.state.si_clock = lambda: now
    headers = get_auth_headers(client, Role.READONLY)

    search = client.get("/api/v1/symbol-intelligence/search?q=INFY", headers=headers)
    assert search.status_code == 200
    assert search.json()["data"]["hits"][0]["instrument_id"] == "NSE:INFY"

    composed = client.get("/api/v1/symbol-intelligence/NSE:INFY", headers=headers)
    assert composed.status_code == 200
    data = composed.json()["data"]
    assert data["identity"]["resolved"] is True
    assert data["decision"]["present"] is True
    assert data["momentum_quality"]["value"] is None
    assert data["entry_quality"]["value"] is None
    assert data["fundamentals"]["status"] == "NOT_INGESTED"
    assert data["news"]["status"] == "NOT_INGESTED"
    assert data["portfolio"]["status"] == "HELD"
    assert data["d1"]["rsi_is_coherent"] is True
    assert data["overall_freshness"]["status"] == "READY"
    iframe = data["darvax"]["iframe_url"] or ""
    assert "symbol=NSE%3AINFY" in iframe or "symbol=NSE:INFY" in iframe
    assert data["momentum_quality"]["named_evidence"]
    assert client.get("/api/v1/symbol-intelligence/NSE:INFY").status_code == 401
    repo.close()


def test_analyze_post_hydrates_and_readonly_cannot_write(
    client: TestClient, tmp_path: Path, monkeypatch
) -> None:
    from athena.errors import ProviderError
    from athena.symbol_intelligence.d1_hydrate import SiHydrationOutcome, SymbolIntelligenceD1Hydrator

    repo = SqliteRepository(tmp_path / "si-api-analyze.db")
    repo.initialize()
    now = datetime(2026, 9, 13, 13, 25, tzinfo=IST)
    cfg = load_config(CONFIG)
    expected = latest_trading_day_on_or_before(
        CalendarEngine.from_config_dir(CONFIG, cfg.market), now.astimezone(IST).date()
    )
    repo.upsert_instrument(_instrument("NSE:INFY", "INFY"))
    repo.add_candles(_d1_bars("NSE:INFY", expected - timedelta(days=21), count=30))
    client.app.state.sqlite_repo = repo
    client.app.state.si_clock = lambda: now
    calls: list[str] = []

    def _hydrate(self, instrument_id: str, *, as_of):
        calls.append(instrument_id)
        repo.add_candles(_d1_bars("NSE:INFY", expected, count=60))
        return SiHydrationOutcome(status="HYDRATED", detail="api test", candles_written=60)

    monkeypatch.setattr(SymbolIntelligenceD1Hydrator, "needs_refresh", lambda *a, **k: True)
    monkeypatch.setattr(SymbolIntelligenceD1Hydrator, "hydrate", _hydrate)
    monkeypatch.setattr(
        "athena.symbol_intelligence.composer.fetch_live_quote_view",
        lambda *a, **k: (_ for _ in ()).throw(ProviderError("no live kite in unit test")),
    )
    denied = client.post(
        "/api/v1/symbol-intelligence/NSE:INFY",
        headers=get_auth_headers(client, Role.READONLY, username="si-ro"),
    )
    assert denied.status_code == 403
    assert calls == []
    ok = client.post(
        "/api/v1/symbol-intelligence/NSE:INFY",
        headers=get_auth_headers(client, Role.OPERATOR, username="si-op"),
    )
    assert ok.status_code == 200
    assert calls == ["NSE:INFY"]
    data = ok.json()["data"]
    assert data["hydration"]["status"] == "HYDRATED"
    assert data["d1"]["present"] is True
    assert data["live"]["present"] is False
    assert data["live"]["quote_kind"] == "UNAVAILABLE"
    assert data["live"]["market_state"] == "MARKET CLOSED"
    assert data["overall_freshness"]["status"] == "PARTIAL"
    repo.close()


def test_d1_candle_api_accepts_daily_timeframe(client: TestClient) -> None:
    headers = get_auth_headers(client, Role.READONLY)
    from athena.api.dependencies import get_candle_history_provider

    provider = get_candle_history_provider()
    ts = datetime(2026, 9, 11, 9, 15, tzinfo=IST)
    provider.candles.append(  # type: ignore[attr-defined]
        Candle(
            instrument_id="NSE:INFY",
            timeframe=Timeframe.D1,
            ts_open=ts,
            open=Decimal("100"),
            high=Decimal("101"),
            low=Decimal("99"),
            close=Decimal("100"),
            volume=1000,
            source="test",
        )
    )
    response = client.get(
        "/api/v1/market/instruments/NSE:INFY/candles?timeframe=1d&limit=20",
        headers=headers,
    )
    assert response.status_code == 200
    assert response.json()["data"]["timeframe"] == "1d"
    assert response.json()["data"]["count"] == 1
    still_invalid = client.get(
        "/api/v1/market/instruments/NSE:INFY/candles?timeframe=30m",
        headers=headers,
    )
    assert still_invalid.status_code == 422
