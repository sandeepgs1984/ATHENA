"""Integration tests for P8.3 Core Platform APIs.

Covers:
- paginated/sorted/filtered Decisions
- Decisions details and not found mapping
- Portfolio balances, positions, and unavailable states
- paginated System Pipeline run logs
- Scheduler history executions
- Workspace snapshots summary list vs detail entries
- Security guards and RBAC permission checks
"""

from __future__ import annotations

import hashlib

# ---------------------------------------------------------------------------
# Auth Helpers
# ---------------------------------------------------------------------------
from datetime import datetime, timedelta, timezone
from decimal import Decimal

import pytest
from fastapi.testclient import TestClient

from athena.api.dependencies import (
    get_decision_provider,
    get_pipeline_run_provider,
    get_portfolio_provider,
    get_scheduler_history_provider,
    get_workspace_provider,
)
from athena.api.security.dependencies import (
    get_api_key_repository,
    get_user_repository,
)
from athena.api.security.models import APIKeyMetadata, Permission, Role, User
from athena.domain.decision import Decision, GateResult, Portfolio, Position, TradePlan
from athena.domain.enums import DecisionType, Direction, QualityGate
from athena.orchestration.models import PipelineContext, PipelineStatus, SystemPipelineResult
from athena.orchestration.schedule_models import PipelineScheduleRun
from athena.workspace.models import WorkspaceEntry, WorkspaceReferences, WorkspaceSnapshot, WorkspaceSummary


def get_auth_headers(client: TestClient, role: Role, username: str = "analyst") -> dict[str, str]:
    """Helper to generate JWT bearer headers for a given role."""
    app = client.app
    user = User(user_id=f"usr-{username}", username=username, password_hash="hash", role=role)
    get_user_repository().save(user)

    from athena.api.security.dependencies import get_session_store
    from athena.api.security.models import ROLE_PERMISSIONS, AuthenticatedPrincipal, Session
    
    session = Session(
        session_id="sess-test-run",
        user_id=user.user_id,
        refresh_token_hash="hash",
        created_at=datetime.now(tz=timezone.utc),
        expires_at=datetime.now(tz=timezone.utc) + timedelta(days=1),
        is_revoked=False,
    )
    get_session_store().save(session)

    permissions = ROLE_PERMISSIONS[role]
    principal = AuthenticatedPrincipal(
        user_id=user.user_id,
        username=user.username,
        role=user.role,
        permissions=permissions,
    )

    claims = app.state.claims_factory.create_claims(
        principal=principal,
        token_type="access",
        session_id="sess-test-run",
        now=datetime.now(tz=timezone.utc),
    )
    token = app.state.token_signer.encode(claims.to_dict())
    return {"Authorization": f"Bearer {token}"}


def get_api_key_headers(
    client: TestClient,
    role: Role,
    username: str = "operator",
    permissions: tuple[Permission, ...] | None = None,
) -> dict[str, str]:
    """Helper to generate X-API-Key header for a given role."""
    user = User(user_id=f"usr-{username}", username=username, password_hash="hash", role=role)
    get_user_repository().save(user)

    from athena.api.security.dependencies import get_api_key_repository
    from athena.api.security.models import Permission

    raw_secret = "super_secure_raw_secret_value"
    hashed_secret = hashlib.sha256(raw_secret.encode()).hexdigest()
    
    actual_perms = permissions if permissions is not None else (Permission.READ,)
    key_meta = APIKeyMetadata(
        key_id="key-core-test",
        owner_id=user.user_id,
        key_hash=hashed_secret,
        name="core-test-key",
        created_at=datetime.now(tz=timezone.utc),
        expires_at=None,
        is_active=True,
        permissions=actual_perms,
    )
    get_api_key_repository().save(key_meta)

    return {"X-API-Key": f"key-core-test.{raw_secret}"}


# ---------------------------------------------------------------------------
# Setup Clean Repositories Fixture
# ---------------------------------------------------------------------------

@pytest.fixture(autouse=True)
def clean_and_seed_providers() -> None:
    """Fixture resetting and seeding clean mock provider structures."""
    # Reset security repos
    get_user_repository()._users.clear()
    get_user_repository()._by_username.clear()
    get_api_key_repository()._keys.clear()

    # Reset core domain providers
    dec_p = get_decision_provider()
    dec_p.decisions.clear()  # type: ignore[attr-defined]
    if hasattr(dec_p, "traces"):
        dec_p.traces.clear()  # type: ignore[attr-defined]

    port_p = get_portfolio_provider()
    port_p.portfolio = None  # type: ignore[attr-defined]

    run_p = get_pipeline_run_provider()
    run_p.runs.clear()  # type: ignore[attr-defined]

    sched_p = get_scheduler_history_provider()
    sched_p.runs.clear()  # type: ignore[attr-defined]

    ws_p = get_workspace_provider()
    ws_p.snapshots.clear()  # type: ignore[attr-defined]


# ---------------------------------------------------------------------------
# Endpoint Tests
# ---------------------------------------------------------------------------

class TestDecisionsAPI:
    def test_list_decisions_requires_auth(self, client) -> None:
        response = client.get("/api/v1/decisions")
        assert response.status_code == 401
        assert response.json()["title"] == "Unauthorized"

    def test_list_decisions_forbidden_for_insufficient_role(self, client) -> None:
        headers = get_api_key_headers(client, Role.READONLY, username="guest", permissions=(Permission.EXECUTE,))
        response = client.get("/api/v1/decisions", headers=headers)
        assert response.status_code == 403
        assert response.json()["title"] == "Permission Denied"

    def test_list_decisions_success_with_paging_and_filtering(self, client) -> None:
        headers = get_auth_headers(client, Role.READONLY)
        dec_p = get_decision_provider()

        # Seed 3 decisions
        now = datetime.now(tz=timezone.utc)
        dec1 = Decision(
            decision_id="dec-1",
            ts=now,
            run_id="run-1",
            cycle_id="cycle-1",
            instrument_id="SBIN",
            direction=Direction.LONG,
            decision_type=DecisionType.WATCH,
            explanation="sbin test buy",
            score_ref="score-1",
            trade_plan=None,
        )
        dec2 = Decision(
            decision_id="dec-2",
            ts=now,
            run_id="run-1",
            cycle_id="cycle-1",
            instrument_id="TATA",
            direction=Direction.LONG,
            decision_type=DecisionType.WATCH,
            explanation="tata test buy",
            score_ref="score-2",
            trade_plan=None,
        )
        dec_p.decisions.extend([dec1, dec2])  # type: ignore[attr-defined]

        # 1. Test basic paginated listing
        response = client.get("/api/v1/decisions?page=1&page_size=1", headers=headers)
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "success"
        assert len(data["data"]) == 1
        assert data["pagination"]["total"] == 2
        assert data["pagination"]["total_pages"] == 2

        # 2. Test filtering by instrument
        response = client.get("/api/v1/decisions?instrument_id=SBIN", headers=headers)
        assert response.status_code == 200
        assert len(response.json()["data"]) == 1
        assert response.json()["data"][0]["metadata"]["decision_id"] == "dec-1"

    def test_get_decision_details_success(self, client) -> None:
        headers = get_auth_headers(client, Role.ANALYST)
        dec_p = get_decision_provider()

        now = datetime.now(tz=timezone.utc)
        plan = TradePlan(
            entry_low=Decimal("100.00"),
            entry_high=Decimal("101.00"),
            stop_loss=Decimal("98.00"),
            targets=(Decimal("104.00"), Decimal("106.00")),
            position_size=10,
            risk_amount=Decimal("300.00"),
            risk_reward=Decimal("2.50"),
            valid_from=now,
            valid_until=now + timedelta(hours=1),
        )
        dec = Decision(
            decision_id="dec-detail-1",
            ts=now,
            run_id="run-1",
            cycle_id="cycle-1",
            instrument_id="SBIN",
            direction=Direction.LONG,
            decision_type=DecisionType.TRADE,
            explanation="sbin detail buy",
            score_ref="score-99",
            confidence_ref="conf-99",
            risk_ref="risk-99",
            gate_results=(GateResult(gate=QualityGate.DATA, passed=True, detail="high volume"),),
            trade_plan=plan,
        )
        dec_p.decisions.append(dec)  # type: ignore[attr-defined]
        dec_p.run_details["run-1"] = {  # type: ignore[attr-defined]
            "pipeline": {
                "universe_members": {
                    "SBIN": {
                        "instrument_id": "SBIN",
                        "included": True,
                        "eligibility_summary": "SBIN passed all eligibility rules.",
                        "exclusion_reasons": [],
                        "evidence": [
                            {
                                "rule": "liquidity",
                                "passed": True,
                                "explanation": "Average volume exceeded threshold.",
                                "inputs": {"volume": "1000000"},
                            }
                        ],
                    }
                },
                "decision_reports": {
                    "dec-detail-1": {
                        "score": {
                            "status": "OK",
                            "composite": "72.5",
                            "completeness": "1",
                            "explanation": "Composite from persisted components.",
                            "components": [
                                {
                                    "dimension": "trend",
                                    "status": "OK",
                                    "value": "80",
                                    "weight": 25,
                                    "weighted": "20",
                                    "explanation": "Trend contribution.",
                                    "contributions": [
                                        {
                                            "source": "regime:trend",
                                            "reference_id": "regime-1",
                                            "description": "Bull trend.",
                                            "points": "80",
                                        }
                                    ],
                                }
                            ],
                        },
                        "confidence": {"status": "UNKNOWN"},
                        "risk": {"status": "UNKNOWN"},
                        "regime": {
                            "status": "ASSESSED",
                            "assessment_id": "regime-1",
                            "labels": ["BULL_TREND", "NORMAL_VOLATILITY"],
                            "explanation": "Bull trend, normal volatility.",
                            "evidence": [
                                {
                                    "dimension": "trend",
                                    "outcome": "BULL_TREND",
                                    "explanation": "20D SMA rising.",
                                }
                            ],
                        },
                        "market_health": {
                            "status": "ASSESSED",
                            "assessment_id": "mh-1",
                            "dimensions": {"breadth": "STRONG_BREADTH"},
                            "explanation": "Breadth strongly positive.",
                            "evidence": [
                                {
                                    "dimension": "breadth",
                                    "outcome": "STRONG_BREADTH",
                                    "explanation": "80 advances vs 20 declines.",
                                }
                            ],
                        },
                    }
                },
            }
        }

        response = client.get("/api/v1/decisions/dec-detail-1", headers=headers)
        assert response.status_code == 200
        data = response.json()["data"]
        assert data["metadata"]["decision_id"] == "dec-detail-1"
        assert data["analysis"]["score_ref"]["id"] == "score-99"
        assert data["analysis"]["score_ref"]["resource_type"] == "score"
        assert data["analysis"]["gate_results"][0]["gate"] == "DATA"
        assert data["analysis"]["gate_results"][0]["passed"] is True
        assert data["trade_plan"]["entry_low"] == "100.00"
        assert data["trade_plan"]["stop_loss"] == "98.00"
        assert data["trade_plan"]["targets"] == ["104.00", "106.00"]
        assert data["trade_plan"]["risk_reward"] == "2.50"

        depth_response = client.get(
            "/api/v1/decisions/dec-detail-1/depth", headers=headers
        )
        assert depth_response.status_code == 200
        depth = depth_response.json()["data"]
        assert depth["eligibility"]["status"] == "INCLUDED"
        assert depth["eligibility"]["rules"][0]["rule"] == "liquidity"
        assert depth["score"]["value"] == "72.5"
        assert depth["score"]["dimensions"][0]["name"] == "trend"
        assert depth["score"]["dimensions"][0]["contributions"][0]["reference"] == (
            "regime-1"
        )
        assert depth["confidence"]["status"] == "UNKNOWN"

        context_response = client.get(
            "/api/v1/decisions/dec-detail-1/context", headers=headers
        )
        assert context_response.status_code == 200
        context = context_response.json()["data"]
        assert context["decision_id"] == "dec-detail-1"
        assert context["calendar"]["exchange"]
        assert context["calendar"]["session_type"] in {
            "NORMAL", "WEEKEND", "HOLIDAY", "MUHURAT",
        }
        assert context["regime"]["status"] == "ASSESSED"
        assert context["regime"]["labels"] == ["BULL_TREND", "NORMAL_VOLATILITY"]
        assert context["regime"]["evidence"][0]["dimension"] == "trend"
        assert context["market_health"]["status"] == "ASSESSED"
        assert context["market_health"]["dimensions"]["breadth"] == "STRONG_BREADTH"
        assert context["external_links"] == []

    def test_get_decision_not_found(self, client) -> None:
        headers = get_auth_headers(client, Role.ANALYST)
        response = client.get("/api/v1/decisions/dec-invalid", headers=headers)
        assert response.status_code == 404
        assert response.json()["title"] == "Decision Not Found"


class TestPortfolioAPI:
    def test_get_portfolio_unavailable_returns_503(self, client) -> None:
        headers = get_auth_headers(client, Role.READONLY)
        response = client.get("/api/v1/portfolio", headers=headers)
        assert response.status_code == 503
        assert response.json()["title"] == "Portfolio Unavailable"

    def test_get_portfolio_success(self, client) -> None:
        headers = get_api_key_headers(client, Role.OPERATOR)
        port_p = get_portfolio_provider()

        now = datetime.now(tz=timezone.utc)
        pos = Position(
            position_id="pos-1",
            instrument_id="RELIANCE",
            opened_ts=now,
            quantity=50,
            avg_price=Decimal("2450.00"),
        )
        port = Portfolio(
            ts=now,
            positions=(pos,),
            cash=Decimal("12000.50"),
            exposure_by_sector={"Energy": Decimal("122500.00")},
        )
        port_p.portfolio = port  # type: ignore[attr-defined]

        response = client.get("/api/v1/portfolio", headers=headers)
        assert response.status_code == 200
        data = response.json()["data"]
        assert Decimal(data["summary"]["cash"]) == Decimal("12000.50")
        assert len(data["positions"]) == 1
        assert data["positions"][0]["position_id"] == "pos-1"
        assert data["positions"][0]["instrument_id"] == "RELIANCE"


class TestPipelinesAPI:
    def test_list_runs_success(self, client) -> None:
        headers = get_auth_headers(client, Role.ANALYST)
        run_p = get_pipeline_run_provider()

        now = datetime.now(tz=timezone.utc)
        ctx = PipelineContext(run_id="run-1", as_of=now)
        run1 = SystemPipelineResult(
            run_id="run-1",
            as_of=now,
            pipeline_runs=(),
            workspace_snapshot=None,
            overall_status=PipelineStatus.SUCCESS,
            final_context=ctx,
        )
        run_p.runs.append(run1)  # type: ignore[attr-defined]

        response = client.get("/api/v1/pipelines/runs", headers=headers)
        assert response.status_code == 200
        data = response.json()
        assert len(data["data"]) == 1
        assert data["data"][0]["run_id"] == "run-1"
        assert data["data"][0]["overall_status"] == "SUCCESS"

    def test_get_run_not_found(self, client) -> None:
        headers = get_auth_headers(client, Role.ANALYST)
        response = client.get("/api/v1/pipelines/runs/run-invalid", headers=headers)
        assert response.status_code == 404
        assert response.json()["title"] == "Pipeline Run Not Found"


class TestSchedulerAPI:
    def test_list_history_success(self, client) -> None:
        headers = get_auth_headers(client, Role.ANALYST)
        sched_p = get_scheduler_history_provider()

        now = datetime.now(tz=timezone.utc)
        ctx = PipelineContext(run_id="run-1", as_of=now)
        sys_res = SystemPipelineResult(
            run_id="run-1",
            as_of=now,
            pipeline_runs=(),
            workspace_snapshot=None,
            overall_status=PipelineStatus.SUCCESS,
            final_context=ctx,
        )
        sched_run = PipelineScheduleRun(
            schedule_run_id="sched-run-1",
            job_id="job-sbin",
            definition_id="def-1",
            system_result=sys_res,
            duration_seconds=12.5,
        )
        sched_p.runs.append(sched_run)  # type: ignore[attr-defined]

        response = client.get("/api/v1/scheduler/history", headers=headers)
        assert response.status_code == 200
        data = response.json()
        assert len(data["data"]) == 1
        assert data["data"][0]["schedule_run_id"] == "sched-run-1"
        assert data["data"][0]["job"]["id"] == "job-sbin"
        assert data["data"][0]["job"]["resource_type"] == "job"

    def test_get_scheduler_run_not_found(self, client) -> None:
        headers = get_auth_headers(client, Role.ANALYST)
        response = client.get("/api/v1/scheduler/history/sched-invalid", headers=headers)
        assert response.status_code == 404
        assert response.json()["title"] == "Scheduler Run Not Found"


class TestWorkspaceAPI:
    def test_list_workspace_snapshots_omits_entries(self, client) -> None:
        headers = get_auth_headers(client, Role.READONLY)
        ws_p = get_workspace_provider()

        now = datetime.now(tz=timezone.utc)
        summary = WorkspaceSummary(
            total_entries=1,
            artifact_counts={"report": 1},
            overall_health="HEALTHY",
        )
        entry = WorkspaceEntry(
            entry_id="ent-1",
            artifact_type="report",
            title="SBI Daily Report",
            as_of=now,
            references=WorkspaceReferences(report_id="rep-1"),
        )
        ws_snap = WorkspaceSnapshot(
            snapshot_id="ws-snap-1",
            as_of=now,
            summary=summary,
            entries=(entry,),
            references=WorkspaceReferences(report_id="rep-1"),
        )
        ws_p.snapshots.append(ws_snap)  # type: ignore[attr-defined]

        # List snapshots endpoint
        response = client.get("/api/v1/workspace/snapshots", headers=headers)
        assert response.status_code == 200
        data = response.json()
        assert len(data["data"]) == 1
        assert data["data"][0]["snapshot_id"] == "ws-snap-1"
        # Assert entries is omitted in the list summary DTO response
        assert "entries" not in data["data"][0]

    def test_get_workspace_snapshot_includes_entries(self, client) -> None:
        headers = get_auth_headers(client, Role.READONLY)
        ws_p = get_workspace_provider()

        now = datetime.now(tz=timezone.utc)
        summary = WorkspaceSummary(
            total_entries=1,
            artifact_counts={"report": 1},
            overall_health="HEALTHY",
        )
        entry = WorkspaceEntry(
            entry_id="ent-1",
            artifact_type="report",
            title="SBI Daily Report",
            as_of=now,
            references=WorkspaceReferences(report_id="rep-1"),
        )
        ws_snap = WorkspaceSnapshot(
            snapshot_id="ws-snap-1",
            as_of=now,
            summary=summary,
            entries=(entry,),
            references=WorkspaceReferences(report_id="rep-1"),
        )
        ws_p.snapshots.append(ws_snap)  # type: ignore[attr-defined]

        # Get detail endpoint
        response = client.get("/api/v1/workspace/snapshots/ws-snap-1", headers=headers)
        assert response.status_code == 200
        data = response.json()["data"]
        assert data["snapshot_id"] == "ws-snap-1"
        assert len(data["entries"]) == 1
        assert data["entries"][0]["entry_id"] == "ent-1"
        assert data["entries"][0]["references"]["report_ref"]["id"] == "rep-1"
        assert data["entries"][0]["references"]["report_ref"]["resource_type"] == "report"

    def test_get_workspace_snapshot_not_found(self, client) -> None:
        headers = get_auth_headers(client, Role.READONLY)
        response = client.get("/api/v1/workspace/snapshots/ws-invalid", headers=headers)
        assert response.status_code == 404
        assert response.json()["title"] == "Workspace Snapshot Not Found"


class TestDashboardAPI:
    def test_get_dashboard_calendar_success(self, client) -> None:
        headers = get_auth_headers(client, Role.READONLY)
        response = client.get("/api/v1/dashboard/calendar", headers=headers)
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "success"
        cal = data["data"]
        assert len(cal["years"]) > 0
        assert len(cal["holidays"]) > 0
        assert isinstance(cal["weekly_expiries"], list)
        assert isinstance(cal["monthly_expiries"], list)

