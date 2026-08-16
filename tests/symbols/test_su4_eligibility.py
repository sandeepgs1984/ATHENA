"""SU-4: eligibility profiles (ADR-011 §4).

Two properties carry this milestone: **every exclusion is attributable to one
named rule with a reason**, and **no threshold was invented**. The second
matters as much as the first — a liquidity floor guessed here would silently
exclude symbols on data the catalogue does not contain.
"""

from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal
from pathlib import Path

import pytest

from athena.domain.market import Instrument
from athena.errors import ConfigError
from athena.symbols import build_symbol_records
from athena.symbols.eligibility import (
    PROFILES,
    UNRESTRICTED_EQUITY_SERIES,
    apply_profile,
    describe_profile,
)

OBSERVED = datetime(2026, 8, 15, 12, 0, tzinfo=timezone.utc)


def record(symbol: str, name: str | None = None):
    return build_symbol_records(
        [Instrument(
            instrument_id=f"NSE:{symbol}", symbol=symbol, exchange="NSE", series="EQ",
            name=name or f"{symbol} LIMITED", lot_size=1,
            tick_size=Decimal("0.05"), status="ACTIVE",
        )],
        observed_at=OBSERVED, source="kite",
    )[0]


# --------------------------------------------------------------------------- #
# 1. Every exclusion is attributable
# --------------------------------------------------------------------------- #


def test_each_exclusion_names_a_rule_and_a_reason():
    """'Why isn't X in my scan?' must always have an answer."""
    result = apply_profile("darvax_discovery", [
        record("GOODCO"),
        record("RESTRICTED-BE"),
        record("SOMEBEES", name="NIPPON GOLD BEES"),
        record("660GS30-SG"),
    ])
    assert result.eligible == ("NSE:GOODCO",)
    by_symbol = {e.instrument_id: e for e in result.excluded}
    assert by_symbol["NSE:RESTRICTED-BE"].rule == "unrestricted_equity_series"
    assert by_symbol["NSE:SOMEBEES"].rule == "not_a_fund"
    assert by_symbol["NSE:660GS30-SG"].rule == "known_board"
    for exclusion in result.excluded:
        assert exclusion.reason, "every exclusion must carry a reason in words"


def test_a_symbol_is_attributed_to_exactly_one_rule():
    """Rules stop at the first match, so a reader gets one cause rather than a
    list to weigh. A government security fails both board and series checks; it
    is reported under the first."""
    result = apply_profile("darvax_discovery", [record("660GS30-SG")])
    assert len(result.excluded) == 1
    assert result.excluded[0].rule == "known_board"


def test_counts_by_rule_summarise_a_large_run():
    result = apply_profile("darvax_discovery", [
        record("A"), record("B-BE"), record("C-BE"), record("DETF", name="SOME ETF"),
    ])
    assert result.counts_by_rule() == {"unrestricted_equity_series": 2, "not_a_fund": 1}


def test_profiles_are_describable():
    described = dict(describe_profile("darvax_discovery"))
    assert set(described) == {"known_board", "unrestricted_equity_series", "not_a_fund"}
    assert all(text for text in described.values())


# --------------------------------------------------------------------------- #
# 2. The rules themselves
# --------------------------------------------------------------------------- #


@pytest.mark.parametrize(
    ("symbol", "kept"),
    [
        ("RATNAVEER", True),
        ("JGCHEM", True),
        ("PNGSREVA", True),
        ("SOMETHING-BE", False),   # trade-for-trade
        ("SOMETHING-BZ", False),   # surveillance
        ("SOMETHING-IV", False),   # unpaid call
        ("SOMESME-SM", False),     # SME series is not ordinary equity
        ("660GS30-SG", False),     # government debt
    ],
)
def test_only_ordinary_equity_survives(symbol, kept):
    result = apply_profile("darvax_discovery", [record(symbol)])
    assert bool(result.eligible) is kept


def test_restricted_series_are_excluded_deliberately():
    """BE/BZ are trade-for-trade, usually a surveillance measure. A breakout
    scanner should not be handed instruments the exchange has already flagged."""
    assert "EQ" in UNRESTRICTED_EQUITY_SERIES
    for restricted in ("BE", "BZ", "IV"):
        assert restricted not in UNRESTRICTED_EQUITY_SERIES


def test_unknown_board_is_excluded_by_the_first_rule():
    """SU-1 refuses to guess a board; SU-4 refuses to include what SU-1 could
    not establish."""
    result = apply_profile("darvax_discovery", [record("MYSTERY-ZZ")])
    assert result.eligible == ()
    assert result.excluded[0].rule == "known_board"
    assert "unrecognised suffix" in result.excluded[0].reason


def test_funds_are_identified_by_name_as_well_as_symbol():
    """The dump has no instrument-kind column, so a fund is only identifiable by
    how it is named — a heuristic, applied to both fields."""
    assert apply_profile("darvax_discovery", [record("NIFTYBEES")]).eligible == ()
    assert apply_profile(
        "darvax_discovery", [record("SOMECODE", name="MOTILAL OSWAL ETF")]
    ).eligible == ()


# --------------------------------------------------------------------------- #
# 3. What was deliberately not invented
# --------------------------------------------------------------------------- #


def test_no_liquidity_or_history_threshold_exists():
    """ADR-011 §4 fixes that eligibility is explicit and explainable; it fixes
    no numbers. Liquidity cannot be measured from the catalogue at all —
    `last_price` is 0 for every row — and only from candles, which exist only
    for symbols already ingested. Guessing a floor would exclude on data the
    filter does not have.
    """
    source = (
        Path("src/athena/symbols/eligibility.py").read_text(encoding="utf-8")
    )
    code = "\n".join(
        line for line in source.splitlines()
        if not line.strip().startswith("#") and not line.strip().startswith('"')
    )
    for banned in ("min_volume", "min_turnover", "min_history", "MIN_LIQUIDITY"):
        assert banned not in code, f"a threshold ({banned}) was invented"
    assert {rule.name for rule in PROFILES["darvax_discovery"]} == {
        "known_board", "unrestricted_equity_series", "not_a_fund"
    }


def test_sme_is_not_an_eligibility_rule():
    """ADR-011 §2.2: SME is a board, so including it is a universe composition
    choice visible in config — not a threshold buried in a filter."""
    assert not any(
        "sme" in rule.name.lower() for rule in PROFILES["darvax_discovery"]
    )


def test_the_none_profile_excludes_nothing():
    """`athena_core` uses it, so it must be exactly a pass-through."""
    given = [record("A"), record("B-BE"), record("660GS30-SG")]
    result = apply_profile("none", given)
    assert len(result.eligible) == 3
    assert result.excluded == ()


def test_an_unknown_profile_raises():
    with pytest.raises(ConfigError, match="unknown eligibility profile"):
        apply_profile("nope", [record("A")])


def test_applying_a_profile_is_deterministic():
    given = [record("B"), record("A"), record("C-BE")]
    assert apply_profile("darvax_discovery", given) == apply_profile("darvax_discovery", given)
    assert apply_profile("darvax_discovery", given).eligible == ("NSE:A", "NSE:B")
