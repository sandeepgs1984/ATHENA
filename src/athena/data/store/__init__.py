"""Persistent storage layer (M1.5): SQLite repository for canonical market data.

Persistence only — no provider, validation, or intelligence logic. Returns
canonical domain objects, never database rows.
"""

from athena.data.store.repository import IntegrityReport, SqliteRepository
from athena.data.store.schema import SCHEMA_VERSION

__all__ = ["IntegrityReport", "SCHEMA_VERSION", "SqliteRepository"]
