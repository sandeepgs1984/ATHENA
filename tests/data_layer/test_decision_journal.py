"""R2: decision / trace / journal persistence and SQLite briefing source."""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from zoneinfo import ZoneInfo

import pytest

from athena import BLUEPRINT_VERSION, __version__
from athena.config.models import NotificationsConfig
from athena.data.store import SCHEMA_VERSION, SqliteRepository
from athena.domain.decision import (
    Decision,
    DecisionJournalEntry,
    DecisionTrace,
    TraceStage,
    TradePlan,
)
from athena.domain.enums import DecisionType, Direction, RunStatus, RunTrigger, UserAction
from athena.domain.run import RunRecord
from athena.errors import RepositoryError
from athena.notifications import BriefingDispatcher, BriefingStatus, SqliteDecisionSummarySource

IST = ZoneInfo("Asia/Kolkata")
AS_OF = datetime(2026, 2, 13, 15, 25, tzinfo=IST)


def _watch(decision_id: str = "d-watch-1") -> tuple[Decision, DecisionTrace]:
    decision = Decision(
        decision_id=decision_id,
        ts=AS_OF,
        run_id="run-1",
        cycle_id="c-1",
        decision_type=DecisionType.WATCH,
        explanation="setup forming on SYN-AAA",
        instrument_id="SYN-AAA",
        direction=Direction.NONE,
    )
    trace = DecisionTrace(
        decision_ref=decision_id,
        stages=(TraceStage("decision", (decision_id,), "watch issued"),),
    )
    return decision, trace


def _run_record() -> RunRecord:
    return RunRecord(
        run_id="run-1",
        cycle_id="c-1",
        trigger=RunTrigger.REFRESH,
        started_ts=AS_OF,
        status=RunStatus.COMPLETED,
        software_version=__version__,
        blueprint_version=BLUEPRINT_VERSION,
        strategy_profile="intraday-momentum",
        strategy_profile_version="1",
        indicator_versions={},
        config_snapshot_id="cfg",
        finished_ts=AS_OF,
    )


class TestDecisionPersistence:
    def test_schema_version_is_3(self, tmp_path):
        repo = SqliteRepository(tmp_path / "a.db")
        repo.initialize()
        assert SCHEMA_VERSION == 3
        assert repo.verify_integrity().schema_version_ok
        assert "decisions" in repo.record_counts()
        repo.close()

    def test_round_trip_decision_and_trace(self, tmp_path):
        repo = SqliteRepository(tmp_path / "a.db")
        repo.initialize()
        decision, trace = _watch()
        repo.save_decision(decision, trace=trace)
        loaded = repo.get_decision(decision.decision_id)
        assert loaded == decision
        assert repo.get_trace(decision.decision_id) == trace
        repo.close()

    def test_trade_plan_round_trip(self, tmp_path):
        repo = SqliteRepository(tmp_path / "a.db")
        repo.initialize()
        plan = TradePlan(
            entry_low=Decimal("100"), entry_high=Decimal("101"),
            stop_loss=Decimal("98"), targets=(Decimal("105"),),
            position_size=1, risk_amount=Decimal("200"), risk_reward=Decimal("2.5"),
            valid_from=AS_OF, valid_until=AS_OF.replace(hour=16),
        )
        decision = Decision(
            decision_id="d-trade-1", ts=AS_OF, run_id="r", cycle_id="c",
            decision_type=DecisionType.TRADE, explanation="trade plan advisory only",
            instrument_id="SYN-AAA", direction=Direction.LONG, trade_plan=plan,
        )
        repo.save_decision(decision)
        assert repo.get_decision("d-trade-1") == decision
        repo.close()

    def test_journal_requires_decision(self, tmp_path):
        repo = SqliteRepository(tmp_path / "a.db")
        repo.initialize()
        entry = DecisionJournalEntry("missing", UserAction.ACCEPTED, AS_OF, notes="n")
        with pytest.raises(RepositoryError):
            repo.save_journal_entry(entry)
        repo.close()

    def test_journal_round_trip(self, tmp_path):
        repo = SqliteRepository(tmp_path / "a.db")
        repo.initialize()
        decision, _ = _watch()
        repo.save_decision(decision)
        entry = DecisionJournalEntry(decision.decision_id, UserAction.ACCEPTED, AS_OF, "ok")
        repo.save_journal_entry(entry)
        rows = repo.list_journal()
        assert len(rows) == 1
        assert rows[0] == entry
        repo.close()


class TestSqliteBriefingSource:
    def test_briefing_ok_with_persisted_decision(self, tmp_path):
        repo = SqliteRepository(tmp_path / "a.db")
        repo.initialize()
        repo.save_run(_run_record(), detail={"phase": "finished", "ingestion": {}})
        decision, trace = _watch()
        repo.save_decision(decision, trace=trace)

        out = tmp_path / "briefings"
        cfg = NotificationsConfig()
        # Force file output into temp dir via dry_run FileNotifier path in dispatcher
        from athena.config.models import FileNotifierConfig, NotificationChannelsConfig
        cfg = NotificationsConfig(
            channels=NotificationChannelsConfig(
                file=FileNotifierConfig(enabled=True, output_dir=str(out)),
            ),
        )
        dispatcher = BriefingDispatcher(
            repo, cfg, tzinfo=IST, repo_root=tmp_path,
            decision_source=SqliteDecisionSummarySource(repo, tzinfo=IST),
        )
        result = dispatcher.dispatch(as_of=AS_OF, dry_run=True)
        assert result.briefing.status is BriefingStatus.OK
        assert len(result.briefing.decisions) == 1
        assert result.briefing.decisions[0].trace_stage_count == 1
        assert "no_decision_summaries" not in result.briefing.degradation_reasons
        repo.close()
