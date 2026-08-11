"""DX-3 signal engine, stop policies, and persisted explanations (ADR-010).

The state machine is exercised against hand-built series that put price in each
of the six states deliberately, with the box geometry traced in comments so a
reviewer can confirm the expected state without re-deriving it.

The load-bearing architectural assertion in this file is that a DarvaxSignal is
never an ATHENA Decision and never becomes readable by ATHENA's pipeline.
"""

from __future__ import annotations

import dataclasses
from datetime import datetime, timedelta
from decimal import Decimal
from pathlib import Path
from zoneinfo import ZoneInfo

import pytest

from athena.darvax.config import DarvaxMethodologyConfig, methodology_digest
from athena.darvax.primitives import DarvaxPrimitiveError, darvas_boxes
from athena.darvax.signals import (
    DarvasRule,
    DarvaxSignalType,
    StopBasis,
    compute_stop,
    ema_series,
    evaluate_signal,
    latest_ema,
)
from athena.darvax.store import DARVAX_SCHEMA_VERSION, DarvaxRepository
from athena.domain.enums import Timeframe
from athena.domain.market import Candle

IST = ZoneInfo("Asia/Kolkata")
BASE_TS = datetime(2026, 3, 2, 9, 15, tzinfo=IST)


def _candles(
    highs: list[float],
    lows: list[float],
    closes: list[float] | None = None,
    *,
    instrument_id: str = "NSE:SYN",
) -> list[Candle]:
    cl = closes if closes is not None else lows
    return [
        Candle(
            instrument_id=instrument_id,
            timeframe=Timeframe.D1,
            ts_open=BASE_TS + timedelta(days=i),
            open=Decimal(str(lows[i])),
            high=Decimal(str(highs[i])),
            low=Decimal(str(lows[i])),
            close=Decimal(str(cl[i])),
            volume=1_000,
            source="test",
        )
        for i in range(len(highs))
    ]


# The DX-2 hand-worked box fixture: completes box [8, 12] (topmost) at index 10,
# then box [8, 10] (NOT topmost) at index 15.
_H = [10, 11, 12, 11, 11, 11, 10, 9, 9, 9, 9, 10, 9, 9, 9, 9]
_L = [9, 10, 11, 10, 10, 10, 9, 8, 8, 8, 8, 9, 8, 8, 8, 8]

#: The prefix that stops after box 1 completes — topmost box [8, 12].
_TOPMOST_H = _H[:11]
_TOPMOST_L = _L[:11]


def _with_final_bar(
    highs: list[float], lows: list[float], *, high: float, low: float, close: float
) -> list[Candle]:
    """Append one bar whose close decides which state the engine resolves to."""
    return _candles(
        [*highs, high], [*lows, low], [*lows, close]
    )


# =========================================================================== #
# State machine — one test per state
# =========================================================================== #


def test_no_box_state_is_still_explained():
    """Insufficient structure is an explainable outcome, not a silent empty."""
    signal = evaluate_signal(_candles([10, 11], [9, 10]))
    assert signal.signal_type is DarvaxSignalType.NO_BOX
    assert signal.darvas_rule is None
    assert signal.box_top is None
    assert "No Darvas box has completed" in signal.explanation
    assert signal.evidence, "even NO_BOX must carry an evidence trace"


def test_inside_topmost_box_is_rule_a():
    """Box [8,12] topmost; final close 10 sits inside it."""
    candles = _with_final_bar(_TOPMOST_H, _TOPMOST_L, high=11, low=9, close=10)
    signal = evaluate_signal(candles)
    assert signal.signal_type is DarvaxSignalType.INSIDE_TOPMOST_BOX
    assert signal.darvas_rule is DarvasRule.A_HOLD_WHILE_IN_TOPMOST_BOX
    assert (signal.box_bottom, signal.box_top) == (Decimal("8"), Decimal("12"))
    assert signal.box_is_topmost is True
    assert signal.stop is None, "no entry in view, so no stop is asserted"


def test_breakout_is_rule_b_and_carries_a_stop():
    """Final close 13 clears the topmost ceiling of 12."""
    candles = _with_final_bar(_TOPMOST_H, _TOPMOST_L, high=13, low=12, close=13)
    signal = evaluate_signal(candles)
    assert signal.signal_type is DarvaxSignalType.BREAKOUT
    assert signal.darvas_rule is DarvasRule.B_BUY_ABOVE_TOPMOST_BOX
    assert signal.stop is not None
    # Entry reference is the prior bar's high (deck p.44) = 9 for this fixture.
    assert signal.trigger_price == Decimal("9")
    assert signal.stop.basis is StopBasis.CANONICAL_DARVAS_PCT


def test_below_box_bottom_is_rule_c():
    """Final close 7 is beneath the topmost box floor of 8."""
    candles = _with_final_bar(_TOPMOST_H, _TOPMOST_L, high=8, low=7, close=7)
    signal = evaluate_signal(candles)
    assert signal.signal_type is DarvaxSignalType.BELOW_BOX_BOTTOM
    assert signal.darvas_rule is DarvasRule.C_SELL_BELOW_NEW_BOX_BOTTOM


def test_inside_topmost_box_even_when_a_lower_box_completed_later():
    """The 16-bar fixture's topmost box is [8,12] while the most recently
    completed box is the lower [8,10]. Rules A/B/D reference the *topmost* box,
    so a close of 8 — inside [8,12] — is rule A, not rule D. Using the latest
    completed box as the reference instead would misreport this."""
    signal = evaluate_signal(_candles(_H, _L))
    assert signal.signal_type is DarvaxSignalType.INSIDE_TOPMOST_BOX
    assert (signal.box_bottom, signal.box_top) == (Decimal("8"), Decimal("12"))
    # The lower, more recent box is still surfaced in the evidence so the
    # divergence is visible rather than hidden.
    names = {e.name for e in signal.evidence}
    assert "latest_completed_box" in names


def test_not_in_topmost_box_is_rule_d():
    """Rule D needs price *below* the topmost box floor with lower structure
    formed since: topmost is [8,12], the newest box is [8,10], and the final
    close of 7 is beneath 8."""
    candles = _with_final_bar(_H, _L, high=8, low=7, close=7)
    signal = evaluate_signal(candles)
    assert signal.signal_type is DarvaxSignalType.NOT_IN_TOPMOST_BOX
    assert signal.darvas_rule is DarvasRule.D_NO_REASON_OUTSIDE_TOPMOST_BOX
    assert "rule D" in signal.explanation


def test_close_above_every_box_ceiling_is_a_breakout_not_rule_d():
    """Regression for a real-data defect (found on NSE:TVSMOTOR, close 4398 with
    its highest box ceiling at 3807.90): when price has run above *every* box it
    ever formed, that is the strongest Darvas condition — rule B. An earlier
    implementation referenced the most recently completed box instead and
    reported rule D ("no reason to HOLD or BUY"), inverting the meaning."""
    # Topmost box is [8,12]; a lower box [8,10] completes after it; final close
    # of 20 is above every ceiling in the series.
    candles = _with_final_bar(_H, _L, high=20, low=19, close=20)
    signal = evaluate_signal(candles)
    assert signal.signal_type is DarvaxSignalType.BREAKOUT
    assert signal.darvas_rule is DarvasRule.B_BUY_ABOVE_TOPMOST_BOX
    assert signal.box_top == Decimal("12"), "must reference the topmost ceiling"
    assert signal.stop is not None


def test_breakout_retest_is_recognised():
    """After box [8,12] completes at index 10: bar 11 closes 13 (breakout), bar
    12 dips its low back to 12.1 — inside the 2% ceiling zone (12 * 1.02 =
    12.24) — while still closing 13, above the ceiling. That is the deck's
    breakout-retest (p.28)."""
    highs = [*_TOPMOST_H, 13, 13]
    lows = [*_TOPMOST_L, 12, 12.1]
    closes = [*_TOPMOST_L, 13, 13]
    signal = evaluate_signal(_candles(highs, lows, closes))
    assert signal.signal_type is DarvaxSignalType.BREAKOUT_RETEST
    assert signal.darvas_rule is DarvasRule.B_BUY_ABOVE_TOPMOST_BOX
    assert signal.stop is not None


def test_close_back_below_ceiling_is_not_a_retest():
    """A breakout that gives the level back is a failed retest, not a retest —
    the state falls back to a plain breakout once price reclaims the ceiling."""
    highs = [*_TOPMOST_H, 13, 13, 13]
    lows = [*_TOPMOST_L, 12, 11, 12]
    closes = [*_TOPMOST_L, 13, 11.5, 13]  # middle bar closes below 12
    signal = evaluate_signal(_candles(highs, lows, closes))
    assert signal.signal_type is DarvaxSignalType.BREAKOUT


# =========================================================================== #
# Stop policies
# =========================================================================== #


def test_canonical_darvas_stop_is_ten_percent_below_entry():
    """Darvas rule B, deck p.67. 100 - 10% = 90.00."""
    candles = _candles([100] * 5, [100] * 5)
    stop = compute_stop(
        candles, DarvaxMethodologyConfig(), reference_price=Decimal("100")
    )
    assert stop is not None
    assert stop.basis is StopBasis.CANONICAL_DARVAS_PCT
    assert stop.price == Decimal("90.00")
    assert stop.pct == Decimal("10")
    assert "p.67" in stop.detail


def test_darvax_tight_stop_is_one_percent_below_entry():
    """Deck p.44. 100 - 1% = 99.00. The detail must carry ADR-010's recorded
    caution that this is implausibly tight for a breakout entry."""
    candles = _candles([100] * 5, [100] * 5)
    stop = compute_stop(
        candles,
        DarvaxMethodologyConfig(stop_policy="darvax_tight"),
        reference_price=Decimal("100"),
    )
    assert stop is not None
    assert stop.basis is StopBasis.DARVAX_TIGHT_PCT
    assert stop.price == Decimal("99.00")
    assert "implausibly tight" in stop.detail


def test_ema_ladder_stop_uses_the_configured_horizon():
    """swing horizon -> the 10 EMA rung (deck p.9)."""
    candles = _candles([100] * 20, [100] * 20)
    stop = compute_stop(
        candles,
        DarvaxMethodologyConfig(stop_policy="ema_ladder"),
        reference_price=Decimal("100"),
    )
    assert stop is not None
    assert stop.basis is StopBasis.EMA_LADDER
    assert stop.ema_period == 10
    # A flat series' EMA equals the flat price.
    assert stop.price == Decimal("100.00")
    assert "close below" in stop.detail.lower()


def test_ema_ladder_stop_is_unavailable_rather_than_invented_when_history_is_short():
    """Fewer bars than the EMA period means no level exists. Returning None is
    honest; fabricating a stop the owner might act on would not be."""
    candles = _candles([100] * 4, [100] * 4)
    stop = compute_stop(
        candles,
        DarvaxMethodologyConfig(stop_policy="ema_ladder"),
        reference_price=Decimal("100"),
    )
    assert stop is None


def test_engine_reports_unavailable_ema_stop_in_its_evidence():
    """The signal must say so explicitly rather than silently omitting it."""
    candles = _with_final_bar(_TOPMOST_H, _TOPMOST_L, high=13, low=12, close=13)
    config = DarvaxMethodologyConfig(
        stop_policy="ema_ladder",
        breakout={"stop_horizon": "investor"},  # 200 EMA, far longer than history
    )
    signal = evaluate_signal(candles, config)
    assert signal.signal_type is DarvaxSignalType.BREAKOUT
    assert signal.stop is None
    stop_evidence = [e for e in signal.evidence if e.name == "stop"]
    assert stop_evidence and stop_evidence[0].value == "UNAVAILABLE"


def test_stop_policy_selection_actually_changes_the_stop():
    candles = _candles([100] * 20, [100] * 20)
    prices = {
        policy: compute_stop(
            candles,
            DarvaxMethodologyConfig(stop_policy=policy),
            reference_price=Decimal("100"),
        ).price
        for policy in ("canonical_darvas", "darvax_tight", "ema_ladder")
    }
    assert len(set(prices.values())) == 3, prices


# =========================================================================== #
# EMA
# =========================================================================== #


def test_ema_of_a_flat_series_is_the_flat_value():
    assert ema_series([Decimal("50")] * 10, 5)[-1] == Decimal("50")


def test_ema_seed_is_the_simple_mean_of_the_first_period():
    """closes 1..5, period 5 -> seed = mean(1..5) = 3, and it is the only value."""
    values = ema_series([Decimal(n) for n in (1, 2, 3, 4, 5)], 5)
    assert values == (Decimal("3"),)


def test_ema_hand_worked_one_step_past_the_seed():
    """period 3 over [1,2,3,10]: seed = 2, k = 2/4 = 0.5,
    next = 10*0.5 + 2*0.5 = 6."""
    values = ema_series([Decimal(n) for n in (1, 2, 3, 10)], 3)
    assert values == (Decimal("2"), Decimal("6"))


def test_latest_ema_returns_none_for_short_history_but_raises_on_bad_period():
    candles = _candles([10] * 3, [10] * 3)
    assert latest_ema(candles, 10) is None
    with pytest.raises(DarvaxPrimitiveError, match="period must be >= 1"):
        latest_ema(candles, 0)


# =========================================================================== #
# Explainability, determinism, replayability
# =========================================================================== #


def test_every_signal_carries_explanation_and_evidence():
    for candles in (
        _candles([10, 11], [9, 10]),
        _with_final_bar(_TOPMOST_H, _TOPMOST_L, high=11, low=9, close=10),
        _with_final_bar(_TOPMOST_H, _TOPMOST_L, high=13, low=12, close=13),
        _with_final_bar(_TOPMOST_H, _TOPMOST_L, high=8, low=7, close=7),
        _candles(_H, _L),
    ):
        signal = evaluate_signal(candles)
        assert signal.explanation.strip(), signal.signal_type
        assert signal.evidence, signal.signal_type
        assert signal.methodology_digest
        assert signal.darvax_version


def test_dar_card_rule_text_is_quoted_in_the_evidence():
    """Attribution is faithful: the evidence carries Darvas' own wording rather
    than a paraphrase of it."""
    signal = evaluate_signal(
        _with_final_bar(_TOPMOST_H, _TOPMOST_L, high=13, low=12, close=13)
    )
    rule_evidence = [e for e in signal.evidence if e.name == "dar_card_rule"]
    assert rule_evidence
    assert "10 percent stop-loss" in rule_evidence[0].detail


def test_signals_are_deterministic_and_ids_are_stable():
    candles = _with_final_bar(_TOPMOST_H, _TOPMOST_L, high=13, low=12, close=13)
    first = evaluate_signal(candles)
    second = evaluate_signal(candles)
    assert first == second, "engine must be deterministic"
    assert first.signal_id == second.signal_id
    assert first.as_of == candles[-1].ts_open, "as_of comes from data, not a clock"


def test_methodology_digest_changes_when_settings_change():
    candles = _with_final_bar(_TOPMOST_H, _TOPMOST_L, high=13, low=12, close=13)
    a = evaluate_signal(candles, DarvaxMethodologyConfig())
    b = evaluate_signal(
        candles, DarvaxMethodologyConfig(canonical_stop_pct=Decimal("12"))
    )
    assert a.methodology_digest != b.methodology_digest
    assert a.methodology_digest == methodology_digest(DarvaxMethodologyConfig())


def test_box_confirmation_bars_flows_from_config_into_the_engine():
    """Proves DX-3 actually wires DX-2's parameter rather than ignoring it.

    Asserted on the box *count* carried in the evidence, because that is the
    value the config demonstrably changes here: confirmation_bars=1 finds three
    boxes on this fixture and =3 finds two. The final box's top/bottom happens to
    coincide at [8,10] under both settings, so asserting on those alone would
    pass for the wrong reason.
    """
    candles = _candles(_H, _L)
    assert len(darvas_boxes(candles, confirmation_bars=1)) == 3
    assert len(darvas_boxes(candles, confirmation_bars=3)) == 2

    def _boxes_in_evidence(confirmation_bars: int) -> str:
        signal = evaluate_signal(
            candles,
            DarvaxMethodologyConfig(box={"confirmation_bars": confirmation_bars}),
        )
        evidence = {e.name: e.value for e in signal.evidence}
        return evidence["boxes_completed"]

    assert _boxes_in_evidence(1) == "3"
    assert _boxes_in_evidence(3) == "2"


def test_signals_are_immutable():
    signal = evaluate_signal(_candles([10, 11], [9, 10]))
    with pytest.raises(dataclasses.FrozenInstanceError):
        signal.signal_type = DarvaxSignalType.BREAKOUT  # type: ignore[misc]


def test_engine_rejects_newest_first_input():
    candles = _candles(_H, _L)
    with pytest.raises(DarvaxPrimitiveError, match="list_candles_recent"):
        evaluate_signal(list(reversed(candles)))


def test_every_signal_is_labelled_experimental_until_dx5():
    signal = evaluate_signal(_candles(_H, _L))
    assert signal.status == "EXPERIMENTAL_UNVALIDATED"


# =========================================================================== #
# Persistence (DarvaX-owned database only)
# =========================================================================== #


@pytest.fixture()
def store(tmp_path: Path) -> DarvaxRepository:
    repo = DarvaxRepository(tmp_path / "darvax.db")
    repo.initialize()
    yield repo
    repo.close()


def test_darvax_schema_is_at_version_two(store: DarvaxRepository):
    assert DARVAX_SCHEMA_VERSION == 2
    assert store.schema_version() == 2


def test_signal_round_trips_with_explanation_and_evidence_intact(
    store: DarvaxRepository,
):
    """Explanation and evidence are read back as stored, never recomputed."""
    signal = evaluate_signal(
        _with_final_bar(_TOPMOST_H, _TOPMOST_L, high=13, low=12, close=13)
    )
    store.save_signal(signal)

    loaded = store.latest_signal(signal.instrument_id)
    assert loaded is not None
    assert loaded == signal, "round-trip must be lossless"
    assert loaded.explanation == signal.explanation
    assert loaded.evidence == signal.evidence
    assert loaded.stop is not None
    assert loaded.stop.price == signal.stop.price


def test_saving_the_same_signal_twice_is_idempotent(store: DarvaxRepository):
    """Replaying the engine over identical candles must not duplicate history."""
    signal = evaluate_signal(_candles(_H, _L))
    store.save_signal(signal)
    store.save_signal(signal)
    assert len(store.list_signals()) == 1


def test_list_signals_is_newest_first(store: DarvaxRepository):
    older = evaluate_signal(_candles(_H, _L))
    newer = dataclasses.replace(
        older,
        signal_id="darvax-NSE:SYN-later",
        as_of=older.as_of + timedelta(days=1),
    )
    store.save_signal(older)
    store.save_signal(newer)
    listed = store.list_signals()
    assert [s.signal_id for s in listed] == [newer.signal_id, older.signal_id]


def test_signal_with_no_box_and_no_stop_round_trips(store: DarvaxRepository):
    """Nullable columns must survive the trip — the NO_BOX case has neither box
    geometry nor a stop."""
    signal = evaluate_signal(_candles([10, 11], [9, 10]))
    store.save_signal(signal)
    loaded = store.latest_signal(signal.instrument_id)
    assert loaded == signal
    assert loaded.box_top is None and loaded.stop is None


def test_darvax_store_writes_only_to_its_own_database(store: DarvaxRepository, tmp_path):
    """The signals table must exist in darvax.db and nowhere near athena.db."""
    signal = evaluate_signal(_candles(_H, _L))
    store.save_signal(signal)
    assert Path(store.path).name == "darvax.db"

    from athena.data.store.repository import SqliteRepository

    athena = SqliteRepository(tmp_path / "athena.db")
    athena.initialize()
    try:
        assert not any("darvax" in t.lower() for t in athena.record_counts())
    finally:
        athena.close()


# =========================================================================== #
# The architectural guarantee DX-3 must not break
# =========================================================================== #


def test_darvax_signal_is_not_an_athena_decision():
    """ADR-010 forbids converting a DarvaxSignal into an ATHENA Decision, even
    as a convenience. The types must be structurally distinct and DarvaX must
    expose no such conversion."""
    import athena.darvax.signals as signals
    from athena.domain.decision import Decision

    signal = evaluate_signal(_candles(_H, _L))
    assert not isinstance(signal, Decision)

    decision_fields = {f.name for f in dataclasses.fields(Decision)}
    signal_fields = {f.name for f in dataclasses.fields(signal)}
    # A shared name or two (instrument_id) is unavoidable; a shared *shape* is not.
    assert not decision_fields.issubset(signal_fields)
    assert "decision_type" not in signal_fields
    assert "gate_results" not in signal_fields
    assert "trade_plan" not in signal_fields

    for name in dir(signals):
        assert "decision" not in name.lower(), (
            f"darvax.signals exports {name!r}; no Decision bridge may exist"
        )


def test_darvax_signals_package_imports_no_athena_engine():
    """DX-3 must not have quietly reached into ATHENA's analytical core."""
    import ast

    pkg = Path(__file__).resolve().parents[2] / "src" / "athena" / "darvax" / "signals"
    allowed = {"athena.darvax", "athena.domain", "athena.errors"}
    for py in pkg.rglob("*.py"):
        tree = ast.parse(py.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            module = None
            if isinstance(node, ast.ImportFrom):
                module = node.module or ""
            elif isinstance(node, ast.Import):
                module = node.names[0].name
            if module and module.startswith("athena."):
                assert any(module.startswith(prefix) for prefix in allowed), (
                    f"{py.name} imports {module!r}, outside the allowed set {allowed}"
                )
