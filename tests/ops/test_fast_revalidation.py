"""Milestone B (2026-08-04): fast decision-list-only revalidation tier —
current_decision_list_instrument_ids is the pure, easily-testable piece
(the scoped-ingest-then-score mechanics themselves mirror
symbol_validate.validate_symbols exactly, which has no dedicated
end-to-end unit test in this codebase either — it requires a live/mocked
Kite connection this suite deliberately doesn't set up)."""

from __future__ import annotations

from datetime import datetime
from zoneinfo import ZoneInfo

from athena.data.store.repository import SqliteRepository
from athena.domain.decision import Decision
from athena.domain.enums import DecisionType, Direction
from athena.ops.fast_revalidation import current_decision_list_instrument_ids

IST = ZoneInfo("Asia/Kolkata")


def _decision(decision_id: str, instrument_id: str | None, ts: datetime) -> Decision:
    return Decision(
        decision_id=decision_id,
        ts=ts,
        run_id="run-1",
        cycle_id="cycle-1",
        decision_type=DecisionType.WATCH,
        explanation="test decision",
        instrument_id=instrument_id,
        direction=Direction.NONE,
    )


class TestCurrentDecisionListInstrumentIds:
    def test_empty_when_no_decisions(self, tmp_path):
        repo = SqliteRepository(tmp_path / "a.db")
        repo.initialize()
        assert current_decision_list_instrument_ids(repo, max_symbols=100) == []
        repo.close()

    def test_returns_one_instrument_per_decision(self, tmp_path):
        repo = SqliteRepository(tmp_path / "b.db")
        repo.initialize()
        repo.save_decision(_decision("d1", "NSE:RELIANCE", datetime(2026, 8, 4, 10, 0, tzinfo=IST)))
        repo.save_decision(_decision("d2", "NSE:INFY", datetime(2026, 8, 4, 10, 5, tzinfo=IST)))
        ids = current_decision_list_instrument_ids(repo, max_symbols=100)
        assert set(ids) == {"NSE:RELIANCE", "NSE:INFY"}
        repo.close()

    def test_newest_decided_first(self, tmp_path):
        repo = SqliteRepository(tmp_path / "c.db")
        repo.initialize()
        repo.save_decision(_decision("d1", "NSE:OLD", datetime(2026, 8, 4, 9, 0, tzinfo=IST)))
        repo.save_decision(_decision("d2", "NSE:NEW", datetime(2026, 8, 4, 14, 0, tzinfo=IST)))
        repo.save_decision(_decision("d3", "NSE:MID", datetime(2026, 8, 4, 11, 0, tzinfo=IST)))
        ids = current_decision_list_instrument_ids(repo, max_symbols=100)
        assert ids == ["NSE:NEW", "NSE:MID", "NSE:OLD"]
        repo.close()

    def test_caps_at_max_symbols(self, tmp_path):
        repo = SqliteRepository(tmp_path / "d.db")
        repo.initialize()
        for i in range(10):
            repo.save_decision(
                _decision(f"d{i}", f"NSE:SYM{i}", datetime(2026, 8, 4, 9, i, tzinfo=IST))
            )
        ids = current_decision_list_instrument_ids(repo, max_symbols=3)
        assert len(ids) == 3
        # Newest three (by ts) survive the cap.
        assert ids == ["NSE:SYM9", "NSE:SYM8", "NSE:SYM7"]
        repo.close()

    def test_excludes_decisions_with_no_instrument_id(self, tmp_path):
        repo = SqliteRepository(tmp_path / "e.db")
        repo.initialize()
        repo.save_decision(_decision("d1", None, datetime(2026, 8, 4, 10, 0, tzinfo=IST)))
        repo.save_decision(_decision("d2", "NSE:RELIANCE", datetime(2026, 8, 4, 10, 5, tzinfo=IST)))
        ids = current_decision_list_instrument_ids(repo, max_symbols=100)
        assert ids == ["NSE:RELIANCE"]
        repo.close()
