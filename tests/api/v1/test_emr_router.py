"""EM-6B: GET /emr/experimental/touch-10-radar router tests.

Every test injects `client.app.state.emr_db_path` to point at an isolated
tmp_path fixture database (never the real `db/emr.db`), seeded via the
real, already-tested `EmrRepository` write side. Also covers the isolation
(no canonical/DarvaX import) and read-only-mutation proofs required for
the API layer specifically -- distinct from EM-6A's own module-level
proofs, which this reuses transitively but does not duplicate.
"""

from __future__ import annotations

import os

from fastapi.testclient import TestClient
from tests.api.v1.test_core_apis import get_auth_headers

from athena.api.security.models import Role
from athena.explosive_move.store.repository import EmrRepository

ENDPOINT = "/api/v1/emr/experimental/touch-10-radar"


def _repo(tmp_path) -> EmrRepository:
    repo = EmrRepository(tmp_path / "emr.db")
    repo.initialize()
    return repo


def _scan_run(run_id: str = "run-1", **overrides) -> dict:
    base = {
        "run_id": run_id, "session_date": "2026-08-28", "checkpoint": "12:00",
        "frozen_model_version": "v1", "status": "COMPLETE",
        "started_ts": "2026-08-28T12:00:00+05:30", "finished_ts": "2026-08-28T12:00:05+05:30",
        "eligible_count": 2, "ineligible_count": 1,
    }
    base.update(overrides)
    return base


def _candidate(**overrides) -> dict:
    base = {
        "run_id": "run-1", "instrument_id": "NSE:INFY", "family": "TOUCH", "threshold_percent": 10,
        "checkpoint": "12:00", "session_date": "2026-08-28", "rank": 1, "raw_logit": -1.2,
        "raw_logistic_estimate": 0.05, "calibrated_probability": 0.05,
        "probability_language": "calibrated_probability",
        "em4b_model_version": "em4b-v1", "em4d_calibration_version": "em4d-v1",
        "evidence_timestamp": "2026-08-28T12:00:02+05:30", "evidence_completeness_known": 22,
        "evidence_completeness_total": 22, "freshness": "FRESH", "feasibility": "FEASIBLE",
        "state": "WATCH", "state_reason": "rank <= 20",
    }
    base.update(overrides)
    return base


def test_requires_auth(client: TestClient) -> None:
    response = client.get(ENDPOINT)
    assert response.status_code == 401


# --------------------------------------------------------------------------- #
# 1/2. Missing db/emr.db / no COMPLETE scan
# --------------------------------------------------------------------------- #


def test_missing_db_file_returns_honest_empty_state(client: TestClient, tmp_path) -> None:
    client.app.state.emr_db_path = tmp_path / "does-not-exist.db"
    headers = get_auth_headers(client, Role.READONLY)

    response = client.get(ENDPOINT, headers=headers)
    assert response.status_code == 200
    data = response.json()["data"]
    assert data["scan"] is None
    assert data["scan_age"] is None
    assert data["touch_10"] == []
    assert data["coverage"] is None
    assert data["label"]
    assert "not a trade recommendation" in data["disclaimer"].lower() or "no completed" in data["disclaimer"].lower()


def test_initialized_but_no_complete_scan_returns_empty_state(client: TestClient, tmp_path) -> None:
    repo = _repo(tmp_path)
    client.app.state.emr_db_path = repo.path
    headers = get_auth_headers(client, Role.READONLY)

    response = client.get(ENDPOINT, headers=headers)
    assert response.status_code == 200
    data = response.json()["data"]
    assert data["scan"] is None
    assert data["touch_10"] == []


# --------------------------------------------------------------------------- #
# 3/4. Coherent COMPLETE scan / ranked candidates
# --------------------------------------------------------------------------- #


def test_coherent_scan_with_ranked_candidates(client: TestClient, tmp_path) -> None:
    repo = _repo(tmp_path)
    repo.save_scan_run(_scan_run())
    repo.save_candidates([
        _candidate(instrument_id="NSE:INFY", rank=1),
        _candidate(instrument_id="NSE:TCS", rank=2),
    ])
    client.app.state.emr_db_path = repo.path
    headers = get_auth_headers(client, Role.READONLY)

    response = client.get(ENDPOINT, headers=headers)
    assert response.status_code == 200
    data = response.json()["data"]
    assert data["scan"]["run_id"] == "run-1"
    assert data["scan"]["session_date"] == "2026-08-28"
    assert data["scan"]["checkpoint"] == "12:00"
    assert [c["instrument_id"] for c in data["touch_10"]] == ["NSE:INFY", "NSE:TCS"]
    assert data["scan_age"] is not None
    assert data["scan_age"]["age_seconds"] >= 0


# --------------------------------------------------------------------------- #
# 5. Zero ranked candidates in an otherwise-complete scan
# --------------------------------------------------------------------------- #


def test_complete_scan_with_zero_ranked_candidates(client: TestClient, tmp_path) -> None:
    repo = _repo(tmp_path)
    repo.save_scan_run(_scan_run())
    repo.save_candidates([
        _candidate(instrument_id="NSE:INELIGIBLE", rank=None, feasibility="INFEASIBLE",
                    feasibility_reason="STALE_DATA", state="INACTIVE", state_reason="hard ineligible"),
    ])
    client.app.state.emr_db_path = repo.path
    headers = get_auth_headers(client, Role.READONLY)

    response = client.get(ENDPOINT, headers=headers)
    assert response.status_code == 200
    data = response.json()["data"]
    assert data["scan"] is not None  # a scan DID complete
    assert data["touch_10"] == []  # but nothing ranked
    assert data["coverage"]["evaluated_count"] == 1
    assert data["coverage"]["ranked_count"] == 0
    assert data["coverage"]["unranked_count"] == 1


# --------------------------------------------------------------------------- #
# 6. Coverage data
# --------------------------------------------------------------------------- #


def test_coverage_reflects_ranked_and_unranked_with_reasons(client: TestClient, tmp_path) -> None:
    repo = _repo(tmp_path)
    repo.save_scan_run(_scan_run())
    repo.save_candidates([
        _candidate(instrument_id="NSE:RANKED", rank=1),
        _candidate(instrument_id="NSE:STALE", rank=None, feasibility="INFEASIBLE",
                    feasibility_reason="STALE_DATA", state="INACTIVE", state_reason="hard ineligible"),
    ])
    client.app.state.emr_db_path = repo.path
    headers = get_auth_headers(client, Role.READONLY)

    response = client.get(ENDPOINT, headers=headers)
    coverage = response.json()["data"]["coverage"]
    assert coverage["evaluated_count"] == 2
    assert coverage["ranked_count"] == 1
    assert coverage["unranked_count"] == 1
    reasons = dict(coverage["unranked_reason_counts"])
    assert reasons["STALE_DATA"] == 1


# --------------------------------------------------------------------------- #
# 7. Null calibrated probability
# --------------------------------------------------------------------------- #


def test_null_calibrated_probability_is_preserved_not_zeroed(client: TestClient, tmp_path) -> None:
    repo = _repo(tmp_path)
    repo.save_scan_run(_scan_run())
    repo.save_candidates([_candidate(instrument_id="NSE:UNKNOWNPROB", rank=1, calibrated_probability=None)])
    client.app.state.emr_db_path = repo.path
    headers = get_auth_headers(client, Role.READONLY)

    response = client.get(ENDPOINT, headers=headers)
    candidate = response.json()["data"]["touch_10"][0]
    assert candidate["calibrated_probability"] is None


# --------------------------------------------------------------------------- #
# 8. Timestamp/timezone preservation
# --------------------------------------------------------------------------- #


def test_timezone_aware_timestamps_are_preserved_verbatim(client: TestClient, tmp_path) -> None:
    repo = _repo(tmp_path)
    repo.save_scan_run(_scan_run(started_ts="2026-08-28T12:00:00+05:30", finished_ts="2026-08-28T12:00:05+05:30"))
    client.app.state.emr_db_path = repo.path
    headers = get_auth_headers(client, Role.READONLY)

    response = client.get(ENDPOINT, headers=headers)
    scan = response.json()["data"]["scan"]
    assert scan["started_ts"] == "2026-08-28T12:00:00+05:30"
    assert scan["finished_ts"] == "2026-08-28T12:00:05+05:30"


# --------------------------------------------------------------------------- #
# 9/10. One-response/one-run coherence; no cross-scan mixing
# --------------------------------------------------------------------------- #


def test_response_never_mixes_two_scan_runs(client: TestClient, tmp_path) -> None:
    repo = _repo(tmp_path)
    repo.save_scan_run(_scan_run(run_id="run-old", started_ts="2026-08-28T09:00:00+05:30"))
    repo.save_scan_run(_scan_run(run_id="run-new", started_ts="2026-08-28T14:00:00+05:30"))
    repo.save_candidates([_candidate(run_id="run-old", instrument_id="NSE:OLD", rank=1)])
    repo.save_candidates([_candidate(run_id="run-new", instrument_id="NSE:NEW", rank=1)])
    client.app.state.emr_db_path = repo.path
    headers = get_auth_headers(client, Role.READONLY)

    response = client.get(ENDPOINT, headers=headers)
    data = response.json()["data"]
    assert data["scan"]["run_id"] == "run-new"
    assert [c["instrument_id"] for c in data["touch_10"]] == ["NSE:NEW"]


# --------------------------------------------------------------------------- #
# 11. Read-only behavior
# --------------------------------------------------------------------------- #


def test_endpoint_never_mutates_the_database(client: TestClient, tmp_path) -> None:
    repo = _repo(tmp_path)
    repo.save_scan_run(_scan_run())
    repo.save_candidates([_candidate(instrument_id="NSE:INFY", rank=1)])
    repo.close()

    before_mtime = os.path.getmtime(repo.path)
    before_size = os.path.getsize(repo.path)
    client.app.state.emr_db_path = repo.path
    headers = get_auth_headers(client, Role.READONLY)

    for _ in range(3):
        response = client.get(ENDPOINT, headers=headers)
        assert response.status_code == 200

    assert os.path.getmtime(repo.path) == before_mtime
    assert os.path.getsize(repo.path) == before_size


# --------------------------------------------------------------------------- #
# 12. No provider call
# --------------------------------------------------------------------------- #


def test_router_and_service_source_have_no_provider_or_scanner_calls() -> None:
    import inspect

    from athena.api.v1.routers import emr as emr_router_module
    from athena.api.v1.services import emr_presentation_service as emr_service_module

    for module in (emr_router_module, emr_service_module):
        source = inspect.getsource(module)
        lowered = source.lower()
        assert not any(term in lowered for term in ("kite", "requests.", "httpx.", "urllib.request"))
        assert "run_scan_cycle(" not in source


# --------------------------------------------------------------------------- #
# 13/14. No canonical Decision/EntryQualification/DarvaX dependency
# --------------------------------------------------------------------------- #


def test_router_and_service_import_nothing_canonical_or_darvax() -> None:
    """Checks actual import statements (AST), not any string occurrence --
    both modules' own docstrings legitimately *name* forbidden modules to
    document the isolation boundary, which must not itself trip this
    check."""
    import ast
    import inspect

    from athena.api.v1.routers import emr as emr_router_module
    from athena.api.v1.services import emr_presentation_service as emr_service_module

    forbidden_prefixes = (
        "athena.scoring", "athena.decision", "athena.risk", "athena.trade_plan",
        "athena.darvax", "athena.data.store.repository", "athena.intraday",
        "athena.intraday.entry_qualification", "athena.portfolio",
    )
    for module in (emr_router_module, emr_service_module):
        tree = ast.parse(inspect.getsource(module))
        imported_names = []
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                imported_names.extend(a.name for a in node.names)
            elif isinstance(node, ast.ImportFrom) and node.module:
                imported_names.append(node.module)
        for name in imported_names:
            for prefix in forbidden_prefixes:
                assert not name.startswith(prefix), (
                    f"{module.__name__} imports forbidden module: {name}"
                )


def test_response_never_includes_canonical_terminology(client: TestClient, tmp_path) -> None:
    """No trade-authorizing or canonical-Decision language anywhere in a
    populated response body."""
    repo = _repo(tmp_path)
    repo.save_scan_run(_scan_run())
    repo.save_candidates([_candidate(instrument_id="NSE:INFY", rank=1)])
    client.app.state.emr_db_path = repo.path
    headers = get_auth_headers(client, Role.READONLY)

    response = client.get(ENDPOINT, headers=headers)
    body_text = response.text.upper()
    forbidden_terms = (
        "BUY", "SELL", "STRONG BUY", "TRADE CONFIRMED", "ACTIONABLE TRADE",
        "ENTRY PRICE", "STOP LOSS", "TARGET PRICE", "POSITION SIZE", "RISK/REWARD",
    )
    for term in forbidden_terms:
        assert term not in body_text, f"forbidden trade-authorizing term found: {term}"


# --------------------------------------------------------------------------- #
# 15. Storage failure follows real error semantics (not silently "no candidates")
# --------------------------------------------------------------------------- #


def test_corrupt_database_is_a_real_error_not_a_silent_empty_state(client: TestClient, tmp_path) -> None:
    corrupt = tmp_path / "corrupt.db"
    corrupt.write_bytes(b"this is not a valid sqlite file")
    client.app.state.emr_db_path = corrupt
    headers = get_auth_headers(client, Role.READONLY)

    response = client.get(ENDPOINT, headers=headers)
    # A malformed (but existing) file must not be silently reported as
    # "no completed scan" -- it must surface as a real error.
    assert response.status_code >= 500


# --------------------------------------------------------------------------- #
# request_date query param
# --------------------------------------------------------------------------- #


def test_session_date_query_param_scopes_the_scan(client: TestClient, tmp_path) -> None:
    repo = _repo(tmp_path)
    repo.save_scan_run(_scan_run(run_id="run-yesterday", session_date="2026-08-27",
                                  started_ts="2026-08-27T14:00:00+05:30"))
    repo.save_scan_run(_scan_run(run_id="run-today", session_date="2026-08-28",
                                  started_ts="2026-08-28T09:30:00+05:30"))
    client.app.state.emr_db_path = repo.path
    headers = get_auth_headers(client, Role.READONLY)

    response = client.get(f"{ENDPOINT}?session_date=2026-08-27", headers=headers)
    assert response.json()["data"]["scan"]["run_id"] == "run-yesterday"
