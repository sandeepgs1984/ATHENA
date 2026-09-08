"""Portfolio Sync catalog-miss and BSE remap tests."""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

import pytest

from athena.api.v1.services.my_portfolio_service import MyPortfolioService
from athena.data.store.repository import SqliteRepository
from athena.errors import RepositoryError
from athena.ops.symbol_validate import SymbolValidateResult

NOW = datetime(2026, 9, 8, 3, 6, tzinfo=timezone.utc)


def _seed_holding(repo: SqliteRepository, instrument_id: str) -> None:
    conn = repo._conn  # type: ignore[attr-defined]
    conn.execute(
        """
        INSERT INTO portfolio_imports (
            import_id, filename, source, uploaded_at, parser_version, status,
            total_rows, accepted_rows, rejected_rows, unresolved_rows, ambiguous_rows
        )
        VALUES ('digest-import', 'holdings.csv', 'generic', '2026-09-02T10:00:00+00:00',
            'v1', 'CONFIRMED', 1, 1, 0, 0, 0)
        """
    )
    conn.execute(
        """
        INSERT INTO portfolio_holdings (
            holding_id, instrument_id, quantity, avg_price, imported_at, updated_at,
            source_import_id, source_row_id
        )
        VALUES ('hold-1', ?, 10, '100', '2026-09-02T10:00:00+00:00',
            '2026-09-02T10:00:00+00:00', 'digest-import', '1')
        """,
        (instrument_id,),
    )
    conn.commit()


def test_remap_portfolio_holding_instrument_id(tmp_path: Path) -> None:
    repo = SqliteRepository(tmp_path / "athena.db")
    repo.initialize()
    _seed_holding(repo, "NSE:HFCL")
    remapped = repo.remap_portfolio_holding_instrument_id(
        from_instrument_id="NSE:HFCL",
        to_instrument_id="BSE:HFCL",
        updated_at=NOW,
        reason="NSE catalog miss; resolved on BSE",
    )
    assert remapped.instrument_id == "BSE:HFCL"
    assert remapped.quantity == 10
    assert repo.get_portfolio_holding("NSE:HFCL") is None
    assert remapped.provenance["exchange_remaps"][0]["to_instrument_id"] == "BSE:HFCL"
    repo.close()


def test_remap_portfolio_holding_rejects_conflict(tmp_path: Path) -> None:
    repo = SqliteRepository(tmp_path / "athena.db")
    repo.initialize()
    _seed_holding(repo, "NSE:HFCL")
    conn = repo._conn  # type: ignore[attr-defined]
    conn.execute(
        """
        INSERT INTO portfolio_holdings (
            holding_id, instrument_id, quantity, avg_price, imported_at, updated_at,
            source_import_id, source_row_id
        )
        VALUES ('hold-2', 'BSE:HFCL', 1, '10', '2026-09-02T10:00:00+00:00',
            '2026-09-02T10:00:00+00:00', 'digest-import', '2')
        """
    )
    conn.commit()
    with pytest.raises(RepositoryError, match="HOLDING_ALREADY_EXISTS"):
        repo.remap_portfolio_holding_instrument_id(
            from_instrument_id="NSE:HFCL",
            to_instrument_id="BSE:HFCL",
            updated_at=NOW,
            reason="conflict",
        )
    repo.close()


def test_validation_runner_skips_nse_miss_and_remaps_bse_hit(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    repo = SqliteRepository(tmp_path / "athena.db")
    repo.initialize()
    _seed_holding(repo, "NSE:HFCL")
    calls: list[tuple[tuple[str, ...], str | None]] = []

    def fake_validate(
        repo_arg,
        config_dir,
        *,
        symbols,
        as_of,
        repo_root=None,
        exchange=None,
        require_all_resolved=True,
    ):
        calls.append((tuple(symbols), exchange))
        skipped = ("HFCL",) if exchange != "BSE" else ()
        return SymbolValidateResult(
            run_id="nse-run" if exchange != "BSE" else "bse-run",
            status="SUCCESS",
            symbols=tuple(symbols),
            eligible=0,
            excluded=0,
            decisions=0,
            qualified=0,
            skipped_symbols=skipped,
        )

    def fake_resolve(config_dir, symbols, *, repo_root=None, exchange=None):
        if exchange == "BSE":
            return object(), {"HFCL": "BSE:HFCL"}, []
        return object(), {}, [str(symbol).upper() for symbol in symbols]

    monkeypatch.setattr("athena.ops.symbol_validate.validate_symbols", fake_validate)
    monkeypatch.setattr("athena.ops.symbol_validate.resolve_against_catalog", fake_resolve)

    service = MyPortfolioService(repo, config_dir=tmp_path, repo_root=None)
    run = service._validation_runner()
    assert run is not None
    run_id = run(["HFCL"], NOW)
    assert run_id == "bse-run"
    assert calls == [(("HFCL",), None), (("HFCL",), "BSE")]
    assert repo.get_portfolio_holding("BSE:HFCL") is not None
    assert repo.get_portfolio_holding("NSE:HFCL") is None
    repo.close()
