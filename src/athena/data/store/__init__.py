"""Persistent storage layer (M1.5): SQLite repository for canonical market data.

Persistence only — no provider, validation, or intelligence logic. Returns
canonical domain objects, never database rows.
"""

from athena.data.store.backup import (
    BackupResult,
    RestoreResult,
    create_backup,
    restore_backup,
)
from athena.data.store.repository import IntegrityReport, SqliteRepository
from athena.data.store.schema import SCHEMA_VERSION

__all__ = [
    "SCHEMA_VERSION",
    "BackupResult",
    "IntegrityReport",
    "RestoreResult",
    "SqliteRepository",
    "create_backup",
    "restore_backup",
]
