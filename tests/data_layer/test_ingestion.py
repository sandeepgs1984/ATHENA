"""Live ingestion cycle tests (M10.1): FileProvider → validate → SQLite."""

from __future__ import annotations

from datetime import date, datetime, timedelta
from decimal import Decimal
from pathlib import Path
from zoneinfo import ZoneInfo

import pytest

from athena.calendar.engine import CalendarEngine
from athena.config.loader import load_config, load_ingestion_config, load_validation_config
from athena.config.models import (
    FileProviderConfig,
    GapConfig,
    IngestionConfig,
    ProviderCapabilitiesConfig,
    ValidationConfig,
)
from athena.data.ingestion import LiveIngestionEngine, build_ingest_validator
from athena.data.providers.file_provider import FileProvider
from athena.data.store import SqliteRepository
from athena.data.validation import QuarantineRegistry, validate_quotes
from athena.domain.enums import Timeframe
from athena.domain.market import MarketSnapshot, Quote
from athena.errors import ConfigError, DataStaleError

IST = ZoneInfo("Asia/Kolkata")
AS_OF = datetime(2026, 2, 13, 15, 35, tzinfo=IST)


def _caps() -> ProviderCapabilitiesConfig:
    return ProviderCapabilitiesConfig(
        timeframes=["1d", "5m"], max_history_days=365,
        supports_quotes=True, supports_market_snapshot=True,
    )


def _write_provider_tree(root: Path, *, quote_ts: str = "2026-02-13T15:30:00+05:30") -> FileProvider:
    root.mkdir(parents=True, exist_ok=True)
    (root / "daily").mkdir()
    (root / "intraday" / "5m").mkdir(parents=True)
    (root / "instruments.csv").write_text(
        "instrument_id,symbol,exchange,series,isin,lot_size,tick_size,status,listed_date,delisted_date\n"
        "SYN-AAA,AAA,NSE,EQ,,1,0.05,ACTIVE,,\n",
        encoding="utf-8",
    )
    (root / "daily" / "SYN-AAA.csv").write_text(
        "ts_open,open,high,low,close,volume\n"
        "2026-02-11T09:15:00+05:30,107.00,109.00,106.00,108.00,1000\n"
        "2026-02-12T09:15:00+05:30,108.00,110.00,107.00,109.00,1000\n"
        "2026-02-13T09:15:00+05:30,109.00,111.00,108.00,110.00,1000\n",
        encoding="utf-8",
    )
    (root / "intraday" / "5m" / "SYN-AAA.csv").write_text(
        "ts_open,open,high,low,close,volume\n"
        "2026-02-13T15:20:00+05:30,109.00,109.50,108.80,109.20,100\n"
        "2026-02-13T15:25:00+05:30,109.20,109.60,109.00,109.40,100\n"
        "2026-02-13T15:30:00+05:30,109.40,109.80,109.20,109.50,100\n",
        encoding="utf-8",
    )
    (root / "quotes.csv").write_text(
        "instrument_id,ts,last_price,volume\n"
        f"SYN-AAA,{quote_ts},109.50,42000\n",
        encoding="utf-8",
    )
    (root / "snapshot.json").write_text(
        '{"ts":"2026-02-13T15:30:00+05:30","indices":{"NIFTY50":25000},"breadth_advances":1,'
        '"breadth_declines":0,"india_vix":14.5}',
        encoding="utf-8",
    )
    cfg = FileProviderConfig(
        data_root=str(root), instruments_file="instruments.csv", daily_dir="daily",
        intraday_dir="intraday", quotes_file="quotes.csv", snapshot_file="snapshot.json",
        capabilities=_caps(),
    )
    return FileProvider(cfg, root)


def _engine(tmp_path: Path, config_dir: Path, provider: FileProvider,
            ingest: IngestionConfig | None = None) -> tuple[LiveIngestionEngine, SqliteRepository]:
    base = load_config(config_dir)
    calendar = CalendarEngine.from_config_dir(config_dir, base.market)
    vcfg = load_validation_config(config_dir)
    ingest = ingest or IngestionConfig(
        provider="file", timeframes=["5m"], lookback_minutes=30, lookback_days=5,
        include_daily=True, include_quotes=True, validate_gaps=False, skip_existing=True,
        quarantine_on_failure=True, instrument_ids=["SYN-AAA"],
    )
    validator = build_ingest_validator(calendar, vcfg, ingest, IST)
    repo = SqliteRepository(tmp_path / "athena.db")
    repo.initialize()
    engine = LiveIngestionEngine(
        provider, repo, validator, QuarantineRegistry(), ingest, vcfg, tzinfo=IST,
    )
    return engine, repo


class TestHappyPath:
    def test_poll_validate_persist(self, tmp_path, config_dir):
        provider = _write_provider_tree(tmp_path / "data")
        engine, repo = _engine(tmp_path, config_dir, provider)
        result = engine.run_cycle(as_of=AS_OF)
        assert result.instruments_upserted == 1
        assert result.candles_written >= 3  # daily + intraday in lookback
        assert result.quotes_written == 1
        assert result.datasets_validated >= 2
        assert repo.get_instrument("SYN-AAA") is not None
        dailies = repo.get_candles(
            "SYN-AAA", Timeframe.D1,
            datetime(2026, 2, 11, tzinfo=IST), datetime(2026, 2, 13, 23, 59, tzinfo=IST),
        )
        assert len(dailies) == 3
        quotes = repo.get_quotes("SYN-AAA")
        assert len(quotes) == 1
        assert quotes[0].last_price == Decimal("109.50")
        snap = repo.get_latest_snapshot()
        assert snap is not None
        assert snap.india_vix == Decimal("14.5")
        assert result.snapshots_written == 1

    def test_reingest_skips_existing(self, tmp_path, config_dir):
        provider = _write_provider_tree(tmp_path / "data")
        engine, repo = _engine(tmp_path, config_dir, provider)
        first = engine.run_cycle(as_of=AS_OF)
        second = engine.run_cycle(as_of=AS_OF)
        assert first.candles_written > 0
        # Closed prior days (2026-02-11, -12) are still skip-if-present, but
        # AS_OF's own date (2026-02-13) is the still-forming trading day —
        # its daily candle is always re-written (owner-reported, 2026-08-04:
        # skipping it froze that day's candle at whatever partial value the
        # first ingest of the day captured, never correcting to the real
        # close) — so exactly the one "today" daily candle is rewritten here.
        assert second.candles_written == 1
        assert second.quotes_written == 0
        assert len(repo.get_quotes("SYN-AAA")) == 1

    def test_reingest_after_later_snapshot_does_not_raise(self, tmp_path, config_dir):
        """Owner-reported (2026-08-10): the old guard skipped re-ingesting a
        snapshot only when it exactly matched the single most-recent one —
        so once ANY later snapshot existed (always true on a second
        after-hours validate, since every after-hours as_of is the same
        frozen session close — see resolve_validate_as_of), re-ingesting the
        original as_of's snapshot raised UNIQUE constraint failed on
        market_snapshots.ts instead of being silently skipped."""
        provider = _write_provider_tree(tmp_path / "data")
        engine, repo = _engine(tmp_path, config_dir, provider)
        engine.run_cycle(as_of=AS_OF)

        repo.add_snapshot(
            MarketSnapshot(ts=AS_OF + timedelta(hours=1), indices={"NIFTY50": Decimal("25010")})
        )

        second = engine.run_cycle(as_of=AS_OF)  # must not raise
        assert second.snapshots_written == 1
        snap = repo.get_latest_snapshot()
        assert snap is not None
        assert snap.ts == AS_OF + timedelta(hours=1)


class TestFailures:
    def test_stale_quotes_quarantined_not_raised(self, tmp_path, config_dir):
        # Owner-reported (2026-08-04): one stale/invalid dataset used to
        # abort the whole cycle, discarding every other instrument's already-
        # fetched, already-valid data too. Under the default
        # quarantine_on_failure=True, the cycle now succeeds — the offending
        # dataset is quarantined and skipped, visibly, rather than raised.
        provider = _write_provider_tree(
            tmp_path / "data", quote_ts="2026-02-13T14:00:00+05:30",
        )
        engine, repo = _engine(tmp_path, config_dir, provider)
        result = engine.run_cycle(as_of=AS_OF)
        assert repo.get_quarantine("quotes") is not None
        assert repo.get_quotes("SYN-AAA") == []
        assert result.datasets_quarantined == 1
        assert result.quarantined_dataset_ids == ("quotes",)
        # The rest of the cycle was not discarded because of the bad quotes.
        assert result.candles_written > 0

    def test_stale_quotes_raises_in_strict_mode(self, tmp_path, config_dir):
        provider = _write_provider_tree(
            tmp_path / "data", quote_ts="2026-02-13T14:00:00+05:30",
        )
        ingest = IngestionConfig(
            provider="file", timeframes=["5m"], lookback_minutes=30, lookback_days=5,
            include_daily=True, include_quotes=True, validate_gaps=False,
            skip_existing=True, quarantine_on_failure=False, instrument_ids=["SYN-AAA"],
        )
        engine, repo = _engine(tmp_path, config_dir, provider, ingest=ingest)
        with pytest.raises(DataStaleError, match=r"quotes"):
            engine.run_cycle(as_of=AS_OF)
        assert repo.get_quotes("SYN-AAA") == []

    def test_stale_intraday_quarantined_not_raised(self, tmp_path, config_dir):
        provider = _write_provider_tree(tmp_path / "data")
        # Move as_of far past last bar; disable quotes so candle freshness is the fail path.
        ingest = IngestionConfig(
            provider="file", timeframes=["5m"], lookback_minutes=120, lookback_days=5,
            include_daily=False, include_quotes=False, validate_gaps=False,
            skip_existing=True, quarantine_on_failure=True, instrument_ids=["SYN-AAA"],
        )
        engine, repo = _engine(tmp_path, config_dir, provider, ingest=ingest)
        stale_as_of = datetime(2026, 2, 13, 16, 30, tzinfo=IST)
        result = engine.run_cycle(as_of=stale_as_of)
        assert repo.record_counts()["candles"] == 0
        assert result.datasets_quarantined == 1
        assert result.quarantined_dataset_ids == ("SYN-AAA:5m",)

    def test_stale_intraday_raises_in_strict_mode(self, tmp_path, config_dir):
        provider = _write_provider_tree(tmp_path / "data")
        ingest = IngestionConfig(
            provider="file", timeframes=["5m"], lookback_minutes=120, lookback_days=5,
            include_daily=False, include_quotes=False, validate_gaps=False,
            skip_existing=True, quarantine_on_failure=False, instrument_ids=["SYN-AAA"],
        )
        engine, repo = _engine(tmp_path, config_dir, provider, ingest=ingest)
        stale_as_of = datetime(2026, 2, 13, 16, 30, tzinfo=IST)
        with pytest.raises(DataStaleError, match=r"5m"):
            engine.run_cycle(as_of=stale_as_of)
        assert repo.record_counts()["candles"] == 0


class TestQuoteValidator:
    def test_non_positive_fails(self):
        q = Quote(
            instrument_id="X", ts=AS_OF, last_price=Decimal("0"), volume=1, source="t",
        )
        summary = validate_quotes([q], as_of=AS_OF, max_minutes_behind=20)
        assert not summary.passed

    def test_fresh_passes(self):
        q = Quote(
            instrument_id="X", ts=AS_OF - timedelta(minutes=5),
            last_price=Decimal("10"), volume=1, source="t",
        )
        summary = validate_quotes([q], as_of=AS_OF, max_minutes_behind=20)
        assert summary.passed


class TestConfig:
    def test_loads_production_ingestion_config(self, config_dir):
        cfg = load_ingestion_config(config_dir)
        assert cfg.provider in {"file", "kite"}
        assert "5m" in cfg.timeframes
        assert cfg.validate_gaps is False

    def test_missing_ingestion_config_fails(self, tmp_path):
        with pytest.raises(ConfigError, match=r"ingestion.json"):
            load_ingestion_config(tmp_path)

    def test_build_validator_disables_gaps(self, config_dir):
        base = load_config(config_dir)
        calendar = CalendarEngine.from_config_dir(config_dir, base.market)
        vcfg = ValidationConfig(
            freshness=load_validation_config(config_dir).freshness,
            gaps=GapConfig(daily_enabled=True, intraday_enabled=True),
        )
        ingest = IngestionConfig(validate_gaps=False)
        validator = build_ingest_validator(calendar, vcfg, ingest, IST)
        # Empty candles fail freshness, but gap report must not appear when disabled.
        summary = validator.validate_daily(
            "x:1d", [], start=date(2026, 2, 11), end=date(2026, 2, 13), as_of=AS_OF,
        )
        types = {r.validation_type.value for r in summary.reports}
        assert "GAP" not in types
