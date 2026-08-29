"""M5 settlement repair (Owner-authorized 2026-08-28) -- no real Kite calls
in any test here; the provider is a fully injected fake."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime
from decimal import Decimal
from pathlib import Path
from zoneinfo import ZoneInfo

import pytest

from athena.data.live_m5_settlement_repair import (
    repair_instrument,
    resolve_settlement_repair_dates,
    run_settlement_repair,
)
from athena.data.retrying_provider import RetryingMarketDataProvider
from athena.data.store import SqliteRepository
from athena.domain.enums import Timeframe
from athena.domain.market import Candle, Instrument
from athena.errors import ProviderError

IST = ZoneInfo("Asia/Kolkata")
INST = "NSE:TEST"


def _drifted_candle(ts: datetime, close="100") -> Candle:
    c = Decimal(close)
    return Candle(instrument_id=INST, timeframe=Timeframe.M5, ts_open=ts,
                  open=c, high=c + 1, low=c - 1, close=c, volume=1000, source="test")


def _settled_session(session_date: date, instrument_id: str = INST) -> list[Candle]:
    """A clean, fully grid-aligned 09:15-09:30 mini-session (4 slots)."""
    c = Decimal("100")
    return [
        Candle(instrument_id=instrument_id, timeframe=Timeframe.M5,
              ts_open=datetime.combine(session_date, datetime.min.time(), tzinfo=IST).replace(hour=9, minute=m),
              open=c, high=c + 1, low=c - 1, close=c, volume=1000, source="test")
        for m in (15, 20, 25, 30)
    ]


@dataclass
class _FakeProvider:
    """Minimal `MarketDataProvider`-shaped fake: only `intraday_candles` is
    exercised by the repair path. `settled_dates` marks which dates have a
    "settled" 4-slot session available (built fresh, correctly tagged with
    whichever `instrument_id` is actually requested); `fail_dates`
    simulates a real provider error for specific dates."""

    settled_dates: frozenset[date] = frozenset()
    fail_dates: frozenset[date] = frozenset()
    name: str = "fake"

    def intraday_candles(self, instrument_id, timeframe, start, end):
        for d in self.fail_dates:
            if start.date() <= d <= end.date():
                raise ProviderError(f"kite network failure fetching {instrument_id}")
        out: list[Candle] = []
        for d in self.settled_dates:
            if start.date() <= d <= end.date():
                out.extend(_settled_session(d, instrument_id))
        return out


@pytest.fixture()
def repo(tmp_path: Path) -> SqliteRepository:
    r = SqliteRepository(tmp_path / "athena.db")
    r.initialize()
    r.upsert_instrument(Instrument(
        instrument_id=INST, symbol="TEST", exchange="NSE", series="EQ", isin="INE000A01TST",
        lot_size=1, tick_size=Decimal("0.05"), status="ACTIVE", listed_date=date(2020, 1, 1),
    ))
    yield r
    r.close()


class TestResolveSettlementRepairDates:
    def test_covers_every_day_up_to_but_excluding_today(self):
        dates = resolve_settlement_repair_dates(earliest_available=date(2026, 8, 25), today=date(2026, 8, 28))
        assert dates == (date(2026, 8, 25), date(2026, 8, 26), date(2026, 8, 27))

    def test_empty_when_nothing_is_available_before_today(self):
        assert resolve_settlement_repair_dates(earliest_available=date(2026, 8, 28), today=date(2026, 8, 28)) == ()

    def test_id5_real_gap_date_2026_08_28_is_the_sole_target(self):
        """ID-5: the 2026-08-28 settlement repair run's own `today` was
        2026-08-28 (per its manifest), so that date was excluded by
        design -- it never settled during that run. As of 2026-08-29 it
        is a fully closed, settled session and is the sole date this
        function should now resolve to repair."""
        dates = resolve_settlement_repair_dates(earliest_available=date(2026, 8, 28), today=date(2026, 8, 29))
        assert dates == (date(2026, 8, 28),)


class TestRepairInstrument:
    def test_drifted_candles_are_replaced_by_the_settled_response_not_accumulated(self, repo):
        d = date(2026, 8, 20)
        repo.add_candles([_drifted_candle(datetime(2026, 8, 20, 9, 43, 55, tzinfo=IST))])
        provider = _FakeProvider(settled_dates=frozenset({d}))

        records = repair_instrument(provider=provider, repo=repo, instrument_id=INST, dates=(d,), tzinfo=IST)

        assert len(records) == 1
        r = records[0]
        assert r.rows_before == 1
        assert r.off_grid_before == 1
        assert r.rows_fetched == 4
        assert r.rows_deleted == 1
        assert r.rows_inserted == 4
        assert r.off_grid_after == 0
        got = repo.get_candles(INST, Timeframe.M5, datetime(2026, 8, 20, 0, 0, tzinfo=IST),
                               datetime(2026, 8, 20, 23, 59, tzinfo=IST))
        assert len(got) == 4
        assert {c.ts_open.minute for c in got} == {15, 20, 25, 30}

    def test_missing_early_session_coverage_is_detected_before_and_restored_after(self, repo):
        d = date(2026, 8, 20)
        # Before: only a late candle -- no coverage before the 09:20 probe.
        repo.add_candles([_drifted_candle(datetime(2026, 8, 20, 10, 30, tzinfo=IST))])
        provider = _FakeProvider(settled_dates=frozenset({d}))

        records = repair_instrument(provider=provider, repo=repo, instrument_id=INST, dates=(d,), tzinfo=IST)

        r = records[0]
        assert r.has_early_coverage_before is False
        assert r.has_early_coverage_after is True

    def test_a_session_with_zero_prior_data_is_populated_cleanly(self, repo):
        d = date(2026, 8, 20)
        provider = _FakeProvider(settled_dates=frozenset({d}))

        records = repair_instrument(provider=provider, repo=repo, instrument_id=INST, dates=(d,), tzinfo=IST)

        r = records[0]
        assert (r.rows_before, r.rows_deleted, r.rows_inserted) == (0, 0, 4)

    def test_a_provider_failure_leaves_the_session_untouched_and_is_recorded(self, repo):
        d = date(2026, 8, 20)
        original = _drifted_candle(datetime(2026, 8, 20, 9, 43, 55, tzinfo=IST))
        repo.add_candles([original])
        provider = _FakeProvider(fail_dates=frozenset({d}))

        records = repair_instrument(provider=provider, repo=repo, instrument_id=INST, dates=(d,), tzinfo=IST)

        r = records[0]
        assert r.error is not None
        assert r.rows_deleted == 0 and r.rows_inserted == 0
        got = repo.get_candles(INST, Timeframe.M5, datetime(2026, 8, 20, 0, 0, tzinfo=IST),
                               datetime(2026, 8, 20, 23, 59, tzinfo=IST))
        assert len(got) == 1 and got[0].ts_open == original.ts_open

    def test_one_fetch_covers_the_whole_multi_day_span_not_one_request_per_day(self, repo):
        dates = (date(2026, 8, 18), date(2026, 8, 19), date(2026, 8, 20))
        calls = []
        provider = _FakeProvider(settled_dates=frozenset(dates))
        original_fetch = provider.intraday_candles

        def _counting_fetch(iid, tf, start, end):
            calls.append((start, end))
            return original_fetch(iid, tf, start, end)

        provider.intraday_candles = _counting_fetch
        repair_instrument(provider=provider, repo=repo, instrument_id=INST, dates=dates, tzinfo=IST)

        assert len(calls) == 1
        assert calls[0][0].date() == dates[0] and calls[0][1].date() == dates[-1]

    def test_a_day_absent_from_the_fresh_fetch_is_left_with_zero_rows(self, repo):
        """Real-world case: the affected day turns out to be a genuine
        non-trading day, or Kite has nothing for it -- the repair must not
        fabricate rows, and must still atomically clear any stale
        provisional rows that were there before."""
        d = date(2026, 8, 20)
        repo.add_candles([_drifted_candle(datetime(2026, 8, 20, 9, 43, 55, tzinfo=IST))])
        provider = _FakeProvider(settled_dates=frozenset())

        records = repair_instrument(provider=provider, repo=repo, instrument_id=INST, dates=(d,), tzinfo=IST)

        r = records[0]
        assert (r.rows_before, r.rows_fetched, r.rows_deleted, r.rows_inserted) == (1, 0, 1, 0)


class TestRunSettlementRepair:
    def test_aggregates_across_instruments_and_reports_real_request_stats(self, repo):
        d = date(2026, 8, 20)
        repo.upsert_instrument(Instrument(
            instrument_id="NSE:TEST2", symbol="TEST2", exchange="NSE", series="EQ", isin="INE000A01TS2",
            lot_size=1, tick_size=Decimal("0.05"), status="ACTIVE", listed_date=date(2020, 1, 1),
        ))
        provider = RetryingMarketDataProvider(inner=_FakeProvider(settled_dates=frozenset({d})))

        manifest = run_settlement_repair(
            provider=provider, repo=repo, instrument_ids=(INST, "NSE:TEST2"), dates=(d,), tzinfo=IST,
        )

        assert manifest.request_count == 2  # one fetch per instrument
        assert manifest.rows_inserted_total == 8  # 4 slots x 2 instruments
        assert manifest.failure_count == 0
        assert manifest.finished_at >= manifest.started_at
