"""Universe resolution (SU-3, ADR-011).

Turns a **universe name** into a set of symbols by unioning the groups SU-2
recorded. Scanners reference a name; no scanner hardcodes a group or a filter,
so adding one is a configuration change.

## Naming, deliberately

This module is ``symbols.universes``, not ``universe``. ATHENA already has an
``athena.universe`` package — the `UniverseEngine` that applies eligibility
(series, liquidity, history, size) to instruments. That engine is **unchanged
and still runs**. What is added here is the step *before* it: deciding which
symbols are even candidates. Conflating the two names would invite exactly the
confusion this ADR exists to remove.

## Why an unimplemented eligibility profile raises

`resolve_universe` refuses to resolve a universe whose eligibility profile does
not exist yet, rather than returning the unfiltered group union. Returning
unfiltered symbols under the name of a filtered universe is the silent-wrongness
pattern this whole track exists to eliminate — a caller would believe filtering
had happened. Profiles arrive in SU-4; until then only ``none`` resolves.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from pathlib import Path
from typing import Protocol

from pydantic import BaseModel, ConfigDict, Field, ValidationError, model_validator

from athena.errors import ConfigError
from athena.symbols.eligibility import PROFILES, Exclusion, apply_profile

#: The only eligibility profile SU-3 can honour: apply nothing. `athena_core`
#: uses it because ATHENA applies no group-level filter today — its own
#: `UniverseEngine` still runs downstream, unchanged.
ELIGIBILITY_NONE = "none"

#: Implemented profiles, taken from the eligibility module itself so the two
#: can never disagree — a profile that exists there is resolvable here.
IMPLEMENTED_ELIGIBILITY: frozenset[str] = frozenset(PROFILES)


class _Strict(BaseModel):
    """Unknown keys are errors — a mistyped universe must fail loudly."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    @model_validator(mode="before")
    @classmethod
    def _drop_meta(cls, values: object) -> object:
        if isinstance(values, dict):
            return {
                k: v
                for k, v in values.items()
                if not (isinstance(k, str) and k.startswith("_"))
            }
        return values


class UniverseDefinition(_Strict):
    """One named universe: which groups, and which eligibility profile."""

    groups: list[str] = Field(min_length=1)
    eligibility: str = ELIGIBILITY_NONE
    description: str = ""

    @model_validator(mode="after")
    def _groups_are_unique(self) -> UniverseDefinition:
        if len(self.groups) != len(set(self.groups)):
            raise ValueError(f"duplicate groups in universe: {self.groups}")
        return self


class UniversesConfig(_Strict):
    """The full `config/universes.json` contract."""

    universes: dict[str, UniverseDefinition]

    @model_validator(mode="after")
    def _core_universe_is_declared(self) -> UniversesConfig:
        # `athena_core` is what every existing ATHENA engine will resolve once
        # SU-6 wires consumers up. Losing it silently would leave them with no
        # universe at all, so its absence is a configuration error.
        if "athena_core" not in self.universes:
            raise ValueError("config/universes.json must declare 'athena_core'")
        return self


class GroupReader(Protocol):
    """The only thing resolution needs from storage."""

    def list_group_members(
        self, group_name: str, *, as_of: date | None = None
    ) -> list[str]: ...

    def latest_group_effective_date(self, group_name: str) -> date | None: ...

    def get_symbol_record(self, instrument_id: str): ...


@dataclass(frozen=True, slots=True)
class UniverseResolution:
    """A resolved universe, with enough detail to explain what it contains.

    ``empty_groups`` matters: a universe that resolves to nothing because its
    groups were never loaded is a very different situation from one that is
    genuinely empty, and a caller that cannot tell them apart will misread a
    missing data load as "no symbols qualify".
    """

    name: str
    symbols: tuple[str, ...]
    groups: tuple[str, ...]
    eligibility: str
    empty_groups: tuple[str, ...] = ()
    effective_dates: tuple[tuple[str, date], ...] = ()
    excluded: tuple[Exclusion, ...] = ()
    """Symbols removed by the eligibility profile, each with its rule and
    reason — so "why isn't X in my scan?" always has an answer."""

    def exclusion_counts(self) -> dict[str, int]:
        counts: dict[str, int] = {}
        for item in self.excluded:
            counts[item.rule] = counts.get(item.rule, 0) + 1
        return counts

    @property
    def is_empty(self) -> bool:
        return not self.symbols


def load_universes_config(config_dir: Path | str) -> UniversesConfig:
    """Load + validate `config/universes.json`."""
    import json

    path = Path(config_dir) / "universes.json"
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise ConfigError(f"universes config not found: {path}") from exc
    except json.JSONDecodeError as exc:
        raise ConfigError(f"universes config is not valid JSON ({path}): {exc}") from exc
    try:
        return UniversesConfig.model_validate(raw)
    except ValidationError as exc:
        raise ConfigError(f"invalid universes config ({path}): {exc}") from exc


def resolve_universe(
    name: str,
    *,
    config: UniversesConfig,
    reader: GroupReader,
    as_of: date | None = None,
) -> UniverseResolution:
    """Resolve a named universe to its symbols.

    Groups are **unioned**, then sorted, so the result is deterministic
    regardless of group order or storage iteration order.

    Raises:
        ConfigError: if the universe is not declared, or declares an eligibility
            profile that is not implemented yet — see the module docstring for
            why that is a failure rather than an unfiltered result.
    """
    definition = config.universes.get(name)
    if definition is None:
        raise ConfigError(
            f"unknown universe '{name}'; declared: {sorted(config.universes)}"
        )
    if definition.eligibility not in IMPLEMENTED_ELIGIBILITY:
        raise ConfigError(
            f"universe '{name}' requires eligibility profile "
            f"'{definition.eligibility}', which is not implemented "
            f"(implemented: {sorted(IMPLEMENTED_ELIGIBILITY)}). Resolving it "
            f"would return unfiltered symbols under the name of a filtered "
            f"universe."
        )

    collected: set[str] = set()
    empty: list[str] = []
    dates: list[tuple[str, date]] = []
    for group in definition.groups:
        members = reader.list_group_members(group, as_of=as_of)
        if not members:
            empty.append(group)
            continue
        collected.update(members)
        effective = reader.latest_group_effective_date(group)
        if effective is not None:
            dates.append((group, effective))

    excluded: tuple[Exclusion, ...] = ()
    if definition.eligibility != ELIGIBILITY_NONE and collected:
        # Eligibility needs the canonical record, not just the id — the board,
        # series and classification reason all live on the symbol master.
        records = [
            record
            for record in (reader.get_symbol_record(i) for i in sorted(collected))
            if record is not None
        ]
        outcome = apply_profile(definition.eligibility, records)
        collected = set(outcome.eligible)
        excluded = outcome.excluded

    return UniverseResolution(
        name=name,
        symbols=tuple(sorted(collected)),
        groups=tuple(definition.groups),
        eligibility=definition.eligibility,
        empty_groups=tuple(empty),
        effective_dates=tuple(dates),
        excluded=excluded,
    )


def resolvable_universes(config: UniversesConfig) -> tuple[str, ...]:
    """Universes whose eligibility profile is implemented today.

    Exposed so a caller can list what actually works rather than discovering it
    by catching exceptions one name at a time.
    """
    return tuple(
        sorted(
            name
            for name, definition in config.universes.items()
            if definition.eligibility in IMPLEMENTED_ELIGIBILITY
        )
    )


def declared_groups(config: UniversesConfig) -> tuple[str, ...]:
    """Every group any universe references — the set SU-2 must be able to load."""
    return tuple(sorted({g for d in config.universes.values() for g in d.groups}))
