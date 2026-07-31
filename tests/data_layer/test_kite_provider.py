"""Unit + contract helpers for KiteProvider with a fake transport (no network)."""

from __future__ import annotations

import json
from collections.abc import Mapping, Sequence
from datetime import date, datetime
from decimal import Decimal
from pathlib import Path
from zoneinfo import ZoneInfo

import pytest

from athena.config.models import KiteProviderConfig, ProviderCapabilitiesConfig
from athena.data.providers.factory import build_market_data_provider
from athena.data.providers.kite_provider import KiteProvider
from athena.data.providers.kite_transport import UrllibKiteTransport, _assert_allowed
from athena.domain.enums import Timeframe
from athena.errors import ConfigError, ProviderError

IST = ZoneInfo("Asia/Kolkata")

_INSTRUMENTS_CSV = """\
instrument_token,exchange_token,tradingsymbol,name,last_price,expiry,strike,tick_size,lot_size,instrument_type,segment,exchange
408065,1594,INFY,INFOSYS,0,,,0.05,1,EQ,NSE,NSE
738561,2885,RELIANCE,RELIANCE,0,,,0.05,1,EQ,NSE,NSE
256265,1001,NIFTY 50,NIFTY 50,0,,,0.05,1,INDEX,INDICES,NSE
999001,1002,NIFTY IT,NIFTY IT,0,,,0.05,1,INDEX,INDICES,NSE
264969,1035,INDIA VIX,INDIA VIX,0,,,0.05,1,INDEX,INDICES,NSE
"""

_DAILY = [
    ["2026-02-10T09:15:00+0530", 1000.0, 1010.0, 990.0, 1005.0, 10000],
    ["2026-02-11T09:15:00+0530", 1005.0, 1020.0, 1000.0, 1015.0, 11000],
    ["2026-02-12T09:15:00+0530", 1015.0, 1030.0, 1010.0, 1025.0, 12000],
]

_INTRADAY = [
    ["2026-02-12T09:15:00+0530", 1015.0, 1016.0, 1014.0, 1015.5, 100],
    ["2026-02-12T09:20:00+0530", 1015.5, 1017.0, 1015.0, 1016.0, 120],
]


class FakeKiteTransport:
    """Deterministic in-memory Kite responses."""

    def __init__(self) -> None:
        self.calls: list[tuple[str, object]] = []

    def get_text(self, path: str, params: Mapping[str, str] | Sequence[tuple[str, str]] | None = None) -> str:
        self.calls.append((path, params))
        if path.startswith("/instruments/"):
            return _INSTRUMENTS_CSV
        raise ProviderError(f"unexpected text path {path}")

    def get_json(self, path: str, params: Mapping[str, str] | Sequence[tuple[str, str]] | None = None) -> dict:
        self.calls.append((path, params))
        if path.startswith("/instruments/historical/"):
            interval = path.rsplit("/", 1)[-1]
            candles = _DAILY if interval == "day" else _INTRADAY
            return {"status": "success", "data": {"candles": candles}}
        if path == "/quote":
            data = {
                "NSE:INFY": {
                    "instrument_token": 408065,
                    "timestamp": "2026-02-12 15:30:00",
                    "last_price": 1025.0,
                    "volume": 50000,
                },
                "NSE:RELIANCE": {
                    "instrument_token": 738561,
                    "timestamp": "2026-02-12 15:30:00",
                    "last_price": 2500.0,
                    "volume": 40000,
                },
                "NSE:NIFTY 50": {
                    "instrument_token": 256265,
                    "timestamp": "2026-02-12 15:30:00",
                    "last_price": 22000.0,
                    "volume": 0,
                },
                "NSE:NIFTY IT": {
                    "instrument_token": 999001,
                    "timestamp": "2026-02-12 15:30:00",
                    "last_price": 35500.0,
                    "volume": 0,
                },
                "NSE:INDIA VIX": {
                    "instrument_token": 264969,
                    "timestamp": "2026-02-12 15:30:00",
                    "last_price": 12.5,
                    "volume": 0,
                },
            }
            # Only return requested keys when params present.
            if params:
                keys = [v for k, v in params] if not isinstance(params, Mapping) else list(params.values())
                data = {k: data[k] for k in keys if k in data}
            return {"status": "success", "data": data}
        raise ProviderError(f"unexpected json path {path}")


def _config(**kw) -> KiteProviderConfig:
    base = dict(
        exchange="NSE",
        instrument_types=["EQ"],
        symbols=["INFY", "RELIANCE"],
        index_instruments=["NSE:NIFTY 50"],
        india_vix_instrument="NSE:INDIA VIX",
        base_url="https://api.kite.trade",
        quote_batch_size=500,
        capabilities=ProviderCapabilitiesConfig(
            timeframes=["1d", "5m", "15m"],
            max_history_days=2000,
            supports_quotes=True,
            supports_market_snapshot=True,
        ),
    )
    base.update(kw)
    return KiteProviderConfig(**base)


@pytest.fixture()
def provider() -> KiteProvider:
    return KiteProvider(_config(), FakeKiteTransport())


class TestKiteProviderUnit:
    def test_instruments_use_exchange_symbol_ids(self, provider: KiteProvider):
        ids = {i.instrument_id for i in provider.instruments()}
        assert "NSE:INFY" in ids
        assert "NSE:RELIANCE" in ids
        assert "NSE:NIFTY 50" in ids  # snapshot index always included

    def test_instruments_capture_real_company_name_from_kite_dump(self, provider: KiteProvider):
        """Kite's instrument dump already carries a `name` column — ingestion
        previously discarded it entirely. Confirms it's now captured, not
        just present in the fixture."""
        by_id = {i.instrument_id: i for i in provider.instruments()}
        assert by_id["NSE:INFY"].name == "INFOSYS"
        assert by_id["NSE:RELIANCE"].name == "RELIANCE"

    def test_daily_candles_sorted(self, provider: KiteProvider):
        candles = provider.daily_candles("NSE:INFY", date(2026, 2, 10), date(2026, 2, 12))
        assert len(candles) == 3
        assert [c.ts_open for c in candles] == sorted(c.ts_open for c in candles)
        assert candles[0].close == Decimal("1005.0")
        assert candles[0].source == "kite"

    def test_unknown_instrument_fails(self, provider: KiteProvider):
        with pytest.raises(ProviderError, match=r"NO-SUCH"):
            provider.daily_candles("NO-SUCH", date(2026, 2, 10), date(2026, 2, 12))

    def test_unsupported_timeframe_fails(self, provider: KiteProvider):
        start = datetime(2026, 2, 12, 9, 15, tzinfo=IST)
        end = datetime(2026, 2, 12, 15, 30, tzinfo=IST)
        with pytest.raises(ProviderError, match=r"1m"):
            provider.intraday_candles("NSE:INFY", Timeframe.M1, start, end)

    def test_quotes_and_snapshot(self, provider: KiteProvider):
        quotes = provider.quotes(["NSE:INFY"])
        assert len(quotes) == 1
        assert quotes[0].last_price == Decimal("1025.0")
        snap = provider.market_snapshot()
        assert "NIFTY 50" in snap.indices
        assert snap.india_vix == Decimal("12.5")
        assert snap.breadth_advances == 0

    def test_snapshot_indices_do_not_expand_benchmark_history_set(self):
        transport = FakeKiteTransport()
        config = _config(
            index_instruments=["NSE:NIFTY 50"],
        )
        provider = KiteProvider(
            config,
            transport,
            snapshot_index_instruments=["NSE:NIFTY 50", "NSE:NIFTY IT"],
        )

        ids = {item.instrument_id for item in provider.instruments()}
        snapshot = provider.market_snapshot()

        assert config.index_instruments == ["NSE:NIFTY 50"]
        assert "NSE:NIFTY IT" in ids
        assert snapshot.indices == {
            "NIFTY 50": Decimal("22000.0"),
            "NIFTY IT": Decimal("35500.0"),
        }
        quote_call = next(call for call in transport.calls if call[0] == "/quote")
        assert quote_call[1] == [
            ("i", "NSE:NIFTY 50"),
            ("i", "NSE:NIFTY IT"),
            ("i", "NSE:INDIA VIX"),
        ]

    def test_from_config_dir_loads_snapshot_catalog_separately(self):
        config_dir = Path(__file__).resolve().parents[2] / "config"
        transport = FakeKiteTransport()
        provider = KiteProvider.from_config_dir(
            config_dir,
            transport=transport,
            symbols=["INFY"],
        )

        snapshot = provider.market_snapshot()
        quote_call = next(call for call in transport.calls if call[0] == "/quote")
        requested = [value for key, value in quote_call[1] if key == "i"]

        assert "NIFTY 50" in snapshot.indices
        assert "NIFTY IT" in snapshot.indices
        assert "NSE:NIFTY MIDCAP 100" in requested
        assert "NSE:NIFTY PSU BANK" in requested
        assert requested[-1] == "NSE:INDIA VIX"

    def test_health_ok(self, provider: KiteProvider):
        health = provider.health()
        assert health.status.value == "OK"
        assert "kite" in health.detail.lower()

    def test_missing_symbol_in_universe_fails(self):
        transport = FakeKiteTransport()
        prov = KiteProvider(_config(symbols=["INFY", "NOTREAL"]), transport)
        with pytest.raises(ProviderError, match=r"NOTREAL"):
            prov.instruments()

    def test_non_strict_filter_keeps_resolvable_symbols(self):
        """Owner candidate lists are data, not configuration: one typo'd symbol
        must not abort a whole cycle. Callers passing a scope resolve and report
        the misses themselves, so the provider returns what the exchange lists."""
        prov = KiteProvider(
            _config(symbols=["INFY", "NOTREAL"]),
            FakeKiteTransport(),
            strict_symbol_filter=False,
        )
        ids = {i.instrument_id for i in prov.instruments()}
        assert "NSE:INFY" in ids
        assert not any("NOTREAL" in i for i in ids)

    def test_non_strict_filter_returns_no_equity_when_nothing_resolves(self):
        """Nothing to trade is not the provider's call to make: it returns the
        snapshot indices only, and the caller that supplied the scope raises."""
        prov = KiteProvider(
            _config(symbols=["NOTREAL"]),
            FakeKiteTransport(),
            strict_symbol_filter=False,
        )
        assert [i.instrument_id for i in prov.instruments() if i.series == "EQ"] == []

    def test_transport_refuses_order_paths(self):
        with pytest.raises(ProviderError, match=r"refused path"):
            _assert_allowed("/orders")
        with pytest.raises(ProviderError, match=r"refused path"):
            _assert_allowed("/portfolio/positions")

    def test_urllib_transport_requires_secrets(self):
        with pytest.raises(ProviderError, match=r"KITE_API_KEY"):
            UrllibKiteTransport(base_url="https://api.kite.trade", api_key="", access_token="x")
        with pytest.raises(ProviderError, match=r"KITE_ACCESS_TOKEN"):
            UrllibKiteTransport(base_url="https://api.kite.trade", api_key="k", access_token="")

    def test_endpoint_class_buckets(self):
        from athena.data.providers.kite_transport import endpoint_class

        assert endpoint_class("/quote") == "quote"
        assert endpoint_class("/instruments/historical/408065/day") == "historical"
        assert endpoint_class("/instruments/NSE") == "other"

    def test_pacing_waits_between_same_class_requests(self, monkeypatch: pytest.MonkeyPatch):
        """Quote class is 1 req/s: a second quote before the interval must sleep."""
        from athena.config.models import KiteRateLimitConfig
        from athena.data.providers.kite_transport import UrllibKiteTransport

        sleeps: list[float] = []
        clock = {"t": 100.0}

        def fake_sleep(seconds: float) -> None:
            sleeps.append(seconds)
            clock["t"] += seconds

        class _Resp:
            def __enter__(self):
                return self

            def __exit__(self, *args):
                return False

            def read(self) -> bytes:
                return b'{"status":"success","data":{}}'

        monkeypatch.setattr(
            "urllib.request.urlopen", lambda *a, **k: _Resp()
        )
        transport = UrllibKiteTransport(
            base_url="https://api.kite.trade",
            api_key="k",
            access_token="t",
            rate_limit=KiteRateLimitConfig(
                quote_min_interval_seconds=1.0,
                historical_min_interval_seconds=0.334,
                other_min_interval_seconds=0.1,
                max_429_retries=0,
            ),
            sleep=fake_sleep,
            clock=lambda: clock["t"],
        )
        transport.get_json("/quote")
        clock["t"] += 0.2  # only 0.2s later — must wait ~0.8s
        transport.get_json("/quote")
        assert sleeps and sleeps[0] == pytest.approx(0.8, abs=0.01)

    def test_429_retries_then_fails_loudly(self, monkeypatch: pytest.MonkeyPatch):
        import urllib.error

        from athena.config.models import KiteRateLimitConfig
        from athena.data.providers.kite_transport import UrllibKiteTransport

        attempts = {"n": 0}
        sleeps: list[float] = []
        clock = {"t": 0.0}

        class _Body:
            def read(self) -> bytes:
                return b"rate limited"

            def close(self) -> None:
                return None

        def fake_open_with_body(*_a, **_k):
            attempts["n"] += 1
            raise urllib.error.HTTPError(
                url="https://api.kite.trade/quote",
                code=429,
                msg="Too Many Requests",
                hdrs=None,  # type: ignore[arg-type]
                fp=_Body(),  # type: ignore[arg-type]
            )

        def fake_sleep(seconds: float) -> None:
            sleeps.append(seconds)
            clock["t"] += seconds

        monkeypatch.setattr("urllib.request.urlopen", fake_open_with_body)
        transport = UrllibKiteTransport(
            base_url="https://api.kite.trade",
            api_key="k",
            access_token="t",
            rate_limit=KiteRateLimitConfig(
                quote_min_interval_seconds=0.001,
                historical_min_interval_seconds=0.001,
                other_min_interval_seconds=0.001,
                max_429_retries=2,
                retry_backoff_base_seconds=0.5,
            ),
            sleep=fake_sleep,
            clock=lambda: clock["t"],
        )
        with pytest.raises(ProviderError, match=r"kite HTTP 429"):
            transport.get_json("/quote")
        # 1 initial + 2 retries = 3 attempts; backoff 0.5 then 1.0 (pace sleeps
        # are ~0.001 and ignored here by filtering)
        assert attempts["n"] == 3
        backoffs = [s for s in sleeps if s >= 0.4]
        assert backoffs == [pytest.approx(0.5), pytest.approx(1.0)]

    def test_factory_selects_kite(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
        config_dir = tmp_path / "config"
        (config_dir / "providers").mkdir(parents=True)
        (config_dir / "providers" / "kite.json").write_text(
            json.dumps({
                "exchange": "NSE",
                "instrument_types": ["EQ"],
                "symbols": ["INFY"],
                "index_instruments": ["NSE:NIFTY 50"],
                "india_vix_instrument": "NSE:INDIA VIX",
                "capabilities": {
                    "timeframes": ["1d", "5m"],
                    "max_history_days": 365,
                    "supports_quotes": True,
                    "supports_market_snapshot": True,
                },
            }),
            encoding="utf-8",
        )
        (config_dir / "ingestion.json").write_text(
            json.dumps({"provider": "kite", "timeframes": ["5m"]}),
            encoding="utf-8",
        )
        monkeypatch.setenv("KITE_API_KEY", "key")
        monkeypatch.setenv("KITE_ACCESS_TOKEN", "token")
        # Factory builds real Urllib transport; swap by constructing provider with fake.
        built = build_market_data_provider(config_dir, provider_name="kite")
        assert built.name == "kite"

    def test_factory_rejects_unknown(self, tmp_path: Path):
        with pytest.raises(ConfigError, match=r"not supported"):
            build_market_data_provider(tmp_path, provider_name="upstox")
