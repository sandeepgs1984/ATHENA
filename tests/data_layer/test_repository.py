"""SqliteRepository tests (M1.5): schema, CRUD, append-only, transactions,
FK enforcement, duplicates, integrity, quarantine, corporate actions, ranges."""

from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from pathlib import Path
from zoneinfo import ZoneInfo

import pytest

from athena.data.store import SqliteRepository
from athena.data.validation.quarantine import QuarantineRecord
from athena.data.validation.reports import (
    Severity,
    ValidationReport,
    ValidationResult,
    ValidationType,
)
from athena.domain.enums import Timeframe
from athena.domain.market import (
    Candle,
    CorporateAction,
    Instrument,
    MarketSnapshot,
    Quote,
)
from athena.errors import RepositoryError

IST = ZoneInfo("Asia/Kolkata")
INST = "INE-REPO-0001"


@pytest.fixture()
def repo(tmp_path: Path) -> SqliteRepository:
    r = SqliteRepository(tmp_path / "athena.db")
    r.initialize()
    yield r
    r.close()


def _instrument(iid: str = INST, symbol: str = "AAA") -> Instrument:
    return Instrument(instrument_id=iid, symbol=symbol, exchange="NSE", series="EQ",
                      isin="INE000A01AAA", lot_size=1, tick_size=Decimal("0.05"),
                      status="ACTIVE", listed_date=date(2020, 1, 1))


def _candle(day: date, tf=Timeframe.D1, close="100") -> Candle:
    c = Decimal(close)
    return Candle(instrument_id=INST, timeframe=tf,
                  ts_open=datetime.combine(day, datetime.min.time(), tzinfo=IST).replace(hour=9, minute=15),
                  open=c, high=c + 1, low=c - 1, close=c, volume=1000, source="test")


class TestSchemaAndConfig:
    def test_wal_mode_enabled(self, repo):
        assert repo.journal_mode == "wal"

    def test_foreign_keys_enabled(self, repo):
        assert repo.foreign_keys_enabled is True

    def test_initialize_is_idempotent(self, repo):
        repo.initialize()  # second call must not error or duplicate schema_version
        assert repo.verify_integrity().schema_version_ok

    def test_runs_started_ts_index_exists(self, repo):
        """Perf fix (2026-08-03): list_runs(limit=N) with no trigger filter
        — used by the dashboard's pipeline-runs list, candidates/validate
        verdict lookups, market summary, diagnostics, notifications, and
        OwnerValidationPipeline._last_full_universe_summary() — had no
        usable index for its `ORDER BY started_ts DESC, run_id DESC`,
        forcing a full table scan that materialized every row's
        (multi-MB, in production) detail_json just to sort and take the
        top N. Confirmed ~80x faster against the real production database
        once this index exists; this locks in that the index is actually
        created, not just present in the source."""
        names = {
            row[0] for row in
            repo._conn.execute(
                "SELECT name FROM sqlite_master WHERE type='index' AND tbl_name='runs'"
            )
        }
        assert "idx_runs_started_ts" in names

    def test_list_runs_without_trigger_filter_avoids_full_table_scan(self, repo):
        plan = [
            row[3] for row in repo._conn.execute(
                "EXPLAIN QUERY PLAN SELECT run_id FROM runs "
                "ORDER BY started_ts DESC, run_id DESC LIMIT 50"
            )
        ]
        assert any("idx_runs_started_ts" in step for step in plan), plan
        assert not any(step == "SCAN runs" for step in plan), plan


class TestInstruments:
    def test_store_and_retrieve(self, repo):
        repo.upsert_instrument(_instrument())
        got = repo.get_instrument(INST)
        assert got == _instrument()

    def test_update_via_upsert(self, repo):
        repo.upsert_instrument(_instrument())
        repo.upsert_instrument(Instrument(instrument_id=INST, symbol="AAA", exchange="NSE",
                                          series="BE", isin="INE000A01AAA", lot_size=1,
                                          tick_size=Decimal("0.05"), status="SUSPENDED"))
        assert repo.get_instrument(INST).status == "SUSPENDED"
        assert len(repo.list_instruments()) == 1

    def test_missing_instrument_returns_none(self, repo):
        assert repo.get_instrument("NOPE") is None

    def test_name_column_roundtrips(self, repo):
        """SCHEMA_VERSION 9: instruments.name — real company name from
        Kite's own instrument dump, previously discarded on ingestion."""
        repo.upsert_instrument(
            Instrument(instrument_id=INST, symbol="AAA", exchange="NSE", series="EQ",
                       name="Alpha Alloys Limited")
        )
        assert repo.get_instrument(INST).name == "Alpha Alloys Limited"
        assert repo.list_instruments()[0].name == "Alpha Alloys Limited"

    def test_name_absent_reads_as_none_never_fabricated(self, repo):
        repo.upsert_instrument(_instrument())
        assert repo.get_instrument(INST).name is None

    def test_sector_column_roundtrips(self, repo):
        """SCHEMA_VERSION 10: instruments.sector — NSE Industry from the
        Nifty 500 seed CSV (MI-4), previously discarded on parse."""
        repo.upsert_instrument(
            Instrument(instrument_id=INST, symbol="AAA", exchange="NSE", series="EQ",
                       sector="IT")
        )
        assert repo.get_instrument(INST).sector == "IT"
        assert repo.list_instruments()[0].sector == "IT"

    def test_kite_upsert_preserves_existing_sector(self, repo):
        repo.upsert_instrument(
            Instrument(instrument_id=INST, symbol="AAA", exchange="NSE", series="EQ",
                       sector="IT")
        )
        # Kite catalog refresh has no sector — must not wipe the seed value.
        repo.upsert_instrument(
            Instrument(instrument_id=INST, symbol="AAA", exchange="NSE", series="EQ",
                       name="Alpha Alloys Limited", sector=None)
        )
        got = repo.get_instrument(INST)
        assert got.name == "Alpha Alloys Limited"
        assert got.sector == "IT"

    def test_update_instrument_sector_by_symbol(self, repo):
        repo.upsert_instrument(_instrument())
        assert repo.update_instrument_sector("AAA", "Financial Services") == 1
        assert repo.get_instrument(INST).sector == "Financial Services"

    def test_initialize_migrates_pre_existing_db_missing_name_column(self, tmp_path):
        """A database created before SCHEMA_VERSION 9 (instruments table has
        no `name` column) must not break — initialize() adds it in place,
        idempotently, without touching any other column or existing rows."""
        db_path = tmp_path / "legacy.db"
        legacy = SqliteRepository(db_path)
        legacy.initialize()
        # Simulate the pre-migration schema by dropping back to the old
        # column set on a fresh connection to the same file.
        legacy._conn.execute("ALTER TABLE instruments RENAME TO instruments_new")
        legacy._conn.execute(
            "CREATE TABLE instruments (instrument_id TEXT PRIMARY KEY, isin TEXT, "
            "symbol TEXT NOT NULL, exchange TEXT NOT NULL, series TEXT NOT NULL, "
            "lot_size INTEGER NOT NULL, tick_size TEXT NOT NULL, status TEXT NOT NULL, "
            "listed_date TEXT, delisted_date TEXT)"
        )
        legacy._conn.execute("DROP TABLE instruments_new")
        legacy._conn.execute(
            "INSERT INTO instruments (instrument_id, isin, symbol, exchange, series, "
            "lot_size, tick_size, status, listed_date, delisted_date) "
            "VALUES ('LEGACY-1', NULL, 'OLD', 'NSE', 'EQ', 1, '0.05', 'ACTIVE', NULL, NULL)"
        )
        legacy._conn.commit()
        legacy.close()

        migrated = SqliteRepository(db_path)
        migrated.initialize()
        pre_existing = migrated.get_instrument("LEGACY-1")
        assert pre_existing is not None
        assert pre_existing.symbol == "OLD"
        assert pre_existing.name is None
        assert pre_existing.sector is None
        migrated.upsert_instrument(
            Instrument(instrument_id="LEGACY-1", symbol="OLD", exchange="NSE", series="EQ",
                       name="Old Co Ltd", sector="Capital Goods")
        )
        got = migrated.get_instrument("LEGACY-1")
        assert got.name == "Old Co Ltd"
        assert got.sector == "Capital Goods"
        migrated.close()


class TestCandles:
    def test_append_and_range_query(self, repo):
        repo.upsert_instrument(_instrument())
        repo.add_candles([_candle(date(2026, 2, d)) for d in (2, 3, 4, 5)])
        got = repo.get_candles(INST, Timeframe.D1,
                               datetime(2026, 2, 3, tzinfo=IST), datetime(2026, 2, 4, 23, tzinfo=IST))
        assert [c.ts_open.date() for c in got] == [date(2026, 2, 3), date(2026, 2, 4)]
        assert all(isinstance(c, Candle) for c in got)
        assert got[0].close == Decimal("100")

    def test_daily_and_intraday_coexist(self, repo):
        repo.upsert_instrument(_instrument())
        repo.add_candles([_candle(date(2026, 2, 2), Timeframe.D1)])
        repo.add_candles([_candle(date(2026, 2, 2), Timeframe.M5)])
        daily = repo.get_candles(INST, Timeframe.D1, datetime(2026, 2, 1, tzinfo=IST),
                                 datetime(2026, 2, 28, tzinfo=IST))
        intraday = repo.get_candles(INST, Timeframe.M5, datetime(2026, 2, 1, tzinfo=IST),
                                    datetime(2026, 2, 28, tzinfo=IST))
        assert len(daily) == 1 and len(intraday) == 1

    def test_duplicate_candle_upserts(self, repo):
        # add_candles is an upsert (owner-reported, 2026-08-04): the still-
        # forming daily candle for the current trading day is re-fetched on
        # every ingestion cycle and must land its corrected OHLC, not be
        # rejected as a duplicate of its own earlier, partial version.
        repo.upsert_instrument(_instrument())
        repo.add_candles([_candle(date(2026, 2, 2), close="100")])
        repo.add_candles([_candle(date(2026, 2, 2), close="105")])
        got = repo.get_candles(INST, Timeframe.D1,
                               datetime(2026, 2, 2, tzinfo=IST), datetime(2026, 2, 2, 23, tzinfo=IST))
        assert len(got) == 1
        assert got[0].close == Decimal("105")

    def test_foreign_key_enforced(self, repo):
        with pytest.raises(RepositoryError, match=r"integrity violation"):
            repo.add_candles([_candle(date(2026, 2, 2))])  # instrument not stored

    def test_empty_range_returns_empty(self, repo):
        repo.upsert_instrument(_instrument())
        assert repo.get_candles(INST, Timeframe.D1, datetime(2026, 1, 1, tzinfo=IST),
                                datetime(2026, 1, 31, tzinfo=IST)) == []


class TestTransactions:
    def test_rollback_on_exception(self, repo):
        repo.upsert_instrument(_instrument())
        with pytest.raises(RuntimeError), repo.transaction() as cur:
            cur.execute(
                "INSERT INTO candles (instrument_id, timeframe, ts_open, open, high, low, "
                "close, volume, source, adjusted) VALUES (?,?,?,?,?,?,?,?,?,?)",
                (INST, "1d", "2026-02-02T09:15:00+05:30", "100", "101", "99", "100", 1000,
                 "test", 0))
            raise RuntimeError("boom")
        # rolled back → nothing persisted
        assert repo.get_candles(INST, Timeframe.D1, datetime(2026, 2, 1, tzinfo=IST),
                                datetime(2026, 2, 28, tzinfo=IST)) == []

    def test_commit_on_success(self, repo):
        repo.upsert_instrument(_instrument())
        with repo.transaction() as cur:
            cur.execute(
                "INSERT INTO candles (instrument_id, timeframe, ts_open, open, high, low, "
                "close, volume, source, adjusted) VALUES (?,?,?,?,?,?,?,?,?,?)",
                (INST, "1d", "2026-02-02T09:15:00+05:30", "100", "101", "99", "100", 1000,
                 "test", 0))
        assert len(repo.get_candles(INST, Timeframe.D1, datetime(2026, 2, 1, tzinfo=IST),
                                    datetime(2026, 2, 28, tzinfo=IST))) == 1


class TestQuotesAndSnapshots:
    def test_quotes_roundtrip(self, repo):
        repo.upsert_instrument(_instrument())
        q = Quote(instrument_id=INST, ts=datetime(2026, 2, 2, 15, 30, tzinfo=IST),
                  last_price=Decimal("123.45"), volume=5000, source="test")
        repo.add_quotes([q])
        assert repo.get_quotes(INST) == [q]

    def test_latest_snapshot(self, repo):
        older = MarketSnapshot(ts=datetime(2026, 2, 2, 15, 30, tzinfo=IST),
                               indices={"NIFTY50": Decimal("25000")})
        newer = MarketSnapshot(ts=datetime(2026, 2, 3, 15, 30, tzinfo=IST),
                               indices={"NIFTY50": Decimal("25100.50")}, india_vix=Decimal("14.2"))
        repo.add_snapshot(older)
        repo.add_snapshot(newer)
        latest = repo.get_latest_snapshot()
        assert latest.ts == newer.ts
        assert latest.indices["NIFTY50"] == Decimal("25100.50")
        assert latest.india_vix == Decimal("14.2")


class TestCorporateActions:
    def test_roundtrip(self, repo):
        repo.upsert_instrument(_instrument())
        ca = CorporateAction(action_id="s1", instrument_id=INST, action_type="SPLIT",
                             ex_date=date(2026, 2, 4), details={"from_shares": "1", "to_shares": "5"})
        repo.add_corporate_action(ca)
        got = repo.get_corporate_actions(INST)
        assert len(got) == 1
        assert got[0].action_type == "SPLIT"
        assert got[0].ex_date == date(2026, 2, 4)
        assert got[0].details == {"from_shares": "1", "to_shares": "5"}

    def test_foreign_key_enforced(self, repo):
        ca = CorporateAction(action_id="s1", instrument_id="MISSING", action_type="SPLIT",
                             ex_date=date(2026, 2, 4), details={})
        with pytest.raises(RepositoryError, match=r"integrity violation"):
            repo.add_corporate_action(ca)


class TestQuarantinePersistence:
    def _record(self) -> QuarantineRecord:
        report = ValidationReport(
            validation_type=ValidationType.OHLC, result=ValidationResult.FAILED,
            severity=Severity.CRITICAL, explanation="non-positive price",
            ts=datetime(2026, 2, 6, 18, tzinfo=IST), evidence=("2026-02-02 price 0",),
            statistics={"non_positive_price_count": 1})
        return QuarantineRecord(dataset_id="X:1d", reason="OHLC: non-positive price",
                                failed_reports=(report,),
                                quarantined_ts=datetime(2026, 2, 6, 18, tzinfo=IST))

    def test_persist_and_restore_with_evidence(self, repo):
        repo.save_quarantine(self._record())
        got = repo.get_quarantine("X:1d")
        assert got is not None
        assert got.reason == "OHLC: non-positive price"
        assert len(got.failed_reports) == 1
        r = got.failed_reports[0]
        assert r.validation_type is ValidationType.OHLC
        assert r.severity is Severity.CRITICAL
        assert r.evidence == ("2026-02-02 price 0",)
        assert r.statistics["non_positive_price_count"] == 1

    def test_list_quarantine(self, repo):
        repo.save_quarantine(self._record())
        assert len(repo.list_quarantine()) == 1

    def test_missing_returns_none(self, repo):
        assert repo.get_quarantine("nope") is None


class TestIntegrity:
    def test_healthy_database(self, repo):
        report = repo.verify_integrity()
        assert report.ok
        assert report.integrity_check == "ok"
        assert report.foreign_key_violations == 0
        assert report.schema_version_ok

    def test_empty_database_is_healthy(self, tmp_path):
        r = SqliteRepository(tmp_path / "empty.db")
        r.initialize()
        assert r.verify_integrity().ok
        r.close()

    def test_corrupted_file_fails_loudly(self, tmp_path):
        # A non-SQLite file must be rejected loudly. SQLite detects this eagerly
        # (at open, via the WAL pragma) or lazily (at query) depending on version;
        # either way it surfaces as RepositoryError, never a silent success.
        bad = tmp_path / "corrupt.db"
        bad.write_bytes(b"this is not a sqlite database" * 10)
        with pytest.raises(RepositoryError):
            repo = SqliteRepository(bad)
            repo.verify_integrity()
