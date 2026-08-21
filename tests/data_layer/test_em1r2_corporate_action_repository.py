"""EM-1r2 atomic corporate-action persistence tests."""

from __future__ import annotations

from datetime import date
from pathlib import Path

import pytest

from athena.data.store import SqliteRepository
from athena.domain.market import CorporateAction, Instrument
from athena.errors import RepositoryError


@pytest.fixture()
def repo(tmp_path: Path):
    repository = SqliteRepository(tmp_path / "athena.db")
    repository.initialize()
    repository.upsert_instrument(
        Instrument(instrument_id="nse:AAA", symbol="AAA", exchange="NSE", series="EQ")
    )
    yield repository
    repository.close()


def _action(action_id: str, *, action_type: str = "BONUS") -> CorporateAction:
    return CorporateAction(
        action_id=action_id,
        instrument_id="nse:AAA",
        action_type=action_type,
        ex_date=date(2024, 6, 3),
        details={"official_record_id": action_id},
    )


def test_batch_insert_is_atomic_and_exact_replay_is_idempotent(repo) -> None:
    actions = (_action("ca-1"), _action("ca-2", action_type="MERGER"))

    assert repo.add_corporate_actions(actions) == 2
    assert repo.add_corporate_actions(tuple(reversed(actions))) == 0
    assert repo.get_corporate_actions("nse:AAA") == list(actions)


def test_conflicting_ids_within_batch_fail_before_write(repo) -> None:
    with pytest.raises(RepositoryError, match="conflict within batch"):
        repo.add_corporate_actions((_action("ca-1"), _action("ca-1", action_type="SPLIT")))

    assert repo.get_corporate_actions("nse:AAA") == []


def test_conflicting_replay_does_not_mutate_existing_evidence(repo) -> None:
    original = _action("ca-1")
    repo.add_corporate_actions((original,))

    with pytest.raises(RepositoryError, match="replay conflict"):
        repo.add_corporate_actions((_action("ca-1", action_type="SPLIT"),))

    assert repo.get_corporate_actions("nse:AAA") == [original]
