"""Tests for owner-triggered full-universe validation (ADR-007 / MI-5)."""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

import pytest

from athena.data.store.repository import SqliteRepository
from athena.ops.full_validation import CycleBusyError, start_full_validation
from athena.ops.owner_candidates import SqliteCandidateStore
from athena.ops.serve_runtime import (
    CycleRunnerLock,
    FullValidationProgress,
    ServeRuntime,
    set_serve_runtime,
)


@pytest.fixture()
def runtime() -> ServeRuntime:
    rt = ServeRuntime(cycles_enabled=False, host="127.0.0.1", port=8000)
    set_serve_runtime(rt)
    yield rt
    set_serve_runtime(None)


def test_start_refuses_without_serve_runtime(tmp_path: Path) -> None:
    set_serve_runtime(None)
    with pytest.raises(CycleBusyError, match="athena serve"):
        start_full_validation(
            repo_root=tmp_path,
            config_dir=tmp_path / "config",
            db_path=tmp_path / "t.db",
        )


def test_start_refuses_when_lock_held(tmp_path: Path, runtime: ServeRuntime) -> None:
    db = tmp_path / "t.db"
    repo = SqliteRepository(db)
    repo.initialize()
    SqliteCandidateStore(repo).upsert_candidate(symbol="INFY")
    repo.close()

    lock_path = tmp_path / "cycle.lock"
    holder = CycleRunnerLock(lock_path)
    assert holder.acquire()
    try:
        with pytest.raises(CycleBusyError, match="cycle lock busy"):
            start_full_validation(
                repo_root=tmp_path,
                config_dir=tmp_path / "config",
                db_path=db,
                lock_path=lock_path,
            )
    finally:
        holder.release()


def test_start_refuses_when_already_running(tmp_path: Path, runtime: ServeRuntime) -> None:
    runtime.set_full_validation(
        FullValidationProgress(
            state="running",
            stage="ingesting",
            symbols_total=10,
            started_at=datetime.now(tz=timezone.utc),
        )
    )
    with pytest.raises(CycleBusyError, match="already running"):
        start_full_validation(
            repo_root=tmp_path,
            config_dir=tmp_path / "config",
            db_path=tmp_path / "t.db",
            lock_path=tmp_path / "cycle.lock",
        )


class TestUnresolvedCandidatesAreReportedNotSilentlyDropped:
    """A candidate that stops resolving must be skipped **and named**.

    Skipping is correct — one delisted or renamed ticker must never stop the
    cycle. Skipping silently is not. `E2E NETWORKS` moved to the BE series
    (becoming `E2E-BE`), stopped resolving, and went stale for four sessions
    with nothing reported, because this path dropped it with a bare
    comprehension while the CLI reported its own misses.
    """

    def _engine_for(self, tmp_path: Path, catalog: list[str], candidates: list[str]):
        import shutil
        from decimal import Decimal
        from zoneinfo import ZoneInfo

        from athena.config.loader import load_config
        from athena.domain.market import Instrument
        from athena.ops import full_validation as fv

        config_dir = tmp_path / "config"
        shutil.copytree(Path(__file__).resolve().parents[2] / "config", config_dir)

        repo = SqliteRepository(tmp_path / "t.db")
        repo.initialize()
        store = SqliteCandidateStore(repo)
        for symbol in candidates:
            store.upsert_candidate(symbol=symbol)

        class FakeProvider:
            def instruments(self):
                return [
                    Instrument(
                        instrument_id=f"NSE:{s}", symbol=s, exchange="NSE", series="EQ",
                        name=s, lot_size=1, tick_size=Decimal("0.05"), status="ACTIVE",
                    )
                    for s in catalog
                ]

        cfg = load_config(config_dir)
        tz = ZoneInfo(cfg.market.timezone)
        original = fv.build_market_data_provider
        fv.build_market_data_provider = lambda *a, **k: FakeProvider()
        try:
            return fv._build_scoped_ingest_engine(
                config_dir, cfg, repo, tz, repo_root=tmp_path
            ), repo
        finally:
            fv.build_market_data_provider = original

    def test_a_missing_candidate_is_named_in_the_detail(self, tmp_path: Path):
        (_, detail), repo = self._engine_for(
            tmp_path, catalog=["GOOD1", "GOOD2"], candidates=["GOOD1", "GOOD2", "E2E"]
        )
        try:
            assert detail is not None, "a skipped candidate must be reported"
            assert "E2E" in detail
            assert "1 candidate(s) skipped" in detail
        finally:
            repo.close()

    def test_the_batch_still_proceeds_with_the_good_symbols(self, tmp_path: Path):
        """The owner's requirement: one bad symbol never stops the rest."""
        (engine, _), repo = self._engine_for(
            tmp_path, catalog=["GOOD1", "GOOD2"], candidates=["GOOD1", "E2E", "GOOD2"]
        )
        try:
            assert sorted(engine._config.instrument_ids) == ["NSE:GOOD1", "NSE:GOOD2"]
        finally:
            repo.close()

    def test_no_detail_when_every_candidate_resolves(self, tmp_path: Path):
        (_, detail), repo = self._engine_for(
            tmp_path, catalog=["GOOD1"], candidates=["GOOD1"]
        )
        try:
            assert detail is None, "a clean run must not invent a warning"
        finally:
            repo.close()
