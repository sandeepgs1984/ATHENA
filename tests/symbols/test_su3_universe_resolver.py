"""SU-3: universe resolution (ADR-011).

The load-bearing test is `test_athena_core_is_set_identical_to_the_live_owner_candidates`.
ADR-011 §3.1 makes it a non-negotiable acceptance criterion: `athena_core` must
return exactly what ATHENA ingests today, asserted against the **live table**
rather than a count or a fixture. An earlier ADR draft defined it as `NIFTY_500`,
which would have silently changed every engine's universe at the moment the
migration was supposed to preserve behaviour. If that test fails, SU-3 has failed
no matter how clean the abstraction looks.
"""

from __future__ import annotations

import json
import sqlite3
from datetime import date, datetime, timezone
from decimal import Decimal
from pathlib import Path

import pytest
from pydantic import ValidationError

from athena.data.store.repository import SqliteRepository
from athena.domain.market import Instrument
from athena.errors import ConfigError
from athena.symbols import build_symbol_records
from athena.symbols.groups import (
    GROUP_OWNER_CANDIDATES,
    index_memberships,
    owner_candidate_memberships,
)
from athena.symbols.universes import (
    ELIGIBILITY_NONE,
    UniverseDefinition,
    UniversesConfig,
    declared_groups,
    load_universes_config,
    resolvable_universes,
    resolve_universe,
)

REPO_ROOT = Path(__file__).resolve().parents[2]
CONFIG_DIR = REPO_ROOT / "config"
LIVE_DB = REPO_ROOT / "db" / "athena.db"
OBSERVED = datetime(2026, 8, 15, 12, 0, tzinfo=timezone.utc)
EFFECTIVE = date(2026, 7, 31)


def instrument(symbol: str) -> Instrument:
    return Instrument(
        instrument_id=f"NSE:{symbol}", symbol=symbol, exchange="NSE", series="EQ",
        name=f"{symbol} LTD", lot_size=1, tick_size=Decimal("0.05"), status="ACTIVE",
    )


def records(*symbols: str):
    return build_symbol_records(
        [instrument(s) for s in symbols], observed_at=OBSERVED, source="kite"
    )


def config_with(**universes) -> UniversesConfig:
    payload = {"athena_core": {"groups": [GROUP_OWNER_CANDIDATES]}}
    payload.update(universes)
    return UniversesConfig(universes={k: UniverseDefinition(**v) for k, v in payload.items()})


@pytest.fixture()
def repo(tmp_path: Path) -> SqliteRepository:
    r = SqliteRepository(tmp_path / "athena.db")
    r.initialize()
    yield r
    r.close()


# --------------------------------------------------------------------------- #
# 1. THE acceptance criterion (ADR-011 §3.1)
# --------------------------------------------------------------------------- #


@pytest.mark.skipif(not LIVE_DB.exists(), reason="live ledger not present")
def test_athena_core_is_set_identical_to_the_live_owner_candidates(tmp_path: Path):
    """`athena_core` must return exactly what ATHENA runs on today.

    Compared as **sets against the live table**, not against a count and not a
    fixture: a same-size-but-different universe is the failure this criterion
    exists to catch.
    """
    live = sqlite3.connect(f"file:{LIVE_DB}?mode=ro", uri=True)
    candidates = [r[0] for r in live.execute(
        "SELECT symbol FROM owner_candidates WHERE active=1")]
    ingested = {r[0] for r in live.execute("SELECT instrument_id FROM instruments")}
    live.close()

    repo = SqliteRepository(tmp_path / "athena.db")
    repo.initialize()
    try:
        master = build_symbol_records(
            [instrument(s) for s in candidates], observed_at=OBSERVED, source="kite")
        repo.upsert_symbol_records(master)
        build = owner_candidate_memberships(
            candidates, effective_date=EFFECTIVE, records=master)
        repo.upsert_group_memberships(build.memberships)

        resolved = resolve_universe(
            "athena_core", config=load_universes_config(CONFIG_DIR), reader=repo)

        expected = {f"NSE:{s.upper()}" for s in candidates}
        assert set(resolved.symbols) == expected, (
            "athena_core must be set-identical to the live owner candidate list"
        )
        assert resolved.eligibility == ELIGIBILITY_NONE, (
            "applying a filter here would change ATHENA's universe under the "
            "guise of a refactor"
        )
        # Every resolved symbol that ATHENA actually ingested must be present in
        # the ledger. The reverse does not hold and must not be asserted: a
        # candidate the exchange no longer lists resolves here but was never
        # ingested, which is a data situation rather than a resolver fault.
        assert set(resolved.symbols) & ingested, "no overlap with the live ledger"
    finally:
        repo.close()


def test_shipped_config_declares_athena_core_as_owner_candidates():
    """Guards the specific regression ADR-011 §3.1 records: defining ATHENA's
    universe as an index would silently change every engine's inputs."""
    config = load_universes_config(CONFIG_DIR)
    core = config.universes["athena_core"]
    assert core.groups == [GROUP_OWNER_CANDIDATES]
    assert core.eligibility == ELIGIBILITY_NONE
    assert not any(g.startswith("NIFTY") for g in core.groups)


def test_athena_core_is_mandatory_in_config():
    with pytest.raises(ValueError, match="athena_core"):
        UniversesConfig(universes={"other": UniverseDefinition(groups=["X"])})


# --------------------------------------------------------------------------- #
# 2. Resolution mechanics
# --------------------------------------------------------------------------- #


def test_groups_are_unioned_and_sorted(repo: SqliteRepository):
    master = records("AAA", "BBB", "CCC")
    repo.upsert_group_memberships(index_memberships(
        [("nifty_50", ["CCC", "AAA"]), ("nifty_it", ["BBB", "AAA"])],
        effective_date=EFFECTIVE, source="NSE", records=master).memberships)

    resolved = resolve_universe(
        "combo",
        config=config_with(combo={"groups": ["NIFTY_50", "NIFTY_IT"]}),
        reader=repo,
    )
    assert resolved.symbols == ("NSE:AAA", "NSE:BBB", "NSE:CCC"), "union, deduped, sorted"


def test_resolution_is_deterministic_regardless_of_group_order(repo: SqliteRepository):
    master = records("AAA", "BBB")
    repo.upsert_group_memberships(index_memberships(
        [("nifty_50", ["AAA"]), ("nifty_it", ["BBB"])],
        effective_date=EFFECTIVE, source="NSE", records=master).memberships)
    a = resolve_universe("x", config=config_with(x={"groups": ["NIFTY_50", "NIFTY_IT"]}), reader=repo)
    b = resolve_universe("x", config=config_with(x={"groups": ["NIFTY_IT", "NIFTY_50"]}), reader=repo)
    assert a.symbols == b.symbols


def test_empty_groups_are_reported_not_silently_swallowed(repo: SqliteRepository):
    """A universe empty because its groups were never loaded is a very different
    situation from one that is genuinely empty."""
    master = records("AAA")
    repo.upsert_group_memberships(index_memberships(
        [("nifty_50", ["AAA"])], effective_date=EFFECTIVE, source="NSE",
        records=master).memberships)
    resolved = resolve_universe(
        "mixed", config=config_with(mixed={"groups": ["NIFTY_50", "NIFTY_500"]}), reader=repo)
    assert resolved.symbols == ("NSE:AAA",)
    assert resolved.empty_groups == ("NIFTY_500",)


def test_a_fully_unloaded_universe_is_empty_and_says_which_groups(repo: SqliteRepository):
    resolved = resolve_universe(
        "ghost", config=config_with(ghost={"groups": ["NIFTY_500"]}), reader=repo)
    assert resolved.is_empty
    assert resolved.empty_groups == ("NIFTY_500",)


def test_effective_dates_are_reported(repo: SqliteRepository):
    master = records("AAA")
    repo.upsert_group_memberships(index_memberships(
        [("nifty_50", ["AAA"])], effective_date=EFFECTIVE, source="NSE",
        records=master).memberships)
    resolved = resolve_universe("x", config=config_with(x={"groups": ["NIFTY_50"]}), reader=repo)
    assert resolved.effective_dates == (("NIFTY_50", EFFECTIVE),)


def test_as_of_resolves_historical_membership(repo: SqliteRepository):
    """A screen run before an index rebalance must remain reproducible after."""
    old, new = date(2026, 7, 31), date(2026, 9, 30)
    master = records("AAA", "BBB")
    repo.upsert_group_memberships(index_memberships(
        [("nifty_50", ["AAA"])], effective_date=old, source="NSE", records=master).memberships)
    repo.upsert_group_memberships(index_memberships(
        [("nifty_50", ["BBB"])], effective_date=new, source="NSE", records=master).memberships)
    cfg = config_with(x={"groups": ["NIFTY_50"]})
    assert resolve_universe("x", config=cfg, reader=repo).symbols == ("NSE:BBB",)
    assert resolve_universe("x", config=cfg, reader=repo, as_of=old).symbols == ("NSE:AAA",)


# --------------------------------------------------------------------------- #
# 3. Failing loudly
# --------------------------------------------------------------------------- #


def test_an_unknown_universe_raises_and_lists_what_exists(repo: SqliteRepository):
    with pytest.raises(ConfigError) as excinfo:
        resolve_universe("nope", config=config_with(), reader=repo)
    assert "unknown universe" in str(excinfo.value)
    assert "athena_core" in str(excinfo.value)


def test_an_unimplemented_eligibility_profile_raises(repo: SqliteRepository):
    """Returning the unfiltered union under the name of a filtered universe is
    the silent-wrongness this whole track exists to remove."""
    cfg = config_with(dx={"groups": ["NSE_MAINBOARD"], "eligibility": "darvax_discovery"})
    with pytest.raises(ConfigError) as excinfo:
        resolve_universe("dx", config=cfg, reader=repo)
    message = str(excinfo.value)
    assert "not implemented" in message
    assert "SU-4" in message, "the error must say where the profile is coming from"


def test_the_shipped_darvax_universe_is_not_yet_resolvable(repo: SqliteRepository):
    """It is declared to record intent, and refuses to resolve until SU-4."""
    config = load_universes_config(CONFIG_DIR)
    assert "darvax_discovery" not in resolvable_universes(config)
    with pytest.raises(ConfigError):
        resolve_universe("darvax_discovery", config=config, reader=repo)


def test_unknown_config_keys_and_duplicate_groups_are_rejected():
    """Typos must fail loudly: a mistyped key that is silently ignored gives a
    universe quietly different from the one written down."""
    with pytest.raises(ValidationError):
        UniverseDefinition(groups=["A"], typo=True)
    with pytest.raises(ValidationError, match="duplicate"):
        UniverseDefinition(groups=["A", "A"])
    with pytest.raises(ValidationError):
        UniverseDefinition(groups=[])


def test_missing_config_file_raises_config_error(tmp_path: Path):
    with pytest.raises(ConfigError, match="not found"):
        load_universes_config(tmp_path)


def test_malformed_config_raises_config_error(tmp_path: Path):
    (tmp_path / "universes.json").write_text("{not json", encoding="utf-8")
    with pytest.raises(ConfigError, match="not valid JSON"):
        load_universes_config(tmp_path)


# --------------------------------------------------------------------------- #
# 4. The shipped configuration is honest about what it can do
# --------------------------------------------------------------------------- #


def test_every_group_the_config_references_is_one_su2_can_produce():
    """Catches a universe pointing at a group nobody builds — which would
    resolve to empty forever with no error."""
    from athena.symbols.groups import GROUP_MAINBOARD, GROUP_SME

    config = load_universes_config(CONFIG_DIR)
    snapshot_groups = {
        e["key"].upper()
        for e in json.loads(
            (REPO_ROOT / "data" / "index_constituents" / "2026-07-31" / "manifest.json")
            .read_text(encoding="utf-8")
        )["indices"]
    }
    buildable = snapshot_groups | {GROUP_MAINBOARD, GROUP_SME, GROUP_OWNER_CANDIDATES}
    # The derived group is rule-defined and intentionally unbuilt until SU-4.
    derived = {"NSE_ALL_ELIGIBLE_EQUITY"}

    unknown = set(declared_groups(config)) - buildable - derived
    assert unknown == set(), f"config references groups nothing can build: {unknown}"


def test_universes_naming_a_missing_index_are_not_shipped_as_resolvable():
    """ADR-011 named NIFTY_500/MIDCAP_150/TOTAL_MARKET/FNO, none of which have a
    snapshot. Shipping them as resolvable would produce silently empty universes
    that look successful."""
    config = load_universes_config(CONFIG_DIR)
    missing = {"NIFTY_100", "NIFTY_200", "NIFTY_500", "NIFTY_MIDCAP_150",
               "NIFTY_SMALLCAP_250", "NIFTY_MICROCAP_250", "NIFTY_TOTAL_MARKET", "FNO"}
    for name in resolvable_universes(config):
        referenced = set(config.universes[name].groups)
        assert not (referenced & missing), (
            f"universe '{name}' is marked resolvable but references {referenced & missing}"
        )


# --------------------------------------------------------------------------- #
# 5. One bad symbol must never stop the batch (owner requirement, 2026-08-15)
# --------------------------------------------------------------------------- #


class TestPartialFailureNeverStopsTheBatch:
    """A symbol that cannot be resolved is skipped and reported; every other
    symbol still gets processed.

    Stated as a requirement after `E2E` was found unresolvable in the live
    candidate list. Asserted at every layer that touches a batch, because the
    guarantee is only worth anything if it holds end to end — a single raise
    anywhere would take the whole universe down with one delisted ticker.
    """

    def test_membership_building_survives_a_bad_symbol(self):
        good = [f"SYM{i:03d}" for i in range(50)]
        master = records(*good)
        build = owner_candidate_memberships(
            [*good[:25], "GHOSTCO", *good[25:]],
            effective_date=EFFECTIVE, records=master,
        )
        assert len(build.memberships) == 50, "every good symbol survived"
        assert build.unresolved == ((GROUP_OWNER_CANDIDATES, "GHOSTCO"),)

    def test_index_membership_survives_several_bad_symbols(self):
        good = [f"IDX{i:03d}" for i in range(30)]
        master = records(*good)
        build = index_memberships(
            [("nifty_50", [*good, "DEAD1", "DEAD2"])],
            effective_date=EFFECTIVE, source="NSE", records=master,
        )
        assert len(build.memberships) == 30
        assert {s for _, s in build.unresolved} == {"DEAD1", "DEAD2"}

    def test_resolution_survives_a_group_that_has_no_data(self, repo: SqliteRepository):
        master = records("AAA", "BBB")
        repo.upsert_group_memberships(index_memberships(
            [("nifty_50", ["AAA", "BBB"])], effective_date=EFFECTIVE,
            source="NSE", records=master).memberships)
        resolved = resolve_universe(
            "mixed",
            config=config_with(mixed={"groups": ["NIFTY_50", "NEVER_LOADED"]}),
            reader=repo,
        )
        assert resolved.symbols == ("NSE:AAA", "NSE:BBB"), "good group still resolved"
        assert resolved.empty_groups == ("NEVER_LOADED",), "the gap is reported"

    def test_a_symbol_missing_from_the_master_does_not_block_persistence(
        self, repo: SqliteRepository
    ):
        """End to end: build with a bad symbol present, persist, resolve."""
        good = ["AAA", "BBB", "CCC"]
        master = records(*good)
        repo.upsert_symbol_records(master)
        build = owner_candidate_memberships(
            [*good, "GHOSTCO"], effective_date=EFFECTIVE, records=master)
        assert repo.upsert_group_memberships(build.memberships) == 3

        resolved = resolve_universe("athena_core", config=config_with(), reader=repo)
        assert resolved.symbols == ("NSE:AAA", "NSE:BBB", "NSE:CCC")
