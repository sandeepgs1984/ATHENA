"""FileProvider unit tests (M1.2): every load path, error path, and config path."""

from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from pathlib import Path
from zoneinfo import ZoneInfo

import pytest

from athena.config.loader import load_file_provider_config
from athena.config.models import FileProviderConfig, ProviderCapabilitiesConfig
from athena.data.providers.file_provider import FileProvider
from athena.domain.enums import Timeframe
from athena.errors import ConfigError, ProviderError

DATA = Path(__file__).resolve().parents[1] / "data"
SYNTHETIC = DATA / "fileprovider"
SAMPLE = DATA / "fileprovider_sample"
IST = ZoneInfo("Asia/Kolkata")


def _caps(**kw) -> ProviderCapabilitiesConfig:
    base = dict(timeframes=["1d", "5m"], max_history_days=365,
                supports_quotes=True, supports_market_snapshot=True)
    base.update(kw)
    return ProviderCapabilitiesConfig(**base)


def _config(**kw) -> FileProviderConfig:
    caps = kw.pop("capabilities", _caps())
    base = dict(data_root="unused", instruments_file="instruments.csv", daily_dir="daily",
                intraday_dir="intraday", quotes_file="quotes.csv", snapshot_file="snapshot.json",
                capabilities=caps)
    base.update(kw)
    return FileProviderConfig(**base)


@pytest.fixture()
def provider() -> FileProvider:
    return FileProvider(_config(), SYNTHETIC)


@pytest.fixture()
def sample_provider() -> FileProvider:
    return FileProvider(_config(), SAMPLE)


class TestLoading:
    def test_daily_loading_preserves_decimal_and_tz(self, provider):
        candles = provider.daily_candles("SYN-AAA", date(2026, 2, 2), date(2026, 2, 13))
        assert len(candles) == 10
        first = candles[0]
        assert first.open == Decimal("100.00")
        assert isinstance(first.open, Decimal)
        assert first.ts_open.utcoffset().total_seconds() == 5.5 * 3600

    def test_daily_range_is_inclusive_and_filters(self, provider):
        subset = provider.daily_candles("SYN-AAA", date(2026, 2, 3), date(2026, 2, 5))
        assert all(date(2026, 2, 3) <= c.ts_open.date() <= date(2026, 2, 5) for c in subset)
        assert len(subset) == 3

    def test_intraday_loading(self, provider):
        start = datetime(2026, 2, 2, 9, 15, tzinfo=IST)
        end = datetime(2026, 2, 2, 15, 30, tzinfo=IST)
        candles = provider.intraday_candles("SYN-AAA", Timeframe.M5, start, end)
        assert len(candles) == 6
        assert all(c.timeframe is Timeframe.M5 for c in candles)

    def test_instrument_lookup(self, provider):
        instruments = {i.instrument_id: i for i in provider.instruments()}
        assert set(instruments) == {"SYN-AAA", "SYN-BBB"}
        assert instruments["SYN-AAA"].tick_size == Decimal("0.05")
        assert instruments["SYN-BBB"].listed_date == date(2021, 6, 15)

    def test_quote_retrieval_at_most_one_per_id(self, provider):
        quotes = provider.quotes(["SYN-AAA", "SYN-BBB"])
        assert {q.instrument_id for q in quotes} == {"SYN-AAA", "SYN-BBB"}
        assert next(q for q in quotes if q.instrument_id == "SYN-AAA").last_price == Decimal("109.50")

    def test_market_snapshot(self, provider):
        snap = provider.market_snapshot()
        assert snap.indices["NIFTY50"] == Decimal("25000.50")
        assert snap.india_vix == Decimal("14.5")

    def test_health_reports_last_snapshot_ts(self, provider):
        health = provider.health()
        assert health.last_data_ts == datetime(2026, 2, 13, 15, 30, tzinfo=IST)


class TestRealisticSample:
    def test_real_symbols_and_multi_index_snapshot(self, sample_provider):
        instruments = {i.symbol: i for i in sample_provider.instruments()}
        assert {"RELIANCE", "TCS"} <= set(instruments)
        assert instruments["RELIANCE"].instrument_id == "INE002A01018"
        snap = sample_provider.market_snapshot()
        assert set(snap.indices) == {"NIFTY50", "BANKNIFTY"}

    def test_deterministic_across_reads(self, sample_provider):
        a = sample_provider.daily_candles("INE002A01018", date(2026, 1, 1), date(2026, 1, 2))
        b = sample_provider.daily_candles("INE002A01018", date(2026, 1, 1), date(2026, 1, 2))
        assert a == b


class TestEmptyAndMissing:
    def test_known_instrument_without_timeframe_file_is_empty(self, provider):
        start = datetime(2026, 2, 2, 9, 15, tzinfo=IST)
        end = datetime(2026, 2, 2, 15, 30, tzinfo=IST)
        # SYN-BBB has no intraday file → empty, not an error
        assert provider.intraday_candles("SYN-BBB", Timeframe.M5, start, end) == []

    def test_missing_instruments_file_fails_loudly(self, tmp_path):
        prov = FileProvider(_config(), tmp_path)
        with pytest.raises(ProviderError, match=r"missing file"):
            prov.instruments()

    def test_missing_quotes_file_fails_loudly(self, tmp_path):
        (tmp_path / "instruments.csv").write_text(
            "instrument_id,symbol,exchange,series,isin,lot_size,tick_size,status,listed_date,delisted_date\n"
            "X,X,NSE,EQ,,1,0.05,ACTIVE,,\n", encoding="utf-8")
        prov = FileProvider(_config(), tmp_path)
        with pytest.raises(ProviderError, match=r"missing quotes file"):
            prov.quotes(["X"])


class TestErrorHandling:
    def test_unknown_instrument(self, provider):
        with pytest.raises(ProviderError, match=r"unknown instrument id: ZZZ"):
            provider.daily_candles("ZZZ", date(2026, 2, 2), date(2026, 2, 13))

    def test_unsupported_timeframe(self, provider):
        start = datetime(2026, 2, 2, 9, 15, tzinfo=IST)
        end = datetime(2026, 2, 2, 15, 30, tzinfo=IST)
        with pytest.raises(ProviderError, match=r"15m not supported"):
            provider.intraday_candles("SYN-AAA", Timeframe.M15, start, end)

    def test_unsupported_quote_capability(self, tmp_path):
        prov = FileProvider(_config(capabilities=_caps(supports_quotes=False)), SYNTHETIC)
        with pytest.raises(ProviderError, match=r"does not support quotes"):
            prov.quotes(["SYN-AAA"])

    def test_unsupported_snapshot_capability(self):
        prov = FileProvider(_config(capabilities=_caps(supports_market_snapshot=False)), SYNTHETIC)
        with pytest.raises(ProviderError, match=r"does not support market snapshot"):
            prov.market_snapshot()

    def test_corrupted_price_fails_loudly(self, tmp_path):
        _seed_instrument(tmp_path)
        (tmp_path / "daily").mkdir()
        (tmp_path / "daily" / "X.csv").write_text(
            "ts_open,open,high,low,close,volume\n"
            "2026-02-02T09:15:00+05:30,not_a_number,101,99,100,1000\n", encoding="utf-8")
        prov = FileProvider(_config(), tmp_path)
        with pytest.raises(ProviderError, match=r"corrupted data.*not a valid open"):
            prov.daily_candles("X", date(2026, 2, 1), date(2026, 2, 28))

    def test_impossible_ohlc_is_corrupted(self, tmp_path):
        _seed_instrument(tmp_path)
        (tmp_path / "daily").mkdir()
        (tmp_path / "daily" / "X.csv").write_text(
            "ts_open,open,high,low,close,volume\n"
            "2026-02-02T09:15:00+05:30,100,98,99,100,1000\n", encoding="utf-8")  # high<low
        prov = FileProvider(_config(), tmp_path)
        with pytest.raises(ProviderError, match=r"corrupted candle.*Impossible OHLC"):
            prov.daily_candles("X", date(2026, 2, 1), date(2026, 2, 28))

    def test_naive_timestamp_is_corrupted(self, tmp_path):
        _seed_instrument(tmp_path)
        (tmp_path / "daily").mkdir()
        (tmp_path / "daily" / "X.csv").write_text(
            "ts_open,open,high,low,close,volume\n"
            "2026-02-02T09:15:00,100,101,99,100,1000\n", encoding="utf-8")  # no tz
        prov = FileProvider(_config(), tmp_path)
        with pytest.raises(ProviderError, match=r"lacks a timezone"):
            prov.daily_candles("X", date(2026, 2, 1), date(2026, 2, 28))

    def test_duplicate_timestamp_is_rejected(self, tmp_path):
        _seed_instrument(tmp_path)
        (tmp_path / "daily").mkdir()
        (tmp_path / "daily" / "X.csv").write_text(
            "ts_open,open,high,low,close,volume\n"
            "2026-02-02T09:15:00+05:30,100,101,99,100,1000\n"
            "2026-02-02T09:15:00+05:30,100,101,99,100,1000\n", encoding="utf-8")
        prov = FileProvider(_config(), tmp_path)
        with pytest.raises(ProviderError, match=r"duplicate candle timestamp"):
            prov.daily_candles("X", date(2026, 2, 1), date(2026, 2, 28))

    def test_wrong_header_is_invalid_format(self, tmp_path):
        _seed_instrument(tmp_path)
        (tmp_path / "daily").mkdir()
        (tmp_path / "daily" / "X.csv").write_text(
            "date,open,high,low,close,volume\n", encoding="utf-8")  # wrong first column
        prov = FileProvider(_config(), tmp_path)
        with pytest.raises(ProviderError, match=r"invalid file format.*expected first column 'ts_open'"):
            prov.daily_candles("X", date(2026, 2, 1), date(2026, 2, 28))

    def test_invalid_snapshot_json(self, tmp_path):
        _seed_instrument(tmp_path)
        (tmp_path / "snapshot.json").write_text("{not valid json", encoding="utf-8")
        prov = FileProvider(_config(), tmp_path)
        with pytest.raises(ProviderError, match=r"invalid JSON in snapshot"):
            prov.market_snapshot()


class TestConfiguration:
    def test_loads_from_production_config(self):
        config = load_file_provider_config(Path(__file__).resolve().parents[2] / "config")
        assert config.data_root == "data"
        assert "1d" in config.capabilities.timeframes

    def test_missing_provider_config_fails(self, tmp_path):
        with pytest.raises(ConfigError, match=r"Missing configuration file.*file.json"):
            load_file_provider_config(tmp_path)

    def test_from_config_dir_resolves_data_root(self, tmp_path):
        cfg_dir = tmp_path / "config" / "providers"
        cfg_dir.mkdir(parents=True)
        (tmp_path / "config" / "providers" / "file.json").write_text(
            '{"data_root":"data","instruments_file":"instruments.csv","daily_dir":"daily",'
            '"intraday_dir":"intraday","quotes_file":"quotes.csv","snapshot_file":"snapshot.json",'
            '"capabilities":{"timeframes":["1d"],"max_history_days":30,'
            '"supports_quotes":false,"supports_market_snapshot":false}}', encoding="utf-8")
        prov = FileProvider.from_config_dir(tmp_path / "config")
        assert prov.name == "file"
        assert not prov.capabilities().supports_quotes


def _seed_instrument(root: Path) -> None:
    root.mkdir(parents=True, exist_ok=True)
    (root / "instruments.csv").write_text(
        "instrument_id,symbol,exchange,series,isin,lot_size,tick_size,status,listed_date,delisted_date\n"
        "X,X,NSE,EQ,,1,0.05,ACTIVE,,\n", encoding="utf-8")
