"""Shared entrypoint: seed owner_candidates from configured constituent source."""

from __future__ import annotations

from datetime import datetime
from pathlib import Path

from athena.data.store.repository import SqliteRepository
from athena.ops.constituents import (
    CandidateSeedResult,
    CandidateSeeder,
    load_candidate_seed_config,
)
from athena.ops.owner_candidates import SqliteCandidateStore


def seed_owner_candidates(
    repo: SqliteRepository,
    config_dir: Path,
    *,
    as_of: datetime,
    repo_root: Path | None = None,
) -> CandidateSeedResult:
    """Merge-unique seed into SQLite owner_candidates (once per day when configured)."""
    cfg = load_candidate_seed_config(config_dir)
    store = SqliteCandidateStore(repo)
    seeder = CandidateSeeder(
        store,
        cfg,
        repo_root=repo_root,
        meta_get=repo.get_ops_meta,
        meta_set=lambda k, v: repo.set_ops_meta(k, v, updated_ts=as_of),
        instrument_repo=repo,
    )
    return seeder.run(as_of=as_of)
