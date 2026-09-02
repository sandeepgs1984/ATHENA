from __future__ import annotations

import sqlite3

from athena.data.id6b1_entry_qualification_baseline import pct, phi


def test_pct_handles_empty_denominator() -> None:
    assert pct(0, 0) == 0.0
    assert pct(1, 4) == 25.0


def test_phi_reports_perfect_positive_association() -> None:
    rows = [
        {"a": True, "b": True},
        {"a": True, "b": True},
        {"a": False, "b": False},
        {"a": False, "b": False},
    ]
    assert phi("a", "b", rows) == 1.0


def test_sqlite_query_only_blocks_writes() -> None:
    conn = sqlite3.connect(":memory:")
    conn.execute("CREATE TABLE t (id INTEGER PRIMARY KEY)")
    conn.execute("PRAGMA query_only=ON")
    try:
        try:
            conn.execute("INSERT INTO t (id) VALUES (1)")
        except sqlite3.OperationalError as exc:
            assert "readonly" in str(exc).lower() or "read-only" in str(exc).lower()
        else:  # pragma: no cover - defensive on unsupported SQLite builds
            raise AssertionError("query_only did not block a write")
    finally:
        conn.close()
