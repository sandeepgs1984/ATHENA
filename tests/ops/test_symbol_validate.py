"""Symbol validate perf fix tests. 2026-08-03: index/VIX re-ingestion is
skipped once a genuine today's-daily-candle freshness signal exists,
instead of unconditionally re-fetching every configured index on every
single-symbol validate. 2026-08-10: that fix alone still re-ingests every
stale index synchronously when many/all of them are stale at once (e.g.
right after market open, before REFRESH has caught them all up) — capped
via _indices_to_catch_up."""

from __future__ import annotations

from datetime import date, datetime, timedelta
from decimal import Decimal
from pathlib import Path
from zoneinfo import ZoneInfo

from athena.data.store.repository import SqliteRepository
from athena.domain.enums import Timeframe
from athena.domain.market import Candle, Instrument
import pytest

from athena.errors import DataValidationError
from athena.ops.owner_candidates import SqliteCandidateStore
from athena.ops.symbol_validate import (
    _index_instrument_needs_refresh,
    _indices_to_catch_up,
    validate_symbols,
)

IST = ZoneInfo("Asia/Kolkata")
CONFIG_DIR = Path(__file__).resolve().parents[2] / "config"


def _candle(iid: str, day: date, close: str = "100") -> Candle:
    px = Decimal(close)
    ts = datetime.combine(day, datetime.min.time(), tzinfo=IST).replace(hour=9, minute=15)
    return Candle(
        instrument_id=iid, timeframe=Timeframe.D1, ts_open=ts,
        open=px, high=px + Decimal("1"), low=px - Decimal("1"), close=px,
        volume=1000, source="test",
    )


class TestIndexInstrumentNeedsRefresh:
    def test_true_when_no_candles_exist_at_all(self, tmp_path: Path):
        repo = SqliteRepository(tmp_path / "a.db")
        repo.initialize()
        as_of = datetime(2026, 8, 3, 10, 0, tzinfo=IST)
        assert _index_instrument_needs_refresh(repo, "NSE:NIFTY IT", as_of, IST) is True
        repo.close()

    def test_false_when_todays_daily_candle_already_present(self, tmp_path: Path):
        repo = SqliteRepository(tmp_path / "b.db")
        repo.initialize()
        iid = "NSE:NIFTY IT"
        repo.upsert_instrument(
            Instrument(instrument_id=iid, symbol="NIFTY IT", exchange="NSE", series="INDEX", status="ACTIVE")
        )
        as_of = datetime(2026, 8, 3, 10, 0, tzinfo=IST)
        repo.add_candles([_candle(iid, as_of.date())])
        assert _index_instrument_needs_refresh(repo, iid, as_of, IST) is False
        repo.close()

    def test_true_when_only_a_prior_days_candle_is_present(self, tmp_path: Path):
        repo = SqliteRepository(tmp_path / "c.db")
        repo.initialize()
        iid = "NSE:NIFTY IT"
        repo.upsert_instrument(
            Instrument(instrument_id=iid, symbol="NIFTY IT", exchange="NSE", series="INDEX", status="ACTIVE")
        )
        as_of = datetime(2026, 8, 3, 10, 0, tzinfo=IST)
        repo.add_candles([_candle(iid, as_of.date() - timedelta(days=1))])
        assert _index_instrument_needs_refresh(repo, iid, as_of, IST) is True
        repo.close()

    def test_uses_only_the_most_recent_candle(self, tmp_path: Path):
        """A stale run today shouldn't be masked by older history existing —
        only the single most recent candle's date is the freshness signal."""
        repo = SqliteRepository(tmp_path / "d.db")
        repo.initialize()
        iid = "NSE:NIFTY IT"
        repo.upsert_instrument(
            Instrument(instrument_id=iid, symbol="NIFTY IT", exchange="NSE", series="INDEX", status="ACTIVE")
        )
        as_of = datetime(2026, 8, 3, 10, 0, tzinfo=IST)
        repo.add_candles([
            _candle(iid, as_of.date() - timedelta(days=5)),
            _candle(iid, as_of.date() - timedelta(days=1)),
        ])
        assert _index_instrument_needs_refresh(repo, iid, as_of, IST) is True


class TestIndicesToCatchUp:
    def test_below_cap_all_caught_up(self):
        assert _indices_to_catch_up(["NSE:NIFTY IT", "NSE:INDIA VIX"], max_to_catch_up=2) == [
            "NSE:NIFTY IT", "NSE:INDIA VIX",
        ]

    def test_at_cap_all_caught_up(self):
        stale = ["NSE:NIFTY IT", "NSE:NIFTY AUTO"]
        assert _indices_to_catch_up(stale, max_to_catch_up=2) == stale

    def test_above_cap_none_caught_up(self):
        # Owner-reported (2026-08-10): 11 tracked indices/VIX all stale at
        # once (right after market open) must not all be re-ingested
        # synchronously during a single-symbol validate.
        stale = [f"NSE:IDX{i}" for i in range(11)]
        assert _indices_to_catch_up(stale, max_to_catch_up=2) == []

    def test_empty_stale_list(self):
        assert _indices_to_catch_up([], max_to_catch_up=2) == []


def test_validate_symbols_can_skip_unresolved_catalog_misses(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    repo = SqliteRepository(tmp_path / "athena.db")
    repo.initialize()
    SqliteCandidateStore(repo).upsert_candidate(symbol="HFCL", notes="test", active=True)

    def fake_resolve(config_dir, symbols, *, repo_root=None, exchange=None):
        return object(), {}, [str(symbol).upper() for symbol in symbols]

    monkeypatch.setattr("athena.ops.symbol_validate.resolve_against_catalog", fake_resolve)
    as_of = datetime(2026, 9, 7, 15, 30, tzinfo=IST)
    result = validate_symbols(
        repo,
        CONFIG_DIR,
        symbols=["HFCL"],
        as_of=as_of,
        require_all_resolved=False,
    )
    assert result.status == "skipped"
    assert result.skipped_symbols == ("HFCL",)
    with pytest.raises(DataValidationError, match="symbols not in Kite catalog: HFCL"):
        validate_symbols(repo, CONFIG_DIR, symbols=["HFCL"], as_of=as_of)
    repo.close()
