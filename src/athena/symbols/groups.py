"""Symbol group membership (SU-2, ADR-011).

A symbol belongs to many groups — an index, a board, the owner's curated list —
and **membership is metadata on the canonical symbol, never a duplicated symbol
record** (ADR-011 §2). This module builds those memberships; persisting and
querying them is the repository's job, and resolving a *universe* from them is
SU-3's.

Membership is **dated**. Index constituents change, so a membership is only ever
true as of some effective date, and the existing immutable snapshot convention
(`data/index_constituents/<effective-date>/`) is reused rather than replaced.
Recording membership undated would make a past screen unreproducible the moment
an index was rebalanced.

## What this module deliberately does not do

`NSE_ALL_ELIGIBLE_EQUITY` is **not** built here. ADR-011 §2.3 defines it as
whatever its eligibility rules resolve to, and those rules are SU-4's. Baking a
materialised list of it now would turn a rule-defined group into a frozen one —
the exact thing §2.3 forbids.
"""

from __future__ import annotations

from collections.abc import Iterable, Sequence
from dataclasses import dataclass
from datetime import date
from enum import Enum

from athena.symbols.models import Board, SymbolRecord


class GroupKind(str, Enum):
    """Where a group's membership comes from. Kept distinct because the kinds
    have genuinely different provenance and update cadence."""

    INDEX = "INDEX"
    """From a dated NSE constituent snapshot."""
    SEGMENT = "SEGMENT"
    """Exchange segment eligibility, e.g. F&O. No source available yet."""
    BOARD = "BOARD"
    """Listing board, derived from the symbol master's classification."""
    CURATED = "CURATED"
    """A human-maintained list — today, the owner's candidates."""
    DERIVED = "DERIVED"
    """Rule-defined and resolved on demand, never materialised here (§2.3)."""


#: Canonical group names for the two boards. Named constants so a typo is an
#: import error rather than a silently empty group.
GROUP_MAINBOARD = "NSE_MAINBOARD"
GROUP_SME = "NSE_SME"
GROUP_OWNER_CANDIDATES = "OWNER_CANDIDATES"


def index_group_name(snapshot_key: str) -> str:
    """``nifty_midcap_100`` → ``NIFTY_MIDCAP_100``.

    A pure, reversible renaming of the snapshot key. Deliberately not a lookup
    table mapping to prettier names: an invented mapping is a place for a group
    to be silently misattributed to the wrong index.
    """
    key = snapshot_key.strip()
    if not key:
        raise ValueError("index snapshot key must not be empty")
    return key.upper()


@dataclass(frozen=True, slots=True)
class GroupMembership:
    """One symbol's membership of one group, as of one date."""

    instrument_id: str
    group_name: str
    kind: GroupKind
    effective_date: date
    source: str
    """Where the membership came from, e.g. ``NSE Indices Limited`` or
    ``owner_candidates``."""


@dataclass(frozen=True, slots=True)
class MembershipBuild:
    """Memberships built, plus what could not be resolved.

    Unresolved symbols are **returned, not dropped**. An index constituent that
    is absent from the symbol master is a real signal — a stale snapshot, a
    renamed ticker, or a catalogue gap — and silently discarding it would hide
    exactly the kind of coverage hole ADR-011 exists to expose.
    """

    memberships: tuple[GroupMembership, ...]
    unresolved: tuple[tuple[str, str], ...] = ()
    """``(group_name, symbol)`` pairs with no matching canonical symbol."""


def _resolver(records: Sequence[SymbolRecord]) -> dict[str, str]:
    """Bare trading symbol → canonical ``instrument_id``."""
    return {r.symbol.upper(): r.instrument_id for r in records}


def index_memberships(
    snapshot_indices: Iterable[tuple[str, Sequence[str]]],
    *,
    effective_date: date,
    source: str,
    records: Sequence[SymbolRecord],
) -> MembershipBuild:
    """Build index memberships from a loaded constituent snapshot.

    Args:
        snapshot_indices: ``(snapshot_key, symbols)`` pairs, as produced by
            ``load_index_constituent_snapshot`` — which already verifies the
            checksum and member count, so this function trusts its input's
            integrity and concerns itself only with resolution.
    """
    lookup = _resolver(records)
    built: list[GroupMembership] = []
    unresolved: list[tuple[str, str]] = []
    for snapshot_key, symbols in snapshot_indices:
        group = index_group_name(snapshot_key)
        for symbol in symbols:
            instrument_id = lookup.get(symbol.strip().upper())
            if instrument_id is None:
                unresolved.append((group, symbol))
                continue
            built.append(
                GroupMembership(
                    instrument_id=instrument_id,
                    group_name=group,
                    kind=GroupKind.INDEX,
                    effective_date=effective_date,
                    source=source,
                )
            )
    return MembershipBuild(tuple(built), tuple(unresolved))


def board_memberships(
    records: Sequence[SymbolRecord], *, effective_date: date
) -> MembershipBuild:
    """Derive `NSE_MAINBOARD` / `NSE_SME` membership from the symbol master.

    Symbols whose board is ``UNKNOWN`` join **neither** group. That is the point
    of SU-1's honest classification: an instrument nobody has established the
    board for must not be swept into the main board, where a scanner would treat
    it as ordinary equity.
    """
    built = [
        GroupMembership(
            instrument_id=r.instrument_id,
            group_name=GROUP_MAINBOARD if r.board is Board.MAINBOARD else GROUP_SME,
            kind=GroupKind.BOARD,
            effective_date=effective_date,
            source=f"symbol_master:{r.series_source.value}",
        )
        for r in records
        if r.board in (Board.MAINBOARD, Board.SME)
    ]
    return MembershipBuild(tuple(built))


def owner_candidate_memberships(
    symbols: Iterable[str],
    *,
    effective_date: date,
    records: Sequence[SymbolRecord],
) -> MembershipBuild:
    """Build `OWNER_CANDIDATES` membership from the owner's curated list.

    ADR-011 §2.1: this is a first-class group, not a legacy artefact. It is the
    universe ATHENA actually runs on today, and it contains names no index does.
    """
    lookup = _resolver(records)
    built: list[GroupMembership] = []
    unresolved: list[tuple[str, str]] = []
    for symbol in symbols:
        bare = symbol.strip().upper().split(":")[-1]
        instrument_id = lookup.get(bare)
        if instrument_id is None:
            unresolved.append((GROUP_OWNER_CANDIDATES, symbol))
            continue
        built.append(
            GroupMembership(
                instrument_id=instrument_id,
                group_name=GROUP_OWNER_CANDIDATES,
                kind=GroupKind.CURATED,
                effective_date=effective_date,
                source="owner_candidates",
            )
        )
    return MembershipBuild(tuple(built), tuple(unresolved))
