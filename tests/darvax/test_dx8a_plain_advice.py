"""DX-8a: the stop the screener never showed, and advice in plain English.

Two properties. First, **a screen that says "enter" must say where to get out** —
rule B mandates a stop, the signal always carried one, and `ScreenResult` never
copied it. Second, the plain and technical sentences must stay **two registers
of one conclusion**, not two claims and not two copies.
"""

from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal
from pathlib import Path

import pytest

from athena.darvax.screening.engine import (
    action_for,
    action_for_held,
    distance_to_breakout,
    plain_reason,
    screen_signal,
)
from athena.darvax.screening.models import DarvaxAction
from athena.darvax.signals.models import (
    DarvasRule,
    DarvaxSignal,
    DarvaxSignalType,
    DarvaxStop,
    StopBasis,
)
from athena.darvax.store.repository import DarvaxRepository

AS_OF = datetime(2026, 8, 16, 10, 0, tzinfo=timezone.utc)

#: Vocabulary that requires the methodology to decode. The plain sentence must
#: contain none of it; the technical one must cite a rule.
JARGON = ("rule A", "rule B", "rule C", "rule D", "DAR-CARD", "topmost box")

_RULE = {
    DarvaxSignalType.BREAKOUT: DarvasRule.B_BUY_ABOVE_TOPMOST_BOX,
    DarvaxSignalType.BREAKOUT_RETEST: DarvasRule.B_BUY_ABOVE_TOPMOST_BOX,
    DarvaxSignalType.INSIDE_TOPMOST_BOX: DarvasRule.A_HOLD_WHILE_IN_TOPMOST_BOX,
    DarvaxSignalType.BELOW_BOX_BOTTOM: DarvasRule.C_SELL_BELOW_NEW_BOX_BOTTOM,
    DarvaxSignalType.NOT_IN_TOPMOST_BOX: DarvasRule.D_NO_REASON_OUTSIDE_TOPMOST_BOX,
    DarvaxSignalType.NO_BOX: DarvasRule.D_NO_REASON_OUTSIDE_TOPMOST_BOX,
}


def signal(state, *, symbol="AAA", close="100", with_stop=True) -> DarvaxSignal:
    stop = (
        DarvaxStop(
            basis=StopBasis.CANONICAL_DARVAS_PCT,
            price=Decimal("94.5"),
            reference_price=Decimal("105"),
            detail="10% below the entry reference 105 = 94.5.",
            pct=Decimal("10"),
        )
        if with_stop
        else None
    )
    return DarvaxSignal(
        signal_id=f"sig-{symbol}",
        instrument_id=f"NSE:{symbol}",
        as_of=AS_OF,
        signal_type=state,
        darvas_rule=_RULE[state],
        close=Decimal(close),
        box_top=Decimal("105"),
        box_bottom=Decimal("95"),
        trigger_price=Decimal("106"),
        stop=stop,
        explanation="from DX-3",
        evidence={},
        methodology_digest="digest",
        darvax_version="test",
    )


# --------------------------------------------------------------------------- #
# 1. The stop the screener could not show
# --------------------------------------------------------------------------- #


def test_a_screen_result_carries_the_stop_the_signal_computed():
    """The gap that made this milestone a correctness fix rather than a visual
    one: DarvaX told the owner to enter and could not tell them where to exit."""
    result = screen_signal(signal(DarvaxSignalType.BREAKOUT), sweep_id="s")
    assert result.stop_price == Decimal("94.5")
    assert result.stop_basis == StopBasis.CANONICAL_DARVAS_PCT.value


def test_the_stop_is_copied_not_recomputed():
    """Copied so a stored screen keeps the level it was actually computed with,
    exactly as a signal keeps its methodology_digest (ADR-005)."""
    sig = signal(DarvaxSignalType.BREAKOUT)
    object.__setattr__(
        sig,
        "stop",
        DarvaxStop(
            basis=StopBasis.DARVAX_TIGHT_PCT,
            price=Decimal("1.23"),
            reference_price=Decimal("2"),
            detail="whatever the engine decided",
            pct=Decimal("1"),
        ),
    )
    result = screen_signal(sig, sweep_id="s")
    assert result.stop_price == Decimal("1.23"), "the engine's value must win"
    assert result.stop_basis == StopBasis.DARVAX_TIGHT_PCT.value


def test_a_signal_without_a_stop_reports_none_rather_than_inventing_one():
    result = screen_signal(
        signal(DarvaxSignalType.INSIDE_TOPMOST_BOX, with_stop=False), sweep_id="s"
    )
    assert result.stop_price is None
    assert result.stop_basis is None


def test_risk_per_share_is_derivable_from_persisted_values():
    """The UI shows risk per share as trigger − stop. Both must be present on
    the record, or the ticket cannot be assembled without recomputation."""
    result = screen_signal(signal(DarvaxSignalType.BREAKOUT), sweep_id="s")
    assert result.trigger_price is not None and result.stop_price is not None
    assert result.trigger_price - result.stop_price == Decimal("11.5")


# --------------------------------------------------------------------------- #
# 2. Two registers of one conclusion — the decision-1b guard
# --------------------------------------------------------------------------- #


def test_every_action_produces_both_sentences():
    for state in DarvaxSignalType:
        result = screen_signal(signal(state), sweep_id="s")
        assert result.action_reason.strip(), state
        assert result.action_reason_plain.strip(), state


def test_the_plain_sentence_contains_no_methodology_jargon():
    """Half the drift guard. Without it the plain field decays into a copy of
    the technical one and the redesign achieves nothing."""
    for state in DarvaxSignalType:
        plain = screen_signal(signal(state), sweep_id="s").action_reason_plain
        for word in JARGON:
            assert word not in plain, f"{state}: plain sentence says {word!r}: {plain}"


def test_the_technical_sentence_still_cites_a_rule():
    """The other half. Without it, "simplify" quietly becomes "delete the
    methodology" and the audit trail goes with it."""
    for state in DarvaxSignalType:
        reason = screen_signal(signal(state), sweep_id="s").action_reason
        assert any(word in reason for word in JARGON), f"{state}: {reason}"


def test_the_two_sentences_are_not_identical():
    for state in DarvaxSignalType:
        result = screen_signal(signal(state), sweep_id="s")
        assert result.action_reason != result.action_reason_plain, state


def test_neither_sentence_leaks_none():
    for state in DarvaxSignalType:
        for with_stop in (True, False):
            r = screen_signal(signal(state, with_stop=with_stop), sweep_id="s")
            assert "None" not in r.action_reason, state
            assert "None" not in r.action_reason_plain, state


def test_held_advice_also_produces_both_registers():
    for state in DarvaxSignalType:
        for stop in (None, Decimal("99")):
            action, reason, plain = action_for_held(signal(state), stop_price=stop)
            assert reason.strip() and plain.strip(), (state, stop)
            assert any(w in reason for w in JARGON), (state, reason)
            for word in JARGON:
                assert word not in plain, (state, plain)


def test_a_held_exit_says_which_exit_it_was():
    """"Your stop was hit" and "it left its range" are different news to a
    holder; a generic plain sentence would flatten them."""
    _, _, stopped = action_for_held(
        signal(DarvaxSignalType.INSIDE_TOPMOST_BOX, close="90"),
        stop_price=Decimal("99"),
    )
    _, _, left_range = action_for_held(
        signal(DarvaxSignalType.BELOW_BOX_BOTTOM), stop_price=None
    )
    assert "stop" in stopped.lower()
    assert stopped != left_range


def test_plain_reason_names_the_buy_level_when_there_is_one():
    sig = signal(DarvaxSignalType.BREAKOUT)
    pct, _ = distance_to_breakout(sig)
    plain = plain_reason(sig, DarvaxAction.ENTER, breakout_pct=pct)
    assert "106" in plain, plain


# --------------------------------------------------------------------------- #
# 3. Persistence
# --------------------------------------------------------------------------- #


@pytest.fixture()
def store(tmp_path: Path) -> DarvaxRepository:
    r = DarvaxRepository(tmp_path / "darvax.db")
    r.initialize()
    yield r
    r.close()


def test_the_new_fields_round_trip(store: DarvaxRepository):
    original = screen_signal(signal(DarvaxSignalType.BREAKOUT), sweep_id="s")
    store.save_screen_results([original])
    back = store.list_screen_results("s")[0]
    assert back.stop_price == original.stop_price
    assert back.stop_basis == original.stop_basis
    assert back.action_reason_plain == original.action_reason_plain


def test_a_pre_dx8a_row_reads_back_empty_rather_than_guessed(
    store: DarvaxRepository, tmp_path: Path
):
    import sqlite3

    store.save_screen_results(
        [screen_signal(signal(DarvaxSignalType.BREAKOUT), sweep_id="s")]
    )
    con = sqlite3.connect(str(tmp_path / "darvax.db"))
    con.execute(
        "UPDATE darvax_screen_results SET action_reason_plain=NULL, "
        "stop_price=NULL, stop_basis=NULL"
    )
    con.commit()
    con.close()

    back = store.list_screen_results("s")[0]
    assert back.action_reason_plain == ""
    assert back.stop_price is None, "a stop must never be invented for an old row"


def test_the_api_exposes_the_stop_and_the_plain_reason():
    repo_root = Path(__file__).resolve().parents[2]
    source = (repo_root / "src/athena/darvax/api/routes.py").read_text(encoding="utf-8")
    for field in ("action_reason_plain", "stop_price", "stop_basis"):
        assert f'"{field}"' in source, field
