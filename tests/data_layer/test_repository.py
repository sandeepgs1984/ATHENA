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

    def test_duplicate_candle_rejected(self, repo):
        repo.upsert_instrument(_instrument())
        repo.add_candles([_candle(date(2026, 2, 2))])
        with pytest.raises(RepositoryError, match=r"integrity violation"):
            repo.add_candles([_candle(date(2026, 2, 2))])

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
