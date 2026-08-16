"""Scanner eligibility profiles (SU-4, ADR-011).

A profile is a **named, ordered set of rules** applied to the symbols a universe
resolved. Every exclusion is attributable to one named rule with a reason in
words, so "why isn't X in my scan?" always has an answer.

## What is deliberately not here: thresholds

ADR-011 §4 fixes that eligibility is explicit, named and explainable — it fixes
no numbers, and neither does this module. Liquidity and minimum-history rules
are **not implemented**, for a reason that is structural rather than a matter of
taste:

* the broker instrument dump reports ``last_price`` as ``0`` for **every** row,
  so liquidity cannot be measured from the catalogue at all;
* it can only be measured from candles, which exist only for symbols already
  ingested — and the point of a discovery universe is to decide what to ingest.

That circularity is real and may force a staged approach for **correctness**
rather than performance. Inventing a volume floor here would produce a filter
that silently excludes on data it does not have.

## Why SME is not a rule

SME is a **listing board**, modelled as a group in SU-2. Including or excluding
it is therefore a universe composition choice — visible in
`config/universes.json` and reviewable in a diff — rather than a threshold
buried in a filter. ADR-011 §2.2 asked for SME to be an explicit decision; group
membership is the mechanism that makes it one.
"""

from __future__ import annotations

from collections.abc import Callable, Sequence
from dataclasses import dataclass

from athena.errors import ConfigError
from athena.symbols.models import Board, SymbolRecord

#: Series that are ordinary, unrestricted equity. Everything else on the main
#: board is restricted in some way: ``BE``/``BZ`` are trade-for-trade (often a
#: surveillance measure) and ``IV`` carries an unpaid-call variant. A discovery
#: scanner looking for clean breakouts should not be handed instruments the
#: exchange has already flagged.
UNRESTRICTED_EQUITY_SERIES = frozenset({"EQ"})

#: Substrings that identify a fund rather than a company. Heuristic, and
#: labelled as such: the broker dump has no instrument-kind column, so an ETF is
#: only identifiable by how it is named.
_FUND_MARKERS = ("ETF", "BEES", " FUND", "GOLDBEES", "LIQUIDBEES")


@dataclass(frozen=True, slots=True)
class Exclusion:
    """One symbol removed by one rule, with the reason recorded."""

    instrument_id: str
    rule: str
    reason: str


@dataclass(frozen=True, slots=True)
class EligibilityResult:
    """What survived, what did not, and why.

    ``excluded`` is returned in full rather than counted: a scanner that cannot
    say why a symbol is missing is exactly the opaque behaviour ADR-011 set out
    to remove.
    """

    profile: str
    eligible: tuple[str, ...]
    excluded: tuple[Exclusion, ...]

    def counts_by_rule(self) -> dict[str, int]:
        counts: dict[str, int] = {}
        for item in self.excluded:
            counts[item.rule] = counts.get(item.rule, 0) + 1
        return counts


@dataclass(frozen=True, slots=True)
class EligibilityRule:
    """A named predicate. ``keep`` returns True when the symbol survives."""

    name: str
    describe: str
    keep: Callable[[SymbolRecord], bool]
    reason_when_excluded: Callable[[SymbolRecord], str]


def _is_fund(record: SymbolRecord) -> bool:
    haystack = f"{record.symbol} {record.name or ''}".upper()
    return any(marker in haystack for marker in _FUND_MARKERS)


RULE_KNOWN_BOARD = EligibilityRule(
    name="known_board",
    describe="the listing board must have been established, not guessed",
    keep=lambda r: r.board in (Board.MAINBOARD, Board.SME),
    reason_when_excluded=lambda r: (
        f"board is {r.board.value}: {r.classification_reason}"
    ),
)

RULE_UNRESTRICTED_SERIES = EligibilityRule(
    name="unrestricted_equity_series",
    describe="only ordinary equity series, excluding trade-for-trade and surveillance",
    keep=lambda r: r.series in UNRESTRICTED_EQUITY_SERIES,
    reason_when_excluded=lambda r: (
        f"series {r.series} is not ordinary equity "
        f"(allowed: {sorted(UNRESTRICTED_EQUITY_SERIES)})"
    ),
)

RULE_NOT_A_FUND = EligibilityRule(
    name="not_a_fund",
    describe="exclude ETFs and funds, which are not companies with a chart to break out of",
    keep=lambda r: not _is_fund(r),
    reason_when_excluded=lambda r: f"name or symbol identifies a fund: {r.name or r.symbol}",
)


#: Profiles by name. Rules are code rather than configuration because they are
#: *logic* with no numbers to tune; when threshold rules arrive they belong in
#: config, per ATHENA's configuration-over-hardcoding rule.
PROFILES: dict[str, tuple[EligibilityRule, ...]] = {
    "none": (),
    "darvax_discovery": (
        RULE_KNOWN_BOARD,
        RULE_UNRESTRICTED_SERIES,
        RULE_NOT_A_FUND,
    ),
}


def apply_profile(
    profile: str, records: Sequence[SymbolRecord]
) -> EligibilityResult:
    """Apply a named profile, recording every exclusion and its reason.

    Rules are applied in order and a symbol stops at the **first** rule that
    excludes it, so each exclusion has exactly one attributable cause rather
    than a list a reader has to weigh.
    """
    rules = PROFILES.get(profile)
    if rules is None:
        raise ConfigError(
            f"unknown eligibility profile '{profile}'; "
            f"implemented: {sorted(PROFILES)}"
        )

    eligible: list[str] = []
    excluded: list[Exclusion] = []
    for record in records:
        for rule in rules:
            if not rule.keep(record):
                excluded.append(
                    Exclusion(
                        instrument_id=record.instrument_id,
                        rule=rule.name,
                        reason=rule.reason_when_excluded(record),
                    )
                )
                break
        else:
            eligible.append(record.instrument_id)

    return EligibilityResult(
        profile=profile,
        eligible=tuple(sorted(eligible)),
        excluded=tuple(excluded),
    )


def describe_profile(profile: str) -> tuple[tuple[str, str], ...]:
    """``(rule name, description)`` pairs, for showing what a profile does."""
    rules = PROFILES.get(profile)
    if rules is None:
        raise ConfigError(f"unknown eligibility profile '{profile}'")
    return tuple((rule.name, rule.describe) for rule in rules)
