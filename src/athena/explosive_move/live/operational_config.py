"""EM-7B: EMR-owned operational configuration for the live-shadow worker
(ADR-014 §§9, 23).

Mirrors DarvaX's config-gate PATTERN only (`athena.darvax.config`'s own
`_Strict`/loader shape) -- this module does not import DarvaX code, and
DarvaX does not import this. `config/emr/operational.json` is EMR-owned,
separate from `config/darvax.json` and from ATHENA's own `athena.config`
stack.

**EM-7B.1 authority correction (2026-09-04):** Owner/Chief Architect
source review found that `EmrOperationalConfig` originally also carried
`max_checkpoint_price_delay_seconds` as an independently operator-
tunable field, set to `300.0` -- a value that, by coincidence of
provenance rather than deliberate citation, happened to exactly equal
`checkpoint_reference_price.MAX_CHECKPOINT_OBSERVATION_DELAY_SECONDS`, a
value that module's own docstring calls a "**Frozen bound**... EM-5 must
not dynamically retune this." Having a frozen, owner-approved bound sit
in an operator-editable JSON file was itself the defect, independent of
whether the shipped number happened to be correct. **Resolved:** the
field is removed entirely; `worker.py` now imports and uses the frozen
constant directly, so no config edit can ever change it. `max_staleness_minutes`
was independently audited and kept -- `eligibility.py`'s own docstring
explicitly documents it as "an operational tuning knob, not evidence,"
distinct from the frozen bound above, and its shipped default (`30.0`)
matches `canary_gate.run_em5_production_canary`'s own already-accepted
default exactly (proven by a regression test importing that function's
real signature, not a hardcoded duplicate). `base_universe`/`model_version`
remain configurable *selectors* (owner's own framing) but
`load_emr_operational_config` now validates each resolves to an
already-frozen, already-approved source -- `base_universe` against
ADR-014 §11's own named base universe, `model_version` against an
actually-promoted `config/emr/frozen_models/<version>/` artifact whose
own manifest agrees -- so a config edit can select among frozen
artifacts/policies but can never invent an unapproved one. Direct
`EmrOperationalConfig(...)` construction (this module's test suite's own
extensive fixture-isolation use) is deliberately NOT constrained this
way -- the authority boundary lives at the config-*file*-loading
boundary (`load_emr_operational_config`), the one an operator can
actually reach by editing JSON, not at the general-purpose dataclass's
own constructor.

Contains operational concerns only: the `enabled` gate (shipped default
`False`), which base ADR-011 universe to resolve before applying the
frozen mature-history filter, which frozen model artifact version to
load, one staleness tolerance already used by `ScanCycleConfig` (the one
genuinely operational tolerance -- see the correction note above), and
the worker's own poll cadence. It must never gain a feature/model/
calibration/threshold field, nor any other genuinely frozen runtime
bound -- those are either frozen research artifacts under
`config/emr/frozen_models/` (loaded by `frozen_inference.load_frozen_model`)
or frozen Python constants (like `MAX_CHECKPOINT_OBSERVATION_DELAY_SECONDS`),
never JSON configuration.
"""

from __future__ import annotations

import json
from pathlib import Path

from pydantic import BaseModel, ConfigDict, Field, ValidationError, model_validator

from athena.errors import ConfigError

#: Filename EMR owns, resolved relative to the caller's config directory
#: (i.e. `config/emr/operational.json`).
EMR_OPERATIONAL_CONFIG_RELATIVE_PATH = Path("emr") / "operational.json"

#: ADR-014 §11's own frozen initial-EM-7-shadow base universe -- "the
#: same base universe Section 14's canary used." `EmrOperationalConfig`
#: (a general-purpose, freely-constructible dataclass used extensively by
#: this module's own test suite for fixture isolation) does not enforce
#: this itself; `load_emr_operational_config` -- the boundary an operator
#: actually reaches by editing JSON -- does.
ADR_014_APPROVED_BASE_UNIVERSE = "athena_core"


class _Strict(BaseModel):
    """Unknown keys are errors -- a typo in EMR operational config must
    fail loudly, never silently default to enabled behavior. Mirrors
    `athena.config.models._Strict`/`athena.darvax.config._Strict`'s
    identical convention, independently (EMR owns its own config stack):
    keys prefixed with `_` are human documentation, dropped before
    validation at every nesting level."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    @model_validator(mode="before")
    @classmethod
    def _drop_doc_keys(cls, values: object) -> object:
        if isinstance(values, dict):
            return {k: v for k, v in values.items() if not (isinstance(k, str) and k.startswith("_"))}
        return values


class EmrOperationalConfig(_Strict):
    """The complete EM-7B operational configuration contract, owned
    entirely by EMR. Shipped default is `enabled=False` -- EMR live
    scheduling is opt-in, exactly mirroring DarvaX's own ADR-010 §7
    default-disabled pattern."""

    enabled: bool = Field(
        default=False,
        description="Off (default): the worker never initializes EmrRepository, never creates "
        "db/emr.db, never invokes the scanner, never makes a provider call.",
    )
    base_universe: str = Field(
        default="athena_core",
        min_length=1,
        description="The base ADR-011 named universe resolved before the frozen mature-history "
        "filter (select_mature_history_instruments) narrows it -- the same base universe "
        "Section 14's canary used. Not itself the scanned population.",
    )
    model_version: str = Field(
        default="v1",
        min_length=1,
        description="Which promoted frozen model/deterministic-rule artifact version "
        "(config/emr/frozen_models/<version>/) to load -- a version selector, "
        "never a methodology parameter itself.",
    )
    max_staleness_minutes: float = Field(
        default=30.0, gt=0,
        description="Passed straight through to ScanCycleConfig.max_staleness_minutes. Genuinely "
        "operational (eligibility.py's own docstring: 'an operational tuning knob, not evidence') "
        "-- unlike the checkpoint-price delay tolerance, this is legitimately configurable here. "
        "Shipped default matches canary_gate.run_em5_production_canary's own accepted default.",
    )
    poll_interval_seconds: float = Field(
        default=30.0, ge=5.0,
        description="How often the background worker loop ticks. Not a per-checkpoint cadence -- "
        "the worker derives which single checkpoint (if any) is due and not yet represented "
        "on every tick; a shorter interval only makes that decision sooner, it never causes "
        "extra invocations (see worker.py's checkpoint-due algorithm).",
    )


def emr_operational_config_path(config_dir: Path | str) -> Path:
    return Path(config_dir) / EMR_OPERATIONAL_CONFIG_RELATIVE_PATH


def _validate_resolves_to_frozen_sources(config: EmrOperationalConfig, config_dir: Path | str) -> None:
    """EM-7B.1 (Owner/Chief Architect correction): `base_universe` and
    `model_version` remain configurable *selectors*, but an edited config
    file must never be able to select an unapproved universe or a
    never-promoted model artifact. Applied only to a real, explicitly
    loaded config file -- never to direct `EmrOperationalConfig(...)`
    construction, which this module's own test suite uses extensively
    for fixture isolation, and which has no config-file boundary to
    police in the first place."""
    if config.base_universe != ADR_014_APPROVED_BASE_UNIVERSE:
        raise ConfigError(
            f"EMR operational config base_universe {config.base_universe!r} is not the ADR-014 "
            f"Section 11 frozen initial-shadow base universe {ADR_014_APPROVED_BASE_UNIVERSE!r} -- "
            "refusing to silently scan an unapproved universe"
        )
    manifest_path = Path(config_dir) / "emr" / "frozen_models" / config.model_version / "FROZEN_MODEL_MANIFEST.json"
    if not manifest_path.is_file():
        raise ConfigError(
            f"EMR operational config model_version {config.model_version!r} has no promoted frozen "
            f"model manifest at {manifest_path} -- refusing to select a never-promoted artifact"
        )
    try:
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise ConfigError(f"frozen model manifest is not valid JSON ({manifest_path}): {exc}") from exc
    manifest_version = manifest.get("version")
    if manifest_version != config.model_version:
        raise ConfigError(
            f"EMR operational config model_version {config.model_version!r} does not match its own "
            f"promoted manifest's recorded version {manifest_version!r} ({manifest_path})"
        )


def load_emr_operational_config(config_dir: Path | str) -> EmrOperationalConfig:
    """Load + validate the EMR operational configuration. Missing file is
    NOT an error -- it is treated exactly like an explicit
    `{"enabled": false}` (every other field takes its default), so a
    fresh checkout with no `config/emr/operational.json` yet is safely
    inert rather than a hard failure -- the frozen-source check below
    does not apply to this inert default. A present-but-invalid file (bad
    JSON, wrong types, unknown keys, or a base_universe/model_version
    that does not resolve to an already-frozen, already-approved source)
    fails loudly -- malformed config must never silently resolve to
    enabled behavior, and a config edit must never silently change scanner
    evidence acceptance."""
    path = emr_operational_config_path(config_dir)
    if not path.exists():
        return EmrOperationalConfig()
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise ConfigError(f"EMR operational config is not valid JSON ({path}): {exc}") from exc
    try:
        config = EmrOperationalConfig.model_validate(raw)
    except ValidationError as exc:
        raise ConfigError(f"invalid EMR operational config ({path}): {exc}") from exc
    _validate_resolves_to_frozen_sources(config, config_dir)
    return config
