"""Nifty 500 candidate seed tests (merge-unique, once-per-day)."""

from __future__ import annotations

from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

import pytest

from athena.data.store.repository import SqliteRepository
from athena.ops.constituents import (
    CandidateSeedConfig,
    CandidateSeeder,
    parse_nifty_constituent_csv,
)
from athena.ops.owner_candidates import InMemoryCandidateStore, SqliteCandidateStore

IST = ZoneInfo("Asia/Kolkata")
AS_OF = datetime(2026, 7, 24, 8, 30, tzinfo=IST)
SAMPLE = (
    Path(__file__).resolve().parents[1]
    / "data"
    / "constituents"
    / "ind_nifty500list_sample.csv"
)


class TestParseConstituents:
    def test_parse_sample_csv(self) -> None:
        text = SAMPLE.read_text(encoding="utf-8")
        symbols = parse_nifty_constituent_csv(text)
        assert symbols == ("ALPHA", "BETA", "GAMMA", "DELTA")


class TestCandidateSeeder:
    def test_merge_unique_and_once_per_day(self, tmp_path: Path) -> None:
        store = InMemoryCandidateStore()
        store.upsert_candidate(symbol="BETA", notes="manual")
        meta: dict[str, str] = {}

        cfg = CandidateSeedConfig(
            source="NIFTY500",
            merge_unique=True,
            once_per_day=True,
            local_file=str(SAMPLE),
        )
        seeder = CandidateSeeder(
            store,
            cfg,
            repo_root=Path("/"),
            meta_get=meta.get,
            meta_set=meta.__setitem__,
        )
        first = seeder.run(as_of=AS_OF)
        assert first.status == "seeded"
        assert first.fetched == 4
        assert first.added == 3  # ALPHA, GAMMA, DELTA (BETA already present)
        assert first.already_present == 1

        symbols = {c.symbol for c in store.list_candidates()}
        assert symbols == {"ALPHA", "BETA", "GAMMA", "DELTA"}
        beta = next(c for c in store.list_candidates() if c.symbol == "BETA")
        assert beta.notes == "manual"  # not overwritten

        second = seeder.run(as_of=AS_OF)
        assert second.status == "skipped_already_today"
        assert second.added == 0

    def test_sqlite_meta_round_trip(self, tmp_path: Path) -> None:
        repo = SqliteRepository(tmp_path / "s.db")
        repo.initialize()
        store = SqliteCandidateStore(repo)
        cfg = CandidateSeedConfig(
            source="NIFTY500",
            local_file=str(SAMPLE),
        )
        seeder = CandidateSeeder(
            store,
            cfg,
            repo_root=Path("/"),
            meta_get=repo.get_ops_meta,
            meta_set=lambda k, v: repo.set_ops_meta(k, v, updated_ts=AS_OF),
        )
        result = seeder.run(as_of=AS_OF)
        assert result.status == "seeded"
        assert repo.get_ops_meta("candidate_seed:NIFTY500:last_date") == "2026-07-24"
        assert len(store.list_candidates()) == 4
        repo.close()

    def test_disabled(self) -> None:
        store = InMemoryCandidateStore()
        seeder = CandidateSeeder(store, CandidateSeedConfig(source="none"))
        result = seeder.run(as_of=AS_OF)
        assert result.status == "disabled"
        assert store.list_candidates() == []
