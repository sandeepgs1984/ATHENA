"""The single approved ATHENA→DarvaX seam (ADR-010 §4).

This is the *only* place in ATHENA core that knows DarvaX exists, and it knows
exactly one fact about it: whether activation was requested. It deliberately
does not import ``athena.darvax`` at module scope — the import happens inside
``mount_darvax_if_enabled`` and only after the flag says yes, which is what
makes "disabled means never imported" true rather than aspirational.

Deleting this file, ``config/darvax.json``, ``src/athena/darvax/``, and the
three-line call in ``create_app`` removes DarvaX completely and leaves ATHENA
unchanged.

**Methodology blindness is the point.** Nothing here parses stop policies, EMA
ladders, Fibonacci parameters, box settings, or signal thresholds — those are
DarvaX's to own and validate (ADR-010 §8). ATHENA reads one boolean.
"""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import TYPE_CHECKING

from athena.errors import ConfigError

if TYPE_CHECKING:  # pragma: no cover - typing only, never an runtime import
    from fastapi import FastAPI

logger = logging.getLogger(__name__)

#: DarvaX owns this file; ATHENA only ever reads the one key below from it.
_DARVAX_CONFIG_FILENAME = "darvax.json"

#: The only key ATHENA is permitted to read out of DarvaX's config.
_ACTIVATION_KEY = "enabled"

#: Where the satellite mounts. Kept here so the seam is fully self-contained.
DARVAX_MOUNT_PATH = "/darvax"

#: The only ATHENA app-state objects shared with the DarvaX sub-application, and
#: solely so DarvaX can *delegate* authentication to ATHENA rather than
#: implementing its own (DX-4). ATHENA's auth guard reads these from
#: ``request.app.state``, which for a mounted sub-app is the sub-app's own state.
#: Nothing else is shared: DarvaX gets no providers, no repositories, no config.
_SHARED_AUTH_STATE: tuple[str, ...] = ("token_signer", "claims_factory")


def darvax_activation_requested(config_dir: Path | str) -> bool:
    """Whether ``config/darvax.json`` asks for the satellite to be active.

    Reads **only** ``enabled``. A missing file means "not requested" — DarvaX is
    opt-in and its absence is a normal, supported state, not an error.
    """
    path = Path(config_dir) / _DARVAX_CONFIG_FILENAME
    if not path.is_file():
        return False
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise ConfigError(f"DarvaX config is not valid JSON ({path}): {exc}") from exc
    if not isinstance(raw, dict):
        raise ConfigError(f"DarvaX config must be a JSON object ({path})")
    return bool(raw.get(_ACTIVATION_KEY, False))


def _default_repo_root() -> Path:
    """Repo root, resolved locally so this seam stays self-contained/removable."""
    root = Path(__file__).resolve().parent
    for _ in range(8):
        if (root / "pyproject.toml").is_file():
            break
        root = root.parent
    return root


def mount_darvax_if_enabled(
    app: FastAPI,
    *,
    repo: object | None,
    config_dir: Path | str | None = None,
    repo_root: Path | str | None = None,
) -> bool:
    """Mount the DarvaX satellite when enabled. Returns whether it mounted.

    An ``enabled: true`` that cannot be honoured is a hard startup failure, not
    a silent downgrade (ADR-010 §4): leaving the owner believing DarvaX is
    running when it is not is a worse outcome than refusing to start.
    """
    resolved_root = Path(repo_root) if repo_root is not None else _default_repo_root()
    resolved_config_dir = (
        Path(config_dir) if config_dir is not None else resolved_root / "config"
    )

    if not darvax_activation_requested(resolved_config_dir):
        return False

    try:
        from athena.darvax.api import SqliteMarketDataAdapter, create_darvax_app
    except ImportError as exc:
        raise ConfigError(
            "DarvaX is enabled in config/darvax.json but the DarvaX module "
            "(athena.darvax) is not present. Either restore/install the module, "
            f"or set {_ACTIVATION_KEY}=false in config/darvax.json."
        ) from exc

    if repo is None:
        raise ConfigError(
            "DarvaX is enabled in config/darvax.json but ATHENA's SQLite ledger "
            "is not available to read from. Start the API with the live ledger "
            f"wired, or set {_ACTIVATION_KEY}=false in config/darvax.json."
        )

    darvax_app = create_darvax_app(
        config_dir=resolved_config_dir,
        market_data=SqliteMarketDataAdapter(repo),  # type: ignore[arg-type]
        repo_root=resolved_root,
    )

    # DarvaX delegates authentication to ATHENA instead of standing up a second
    # login: one credential, one place where auth correctness lives. ATHENA's
    # guard resolves these two objects from ``request.app.state``, and a mounted
    # sub-application has its own ``state``, so they are shared explicitly here.
    # Only these two are copied — DarvaX gets no other ATHENA app state.
    for attribute in _SHARED_AUTH_STATE:
        if hasattr(app.state, attribute):
            setattr(darvax_app.state, attribute, getattr(app.state, attribute))

    app.mount(DARVAX_MOUNT_PATH, darvax_app)
    logger.info("DarvaX satellite mounted at %s (experimental)", DARVAX_MOUNT_PATH)
    return True
