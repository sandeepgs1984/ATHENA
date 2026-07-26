"""Owner-entered fill ledger API + SQLite portfolio provider tests."""

from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from tests.api.v1.test_core_apis import get_auth_headers

from athena.api.dependencies import get_portfolio_provider
from athena.api.security.models import Role
from athena.api.v1.providers.sqlite_providers import (
    SqliteDecisionProvider,
    SqlitePipelineRunProvider,
    SqlitePortfolioProvider,
)
from athena.data.store.repository import SqliteRepository
from athena.domain.decision import (
    Decision,
    DecisionJournalEntry,
    DecisionTrace,
    TraceStage,
    TradeOutcome,
)
from athena.domain.enums import DecisionType, Direction, RunStatus, RunTrigger, UserAction
from athena.domain.run import RunRecord


@pytest.fixture(autouse=True)
def reset_portfolio() -> None:
    p = get_portfolio_provider()
    p.portfolio = None  # type: ignore[attr-defined]
    p.starting_cash = Decimal("100000.00")  # type: ignore[attr-defined]


class TestOwnerPositionAPI:
    def test_open_and_close_position(self, client: TestClient) -> None:
        headers = get_auth_headers(client, Role.OPERATOR)
        open_resp = client.post(
            "/api/v1/portfolio/positions",
            headers=headers,
            json={
                "instrument_id": "infy",
                "quantity": 10,
                "avg_price": "1500.00",
                "broker": "kite",
                "sector": "IT",
            },
        )
        assert open_resp.status_code == 201
        body = open_resp.json()["data"]
        assert body["summary"]["cash"] == "85000.00"
        assert len(body["positions"]) == 1
        assert body["positions"][0]["instrument_id"] == "INFY"
        pos_id = body["positions"][0]["position_id"]

        close_resp = client.post(
            f"/api/v1/portfolio/positions/{pos_id}/close",
            headers=headers,
            json={"exit_price": "1550.00"},
        )
        assert close_resp.status_code == 200
        closed = close_resp.json()["data"]
        assert closed["summary"]["cash"] == "100500.00"
        assert closed["positions"][0]["closed_ts"] is not None
        assert closed["positions"][0]["meta"]["exit_price"] == "1550.00"

    def test_open_requires_execute(self, client: TestClient) -> None:
        headers = get_auth_headers(client, Role.READONLY)
        resp = client.post(
            "/api/v1/portfolio/positions",
            headers=headers,
            json={"instrument_id": "INFY", "quantity": 1, "avg_price": "1"},
        )
        assert resp.status_code == 403

    def test_reset_open_keeps_closed(self, client: TestClient) -> None:
        headers = get_auth_headers(client, Role.ADMIN)
        open_a = client.post(
            "/api/v1/portfolio/positions",
            headers=headers,
            json={"instrument_id": "INFY", "quantity": 10, "avg_price": "100"},
        ).json()["data"]
        closed_id = open_a["positions"][0]["position_id"]
        client.post(
            f"/api/v1/portfolio/positions/{closed_id}/close",
            headers=headers,
            json={"exit_price": "110"},
        )
        client.post(
            "/api/v1/portfolio/positions",
            headers=headers,
            json={"instrument_id": "TCS", "quantity": 5, "avg_price": "100"},
        )
        bad = client.post(
            "/api/v1/portfolio/positions/reset",
            headers=headers,
            json={"confirmation": "YES", "scope": "open"},
        )
        assert bad.status_code == 400

        ok = client.post(
            "/api/v1/portfolio/positions/reset",
            headers=headers,
            json={"confirmation": "CONFIRM", "scope": "open"},
        )
        assert ok.status_code == 200
        data = ok.json()["data"]
        assert data["scope"] == "open"
        assert data["deleted_count"] == 1
        remaining = data["portfolio"]["positions"]
        assert len(remaining) == 1
        assert remaining[0]["instrument_id"] == "INFY"
        assert remaining[0]["closed_ts"] is not None

    def test_reset_all_restores_starting_cash(self, client: TestClient) -> None:
        headers = get_auth_headers(client, Role.ADMIN)
        client.post(
            "/api/v1/portfolio/positions",
            headers=headers,
            json={"instrument_id": "INFY", "quantity": 10, "avg_price": "1000"},
        )
        resp = client.post(
            "/api/v1/portfolio/positions/reset",
            headers=headers,
            json={"confirmation": "CONFIRM", "scope": "all"},
        )
        assert resp.status_code == 200
        data = resp.json()["data"]
        assert data["deleted_count"] == 1
        assert data["portfolio"]["summary"]["cash"] == "100000.00"
        assert data["portfolio"]["positions"] == []

    def test_reset_requires_admin(self, client: TestClient) -> None:
        headers = get_auth_headers(client, Role.OPERATOR)
        resp = client.post(
            "/api/v1/portfolio/positions/reset",
            headers=headers,
            json={"confirmation": "CONFIRM", "scope": "all"},
        )
        assert resp.status_code == 403


class TestSqliteProviders:
    def test_decision_provider_round_trip(self, tmp_path: Path) -> None:
        repo = SqliteRepository(tmp_path / "p.db")
        repo.initialize()
        now = datetime(2026, 7, 23, 10, 0, tzinfo=timezone.utc)
        decision = Decision(
            decision_id="dec-live-1",
            ts=now,
            run_id="run-1",
            cycle_id="cycle-1",
            instrument_id="INFY",
            direction=Direction.LONG,
            decision_type=DecisionType.WATCH,
            explanation="live",
        )
        trace = DecisionTrace(
            decision_ref="dec-live-1",
            stages=(TraceStage("decision", ("dec-live-1",), "composed"),),
        )
        repo.save_decision(decision, trace=trace)
        provider = SqliteDecisionProvider(repo)
        assert provider.get_decision("dec-live-1") is not None
        assert provider.get_trace("dec-live-1") is not None
        repo.close()

    def test_reset_decisions_data_respects_foreign_keys(self, tmp_path: Path) -> None:
        """Regression test: delete_decisions_data's first implementation
        deleted the `decisions` parent row before its child rows
        (decision_traces/decision_journal/trade_outcomes, each
        `REFERENCES decisions(decision_id)`), which raised a live
        `FOREIGN KEY constraint failed` against the real SQLite database
        (foreign_keys=ON) even though it passed against the in-memory
        provider used elsewhere in the test suite, since that provider has
        no FK enforcement to violate. Uses a real SqliteRepository
        specifically to exercise that constraint."""
        repo = SqliteRepository(tmp_path / "p.db")
        repo.initialize()
        assert repo.foreign_keys_enabled
        now = datetime(2026, 7, 23, 10, 0, tzinfo=timezone.utc)
        decision = Decision(
            decision_id="dec-reset-1", ts=now, run_id="run-1", cycle_id="cycle-1",
            instrument_id="INFY", direction=Direction.LONG, decision_type=DecisionType.WATCH,
            explanation="live",
        )
        trace = DecisionTrace(
            decision_ref="dec-reset-1",
            stages=(TraceStage("decision", ("dec-reset-1",), "composed"),),
        )
        repo.save_decision(decision, trace=trace)
        repo.save_journal_entry(
            DecisionJournalEntry(
                decision_ref="dec-reset-1", user_action=UserAction.ACCEPTED,
                action_ts=now, notes="",
            )
        )
        repo.save_trade_outcome(
            TradeOutcome(
                outcome_id="out-1", decision_ref="dec-reset-1",
                entry_price=Decimal("100"), exit_price=Decimal("110"), quantity=10,
                pnl=Decimal("100"), holding_seconds=60, adherence={}, closed_ts=now,
            )
        )

        counts = repo.delete_decisions_data()
        assert counts["decisions"] == 1
        assert counts["decision_traces"] == 1
        assert counts["decision_journal"] == 1
        assert counts["trade_outcomes"] == 1
        assert repo.get_decision("dec-reset-1") is None
        assert repo.get_trace("dec-reset-1") is None
        assert repo.get_journal_entry("dec-reset-1") is None
        assert repo.get_trade_outcome("dec-reset-1") is None
        repo.close()

    def test_portfolio_cash_from_starting(self, tmp_path: Path) -> None:
        repo = SqliteRepository(tmp_path / "p.db")
        repo.initialize()
        provider = SqlitePortfolioProvider(repo, starting_cash=Decimal("100000"))
        opened = provider.open_position(
            instrument_id="INFY",
            quantity=10,
            avg_price=Decimal("1000"),
            broker="kite",
        )
        portfolio = provider.get_portfolio()
        assert portfolio.cash == Decimal("90000")
        assert len(portfolio.positions) == 1
        provider.close_position(opened.position_id, exit_price=Decimal("1100"))
        after = provider.get_portfolio()
        assert after.cash == Decimal("101000")
        repo.close()

    def test_pipeline_provider_uses_config_symbols_fallback(
        self, tmp_path: Path
    ) -> None:
        repo = SqliteRepository(tmp_path / "p.db")
        repo.initialize()
        now = datetime(2026, 7, 23, 10, 0, tzinfo=timezone.utc)
        run = RunRecord(
            run_id="run-x",
            cycle_id="c1",
            trigger=RunTrigger.REFRESH,
            started_ts=now,
            status=RunStatus.COMPLETED,
            software_version="0",
            blueprint_version="0",
            strategy_profile="default",
            strategy_profile_version="1",
            indicator_versions={},
            config_snapshot_id="cfg",
            finished_ts=now,
        )
        repo.save_run(run, detail={"phase": "finished", "pipeline": {"mode": "ingest_only"}})

        cfg = tmp_path / "config"
        (cfg / "providers").mkdir(parents=True)
        (cfg / "providers" / "kite.json").write_text(
            '{"symbols": ["NSE:INFY", "TCS"]}', encoding="utf-8"
        )
        provider = SqlitePipelineRunProvider(repo, config_dir=cfg)
        result = provider.get_run("run-x")
        assert result is not None
        data = result.final_context.data
        # Kite symbols are reference-only — never shown as Eligible without UniverseEngine
        assert data["universe_members"] == {}
        assert data["universe_source"] == "no_validation_run"
        assert data["configured_ingest_symbols"] == ["INFY", "TCS"]
        repo.close()
