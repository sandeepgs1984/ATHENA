"""DarvaX-owned configuration (ADR-010 §8).

The ownership boundary is absolute:

* **ATHENA core** reads exactly one thing from ``config/darvax.json`` — whether
  satellite activation is requested — via the methodology-blind helper in
  ``athena.api.darvax_mount``. That is the total extent of its knowledge.
* **DarvaX** (this module) loads, validates, and owns the complete
  ``DarvaxConfig`` *after* the mount decision has already been made.

No DarvaX methodology field may ever appear in an ``athena.config`` model. The
fact that both files live under ``config/`` is a filesystem convention, not a
shared-ownership claim.

DX-1 note: the methodology block below is **schema only**. Nothing in DX-1
reads these values to compute anything — no stop is calculated, no EMA is
evaluated. They exist here so that configuration *ownership and validation*
can be proven now (ADR-010 DX-1 acceptance test 12), ahead of the DX-2/DX-3
milestones that will actually consume them.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, ValidationError, model_validator

from athena.errors import ConfigError

#: Filename DarvaX owns, resolved relative to the caller's config directory.
DARVAX_CONFIG_FILENAME = "darvax.json"


class _Strict(BaseModel):
    """Unknown keys are errors — a typo in DarvaX config must fail loudly.

    Mirrors ``athena.config.models._Strict``'s convention (independently, since
    DarvaX owns its own config stack): keys prefixed with ``_`` are human
    documentation, not configuration, and are dropped at every nesting level
    before validation.
    """

    model_config = ConfigDict(extra="forbid", frozen=True)

    @model_validator(mode="before")
    @classmethod
    def _drop_doc_keys(cls, values: object) -> object:
        if isinstance(values, dict):
            return {
                k: v
                for k, v in values.items()
                if not (isinstance(k, str) and k.startswith("_"))
            }
        return values


class DarvaxDatabaseConfig(_Strict):
    """Where DarvaX keeps its own ledger. Never ``db/athena.db`` (ADR-010 §2)."""

    path: str = Field(
        default="db/darvax.db",
        min_length=1,
        description="DarvaX-owned SQLite file, separate from ATHENA's database.",
    )


class DarvaxMethodologyConfig(_Strict):
    """Methodology parameters — schema and validation only in DX-1.

    ADR-010 §8 records that the source deck contradicts itself on stop sizing:
    Nicolas Darvas' canonical rule is a 10% stop on first breakout (deck p.67),
    while DarvaX's own "How to Play" says 1% (deck p.44). That contradiction is
    deliberately *not* settled in code — both are selectable, defaulting to the
    canonical attributable rule, and DX-5's evidence decides which is used.
    """

    stop_policy: Literal["canonical_darvas", "darvax_tight"] = Field(
        default="canonical_darvas",
        description="Which documented stop rule to apply once DX-3 consumes it.",
    )
    canonical_stop_pct: float = Field(
        default=10.0, gt=0.0, le=50.0,
        description="Darvas' canonical first-breakout stop, deck p.67.",
    )
    tight_stop_pct: float = Field(
        default=1.0, gt=0.0, le=50.0,
        description="DarvaX's own tighter variant, deck p.44.",
    )
    ema_stop_ladder: dict[str, int] = Field(
        default_factory=lambda: {
            "very_short_term": 5,
            "swing": 10,
            "positional": 20,
            "investor": 200,
        },
        description="Close-below EMA exit ladder by horizon, deck p.9.",
    )


class DarvaxConfig(_Strict):
    """The complete DarvaX configuration contract, owned entirely by DarvaX."""

    enabled: bool = Field(
        default=False,
        description="Shipped default is False — DarvaX is opt-in (ADR-010 §7).",
    )
    database: DarvaxDatabaseConfig = Field(default_factory=DarvaxDatabaseConfig)
    methodology: DarvaxMethodologyConfig = Field(
        default_factory=DarvaxMethodologyConfig
    )


def darvax_config_path(config_dir: Path | str) -> Path:
    return Path(config_dir) / DARVAX_CONFIG_FILENAME


def load_darvax_config(config_dir: Path | str) -> DarvaxConfig:
    """Load + validate the full DarvaX configuration.

    Called by DarvaX itself, only after ATHENA's mount seam has already decided
    activation was requested. ATHENA never calls this — it would couple
    ATHENA's startup to DarvaX methodology validation, which ADR-010 forbids.
    """
    path = darvax_config_path(config_dir)
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise ConfigError(f"DarvaX config not found: {path}") from exc
    except json.JSONDecodeError as exc:
        raise ConfigError(f"DarvaX config is not valid JSON ({path}): {exc}") from exc
    try:
        return DarvaxConfig.model_validate(raw)
    except ValidationError as exc:
        raise ConfigError(f"invalid DarvaX config ({path}): {exc}") from exc
