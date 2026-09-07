"""ID-8: full historical entry/risk outcome validation harness tests.

Pure-function tests use synthetic candle tuples; the harness integration
tests use a temp, disposable SQLite DB seeded via `SqliteRepository`,
never `db/athena.db`.
"""

from __future__ import annotations

import inspect
import tempfile
from datetime import date, datetime, timedelta
from decimal import Decimal
from pathlib import Path
from zoneinfo import ZoneInfo

import pytest

from athena.data import id8_entry_risk_outcome_validation as m
from athena.data.id8_entry_risk_outcome_validation import (
    analyze_forward_outcome,
    build_trade_episodes,
    forward_candles,
)
from athena.data.id6b1_entry_qualification_baseline import ReadOnlyStore
from athena.data.store.repository import SqliteRepository
from athena.domain.enums import Timeframe
from athena.domain.market import Candle, Instrument

IST = ZoneInfo("Asia/Kolkata")


# --------------------------------------------------------------------------- #
# Structural isolation: PHASE A must never import the PHASE B forward reader.
# --------------------------------------------------------------------------- #


def test_phase_a_never_calls_forward_candles() -> None:
    """`_reconstruct_eq_at_checkpoint` and `build_trade_episodes` (PHASE A)
    must never reference `forward_candles` (PHASE B) -- proven by direct
    source scan of each function's own body, not the whole module (which
    legitimately contains both)."""
    for fn in (m.build_trade_episodes, m._reconstruct_eq_at_checkpoint, m._get_decision):
        src = inspect.getsource(fn)
        assert "forward_candles(" not in src
        assert "analyze_forward_outcome(" not in src


def test_no_save_calls_in_module_source() -> None:
    source = inspect.getsource(m)
    assert "save_entry_qualification(" not in source
    assert "save_entry_actionability(" not in source
    assert "INSERT INTO" not in source


def test_no_provider_network_calls_in_module_source() -> None:
    source = inspect.getsource(m)
    lowered = source.lower()
    for forbidden in ("kite", "requests.", "httpx.", "urllib.request"):
        assert forbidden not in lowered


def test_long_and_short_summarized_in_separate_blocks() -> None:
    """Owner correction #1/#15: `_summarize` must never combine LONG and
    SHORT into one denominator -- proven directly on synthetic
    observations without needing a full harness run."""
    long_obs = [{"direction": "LONG", "session_date": "2026-08-13", "terminal": "INSUFFICIENT_FORWARD_DATA"}]
    short_obs = [
        {"direction": "SHORT", "session_date": "2026-09-07", "terminal": "INSUFFICIENT_FORWARD_DATA"},
        {"direction": "SHORT", "session_date": "2026-09-07", "terminal": "INSUFFICIENT_FORWARD_DATA"},
    ]
    summary = m._summarize(
        episode_report={"total_decisions": 3, "total_episodes": 3, "accounted_rows": 3, "reconciles": True, "episodes": []},
        direction_counts_episodes={"LONG": 1, "SHORT": 2}, qualified_count=3,
        observations=long_obs + short_obs, defects=[], unexpected=[], rows_attempted=3,
        db_path=Path("x"), schema_version_start=18, schema_version_end=18, started=0.0,
        output_dir=Path(tempfile.mkdtemp()),
    )
    assert summary["primary_LONG"]["n"] == 1
    assert summary["replayed_SHORT_diagnostic"]["n"] == 2
    # The denominator for any LONG rate must never include the 2 SHORT rows.
    assert summary["primary_LONG"]["n"] != summary["direction_distribution_observations"].get("LONG", 0) + \
        summary["direction_distribution_observations"].get("SHORT", 0)


# --------------------------------------------------------------------------- #
# Pure-function tests: forward-window leak safety
# --------------------------------------------------------------------------- #


class _FakeConn:
    def __init__(self, rows):
        self._rows = rows
        self.captured_sql = None
        self.captured_params = None

    def execute(self, sql, params=()):
        self.captured_sql = sql
        self.captured_params = params
        return self

    def fetchall(self):
        return self._rows


class _FakeStore:
    def __init__(self, rows):
        self.conn = _FakeConn(rows)


def test_forward_candles_uses_direct_filter_never_limit() -> None:
    store = _FakeStore([("2026-08-13T10:20:00+05:30", 101, 99, 100)])
    forward_candles(
        store, instrument_id="NSE:X", session_date="2026-08-13",
        after_ts_open="2026-08-13T10:15:00+05:30", session_close_ts=None,
    )
    sql = store.conn.captured_sql
    assert "LIMIT" not in sql.upper()
    assert "ts_open>?" in sql
    assert "substr(ts_open,1,10)=?" in sql


def test_forward_candles_excludes_post_close_bar() -> None:
    """Owner correction #3: a canonical session-close upper bound must
    exclude a bar whose own completion instant falls after it, even
    though it shares the same calendar date as in-session bars."""
    in_session = "2026-08-13T15:20:00+05:30"  # completes 15:25, before a 15:30 close
    after_close = "2026-08-13T15:30:00+05:30"  # completes 15:35, AFTER a 15:30 close
    store = _FakeStore([
        (in_session, 101, 99, 100),
        (after_close, 200, 198, 199),
    ])
    close_ts = datetime(2026, 8, 13, 15, 30, tzinfo=IST)
    result = forward_candles(
        store, instrument_id="NSE:X", session_date="2026-08-13",
        after_ts_open="2026-08-13T15:00:00+05:30", session_close_ts=close_ts,
    )
    assert len(result) == 1
    assert result[0][0] == in_session


def test_forward_candles_boundary_bar_completing_exactly_at_close_is_included() -> None:
    """A bar whose completion is exactly AT the canonical close (e.g. a
    15:25 bar completing at 15:30 for a 15:30 close) is the last
    legitimately eligible bar -- must not be excluded by an off-by-one."""
    boundary_bar = "2026-08-13T15:25:00+05:30"  # completes exactly at 15:30
    store = _FakeStore([(boundary_bar, 101, 99, 100)])
    close_ts = datetime(2026, 8, 13, 15, 30, tzinfo=IST)
    result = forward_candles(
        store, instrument_id="NSE:X", session_date="2026-08-13",
        after_ts_open="2026-08-13T15:00:00+05:30", session_close_ts=close_ts,
    )
    assert len(result) == 1


def test_build_trade_episodes_breaks_on_intervening_non_trade_row() -> None:
    """The exact bug this module's own docstring documents fixing: an
    episode builder that pre-filters to decision_type=TRADE before
    grouping can never detect an intervening WATCH row, over-merging
    episodes. This test seeds the full timeline (TRADE, TRADE, WATCH,
    TRADE, TRADE) for one instrument/session and proves two separate
    2-length episodes are produced, not one 4-length episode."""
    class Row:
        def __init__(self, decision_id, ts, instrument_id, direction, decision_type):
            self._t = (decision_id, ts, instrument_id, direction, decision_type)

        def __iter__(self):
            return iter(self._t)

        def __getitem__(self, i):
            return self._t[i]

    rows = [
        Row("d1", "2026-08-13T09:30:00+05:30", "NSE:X", "LONG", "TRADE"),
        Row("d2", "2026-08-13T09:35:00+05:30", "NSE:X", "LONG", "TRADE"),
        Row("w1", "2026-08-13T09:40:00+05:30", "NSE:X", "NONE", "WATCH"),
        Row("d3", "2026-08-13T09:45:00+05:30", "NSE:X", "LONG", "TRADE"),
        Row("d4", "2026-08-13T09:50:00+05:30", "NSE:X", "LONG", "TRADE"),
    ]
    store = _FakeStore(rows)
    report = build_trade_episodes(store, decision_type="TRADE")
    assert report["total_decisions"] == 4
    assert report["total_episodes"] == 2
    assert report["accounted_rows"] == 4
    assert report["reconciles"] is True
    lengths = sorted(e["episode_length"] for e in report["episodes"])
    assert lengths == [2, 2]
    assert report["episodes"][0]["first_decision_id"] == "d1"
    assert report["episodes"][1]["first_decision_id"] == "d3"


def test_build_trade_episodes_session_change_breaks_episode() -> None:
    class Row:
        def __init__(self, t):
            self._t = t

        def __iter__(self):
            return iter(self._t)

        def __getitem__(self, i):
            return self._t[i]

    rows = [
        Row(("d1", "2026-08-13T09:30:00+05:30", "NSE:X", "LONG", "TRADE")),
        Row(("d2", "2026-08-14T09:30:00+05:30", "NSE:X", "LONG", "TRADE")),
    ]
    store = _FakeStore(rows)
    report = build_trade_episodes(store, decision_type="TRADE")
    assert report["total_episodes"] == 2
    assert report["reconciles"] is True


# --------------------------------------------------------------------------- #
# Harness integration: real disposable temp DB
# --------------------------------------------------------------------------- #


def _seed_candles(repo, instrument_id: str, day: date, closes: list[float]) -> None:
    candles = []
    for i, close in enumerate(closes):
        ts = datetime.combine(day, datetime.min.time(), tzinfo=IST).replace(hour=9, minute=15)
        ts += timedelta(minutes=5 * i)
        px = Decimal(str(close))
        candles.append(Candle(
            instrument_id=instrument_id, timeframe=Timeframe.M5, ts_open=ts,
            open=px, high=px + Decimal("0.5"), low=px - Decimal("0.5"), close=px,
            volume=10_000, source="test",
        ))
    repo.add_candles(candles)


@pytest.fixture()
def seeded_forward_db(tmp_path: Path) -> Path:
    """A real, disposable SQLite DB (never `db/athena.db`) with a real
    TRADE decision and a real, hand-built M5 forward path that reaches
    +1% at a known bar -- proves the full analyze_forward_outcome path
    end-to-end against real repository-persisted candles."""
    db_path = tmp_path / "athena.db"
    repo = SqliteRepository(db_path)
    repo.initialize()
    iid = "NSE:AAA"
    repo.upsert_instrument(Instrument(instrument_id=iid, symbol="AAA", exchange="NSE", series="EQ", status="ACTIVE"))
    day = date(2026, 8, 13)
    # Entry at bar index 0 (close=100); forward bars rise to 101.5 (+1.5%) at index 3.
    closes = [100.0, 100.2, 100.6, 101.5, 101.2, 100.9]
    _seed_candles(repo, iid, day, closes)
    repo.close()
    return db_path


def _call(store, *, instrument_id, session_date, entry_ts_open, entry_price, direction,
          checkpoint_vwap=None, or15_lvl=None, atr_lvl=None, session_close_ts=None):
    return analyze_forward_outcome(
        store=store, indicator_engine=None, instrument_id=instrument_id, session_date=session_date,
        entry_ts_open=entry_ts_open, entry_price=entry_price, direction=direction,
        checkpoint_vwap=checkpoint_vwap, or15_lvl=or15_lvl, atr_lvl=atr_lvl,
        session_close_ts=session_close_ts,
    )


def test_analyze_forward_outcome_long_reaches_targets(seeded_forward_db: Path) -> None:
    store = ReadOnlyStore(seeded_forward_db)
    outcome = _call(
        store, instrument_id="NSE:AAA", session_date="2026-08-13",
        entry_ts_open=datetime(2026, 8, 13, 9, 15, tzinfo=IST).isoformat(), entry_price=Decimal("100"),
        direction="LONG",
    )
    store.close()
    assert outcome is not None
    assert outcome["forward_bars"] == 5
    assert outcome["t1_intrabar_min"] is not None  # +1% -> 101, reached by bar with high 101.5+0.5
    assert outcome["t2_intrabar_min"] is not None  # +1.5% -> 101.5
    assert outcome["valid_geometry"] is False  # no VWAP supplied
    # No valid geometry -> no VWAP-vs-target ordering claim is possible.
    assert outcome["terminal"] is None


def test_analyze_forward_outcome_short_direction_signs_correctly(seeded_forward_db: Path) -> None:
    """A falling path for a SHORT position -- MFE/MAE and target direction
    must flip correctly relative to the LONG case above."""
    db_path = seeded_forward_db.parent / "athena_short.db"
    repo = SqliteRepository(db_path)
    repo.initialize()
    iid = "NSE:BBB"
    repo.upsert_instrument(Instrument(instrument_id=iid, symbol="BBB", exchange="NSE", series="EQ", status="ACTIVE"))
    day = date(2026, 8, 13)
    closes = [100.0, 99.8, 99.4, 98.5, 98.8, 99.1]  # falls to -1.5% at index 3
    _seed_candles(repo, iid, day, closes)
    repo.close()

    store = ReadOnlyStore(db_path)
    outcome = _call(
        store, instrument_id=iid, session_date="2026-08-13",
        entry_ts_open=datetime(2026, 8, 13, 9, 15, tzinfo=IST).isoformat(), entry_price=Decimal("100"),
        direction="SHORT",
    )
    store.close()
    assert outcome is not None
    assert outcome["t1_intrabar_min"] is not None
    assert outcome["t2_intrabar_min"] is not None
    assert outcome["mfe_pct"] > 0  # price fell -> favorable for SHORT


def test_analyze_forward_outcome_no_forward_data_returns_none(seeded_forward_db: Path) -> None:
    store = ReadOnlyStore(seeded_forward_db)
    outcome = _call(
        store, instrument_id="NSE:AAA", session_date="2026-08-13",
        entry_ts_open=datetime(2026, 8, 13, 9, 40, tzinfo=IST).isoformat(),  # last real bar
        entry_price=Decimal("100"), direction="LONG",
    )
    store.close()
    assert outcome is None


def test_target_touch_direction_matches_frozen_contract() -> None:
    """Direct proof the corrected §24 direction is implemented: a LONG
    target uses `high>=target`, a SHORT target uses `low<=target` -- a
    candle whose only extreme in the *wrong* direction reaches the naive
    mirror level must NOT register a hit."""
    with tempfile.TemporaryDirectory() as td:
        db_path = Path(td) / "athena.db"
        repo = SqliteRepository(db_path)
        repo.initialize()
        iid = "NSE:CCC"
        repo.upsert_instrument(Instrument(instrument_id=iid, symbol="CCC", exchange="NSE", series="EQ", status="ACTIVE"))
        day = date(2026, 8, 13)
        ts0 = datetime.combine(day, datetime.min.time(), tzinfo=IST).replace(hour=9, minute=15)
        entry_candle = Candle(instrument_id=iid, timeframe=Timeframe.M5, ts_open=ts0,
                               open=Decimal("100"), high=Decimal("100"), low=Decimal("100"),
                               close=Decimal("100"), volume=1000, source="test")
        forward_candle = Candle(instrument_id=iid, timeframe=Timeframe.M5, ts_open=ts0 + timedelta(minutes=5),
                                 open=Decimal("99.5"), high=Decimal("100.3"), low=Decimal("99.0"),
                                 close=Decimal("99.8"), volume=1000, source="test")
        repo.add_candles([entry_candle, forward_candle])
        repo.close()

        store = ReadOnlyStore(db_path)
        outcome = _call(
            store, instrument_id=iid, session_date="2026-08-13",
            entry_ts_open=ts0.isoformat(), entry_price=Decimal("100"), direction="LONG",
        )
        store.close()
        assert outcome is not None
        assert outcome["t1_intrabar_min"] is None  # high=100.3 never reaches 101 -- correctly NOT hit


def test_invalid_geometry_never_produces_a_terminal_ordering() -> None:
    """Owner correction #5: an observation with invalid initial VWAP
    geometry (VWAP on the wrong side for its own direction) must never
    contribute a TARGET_SIDE_NO_LATER_THAN_INVALIDATION/INVALIDATION_FIRST
    claim -- `terminal` must be `None`, even though T1 is genuinely
    reached, because there is no valid invalidation to order it against."""
    with tempfile.TemporaryDirectory() as td:
        db_path = Path(td) / "athena.db"
        repo = SqliteRepository(db_path)
        repo.initialize()
        iid = "NSE:DDD"
        repo.upsert_instrument(Instrument(instrument_id=iid, symbol="DDD", exchange="NSE", series="EQ", status="ACTIVE"))
        day = date(2026, 8, 13)
        closes = [100.0, 100.2, 100.6, 101.5]
        _seed_candles(repo, iid, day, closes)
        repo.close()

        store = ReadOnlyStore(db_path)
        # LONG with VWAP ABOVE entry -- invalid geometry for a LONG.
        outcome = _call(
            store, instrument_id=iid, session_date="2026-08-13",
            entry_ts_open=datetime(2026, 8, 13, 9, 15, tzinfo=IST).isoformat(), entry_price=Decimal("100"),
            direction="LONG", checkpoint_vwap=Decimal("105"),
        )
        store.close()
        assert outcome is not None
        assert outcome["valid_geometry"] is False
        assert outcome["t1_intrabar_min"] is not None  # T1 genuinely reached
        assert outcome["terminal"] is None  # but no ordering claim is made
        assert outcome["vwap_loss_min"] is None  # VWAP-loss is never evaluated without valid geometry


def test_run_full_study_never_mutates_source_db(seeded_forward_db: Path) -> None:
    before = seeded_forward_db.read_bytes()
    store = ReadOnlyStore(seeded_forward_db)
    build_trade_episodes(store, decision_type="TRADE")
    store.close()
    after = seeded_forward_db.read_bytes()
    assert before == after


def test_terminal_ordering_labels_never_include_ambiguous_same_bar() -> None:
    """§32/§54's corrected same-bar policy: target-vs-VWAP-loss ordering
    never uses AMBIGUOUS_SAME_BAR (structurally proven unreachable for
    that specific pairing) -- the label is reserved exclusively for the
    OR15 intrabar comparator's own separate ambiguity tracking."""
    source = inspect.getsource(m.analyze_forward_outcome)
    assert "AMBIGUOUS_SAME_BAR" not in source
    assert '"terminal"' in inspect.getsource(m)


def test_or15_ambiguous_with_t1_when_both_intrabar_same_bar() -> None:
    """A single forward bar whose high/low crosses BOTH the LONG T1 level
    and the OR15-boundary level (both intrabar barriers) must be flagged
    `or15_ambiguous_with_t1` -- genuine OHLC-level ambiguity, unlike the
    target-vs-VWAP-loss pairing."""
    with tempfile.TemporaryDirectory() as td:
        db_path = Path(td) / "athena.db"
        repo = SqliteRepository(db_path)
        repo.initialize()
        iid = "NSE:EEE"
        repo.upsert_instrument(Instrument(instrument_id=iid, symbol="EEE", exchange="NSE", series="EQ", status="ACTIVE"))
        day = date(2026, 8, 13)
        ts0 = datetime.combine(day, datetime.min.time(), tzinfo=IST).replace(hour=9, minute=15)
        entry_candle = Candle(instrument_id=iid, timeframe=Timeframe.M5, ts_open=ts0,
                               open=Decimal("100"), high=Decimal("100"), low=Decimal("100"),
                               close=Decimal("100"), volume=1000, source="test")
        # One forward bar whose range [98, 102] crosses both T1 (101, LONG)
        # and a hypothetical OR15 level (98, LONG support) in the same bar.
        forward_candle = Candle(instrument_id=iid, timeframe=Timeframe.M5, ts_open=ts0 + timedelta(minutes=5),
                                 open=Decimal("100"), high=Decimal("102"), low=Decimal("98"),
                                 close=Decimal("101.2"), volume=1000, source="test")
        repo.add_candles([entry_candle, forward_candle])
        repo.close()

        store = ReadOnlyStore(db_path)
        outcome = _call(
            store, instrument_id=iid, session_date="2026-08-13",
            entry_ts_open=ts0.isoformat(), entry_price=Decimal("100"), direction="LONG",
            or15_lvl=Decimal("98"),
        )
        store.close()
        assert outcome is not None
        assert outcome["or15_intrabar_min"] is not None
        assert outcome["t1_intrabar_min"] is not None
        assert outcome["or15_ambiguous_with_t1"] is True


def test_session_block_bootstrap_is_deterministic() -> None:
    obs = [
        {"session_date": f"2026-08-{d:02d}", "terminal": "TARGET_SIDE_NO_LATER_THAN_INVALIDATION" if i % 2 else "INVALIDATION_FIRST", "t1_intrabar_min": 10.0 if i % 2 else None}
        for i, d in enumerate(range(10, 20))
    ]
    r1 = m._session_block_bootstrap(obs, metric_fn=lambda rows: m._rate(rows, "t1_intrabar_min"))
    r2 = m._session_block_bootstrap(obs, metric_fn=lambda rows: m._rate(rows, "t1_intrabar_min"))
    assert r1 == r2


def test_d1_atr_level_direction_aware() -> None:
    long_level = m._d1_atr_level(Decimal("2"), Decimal("100"), "LONG")
    short_level = m._d1_atr_level(Decimal("2"), Decimal("100"), "SHORT")
    assert long_level == Decimal("98")
    assert short_level == Decimal("102")
    assert m._d1_atr_level(None, Decimal("100"), "LONG") is None
