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

import hashlib
import json
from decimal import Decimal
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


class DarvaxBoxConfig(_Strict):
    """Darvas box construction settings (DX-2 primitive, wired here in DX-3)."""

    confirmation_bars: int = Field(
        default=3, ge=1, le=50,
        description=(
            "Bars a ceiling/floor must survive unbeaten to be confirmed. The "
            "deck states no number; 3 is the value used by the classical Darvas "
            "implementations it links to."
        ),
    )


class DarvaxSwingConfig(_Strict):
    """ZigZag swing settings (deck p.32)."""

    threshold_pct: Decimal = Field(
        default=Decimal("5"), gt=Decimal(0), le=Decimal(100),
        description="Reversal percentage that confirms a ZigZag pivot.",
    )


class DarvaxBreakoutConfig(_Strict):
    """Box breakout / retest recognition (deck p.28 'Breakout-Retest', p.44)."""

    retest_tolerance_pct: Decimal = Field(
        default=Decimal("2"), gt=Decimal(0), le=Decimal(25),
        description=(
            "How close price must come back to the box ceiling to count as a "
            "retest, as a percentage of the ceiling. The deck shows retests "
            "qualitatively (the #TRENT example) without naming a tolerance."
        ),
    )
    stop_horizon: Literal[
        "very_short_term", "swing", "positional", "investor"
    ] = Field(
        default="swing",
        description=(
            "Which rung of the EMA stop ladder applies (deck p.9). 'swing' is "
            "the 10 EMA rung, matching ATHENA's own swing-trading focus."
        ),
    )


class DarvaxScanConfig(_Strict):
    """Bounds on a DarvaX scan (DX-4).

    Both bounds exist to keep the satellite's read load explicitly capped rather
    than open-ended: DarvaX shares a workstation with ATHENA, and ADR-010's
    performance guarantee is architectural (no synchronous dependency), not a
    promise of zero host-level contention. DX-4a measures that contention; these
    caps keep it bounded in the meantime.
    """

    max_instruments: int = Field(
        default=50, ge=1, le=1000,
        description="Most instruments one scan request may evaluate.",
    )
    lookback_bars: int = Field(
        default=400, ge=10, le=5000,
        description="Candles per instrument fed to the signal engine.",
    )


class DarvaxMethodologyConfig(_Strict):
    """Methodology parameters, owned entirely by DarvaX.

    ADR-010 §8 records that the source deck contradicts itself on stop sizing:
    Nicolas Darvas' canonical rule is a 10% stop on first breakout (deck p.67),
    while DarvaX's own "How to Play" says 1% (deck p.44). That contradiction is
    deliberately *not* settled in code — both are selectable, defaulting to the
    canonical attributable rule, and DX-5's evidence decides which is used.

    Every numeric here is either quoted from the deck or, where the deck is
    silent, carries a documented rationale — never an invented value presented
    as the author's.
    """

    stop_policy: Literal["canonical_darvas", "darvax_tight", "ema_ladder"] = Field(
        default="canonical_darvas",
        description=(
            "Which documented stop rule to apply. 'canonical_darvas' = 10% on "
            "first breakout (deck p.67); 'darvax_tight' = 1% below entry (deck "
            "p.44); 'ema_ladder' = close-below-EMA for the configured horizon "
            "(deck p.9)."
        ),
    )
    canonical_stop_pct: Decimal = Field(
        default=Decimal("10"), gt=Decimal(0), le=Decimal(50),
        description="Darvas' canonical first-breakout stop, deck p.67.",
    )
    tight_stop_pct: Decimal = Field(
        default=Decimal("1"), gt=Decimal(0), le=Decimal(50),
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
    box: DarvaxBoxConfig = Field(default_factory=DarvaxBoxConfig)
    swing: DarvaxSwingConfig = Field(default_factory=DarvaxSwingConfig)
    breakout: DarvaxBreakoutConfig = Field(default_factory=DarvaxBreakoutConfig)

    @model_validator(mode="after")
    def _ladder_must_cover_the_selected_horizon(self) -> DarvaxMethodologyConfig:
        horizon = self.breakout.stop_horizon
        if horizon not in self.ema_stop_ladder:
            raise ValueError(
                f"ema_stop_ladder has no rung for breakout.stop_horizon "
                f"{horizon!r}; available rungs: {sorted(self.ema_stop_ladder)}"
            )
        for name, period in self.ema_stop_ladder.items():
            if period < 1:
                raise ValueError(
                    f"ema_stop_ladder[{name!r}] must be >= 1, got {period}"
                )
        return self


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
    scan: DarvaxScanConfig = Field(default_factory=DarvaxScanConfig)


def methodology_digest(methodology: DarvaxMethodologyConfig) -> str:
    """Stable short hash of the methodology settings.

    Persisted alongside every DarvaX signal so a signal can always be traced
    back to the exact parameters that produced it — the replayability
    requirement in ADR-010 §10. Deterministic: same settings always yield the
    same digest, and any change to any value changes it.
    """
    canonical = json.dumps(
        methodology.model_dump(mode="json"), sort_keys=True, separators=(",", ":")
    )
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()[:16]


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
