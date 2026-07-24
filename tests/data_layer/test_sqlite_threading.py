"""SqliteRepository must be safe for FastAPI multi-threaded request handlers."""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
from decimal import Decimal

from athena.data.store.repository import SqliteRepository
from athena.domain.decision import Decision
from athena.domain.enums import DecisionType, Direction


def test_repository_usable_from_worker_threads(tmp_path) -> None:
    """API opens the repo on the main thread; request workers must still read/write."""
    repo = SqliteRepository(tmp_path / "threaded.db")
    repo.initialize()

    now = datetime(2026, 7, 24, 8, 0, tzinfo=timezone.utc)

    def worker(i: int) -> str:
        decision_id = f"dec-thread-{i}"
        repo.save_decision(
            Decision(
                decision_id=decision_id,
                ts=now,
                run_id="run-1",
                cycle_id="cycle-1",
                instrument_id="INFY",
                direction=Direction.LONG,
                decision_type=DecisionType.WATCH,
                explanation=f"thread {i}",
            )
        )
        loaded = repo.get_decision(decision_id)
        assert loaded is not None
        repo.save_owner_position(
            position_id=f"pos-thread-{i}",
            instrument_id="INFY",
            opened_ts=now,
            quantity=1,
            avg_price=Decimal("100.00"),
            broker="kite",
        )
        assert repo.get_owner_position(f"pos-thread-{i}") is not None
        return decision_id

    with ThreadPoolExecutor(max_workers=8) as pool:
        futures = [pool.submit(worker, i) for i in range(24)]
        ids = [f.result() for f in as_completed(futures)]

    assert len(ids) == 24
    assert len(repo.list_decisions(limit=100)) >= 24
    assert len(repo.list_owner_positions(limit=100)) >= 24
    repo.close()
