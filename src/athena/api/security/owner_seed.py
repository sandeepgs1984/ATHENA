"""Seed the single owner account from environment (Live Entry M-E1).

Secrets stay in ``.env``. Prefer ``ATHENA_OWNER_PASSWORD_HASH`` (bcrypt);
generate with ``athena set-owner-password``.
"""

from __future__ import annotations

import logging
import os

from athena.api.security.models import Role, User
from athena.api.security.repos import UserRepository

logger = logging.getLogger(__name__)

OWNER_USER_ID = "usr-owner"


def owner_credentials_configured() -> bool:
    """True when a bcrypt password hash is present for the owner account."""
    return bool(os.environ.get("ATHENA_OWNER_PASSWORD_HASH", "").strip())


def single_user_bypass_enabled() -> bool:
    """Allow unauthenticated ADMIN principal when owner auth is not configured.

    When ``ATHENA_OWNER_PASSWORD_HASH`` is set, bypass is disabled even if
    ``ATHENA_SINGLE_USER=true`` so the unlock screen is authoritative.
    """
    if owner_credentials_configured():
        return False
    return os.environ.get("ATHENA_SINGLE_USER", "false").lower() == "true"


def auth_required() -> bool:
    """Whether the dashboard must present a session (JWT) for API access."""
    return not single_user_bypass_enabled()


def seed_owner_user(user_repo: UserRepository) -> User | None:
    """Upsert the owner ADMIN user from env. Returns None if not configured."""
    password_hash = os.environ.get("ATHENA_OWNER_PASSWORD_HASH", "").strip()
    if not password_hash:
        return None

    username = (os.environ.get("ATHENA_OWNER_USER") or "owner").strip() or "owner"
    user = User(
        user_id=OWNER_USER_ID,
        username=username,
        password_hash=password_hash,
        role=Role.ADMIN,
        is_active=True,
    )
    user_repo.save(user)
    logger.info("Owner auth user seeded (username=%s)", username)
    return user
