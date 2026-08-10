"""R2: decision / trace / journal persistence and SQLite briefing source."""

from __future__ import annotations

from dataclasses import replace
from datetime import datetime, timedelta
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
    TradeOutcome,
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
    def test_schema_version_is_current(self, tmp_path):
        repo = SqliteRepository(tmp_path / "a.db")
        repo.initialize()
        assert SCHEMA_VERSION == 12
        assert repo.verify_integrity().schema_version_ok
        assert "decisions" in repo.record_counts()
        assert "owner_positions" in repo.record_counts()
        assert "owner_candidates" in repo.record_counts()
        assert "saved_symbols" in repo.record_counts()
        assert "ops_meta" in repo.record_counts()
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

    def test_latest_decisions_by_instrument_is_deterministic(self, tmp_path):
        repo = SqliteRepository(tmp_path / "a.db")
        repo.initialize()
        base, _ = _watch("d-base")
        tied = replace(base, decision_id="d-tied", decision_type=DecisionType.NO_TRADE)
        later = replace(
            base,
            decision_id="d-later",
            ts=AS_OF + timedelta(minutes=1),
            decision_type=DecisionType.WATCH,
        )
        other = replace(base, decision_id="d-other", instrument_id="SYN-BBB")
        for decision in (base, tied, later, other):
            repo.save_decision(decision)

        latest = repo.list_latest_decisions_by_instrument()

        assert [(item.instrument_id, item.decision_id) for item in latest] == [
            ("SYN-AAA", "d-later"),
            ("SYN-BBB", "d-other"),
        ]
        repo.close()

        tie_repo = SqliteRepository(tmp_path / "tie.db")
        tie_repo.initialize()
        tie_repo.save_decision(base)
        tie_repo.save_decision(tied)
        assert tie_repo.list_latest_decisions_by_instrument()[0].decision_id == "d-tied"
        tie_repo.close()

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
        assert repo.get_journal_entry(decision.decision_id) == entry
        assert repo.get_journal_entry("no-such-decision") is None
        repo.close()

    def test_outcome_requires_decision(self, tmp_path):
        repo = SqliteRepository(tmp_path / "a.db")
        repo.initialize()
        outcome = TradeOutcome(
            outcome_id="o1", decision_ref="missing",
            entry_price=Decimal("100"), exit_price=Decimal("104"), quantity=10,
            pnl=Decimal("40"), holding_seconds=600, adherence={}, closed_ts=AS_OF,
        )
        with pytest.raises(RepositoryError):
            repo.save_trade_outcome(outcome)
        repo.close()

    def test_outcome_round_trip(self, tmp_path):
        repo = SqliteRepository(tmp_path / "a.db")
        repo.initialize()
        decision, _ = _watch()
        repo.save_decision(decision)
        outcome = TradeOutcome(
            outcome_id="o1", decision_ref=decision.decision_id,
            entry_price=Decimal("100.50"), exit_price=Decimal("104.00"), quantity=10,
            pnl=Decimal("35.00"), holding_seconds=1800,
            adherence={"entered_within_zone": True, "hit_target": True, "hit_stop": False},
            closed_ts=AS_OF,
        )
        repo.save_trade_outcome(outcome)
        assert repo.get_trade_outcome(decision.decision_id) == outcome
        assert repo.get_trade_outcome("no-such-decision") is None
        rows = repo.list_trade_outcomes()
        assert len(rows) == 1
        assert rows[0] == outcome
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
