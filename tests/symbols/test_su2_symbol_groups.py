"""SU-2: symbol group membership (ADR-011).

The properties that matter: membership is **metadata on one canonical symbol**
rather than a duplicated record, it is **dated** so a pre-rebalance screen stays
reproducible, and an unresolvable constituent is **surfaced rather than
dropped** — a symbol missing from the master is precisely the coverage hole this
work exists to expose.
"""

from __future__ import annotations

import json
from datetime import date, datetime, timezone
from decimal import Decimal
from pathlib import Path

import pytest

from athena.data.index_constituents import load_index_constituent_snapshot
from athena.data.store.repository import SqliteRepository
from athena.domain.market import Instrument
from athena.symbols import Board, build_symbol_records
from athena.symbols.groups import (
    GROUP_MAINBOARD,
    GROUP_OWNER_CANDIDATES,
    GROUP_SME,
    GroupKind,
    board_memberships,
    index_group_name,
    index_memberships,
    owner_candidate_memberships,
)

REPO_ROOT = Path(__file__).resolve().parents[2]
SNAPSHOT_DIR = REPO_ROOT / "data" / "index_constituents" / "2026-07-31"
OBSERVED = datetime(2026, 8, 15, 12, 0, tzinfo=timezone.utc)
EFFECTIVE = date(2026, 7, 31)


def instrument(symbol: str) -> Instrument:
    return Instrument(
        instrument_id=f"NSE:{symbol}", symbol=symbol, exchange="NSE", series="EQ",
        name=f"{symbol} LIMITED", lot_size=1, tick_size=Decimal("0.05"), status="ACTIVE",
    )


def records(*symbols: str):
    return build_symbol_records(
        [instrument(s) for s in symbols], observed_at=OBSERVED, source="kite"
    )


@pytest.fixture()
def repo(tmp_path: Path) -> SqliteRepository:
    r = SqliteRepository(tmp_path / "athena.db")
    r.initialize()
    yield r
    r.close()


# --------------------------------------------------------------------------- #
# 1. Group naming
# --------------------------------------------------------------------------- #


@pytest.mark.parametrize(
    ("key", "expected"),
    [("nifty_50", "NIFTY_50"), ("nifty_midcap_100", "NIFTY_MIDCAP_100"),
     ("nifty_psu_bank", "NIFTY_PSU_BANK")],
)
def test_index_group_names_are_a_pure_renaming(key, expected):
    """Deliberately not a lookup table: an invented mapping is a place for a
    group to be silently misattributed to the wrong index."""
    assert index_group_name(key) == expected


def test_empty_index_key_is_rejected():
    with pytest.raises(ValueError):
        index_group_name("  ")


# --------------------------------------------------------------------------- #
# 2. Index membership, from the real checksum-verified snapshot
# --------------------------------------------------------------------------- #


def test_index_membership_is_built_from_the_real_snapshot():
    keys = {e["key"] for e in json.loads((SNAPSHOT_DIR / "manifest.json").read_text())["indices"]}
    snapshot = load_index_constituent_snapshot(
        SNAPSHOT_DIR / "manifest.json", expected_index_keys=keys
    )
    nifty50 = snapshot.by_key()["nifty_50"]
    master = records(*nifty50.symbols)

    build = index_memberships(
        [("nifty_50", nifty50.symbols)],
        effective_date=snapshot.effective_date,
        source=snapshot.provider,
        records=master,
    )
    assert len(build.memberships) == 50
    assert build.unresolved == ()
    assert {m.group_name for m in build.memberships} == {"NIFTY_50"}
    assert all(m.kind is GroupKind.INDEX for m in build.memberships)
    assert all(m.effective_date == EFFECTIVE for m in build.memberships)


def test_a_constituent_absent_from_the_master_is_surfaced_not_dropped():
    """A stale snapshot, a renamed ticker or a catalogue gap must be visible.
    Silently discarding it hides the coverage hole ADR-011 exists to expose."""
    build = index_memberships(
        [("nifty_50", ["RELIANCE", "GHOSTCO"])],
        effective_date=EFFECTIVE, source="NSE", records=records("RELIANCE"),
    )
    assert [m.instrument_id for m in build.memberships] == ["NSE:RELIANCE"]
    assert build.unresolved == (("NIFTY_50", "GHOSTCO"),)


def test_symbol_resolution_is_case_insensitive():
    build = index_memberships(
        [("nifty_it", ["infy"])], effective_date=EFFECTIVE, source="NSE",
        records=records("INFY"),
    )
    assert [m.instrument_id for m in build.memberships] == ["NSE:INFY"]


# --------------------------------------------------------------------------- #
# 3. Board membership
# --------------------------------------------------------------------------- #


def test_boards_are_derived_from_the_symbol_master():
    build = board_memberships(records("RELIANCE", "SOMESME-SM"), effective_date=EFFECTIVE)
    by_group = {m.group_name: m.instrument_id for m in build.memberships}
    assert by_group[GROUP_MAINBOARD] == "NSE:RELIANCE"
    assert by_group[GROUP_SME] == "NSE:SOMESME-SM"
    assert all(m.kind is GroupKind.BOARD for m in build.memberships)


def test_an_unknown_board_joins_neither_group():
    """SU-1's honest classification would be pointless if SU-2 then swept
    unclassified instruments into the main board, where a scanner would treat
    them as ordinary equity."""
    master = records("660GS30-SG", "MYSTERY-ZZ")
    assert all(r.board is Board.UNKNOWN for r in master)
    assert board_memberships(master, effective_date=EFFECTIVE).memberships == ()


# --------------------------------------------------------------------------- #
# 4. Owner candidates — a first-class group (ADR-011 §2.1)
# --------------------------------------------------------------------------- #


def test_owner_candidates_become_a_group():
    build = owner_candidate_memberships(
        ["JGCHEM", "RATNAVEER"], effective_date=EFFECTIVE,
        records=records("JGCHEM", "RATNAVEER"),
    )
    assert {m.instrument_id for m in build.memberships} == {"NSE:JGCHEM", "NSE:RATNAVEER"}
    assert all(m.group_name == GROUP_OWNER_CANDIDATES for m in build.memberships)
    assert all(m.kind is GroupKind.CURATED for m in build.memberships)


def test_owner_candidates_accept_qualified_or_bare_symbols():
    build = owner_candidate_memberships(
        ["NSE:JGCHEM", "ratnaveer"], effective_date=EFFECTIVE,
        records=records("JGCHEM", "RATNAVEER"),
    )
    assert len(build.memberships) == 2


def test_an_unknown_candidate_is_surfaced():
    build = owner_candidate_memberships(
        ["GHOSTCO"], effective_date=EFFECTIVE, records=records("JGCHEM")
    )
    assert build.memberships == ()
    assert build.unresolved == ((GROUP_OWNER_CANDIDATES, "GHOSTCO"),)


# --------------------------------------------------------------------------- #
# 5. Persistence and dated semantics
# --------------------------------------------------------------------------- #


def test_membership_round_trips(repo: SqliteRepository):
    build = index_memberships(
        [("nifty_it", ["INFY", "TCS"])], effective_date=EFFECTIVE, source="NSE",
        records=records("INFY", "TCS"),
    )
    assert repo.upsert_group_memberships(build.memberships) == 2
    assert repo.list_group_members("NIFTY_IT") == ["NSE:INFY", "NSE:TCS"]
    assert repo.list_known_groups() == ["NIFTY_IT"]


def test_no_symbol_record_is_duplicated_per_group(repo: SqliteRepository):
    """ADR-011 §2: membership is metadata on one canonical symbol."""
    master = records("INFY")
    repo.upsert_symbol_records(master)
    for group, symbols in (("nifty_50", ["INFY"]), ("nifty_it", ["INFY"])):
        repo.upsert_group_memberships(
            index_memberships([(group, symbols)], effective_date=EFFECTIVE,
                              source="NSE", records=master).memberships
        )
    assert len(repo.list_symbol_records()) == 1, "one symbol row, many groups"
    assert [g for g, _ in repo.list_groups_for_symbol("NSE:INFY")] == ["NIFTY_50", "NIFTY_IT"]


def test_a_rebalance_adds_history_rather_than_overwriting(repo: SqliteRepository):
    """The reason membership is dated: a screen run before a rebalance must stay
    reproducible after it."""
    old, new = date(2026, 7, 31), date(2026, 9, 30)
    master = records("AAA", "BBB")
    repo.upsert_group_memberships(index_memberships(
        [("nifty_50", ["AAA"])], effective_date=old, source="NSE", records=master).memberships)
    repo.upsert_group_memberships(index_memberships(
        [("nifty_50", ["BBB"])], effective_date=new, source="NSE", records=master).memberships)

    assert repo.list_group_members("NIFTY_50") == ["NSE:BBB"], "latest by default"
    assert repo.list_group_members("NIFTY_50", as_of=old) == ["NSE:AAA"], "history intact"
    assert repo.latest_group_effective_date("NIFTY_50") == new


def test_as_of_before_any_snapshot_is_empty(repo: SqliteRepository):
    repo.upsert_group_memberships(index_memberships(
        [("nifty_50", ["AAA"])], effective_date=EFFECTIVE, source="NSE",
        records=records("AAA")).memberships)
    assert repo.list_group_members("NIFTY_50", as_of=date(2020, 1, 1)) == []


def test_reloading_the_same_snapshot_is_idempotent(repo: SqliteRepository):
    build = index_memberships([("nifty_50", ["AAA"])], effective_date=EFFECTIVE,
                              source="NSE", records=records("AAA"))
    repo.upsert_group_memberships(build.memberships)
    repo.upsert_group_memberships(build.memberships)
    assert repo.list_group_members("NIFTY_50") == ["NSE:AAA"]


def test_an_unknown_group_is_empty_rather_than_an_error(repo: SqliteRepository):
    """A resolver asking about a group nobody has loaded should get an empty
    universe, not an exception — 'no members' is a legitimate answer."""
    assert repo.list_group_members("NIFTY_500") == []
    assert repo.latest_group_effective_date("NIFTY_500") is None


def test_empty_input_is_a_no_op(repo: SqliteRepository):
    assert repo.upsert_group_memberships([]) == 0


# --------------------------------------------------------------------------- #
# 6. Scope discipline
# --------------------------------------------------------------------------- #


def test_the_derived_group_is_not_materialised_here():
    """ADR-011 §2.3: NSE_ALL_ELIGIBLE_EQUITY is whatever its rules resolve to,
    and those rules are SU-4's. Building a frozen list of it now would turn a
    rule-defined group into exactly the fixed list §2.3 forbids."""
    import athena.symbols.groups as groups

    assert {n for n in dir(groups) if n.endswith("_memberships")} == {
        "index_memberships",
        "board_memberships",
        "owner_candidate_memberships",
    }, "a builder for the derived group would freeze a rule-defined universe"
    assert not hasattr(groups, "GROUP_ALL_ELIGIBLE_EQUITY"), (
        "the derived group must not get a materialised constant here"
    )


def test_su2_changes_no_consumer_behaviour(repo: SqliteRepository):
    """Additive: nothing reads symbol_group yet (SU-3 does)."""
    before = repo.list_instruments()
    repo.upsert_group_memberships(index_memberships(
        [("nifty_50", ["AAA"])], effective_date=EFFECTIVE, source="NSE",
        records=records("AAA")).memberships)
    assert repo.list_instruments() == before
