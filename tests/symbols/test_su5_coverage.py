"""SU-5: coverage planning and bounded backfill (ADR-011).

The properties that carry this milestone: **planning fetches nothing**,
**execution is bounded by an explicit limit with no default**, and **one failing
symbol never costs the run**. Each guards against a specific way a discovery
universe could become expensive or dishonest.
"""

from __future__ import annotations

from datetime import date, datetime, timedelta
from decimal import Decimal
from pathlib import Path

import pytest

from athena.data.store.repository import SqliteRepository
from athena.domain.enums import Timeframe
from athena.domain.market import Candle, Instrument
from athena.symbols.coverage import (
    CoverageRequirement,
    execute_backfill,
    plan_coverage,
)
from athena.symbols.universes import load_universes_config

IST_BASE = datetime(2026, 1, 1, 9, 15)
REQUIREMENT = CoverageRequirement(
    timeframe=Timeframe.D1, minimum_bars=10, reason="test fixture"
)


class FakeReader:
    """Records what planning asked for, so 'fetches nothing' is provable."""

    def __init__(self, counts: dict[str, int]) -> None:
        self._counts = counts
        self.calls = 0

    def candle_coverage(self, timeframe, instrument_ids):
        self.calls += 1
        return {i: self._counts.get(i, 0) for i in instrument_ids}


# --------------------------------------------------------------------------- #
# 1. Planning reports; it does not fetch
# --------------------------------------------------------------------------- #


def test_planning_splits_satisfied_from_short():
    reader = FakeReader({"NSE:A": 50, "NSE:B": 3})
    plan = plan_coverage("u", ["NSE:A", "NSE:B", "NSE:C"], REQUIREMENT, reader)
    assert plan.satisfied == ("NSE:A",)
    assert {g.instrument_id for g in plan.gaps} == {"NSE:B", "NSE:C"}
    assert not plan.is_satisfied


def test_a_symbol_with_no_candles_is_a_gap_not_an_omission():
    """Absent from the ledger must not read as absent from the request."""
    plan = plan_coverage("u", ["NSE:NEW"], REQUIREMENT, FakeReader({}))
    assert plan.gaps[0].have == 0
    assert plan.gaps[0].shortfall == 10


def test_planning_reads_once_and_fetches_nothing():
    """A 2,700-symbol universe must not become a network operation because
    somebody asked what was missing."""
    reader = FakeReader({})
    plan_coverage("u", [f"NSE:S{i}" for i in range(500)], REQUIREMENT, reader)
    assert reader.calls == 1, "one bulk read, not one per symbol"


def test_cost_is_estimated_so_the_owner_knows_what_they_are_starting():
    plan = plan_coverage("u", [f"NSE:S{i}" for i in range(100)], REQUIREMENT, FakeReader({}))
    assert plan.estimated_requests == 100
    assert plan.estimated_seconds() == pytest.approx(33.4, rel=0.01)
    assert "100 short" in plan.summary()


def test_a_fully_covered_universe_needs_no_work():
    plan = plan_coverage("u", ["NSE:A"], REQUIREMENT, FakeReader({"NSE:A": 999}))
    assert plan.is_satisfied
    assert plan.estimated_requests == 0


def test_requirement_rejects_a_nonsense_minimum():
    with pytest.raises(ValueError):
        CoverageRequirement(timeframe=Timeframe.D1, minimum_bars=0)


# --------------------------------------------------------------------------- #
# 2. Execution is bounded, and one bad symbol never stops it
# --------------------------------------------------------------------------- #


def _plan(n: int):
    return plan_coverage("u", [f"NSE:S{i:03d}" for i in range(n)], REQUIREMENT, FakeReader({}))


def test_backfill_respects_the_limit_and_reports_what_it_left():
    """A partial run must never look like a complete one."""
    seen: list[str] = []
    outcome = execute_backfill(
        _plan(10),
        fetch=lambda iid, s, e: seen.append(iid) or 5,
        limit=3, end=date(2026, 8, 15), lookback_days=365,
    )
    assert len(seen) == 3
    assert outcome.remaining == 7
    assert len(outcome.filled) == 3


def test_limit_is_required_and_validated():
    """No default: a backfill that silently means 'everything' is how a
    fifteen-minute network operation starts by accident."""
    with pytest.raises(TypeError):
        execute_backfill(_plan(1), fetch=lambda *a: 1, end=date(2026, 8, 15), lookback_days=365)
    with pytest.raises(ValueError):
        execute_backfill(_plan(1), fetch=lambda *a: 1, limit=0,
                         end=date(2026, 8, 15), lookback_days=365)


def test_one_failing_symbol_does_not_stop_the_batch():
    """The owner's standing requirement, asserted at the backfill layer."""
    def fetch(instrument_id, start, end):
        if instrument_id == "NSE:S002":
            raise RuntimeError("delisted")
        return 400

    outcome = execute_backfill(
        _plan(5), fetch=fetch, limit=5, end=date(2026, 8, 15), lookback_days=365
    )
    assert len(outcome.filled) == 4, "every good symbol still filled"
    assert outcome.failed == (("NSE:S002", "RuntimeError: delisted"),)
    assert outcome.remaining == 0


def test_several_failures_are_all_recorded():
    def fetch(instrument_id, start, end):
        if instrument_id in {"NSE:S000", "NSE:S003"}:
            raise ValueError("bad symbol")
        return 100

    outcome = execute_backfill(
        _plan(5), fetch=fetch, limit=5, end=date(2026, 8, 15), lookback_days=365
    )
    assert {i for i, _ in outcome.failed} == {"NSE:S000", "NSE:S003"}
    assert len(outcome.filled) == 3


def test_an_empty_response_is_recorded_rather_than_counted_as_success():
    """A symbol that resolves but has no history is a real situation, and
    counting it as filled would leave a permanent silent gap."""
    outcome = execute_backfill(
        _plan(1), fetch=lambda *a: 0, limit=1, end=date(2026, 8, 15), lookback_days=365
    )
    assert outcome.filled == ()
    assert outcome.failed == (("NSE:S000", "provider returned no candles"),)


def test_the_fetch_window_is_derived_from_lookback():
    windows: list[tuple[date, date]] = []
    execute_backfill(
        _plan(1), fetch=lambda iid, s, e: windows.append((s, e)) or 1,
        limit=1, end=date(2026, 8, 15), lookback_days=365,
    )
    start, end = windows[0]
    assert end == date(2026, 8, 15)
    assert (end - start).days == 364


# --------------------------------------------------------------------------- #
# 3. Against the real repository
# --------------------------------------------------------------------------- #


@pytest.fixture()
def repo(tmp_path: Path) -> SqliteRepository:
    r = SqliteRepository(tmp_path / "athena.db")
    r.initialize()
    yield r
    r.close()


def _seed(repo: SqliteRepository, symbol: str, bars: int) -> None:
    from zoneinfo import ZoneInfo

    ist = ZoneInfo("Asia/Kolkata")
    repo.upsert_instrument(Instrument(
        instrument_id=f"NSE:{symbol}", symbol=symbol, exchange="NSE", series="EQ",
        name=symbol, lot_size=1, tick_size=Decimal("0.05"), status="ACTIVE"))
    repo.add_candles([
        Candle(
            instrument_id=f"NSE:{symbol}", timeframe=Timeframe.D1,
            ts_open=IST_BASE.replace(tzinfo=ist) + timedelta(days=i),
            open=Decimal(100), high=Decimal(101), low=Decimal(99),
            close=Decimal(100), volume=1000, source="test",
        )
        for i in range(bars)
    ])


def test_coverage_counts_come_from_the_real_ledger(repo: SqliteRepository):
    _seed(repo, "RICH", 40)
    _seed(repo, "POOR", 3)
    counts = repo.candle_coverage(Timeframe.D1, ["NSE:RICH", "NSE:POOR", "NSE:NONE"])
    assert counts == {"NSE:RICH": 40, "NSE:POOR": 3, "NSE:NONE": 0}


def test_coverage_chunks_beyond_sqlite_parameter_limits(repo: SqliteRepository):
    """A discovery universe is thousands of symbols; the query must not break
    on SQLite's host-parameter cap."""
    _seed(repo, "REAL", 5)
    ids = [f"NSE:FAKE{i:05d}" for i in range(1500)] + ["NSE:REAL"]
    counts = repo.candle_coverage(Timeframe.D1, ids)
    assert len(counts) == 1501
    assert counts["NSE:REAL"] == 5
    assert counts["NSE:FAKE00000"] == 0


def test_empty_request_is_a_no_op(repo: SqliteRepository):
    assert repo.candle_coverage(Timeframe.D1, []) == {}


def test_planning_against_the_real_repository(repo: SqliteRepository):
    _seed(repo, "RICH", 40)
    _seed(repo, "POOR", 3)
    plan = plan_coverage("u", ["NSE:RICH", "NSE:POOR"], REQUIREMENT, repo)
    assert plan.satisfied == ("NSE:RICH",)
    assert plan.gaps[0].instrument_id == "NSE:POOR" and plan.gaps[0].have == 3


# --------------------------------------------------------------------------- #
# 4. The shipped configuration
# --------------------------------------------------------------------------- #


def test_darvax_declares_coverage_traceable_to_its_own_methodology():
    """A bar count with no stated origin is indistinguishable from a guess.
    400 is DarvaX's own `scan.lookback_bars`, not a number chosen here."""
    import json

    config = load_universes_config(Path(__file__).resolve().parents[2] / "config")
    coverage = config.universes["darvax_discovery"].coverage
    assert coverage is not None
    assert coverage.timeframe == "1d"
    assert "lookback_bars" in coverage.reason

    darvax = json.loads(
        (Path(__file__).resolve().parents[2] / "config" / "darvax.json")
        .read_text(encoding="utf-8")
    )
    declared = darvax.get("scan", {}).get("lookback_bars", 400)
    assert coverage.minimum_bars == declared, (
        "the coverage requirement must track DarvaX's stated lookback"
    )


def test_athena_core_declares_no_coverage():
    """Its symbols are already ingested by the existing cycle; declaring a
    requirement would imply a backfill ATHENA does not need."""
    config = load_universes_config(Path(__file__).resolve().parents[2] / "config")
    assert config.universes["athena_core"].coverage is None
