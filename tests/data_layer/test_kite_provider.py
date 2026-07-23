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

    def test_health_ok(self, provider: KiteProvider):
        health = provider.health()
        assert health.status.value == "OK"
        assert "kite" in health.detail.lower()

    def test_missing_symbol_in_universe_fails(self):
        transport = FakeKiteTransport()
        prov = KiteProvider(_config(symbols=["INFY", "NOTREAL"]), transport)
        with pytest.raises(ProviderError, match=r"NOTREAL"):
            prov.instruments()

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
