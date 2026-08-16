"""DX-7a: an action, and its justification, computed once and persisted.

The property under test is ADR-005 applied to advice: **the words the owner
reads are produced by the engine that chose the action and stored with it.**
A screen that recomputed either in the API or the browser could tell the owner
to enter a trade for a reason the engine never concluded.
"""

from __future__ import annotations

import ast
from datetime import datetime, timezone
from decimal import Decimal
from pathlib import Path

import pytest

from athena.darvax.screening.engine import (
    action_for,
    action_reason,
    distance_to_breakout,
    screen_signal,
    screen_signals,
)
from athena.darvax.screening.models import (
    RISK_BEARING_ACTIONS,
    DarvaxAction,
    DarvaxTier,
    ScreenResult,
)
from athena.darvax.signals.models import DarvasRule, DarvaxSignal, DarvaxSignalType
from athena.darvax.store.repository import DarvaxRepository
from athena.errors import AthenaError

REPO_ROOT = Path(__file__).resolve().parents[2]
AS_OF = datetime(2026, 8, 16, 10, 0, tzinfo=timezone.utc)

_RULE_BY_STATE = {
    DarvaxSignalType.BREAKOUT: DarvasRule.B_BUY_ABOVE_TOPMOST_BOX,
    DarvaxSignalType.BREAKOUT_RETEST: DarvasRule.B_BUY_ABOVE_TOPMOST_BOX,
    DarvaxSignalType.INSIDE_TOPMOST_BOX: DarvasRule.A_HOLD_WHILE_IN_TOPMOST_BOX,
    DarvaxSignalType.BELOW_BOX_BOTTOM: DarvasRule.C_SELL_BELOW_NEW_BOX_BOTTOM,
    DarvaxSignalType.NOT_IN_TOPMOST_BOX: DarvasRule.D_NO_REASON_OUTSIDE_TOPMOST_BOX,
    DarvaxSignalType.NO_BOX: DarvasRule.D_NO_REASON_OUTSIDE_TOPMOST_BOX,
}


def signal(
    state: DarvaxSignalType,
    *,
    symbol: str = "AAA",
    close: str = "100",
    box_top: str | None = "105",
    box_bottom: str | None = "95",
    trigger: str | None = None,
) -> DarvaxSignal:
    return DarvaxSignal(
        signal_id=f"sig-{symbol}",
        instrument_id=f"NSE:{symbol}",
        as_of=AS_OF,
        signal_type=state,
        darvas_rule=_RULE_BY_STATE[state],
        close=Decimal(close),
        box_top=Decimal(box_top) if box_top else None,
        box_bottom=Decimal(box_bottom) if box_bottom else None,
        trigger_price=Decimal(trigger) if trigger else None,
        explanation="structural explanation from DX-3",
        evidence={},
        methodology_digest="digest",
        darvax_version="test",
    )


# --------------------------------------------------------------------------- #
# 1. The mapping
# --------------------------------------------------------------------------- #


@pytest.mark.parametrize(
    ("state", "expected"),
    [
        (DarvaxSignalType.BREAKOUT, DarvaxAction.ENTER),
        (DarvaxSignalType.BREAKOUT_RETEST, DarvaxAction.ENTER_ON_RETEST),
        (DarvaxSignalType.INSIDE_TOPMOST_BOX, DarvaxAction.WAIT),
        (DarvaxSignalType.BELOW_BOX_BOTTOM, DarvaxAction.EXIT_IF_HELD),
        (DarvaxSignalType.NOT_IN_TOPMOST_BOX, DarvaxAction.NO_ENTRY),
        (DarvaxSignalType.NO_BOX, DarvaxAction.NO_ENTRY),
    ],
)
def test_every_signal_state_maps_to_an_action(state, expected):
    assert action_for(state) is expected


def test_every_signal_state_is_mapped():
    """Total by construction — a new state must be classified deliberately."""
    for state in DarvaxSignalType:
        assert isinstance(action_for(state), DarvaxAction)


def test_an_unmapped_state_raises_rather_than_defaulting():
    """Defaulting would be worse here than for tiers: an unclassified state
    silently becoming ENTER proposes risking money on a state nobody reviewed."""

    class Bogus:
        pass

    with pytest.raises(AthenaError, match="no action defined"):
        action_for(Bogus())  # type: ignore[arg-type]


def test_the_exit_action_stays_conditional_until_positions_exist():
    """DarvaX cannot see holdings until DX-7b. `EXIT_IF_HELD` says exactly that;
    a bare `EXIT` would be advice about a position that may not exist."""
    assert action_for(DarvaxSignalType.BELOW_BOX_BOTTOM) is DarvaxAction.EXIT_IF_HELD
    assert not hasattr(DarvaxAction, "HOLD"), (
        "HOLD is DX-7b — it is meaningless while DarvaX cannot see positions"
    )


def test_only_entry_actions_are_marked_risk_bearing():
    """Which chips carry the unvalidated badge is a domain fact (decision 3b).
    WAIT and NO_ENTRY risk nothing; EXIT_IF_HELD reduces exposure."""
    assert RISK_BEARING_ACTIONS == {DarvaxAction.ENTER, DarvaxAction.ENTER_ON_RETEST}


# --------------------------------------------------------------------------- #
# 2. The reason — real numbers, real rules
# --------------------------------------------------------------------------- #


@pytest.mark.parametrize(
    ("state", "rule_word"),
    [
        (DarvaxSignalType.BREAKOUT, "rule B"),
        (DarvaxSignalType.BREAKOUT_RETEST, "rule B"),
        (DarvaxSignalType.INSIDE_TOPMOST_BOX, "rule A"),
        (DarvaxSignalType.BELOW_BOX_BOTTOM, "rule C"),
        (DarvaxSignalType.NO_BOX, "rule D"),
    ],
)
def test_every_reason_names_the_darvas_rule_it_came_from(state, rule_word):
    """Advice must be traceable to the methodology, not to DarvaX's phrasing."""
    sig = signal(state)
    pct, ref = distance_to_breakout(sig)
    reason = action_reason(sig, action_for(state), breakout_pct=pct, breakout_ref=ref)
    assert rule_word in reason, reason


def test_the_reason_carries_the_numbers_that_drove_it():
    sig = signal(DarvaxSignalType.BREAKOUT, close="106", box_top="105", trigger="105.5")
    pct, ref = distance_to_breakout(sig)
    reason = action_reason(
        sig, DarvaxAction.ENTER, breakout_pct=pct, breakout_ref=ref
    )
    assert "105" in reason and "105.5" in reason, reason


def test_a_prose_percentage_is_rounded_for_reading_not_for_sorting():
    """A live screen produced "1.3333% below the box ceiling". The stored field
    keeps four places because ranking sorts on it; the sentence must not, or it
    claims precision a distance-to-a-price does not have."""
    sig = signal(DarvaxSignalType.INSIDE_TOPMOST_BOX, close="103.5", box_top="104.88")
    pct, ref = distance_to_breakout(sig)
    assert pct is not None and len(str(pct).split(".")[-1]) == 4, (
        "precondition: the stored value still carries four places"
    )
    reason = action_reason(sig, DarvaxAction.WAIT, breakout_pct=pct, breakout_ref=ref)
    assert str(pct) not in reason, f"raw 4dp value leaked into prose: {reason}"
    assert "%" in reason


def test_a_reason_survives_missing_optional_levels():
    """A signal with no box must still produce readable advice rather than
    'None' leaking into a sentence the owner reads."""
    sig = signal(DarvaxSignalType.NO_BOX, box_top=None, box_bottom=None)
    pct, ref = distance_to_breakout(sig)
    reason = action_reason(
        sig, DarvaxAction.NO_ENTRY, breakout_pct=pct, breakout_ref=ref
    )
    assert reason and "None" not in reason, reason


def test_every_action_produces_a_non_empty_reason():
    for state in DarvaxSignalType:
        sig = signal(state)
        pct, ref = distance_to_breakout(sig)
        reason = action_reason(
            sig, action_for(state), breakout_pct=pct, breakout_ref=ref
        )
        assert reason.strip(), f"{state} produced no reason"
        assert "None" not in reason, f"{state} leaked None: {reason}"


# --------------------------------------------------------------------------- #
# 3. Screening sets both, and ranking preserves them
# --------------------------------------------------------------------------- #


def test_screen_signal_sets_action_and_reason():
    result = screen_signal(signal(DarvaxSignalType.BREAKOUT), sweep_id="swp-1")
    assert result.action is DarvaxAction.ENTER
    assert result.action_reason


def test_ranking_does_not_drop_the_new_fields():
    """`rank_tier` used to rebuild ScreenResult field by field, so any field
    added without editing it was silently lost. This is that regression."""
    results = screen_signals(
        [
            signal(DarvaxSignalType.BREAKOUT, symbol="AAA"),
            signal(DarvaxSignalType.BREAKOUT, symbol="BBB", close="107"),
        ],
        sweep_id="swp-1",
    )
    assert results
    for r in results:
        assert r.action is DarvaxAction.ENTER
        assert r.action_reason, f"{r.instrument_id} lost its reason during ranking"


def test_ranking_still_assigns_ranks():
    results = screen_signals(
        [signal(DarvaxSignalType.BREAKOUT, symbol=s) for s in ("AAA", "BBB", "CCC")],
        sweep_id="swp-1",
    )
    actionable = [r for r in results if r.tier is DarvaxTier.ACTIONABLE]
    assert sorted(r.rank for r in actionable) == [1, 2, 3]


# --------------------------------------------------------------------------- #
# 4. Persistence — stored and read back, never recomputed
# --------------------------------------------------------------------------- #


@pytest.fixture()
def store(tmp_path: Path) -> DarvaxRepository:
    r = DarvaxRepository(tmp_path / "darvax.db")
    r.initialize()
    yield r
    r.close()


def test_action_round_trips_through_the_store(store: DarvaxRepository):
    results = screen_signals(
        [signal(DarvaxSignalType.BREAKOUT), signal(DarvaxSignalType.NO_BOX, symbol="ZZZ")],
        sweep_id="swp-1",
    )
    store.save_screen_results(results)
    back = {r.instrument_id: r for r in store.list_screen_results("swp-1")}
    assert back["NSE:AAA"].action is DarvaxAction.ENTER
    assert back["NSE:AAA"].action_reason == results[0].action_reason
    assert back["NSE:ZZZ"].action is DarvaxAction.NO_ENTRY


def test_a_pre_dx7a_row_reads_back_as_unrecorded_not_as_advice(
    store: DarvaxRepository, tmp_path: Path
):
    """Rows written before DX-7a have NULL action. They must not present as a
    conclusion the engine reached — the empty reason is the tell."""
    results = screen_signals([signal(DarvaxSignalType.BREAKOUT)], sweep_id="swp-1")
    store.save_screen_results(results)
    import sqlite3

    con = sqlite3.connect(str(tmp_path / "darvax.db"))
    con.execute("UPDATE darvax_screen_results SET action=NULL, action_reason=NULL")
    con.commit()
    con.close()

    back = store.list_screen_results("swp-1")[0]
    assert back.action_reason == "", (
        "an unrecorded action must not carry a justification"
    )


def test_the_schema_records_the_new_version(store: DarvaxRepository):
    from athena.darvax.store import DARVAX_SCHEMA_VERSION

    assert store.schema_version() == DARVAX_SCHEMA_VERSION


def test_upgrading_an_existing_database_adds_the_columns(tmp_path: Path):
    """The owner's darvax.db already exists at an older version; initialize()
    must ALTER the columns in rather than silently leaving them missing."""
    import sqlite3

    path = tmp_path / "old.db"
    con = sqlite3.connect(str(path))
    con.execute(
        "CREATE TABLE darvax_screen_results ("
        "sweep_id TEXT NOT NULL, instrument_id TEXT NOT NULL, signal_id TEXT NOT NULL,"
        "tier TEXT NOT NULL, signal_type TEXT NOT NULL, darvas_rule TEXT,"
        "rank INTEGER NOT NULL, close TEXT NOT NULL, box_top TEXT, box_bottom TEXT,"
        "trigger_price TEXT, distance_to_trigger_pct TEXT, explanation TEXT NOT NULL,"
        "PRIMARY KEY (sweep_id, instrument_id))"
    )
    con.commit()
    con.close()

    repo = DarvaxRepository(path)
    repo.initialize()
    con = sqlite3.connect(str(path))
    cols = {r[1] for r in con.execute("PRAGMA table_info(darvax_screen_results)")}
    con.close()
    repo.close()
    assert {"action", "action_reason"} <= cols


# --------------------------------------------------------------------------- #
# 5. ADR-005 — the browser must not derive advice
# --------------------------------------------------------------------------- #


def _strip_js_comments(source: str) -> str:
    out, i, n = [], 0, len(source)
    while i < n:
        if source.startswith("//", i):
            i = source.find("\n", i)
            if i == -1:
                break
        elif source.startswith("/*", i):
            end = source.find("*/", i + 2)
            i = n if end == -1 else end + 2
        else:
            out.append(source[i])
            i += 1
    return "".join(out)


def test_the_api_exposes_the_stored_action():
    """Serialisation reads `result.action`; it must not re-derive from tier."""
    source = (REPO_ROOT / "src/athena/darvax/api/routes.py").read_text(encoding="utf-8")
    assert '"action": result.action.value' in source
    assert '"action_reason": result.action_reason' in source


def test_the_api_tells_the_client_which_actions_carry_risk():
    """So the badge list is not hardcoded in JS, where it would drift when an
    action is added (design §4, decision 3b)."""
    source = (REPO_ROOT / "src/athena/darvax/api/routes.py").read_text(encoding="utf-8")
    assert "risk_bearing" in source
    assert "RISK_BEARING_ACTIONS" in source


def test_the_action_vocabulary_is_not_reimplemented_in_javascript():
    """A JS mapping from signal_type to an action word would be a second source
    of truth for advice, free to disagree with the engine (ADR-005).

    Deliberately **line**-scoped, not file-scoped. `darvax.js` already displays
    signal states in the DX-6c table, and DX-7c will legitimately use action
    names for styling and labels — a file-level check would fail on both and
    invite being deleted. What is actually forbidden is the two appearing
    *together*, which is what a lookup table or a ternary looks like:

        INSIDE_TOPMOST_BOX: 'WAIT'                      // caught
        cls = t === 'BELOW_BOX_BOTTOM' ? 'EXIT' : ''    // caught
        <td>${r.signal_type}</td>                       // fine
        <span class="act act-${r.action}">              // fine
    """
    states = ("BREAKOUT_RETEST", "INSIDE_TOPMOST_BOX", "BELOW_BOX_BOTTOM", "NO_BOX")
    actions = ("ENTER", "ENTER_ON_RETEST", "WAIT", "EXIT_IF_HELD", "NO_ENTRY")
    offenders = []
    for js in (REPO_ROOT / "src/athena/darvax/api/static").glob("*.js"):
        code = _strip_js_comments(js.read_text(encoding="utf-8"))
        for lineno, line in enumerate(code.splitlines(), start=1):
            hit_state = next((s for s in states if s in line), None)
            if hit_state is None:
                continue
            # Strip the state first: BREAKOUT_RETEST contains no action word,
            # but NO_BOX-style names must not be matched against by accident.
            rest = line.replace(hit_state, "")
            hit_action = next((a for a in actions if a in rest), None)
            if hit_action is not None:
                offenders.append(f"{js.name}:{lineno} {hit_state} -> {hit_action}")
    assert offenders == [], (
        f"advice must come from the engine, not be re-derived in JS: {offenders}"
    )


def test_that_guard_would_actually_catch_a_javascript_mapping():
    """Proves the check above is not vacuous — it currently passes because no JS
    maps states to actions, which is indistinguishable from a broken check."""
    bad = "const ACT = { INSIDE_TOPMOST_BOX: 'WAIT' };"
    states = ("INSIDE_TOPMOST_BOX",)
    actions = ("WAIT",)
    line = _strip_js_comments(bad)
    hit_state = next((s for s in states if s in line), None)
    rest = line.replace(hit_state, "")
    assert hit_state and any(a in rest for a in actions)
