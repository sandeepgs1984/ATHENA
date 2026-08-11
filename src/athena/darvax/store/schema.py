"""DarvaX's own SQLite schema, versioned independently of ATHENA (ADR-010 §2).

DarvaX keeps its own database file (``db/darvax.db``). ATHENA's
``SCHEMA_VERSION``, ``ddl_statements()``, ``record_counts()``, backup, restore,
and integrity checks remain untouched and unaware of anything here — which is
what makes "delete DarvaX" a clean, complete operation.

DX-1 deliberately defines only the version table. Signal/evidence tables belong
to DX-3, which is where the first DarvaX artifacts are actually produced.
"""

from __future__ import annotations

#: Bumped independently of ATHENA's SCHEMA_VERSION. They never interact.
DARVAX_SCHEMA_VERSION = 1

_DDL: tuple[str, ...] = (
    "CREATE TABLE IF NOT EXISTS darvax_schema_version (version INTEGER NOT NULL)",
)


def darvax_ddl_statements() -> tuple[str, ...]:
    return _DDL
