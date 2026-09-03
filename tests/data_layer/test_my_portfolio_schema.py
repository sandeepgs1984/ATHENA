"""PS-P1 My Portfolio SQLite schema contract tests."""

from __future__ import annotations

import sqlite3
from pathlib import Path

import pytest

from athena.data.store.repository import SqliteRepository
from athena.data.store.schema import SCHEMA_VERSION


def _columns(conn: sqlite3.Connection, table: str) -> set[str]:
    return {row[1] for row in conn.execute(f"PRAGMA table_info({table})")}


def _seed_confirmed_holdings(
    repo: SqliteRepository,
    rows: list[tuple[str, int, str]],
) -> None:
    conn = repo._conn  # type: ignore[attr-defined]
    conn.execute(
        """
        INSERT INTO portfolio_imports (
            import_id, filename, source, uploaded_at, parser_version, status,
            total_rows, accepted_rows, rejected_rows, unresolved_rows, ambiguous_rows
        )
        VALUES ('digest-import', 'holdings.csv', 'generic', '2026-09-02T10:00:00+00:00',
            'v1', 'CONFIRMED', ?, ?, 0, 0, 0)
        """,
        (len(rows), len(rows)),
    )
    for index, (instrument_id, quantity, avg_price) in enumerate(rows, start=1):
        conn.execute(
            """
            INSERT INTO portfolio_holdings (
                holding_id, instrument_id, quantity, avg_price, imported_at, updated_at,
                source_import_id, source_row_id
            )
            VALUES (?, ?, ?, ?, '2026-09-02T10:00:00+00:00',
                '2026-09-02T10:00:00+00:00', 'digest-import', ?)
            """,
            (f"hold-{index}", instrument_id, quantity, avg_price, str(index)),
        )
    conn.commit()


def test_my_portfolio_tables_are_created_in_athena_schema(tmp_path: Path) -> None:
    repo = SqliteRepository(tmp_path / "athena.db")
    repo.initialize()

    expected = {
        "portfolio_imports",
        "portfolio_import_rows",
        "portfolio_holdings",
        "portfolio_reconciliations",
        "portfolio_sync_runs",
        "portfolio_analysis_snapshots",
    }
    tables = {
        row[0]
        for row in repo._conn.execute(  # type: ignore[attr-defined]
            "SELECT name FROM sqlite_master WHERE type='table'"
        )
    }

    assert expected <= tables
    assert repo._conn.execute("SELECT version FROM schema_version").fetchone()[0] == SCHEMA_VERSION
    repo.close()


def test_my_portfolio_schema_preserves_owner_positions_contract(tmp_path: Path) -> None:
    repo = SqliteRepository(tmp_path / "athena.db")
    repo.initialize()

    assert _columns(repo._conn, "owner_positions") == {  # type: ignore[attr-defined]
        "position_id",
        "instrument_id",
        "opened_ts",
        "quantity",
        "avg_price",
        "closed_ts",
        "exit_price",
        "decision_ref",
        "broker",
        "notes",
        "sector",
        "meta_json",
    }
    repo.close()


def test_canonical_holding_uniqueness_by_instrument(tmp_path: Path) -> None:
    repo = SqliteRepository(tmp_path / "athena.db")
    repo.initialize()
    conn = repo._conn  # type: ignore[attr-defined]
    conn.execute(
        """
        INSERT INTO portfolio_imports (
            import_id, filename, source, uploaded_at, parser_version, status,
            total_rows, accepted_rows, rejected_rows, unresolved_rows, ambiguous_rows
        )
        VALUES ('imp-1', 'holdings.csv', 'generic', '2026-09-02T10:00:00+00:00',
            'v1', 'CONFIRMED', 1, 1, 0, 0, 0)
        """
    )
    conn.execute(
        """
        INSERT INTO portfolio_holdings (
            holding_id, instrument_id, quantity, avg_price, imported_at, updated_at,
            source_import_id, source_row_id
        )
        VALUES ('hold-1', 'NSE:INFY', 10, '1500',
            '2026-09-02T10:00:00+00:00', '2026-09-02T10:00:00+00:00',
            'imp-1', '1')
        """
    )

    with pytest.raises(sqlite3.IntegrityError):
        conn.execute(
            """
            INSERT INTO portfolio_holdings (
                holding_id, instrument_id, quantity, avg_price, imported_at, updated_at,
                source_import_id, source_row_id
            )
            VALUES ('hold-2', 'NSE:INFY', 5, '1510',
                '2026-09-02T10:00:00+00:00', '2026-09-02T10:00:00+00:00',
                'imp-1', '2')
            """
        )
    repo.close()


def test_portfolio_holdings_digest_is_stable_and_order_independent(tmp_path: Path) -> None:
    repo_a = SqliteRepository(tmp_path / "a.db")
    repo_b = SqliteRepository(tmp_path / "b.db")
    repo_a.initialize()
    repo_b.initialize()
    _seed_confirmed_holdings(
        repo_a,
        [("NSE:INFY", 10, "1500"), ("NSE:TCS", 5, "3000")],
    )
    _seed_confirmed_holdings(
        repo_b,
        [("NSE:TCS", 5, "3000"), ("NSE:INFY", 10, "1500")],
    )

    assert repo_a.portfolio_holdings_digest() == repo_b.portfolio_holdings_digest()
    repo_a.close()
    repo_b.close()


@pytest.mark.parametrize(
    "rows",
    [
        [("NSE:INFY", 11, "1500"), ("NSE:TCS", 5, "3000")],
        [("NSE:INFY", 10, "1510"), ("NSE:TCS", 5, "3000")],
        [("NSE:INFY", 10, "1500"), ("NSE:TCS", 5, "3000"), ("NSE:RELIANCE", 1, "2800")],
        [("NSE:INFY", 10, "1500")],
    ],
)
def test_portfolio_holdings_digest_changes_with_sync_relevant_facts(
    tmp_path: Path,
    rows: list[tuple[str, int, str]],
) -> None:
    base = SqliteRepository(tmp_path / "base.db")
    changed = SqliteRepository(tmp_path / "changed.db")
    base.initialize()
    changed.initialize()
    _seed_confirmed_holdings(
        base,
        [("NSE:INFY", 10, "1500"), ("NSE:TCS", 5, "3000")],
    )
    _seed_confirmed_holdings(changed, rows)

    assert changed.portfolio_holdings_digest() != base.portfolio_holdings_digest()
    base.close()
    changed.close()


def test_schema_has_sync_and_analysis_provenance_columns(tmp_path: Path) -> None:
    repo = SqliteRepository(tmp_path / "athena.db")
    repo.initialize()
    conn = repo._conn  # type: ignore[attr-defined]

    assert {
        "status",
        "market_data_through",
        "validation_run_id",
        "analysis_version",
        "progress_json",
        "per_symbol_json",
        "error_json",
    } <= _columns(conn, "portfolio_sync_runs")
    assert {
        "row_json",
        "freshness_json",
        "provenance_json",
        "unavailable_json",
        "failure_json",
    } <= _columns(conn, "portfolio_analysis_snapshots")
    repo.close()
