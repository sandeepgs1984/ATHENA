"""SU-1: canonical symbol master (ADR-011).

The assertions that matter here are the ones about **provenance and honesty**:
that an inferred series is never reported as authoritative, that an
unclassifiable instrument is never quietly promoted to equity, and that the
catalogue of what exists stays separate from the record of what was ingested.
Those are the properties ADR-011 was written to establish; the CRUD around them
is mechanics.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from decimal import Decimal
from pathlib import Path

import pytest

from athena.data.store.repository import SqliteRepository
from athena.data.store.schema import SCHEMA_VERSION
from athena.domain.market import Instrument
from athena.symbols import (
    Board,
    SeriesSource,
    build_symbol_records,
    classify_symbol,
)

OBSERVED = datetime(2026, 8, 15, 12, 0, tzinfo=timezone.utc)


def instrument(symbol: str, **kw) -> Instrument:
    base = dict(
        instrument_id=f"NSE:{symbol}",
        symbol=symbol,
        exchange="NSE",
        # Deliberately the value KiteProvider fabricates for every NSE row.
        series="EQ",
        name=f"{symbol} LIMITED",
        lot_size=1,
        tick_size=Decimal("0.05"),
        status="ACTIVE",
    )
    base.update(kw)
    return Instrument(**base)


# --------------------------------------------------------------------------- #
# 1. Classification — inference, and honest about being inference
# --------------------------------------------------------------------------- #


@pytest.mark.parametrize(
    ("symbol", "series", "board"),
    [
        ("RATNAVEER", "EQ", Board.MAINBOARD),
        ("JGCHEM", "EQ", Board.MAINBOARD),
        ("PNGSREVA", "EQ", Board.MAINBOARD),
        ("SOMESME-SM", "SM", Board.SME),
        ("660GS30-SG", "SG", Board.UNKNOWN),
        ("91DTB-TB", "TB", Board.UNKNOWN),
        ("RELIANCE-BE", "BE", Board.MAINBOARD),
    ],
)
def test_series_and_board_are_inferred_from_the_symbol(symbol, series, board):
    got_series, source, got_board, reason = classify_symbol(symbol)
    assert got_series == series
    assert got_board is board
    assert source is SeriesSource.INFERRED_SUFFIX
    assert reason, "every classification must state its reasoning"


def test_an_inference_is_never_reported_as_authoritative():
    """`nse_official` is reserved for a source we do not yet have. Reporting an
    inference under it would make a convention look like a published contract."""
    for symbol in ("RATNAVEER", "SOMESME-SM", "660GS30-SG"):
        _, source, _, _ = classify_symbol(symbol)
        assert source is not SeriesSource.NSE_OFFICIAL


def test_an_unrecognised_suffix_is_not_promoted_to_equity():
    """The accident ADR-011 exists to prevent: an unclassifiable instrument
    silently joining the equity universe."""
    series, source, board, reason = classify_symbol("MYSTERY-ZZ")
    assert board is Board.UNKNOWN
    assert series == "ZZ"
    assert "unrecognised" in reason
    assert source is SeriesSource.INFERRED_SUFFIX


@pytest.mark.parametrize(
    "symbol",
    [
        "BAJAJ-AUTO",   # NIFTY 50 and NIFTY AUTO constituent
        "NAM-INDIA",    # Nippon Life India AMC
        "HCL-INSYS",    # HCL Infosystems
        "BOSCH-HCIL",   # Bosch Home Comfort
        "UMIYA-MRO",    # Umiya Buildcon
        "KLBRENG-B",    # Kilburn Engineering
        "MCCHRLS-B",    # Mac Charles (India)
    ],
)
def test_a_hyphen_in_a_company_name_is_not_a_series(symbol):
    """Found in production 2026-08-16: these seven real equities were classified
    `board=UNKNOWN` because the text after the final hyphen was read as a series
    code, so they appeared in no board-derived universe at all. BAJAJ-AUTO is
    the proof — it resolved into NIFTY_50 by index membership while being
    invisible to `darvax_discovery`."""
    series, _, board, reason = classify_symbol(symbol, tradable=True)
    assert board is Board.MAINBOARD, f"{symbol} is ordinary equity"
    assert series == "EQ"
    assert "company name" in reason


def test_the_two_character_boundary_is_what_separates_the_two_cases():
    """A suffix the right *shape* for a series stays conservative even though it
    is unknown; one the wrong shape is read as a name. Asserted together because
    the fix is only correct if both halves hold — widening the name rule to all
    unrecognised suffixes would promote debt and index rows into equity."""
    _, _, unknown_code_board, _ = classify_symbol("MYSTERY-ZZ", tradable=True)
    _, _, name_board, _ = classify_symbol("MYSTERY-ZZZ", tradable=True)
    assert unknown_code_board is Board.UNKNOWN
    assert name_board is Board.MAINBOARD


@pytest.mark.parametrize(
    "symbol",
    [
        "NIFTY 50",           # no suffix at all — took the plain-EQ default
        "NIFTY BANK",
        "BHARATBOND-APR30",   # name-shaped suffix, but genuinely a debt index
        "HANGSENG BEES-NAV",
        "RELIANCE",           # even an unmistakably equity-shaped symbol
    ],
)
def test_an_untradable_instrument_is_never_placed_on_a_board(symbol):
    """Tradability is a precondition for being on a board. Without this, symbol
    shape alone put NIFTY 50 and 131 other index rows inside `darvax_discovery`,
    because an index carries no series suffix to give it away."""
    _, _, board, reason = classify_symbol(symbol, tradable=False)
    assert board is Board.UNKNOWN
    assert "tick size" in reason


def test_unknown_tradability_falls_back_to_symbol_shape():
    """`None` means nobody established it — which must not be read as `False`,
    or every caller that omits the argument would classify everything UNKNOWN."""
    _, _, board, _ = classify_symbol("RATNAVEER", tradable=None)
    assert board is Board.MAINBOARD


def test_sme_is_a_board_not_a_threshold():
    """ADR-011 §2.2 — SME must be expressible as membership, so including or
    excluding it is a visible decision rather than a filter side effect."""
    _, _, board, reason = classify_symbol("XYZ-SM")
    assert board is Board.SME
    assert "SME" in reason


def test_empty_symbol_is_rejected():
    with pytest.raises(ValueError):
        classify_symbol("   ")


# --------------------------------------------------------------------------- #
# 2. Building records from a provider catalogue
# --------------------------------------------------------------------------- #


def test_the_providers_fabricated_series_is_ignored():
    """KiteProvider reports `series="EQ"` for every NSE row because the dump has
    no series column. Trusting it would mark treasury bills as equity."""
    records = build_symbol_records(
        [instrument("660GS30-SG", series="EQ")], observed_at=OBSERVED, source="kite"
    )
    assert records[0].series == "SG", "provider's fabricated EQ must not win"
    assert records[0].board is Board.UNKNOWN


def test_tradability_is_derived_from_the_tick_size_the_provider_already_gives():
    """The catalogue needs no new field and no new fetch: an index row arrives
    with `tick_size=0`, which is exactly the signal that it is not a listing.
    Asserting it here rather than only on `classify_symbol` is the point — the
    defect was that nobody *passed* the signal, not that the rule was missing."""
    index_row = instrument("NIFTY 50", tick_size=Decimal("0"))
    equity_row = instrument("BAJAJ-AUTO")

    by_id = {
        r.instrument_id: r
        for r in build_symbol_records(
            [index_row, equity_row], observed_at=OBSERVED, source="kite"
        )
    }
    assert by_id["NSE:NIFTY 50"].board is Board.UNKNOWN
    assert by_id["NSE:BAJAJ-AUTO"].board is Board.MAINBOARD


def test_lot_size_cannot_carry_the_tradability_signal():
    """Guards the trap that broke the first attempt at this fix. The NSE dump
    reports lot_size 0 for index rows, but `Instrument` requires `>= 1` and
    `KiteProvider` clamps with `max(lot, 1)` — so a rule keyed on lot size would
    compile, pass a hand-built unit test, and silently never fire in production.
    If this invariant is ever relaxed, revisit `catalog.build_symbol_records`."""
    with pytest.raises(ValueError, match="lot_size"):
        instrument("NIFTY 50", lot_size=0)


def test_records_carry_identity_and_provenance():
    records = build_symbol_records(
        [instrument("RATNAVEER")], observed_at=OBSERVED, source="kite"
    )
    r = records[0]
    assert r.instrument_id == "NSE:RATNAVEER"
    assert r.symbol == "RATNAVEER" and r.exchange == "NSE"
    assert r.source == "kite"
    assert r.first_seen == OBSERVED and r.last_seen == OBSERVED
    assert r.classification_reason


def test_no_broker_token_leaks_into_the_canonical_model():
    """ADR-002 provider independence: a vendor's instrument token must not
    become part of the canonical symbol identity."""
    fields = set(build_symbol_records(
        [instrument("RATNAVEER")], observed_at=OBSERVED, source="kite"
    )[0].__dataclass_fields__)
    for banned in ("instrument_token", "token", "exchange_token"):
        assert banned not in fields


def test_observed_at_must_be_timezone_aware():
    with pytest.raises(ValueError):
        build_symbol_records([instrument("X")], observed_at=datetime(2026, 8, 15), source="kite")


def test_first_seen_is_preserved_across_a_rebuild():
    """`first_seen` records when a symbol was first catalogued. Resetting it on
    every refresh would erase the listing history the column exists to hold."""
    original = OBSERVED - timedelta(days=200)
    records = build_symbol_records(
        [instrument("RATNAVEER")],
        observed_at=OBSERVED,
        source="kite",
        known_first_seen=lambda iid: original if iid == "NSE:RATNAVEER" else None,
    )
    assert records[0].first_seen == original
    assert records[0].last_seen == OBSERVED


def test_building_is_deterministic():
    a = build_symbol_records([instrument("A"), instrument("B-SM")], observed_at=OBSERVED, source="kite")
    b = build_symbol_records([instrument("A"), instrument("B-SM")], observed_at=OBSERVED, source="kite")
    assert a == b


# --------------------------------------------------------------------------- #
# 3. Persistence
# --------------------------------------------------------------------------- #


@pytest.fixture()
def repo(tmp_path: Path) -> SqliteRepository:
    r = SqliteRepository(tmp_path / "athena.db")
    r.initialize()
    yield r
    r.close()


def test_schema_version_is_recorded_and_covers_symbol_master(repo: SqliteRepository):
    """Asserted as an invariant rather than against a literal — pinning the
    number is what broke the equivalent DarvaX test on its own schema bump.

    Uses ``verify_integrity()``'s ``schema_version_ok`` rather than reading the
    table directly, since that is the repository's own public statement about
    whether the database matches the code.
    """
    assert SCHEMA_VERSION >= 13, "SU-1 introduced symbol_master at v13"
    report = repo.verify_integrity()
    assert report.schema_version_ok, report.issues
    assert repo.upsert_symbol_records(
        build_symbol_records([instrument("X")], observed_at=OBSERVED, source="kite")
    ) == 1


def test_records_round_trip_with_classification_intact(repo: SqliteRepository):
    repo.upsert_symbol_records(build_symbol_records(
        [instrument("RATNAVEER"), instrument("SOME-SM"), instrument("660GS30-SG")],
        observed_at=OBSERVED, source="kite",
    ))
    got = {r.instrument_id: r for r in repo.list_symbol_records()}
    assert len(got) == 3

    sme = got["NSE:SOME-SM"]
    assert sme.board is Board.SME and sme.series == "SM"
    assert sme.series_source is SeriesSource.INFERRED_SUFFIX
    assert "SME" in sme.classification_reason
    assert isinstance(sme.tick_size, Decimal)
    assert sme.first_seen == OBSERVED


def test_records_can_be_filtered_by_series_and_board(repo: SqliteRepository):
    repo.upsert_symbol_records(build_symbol_records(
        [instrument("EQ1"), instrument("EQ2"), instrument("S1-SM"), instrument("D1-SG")],
        observed_at=OBSERVED, source="kite",
    ))
    assert {r.symbol for r in repo.list_symbol_records(series="EQ")} == {"EQ1", "EQ2"}
    assert {r.symbol for r in repo.list_symbol_records(board=Board.SME.value)} == {"S1-SM"}
    assert {r.symbol for r in repo.list_symbol_records(board=Board.MAINBOARD.value)} == {"EQ1", "EQ2"}


def test_upsert_is_idempotent_and_preserves_first_seen(repo: SqliteRepository):
    """A refresh updates what a symbol *is* but never when it was first seen."""
    later = OBSERVED + timedelta(days=30)
    repo.upsert_symbol_records(build_symbol_records(
        [instrument("RATNAVEER")], observed_at=OBSERVED, source="kite"))
    repo.upsert_symbol_records(build_symbol_records(
        [instrument("RATNAVEER", name="RENAMED LTD")],
        observed_at=later, source="kite",
        known_first_seen=repo.symbol_master_first_seen,
    ))
    records = repo.list_symbol_records()
    assert len(records) == 1, "a refresh must update in place, not duplicate"
    assert records[0].first_seen == OBSERVED, "first_seen must survive a refresh"
    assert records[0].last_seen == later
    assert records[0].name == "RENAMED LTD"


def test_get_and_first_seen_lookups(repo: SqliteRepository):
    repo.upsert_symbol_records(build_symbol_records(
        [instrument("JGCHEM")], observed_at=OBSERVED, source="kite"))
    assert repo.get_symbol_record("NSE:JGCHEM").symbol == "JGCHEM"
    assert repo.get_symbol_record("NSE:NOPE") is None
    assert repo.symbol_master_first_seen("NSE:JGCHEM") == OBSERVED
    assert repo.symbol_master_first_seen("NSE:NOPE") is None


def test_empty_input_is_a_no_op(repo: SqliteRepository):
    assert repo.upsert_symbol_records([]) == 0


def test_limit_is_validated(repo: SqliteRepository):
    with pytest.raises(ValueError):
        repo.list_symbol_records(limit=0)


# --------------------------------------------------------------------------- #
# 4. The separation SU-1 exists to establish
# --------------------------------------------------------------------------- #


def test_symbol_master_is_independent_of_the_ingested_instruments_table(
    repo: SqliteRepository,
):
    """The whole point of ADR-011: a symbol can *exist* without having been
    ingested. Today the two are conflated, which is why RATNAVEER was invisible
    to every scanner despite being listed on NSE.
    """
    repo.upsert_symbol_records(build_symbol_records(
        [instrument("RATNAVEER"), instrument("PNGSREVA")],
        observed_at=OBSERVED, source="kite",
    ))
    # Nothing was ingested for either symbol.
    assert repo.list_instruments() == []
    # Yet both are known to exist, with classification and provenance.
    assert {r.symbol for r in repo.list_symbol_records()} == {"RATNAVEER", "PNGSREVA"}


def test_no_consumer_behaviour_changed(repo: SqliteRepository):
    """SU-1 is additive: populating the master must not alter what any existing
    engine sees, because nothing reads it yet."""
    before = repo.list_instruments()
    repo.upsert_symbol_records(build_symbol_records(
        [instrument("A"), instrument("B-SM")], observed_at=OBSERVED, source="kite"))
    assert repo.list_instruments() == before
