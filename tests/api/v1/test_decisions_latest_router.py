"""GET /decisions/latest router test (owner-reported, 2026-08-10): the
Decisions & Trace dashboard only ever needs one current decision per
instrument, so it should be able to ask for exactly that instead of
paginating through the full historical event log. Uses an isolated
tmp_path repo (never the real db/athena.db — see
test_decisions_instrument_name.py for why that matters here)."""

from __future__ import annotations

from dataclasses import replace
from datetime import datetime, timedelta, timezone

from fastapi.testclient import TestClient
from tests.api.v1.test_core_apis import get_auth_headers

from athena.api.security.models import Role
from athena.data.store.repository import SqliteRepository
from athena.domain.decision import Decision
from athena.domain.enums import DecisionType, Direction


def _decision(decision_id: str, instrument_id: str, ts: datetime) -> Decision:
    return Decision(
        decision_id=decision_id,
        ts=ts,
        run_id="run-1",
        cycle_id="cycle-1",
        decision_type=DecisionType.WATCH,
        explanation="latest-by-instrument router test",
        instrument_id=instrument_id,
        direction=Direction.NONE,
    )


def test_latest_decisions_requires_auth(client: TestClient) -> None:
    response = client.get("/api/v1/decisions/latest")
    assert response.status_code == 401


def test_latest_decisions_returns_one_per_instrument(
    client: TestClient, tmp_path
) -> None:
    repo = SqliteRepository(tmp_path / "router-latest.db")
    repo.initialize()
    now = datetime.now(tz=timezone.utc)
    older = _decision("dec-aaa-older", "SYN-AAA", now - timedelta(minutes=5))
    newer = replace(older, decision_id="dec-aaa-newer", ts=now)
    other = _decision("dec-bbb", "SYN-BBB", now)
    for d in (older, newer, other):
        repo.save_decision(d)
    client.app.state.sqlite_repo = repo

    headers = get_auth_headers(client, Role.READONLY)
    response = client.get("/api/v1/decisions/latest", headers=headers)
    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "success"
    by_instrument = {row["metadata"]["instrument_id"]: row["metadata"]["decision_id"] for row in payload["data"]}
    assert by_instrument == {"SYN-AAA": "dec-aaa-newer", "SYN-BBB": "dec-bbb"}
    repo.close()


def test_latest_decisions_empty_repo_returns_empty_list(
    client: TestClient, tmp_path
) -> None:
    repo = SqliteRepository(tmp_path / "router-latest-empty.db")
    repo.initialize()
    client.app.state.sqlite_repo = repo

    headers = get_auth_headers(client, Role.READONLY)
    response = client.get("/api/v1/decisions/latest", headers=headers)
    assert response.status_code == 200
    assert response.json()["data"] == []
    repo.close()
