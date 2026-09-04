"""EM-7B: EMR-owned operational configuration for the live-shadow worker
(ADR-014 §§9, 23).

Mirrors DarvaX's config-gate PATTERN only (`athena.darvax.config`'s own
`_Strict`/loader shape) -- this module does not import DarvaX code, and
DarvaX does not import this. `config/emr/operational.json` is EMR-owned,
separate from `config/darvax.json` and from ATHENA's own `athena.config`
stack.

Contains operational concerns only: the `enabled` gate (shipped default
`False`), which base ADR-011 universe to resolve before applying the
frozen mature-history filter, which frozen model artifact version to
load, staleness/delay tolerances already used by `ScanCycleConfig`, and
the worker's own poll cadence. It must never gain a feature/model/
calibration/threshold field -- those are frozen research artifacts under
`config/emr/frozen_models/`, loaded by `frozen_inference.load_frozen_model`,
not configuration.
"""

from __future__ import annotations

import json
from pathlib import Path

from pydantic import BaseModel, ConfigDict, Field, ValidationError, model_validator

from athena.errors import ConfigError

#: Filename EMR owns, resolved relative to the caller's config directory
#: (i.e. `config/emr/operational.json`).
EMR_OPERATIONAL_CONFIG_RELATIVE_PATH = Path("emr") / "operational.json"


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
        description="Passed straight through to ScanCycleConfig.max_staleness_minutes.",
    )
    max_checkpoint_price_delay_seconds: float = Field(
        default=300.0, gt=0,
        description="Passed straight through to ScanCycleConfig.max_checkpoint_price_delay_seconds.",
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


def load_emr_operational_config(config_dir: Path | str) -> EmrOperationalConfig:
    """Load + validate the EMR operational configuration. Missing file is
    NOT an error -- it is treated exactly like an explicit
    `{"enabled": false}` (every other field takes its default), so a
    fresh checkout with no `config/emr/operational.json` yet is safely
    inert rather than a hard failure. A present-but-invalid file (bad
    JSON, wrong types, unknown keys) still fails loudly -- malformed
    config must never silently resolve to enabled behavior."""
    path = emr_operational_config_path(config_dir)
    if not path.exists():
        return EmrOperationalConfig()
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise ConfigError(f"EMR operational config is not valid JSON ({path}): {exc}") from exc
    try:
        return EmrOperationalConfig.model_validate(raw)
    except ValidationError as exc:
        raise ConfigError(f"invalid EMR operational config ({path}): {exc}") from exc
