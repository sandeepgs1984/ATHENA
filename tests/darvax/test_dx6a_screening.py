"""DX-6a: screening engine, eligibility taxonomy, and screen persistence.

The engine is pure — no clock, no config, no IO — so these are hand-worked
fixtures with exact expected values rather than tolerance checks.

The load-bearing assertion in this file is that **no conviction score exists**.
Everything else is mechanics; that one is the design commitment ADR-010
Amendment 2 was accepted on.
"""

from __future__ import annotations

from datetime import datetime, timedelta
from decimal import Decimal
from pathlib import Path
from zoneinfo import ZoneInfo

import pytest

from athena.darvax.screening import (
    TIER_ORDER,
    DarvaxTier,
    ScreenResult,
    SweepRecord,
    box_height_pct,
    distance_to_trigger_pct,
    rank_tier,
    screen_signal,
    screen_signals,
    tier_counts,
    tier_for,
)
from athena.darvax.signals.models import (
    DarvasRule,
    DarvaxSignal,
    DarvaxSignalType,
)
from athena.darvax.store.repository import DarvaxRepository
from athena.darvax.store.schema import DARVAX_SCHEMA_VERSION

IST = ZoneInfo("Asia/Kolkata")
AS_OF = datetime(2026, 8, 13, 15, 30, tzinfo=IST)


def make_signal(
    symbol: str,
    signal_type: DarvaxSignalType,
    *,
    close: str,
    box_top: str | None = None,
    box_bottom: str | None = None,
    trigger: str | None = None,
    rule: DarvasRule | None = None,
) -> DarvaxSignal:
    return DarvaxSignal(
        signal_id=f"{symbol}-20260813",
        instrument_id=f"NSE:{symbol}",
        as_of=AS_OF,
        signal_type=signal_type,
        darvas_rule=rule,
        close=Decimal(close),
        explanation=f"{symbol} explanation computed by the engine",
        evidence=(),
        methodology_digest="a1f09c33be27d410",
        darvax_version="0.1.0",
        box_top=Decimal(box_top) if box_top else None,
        box_bottom=Decimal(box_bottom) if box_bottom else None,
        trigger_price=Decimal(trigger) if trigger else None,
    )


# --------------------------------------------------------------------------- #
# 1. The taxonomy is total and derived from the DAR-CARD rules
# --------------------------------------------------------------------------- #


@pytest.mark.parametrize(
    ("signal_type", "expected"),
    [
        (DarvaxSignalType.BREAKOUT, DarvaxTier.ACTIONABLE),
        (DarvaxSignalType.BREAKOUT_RETEST, DarvaxTier.ACTIONABLE),
        (DarvaxSignalType.INSIDE_TOPMOST_BOX, DarvaxTier.WATCH),
        (DarvaxSignalType.BELOW_BOX_BOTTOM, DarvaxTier.EXIT_RELEVANT),
        (DarvaxSignalType.NOT_IN_TOPMOST_BOX, DarvaxTier.NOT_ELIGIBLE),
        (DarvaxSignalType.NO_BOX, DarvaxTier.NOT_ELIGIBLE),
    ],
)
def test_every_signal_type_maps_to_its_dar_card_tier(signal_type, expected):
    assert tier_for(signal_type) is expected


def test_taxonomy_covers_every_state_the_engine_can_emit():
    """A new signal type must be classified deliberately. If this fails, the
    DX-3 engine gained a state and the screener would silently drop it."""
    for signal_type in DarvaxSignalType:
        assert tier_for(signal_type) in TIER_ORDER


# --------------------------------------------------------------------------- #
# 2. The measurements are exact
# --------------------------------------------------------------------------- #


def test_distance_to_trigger_is_a_percentage_of_close():
    # trigger 2902.50 vs close 2894.00 -> +0.293710...%
    signal = make_signal(
        "BSE", DarvaxSignalType.INSIDE_TOPMOST_BOX,
        close="2894.00", box_top="2915", box_bottom="2710", trigger="2902.50",
    )
    got = distance_to_trigger_pct(signal)
    assert got is not None
    assert got.quantize(Decimal("0.0001")) == Decimal("0.2937")


def test_distance_is_negative_once_price_is_through_the_trigger():
    """Negative is information — price has already cleared the entry — not an
    error state, so it must not be clamped to zero."""
    signal = make_signal(
        "TVSMOTOR", DarvaxSignalType.BREAKOUT,
        close="3841.20", box_top="3807.90", box_bottom="3620", trigger="3835.00",
    )
    got = distance_to_trigger_pct(signal)
    assert got is not None and got < 0


def test_box_height_is_a_percentage_of_the_floor():
    # (3807.90 - 3620) / 3620 * 100 = 5.1906...%
    signal = make_signal(
        "TVSMOTOR", DarvaxSignalType.BREAKOUT,
        close="3841.20", box_top="3807.90", box_bottom="3620", trigger="3835.00",
    )
    got = box_height_pct(signal)
    assert got is not None
    assert got.quantize(Decimal("0.0001")) == Decimal("5.1906")


def test_measurements_are_none_when_their_inputs_are_absent():
    """NO_BOX carries no box and no trigger. Reporting 0.0 would read as
    'right at the trigger' — the most misleading possible value."""
    signal = make_signal("NMDC", DarvaxSignalType.NO_BOX, close="71.85")
    assert distance_to_trigger_pct(signal) is None
    assert box_height_pct(signal) is None
    result = screen_signal(signal, sweep_id="swp-1")
    assert result.distance_to_trigger_pct is None
    assert result.box_height_pct is None


def test_watch_signals_rank_on_the_box_ceiling_when_they_have_no_trigger():
    """The defect a live 528-instrument sweep exposed.

    DX-3 sets ``trigger_price`` only alongside a stop, so no INSIDE_TOPMOST_BOX
    signal has one — and ranking on the trigger alone left the entire WATCH
    tier, the breakout candidates, ordered alphabetically. Distance-to-breakout
    falls back to the box ceiling, which is also the more faithful reference:
    rule B is literally "a move above the topmost box top is a BUY".
    """
    inside = make_signal(
        "BSE", DarvaxSignalType.INSIDE_TOPMOST_BOX,
        close="100", box_top="110", box_bottom="90",
    )
    assert distance_to_trigger_pct(inside) is None, "precondition: no trigger"

    result = screen_signal(inside, sweep_id="swp-1")
    assert result.distance_to_breakout_pct == Decimal("10.0000")
    assert result.breakout_reference == "box_top"


def test_distance_to_breakout_prefers_the_trigger_when_one_exists():
    signal = make_signal(
        "TVS", DarvaxSignalType.BREAKOUT,
        close="100", box_top="98", box_bottom="90", trigger="102",
    )
    result = screen_signal(signal, sweep_id="swp-1")
    assert result.distance_to_breakout_pct == Decimal("2.0000")
    assert result.breakout_reference == "trigger_price"


def test_watch_tier_is_not_ordered_alphabetically():
    """Direct regression guard on the live defect: a screen ordered by symbol
    is no ranking at all."""
    signals = [
        make_signal("AAA", DarvaxSignalType.INSIDE_TOPMOST_BOX,
                    close="100", box_top="150", box_bottom="90"),   # 50% away
        make_signal("ZZZ", DarvaxSignalType.INSIDE_TOPMOST_BOX,
                    close="100", box_top="101", box_bottom="90"),   # 1% away
    ]
    ranked = rank_tier(screen_signal(s, sweep_id="s") for s in signals)
    assert [r.instrument_id for r in ranked] == ["NSE:ZZZ", "NSE:AAA"]


def test_percentages_are_quantised_to_four_places():
    """A live screen emitted ``10.44041450777202072538860104`` for a box height
    — 28 significant digits of precision the measurement does not have."""
    signal = make_signal(
        "X", DarvaxSignalType.INSIDE_TOPMOST_BOX,
        close="193", box_top="213", box_bottom="193",
    )
    height = box_height_pct(signal)
    assert height is not None
    assert height.as_tuple().exponent == -4, f"unquantised: {height}"
    assert len(str(height)) <= 12


def test_measurements_stay_decimal_never_float():
    """Percentages feed a persisted, replayable screen; binary floats would make
    a round trip lossy."""
    signal = make_signal(
        "CDSL", DarvaxSignalType.INSIDE_TOPMOST_BOX,
        close="1842.50", box_top="1880", box_bottom="1748", trigger="1862.00",
    )
    assert isinstance(distance_to_trigger_pct(signal), Decimal)
    assert isinstance(box_height_pct(signal), Decimal)


def test_zero_or_negative_denominators_do_not_raise():
    """Defensive: a zero close or floor must yield None, not ZeroDivisionError
    that would fail an entire universe sweep over one bad row."""
    broken = make_signal(
        "ZERO", DarvaxSignalType.INSIDE_TOPMOST_BOX,
        close="0", box_top="10", box_bottom="0", trigger="5",
    )
    assert distance_to_trigger_pct(broken) is None
    assert box_height_pct(broken) is None


# --------------------------------------------------------------------------- #
# 3. Ranking: closest to breaking out first, deterministic, no hidden index
# --------------------------------------------------------------------------- #


def _watch(symbol: str, close: str, trigger: str) -> DarvaxSignal:
    return make_signal(
        symbol, DarvaxSignalType.INSIDE_TOPMOST_BOX,
        close=close, box_top="9999", box_bottom="1", trigger=trigger,
        rule=DarvasRule.A_HOLD_WHILE_IN_TOPMOST_BOX,
    )


def test_watch_tier_orders_closest_to_trigger_first():
    signals = [
        _watch("FAR", "100", "110"),     # +10%
        _watch("NEAR", "100", "101"),    # +1%
        _watch("MID", "100", "105"),     # +5%
    ]
    ranked = rank_tier(screen_signal(s, sweep_id="swp-1") for s in signals)
    assert [r.instrument_id for r in ranked] == ["NSE:NEAR", "NSE:MID", "NSE:FAR"]
    assert [r.rank for r in ranked] == [1, 2, 3]


def test_results_without_a_trigger_sort_last_not_first():
    """A missing distance must not be treated as zero, which would put
    unmeasurable rows at the very top of the screen."""
    signals = [
        make_signal("NOTRIG", DarvaxSignalType.INSIDE_TOPMOST_BOX,
                    close="100", box_top="120", box_bottom="90"),
        _watch("HASTRIG", "100", "108"),
    ]
    ranked = rank_tier(screen_signal(s, sweep_id="swp-1") for s in signals)
    assert [r.instrument_id for r in ranked] == ["NSE:HASTRIG", "NSE:NOTRIG"]


def test_ordering_is_deterministic_on_ties():
    """Equal distances must break by instrument id, so two runs over the same
    signals always produce the same screen — replayability, not aesthetics."""
    signals = [_watch("ZZZ", "100", "105"), _watch("AAA", "100", "105")]
    first = rank_tier(screen_signal(s, sweep_id="s") for s in signals)
    second = rank_tier(screen_signal(s, sweep_id="s") for s in reversed(signals))
    assert [r.instrument_id for r in first] == [r.instrument_id for r in second]
    assert [r.instrument_id for r in first] == ["NSE:AAA", "NSE:ZZZ"]


def test_ranks_are_per_tier_not_global():
    results = screen_signals(
        [
            make_signal("BRK", DarvaxSignalType.BREAKOUT, close="110",
                        box_top="100", box_bottom="90", trigger="105"),
            _watch("WCH", "100", "104"),
        ],
        sweep_id="swp-1",
    )
    by_tier = {r.tier: r for r in results}
    assert by_tier[DarvaxTier.ACTIONABLE].rank == 1
    assert by_tier[DarvaxTier.WATCH].rank == 1


def test_screen_signals_returns_tiers_in_precedence_order():
    results = screen_signals(
        [
            make_signal("D", DarvaxSignalType.NOT_IN_TOPMOST_BOX, close="10"),
            make_signal("C", DarvaxSignalType.BELOW_BOX_BOTTOM, close="10",
                        box_top="20", box_bottom="15"),
            _watch("A", "100", "104"),
            make_signal("B", DarvaxSignalType.BREAKOUT, close="110",
                        box_top="100", box_bottom="90", trigger="105"),
        ],
        sweep_id="swp-1",
    )
    seen = [r.tier for r in results]
    assert seen == [
        DarvaxTier.ACTIONABLE,
        DarvaxTier.WATCH,
        DarvaxTier.EXIT_RELEVANT,
        DarvaxTier.NOT_ELIGIBLE,
    ]


def test_tier_counts_include_empty_tiers():
    """'No actionable names today' is a real answer the owner must see stated,
    not a missing key that renders as blank."""
    counts = tier_counts(screen_signals([_watch("A", "100", "104")], sweep_id="s"))
    assert counts[DarvaxTier.WATCH] == 1
    assert counts[DarvaxTier.ACTIONABLE] == 0
    assert set(counts) == set(TIER_ORDER)


# --------------------------------------------------------------------------- #
# 4. The design commitment: classification, never a score
# --------------------------------------------------------------------------- #


def test_no_composite_conviction_score_exists_anywhere():
    """ADR-010 Amendment 2 forbids a blended index: the methodology ships no
    backtest evidence, so a 0-100 number would manufacture precision it cannot
    support. Ranking quantities stay individually named and separately shown."""
    fields = set(ScreenResult.__dataclass_fields__)
    for banned in ("score", "conviction", "confidence", "strength", "grade", "rating"):
        assert not any(banned in f.lower() for f in fields), (
            f"ScreenResult gained a {banned!r}-like field; eligibility is a "
            "classification, not a score (ADR-010 Amendment 2)"
        )

    source = Path(
        "src/athena/darvax/screening/engine.py"
    ).read_text(encoding="utf-8")
    assert "def score" not in source


def test_screen_result_carries_the_persisted_explanation_not_a_new_one():
    """ADR-005: the screener renders the engine's rationale, never its own."""
    signal = make_signal("BSE", DarvaxSignalType.INSIDE_TOPMOST_BOX,
                         close="100", box_top="120", box_bottom="90", trigger="104")
    result = screen_signal(signal, sweep_id="swp-1")
    assert result.explanation == signal.explanation


# --------------------------------------------------------------------------- #
# 5. Persistence — schema v3, round trips, idempotency
# --------------------------------------------------------------------------- #


@pytest.fixture()
def store(tmp_path: Path) -> DarvaxRepository:
    repo = DarvaxRepository(tmp_path / "darvax.db")
    repo.initialize()
    yield repo
    repo.close()


def test_schema_version_is_recorded_and_covers_the_screener_tables(
    store: DarvaxRepository,
):
    """Asserted as an invariant, not against a literal — pinning the number is
    what made the DX-3 equivalent break on this milestone's own schema bump."""
    assert store.schema_version() == DARVAX_SCHEMA_VERSION
    assert DARVAX_SCHEMA_VERSION >= 3, "DX-6a introduced the screener tables at v3"
    store.save_sweep(_sweep())
    assert store.get_sweep("swp-1") is not None


def test_added_columns_are_applied_to_an_already_created_database(tmp_path: Path):
    """`CREATE TABLE IF NOT EXISTS` is a no-op on an existing table, so a v3
    database would silently lack the v4 columns without an ALTER step.

    Simulates the owner's real situation: a database created before DX-6b.
    """
    import sqlite3

    db = tmp_path / "legacy.db"
    conn = sqlite3.connect(db)
    conn.execute("CREATE TABLE darvax_schema_version (version INTEGER NOT NULL)")
    conn.execute("INSERT INTO darvax_schema_version(version) VALUES (3)")
    # The v3 shape: no distance_to_breakout_pct, no breakout_reference.
    conn.execute(
        "CREATE TABLE darvax_screen_results ("
        "sweep_id TEXT NOT NULL, instrument_id TEXT NOT NULL, signal_id TEXT NOT NULL,"
        "tier TEXT NOT NULL, signal_type TEXT NOT NULL, darvas_rule TEXT,"
        "rank INTEGER NOT NULL, close TEXT NOT NULL, box_top TEXT, box_bottom TEXT,"
        "trigger_price TEXT, distance_to_trigger_pct TEXT, box_height_pct TEXT,"
        "explanation TEXT NOT NULL, PRIMARY KEY (sweep_id, instrument_id))"
    )
    conn.commit()
    conn.close()

    repo = DarvaxRepository(db)
    repo.initialize()
    try:
        assert repo.schema_version() == DARVAX_SCHEMA_VERSION
        # A round trip proves the columns are really usable, not just present.
        repo.save_sweep(_sweep())
        repo.save_screen_results(
            screen_signals([_watch("BSE", "100", "104")], sweep_id="swp-1")
        )
        stored = repo.list_screen_results("swp-1")
        assert stored[0].distance_to_breakout_pct is not None
        assert stored[0].breakout_reference == "trigger_price"
    finally:
        repo.close()


def _sweep(sweep_id: str = "swp-1", **over) -> SweepRecord:
    base = {
        "sweep_id": sweep_id,
        "started_at": AS_OF,
        "state": "completed",
        "methodology_digest": "a1f09c33be27d410",
        "darvax_version": "0.1.0",
        "requested": 528,
        "evaluated": 522,
        "tier_counts": dict.fromkeys(TIER_ORDER, 0),
        "skipped": (("NSE:SUZLON", "insufficient candles"),),
        "finished_at": AS_OF + timedelta(seconds=41),
        "as_of": AS_OF,
    }
    base.update(over)
    return SweepRecord(**base)


def test_sweep_round_trips_including_skips_and_counts(store: DarvaxRepository):
    counts = dict.fromkeys(TIER_ORDER, 0)
    counts[DarvaxTier.ACTIONABLE] = 4
    store.save_sweep(_sweep(tier_counts=counts))

    got = store.latest_sweep()
    assert got is not None
    assert got.sweep_id == "swp-1"
    assert got.requested == 528 and got.evaluated == 522
    assert got.tier_counts[DarvaxTier.ACTIONABLE] == 4
    assert got.skipped == (("NSE:SUZLON", "insufficient candles"),)
    assert got.as_of == AS_OF
    assert got.partial is False


def test_sweep_save_is_idempotent_and_updates_in_place(store: DarvaxRepository):
    """A sweep is written when it starts and again when it ends; the second
    write must update, not create a second row."""
    store.save_sweep(_sweep(state="running", finished_at=None, evaluated=0))
    store.save_sweep(_sweep(state="completed", evaluated=522))
    assert len(store.list_sweeps()) == 1
    assert store.get_sweep("swp-1").state == "completed"


def test_cancelled_sweep_is_recorded_as_partial(store: DarvaxRepository):
    store.save_sweep(_sweep(state="cancelled", partial=True, evaluated=312))
    got = store.get_sweep("swp-1")
    assert got.partial is True and got.evaluated == 312


def test_screen_results_round_trip_with_measurements_intact(store: DarvaxRepository):
    store.save_sweep(_sweep())
    results = screen_signals(
        [
            make_signal("TVSMOTOR", DarvaxSignalType.BREAKOUT, close="3841.20",
                        box_top="3807.90", box_bottom="3620", trigger="3835.00",
                        rule=DarvasRule.B_BUY_ABOVE_TOPMOST_BOX),
            _watch("BSE", "2894.00", "2902.50"),
            make_signal("NMDC", DarvaxSignalType.NO_BOX, close="71.85"),
        ],
        sweep_id="swp-1",
    )
    assert store.save_screen_results(results) == 3

    stored = store.list_screen_results("swp-1")
    assert len(stored) == 3
    by_id = {r.instrument_id: r for r in stored}

    tvs = by_id["NSE:TVSMOTOR"]
    assert tvs.tier is DarvaxTier.ACTIONABLE
    assert tvs.darvas_rule is DarvasRule.B_BUY_ABOVE_TOPMOST_BOX
    assert tvs.box_height_pct.quantize(Decimal("0.0001")) == Decimal("5.1906")
    assert tvs.distance_to_trigger_pct < 0
    assert isinstance(tvs.close, Decimal)

    # Absent measurements stay absent through the round trip.
    assert by_id["NSE:NMDC"].distance_to_trigger_pct is None
    assert by_id["NSE:NMDC"].box_top is None


def test_screen_results_can_be_filtered_to_one_tier(store: DarvaxRepository):
    store.save_sweep(_sweep())
    store.save_screen_results(
        screen_signals(
            [
                make_signal("BRK", DarvaxSignalType.BREAKOUT, close="110",
                            box_top="100", box_bottom="90", trigger="105"),
                _watch("WCH", "100", "104"),
                make_signal("NIL", DarvaxSignalType.NO_BOX, close="10"),
            ],
            sweep_id="swp-1",
        )
    )
    actionable = store.list_screen_results("swp-1", tier=DarvaxTier.ACTIONABLE)
    assert [r.instrument_id for r in actionable] == ["NSE:BRK"]


def test_screen_results_come_back_in_rank_order(store: DarvaxRepository):
    store.save_sweep(_sweep())
    store.save_screen_results(
        screen_signals(
            [_watch("FAR", "100", "110"), _watch("NEAR", "100", "101"),
             _watch("MID", "100", "105")],
            sweep_id="swp-1",
        )
    )
    got = store.list_screen_results("swp-1", tier=DarvaxTier.WATCH)
    assert [r.instrument_id for r in got] == ["NSE:NEAR", "NSE:MID", "NSE:FAR"]


def test_rescreening_the_same_sweep_updates_rather_than_duplicates(
    store: DarvaxRepository,
):
    store.save_sweep(_sweep())
    first = screen_signals([_watch("BSE", "100", "110")], sweep_id="swp-1")
    store.save_screen_results(first)
    second = screen_signals([_watch("BSE", "100", "101")], sweep_id="swp-1")
    store.save_screen_results(second)

    stored = store.list_screen_results("swp-1")
    assert len(stored) == 1
    assert stored[0].distance_to_trigger_pct.quantize(Decimal("0.01")) == Decimal("1.00")


def test_sweeps_are_isolated_from_each_other(store: DarvaxRepository):
    """Two sweeps must not bleed into one screen."""
    store.save_sweep(_sweep("swp-1"))
    store.save_sweep(_sweep("swp-2", started_at=AS_OF + timedelta(days=1)))
    store.save_screen_results(screen_signals([_watch("A", "100", "104")], sweep_id="swp-1"))
    store.save_screen_results(screen_signals([_watch("B", "100", "104")], sweep_id="swp-2"))

    assert [r.instrument_id for r in store.list_screen_results("swp-1")] == ["NSE:A"]
    assert store.latest_sweep().sweep_id == "swp-2"


def test_empty_result_set_is_a_no_op(store: DarvaxRepository):
    assert store.save_screen_results([]) == 0


def test_list_limits_are_validated(store: DarvaxRepository):
    with pytest.raises(ValueError):
        store.list_sweeps(limit=0)
    with pytest.raises(ValueError):
        store.list_screen_results("swp-1", limit=0)
