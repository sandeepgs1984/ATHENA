"""PS-P2 My Portfolio import/reconciliation API tests."""

from __future__ import annotations

import time
from datetime import datetime, timezone
from decimal import Decimal
from pathlib import Path
from zoneinfo import ZoneInfo

import pytest
from fastapi.testclient import TestClient
from tests.api.v1.test_core_apis import get_auth_headers

from athena.api.app import create_app
from athena.api.config import APISettings
from athena.api.dependencies import get_my_portfolio_service
from athena.api.security.models import Role
from athena.api.v1.services import my_portfolio_service as my_portfolio_service_module
from athena.api.v1.services.my_portfolio_service import MyPortfolioService
from athena.data.store.repository import SqliteRepository
from athena.domain.decision import Decision, TradePlan
from athena.domain.enums import DecisionType, Direction, Timeframe
from athena.domain.market import Candle, Instrument
from athena.intraday.entry_qualification_models import (
    EntryEvidenceFinality,
    EntryQualification,
    EntryQualificationConfirmation,
    EntryQualificationReasonCode,
    EntryQualificationState,
)
from athena.portfolio.my_portfolio_contracts import SyncRunStatus
from athena.portfolio.sync import PortfolioSyncOrchestrator

NOW = datetime(2026, 9, 2, 10, 0, tzinfo=timezone.utc)
SEP1 = datetime(2026, 9, 1, 10, 0, tzinfo=timezone.utc)
SEP2 = datetime(2026, 9, 2, 10, 0, tzinfo=timezone.utc)
FRIDAY = datetime(2026, 7, 17, 15, 30, tzinfo=timezone.utc)


def _instrument(instrument_id: str, symbol: str, exchange: str = "NSE") -> Instrument:
    return Instrument(instrument_id=instrument_id, symbol=symbol, exchange=exchange, series="EQ")


def _candle(instrument_id: str, close: str, ts: datetime = NOW) -> Candle:
    price = Decimal(close)
    return Candle(
        instrument_id=instrument_id,
        timeframe=Timeframe.D1,
        ts_open=ts,
        open=price,
        high=price,
        low=price,
        close=price,
        volume=1000,
        source="test-d1",
    )


def _decision(
    *,
    decision_id: str = "dec-infy",
    instrument_id: str = "NSE:INFY",
    ts: datetime = NOW,
    target: str = "1700",
    entry_low: str = "1500",
    entry_high: str = "1510",
    stop_loss: str = "1450",
) -> Decision:
    return Decision(
        decision_id=decision_id,
        ts=ts,
        run_id=f"run-{decision_id}",
        cycle_id=f"cycle-{decision_id}",
        decision_type=DecisionType.TRADE,
        explanation="Persisted test decision",
        instrument_id=instrument_id,
        direction=Direction.LONG,
        trade_plan=TradePlan(
            entry_low=Decimal(entry_low),
            entry_high=Decimal(entry_high),
            stop_loss=Decimal(stop_loss),
            targets=(Decimal(target),),
            position_size=1,
            risk_amount=Decimal("50"),
            risk_reward=Decimal("4"),
            valid_from=ts,
            valid_until=datetime(2026, 9, 3, 10, 0, tzinfo=timezone.utc),
        ),
    )


def _entry_qualification(
    decision: Decision,
    *,
    as_of: datetime = SEP2,
    state: EntryQualificationState = EntryQualificationState.QUALIFIED,
) -> EntryQualification:
    assert decision.instrument_id is not None
    return EntryQualification(
        instrument_id=decision.instrument_id,
        session_date=as_of.date(),
        as_of=as_of,
        run_id=decision.run_id,
        cycle_id=decision.cycle_id,
        decision_id=decision.decision_id,
        decision_type=decision.decision_type,
        state=state,
        evidence_finality=EntryEvidenceFinality.NO_DECISIVE_PROVISIONAL_M5_DEPENDENCY,
        confirmation=EntryQualificationConfirmation.CONFIRMED_BY_POLICY,
        reason_codes=(EntryQualificationReasonCode.V0_READINESS_POLICY_SATISFIED,),
        evidence_refs=(),
        methodology_version="entry-qualification-v0",
        config_snapshot_id=None,
        explanation="Persisted coherent entry qualification.",
    )


@pytest.fixture()
def my_portfolio_client(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> TestClient:
    monkeypatch.setenv("ATHENA_DB_PATH", str(tmp_path / "athena.db"))
    app = create_app(APISettings())
    repo = app.state.sqlite_repo
    repo.upsert_instrument(_instrument("NSE:INFY", "INFY"))
    repo.upsert_instrument(_instrument("NSE:TCS", "TCS"))
    repo.upsert_instrument(_instrument("NSE:ABC", "ABC", exchange="NSE"))
    repo.upsert_instrument(_instrument("BSE:ABC", "ABC", exchange="BSE"))
    return TestClient(app, raise_server_exceptions=False)


def _preview(client: TestClient, csv_body: bytes, filename: str = "holdings.csv") -> dict:
    headers = get_auth_headers(client, Role.OPERATOR)
    response = client.post(
        "/api/v1/my-portfolio/imports",
        params={"filename": filename},
        headers=headers,
        content=csv_body,
    )
    assert response.status_code == 201
    return response.json()["data"]


def _confirm_infy_holding(client: TestClient) -> SqliteRepository:
    headers = get_auth_headers(client, Role.OPERATOR)
    preview = _preview(client, b"Symbol,Qty,Avg Price\nINFY,10,1500\n")
    response = client.post(
        f"/api/v1/my-portfolio/imports/{preview['import_id']}/confirm",
        headers=headers,
        json={"import_id": preview["import_id"], "confirmation": "CONFIRM"},
    )
    assert response.status_code == 200
    return client.app.state.sqlite_repo


def _confirm_holdings(client: TestClient, csv_body: bytes) -> SqliteRepository:
    headers = get_auth_headers(client, Role.OPERATOR)
    preview = _preview(client, csv_body)
    response = client.post(
        f"/api/v1/my-portfolio/imports/{preview['import_id']}/confirm",
        headers=headers,
        json={"import_id": preview["import_id"], "confirmation": "CONFIRM"},
    )
    assert response.status_code == 200
    return client.app.state.sqlite_repo


def _run_portfolio_sync(
    repo: SqliteRepository,
    *,
    expected_analysis_as_of: datetime | None = SEP2,
    validation_runner=None,
    force_ingestion: bool = False,
):
    orchestrator = PortfolioSyncOrchestrator(
        repo,
        validation_runner=validation_runner,
        expected_analysis_as_of=expected_analysis_as_of,
        market_timezone=ZoneInfo("UTC"),
        force_ingestion=force_ingestion,
    )
    repo.mark_interrupted_portfolio_sync_runs(interrupted_at=NOW)
    run = orchestrator.create_run()
    return orchestrator.run(str(run["sync_run_id"]))


def test_import_preview_persists_rows_and_does_not_mutate_holdings(my_portfolio_client: TestClient) -> None:
    data = _preview(
        my_portfolio_client,
        b"Symbol,Qty,Avg Price\nINFY,10,1500\nUNKNOWN,2,3\nABC,1,1\n",
    )

    assert data["status"] == "PREVIEWED"
    assert data["total_rows"] == 3
    assert data["accepted_rows"] == 1
    assert data["unresolved_rows"] == 1
    assert data["ambiguous_rows"] == 1
    assert data["rows"][0]["resolved_instrument_id"] == "NSE:INFY"

    headers = get_auth_headers(my_portfolio_client, Role.READONLY, username="reader")
    holdings = my_portfolio_client.get("/api/v1/my-portfolio/holdings", headers=headers)
    assert holdings.status_code == 200
    assert holdings.json()["data"] == []

    detail = my_portfolio_client.get(
        f"/api/v1/my-portfolio/imports/{data['import_id']}",
        headers=headers,
    )
    assert detail.status_code == 200
    assert detail.json()["data"]["rows"][1]["mapping_state"] == "UNRESOLVED"


def test_clean_import_confirm_applies_holdings_and_audit_idempotently(my_portfolio_client: TestClient) -> None:
    data = _preview(my_portfolio_client, b"Symbol,Qty,Avg Price\nINFY,10,1500\n")
    headers = get_auth_headers(my_portfolio_client, Role.OPERATOR)

    first = my_portfolio_client.post(
        f"/api/v1/my-portfolio/imports/{data['import_id']}/confirm",
        headers=headers,
        json={"import_id": data["import_id"], "confirmation": "CONFIRM"},
    )
    assert first.status_code == 200
    body = first.json()["data"]
    assert body["already_confirmed"] is False
    assert body["holdings"][0]["instrument_id"] == "NSE:INFY"
    assert body["holdings"][0]["quantity"] == 10
    assert body["holdings"][0]["investment"] == "15000"
    assert body["reconciliation"][0]["action"] == "ADDED"

    second = my_portfolio_client.post(
        f"/api/v1/my-portfolio/imports/{data['import_id']}/confirm",
        headers=headers,
        json={"import_id": data["import_id"], "confirmation": "CONFIRM"},
    )
    assert second.status_code == 200
    assert second.json()["data"]["already_confirmed"] is True

    audit = my_portfolio_client.get(
        f"/api/v1/my-portfolio/imports/{data['import_id']}/reconciliations",
        headers=get_auth_headers(my_portfolio_client, Role.READONLY, username="audit"),
    )
    assert audit.status_code == 200
    assert len(audit.json()["data"]) == 1


def test_reconciliation_reports_updated_removed_and_unchanged(my_portfolio_client: TestClient) -> None:
    headers = get_auth_headers(my_portfolio_client, Role.OPERATOR)
    initial = _preview(my_portfolio_client, b"Symbol,Qty,Avg Price\nINFY,10,1500\nTCS,5,3000\n")
    my_portfolio_client.post(
        f"/api/v1/my-portfolio/imports/{initial['import_id']}/confirm",
        headers=headers,
        json={"import_id": initial["import_id"], "confirmation": "CONFIRM"},
    )

    next_preview = _preview(my_portfolio_client, b"Symbol,Qty,Avg Price\nINFY,10,1500\n")
    actions = {item["instrument_id"]: item["action"] for item in next_preview["proposed_changes"]}

    assert actions["NSE:INFY"] == "UNCHANGED"
    assert actions["NSE:TCS"] == "REMOVED"

    my_portfolio_client.post(
        f"/api/v1/my-portfolio/imports/{next_preview['import_id']}/confirm",
        headers=headers,
        json={"import_id": next_preview["import_id"], "confirmation": "CONFIRM"},
    )
    holdings = my_portfolio_client.get(
        "/api/v1/my-portfolio/holdings",
        headers=get_auth_headers(my_portfolio_client, Role.READONLY, username="holdings"),
    ).json()["data"]
    assert [holding["instrument_id"] for holding in holdings] == ["NSE:INFY"]


def test_invalid_duplicate_and_stale_previews_are_rejected(my_portfolio_client: TestClient) -> None:
    duplicate = _preview(my_portfolio_client, b"Symbol,Qty,Avg Price\nINFY,10,1500\nINFY,2,1600\n")
    assert "DUPLICATE_CANONICAL_INSTRUMENT" in duplicate["rows"][0]["validation_errors"]

    headers = get_auth_headers(my_portfolio_client, Role.OPERATOR)
    invalid_confirm = my_portfolio_client.post(
        f"/api/v1/my-portfolio/imports/{duplicate['import_id']}/confirm",
        headers=headers,
        json={"import_id": duplicate["import_id"], "confirmation": "CONFIRM"},
    )
    assert invalid_confirm.status_code == 400

    old = _preview(my_portfolio_client, b"Symbol,Qty,Avg Price\nINFY,10,1500\n")
    newer = _preview(my_portfolio_client, b"Symbol,Qty,Avg Price\nTCS,1,3000\n")
    my_portfolio_client.post(
        f"/api/v1/my-portfolio/imports/{newer['import_id']}/confirm",
        headers=headers,
        json={"import_id": newer["import_id"], "confirmation": "CONFIRM"},
    )
    stale = my_portfolio_client.post(
        f"/api/v1/my-portfolio/imports/{old['import_id']}/confirm",
        headers=headers,
        json={"import_id": old["import_id"], "confirmation": "CONFIRM"},
    )
    assert stale.status_code == 409
    assert "STALE_PREVIEW" in stale.json()["detail"]


def test_confirm_rolls_back_when_audit_insert_fails(tmp_path: Path) -> None:
    repo = SqliteRepository(tmp_path / "athena.db")
    repo.initialize()
    repo.upsert_instrument(_instrument("NSE:INFY", "INFY"))
    service = MyPortfolioService(repo)
    preview = service.preview_import(filename="holdings.csv", content=b"Symbol,Qty,Avg Price\nINFY,10,1500\n")
    repo._conn.execute(  # type: ignore[attr-defined]
        """
        CREATE TRIGGER fail_portfolio_reconciliation_insert
        AFTER INSERT ON portfolio_reconciliations
        BEGIN
            SELECT RAISE(ABORT, 'forced audit failure');
        END
        """
    )

    with pytest.raises(Exception, match="forced audit failure"):
        service.confirm_import(import_id=preview.import_id, confirmation="CONFIRM")

    assert repo.get_portfolio_import(preview.import_id)["status"] == "PREVIEWED"
    assert repo.list_portfolio_holdings() == []
    assert repo.list_portfolio_reconciliations(preview.import_id) == []
    repo.close()


def test_sync_zero_holdings_finishes_without_snapshot(tmp_path: Path) -> None:
    repo = SqliteRepository(tmp_path / "athena.db")
    repo.initialize()
    service = MyPortfolioService(repo)

    run = service.run_sync_inline()

    assert run.status.value == "SUCCESS"
    assert run.total_holdings == 0
    assert run.progress["message"] == "No holdings imported yet"
    with pytest.raises(Exception, match="no completed My Portfolio snapshot exists"):
        service.latest_snapshot()
    repo.close()


def test_confirmed_holdings_do_not_generate_snapshot_before_manual_sync(
    my_portfolio_client: TestClient,
) -> None:
    _confirm_infy_holding(my_portfolio_client)

    snapshot = my_portfolio_client.get(
        "/api/v1/my-portfolio/snapshot",
        headers=get_auth_headers(my_portfolio_client, Role.READONLY, username="snapshot-reader"),
    )
    holdings = my_portfolio_client.get(
        "/api/v1/my-portfolio/holdings",
        headers=get_auth_headers(my_portfolio_client, Role.READONLY, username="holdings-reader"),
    )

    assert snapshot.status_code == 404
    assert holdings.status_code == 200
    assert holdings.json()["data"][0]["instrument_id"] == "NSE:INFY"


def test_sync_current_d1_reuses_persisted_state_without_refresh(
    my_portfolio_client: TestClient,
) -> None:
    repo = _confirm_infy_holding(my_portfolio_client)
    repo.add_candles([_candle("NSE:INFY", "1600", SEP2)])
    calls: list[tuple[str, ...]] = []

    def runner(symbols, as_of):
        calls.append(tuple(symbols))
        return "refresh-run"

    run = _run_portfolio_sync(repo, validation_runner=runner)

    assert run["status"] == "SUCCESS"
    assert calls == []
    assert run["market_data_through"] == SEP2


def test_sync_missing_d1_invokes_scoped_refresh(
    my_portfolio_client: TestClient,
) -> None:
    repo = _confirm_infy_holding(my_portfolio_client)
    calls: list[tuple[tuple[str, ...], datetime]] = []

    def runner(symbols, as_of):
        calls.append((tuple(symbols), as_of))
        repo.add_candles([_candle("NSE:INFY", "1600", SEP2)])
        return "refresh-run"

    run = _run_portfolio_sync(repo, validation_runner=runner)

    assert run["status"] == "SUCCESS"
    assert calls == [(("INFY",), SEP2)]
    assert run["validation_run_id"] == "refresh-run"
    assert run["market_data_through"] == SEP2


def test_sync_stale_d1_invokes_refresh_and_re_reads_newer_state(
    my_portfolio_client: TestClient,
) -> None:
    repo = _confirm_infy_holding(my_portfolio_client)
    repo.add_candles([_candle("NSE:INFY", "1500", SEP1)])

    def runner(symbols, as_of):
        assert tuple(symbols) == ("INFY",)
        assert as_of == SEP2
        repo.add_candles([_candle("NSE:INFY", "1700", SEP2)])
        repo.save_decision(_decision(decision_id="dec-post-refresh", ts=SEP2, target="1800"))
        return "refresh-run"

    run = _run_portfolio_sync(repo, validation_runner=runner)
    snapshot = MyPortfolioService(repo).latest_snapshot()
    row = snapshot.rows[0]

    assert run["status"] == "SUCCESS"
    assert row.last_price == Decimal("1700")
    assert row.price_as_of == SEP2
    assert row.current_value == Decimal("17000")
    assert row.target_1 == Decimal("1800")
    assert row.provenance.decision_id == "dec-post-refresh"
    assert row.provenance.validation_run_id == "run-dec-post-refresh"
    assert row.status == "STRONG"
    assert row.next_action == "HOLD"
    assert snapshot.summary.market_data_through == SEP2


def test_sync_weekend_or_holiday_expected_session_does_not_refresh_current_prior_session(
    my_portfolio_client: TestClient,
) -> None:
    repo = _confirm_infy_holding(my_portfolio_client)
    repo.add_candles([_candle("NSE:INFY", "1600", FRIDAY)])
    calls: list[tuple[str, ...]] = []

    def runner(symbols, as_of):
        calls.append(tuple(symbols))
        return "refresh-run"

    weekend_run = _run_portfolio_sync(
        repo,
        expected_analysis_as_of=FRIDAY,
        validation_runner=runner,
    )
    holiday_run = _run_portfolio_sync(
        repo,
        expected_analysis_as_of=FRIDAY,
        validation_runner=runner,
    )

    assert weekend_run["status"] == "SUCCESS"
    assert holiday_run["status"] == "SUCCESS"
    assert calls == []


def test_sync_rejects_stale_decision_tradeplan_for_current_price(
    my_portfolio_client: TestClient,
) -> None:
    repo = _confirm_infy_holding(my_portfolio_client)
    repo.add_candles([_candle("NSE:INFY", "1600", SEP2)])
    repo.save_decision(_decision(decision_id="dec-stale", ts=SEP1, target="1900"))

    _run_portfolio_sync(repo)
    row = MyPortfolioService(repo).latest_snapshot().rows[0]

    assert row.last_price == Decimal("1600")
    assert row.freshness.decision_as_of == SEP1
    assert row.provenance.decision_id == "dec-stale"
    assert row.provenance.validation_run_id is None
    assert row.target_1 is None
    assert row.status == "UNAVAILABLE"
    assert row.next_action == "WATCH"
    assert row.key_trigger is None
    assert row.major_support_exit is None
    assert "decision_evidence" in row.provenance.unavailable_fields
    assert "target_1" in row.provenance.unavailable_fields
    assert "STALE_DECISION_EVIDENCE" in row.provenance.interpretation_reason_codes


def test_sync_force_ingestion_refreshes_even_current_d1(
    my_portfolio_client: TestClient,
) -> None:
    repo = _confirm_infy_holding(my_portfolio_client)
    repo.add_candles([_candle("NSE:INFY", "1600", SEP2)])
    calls: list[tuple[str, ...]] = []

    def runner(symbols, as_of):
        calls.append(tuple(symbols))
        repo.add_candles([_candle("NSE:INFY", "1650", SEP2)])
        return "forced-refresh-run"

    run = _run_portfolio_sync(
        repo,
        validation_runner=runner,
        force_ingestion=True,
    )
    row = MyPortfolioService(repo).latest_snapshot().rows[0]

    assert calls == [("INFY",)]
    assert run["validation_run_id"] == "forced-refresh-run"
    assert row.last_price == Decimal("1650")
    assert row.price_as_of == SEP2


def test_sync_builds_server_owned_snapshot_math_and_tradeplan_target(
    my_portfolio_client: TestClient,
) -> None:
    headers = get_auth_headers(my_portfolio_client, Role.OPERATOR)
    preview = _preview(my_portfolio_client, b"Symbol,Qty,Avg Price\nINFY,10,1500\n")
    my_portfolio_client.post(
        f"/api/v1/my-portfolio/imports/{preview['import_id']}/confirm",
        headers=headers,
        json={"import_id": preview["import_id"], "confirmation": "CONFIRM"},
    )
    repo = my_portfolio_client.app.state.sqlite_repo
    repo.add_candles([_candle("NSE:INFY", "1600")])
    decision = Decision(
        decision_id="dec-infy",
        ts=NOW,
        run_id="run-infy",
        cycle_id="cycle-infy",
        decision_type=DecisionType.TRADE,
        explanation="Persisted test decision",
        instrument_id="NSE:INFY",
        direction=Direction.LONG,
        trade_plan=TradePlan(
            entry_low=Decimal("1500"),
            entry_high=Decimal("1510"),
            stop_loss=Decimal("1450"),
            targets=(Decimal("1700"),),
            position_size=1,
            risk_amount=Decimal("50"),
            risk_reward=Decimal("4"),
            valid_from=NOW,
            valid_until=datetime(2026, 9, 3, 10, 0, tzinfo=timezone.utc),
        ),
    )
    repo.save_decision(decision)

    run = MyPortfolioService(repo).run_sync_inline()
    snapshot = MyPortfolioService(repo).latest_snapshot()

    assert run.status.value == "SUCCESS"
    assert run.succeeded_holdings == 1
    assert snapshot.summary.holding_count == 1
    assert snapshot.summary.total_investment == Decimal("15000")
    assert snapshot.summary.total_current_value == Decimal("16000")
    assert snapshot.summary.total_pnl == Decimal("1000")
    assert snapshot.summary.total_pnl_pct == Decimal("6.666666666666666666666666667")
    row = snapshot.rows[0]
    assert row.symbol == "INFY"
    assert row.quantity == 10
    assert row.avg_price == Decimal("1500")
    assert row.last_price == Decimal("1600")
    assert row.current_value == Decimal("16000")
    assert row.pnl == Decimal("1000")
    assert row.status == "STRONG"
    assert row.conviction is None
    assert row.trend_setup is None
    assert row.key_trigger is None
    assert row.support_1 is None
    assert row.major_support_exit == Decimal("1450")
    assert row.target_1 == Decimal("1700")
    assert row.target_2 is None
    assert row.target_3 is None
    assert row.next_action == "HOLD"
    assert row.provenance.decision_id == "dec-infy"
    assert row.provenance.validation_run_id == "run-infy"
    assert row.provenance.interpretation_version == "portfolio-interpretation-v0"
    assert "CURRENT_TRADE_PLAN" in row.provenance.interpretation_reason_codes
    assert "ADD_NOT_CONFIRMED" in row.provenance.interpretation_reason_codes
    assert "status" not in row.provenance.unavailable_fields
    assert "target_2" in row.provenance.unavailable_fields
    assert snapshot.currentness.value == "CURRENT"
    assert snapshot.portfolio_changed_since_sync is False
    assert snapshot.snapshot_holdings_digest == snapshot.current_holdings_digest


def test_sync_sets_entry_low_key_trigger_when_trade_plan_entry_is_actionable(
    my_portfolio_client: TestClient,
) -> None:
    repo = _confirm_infy_holding(my_portfolio_client)
    repo.add_candles([_candle("NSE:INFY", "1600", SEP2)])
    repo.save_decision(
        _decision(
            decision_id="dec-trigger",
            ts=SEP2,
            entry_low="1650",
            entry_high="1660",
            stop_loss="1500",
            target="1800",
        )
    )

    _run_portfolio_sync(repo)
    row = MyPortfolioService(repo).latest_snapshot().rows[0]

    assert row.status == "STRONG"
    assert row.next_action == "HOLD"
    assert row.key_trigger == "1650"
    assert row.major_support_exit == Decimal("1500")
    assert row.target_1 == Decimal("1800")
    assert "TRADE_PLAN_ENTRY_TRIGGER_ACTIVE" in row.provenance.interpretation_reason_codes


def test_sync_allows_add_only_from_coherent_entry_qualification(
    my_portfolio_client: TestClient,
) -> None:
    repo = _confirm_infy_holding(my_portfolio_client)
    repo.add_candles([_candle("NSE:INFY", "1600", SEP2)])
    decision = _decision(decision_id="dec-add", ts=SEP2)
    repo.save_decision(decision)
    repo.save_entry_qualification(_entry_qualification(decision, as_of=SEP2), persisted_at=SEP2)

    _run_portfolio_sync(repo)
    row = MyPortfolioService(repo).latest_snapshot().rows[0]

    assert row.status == "STRONG"
    assert row.next_action == "ADD"
    assert row.provenance.interpretation_evidence["entry_qualification_accepted"] is True
    assert "ENTRY_QUALIFICATION_READY" in row.provenance.interpretation_reason_codes


def test_latest_snapshot_reports_stale_after_holding_quantity_change(
    my_portfolio_client: TestClient,
) -> None:
    repo = _confirm_infy_holding(my_portfolio_client)
    repo.add_candles([_candle("NSE:INFY", "1600", SEP2)])
    _run_portfolio_sync(repo)

    stale_digest = MyPortfolioService(repo).latest_snapshot().snapshot_holdings_digest
    _confirm_holdings(my_portfolio_client, b"Symbol,Qty,Avg Price\nINFY,12,1500\n")
    snapshot = MyPortfolioService(repo).latest_snapshot()

    assert snapshot.currentness.value == "STALE_HOLDINGS_CHANGED"
    assert snapshot.portfolio_changed_since_sync is True
    assert snapshot.currentness_reason == "STALE_HOLDINGS_CHANGED"
    assert snapshot.snapshot_holdings_digest == stale_digest
    assert snapshot.current_holdings_digest != snapshot.snapshot_holdings_digest
    assert snapshot.rows[0].quantity == 10


def test_successful_resync_restores_currentness_after_holdings_change(
    my_portfolio_client: TestClient,
) -> None:
    repo = _confirm_infy_holding(my_portfolio_client)
    repo.add_candles([_candle("NSE:INFY", "1600", SEP2)])
    first = MyPortfolioService(repo).run_sync_inline()

    _confirm_holdings(my_portfolio_client, b"Symbol,Qty,Avg Price\nINFY,12,1500\n")
    stale = MyPortfolioService(repo).latest_snapshot()
    second = MyPortfolioService(repo).run_sync_inline()
    current = MyPortfolioService(repo).latest_snapshot()

    assert stale.snapshot_id == first.sync_run_id
    assert stale.currentness.value == "STALE_HOLDINGS_CHANGED"
    assert current.snapshot_id == second.sync_run_id
    assert current.currentness.value == "CURRENT"
    assert current.snapshot_holdings_digest == current.current_holdings_digest
    assert current.rows[0].quantity == 12
    assert stale.rows[0].quantity == 10


def test_legacy_snapshot_without_holdings_digest_reports_unknown_until_resync(
    my_portfolio_client: TestClient,
) -> None:
    repo = _confirm_infy_holding(my_portfolio_client)
    repo.add_candles([_candle("NSE:INFY", "1600", SEP2)])
    legacy_run = MyPortfolioService(repo).run_sync_inline()
    repo._conn.execute(  # type: ignore[attr-defined]
        "UPDATE portfolio_sync_runs SET provenance_json='{}' WHERE sync_run_id=?",
        (legacy_run.sync_run_id,),
    )
    repo._conn.commit()  # type: ignore[attr-defined]

    unknown = MyPortfolioService(repo).latest_snapshot()
    resync = MyPortfolioService(repo).run_sync_inline()
    current = MyPortfolioService(repo).latest_snapshot()

    assert unknown.snapshot_id == legacy_run.sync_run_id
    assert unknown.currentness.value == "UNKNOWN"
    assert unknown.portfolio_changed_since_sync is False
    assert unknown.currentness_reason == "SNAPSHOT_HOLDINGS_DIGEST_UNAVAILABLE"
    assert unknown.rows[0].quantity == 10
    assert current.snapshot_id == resync.sync_run_id
    assert current.currentness.value == "CURRENT"


def test_latest_snapshot_remains_current_after_semantically_identical_reimport(
    my_portfolio_client: TestClient,
) -> None:
    repo = _confirm_infy_holding(my_portfolio_client)
    repo.add_candles([_candle("NSE:INFY", "1600", SEP2)])
    _run_portfolio_sync(repo)

    _confirm_holdings(my_portfolio_client, b"Symbol,Qty,Avg Price\nINFY,10,1500\n")
    snapshot = MyPortfolioService(repo).latest_snapshot()

    assert snapshot.currentness.value == "CURRENT"
    assert snapshot.portfolio_changed_since_sync is False
    assert snapshot.snapshot_holdings_digest == snapshot.current_holdings_digest


def test_latest_snapshot_reports_stale_after_avg_price_change(
    my_portfolio_client: TestClient,
) -> None:
    repo = _confirm_infy_holding(my_portfolio_client)
    repo.add_candles([_candle("NSE:INFY", "1600", SEP2)])
    _run_portfolio_sync(repo)

    _confirm_holdings(my_portfolio_client, b"Symbol,Qty,Avg Price\nINFY,10,1510\n")
    snapshot = MyPortfolioService(repo).latest_snapshot()

    assert snapshot.currentness.value == "STALE_HOLDINGS_CHANGED"
    assert snapshot.current_holdings_digest != snapshot.snapshot_holdings_digest


def test_latest_snapshot_reports_stale_after_holding_added(
    my_portfolio_client: TestClient,
) -> None:
    repo = _confirm_infy_holding(my_portfolio_client)
    repo.add_candles([_candle("NSE:INFY", "1600", SEP2)])
    _run_portfolio_sync(repo)

    _confirm_holdings(
        my_portfolio_client,
        b"Symbol,Qty,Avg Price\nINFY,10,1500\nTCS,1,3000\n",
    )
    snapshot = MyPortfolioService(repo).latest_snapshot()

    assert snapshot.currentness.value == "STALE_HOLDINGS_CHANGED"
    assert [row.symbol for row in snapshot.rows] == ["INFY"]


def test_latest_snapshot_reports_stale_after_holding_removed(
    my_portfolio_client: TestClient,
) -> None:
    repo = _confirm_holdings(
        my_portfolio_client,
        b"Symbol,Qty,Avg Price\nINFY,10,1500\nTCS,1,3000\n",
    )
    repo.add_candles([
        _candle("NSE:INFY", "1600", SEP2),
        _candle("NSE:TCS", "3100", SEP2),
    ])
    _run_portfolio_sync(repo)

    _confirm_holdings(my_portfolio_client, b"Symbol,Qty,Avg Price\nINFY,10,1500\n")
    snapshot = MyPortfolioService(repo).latest_snapshot()

    assert snapshot.currentness.value == "STALE_HOLDINGS_CHANGED"
    assert {row.symbol for row in snapshot.rows} == {"INFY", "TCS"}


def test_sync_partial_persists_successful_rows_and_failure_metadata(
    my_portfolio_client: TestClient,
) -> None:
    headers = get_auth_headers(my_portfolio_client, Role.OPERATOR)
    preview = _preview(my_portfolio_client, b"Symbol,Qty,Avg Price\nINFY,10,1500\nTCS,5,3000\n")
    my_portfolio_client.post(
        f"/api/v1/my-portfolio/imports/{preview['import_id']}/confirm",
        headers=headers,
        json={"import_id": preview["import_id"], "confirmation": "CONFIRM"},
    )
    repo = my_portfolio_client.app.state.sqlite_repo
    repo.add_candles([_candle("NSE:INFY", "1600")])

    run = MyPortfolioService(repo).run_sync_inline()
    snapshot = MyPortfolioService(repo).latest_snapshot()

    assert run.status.value == "PARTIAL"
    assert run.succeeded_holdings == 1
    assert run.failed_holdings == 1
    assert run.per_symbol["TCS"]["errors"] == ["NO_PERSISTED_D1_CANDLE"]
    assert snapshot.summary.total_current_value is None
    assert {row.symbol for row in snapshot.rows} == {"INFY", "TCS"}
    failed = next(row for row in snapshot.rows if row.symbol == "TCS")
    assert failed.last_price is None
    assert failed.current_value is None
    assert failed.status == "UNAVAILABLE"
    assert failed.next_action == "WATCH"
    assert "NO_PERSISTED_D1_CANDLE" in failed.provenance.failed_components
    assert snapshot.currentness.value == "CURRENT"
    assert snapshot.summary.sync_status.value == "PARTIAL"

    _confirm_holdings(my_portfolio_client, b"Symbol,Qty,Avg Price\nINFY,12,1500\nTCS,5,3000\n")
    stale_snapshot = MyPortfolioService(repo).latest_snapshot()
    assert stale_snapshot.currentness.value == "STALE_HOLDINGS_CHANGED"
    assert stale_snapshot.summary.sync_status.value == "PARTIAL"


class _AliveSyncThread:
    def is_alive(self) -> bool:
        return True


def _install_active_sync(
    monkeypatch: pytest.MonkeyPatch,
    repo: SqliteRepository,
    *,
    status: SyncRunStatus,
) -> str:
    sync_run_id = f"sync-{status.value.lower()}"
    repo.create_portfolio_sync_run(
        sync_run_id=sync_run_id,
        started_at=NOW,
        total_holdings=len(repo.list_portfolio_holdings()),
        analysis_version="my-portfolio-v1",
        status=status,
        progress={"stage": status.value.lower()},
        provenance={"holdings_digest": repo.portfolio_holdings_digest()},
    )
    monkeypatch.setattr(my_portfolio_service_module, "_SYNC_THREAD", _AliveSyncThread())
    monkeypatch.setattr(my_portfolio_service_module, "_SYNC_THREAD_RUN_ID", sync_run_id)
    return sync_run_id


@pytest.mark.parametrize("status", [SyncRunStatus.QUEUED, SyncRunStatus.RUNNING])
def test_confirm_import_is_blocked_during_active_sync_without_mutating_holdings(
    my_portfolio_client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
    status: SyncRunStatus,
) -> None:
    repo = _confirm_infy_holding(my_portfolio_client)
    preview = _preview(my_portfolio_client, b"Symbol,Qty,Avg Price\nINFY,12,1500\n")
    before = repo.portfolio_holdings_digest()
    _install_active_sync(monkeypatch, repo, status=status)

    response = my_portfolio_client.post(
        f"/api/v1/my-portfolio/imports/{preview['import_id']}/confirm",
        headers=get_auth_headers(my_portfolio_client, Role.OPERATOR),
        json={"import_id": preview["import_id"], "confirmation": "CONFIRM"},
    )

    assert response.status_code == 409
    assert "Portfolio Sync is currently running" in response.json()["detail"]
    assert repo.portfolio_holdings_digest() == before
    assert repo.get_portfolio_import(preview["import_id"])["status"] == "PREVIEWED"


def test_import_preview_is_allowed_during_active_sync_but_confirmation_is_blocked(
    my_portfolio_client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    repo = _confirm_infy_holding(my_portfolio_client)
    before = repo.portfolio_holdings_digest()
    _install_active_sync(monkeypatch, repo, status=SyncRunStatus.RUNNING)

    preview = _preview(my_portfolio_client, b"Symbol,Qty,Avg Price\nINFY,12,1500\n")
    response = my_portfolio_client.post(
        f"/api/v1/my-portfolio/imports/{preview['import_id']}/confirm",
        headers=get_auth_headers(my_portfolio_client, Role.OPERATOR),
        json={"import_id": preview["import_id"], "confirmation": "CONFIRM"},
    )

    assert preview["status"] == "PREVIEWED"
    assert response.status_code == 409
    assert repo.portfolio_holdings_digest() == before


@pytest.mark.parametrize(
    "status",
    [SyncRunStatus.SUCCESS, SyncRunStatus.PARTIAL, SyncRunStatus.FAILED, SyncRunStatus.CANCELLED],
)
def test_confirm_import_is_allowed_after_terminal_sync_states(
    my_portfolio_client: TestClient,
    status: SyncRunStatus,
) -> None:
    repo = _confirm_infy_holding(my_portfolio_client)
    repo.create_portfolio_sync_run(
        sync_run_id=f"sync-{status.value.lower()}",
        started_at=NOW,
        total_holdings=1,
        analysis_version="my-portfolio-v1",
        status=status,
        progress={"stage": status.value.lower()},
        provenance={"holdings_digest": repo.portfolio_holdings_digest()},
    )
    preview = _preview(my_portfolio_client, b"Symbol,Qty,Avg Price\nINFY,12,1500\n")

    response = my_portfolio_client.post(
        f"/api/v1/my-portfolio/imports/{preview['import_id']}/confirm",
        headers=get_auth_headers(my_portfolio_client, Role.OPERATOR),
        json={"import_id": preview["import_id"], "confirmation": "CONFIRM"},
    )

    assert response.status_code == 200
    assert repo.list_portfolio_holdings()[0].quantity == 12


def test_failed_sync_does_not_replace_previous_good_snapshot(
    my_portfolio_client: TestClient,
) -> None:
    headers = get_auth_headers(my_portfolio_client, Role.OPERATOR)
    preview = _preview(my_portfolio_client, b"Symbol,Qty,Avg Price\nINFY,10,1500\n")
    my_portfolio_client.post(
        f"/api/v1/my-portfolio/imports/{preview['import_id']}/confirm",
        headers=headers,
        json={"import_id": preview["import_id"], "confirmation": "CONFIRM"},
    )
    repo = my_portfolio_client.app.state.sqlite_repo
    repo.add_candles([_candle("NSE:INFY", "1600")])
    service = MyPortfolioService(repo)
    good = service.run_sync_inline()
    assert service.latest_snapshot().snapshot_id == good.sync_run_id

    repo._conn.execute("DELETE FROM candles")  # type: ignore[attr-defined]
    failed = service.run_sync_inline()

    assert failed.status.value == "FAILED"
    assert service.latest_snapshot().snapshot_id == good.sync_run_id
    assert len(repo.list_portfolio_analysis_snapshots(good.sync_run_id)) == 1
    assert len(repo.list_portfolio_analysis_snapshots(failed.sync_run_id)) == 1


@pytest.mark.parametrize("holding_count", [20, 50, 100])
def test_representative_portfolio_sizes_sync_without_state_drift(
    my_portfolio_client: TestClient,
    holding_count: int,
) -> None:
    repo = my_portfolio_client.app.state.sqlite_repo
    rows = ["Symbol,Qty,Avg Price"]
    candles = []
    for index in range(holding_count):
        symbol = f"P{index:03d}"
        instrument_id = f"NSE:{symbol}"
        repo.upsert_instrument(_instrument(instrument_id, symbol))
        rows.append(f"{symbol},{index + 1},{100 + index}")
        candles.append(_candle(instrument_id, str(110 + index), SEP2))
    _confirm_holdings(my_portfolio_client, ("\n".join(rows) + "\n").encode())
    digest_before = repo.portfolio_holdings_digest()
    repo.add_candles(candles)

    started = time.perf_counter()
    run = _run_portfolio_sync(repo)
    elapsed = time.perf_counter() - started
    snapshot = MyPortfolioService(repo).latest_snapshot()

    assert elapsed >= 0
    assert run["status"] == "SUCCESS"
    assert run["total_holdings"] == holding_count
    assert run["succeeded_holdings"] == holding_count
    assert run["failed_holdings"] == 0
    assert repo.portfolio_holdings_digest() == digest_before
    assert snapshot.summary.holding_count == holding_count
    assert len(snapshot.rows) == holding_count
    assert snapshot.currentness.value == "CURRENT"
    assert snapshot.snapshot_holdings_digest == digest_before


def test_sync_api_starts_background_and_exposes_snapshot(
    my_portfolio_client: TestClient,
) -> None:
    headers = get_auth_headers(my_portfolio_client, Role.OPERATOR)
    preview = _preview(my_portfolio_client, b"Symbol,Qty,Avg Price\nINFY,10,1500\n")
    my_portfolio_client.post(
        f"/api/v1/my-portfolio/imports/{preview['import_id']}/confirm",
        headers=headers,
        json={"import_id": preview["import_id"], "confirmation": "CONFIRM"},
    )
    repo = my_portfolio_client.app.state.sqlite_repo
    repo.add_candles([_candle("NSE:INFY", "1600")])
    my_portfolio_client.app.dependency_overrides[get_my_portfolio_service] = (
        lambda: MyPortfolioService(repo)
    )

    start = my_portfolio_client.post(
        "/api/v1/my-portfolio/sync",
        headers=headers,
        json={"force_ingestion": False},
    )
    assert start.status_code == 202
    sync_id = start.json()["data"]["sync_run_id"]
    assert start.json()["data"]["status"] in {"QUEUED", "RUNNING", "SUCCESS"}

    status_payload = None
    for _ in range(20):
        status_response = my_portfolio_client.get(
            f"/api/v1/my-portfolio/sync/{sync_id}",
            headers=get_auth_headers(my_portfolio_client, Role.READONLY, username="sync-reader"),
        )
        assert status_response.status_code == 200
        status_payload = status_response.json()["data"]
        if status_payload["status"] in {"SUCCESS", "PARTIAL", "FAILED"}:
            break
        time.sleep(0.01)

    assert status_payload is not None
    assert status_payload["status"] == "SUCCESS"
    snapshot = my_portfolio_client.get(
        "/api/v1/my-portfolio/snapshot",
        headers=get_auth_headers(my_portfolio_client, Role.READONLY, username="snapshot-reader"),
    )
    assert snapshot.status_code == 200
    row = snapshot.json()["data"]["rows"][0]
    assert set(row) >= {
        "symbol",
        "qty",
        "avg_price",
        "last_price",
        "price_as_of",
        "investment",
        "current_value",
        "pnl",
        "pnl_pct",
        "status",
        "conviction",
        "trend_or_setup",
        "key_trigger",
        "support_1",
        "major_support_exit",
        "target_1",
        "target_2",
        "target_3",
        "next_action",
        "last_review",
    }
