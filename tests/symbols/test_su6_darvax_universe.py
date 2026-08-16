"""SU-6: DarvaX consumes a resolved universe (ADR-011).

The architectural property under test: **a universe reaches DarvaX as data, not
as a service call.** DarvaX imports no ATHENA resolver, the mount seam stays
methodology-blind, and ADR-010's pinned import surface is unchanged — the wider
universe arrives through the same read-only port that already carries candles.
"""

from __future__ import annotations

import ast
from datetime import datetime, timezone
from decimal import Decimal
from pathlib import Path

import pytest

from athena.darvax.adapters import SqliteMarketDataAdapter
from athena.darvax.config import DarvaxConfig
from athena.data.store.repository import SqliteRepository
from athena.domain.market import Instrument

REPO_ROOT = Path(__file__).resolve().parents[2]
RESOLVED_AT = datetime(2026, 8, 15, 12, 0, tzinfo=timezone.utc)


def instrument(symbol: str) -> Instrument:
    return Instrument(
        instrument_id=f"NSE:{symbol}", symbol=symbol, exchange="NSE", series="EQ",
        name=symbol, lot_size=1, tick_size=Decimal("0.05"), status="ACTIVE",
    )


@pytest.fixture()
def repo(tmp_path: Path) -> SqliteRepository:
    r = SqliteRepository(tmp_path / "athena.db")
    r.initialize()
    for symbol in ("AAA", "BBB", "CCC"):
        r.upsert_instrument(instrument(symbol))
    yield r
    r.close()


# --------------------------------------------------------------------------- #
# 1. Opt-in, defaulting to today's behaviour
# --------------------------------------------------------------------------- #


def test_no_universe_configured_keeps_every_ingested_instrument(repo):
    """SU-6 must change nothing until someone asks for it."""
    assert DarvaxConfig().universe is None
    adapter = SqliteMarketDataAdapter(repo)
    assert {i.symbol for i in adapter.list_instruments()} == {"AAA", "BBB", "CCC"}


def test_a_configured_universe_scopes_discovery(repo):
    repo.save_resolved_universe(
        "darvax_discovery", ["NSE:AAA", "NSE:CCC"], resolved_at=RESOLVED_AT
    )
    adapter = SqliteMarketDataAdapter(repo).with_universe("darvax_discovery")
    assert {i.symbol for i in adapter.list_instruments()} == {"AAA", "CCC"}


def test_the_universe_is_intersected_with_ingested_instruments(repo):
    """A symbol in the universe but with no candles cannot be screened. It is a
    coverage gap for SU-5's planner to report, not something to hand the engine
    and let it fail per symbol."""
    repo.save_resolved_universe(
        "darvax_discovery",
        ["NSE:AAA", "NSE:NOTINGESTED"],
        resolved_at=RESOLVED_AT,
    )
    adapter = SqliteMarketDataAdapter(repo).with_universe("darvax_discovery")
    assert {i.symbol for i in adapter.list_instruments()} == {"AAA"}


def test_an_unresolved_universe_yields_nothing_rather_than_everything(repo):
    """'Nobody has resolved this yet' must not silently become 'no scope'.
    Returning every instrument would ignore the configured universe entirely."""
    adapter = SqliteMarketDataAdapter(repo).with_universe("never_resolved")
    assert list(adapter.list_instruments()) == []


def test_with_universe_does_not_mutate_the_original(repo):
    repo.save_resolved_universe("u", ["NSE:AAA"], resolved_at=RESOLVED_AT)
    base = SqliteMarketDataAdapter(repo)
    scoped = base.with_universe("u")
    assert len(base.list_instruments()) == 3
    assert len(scoped.list_instruments()) == 1


# --------------------------------------------------------------------------- #
# 2. Persistence semantics
# --------------------------------------------------------------------------- #


def test_resolving_again_replaces_rather_than_accumulates(repo):
    """A resolution is a complete statement of what the universe *is*; leaving
    stale rows would let a scanner see symbols the current rules exclude."""
    repo.save_resolved_universe("u", ["NSE:AAA", "NSE:BBB"], resolved_at=RESOLVED_AT)
    repo.save_resolved_universe("u", ["NSE:CCC"], resolved_at=RESOLVED_AT)
    assert repo.list_resolved_universe("u") == ["NSE:CCC"]


def test_universes_do_not_bleed_into_each_other(repo):
    repo.save_resolved_universe("a", ["NSE:AAA"], resolved_at=RESOLVED_AT)
    repo.save_resolved_universe("b", ["NSE:BBB"], resolved_at=RESOLVED_AT)
    assert repo.list_resolved_universe("a") == ["NSE:AAA"]
    assert repo.list_resolved_universe("b") == ["NSE:BBB"]


def test_an_empty_resolution_is_recorded_as_empty(repo):
    repo.save_resolved_universe("u", ["NSE:AAA"], resolved_at=RESOLVED_AT)
    assert repo.save_resolved_universe("u", [], resolved_at=RESOLVED_AT) == 0
    assert repo.list_resolved_universe("u") == []


# --------------------------------------------------------------------------- #
# 3. ADR-010's boundary is unchanged — the point of the whole design
# --------------------------------------------------------------------------- #


def test_darvax_imports_no_athena_universe_machinery():
    """ADR-011 chose 'a universe is data, not a service DarvaX calls' precisely
    so this stays true. A resolver import here would widen the pinned surface."""
    forbidden = {
        "athena.symbols.universes",
        "athena.symbols.eligibility",
        "athena.symbols.groups",
        "athena.symbols.coverage",
        "athena.universe",
    }
    offenders: list[str] = []
    for py in (REPO_ROOT / "src" / "athena" / "darvax").rglob("*.py"):
        tree = ast.parse(py.read_text(encoding="utf-8"), filename=str(py))
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                names = [a.name for a in node.names]
            elif isinstance(node, ast.ImportFrom):
                names = [node.module or ""]
            else:
                continue
            for name in names:
                if any(name == f or name.startswith(f + ".") for f in forbidden):
                    offenders.append(f"{py.name}:{node.lineno} imports {name}")
    assert offenders == [], f"DarvaX imported ATHENA universe machinery: {offenders}"


def test_the_mount_seam_still_reads_only_the_enabled_flag():
    """ATHENA must not learn what a DarvaX universe is. DarvaX applies its own
    universe from its own config, inside its own app."""
    seam = (REPO_ROOT / "src" / "athena" / "api" / "darvax_mount.py").read_text(
        encoding="utf-8"
    )
    assert "universe" not in seam.lower(), (
        "the seam must stay methodology-blind; DarvaX scopes its own adapter"
    )


def test_darvax_scopes_its_adapter_from_its_own_config():
    app_source = (
        REPO_ROOT / "src" / "athena" / "darvax" / "api" / "app.py"
    ).read_text(encoding="utf-8")
    assert "config.universe" in app_source
    assert "with_universe" in app_source


def test_the_shipped_darvax_config_does_not_opt_in_yet():
    """SU-6 is plumbing. Enabling it is the owner's decision, and today the
    wider universe has almost no candles to screen."""
    import json

    raw = json.loads((REPO_ROOT / "config" / "darvax.json").read_text(encoding="utf-8"))
    assert raw.get("universe") in (None, ""), (
        "shipping an opted-in universe would silently change what DarvaX scans"
    )
