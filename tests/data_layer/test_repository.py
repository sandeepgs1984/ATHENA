"""SqliteRepository tests (M1.5): schema, CRUD, append-only, transactions,
FK enforcement, duplicates, integrity, quarantine, corporate actions, ranges."""

from __future__ import annotations

from datetime import date, datetime, timedelta
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

    def test_get_candles_retains_every_row_in_a_high_density_session(self, repo):
        # ID-3.1 §2/§22: the exact real production defect this milestone
        # fixes — a fixed `list_candles_recent(limit=100)` read silently
        # drops a session's own earliest bars once persisted row density
        # for that session exceeds the limit (ID-3's real-data sanity check
        # found 100-130 real M5 rows/session). `get_candles`'s explicit
        # [start, end] bound has no row-count ceiling to breach.
        repo.upsert_instrument(_instrument())
        base = datetime(2026, 2, 2, 9, 15, tzinfo=IST)
        candles = [_m5(base + timedelta(minutes=i)) for i in range(130)]
        repo.add_candles(candles)
        got = repo.get_candles(
            INST, Timeframe.M5, base, base + timedelta(minutes=200)
        )
        assert len(got) == 130
        assert got[0].ts_open == base
        assert got[-1].ts_open == base + timedelta(minutes=129)
        assert list(got) == sorted(got, key=lambda c: c.ts_open)

    def test_earliest_candle_ts_returns_the_minimum_ts_open(self, repo):
        # ID-5D.1: lets a caller retrieve "all available history" for an
        # instrument without hardcoding a lookback-day count.
        repo.upsert_instrument(_instrument())
        repo.add_candles([
            _m5(datetime(2026, 3, 2, 9, 20, tzinfo=IST)),
            _m5(datetime(2026, 2, 2, 9, 15, tzinfo=IST)),
            _m5(datetime(2026, 2, 15, 9, 15, tzinfo=IST)),
        ])
        assert repo.earliest_candle_ts(INST, Timeframe.M5) == datetime(2026, 2, 2, 9, 15, tzinfo=IST)

    def test_earliest_candle_ts_is_none_when_no_candles_exist(self, repo):
        repo.upsert_instrument(_instrument())
        assert repo.earliest_candle_ts(INST, Timeframe.M5) is None

    def test_earliest_candle_ts_is_scoped_to_its_own_timeframe(self, repo):
        repo.upsert_instrument(_instrument())
        repo.add_candles([_candle(date(2026, 1, 1), Timeframe.D1)])
        repo.add_candles([_m5(datetime(2026, 3, 2, 9, 15, tzinfo=IST))])
        assert repo.earliest_candle_ts(INST, Timeframe.M5) == datetime(2026, 3, 2, 9, 15, tzinfo=IST)

    def test_earliest_candle_ts_query_plan_uses_index_not_full_table_scan(self, repo):
        repo.upsert_instrument(_instrument())
        repo.add_candles([_m5(datetime(2026, 2, 2, 9, 15, tzinfo=IST))])
        plan = repo.connection.execute(
            "EXPLAIN QUERY PLAN SELECT MIN(ts_open) FROM candles "
            "WHERE instrument_id=? AND timeframe=?",
            (INST, Timeframe.M5.value),
        ).fetchall()
        plan_text = " ".join(str(row) for row in plan)
        assert "SCAN candles" not in plan_text

    def test_get_candles_query_plan_uses_index_not_full_table_scan(self, repo):
        # ID-3.1 §16: this bounded query runs per symbol across the full
        # owner-candidate universe every cycle — must be an indexed range
        # search on the existing (instrument_id, timeframe, ts_open) index,
        # never a full "SCAN candles".
        repo.upsert_instrument(_instrument())
        repo.add_candles([_m5(datetime(2026, 2, 2, 9, 15, tzinfo=IST))])
        plan = repo.connection.execute(
            "EXPLAIN QUERY PLAN SELECT instrument_id, timeframe, ts_open, open, high, "
            "low, close, volume, source, adjusted FROM candles WHERE instrument_id=? "
            "AND timeframe=? AND ts_open>=? AND ts_open<=? ORDER BY ts_open",
            (INST, Timeframe.M5.value, "2026-02-02T00:00:00+05:30", "2026-02-02T23:59:59+05:30"),
        ).fetchall()
        plan_text = " ".join(str(row) for row in plan)
        assert "SCAN candles" not in plan_text
        assert "SEARCH candles USING INDEX idx_candles_range" in plan_text


def _m5(ts: datetime, close="100") -> Candle:
    c = Decimal(close)
    return Candle(instrument_id=INST, timeframe=Timeframe.M5, ts_open=ts,
                  open=c, high=c + 1, low=c - 1, close=c, volume=1000, source="test")


class TestListCandlesRecentPointInTime:
    """ID-5E: `list_candles_recent(..., as_of=...)` -- market-time
    point-in-time safety. See §32 of the ID-5E milestone spec for the
    12-item contract this class covers."""

    def test_1_no_cutoff_preserves_old_behavior(self, repo):
        repo.upsert_instrument(_instrument())
        candles = [_m5(datetime(2026, 2, 2, 9, 15 + 5 * i, tzinfo=IST)) for i in range(5)]
        repo.add_candles(candles)
        without_as_of = repo.list_candles_recent(INST, Timeframe.M5, limit=3)
        assert [c.ts_open for c in without_as_of] == [c.ts_open for c in candles[-3:]]

    def test_2_cutoff_excludes_future_candle(self, repo):
        repo.upsert_instrument(_instrument())
        repo.add_candles([
            _m5(datetime(2026, 2, 2, 9, 15, tzinfo=IST)),
            _m5(datetime(2026, 2, 2, 9, 20, tzinfo=IST)),
            _m5(datetime(2026, 2, 2, 9, 25, tzinfo=IST)),  # future relative to the cutoff below
        ])
        got = repo.list_candles_recent(
            INST, Timeframe.M5, limit=10, as_of=datetime(2026, 2, 2, 9, 20, tzinfo=IST)
        )
        assert [c.ts_open for c in got] == [
            datetime(2026, 2, 2, 9, 15, tzinfo=IST), datetime(2026, 2, 2, 9, 20, tzinfo=IST),
        ]

    def test_3_exact_ts_open_boundary_is_included(self, repo):
        repo.upsert_instrument(_instrument())
        repo.add_candles([_m5(datetime(2026, 2, 2, 9, 15, tzinfo=IST))])
        got = repo.list_candles_recent(
            INST, Timeframe.M5, limit=10, as_of=datetime(2026, 2, 2, 9, 15, tzinfo=IST)
        )
        assert len(got) == 1

    def test_4_future_rows_cannot_consume_limit(self, repo):
        """§20/§8: seed A-E (relevant history) plus many future rows dated
        after the as_of cutoff. limit=3, as_of at E. A Python-filter-after-
        fetch (or an unbounded SQL fetch) would let the future rows F..J
        consume the top-3 LIMIT slots, returning an empty or wrong result
        for a cutoff at E. Correct SQL-level filtering returns C, D, E."""
        repo.upsert_instrument(_instrument())
        relevant = [_m5(datetime(2026, 2, 2, 9, 15 + 5 * i, tzinfo=IST), close=str(100 + i))
                    for i in range(5)]  # A B C D E
        future_noise = [_m5(datetime(2026, 2, 2, 10, 0, tzinfo=IST) + timedelta(minutes=5 * i),
                            close=str(999 + i))
                        for i in range(20)]  # F G H I J ... many more than the LIMIT
        repo.add_candles([*relevant, *future_noise])
        as_of_e = relevant[-1].ts_open  # cutoff exactly at E
        got = repo.list_candles_recent(INST, Timeframe.M5, limit=3, as_of=as_of_e)
        assert [c.ts_open for c in got] == [c.ts_open for c in relevant[-3:]]  # C, D, E

    def test_5_return_ordering_is_oldest_first_with_or_without_cutoff(self, repo):
        repo.upsert_instrument(_instrument())
        candles = [_m5(datetime(2026, 2, 2, 9, 15 + 5 * i, tzinfo=IST)) for i in range(5)]
        repo.add_candles(candles)
        got = repo.list_candles_recent(INST, Timeframe.M5, limit=10, as_of=candles[-1].ts_open)
        assert [c.ts_open for c in got] == sorted(c.ts_open for c in got)

    def test_6_m5_and_m15_cutoffs_are_isolated_by_timeframe(self, repo):
        repo.upsert_instrument(_instrument())
        m5 = _m5(datetime(2026, 2, 2, 9, 15, tzinfo=IST))
        m15 = Candle(instrument_id=INST, timeframe=Timeframe.M15,
                     ts_open=datetime(2026, 2, 2, 9, 15, tzinfo=IST),
                     open=Decimal("100"), high=Decimal("101"), low=Decimal("99"),
                     close=Decimal("100"), volume=1000, source="test")
        repo.add_candles([m5, m15])
        as_of = datetime(2026, 2, 2, 9, 20, tzinfo=IST)
        got_m5 = repo.list_candles_recent(INST, Timeframe.M5, limit=10, as_of=as_of)
        got_m15 = repo.list_candles_recent(INST, Timeframe.M15, limit=10, as_of=as_of)
        assert len(got_m5) == 1 and got_m5[0].timeframe is Timeframe.M5
        assert len(got_m15) == 1 and got_m15[0].timeframe is Timeframe.M15

    def test_7_d1_works_with_a_cutoff(self, repo):
        repo.upsert_instrument(_instrument())
        repo.add_candles([_candle(date(2026, 2, d)) for d in (2, 3, 4, 5)])
        got = repo.list_candles_recent(
            INST, Timeframe.D1, limit=10,
            as_of=datetime.combine(date(2026, 2, 3), datetime.min.time(), tzinfo=IST).replace(hour=23),
        )
        assert [c.ts_open.date() for c in got] == [date(2026, 2, 2), date(2026, 2, 3)]

    def test_8_9_cutoff_before_all_data_returns_empty(self, repo):
        repo.upsert_instrument(_instrument())
        repo.add_candles([_m5(datetime(2026, 2, 2, 9, 15, tzinfo=IST))])
        got = repo.list_candles_recent(
            INST, Timeframe.M5, limit=10, as_of=datetime(2026, 2, 1, 9, 15, tzinfo=IST)
        )
        assert got == []

    def test_10_cutoff_after_all_data_returns_standard_latest_n(self, repo):
        repo.upsert_instrument(_instrument())
        candles = [_m5(datetime(2026, 2, 2, 9, 15 + 5 * i, tzinfo=IST)) for i in range(5)]
        repo.add_candles(candles)
        got = repo.list_candles_recent(
            INST, Timeframe.M5, limit=3, as_of=datetime(2026, 2, 2, 23, 0, tzinfo=IST)
        )
        assert [c.ts_open for c in got] == [c.ts_open for c in candles[-3:]]

    def test_11_naive_as_of_rejected(self, repo):
        repo.upsert_instrument(_instrument())
        with pytest.raises(ValueError, match="timezone-aware"):
            repo.list_candles_recent(
                INST, Timeframe.M5, limit=10, as_of=datetime(2026, 2, 2, 9, 15)
            )

    def test_12_query_plan_uses_index_not_full_table_scan(self, repo):
        repo.upsert_instrument(_instrument())
        repo.add_candles([_m5(datetime(2026, 2, 2, 9, 15, tzinfo=IST))])
        plan = repo.connection.execute(
            "EXPLAIN QUERY PLAN SELECT instrument_id, timeframe, ts_open, open, high, low, "
            "close, volume, source, adjusted FROM candles WHERE instrument_id=? "
            "AND timeframe=? AND ts_open<=? ORDER BY ts_open DESC LIMIT ?",
            (INST, Timeframe.M5.value, "2026-02-02T23:59:59+05:30", 10),
        ).fetchall()
        plan_text = " ".join(str(row) for row in plan)
        assert "SCAN candles" not in plan_text
        assert "SEARCH candles USING INDEX idx_candles_range" in plan_text


class TestReplaceCandles:
    """`replace_candles` -- the M5 settlement-repair path (Owner-authorized
    2026-08-28): unlike `add_candles`'s upsert, a corrected candle at a
    DIFFERENT exact ts_open than the old drifted one must not sit alongside
    it -- the whole range gets one canonical sequence."""

    def test_a_corrected_timestamp_replaces_rather_than_accumulates_alongside_the_drifted_one(self, repo):
        repo.upsert_instrument(_instrument())
        drifted = _m5(datetime(2026, 8, 28, 9, 43, 55, tzinfo=IST))
        repo.add_candles([drifted])

        settled = _m5(datetime(2026, 8, 28, 9, 45, 0, tzinfo=IST), close="101")
        deleted, inserted = repo.replace_candles(
            INST, Timeframe.M5,
            datetime(2026, 8, 28, 9, 40, tzinfo=IST), datetime(2026, 8, 28, 9, 50, tzinfo=IST),
            [settled],
        )

        assert deleted == 1
        assert inserted == 1
        got = repo.get_candles(INST, Timeframe.M5,
                               datetime(2026, 8, 28, 9, 40, tzinfo=IST), datetime(2026, 8, 28, 9, 50, tzinfo=IST))
        assert len(got) == 1
        assert got[0].ts_open == datetime(2026, 8, 28, 9, 45, 0, tzinfo=IST)
        assert got[0].close == Decimal("101")

    def test_candles_outside_the_replacement_range_are_untouched(self, repo):
        repo.upsert_instrument(_instrument())
        before = _m5(datetime(2026, 8, 28, 9, 15, tzinfo=IST))
        after = _m5(datetime(2026, 8, 28, 10, 15, tzinfo=IST))
        repo.add_candles([before, after])

        repo.replace_candles(
            INST, Timeframe.M5,
            datetime(2026, 8, 28, 9, 40, tzinfo=IST), datetime(2026, 8, 28, 9, 50, tzinfo=IST),
            [],
        )

        got = repo.get_candles(INST, Timeframe.M5,
                               datetime(2026, 8, 28, 0, 0, tzinfo=IST), datetime(2026, 8, 28, 23, 59, tzinfo=IST))
        assert {c.ts_open for c in got} == {before.ts_open, after.ts_open}

    def test_replacing_with_an_empty_list_deletes_without_reinserting(self, repo):
        repo.upsert_instrument(_instrument())
        repo.add_candles([_m5(datetime(2026, 8, 28, 9, 43, 55, tzinfo=IST))])

        deleted, inserted = repo.replace_candles(
            INST, Timeframe.M5,
            datetime(2026, 8, 28, 9, 40, tzinfo=IST), datetime(2026, 8, 28, 9, 50, tzinfo=IST),
            [],
        )

        assert (deleted, inserted) == (1, 0)
        remaining = repo.get_candles(
            INST, Timeframe.M5, datetime(2026, 8, 28, 9, 40, tzinfo=IST), datetime(2026, 8, 28, 9, 50, tzinfo=IST),
        )
        assert remaining == []

    def test_rejects_a_candle_whose_ts_open_falls_outside_the_declared_range(self, repo):
        repo.upsert_instrument(_instrument())
        outside = _m5(datetime(2026, 8, 28, 11, 0, tzinfo=IST))
        with pytest.raises(ValueError, match="ts_open must fall within"):
            repo.replace_candles(
                INST, Timeframe.M5,
                datetime(2026, 8, 28, 9, 40, tzinfo=IST), datetime(2026, 8, 28, 9, 50, tzinfo=IST),
                [outside],
            )

    def test_rejects_a_candle_for_a_different_instrument_or_timeframe(self, repo):
        repo.upsert_instrument(_instrument())
        wrong_tf = Candle(instrument_id=INST, timeframe=Timeframe.M1,
                          ts_open=datetime(2026, 8, 28, 9, 45, tzinfo=IST),
                          open=Decimal("100"), high=Decimal("101"), low=Decimal("99"),
                          close=Decimal("100"), volume=1000, source="test")
        with pytest.raises(ValueError, match="must match instrument_id/timeframe"):
            repo.replace_candles(
                INST, Timeframe.M5,
                datetime(2026, 8, 28, 9, 40, tzinfo=IST), datetime(2026, 8, 28, 9, 50, tzinfo=IST),
                [wrong_tf],
            )

    def test_a_failed_replacement_leaves_the_original_data_intact(self, repo):
        """The delete and insert are one transaction -- an integrity
        failure on the insert half (two candles colliding on the same
        exact (instrument, timeframe, ts_open) unique key, which the plain
        INSERT this method uses -- deliberately not an upsert -- rejects)
        must roll back the delete half too, never leaving the range with
        neither the old nor the new data."""
        repo.upsert_instrument(_instrument())
        original = _m5(datetime(2026, 8, 28, 9, 43, 55, tzinfo=IST))
        repo.add_candles([original])

        colliding_pair = [
            _m5(datetime(2026, 8, 28, 9, 45, tzinfo=IST), close="101"),
            _m5(datetime(2026, 8, 28, 9, 45, tzinfo=IST), close="102"),
        ]

        with pytest.raises(RepositoryError, match="integrity violation"):
            repo.replace_candles(
                INST, Timeframe.M5,
                datetime(2026, 8, 28, 9, 40, tzinfo=IST), datetime(2026, 8, 28, 9, 50, tzinfo=IST),
                colliding_pair,
            )

        got = repo.get_candles(INST, Timeframe.M5,
                               datetime(2026, 8, 28, 9, 40, tzinfo=IST), datetime(2026, 8, 28, 9, 50, tzinfo=IST))
        assert len(got) == 1
        assert got[0].ts_open == original.ts_open


class TestBulkCandlesForInstruments:
    """`candles_for_instruments` -- EM-5's grouped bulk read (ADR-012
    Section 10: one query across a scan's whole eligible universe, never
    one `get_candles` call per symbol)."""

    def test_groups_candles_by_instrument(self, repo):
        other = "NSE:BBB"
        repo.upsert_instrument(_instrument())
        repo.upsert_instrument(_instrument(iid=other, symbol="BBB"))
        repo.add_candles([_candle(date(2026, 2, 2)), _candle(date(2026, 2, 3))])
        repo.add_candles([Candle(instrument_id=other, timeframe=Timeframe.D1,
                                 ts_open=datetime(2026, 2, 2, 9, 15, tzinfo=IST),
                                 open=Decimal("50"), high=Decimal("51"), low=Decimal("49"),
                                 close=Decimal("50"), volume=500, source="test")])
        got = repo.candles_for_instruments(
            [INST, other], Timeframe.D1, datetime(2026, 2, 1, tzinfo=IST), datetime(2026, 2, 28, tzinfo=IST)
        )
        assert {c.ts_open.date() for c in got[INST]} == {date(2026, 2, 2), date(2026, 2, 3)}
        assert [c.close for c in got[other]] == [Decimal("50")]

    def test_instrument_with_no_candles_in_range_is_omitted(self, repo):
        repo.upsert_instrument(_instrument())
        assert repo.candles_for_instruments(
            [INST], Timeframe.D1, datetime(2026, 1, 1, tzinfo=IST), datetime(2026, 1, 31, tzinfo=IST)
        ) == {}

    def test_empty_instrument_list_returns_empty_dict(self, repo):
        assert repo.candles_for_instruments(
            [], Timeframe.D1, datetime(2026, 1, 1, tzinfo=IST), datetime(2026, 1, 31, tzinfo=IST)
        ) == {}

    def test_query_plan_uses_the_range_index_not_a_table_scan(self, repo):
        """EM-5 runs this query across a 500+ instrument universe every
        checkpoint (ADR-012 Section 10) -- a real EXPLAIN QUERY PLAN
        check, not just an index existing in schema.py, proves SQLite
        actually chooses it for this exact query shape (IN-list on
        instrument_id, equality on timeframe, range on ts_open)."""
        marks = ",".join("?" * 3)
        sql = (
            f"SELECT instrument_id, timeframe, ts_open, open, high, low, close, volume, source, "
            f"adjusted FROM candles WHERE timeframe=? AND instrument_id IN ({marks}) "
            f"AND ts_open>=? AND ts_open<=? ORDER BY instrument_id, ts_open"
        )
        params = ("5m", "NSE:A", "NSE:B", "NSE:C", "2026-08-01T00:00:00+05:30", "2026-08-31T23:59:00+05:30")
        plan = repo.connection.execute("EXPLAIN QUERY PLAN " + sql, params).fetchall()
        detail = " ".join(str(row[-1]) for row in plan)
        assert "idx_candles_range" in detail
        assert "SCAN candles" not in detail  # a full table scan would defeat the index entirely

    def test_result_matches_per_symbol_get_candles(self, repo):
        other = "NSE:BBB"
        repo.upsert_instrument(_instrument())
        repo.upsert_instrument(_instrument(iid=other, symbol="BBB"))
        repo.add_candles([_candle(date(2026, 2, d)) for d in (2, 3, 4)])
        repo.add_candles([Candle(instrument_id=other, timeframe=Timeframe.D1,
                                 ts_open=datetime(2026, 2, 3, 9, 15, tzinfo=IST),
                                 open=Decimal("50"), high=Decimal("51"), low=Decimal("49"),
                                 close=Decimal("50"), volume=500, source="test")])
        start, end = datetime(2026, 2, 1, tzinfo=IST), datetime(2026, 2, 28, tzinfo=IST)
        bulk = repo.candles_for_instruments([INST, other], Timeframe.D1, start, end)
        assert bulk[INST] == repo.get_candles(INST, Timeframe.D1, start, end)
        assert bulk[other] == repo.get_candles(other, Timeframe.D1, start, end)

    def test_chunks_beyond_500_instruments(self, repo):
        # SQLite's host-parameter cap forces chunking above ~500 -- proves
        # the loop actually iterates rather than silently truncating.
        ids = [f"NSE:SYM{i:04d}" for i in range(600)]
        for iid in ids:
            repo.upsert_instrument(_instrument(iid=iid, symbol=iid.split(":")[1]))
        repo.add_candles([Candle(instrument_id=ids[0], timeframe=Timeframe.D1,
                                 ts_open=datetime(2026, 2, 2, 9, 15, tzinfo=IST),
                                 open=Decimal("10"), high=Decimal("11"), low=Decimal("9"),
                                 close=Decimal("10"), volume=100, source="test")])
        repo.add_candles([Candle(instrument_id=ids[599], timeframe=Timeframe.D1,
                                 ts_open=datetime(2026, 2, 2, 9, 15, tzinfo=IST),
                                 open=Decimal("20"), high=Decimal("21"), low=Decimal("19"),
                                 close=Decimal("20"), volume=200, source="test")])
        got = repo.candles_for_instruments(
            ids, Timeframe.D1, datetime(2026, 2, 1, tzinfo=IST), datetime(2026, 2, 28, tzinfo=IST)
        )
        assert set(got) == {ids[0], ids[599]}


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


class TestGetLatestQuotePointInTime:
    """ID-5F: `get_latest_quote(..., as_of=...)` -- market-time
    point-in-time safety for quotes, same contract as ID-5E's
    `list_candles_recent(..., as_of=...)`. See §27 of the ID-5F milestone
    spec for the 10-item checklist this class covers."""

    def _q(self, ts: datetime, price: str = "100") -> Quote:
        return Quote(instrument_id=INST, ts=ts, last_price=Decimal(price),
                     volume=1000, source="test")

    def test_1_no_as_of_returns_latest(self, repo):
        repo.upsert_instrument(_instrument())
        repo.add_quotes([
            self._q(datetime(2026, 2, 2, 9, 16, tzinfo=IST), "100"),
            self._q(datetime(2026, 2, 2, 9, 20, tzinfo=IST), "101"),
        ])
        got = repo.get_latest_quote(INST)
        assert got.ts == datetime(2026, 2, 2, 9, 20, tzinfo=IST)

    def test_2_as_of_returns_latest_eligible_quote(self, repo):
        repo.upsert_instrument(_instrument())
        repo.add_quotes([
            self._q(datetime(2026, 2, 2, 9, 16, tzinfo=IST), "100"),
            self._q(datetime(2026, 2, 2, 9, 20, tzinfo=IST), "101"),
            self._q(datetime(2026, 2, 2, 9, 30, tzinfo=IST), "999"),  # future relative to as_of
        ])
        got = repo.get_latest_quote(INST, as_of=datetime(2026, 2, 2, 9, 24, tzinfo=IST))
        assert got.ts == datetime(2026, 2, 2, 9, 20, tzinfo=IST)
        assert got.last_price == Decimal("101")

    def test_3_exact_boundary_quote_included(self, repo):
        repo.upsert_instrument(_instrument())
        repo.add_quotes([self._q(datetime(2026, 2, 2, 9, 20, tzinfo=IST))])
        got = repo.get_latest_quote(INST, as_of=datetime(2026, 2, 2, 9, 20, tzinfo=IST))
        assert got is not None

    def test_4_future_quote_excluded(self, repo):
        repo.upsert_instrument(_instrument())
        repo.add_quotes([self._q(datetime(2026, 2, 2, 9, 25, tzinfo=IST))])
        got = repo.get_latest_quote(INST, as_of=datetime(2026, 2, 2, 9, 20, tzinfo=IST))
        assert got is None

    def test_5_future_quote_does_not_hide_a_valid_earlier_quote(self, repo):
        """§12 non-vacuous shape: a later, ineligible quote existing in the
        database must not prevent the correct earlier one from being
        returned -- proven with an extreme price on the future quote so
        any leak would be obvious."""
        repo.upsert_instrument(_instrument())
        repo.add_quotes([
            self._q(datetime(2026, 2, 2, 9, 20, tzinfo=IST), "101"),
            self._q(datetime(2026, 2, 2, 9, 30, tzinfo=IST), "999999"),
        ])
        got = repo.get_latest_quote(INST, as_of=datetime(2026, 2, 2, 9, 25, tzinfo=IST))
        assert got.ts == datetime(2026, 2, 2, 9, 20, tzinfo=IST)
        assert got.last_price == Decimal("101")

    def test_6_all_quotes_after_as_of_returns_none(self, repo):
        repo.upsert_instrument(_instrument())
        repo.add_quotes([self._q(datetime(2026, 2, 2, 9, 30, tzinfo=IST))])
        got = repo.get_latest_quote(INST, as_of=datetime(2026, 2, 2, 9, 15, tzinfo=IST))
        assert got is None

    def test_7_multiple_historical_quotes_choose_nearest_at_or_before_cutoff(self, repo):
        repo.upsert_instrument(_instrument())
        repo.add_quotes([
            self._q(datetime(2026, 2, 2, 9, 16, tzinfo=IST), "1"),  # Q1
            self._q(datetime(2026, 2, 2, 9, 20, tzinfo=IST), "2"),  # Q2
            self._q(datetime(2026, 2, 2, 9, 24, tzinfo=IST), "3"),  # Q3
            self._q(datetime(2026, 2, 2, 9, 30, tzinfo=IST), "4"),  # Q4
        ])
        got = repo.get_latest_quote(INST, as_of=datetime(2026, 2, 2, 9, 24, tzinfo=IST))
        assert got.last_price == Decimal("3")

    def test_8_naive_as_of_rejected(self, repo):
        repo.upsert_instrument(_instrument())
        with pytest.raises(ValueError, match="timezone-aware"):
            repo.get_latest_quote(INST, as_of=datetime(2026, 2, 2, 9, 20))

    def test_9_instrument_isolation(self, repo):
        repo.upsert_instrument(_instrument())
        repo.upsert_instrument(_instrument(iid="INE-REPO-0002", symbol="BBB"))
        repo.add_quotes([
            self._q(datetime(2026, 2, 2, 9, 20, tzinfo=IST), "100"),
            Quote(instrument_id="INE-REPO-0002", ts=datetime(2026, 2, 2, 9, 25, tzinfo=IST),
                  last_price=Decimal("999"), volume=1000, source="test"),
        ])
        got = repo.get_latest_quote(INST, as_of=datetime(2026, 2, 2, 9, 30, tzinfo=IST))
        assert got.instrument_id == INST
        assert got.last_price == Decimal("100")

    def test_10_query_plan_uses_existing_primary_key_not_a_full_table_scan(self, repo):
        repo.upsert_instrument(_instrument())
        repo.add_quotes([self._q(datetime(2026, 2, 2, 9, 20, tzinfo=IST))])
        plan = repo.connection.execute(
            "EXPLAIN QUERY PLAN SELECT instrument_id, ts, last_price, volume, source FROM quotes "
            "WHERE instrument_id=? AND ts<=? ORDER BY ts DESC LIMIT 1",
            (INST, "2026-02-02T09:30:00+05:30"),
        ).fetchall()
        plan_text = " ".join(str(row) for row in plan)
        assert "SCAN quotes" not in plan_text


class TestGetLatestSnapshotAsOf:
    """ID-5G: `get_latest_snapshot_as_of(as_of)` -- market-time
    point-in-time safety for MarketSnapshot, INCLUSIVE at the exact
    boundary (deliberately distinct from `get_latest_snapshot_before`'s
    own STRICT `<` semantics, which stays untouched for its own two
    "prior state" callers). See §30 of the ID-5G milestone spec."""

    def _snap(self, ts: datetime, nifty: str = "25000") -> MarketSnapshot:
        return MarketSnapshot(ts=ts, indices={"NIFTY50": Decimal(nifty)})

    def test_2_cutoff_selects_latest_eligible_snapshot(self, repo):
        repo.add_snapshot(self._snap(datetime(2026, 2, 2, 9, 16, tzinfo=IST), "25000"))
        repo.add_snapshot(self._snap(datetime(2026, 2, 2, 9, 20, tzinfo=IST), "25010"))
        repo.add_snapshot(self._snap(datetime(2026, 2, 2, 9, 30, tzinfo=IST), "99999"))  # future
        got = repo.get_latest_snapshot_as_of(datetime(2026, 2, 2, 9, 24, tzinfo=IST))
        assert got.ts == datetime(2026, 2, 2, 9, 20, tzinfo=IST)
        assert got.indices["NIFTY50"] == Decimal("25010")

    def test_3_future_snapshot_excluded(self, repo):
        repo.add_snapshot(self._snap(datetime(2026, 2, 2, 9, 30, tzinfo=IST)))
        got = repo.get_latest_snapshot_as_of(datetime(2026, 2, 2, 9, 20, tzinfo=IST))
        assert got is None

    def test_4_future_snapshot_does_not_hide_a_valid_earlier_snapshot(self, repo):
        """Non-vacuous shape: a later, ineligible snapshot existing in the
        database must not prevent the correct earlier one from being
        returned -- proven with an extreme index level on the future
        snapshot so any leak would be obvious."""
        repo.add_snapshot(self._snap(datetime(2026, 2, 2, 9, 20, tzinfo=IST), "25010"))
        repo.add_snapshot(self._snap(datetime(2026, 2, 2, 9, 30, tzinfo=IST), "999999"))
        got = repo.get_latest_snapshot_as_of(datetime(2026, 2, 2, 9, 25, tzinfo=IST))
        assert got.ts == datetime(2026, 2, 2, 9, 20, tzinfo=IST)
        assert got.indices["NIFTY50"] == Decimal("25010")

    def test_5_no_eligible_snapshot_returns_none(self, repo):
        got = repo.get_latest_snapshot_as_of(datetime(2026, 2, 2, 9, 20, tzinfo=IST))
        assert got is None

    def test_6_multiple_historical_snapshots_choose_nearest_at_or_before_cutoff(self, repo):
        repo.add_snapshot(self._snap(datetime(2026, 2, 2, 9, 16, tzinfo=IST), "1"))
        repo.add_snapshot(self._snap(datetime(2026, 2, 2, 9, 20, tzinfo=IST), "2"))
        repo.add_snapshot(self._snap(datetime(2026, 2, 2, 9, 24, tzinfo=IST), "3"))
        repo.add_snapshot(self._snap(datetime(2026, 2, 2, 9, 30, tzinfo=IST), "4"))
        got = repo.get_latest_snapshot_as_of(datetime(2026, 2, 2, 9, 24, tzinfo=IST))
        assert got.indices["NIFTY50"] == Decimal("3")

    def test_7_exact_boundary_snapshot_included(self, repo):
        """ID-5G §3: EXACT_BOUNDARY_INCLUDED, matching every other ID-5E/
        ID-5F point-in-time contract's inclusive `<=` convention -- a
        snapshot timestamped exactly at `as_of` is eligible."""
        repo.add_snapshot(self._snap(datetime(2026, 2, 2, 9, 20, tzinfo=IST)))
        got = repo.get_latest_snapshot_as_of(datetime(2026, 2, 2, 9, 20, tzinfo=IST))
        assert got is not None

    def test_8_naive_as_of_rejected(self, repo):
        with pytest.raises(ValueError, match="timezone-aware"):
            repo.get_latest_snapshot_as_of(datetime(2026, 2, 2, 9, 20))

    def test_9_deterministic_repeat_call(self, repo):
        repo.add_snapshot(self._snap(datetime(2026, 2, 2, 9, 20, tzinfo=IST)))
        as_of = datetime(2026, 2, 2, 9, 25, tzinfo=IST)
        assert repo.get_latest_snapshot_as_of(as_of) == repo.get_latest_snapshot_as_of(as_of)

    def test_10_query_plan_evidence(self, repo):
        """ID-5G §9/§32: `datetime()` wrapping is a deliberate correctness-
        over-speed tradeoff (the file-based provider permits a non-uniform
        UTC offset in a persisted snapshot's `ts`) -- documented here as a
        full SCAN, not silently assumed indexed."""
        repo.add_snapshot(self._snap(datetime(2026, 2, 2, 9, 20, tzinfo=IST)))
        plan = repo.connection.execute(
            "EXPLAIN QUERY PLAN SELECT payload_json FROM market_snapshots "
            "WHERE datetime(ts) <= datetime(?) ORDER BY datetime(ts) DESC LIMIT 1",
            ("2026-02-02T09:30:00+05:30",),
        ).fetchall()
        plan_text = " ".join(str(row) for row in plan)
        assert "SCAN market_snapshots" in plan_text  # accepted tradeoff, documented not hidden

    def test_get_latest_snapshot_before_semantics_are_unchanged(self, repo):
        """ID-5G must not repurpose or weaken get_latest_snapshot_before's
        own STRICT '<' semantics -- its two real callers (previous-session
        snapshot lookup, pre-decision snapshot lookup) depend on same-
        instant coincidence being excluded."""
        exact = datetime(2026, 2, 2, 9, 20, tzinfo=IST)
        repo.add_snapshot(self._snap(exact))
        assert repo.get_latest_snapshot_before(exact) is None
        assert repo.get_latest_snapshot_as_of(exact) is not None


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
