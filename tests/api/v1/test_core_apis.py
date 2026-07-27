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
from urllib.parse import quote

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
from athena.domain.decision import (
    Decision,
    DecisionTrace,
    GateResult,
    Portfolio,
    Position,
    TraceStage,
    TradePlan,
)
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

    def test_decision_journal_and_outcome_roundtrip(self, client) -> None:
        """M-X0: owner response + realized outcome, server-computed pnl/adherence."""
        read_headers = get_auth_headers(client, Role.ANALYST)
        write_headers = get_auth_headers(client, Role.OPERATOR, username="operator")
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
            decision_id="dec-journal-1",
            ts=now,
            run_id="run-journal-1",
            cycle_id="cycle-journal-1",
            instrument_id="SBIN",
            direction=Direction.LONG,
            decision_type=DecisionType.TRADE,
            explanation="sbin journal test",
            trade_plan=plan,
        )
        dec_p.decisions.append(dec)  # type: ignore[attr-defined]

        # No journal/outcome recorded yet
        empty = client.get("/api/v1/decisions/dec-journal-1/journal", headers=read_headers)
        assert empty.status_code == 200
        assert empty.json()["data"] is None

        # Read-only role cannot record a response
        forbidden = client.post(
            "/api/v1/decisions/dec-journal-1/journal",
            json={"user_action": "ACCEPTED", "notes": "taking this"},
            headers=read_headers,
        )
        assert forbidden.status_code == 403

        accept = client.post(
            "/api/v1/decisions/dec-journal-1/journal",
            json={"user_action": "ACCEPTED", "notes": "taking this"},
            headers=write_headers,
        )
        assert accept.status_code == 201
        assert accept.json()["data"]["user_action"] == "ACCEPTED"
        assert accept.json()["data"]["notes"] == "taking this"

        fetched = client.get("/api/v1/decisions/dec-journal-1/journal", headers=read_headers)
        assert fetched.json()["data"]["user_action"] == "ACCEPTED"

        # Outcome: entered within zone, exited at target 1 — pnl computed server-side
        outcome_resp = client.post(
            "/api/v1/decisions/dec-journal-1/outcome",
            json={
                "entry_price": "100.50",
                "exit_price": "104.00",
                "quantity": 10,
            },
            headers=write_headers,
        )
        assert outcome_resp.status_code == 201
        outcome = outcome_resp.json()["data"]
        assert outcome["pnl"] == "35.00"  # (104.00 - 100.50) * 10
        assert outcome["adherence"]["entered_within_zone"] is True
        assert outcome["adherence"]["hit_target"] is True
        assert outcome["adherence"]["hit_stop"] is False
        assert outcome["holding_seconds"] >= 0

        fetched_outcome = client.get(
            "/api/v1/decisions/dec-journal-1/outcome", headers=read_headers
        )
        assert fetched_outcome.json()["data"]["pnl"] == "35.00"

    def test_decision_journal_not_found(self, client) -> None:
        headers = get_auth_headers(client, Role.OPERATOR, username="operator2")
        response = client.post(
            "/api/v1/decisions/dec-nonexistent/journal",
            json={"user_action": "IGNORED"},
            headers=headers,
        )
        assert response.status_code == 404

    def test_get_decision_not_found(self, client) -> None:
        headers = get_auth_headers(client, Role.ANALYST)
        response = client.get("/api/v1/decisions/dec-invalid", headers=headers)
        assert response.status_code == 404
        assert response.json()["title"] == "Decision Not Found"

    def test_decision_analogs_ranking(self, client) -> None:
        """M-X1: nearest-neighbor retrieval, UNKNOWN fingerprints excluded,
        matches carry their logged journal response and realized outcome."""
        headers = get_auth_headers(client, Role.ANALYST)
        write_headers = get_auth_headers(client, Role.OPERATOR, username="operator3")
        dec_p = get_decision_provider()
        now = datetime.now(tz=timezone.utc)

        def _report(score, confidence, risk, *, unknown=False):
            if unknown:
                return {"score": {"status": "UNKNOWN"}}
            return {
                "score": {"status": "OK", "composite": str(score)},
                "confidence": {"status": "OK", "overall": str(confidence)},
                "risk": {"status": "OK", "overall": str(risk)},
            }

        specs = [
            ("dec-analog-target", "run-analog-t", 70, 80, 30, None),
            ("dec-analog-close", "run-analog-c", 72, 78, 32, None),
            ("dec-analog-far", "run-analog-f", 10, 20, 90, None),
            ("dec-analog-unknown", "run-analog-u", None, None, None, "unknown"),
        ]
        for decision_id, run_id, score, confidence, risk, mode in specs:
            dec_p.decisions.append(  # type: ignore[attr-defined]
                Decision(
                    decision_id=decision_id, ts=now, run_id=run_id, cycle_id="cycle-analog",
                    instrument_id="TCS", direction=Direction.NONE,
                    decision_type=DecisionType.WATCH, explanation="analog test",
                )
            )
            report = _report(score, confidence, risk, unknown=(mode == "unknown"))
            dec_p.run_details[run_id] = {  # type: ignore[attr-defined]
                "pipeline": {"decision_reports": {decision_id: report}}
            }

        # The close analog has a logged response + outcome
        client.post(
            "/api/v1/decisions/dec-analog-close/journal",
            json={"user_action": "ACCEPTED", "notes": "worked out"},
            headers=write_headers,
        )
        client.post(
            "/api/v1/decisions/dec-analog-close/outcome",
            json={"entry_price": "100.00", "exit_price": "105.00", "quantity": 5},
            headers=write_headers,
        )

        response = client.get(
            "/api/v1/decisions/dec-analog-target/analogs?limit=5", headers=headers
        )
        assert response.status_code == 200
        data = response.json()["data"]
        assert data["decision_id"] == "dec-analog-target"
        # unknown-fingerprint candidate excluded from comparison entirely
        assert data["compared_count"] == 2
        ids = [a["decision_id"] for a in data["analogs"]]
        assert "dec-analog-target" not in ids
        assert "dec-analog-unknown" not in ids
        # closest match ranks first
        assert ids[0] == "dec-analog-close"
        assert ids[1] == "dec-analog-far"
        assert float(data["analogs"][0]["distance"]) < float(data["analogs"][1]["distance"])
        close = data["analogs"][0]
        assert close["user_action"] == "ACCEPTED"
        assert close["outcome_pnl"] == "25.00"
        # UX-6: return % and holding days derived from the same persisted
        # entry/exit/quantity/holding_seconds — pnl 25.00 over a 500.00 cost
        # basis (entry 100 x qty 5) is an exact 5% return, never recomputed
        # pnl itself
        assert Decimal(close["outcome_return_pct"]) == Decimal("5.00")
        assert close["outcome_holding_days"] is not None
        far = data["analogs"][1]
        assert far["user_action"] is None
        assert far["outcome_pnl"] is None
        assert far["outcome_return_pct"] is None
        assert far["outcome_holding_days"] is None
        # Aggregate is computed only over the one analog with a logged
        # outcome ("close") — a 100% win rate and its own return/holding,
        # not fabricated for the "far" analog that has none
        assert data["outcomes_sample_size"] == 1
        assert Decimal(data["win_rate_pct"]) == Decimal("100.00")
        assert Decimal(data["avg_return_pct"]) == Decimal("5.00")
        assert data["avg_holding_days"] is not None
        # min/max holding reuse the exact same per-analog holding_days values
        # already averaged — with a single realized outcome, min == max ==
        # avg exactly (not a separately-derived number).
        assert Decimal(data["min_holding_days"]) == Decimal(data["avg_holding_days"])
        assert Decimal(data["max_holding_days"]) == Decimal(data["avg_holding_days"])

    def test_decision_analogs_aggregate_mixed_win_loss(self, client) -> None:
        """UX-6: win-rate/avg-return/avg-holding aggregate across analogs with
        a mix of winning and losing realized outcomes — exact arithmetic,
        never rounded to a fabricated round number."""
        headers = get_auth_headers(client, Role.ANALYST)
        write_headers = get_auth_headers(client, Role.OPERATOR, username="operator4")
        dec_p = get_decision_provider()
        now = datetime.now(tz=timezone.utc)

        def _report(score, confidence, risk):
            return {
                "score": {"status": "OK", "composite": str(score)},
                "confidence": {"status": "OK", "overall": str(confidence)},
                "risk": {"status": "OK", "overall": str(risk)},
            }

        specs = [
            ("dec-mix-target", "run-mix-t", 70, 80, 30),
            ("dec-mix-win", "run-mix-w", 71, 79, 31),
            ("dec-mix-loss", "run-mix-l", 69, 81, 29),
        ]
        for decision_id, run_id, score, confidence, risk in specs:
            dec_p.decisions.append(  # type: ignore[attr-defined]
                Decision(
                    decision_id=decision_id, ts=now, run_id=run_id, cycle_id="cycle-mix",
                    instrument_id="TCS", direction=Direction.NONE,
                    decision_type=DecisionType.WATCH, explanation="analog mix test",
                )
            )
            dec_p.run_details[run_id] = {  # type: ignore[attr-defined]
                "pipeline": {"decision_reports": {decision_id: _report(score, confidence, risk)}}
            }

        # Winner: entry 100 -> exit 110, qty 10 => pnl +100.00, return +10%.
        # Closed 3 days after the decision, so the aggregate's min/max holding
        # has a real, deterministic spread to assert on (rather than two
        # outcomes both closed "now", which would collapse to ~0 days apart).
        client.post(
            "/api/v1/decisions/dec-mix-win/outcome",
            json={
                "entry_price": "100.00", "exit_price": "110.00", "quantity": 10,
                "closed_ts": (now + timedelta(days=3)).isoformat(),
            },
            headers=write_headers,
        )
        # Loser: entry 100 -> exit 95, qty 10 => pnl -50.00, return -5%.
        # Closed 7 days after the decision.
        client.post(
            "/api/v1/decisions/dec-mix-loss/outcome",
            json={
                "entry_price": "100.00", "exit_price": "95.00", "quantity": 10,
                "closed_ts": (now + timedelta(days=7)).isoformat(),
            },
            headers=write_headers,
        )

        response = client.get(
            "/api/v1/decisions/dec-mix-target/analogs?limit=5", headers=headers
        )
        assert response.status_code == 200
        data = response.json()["data"]
        assert data["outcomes_sample_size"] == 2
        # One win out of two => 50% win rate
        assert Decimal(data["win_rate_pct"]) == Decimal("50.00")
        # Average of +10% and -5% => +2.5%
        assert Decimal(data["avg_return_pct"]) == Decimal("2.500")
        assert data["avg_holding_days"] is not None
        # min/max reuse the same per-analog holding_days already averaged —
        # a real 3-day/7-day spread across these two analogs, not a guess.
        # Exact (not approximate): closed_ts is an exact +3d/+7d offset of
        # the same `now`, so the day-count arithmetic has no rounding.
        assert Decimal(data["min_holding_days"]) == Decimal("3")
        assert Decimal(data["max_holding_days"]) == Decimal("7")

    def test_decision_analogs_unknown_target_returns_empty(self, client) -> None:
        headers = get_auth_headers(client, Role.ANALYST)
        dec_p = get_decision_provider()
        now = datetime.now(tz=timezone.utc)
        dec_p.decisions.append(  # type: ignore[attr-defined]
            Decision(
                decision_id="dec-analog-no-fp", ts=now, run_id="run-analog-no-fp",
                cycle_id="cycle-analog", instrument_id="TCS", direction=Direction.NONE,
                decision_type=DecisionType.INSUFFICIENT_DATA, explanation="no fingerprint",
            )
        )
        response = client.get(
            "/api/v1/decisions/dec-analog-no-fp/analogs", headers=headers
        )
        assert response.status_code == 200
        data = response.json()["data"]
        assert data["analogs"] == []
        assert data["compared_count"] == 0

    def test_reset_decisions_requires_confirmation_and_admin(self, client) -> None:
        """Decisions & Trace reset (owner-requested "Clear all" feature) is
        CONFIRM-gated and ADMIN-only, mirroring the existing portfolio reset
        pattern — refuses a wrong/missing token and a non-admin caller
        before ever touching data."""
        dec_p = get_decision_provider()
        now = datetime.now(tz=timezone.utc)
        dec_p.decisions.append(  # type: ignore[attr-defined]
            Decision(
                decision_id="dec-reset-1", ts=now, run_id="run-reset-1",
                cycle_id="cycle-reset", instrument_id="TCS", direction=Direction.NONE,
                decision_type=DecisionType.WATCH, explanation="reset test",
            )
        )

        admin_headers = get_auth_headers(client, Role.ADMIN)
        operator_headers = get_auth_headers(client, Role.OPERATOR, username="operator-reset")

        wrong_token = client.post(
            "/api/v1/decisions/reset", headers=admin_headers, json={"confirmation": "YES"}
        )
        assert wrong_token.status_code == 400
        assert dec_p.decisions  # untouched

        forbidden = client.post(
            "/api/v1/decisions/reset", headers=operator_headers, json={"confirmation": "CONFIRM"}
        )
        assert forbidden.status_code == 403
        assert dec_p.decisions  # untouched

    def test_reset_decisions_clears_domain_after_confirmation(self, client) -> None:
        dec_p = get_decision_provider()
        now = datetime.now(tz=timezone.utc)
        dec_p.decisions.append(  # type: ignore[attr-defined]
            Decision(
                decision_id="dec-reset-2", ts=now, run_id="run-reset-2",
                cycle_id="cycle-reset", instrument_id="INFY", direction=Direction.NONE,
                decision_type=DecisionType.WATCH, explanation="reset test 2",
            )
        )
        dec_p.traces["dec-reset-2"] = DecisionTrace(  # type: ignore[attr-defined]
            decision_ref="dec-reset-2",
            stages=(TraceStage("decision", ("dec-reset-2",), "composed"),),
        )

        headers = get_auth_headers(client, Role.ADMIN)
        ok = client.post(
            "/api/v1/decisions/reset", headers=headers, json={"confirmation": "CONFIRM"}
        )
        assert ok.status_code == 200
        data = ok.json()["data"]
        assert data["total_deleted"] >= 2  # at least the decision + its trace
        assert data["deleted_counts"]["decisions"] >= 1
        assert data["deleted_counts"]["decision_traces"] >= 1

        assert dec_p.decisions == []  # type: ignore[attr-defined]
        assert dec_p.traces == {}  # type: ignore[attr-defined]

        listing = client.get("/api/v1/decisions", headers=headers)
        assert listing.status_code == 200
        assert listing.json()["data"] == []

    def test_counterfactual_already_trade(self, client) -> None:
        headers = get_auth_headers(client, Role.ANALYST)
        dec_p = get_decision_provider()
        now = datetime.now(tz=timezone.utc)
        plan = TradePlan(
            entry_low=Decimal("100"), entry_high=Decimal("101"), stop_loss=Decimal("98"),
            targets=(Decimal("104"),), position_size=10, risk_amount=Decimal("20"),
            risk_reward=Decimal("2"), valid_from=now, valid_until=now + timedelta(hours=1),
        )
        dec_p.decisions.append(  # type: ignore[attr-defined]
            Decision(
                decision_id="dec-cf-trade", ts=now, run_id="run-cf-trade", cycle_id="c",
                instrument_id="TCS", direction=Direction.LONG, decision_type=DecisionType.TRADE,
                explanation="trade", trade_plan=plan,
                gate_results=(GateResult(QualityGate.CONFIDENCE, True, "ok"),),
            )
        )
        response = client.get(
            "/api/v1/decisions/dec-cf-trade/counterfactual", headers=headers
        )
        assert response.status_code == 200
        data = response.json()["data"]
        assert data["is_trade"] is True
        assert "Already a TRADE" in data["summary"]
        assert data["gates"] == []

    def test_counterfactual_quantifies_confidence_and_risk_gap(self, client) -> None:
        headers = get_auth_headers(client, Role.ANALYST)
        dec_p = get_decision_provider()
        now = datetime.now(tz=timezone.utc)
        dec_p.decisions.append(  # type: ignore[attr-defined]
            Decision(
                decision_id="dec-cf-watch", ts=now, run_id="run-cf-watch", cycle_id="c",
                instrument_id="TCS", direction=Direction.NONE, decision_type=DecisionType.WATCH,
                explanation="watch",
                gate_results=(
                    GateResult(QualityGate.DATA, True, "ok"),
                    GateResult(QualityGate.EVIDENCE, True, "ok"),
                    GateResult(QualityGate.RISK, False, "risk 65.0 vs max 60"),
                    GateResult(QualityGate.EXPLAINABILITY, True, "ok"),
                    GateResult(QualityGate.CONFIDENCE, False, "confidence 40.0 vs min 50"),
                    GateResult(QualityGate.MARKET, True, "ok"),
                ),
            )
        )
        dec_p.run_details["run-cf-watch"] = {  # type: ignore[attr-defined]
            "pipeline": {
                "decision_reports": {
                    "dec-cf-watch": {
                        "score": {
                            "status": "OK", "composite": "56.0", "completeness": "0.9",
                            "components": [
                                {"dimension": "market_quality", "value": "62.0"},
                            ],
                        },
                        "confidence": {"status": "OK", "overall": "40.0"},
                        "risk": {"status": "OK", "overall": "65.0"},
                    }
                }
            }
        }
        response = client.get(
            "/api/v1/decisions/dec-cf-watch/counterfactual", headers=headers
        )
        assert response.status_code == 200
        data = response.json()["data"]
        assert data["is_trade"] is False
        # 60 (min_composite_for_trade) - 56.0 — Decimal arithmetic keeps 1dp here
        assert data["score_gap"] == "4.0"
        gates_by_name = {g["gate"]: g for g in data["gates"]}
        assert set(gates_by_name) == {"RISK", "CONFIDENCE"}
        assert gates_by_name["CONFIDENCE"]["current"] == "40.0"
        assert gates_by_name["CONFIDENCE"]["gap"] == "10.0"  # 50 - 40
        assert gates_by_name["RISK"]["current"] == "65.0"
        assert gates_by_name["RISK"]["gap"] == "5.0"  # 65 - 60
        # Summary text explicitly formats to 2dp regardless of stored precision
        assert "confidence +10.00" in data["summary"]
        assert "risk -5.00" in data["summary"]

    def test_counterfactual_direction_blocker_when_no_numeric_gap(self, client) -> None:
        """All gates pass and score clears the trade level, but no trend
        direction was determined — must surface as the real blocker, not a
        false 'no gap' result."""
        headers = get_auth_headers(client, Role.ANALYST)
        dec_p = get_decision_provider()
        now = datetime.now(tz=timezone.utc)
        dec_p.decisions.append(  # type: ignore[attr-defined]
            Decision(
                decision_id="dec-cf-nodir", ts=now, run_id="run-cf-nodir", cycle_id="c",
                instrument_id="TCS", direction=Direction.NONE, decision_type=DecisionType.WATCH,
                explanation="watch",
                gate_results=tuple(
                    GateResult(gate, True, "ok") for gate in QualityGate
                ),
            )
        )
        dec_p.run_details["run-cf-nodir"] = {  # type: ignore[attr-defined]
            "pipeline": {
                "decision_reports": {
                    "dec-cf-nodir": {
                        "score": {"status": "OK", "composite": "75.0", "completeness": "1.0",
                                  "components": []},
                        "confidence": {"status": "OK", "overall": "80.0"},
                        "risk": {"status": "OK", "overall": "10.0"},
                    }
                }
            }
        }
        response = client.get(
            "/api/v1/decisions/dec-cf-nodir/counterfactual", headers=headers
        )
        assert response.status_code == 200
        data = response.json()["data"]
        assert data["score_gap"] == "0"
        assert len(data["gates"]) == 1
        assert data["gates"][0]["gate"] == "DIRECTION"
        assert "no clear trend direction" in data["gates"][0]["detail"]

    def test_plan_freshness_no_trade_plan(self, client) -> None:
        headers = get_auth_headers(client, Role.ANALYST)
        dec_p = get_decision_provider()
        now = datetime.now(tz=timezone.utc)
        dec_p.decisions.append(  # type: ignore[attr-defined]
            Decision(
                decision_id="dec-fresh-noplan", ts=now, run_id="run-fresh-noplan", cycle_id="c",
                instrument_id="TCS", direction=Direction.NONE, decision_type=DecisionType.WATCH,
                explanation="watch",
                gate_results=(GateResult(QualityGate.CONFIDENCE, False, "confidence low"),),
            )
        )
        response = client.get(
            "/api/v1/decisions/dec-fresh-noplan/plan-freshness", headers=headers
        )
        assert response.status_code == 200
        data = response.json()["data"]
        assert data["has_trade_plan"] is False
        assert data["status"] == "NO_PLAN"
        assert data["decay_fraction"] is None

    def test_plan_freshness_decay_bands_via_as_of(self, client) -> None:
        """Same 100-minute validity window, four as_of instants — one per
        deterministic decay band. Never a wall-clock read inside the engine;
        the decay is exact arithmetic over persisted valid_from/valid_until
        and the caller-supplied as_of."""
        headers = get_auth_headers(client, Role.ANALYST)
        dec_p = get_decision_provider()
        valid_from = datetime(2026, 7, 25, 9, 15, tzinfo=timezone.utc)
        valid_until = valid_from + timedelta(minutes=100)
        plan = TradePlan(
            entry_low=Decimal("100"), entry_high=Decimal("101"), stop_loss=Decimal("98"),
            targets=(Decimal("104"),), position_size=10, risk_amount=Decimal("20"),
            risk_reward=Decimal("2"), valid_from=valid_from, valid_until=valid_until,
        )
        dec_p.decisions.append(  # type: ignore[attr-defined]
            Decision(
                decision_id="dec-fresh-plan", ts=valid_from, run_id="run-fresh-plan", cycle_id="c",
                instrument_id="TCS", direction=Direction.NONE, decision_type=DecisionType.WATCH,
                explanation="watch", trade_plan=plan,
                gate_results=(GateResult(QualityGate.CONFIDENCE, False, "confidence low"),),
            )
        )

        def freshness_at(offset_minutes: int) -> dict:
            as_of = quote((valid_from + timedelta(minutes=offset_minutes)).isoformat())
            response = client.get(
                f"/api/v1/decisions/dec-fresh-plan/plan-freshness?as_of={as_of}",
                headers=headers,
            )
            assert response.status_code == 200
            return response.json()["data"]

        fresh = freshness_at(10)
        assert fresh["status"] == "FRESH"
        assert fresh["decay_fraction"] == "0.1"
        assert fresh["total_seconds"] == 6000
        assert fresh["remaining_seconds"] == 5400

        aging = freshness_at(60)
        assert aging["status"] == "AGING"
        assert aging["decay_fraction"] == "0.6"

        stale = freshness_at(90)
        assert stale["status"] == "STALE"
        assert stale["decay_fraction"] == "0.9"

        expired = freshness_at(150)
        assert expired["status"] == "EXPIRED"
        assert "EXPIRED" in expired["summary"]

    def test_plan_freshness_not_found(self, client) -> None:
        headers = get_auth_headers(client, Role.ANALYST)
        response = client.get(
            "/api/v1/decisions/dec-invalid/plan-freshness", headers=headers
        )
        assert response.status_code == 404


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

