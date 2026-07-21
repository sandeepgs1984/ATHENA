"""Password hashing interface and implementation (P8.2)."""

from __future__ import annotations

from typing import Protocol

import bcrypt


class PasswordHasher(Protocol):
    """Protocol for password hashing. Abstracted from specific cryptosystems."""

    def hash(self, password: str) -> str:
        """Generate a secure hash for the given plain-text password."""
        ...

    def verify(self, password: str, hashed: str) -> bool:
        """Verify the password against the stored hash."""
        ...


class BcryptPasswordHasher:
    """Default PasswordHasher implementation wrapping bcrypt."""

    def __init__(self, rounds: int = 12) -> None:
        self._rounds = rounds

    def hash(self, password: str) -> str:
        salt = bcrypt.gensalt(self._rounds)
        return bcrypt.hashpw(password.encode("utf-8"), salt).decode("utf-8")

    def verify(self, password: str, hashed: str) -> bool:
        try:
            return bcrypt.checkpw(
                password.encode("utf-8"), hashed.encode("utf-8")
            )
        except Exception:
            return False
