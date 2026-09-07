"""ID-9 V0 Capital Policy Activation: the canonical production
configuration seam for `CapitalPolicy` (2026-09-07).

ID-9's core methodology/implementation is Owner-frozen
(`ID9_V0_CORE_IMPLEMENTATION_METHODOLOGY_CORRECT_NO_PRODUCTION_ACTIVATION`).
The one remaining gap is operational, not methodological: production
constructs `OwnerValidationPipeline` with `capital_policy=None`
(`cli.py`'s `_owner_validation_pipeline`, the single canonical
construction helper both `_cmd_cycle` and `_cmd_serve` share), so every
otherwise-valid current LONG opportunity honestly ends at
`CAPITAL_POLICY_UNAVAILABLE`.

Mirrors `athena.explosive_move.live.operational_config`'s own
established PATTERN only (own `_Strict` base, a `<config_dir>/<file>`
path helper, a `load_*_config` function whose missing-file behavior is
safe-by-construction, unknown keys rejected, a `_meta`/`_note`
documentation key dropped before validation) -- this module does not
import that one, and it does not import it back. The one deliberate
difference: EMR's safe-absence default is a real, always-constructible
`EmrOperationalConfig()` instance (every field has a safe default,
`enabled=False`). `CapitalPolicy` has no such safe default -- there is
no meaningful "off" capital amount -- so this loader's safe-absence
return value is `None`, preserving the exact same
`CAPITAL_POLICY_UNAVAILABLE` production behavior ID-9's own frozen
engine already reports for a `None` policy.

**Do NOT invent Owner values here or anywhere else** (Owner instruction,
§2 of the ID-9 V0 Capital Policy Activation authorization). This module
never chooses, defaults, clamps, or falls back to a numeric policy value
-- it only loads one the Owner has explicitly written to
`config/position_sizing_policy.json`. `config/capital.json`
(`CapitalConfig`) and `config/risk.json` (`RiskConfig`) are confirmed
dormant/consumed-by-zero-engines by the ID-9 discovery report and are
never read by this module, directly or indirectly -- their currently
configured values are not implicitly Owner-approved ID-9 policy.

**Policy-version operational invariant (§6):** `policy_version` is
Owner-controlled *policy* identity, independent of
`position_sizing_models.DEFAULT_METHODOLOGY_VERSION`
(`"position-sizing-v0"`, the sizing *methodology*). Changing a policy
value without also supplying a new `policy_version` is an operator
error this loader cannot detect from a single stateless file read (no
prior value is available to compare against, and building a policy
registry or persistence subsystem merely to enable that comparison is
explicitly out of scope for this milestone) -- so it is a documented
discipline, not an enforced one: **whenever any effective policy value
changes, the Owner/operator must also supply a new `policy_version`.**
"""

from __future__ import annotations

import json
from decimal import Decimal
from pathlib import Path
from typing import Any

from pydantic import BaseModel, ConfigDict, field_validator, model_validator

from athena.errors import ConfigError
from athena.intraday.position_sizing_models import CapitalPolicy

#: Filename the Owner/operator edits directly, resolved relative to the
#: caller's `config_dir` (i.e. `config/position_sizing_policy.json` in
#: production). Deliberately NOT named `sizing.json` or `capital.json`/
#: `risk.json` -- those already exist and are confirmed dormant
#: (`RETAIN_AS_LEGACY_COMPATIBILITY`, ID-9 discovery report); reusing or
#: aliasing one of those names would risk a future reader assuming this
#: is the same (or a replacement for the same) dormant configuration.
POSITION_SIZING_POLICY_CONFIG_FILENAME = "position_sizing_policy.json"


#: The ONLY documentation keys this config format recognizes and drops
#: before validation. ID-9 Capital Policy Config Final Hardening
#: (2026-09-07, Owner/Chief Architect source review): the prior
#: wildcard "drop every key starting with `_`" rule silently swallowed
#: any underscore-prefixed typo (`_metaa`, `_unexpected`,
#: `_risk_budget_per_trade_pct`) instead of rejecting it -- directly
#: contradicting this module's own "unknown keys are errors" contract.
#: Only these two exact keys are dropped; every other key (underscore-
#: prefixed or not) reaches `extra="forbid"` and fails loudly.
_DOCUMENTATION_KEYS = frozenset({"_meta", "_note"})


class _Strict(BaseModel):
    """Unknown keys are errors -- a typo in this policy file must fail
    loudly, never silently fall back to `None`/`CAPITAL_POLICY_UNAVAILABLE`
    and never silently ignore a field the Owner thought they set. Mirrors
    `athena.config.models._Strict`'s and
    `athena.explosive_move.live.operational_config._Strict`'s identical
    convention, independently -- this module owns its own tiny config
    stack rather than joining `athena.config.loader.load_config`'s
    all-files-mandatory aggregate tree (this file must be able to be
    ABSENT without breaking every other `athena` command). Drops only
    the exact, supported documentation keys in `_DOCUMENTATION_KEYS` --
    never a wildcard underscore-prefix rule (2026-09-07 hardening)."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    @model_validator(mode="before")
    @classmethod
    def _drop_documentation_keys(cls, values: object) -> object:
        if isinstance(values, dict):
            return {k: v for k, v in values.items() if k not in _DOCUMENTATION_KEYS}
        return values


def _require_decimal_string(v: Any, *, field_name: str) -> Any:
    """§7: 'no float conversion if Decimal parsing is available.' A JSON
    number (e.g. ``0.5``) is decoded by the `json` module as a Python
    `float` before pydantic ever sees it -- converting that float to
    `Decimal` afterwards can silently carry binary floating-point
    imprecision into a capital/risk figure. Requiring the JSON value to
    already be a string forces exact `Decimal(str)` parsing with no
    float intermediate at all, for every numeric field in this policy."""
    if isinstance(v, str):
        return v
    if isinstance(v, Decimal):
        return v
    raise ValueError(
        f"{field_name} must be a JSON string (e.g. \"0.50\"), not a bare JSON number -- "
        "this avoids float-imprecision when parsing a capital/risk percentage; got "
        f"{type(v).__name__}"
    )


class PositionSizingPolicyConfig(_Strict):
    """The smallest explicit configuration shape for `CapitalPolicy`'s
    four V0 fields (§5) -- nothing else. Do NOT add sector limits,
    liquidity limits, a daily loss limit, portfolio exposure limits,
    broker cash, margin/leverage, or score/confidence/RR multipliers
    here; ID-9 V0's `CapitalPolicy` has exactly these four fields and
    this config shape must not silently grow beyond it.

    Units (§5): `total_deployable_capital` is a plain INR amount (e.g.
    ``"500000.00"``). The two percentage fields use the same
    percent-*number* convention `CapitalPolicy` itself already freezes --
    ``"0.5"`` means 0.5%, never a 0-1 fraction and never 50%.

    Field bounds mirror `CapitalPolicy.__post_init__`'s own invariants
    exactly (never redefined independently) -- and `load_position_sizing_policy_config`
    below additionally constructs a real `CapitalPolicy` from validated
    field values, so those invariants run a second time, for real,
    rather than merely being duplicated here as a parallel range check.
    """

    total_deployable_capital: Decimal
    risk_budget_per_trade_pct: Decimal
    max_position_value_pct: Decimal
    policy_version: str

    @field_validator("total_deployable_capital", "risk_budget_per_trade_pct", "max_position_value_pct", mode="before")
    @classmethod
    def _decimal_fields_must_be_strings(cls, v: Any, info: Any) -> Any:
        return _require_decimal_string(v, field_name=f"position_sizing_policy.{info.field_name}")

    @field_validator("total_deployable_capital")
    @classmethod
    def _positive_capital(cls, v: Decimal) -> Decimal:
        if v <= 0:
            raise ValueError(f"position_sizing_policy.total_deployable_capital must be positive, got {v}")
        return v

    @field_validator("risk_budget_per_trade_pct")
    @classmethod
    def _valid_risk_pct(cls, v: Decimal) -> Decimal:
        if not (0 < v <= 100):
            raise ValueError(
                f"position_sizing_policy.risk_budget_per_trade_pct must be in (0, 100], got {v}"
            )
        return v

    @field_validator("max_position_value_pct")
    @classmethod
    def _valid_max_value_pct(cls, v: Decimal) -> Decimal:
        if not (0 < v <= 100):
            raise ValueError(
                f"position_sizing_policy.max_position_value_pct must be in (0, 100], got {v}"
            )
        return v

    @field_validator("policy_version")
    @classmethod
    def _non_empty_version(cls, v: str) -> str:
        """Trims surrounding whitespace only -- never lowercases, never
        rewrites interior characters. 2026-09-07 hardening: the prior
        version validated `v.strip()` for emptiness but returned the
        original untrimmed `v`, so `"capital-policy-v1"` and
        `" capital-policy-v1 "` would be accepted as different
        `policy_version` identities -- an accidental identity split a
        stray space in the JSON file could silently cause."""
        stripped = v.strip()
        if not stripped:
            raise ValueError("position_sizing_policy.policy_version is mandatory and must be non-empty")
        return stripped


def position_sizing_policy_config_path(config_dir: Path | str) -> Path:
    return Path(config_dir) / POSITION_SIZING_POLICY_CONFIG_FILENAME


def load_position_sizing_policy_config(config_dir: Path | str) -> CapitalPolicy | None:
    """Load + validate the ID-9 capital policy configuration.

    Missing file -> `None` (§4, safe absence): this is NOT an error --
    it is the production-safe default that leaves every ID-9 sizing
    observation honestly reporting `CAPITAL_POLICY_UNAVAILABLE`, exactly
    as it does today, until the Owner explicitly writes this file. A
    present-but-invalid file (bad JSON, wrong types, unknown keys, a
    bare-number percentage/amount, or any value `CapitalPolicy` itself
    would reject) fails loudly with `ConfigError` -- malformed config
    must never silently resolve to a usable (or a differently-shaped)
    policy, and it must never fall back to a dormant `capital.json`/
    `risk.json` value.

    On success, constructs exactly ONE immutable `CapitalPolicy`
    instance from the validated fields (§4) -- callers (namely
    `cli.py`'s `_owner_validation_pipeline`) inject that same instance
    into `OwnerValidationPipeline`, never a different one per symbol.
    """
    path = position_sizing_policy_config_path(config_dir)
    if not path.exists():
        return None
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise ConfigError(f"position sizing policy config is not valid JSON ({path}): {exc}") from exc
    if not isinstance(raw, dict):
        raise ConfigError(f"{path} must contain a JSON object at top level")
    try:
        parsed = PositionSizingPolicyConfig.model_validate(raw)
    except Exception as exc:  # pydantic.ValidationError
        raise ConfigError(f"invalid position sizing policy config ({path}): {exc}") from exc
    try:
        return CapitalPolicy(
            total_deployable_capital=parsed.total_deployable_capital,
            risk_budget_per_trade_pct=parsed.risk_budget_per_trade_pct,
            max_position_value_pct=parsed.max_position_value_pct,
            policy_version=parsed.policy_version,
        )
    except ValueError as exc:
        raise ConfigError(f"invalid position sizing policy config ({path}): {exc}") from exc
