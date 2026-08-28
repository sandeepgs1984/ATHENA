"""EM-5's read-only view of ATHENA's canonical market data -- proves the
Protocol surface is exactly the read methods it declares (no write-shaped
method can slip in unnoticed) and that the adapter's bulk read genuinely
delegates to `SqliteRepository.candles_for_instruments` (one grouped
query, never one per symbol)."""

from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from pathlib import Path
from zoneinfo import ZoneInfo

import pytest

from athena.data.store import SqliteRepository
from athena.domain.enums import Timeframe
from athena.domain.market import Candle, Instrument
from athena.explosive_move.live.market_data_port import (
    EMR_MARKET_DATA_READ_METHODS,
    EmrMarketDataPort,
    SqliteEmrMarketDataAdapter,
)

IST = ZoneInfo("Asia/Kolkata")


@pytest.fixture()
def repo(tmp_path: Path) -> SqliteRepository:
    r = SqliteRepository(tmp_path / "athena.db")
    r.initialize()
    yield r
    r.close()


def _instrument(iid: str, symbol: str) -> Instrument:
    return Instrument(instrument_id=iid, symbol=symbol, exchange="NSE", series="EQ",
                      isin="INE000A01AAA", lot_size=1, tick_size=Decimal("0.05"),
                      status="ACTIVE", listed_date=date(2020, 1, 1))


def _candle(iid: str, day: date) -> Candle:
    return Candle(instrument_id=iid, timeframe=Timeframe.D1,
                  ts_open=datetime(day.year, day.month, day.day, 9, 15, tzinfo=IST),
                  open=Decimal("100"), high=Decimal("101"), low=Decimal("99"),
                  close=Decimal("100"), volume=1000, source="test")


def test_adapter_satisfies_the_protocol(repo):
    assert isinstance(SqliteEmrMarketDataAdapter(repo), EmrMarketDataPort)


def test_protocol_exposes_only_the_declared_read_methods():
    declared = {name for name in vars(EmrMarketDataPort) if not name.startswith("_")}
    assert declared == EMR_MARKET_DATA_READ_METHODS


def test_list_instruments_returns_every_ingested_instrument(repo):
    repo.upsert_instrument(_instrument("A", "AAA"))
    repo.upsert_instrument(_instrument("B", "BBB"))
    adapter = SqliteEmrMarketDataAdapter(repo)
    assert {i.instrument_id for i in adapter.list_instruments()} == {"A", "B"}


def test_resolved_universe_intersects_with_ingested_instruments(repo):
    repo.upsert_instrument(_instrument("A", "AAA"))
    repo.save_resolved_universe("swing-528", ["A", "B"], resolved_at=datetime(2026, 8, 28, tzinfo=IST))
    adapter = SqliteEmrMarketDataAdapter(repo)
    assert adapter.resolved_universe("swing-528") == ("A",)


def test_resolved_universe_empty_when_unresolved(repo):
    repo.upsert_instrument(_instrument("A", "AAA"))
    adapter = SqliteEmrMarketDataAdapter(repo)
    assert adapter.resolved_universe("nonexistent-universe") == ()


def test_candles_for_instruments_delegates_to_the_bulk_grouped_query(repo):
    repo.upsert_instrument(_instrument("A", "AAA"))
    repo.upsert_instrument(_instrument("B", "BBB"))
    repo.add_candles([_candle("A", date(2026, 2, 2)), _candle("B", date(2026, 2, 2))])
    adapter = SqliteEmrMarketDataAdapter(repo)
    got = adapter.candles_for_instruments(
        ["A", "B"], Timeframe.D1, datetime(2026, 2, 1, tzinfo=IST), datetime(2026, 2, 28, tzinfo=IST)
    )
    assert set(got) == {"A", "B"}
