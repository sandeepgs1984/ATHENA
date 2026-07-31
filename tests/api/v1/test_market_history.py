"""Read-only candles API tests (M-D2)."""

from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from tests.api.v1.test_core_apis import get_auth_headers

from athena.api.dependencies import get_candle_history_provider
from athena.api.security.models import Role
from athena.api.v1.providers.in_memory import InMemoryCandleHistoryProvider
from athena.api.v1.services.market_history_service import MarketHistoryService
from athena.config.loader import (
    load_index_intelligence_config,
    load_kite_provider_config,
)
from athena.data.store.repository import SqliteRepository
from athena.domain.enums import Timeframe
from athena.domain.market import Candle, Instrument, MarketSnapshot
from athena.errors import ConfigError
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


def _index_candle(instrument_id: str, ts: datetime, close: str) -> Candle:
    value = Decimal(close)
    return Candle(
        instrument_id=instrument_id,
        timeframe=Timeframe.D1,
        ts_open=ts,
        open=value,
        high=value,
        low=value,
        close=value,
        volume=0,
        source="test",
    )


def _register_index_instrument(repo: SqliteRepository, instrument_id: str) -> None:
    """candles.instrument_id REFERENCES instruments(instrument_id) — indices
    need a real row there too, same as any equity."""
    repo.upsert_instrument(
        Instrument(
            instrument_id=instrument_id,
            symbol=instrument_id.split(":", 1)[-1],
            exchange="NSE",
            series="INDEX",
        )
    )


class TestMarketTicker:
    """DT-2 header ticker — real level + real day-change %, derived only
    from already-persisted Kite snapshot + daily candle data. Uses a real
    SqliteRepository (not the in-memory candle provider) since the ticker
    reads get_latest_snapshot()/list_candles_recent() directly."""

    def test_ticker_computes_level_and_change_pct_from_real_data(
        self, tmp_path: Path
    ) -> None:
        repo = SqliteRepository(tmp_path / "t.db")
        repo.initialize()
        yesterday = datetime(2026, 7, 24, 15, 30, tzinfo=timezone.utc)
        today = datetime(2026, 7, 27, 5, 46, tzinfo=timezone.utc)  # ~11:16 IST

        for iid in ("NSE:NIFTY 50", "NSE:NIFTY BANK", "NSE:INDIA VIX"):
            _register_index_instrument(repo, iid)
        repo.add_candles([_index_candle("NSE:NIFTY 50", yesterday, "23800.00")])
        repo.add_candles([_index_candle("NSE:NIFTY BANK", yesterday, "56800.00")])
        repo.add_candles([_index_candle("NSE:INDIA VIX", yesterday, "13.10")])
        repo.add_snapshot(
            MarketSnapshot(
                ts=today,
                indices={"NIFTY 50": Decimal("23929.90"), "NIFTY BANK": Decimal("57023.55")},
                breadth_advances=0,
                breadth_declines=0,
                india_vix=Decimal("13.30"),
            )
        )

        service = MarketHistoryService(
            InMemoryCandleHistoryProvider(),
            freshness_threshold_minutes=20,
            repo=repo,
        )
        ticker = service.market_ticker()

        assert ticker.nifty.label == "NIFTY 50"
        assert ticker.nifty.level == Decimal("23929.90")
        assert ticker.nifty.change_pct == (
            (Decimal("23929.90") - Decimal("23800.00")) / Decimal("23800.00") * 100
        )
        assert ticker.bank_nifty.level == Decimal("57023.55")
        assert ticker.india_vix.level == Decimal("13.30")
        assert ticker.india_vix.change_pct is not None
        assert ticker.as_of == today
        repo.close()

    def test_ticker_omits_change_pct_without_a_prior_close_never_fabricates(
        self, tmp_path: Path
    ) -> None:
        """No prior-day candle persisted yet — change_pct must be None, not
        a fabricated 0 or the level itself (ADR-005)."""
        repo = SqliteRepository(tmp_path / "t2.db")
        repo.initialize()
        repo.add_snapshot(
            MarketSnapshot(
                ts=datetime(2026, 7, 27, 5, 46, tzinfo=timezone.utc),
                indices={"NIFTY 50": Decimal("23929.90")},
                breadth_advances=0,
                breadth_declines=0,
                india_vix=None,
            )
        )
        service = MarketHistoryService(
            InMemoryCandleHistoryProvider(),
            freshness_threshold_minutes=20,
            repo=repo,
        )
        ticker = service.market_ticker()

        assert ticker.nifty.level == Decimal("23929.90")
        assert ticker.nifty.change_pct is None
        assert ticker.bank_nifty.level is None
        assert ticker.bank_nifty.change_pct is None
        assert ticker.india_vix.level is None
        repo.close()

    def test_ticker_with_no_repo_or_no_snapshot_returns_all_none(self) -> None:
        """No repo wired (e.g. SQLite unavailable) — every field None, never
        a placeholder number."""
        service = MarketHistoryService(
            InMemoryCandleHistoryProvider(),
            freshness_threshold_minutes=20,
        )
        ticker = service.market_ticker()
        assert ticker.nifty.level is None
        assert ticker.bank_nifty.level is None
        assert ticker.india_vix.level is None
        assert ticker.as_of is None

    def test_ticker_endpoint_requires_auth(self, client: TestClient) -> None:
        unauthenticated = client.get("/api/v1/market/ticker")
        assert unauthenticated.status_code == 401

        headers = get_auth_headers(client, Role.READONLY)
        ok = client.get("/api/v1/market/ticker", headers=headers)
        assert ok.status_code == 200
        data = ok.json()["data"]
        # create_app() always wires the real ATHENA_DB_PATH (no test
        # override exists for this, a pre-existing characteristic of this
        # suite — not introduced here), so this hits whatever the real
        # local db/athena.db actually contains, not a clean fixture. Assert
        # the response shape only, never a specific value.
        assert set(data.keys()) == {"nifty", "bank_nifty", "india_vix", "as_of"}
        for key in ("nifty", "bank_nifty", "india_vix"):
            assert set(data[key].keys()) == {"label", "level", "change_pct"}


def _write_index_intelligence_config(config_dir: Path) -> None:
    config_dir.mkdir(parents=True, exist_ok=True)
    (config_dir / "index_intelligence.json").write_text(
        json.dumps(
            {
                "tracked_indices": [
                    {
                        "key": "nifty_it",
                        "label": "NIFTY IT",
                        "instrument_id": "NSE:NIFTY IT",
                        "family": "sectoral",
                        "display_order": 20,
                        "enabled": True,
                    },
                    {
                        "key": "nifty_50",
                        "label": "NIFTY 50",
                        "instrument_id": "NSE:NIFTY 50",
                        "family": "broad_market",
                        "display_order": 10,
                        "enabled": True,
                    },
                    {
                        "key": "disabled",
                        "label": "DISABLED",
                        "instrument_id": "NSE:DISABLED",
                        "family": "sectoral",
                        "display_order": 5,
                        "enabled": False,
                    },
                ]
            }
        ),
        encoding="utf-8",
    )


class TestIndexIntelligence:
    """IX-1 configured index observations stay deterministic and honest."""

    def test_returns_configured_order_and_real_availability(
        self, tmp_path: Path
    ) -> None:
        _write_index_intelligence_config(tmp_path)
        repo = SqliteRepository(tmp_path / "indices.db")
        repo.initialize()
        prior = datetime(2026, 7, 30, 10, 0, tzinfo=timezone.utc)
        current = datetime(2026, 7, 31, 6, 30, tzinfo=timezone.utc)
        _register_index_instrument(repo, "NSE:NIFTY 50")
        repo.add_candles([_index_candle("NSE:NIFTY 50", prior, "24000")])
        repo.add_snapshot(
            MarketSnapshot(
                ts=current,
                indices={
                    "NIFTY 50": Decimal("24240"),
                    "NIFTY IT": Decimal("35500"),
                },
                breadth_advances=0,
                breadth_declines=0,
            )
        )
        service = MarketHistoryService(
            InMemoryCandleHistoryProvider(),
            freshness_threshold_minutes=20,
            config_dir=tmp_path,
            repo=repo,
        )

        result = service.index_intelligence()

        assert [item.key for item in result.indices] == ["nifty_50", "nifty_it"]
        assert result.count == 2
        assert result.available_count == 2
        assert result.indices[0].change_pct == Decimal("1.00")
        assert result.indices[1].change_pct is None
        assert result.indices[1].data_status == "AVAILABLE"
        assert result.as_of == current
        assert result.source == "persisted_market_snapshot"
        repo.close()

    def test_no_snapshot_keeps_catalog_but_reports_no_data(
        self, tmp_path: Path
    ) -> None:
        _write_index_intelligence_config(tmp_path)
        service = MarketHistoryService(
            InMemoryCandleHistoryProvider(),
            freshness_threshold_minutes=20,
            config_dir=tmp_path,
        )

        result = service.index_intelligence()

        assert result.count == 2
        assert result.available_count == 0
        assert all(item.data_status == "NO_DATA" for item in result.indices)
        assert all(item.level is None for item in result.indices)
        assert result.as_of is None

    def test_endpoint_requires_auth_and_exposes_stable_shape(
        self, client: TestClient
    ) -> None:
        assert client.get("/api/v1/market/index-intelligence").status_code == 401

        response = client.get(
            "/api/v1/market/index-intelligence",
            headers=get_auth_headers(client, Role.READONLY),
        )

        assert response.status_code == 200
        data = response.json()["data"]
        assert data["count"] == 12
        assert data["source"] == "persisted_market_snapshot"
        assert set(data["indices"][0]) == {
            "key",
            "label",
            "instrument_id",
            "family",
            "level",
            "change_pct",
            "data_status",
        }

    def test_production_catalog_matches_kite_snapshot_coverage(self) -> None:
        config_dir = Path(__file__).resolve().parents[3] / "config"
        catalog = load_index_intelligence_config(config_dir)
        kite = load_kite_provider_config(config_dir)

        enabled_ids = {
            item.instrument_id for item in catalog.tracked_indices if item.enabled
        }
        assert set(kite.index_instruments) <= enabled_ids

    def test_duplicate_catalog_identity_fails_loudly(self, tmp_path: Path) -> None:
        (tmp_path / "index_intelligence.json").write_text(
            json.dumps(
                {
                    "tracked_indices": [
                        {
                            "key": "one",
                            "label": "ONE",
                            "instrument_id": "NSE:ONE",
                            "family": "sectoral",
                            "display_order": 1,
                        },
                        {
                            "key": "two",
                            "label": "TWO",
                            "instrument_id": "NSE:ONE",
                            "family": "sectoral",
                            "display_order": 2,
                        },
                    ]
                }
            ),
            encoding="utf-8",
        )

        with pytest.raises(ConfigError, match="duplicate tracked index instrument ids"):
            load_index_intelligence_config(tmp_path)


class TestInstrumentQuote:
    """Decisions & Trace header LTP — live preferred, persisted fallback."""

    def test_persisted_quote_used_when_live_unavailable(
        self, tmp_path: Path, monkeypatch
    ) -> None:
        from athena.domain.market import Quote
        from athena.errors import ProviderError

        repo = SqliteRepository(tmp_path / "q.db")
        repo.initialize()
        ts = datetime(2026, 7, 29, 3, 50, tzinfo=timezone.utc)
        _register_index_instrument(repo, "NSE:TEJASNET")
        repo.add_quotes(
            [
                Quote(
                    instrument_id="NSE:TEJASNET",
                    ts=ts,
                    last_price=Decimal("512.35"),
                    volume=1000,
                    source="kite",
                )
            ]
        )

        def _boom(*_a, **_k):
            raise ProviderError("no kite")

        monkeypatch.setattr(
            "athena.api.v1.services.market_history_service.fetch_live_quote",
            _boom,
        )
        service = MarketHistoryService(
            InMemoryCandleHistoryProvider(),
            freshness_threshold_minutes=20,
            repo=repo,
        )
        quote = service.instrument_quote("TEJASNET")
        assert quote.instrument_id == "NSE:TEJASNET"
        assert quote.last_price == Decimal("512.35")
        assert quote.source == "persisted"
        assert quote.change_pct is None
        assert quote.as_of == ts
        repo.close()

    def test_empty_quote_when_no_live_and_no_persisted(self, monkeypatch) -> None:
        from athena.errors import ProviderError

        monkeypatch.setattr(
            "athena.api.v1.services.market_history_service.fetch_live_quote",
            lambda *_a, **_k: (_ for _ in ()).throw(ProviderError("no kite")),
        )
        service = MarketHistoryService(
            InMemoryCandleHistoryProvider(),
            freshness_threshold_minutes=20,
        )
        quote = service.instrument_quote("NSE:MISSING")
        assert quote.last_price is None
        assert quote.source is None
        assert quote.change_pct is None

    def test_live_quote_preferred_over_persisted(
        self, tmp_path: Path, monkeypatch
    ) -> None:
        from athena.domain.market import Quote

        repo = SqliteRepository(tmp_path / "q.db")
        repo.initialize()
        stale_ts = datetime(2026, 7, 28, 10, 0, tzinfo=timezone.utc)
        live_ts = datetime(2026, 7, 29, 3, 50, tzinfo=timezone.utc)
        _register_index_instrument(repo, "NSE:TEJASNET")
        repo.add_quotes(
            [
                Quote(
                    instrument_id="NSE:TEJASNET",
                    ts=stale_ts,
                    last_price=Decimal("500.00"),
                    volume=1,
                    source="kite",
                )
            ]
        )

        def _live(instrument_id: str, *, config_dir):
            return (
                Quote(
                    instrument_id="NSE:TEJASNET",
                    ts=live_ts,
                    last_price=Decimal("512.35"),
                    volume=10,
                    source="kite",
                ),
                Decimal("1.25"),
            )

        monkeypatch.setattr(
            "athena.api.v1.services.market_history_service.fetch_live_quote",
            _live,
        )
        # Clear any prior coalescing cache for this symbol.
        from athena.api.v1.services import market_history_service as mhs

        with mhs._live_quote_lock:
            mhs._live_quote_cache.clear()

        service = MarketHistoryService(
            InMemoryCandleHistoryProvider(),
            freshness_threshold_minutes=20,
            repo=repo,
            config_dir=tmp_path,
        )
        quote = service.instrument_quote("NSE:TEJASNET")
        assert quote.last_price == Decimal("512.35")
        assert quote.change_pct == Decimal("1.25")
        assert quote.source == "kite_live"
        assert quote.as_of == live_ts
        repo.close()

    def test_quote_endpoint_requires_auth(self, client: TestClient) -> None:
        unauthenticated = client.get("/api/v1/market/instruments/NSE:INFY/quote")
        assert unauthenticated.status_code == 401

        headers = get_auth_headers(client, Role.READONLY)
        ok = client.get("/api/v1/market/instruments/NSE:INFY/quote", headers=headers)
        assert ok.status_code == 200
        data = ok.json()["data"]
        assert set(data.keys()) == {
            "instrument_id",
            "last_price",
            "change_pct",
            "as_of",
            "source",
        }
