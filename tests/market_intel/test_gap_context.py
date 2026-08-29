"""Gap Engine (ID-5C) — previous-trading-session-close -> current-session-
open price transition. NOT an intraday return, NOT gap-fill/-hold/
-rejection/-continuation, no BUY/SELL/probability anywhere here; see
`athena.intraday.gap_engine`."""

from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from zoneinfo import ZoneInfo

import pytest

from athena.intraday import GapDirection, GapEngine

IST = ZoneInfo("Asia/Kolkata")
IID = "NSE:TEST"
DAY = date(2026, 8, 28)
PREV_DAY = date(2026, 8, 27)
AS_OF = datetime(2026, 8, 28, 9, 30, tzinfo=IST)


@pytest.fixture()
def engine() -> GapEngine:
    return GapEngine()


def _assess(engine, *, prev_date=PREV_DAY, prev_close="100", current_open="103", as_of=AS_OF):
    return engine.assess(
        IID, as_of=as_of, session_date=DAY,
        previous_session_date=prev_date,
        previous_session_close=Decimal(prev_close) if prev_close is not None else None,
        current_session_open=Decimal(current_open) if current_open is not None else None,
    )


# --------------------------------------------------------------------------- #
# 1-4 — exact formula, both directions, exact zero
# --------------------------------------------------------------------------- #

def test_1_positive_gap_up(engine):
    gc = _assess(engine, prev_close="100", current_open="103")
    assert gc.available is True
    assert gc.gap_pct == Decimal("3")
    assert gc.direction is GapDirection.GAP_UP


def test_2_negative_gap_down(engine):
    gc = _assess(engine, prev_close="100", current_open="97")
    assert gc.gap_pct == Decimal("-3")
    assert gc.direction is GapDirection.GAP_DOWN


def test_3_exact_zero_gap_is_flat(engine):
    gc = _assess(engine, prev_close="100", current_open="100")
    assert gc.gap_pct == Decimal("0")
    assert gc.direction is GapDirection.FLAT


def test_4_exact_formula_value(engine):
    gc = _assess(engine, prev_close="405.20", current_open="412.50")
    expected = (Decimal("412.50") - Decimal("405.20")) / Decimal("405.20") * Decimal(100)
    assert gc.gap_pct == expected
    assert isinstance(gc.gap_pct, Decimal)


# --------------------------------------------------------------------------- #
# 5-7 — availability / UNKNOWN semantics
# --------------------------------------------------------------------------- #

def test_5_previous_close_missing_is_unknown(engine):
    gc = _assess(engine, prev_close=None)
    assert gc.available is False
    assert gc.gap_pct is None
    assert gc.direction is GapDirection.UNKNOWN


def test_6_current_open_missing_is_unknown(engine):
    gc = _assess(engine, current_open=None)
    assert gc.available is False
    assert gc.direction is GapDirection.UNKNOWN


def test_7_both_missing_is_unknown(engine):
    gc = _assess(engine, prev_close=None, current_open=None)
    assert gc.available is False
    assert gc.direction is GapDirection.UNKNOWN


def test_previous_session_date_none_is_unknown(engine):
    gc = engine.assess(
        IID, as_of=AS_OF, session_date=DAY,
        previous_session_date=None, previous_session_close=None,
        current_session_open=Decimal("100"),
    )
    assert gc.available is False


def test_zero_previous_close_is_unknown_not_a_division_error(engine):
    gc = _assess(engine, prev_close="0")
    assert gc.available is False
    assert gc.gap_pct is None
    assert gc.direction is GapDirection.UNKNOWN


# --------------------------------------------------------------------------- #
# 17/19/20 — determinism, Decimal preserved, explanation
# --------------------------------------------------------------------------- #

def test_17_explicit_as_of_determinism(engine):
    a = _assess(engine)
    b = GapEngine().assess(
        IID, as_of=AS_OF, session_date=DAY, previous_session_date=PREV_DAY,
        previous_session_close=Decimal("100"), current_session_open=Decimal("103"),
    )
    assert a == b


def test_19_decimal_arithmetic_preserved(engine):
    gc = _assess(engine)
    assert isinstance(gc.gap_pct, Decimal)
    assert isinstance(gc.previous_session_close, Decimal)
    assert isinstance(gc.current_session_open, Decimal)


def test_20_explanation_is_deterministic_and_mandatory(engine):
    a = _assess(engine)
    b = _assess(engine)
    assert a.explanation == b.explanation
    assert a.explanation
    unavailable = _assess(engine, prev_close=None)
    assert unavailable.explanation
    assert "unavailable" in unavailable.explanation.lower()


def test_naive_as_of_rejected(engine):
    with pytest.raises(ValueError, match="timezone-aware"):
        engine.assess(
            IID, as_of=datetime(2026, 8, 28, 9, 30), session_date=DAY,
            previous_session_date=PREV_DAY, previous_session_close=Decimal("100"),
            current_session_open=Decimal("103"),
        )


def test_immutable_frozen_dataclass(engine):
    gc = _assess(engine)
    with pytest.raises(AttributeError):
        gc.gap_pct = Decimal("999")  # frozen -- no mutation


def test_no_buy_sell_or_probability_concept_exists_on_the_contract():
    """Structural proof, not just a promise: the dataclass has no such
    fields to accidentally populate, and direction has no magnitude band."""
    import dataclasses

    from athena.intraday.gap_models import GapContext as _GC
    forbidden = {"buy", "sell", "trade", "probability", "score", "rank", "quality_grade"}
    names = {f.name.lower() for f in dataclasses.fields(_GC)}
    assert not (names & forbidden), f"GapContext has a forbidden field: {names & forbidden}"
    direction_values = {v.value for v in GapDirection}
    assert direction_values == {"GAP_UP", "GAP_DOWN", "FLAT", "UNKNOWN"}
