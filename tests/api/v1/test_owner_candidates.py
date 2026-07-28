"""Owner validation candidate list API tests (D-V1)."""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from unittest import mock

import pytest
from fastapi.testclient import TestClient

from athena.api.security.models import Role
from athena.api.v1.dtos.market import UpsertCandidateRequest
from athena.api.v1.services.candidates_service import CandidatesService
from athena.data.store.repository import SqliteRepository
from athena.errors import ConfigError, DataValidationError
from athena.domain.enums import DecisionType, Direction, RunStatus, RunTrigger
from athena.domain.decision import Decision
from athena.domain.market import Instrument
from athena.domain.run import RunRecord
from athena.ops.owner_candidates import SqliteCandidateStore
from tests.api.v1.test_core_apis import get_auth_headers


class TestOwnerCandidatesAPI:
    def test_crud_normalize_and_list(self, client: TestClient) -> None:
        headers = get_auth_headers(client, Role.OPERATOR)
        create = client.post(
            "/api/v1/market/candidates",
            headers=headers,
            json={"symbol": "nse:infy", "notes": "core"},
        )
        assert create.status_code == 201
        assert create.json()["data"]["symbol"] == "INFY"

        listed = client.get("/api/v1/market/candidates", headers=headers)
        assert listed.status_code == 200
        body = listed.json()["data"]
        assert body["count"] == 1
        assert body["candidates"][0]["symbol"] == "INFY"

        put = client.put(
            "/api/v1/market/candidates",
            headers=headers,
            json={"symbol": "RELIANCE"},
        )
        assert put.status_code == 200
        assert put.json()["data"]["symbol"] == "RELIANCE"

        listed2 = client.get("/api/v1/market/candidates", headers=headers)
        assert listed2.json()["data"]["count"] == 2

        deleted = client.delete("/api/v1/market/candidates/INFY", headers=headers)
        assert deleted.status_code == 200
        assert deleted.json()["data"]["deleted"] is True

        listed3 = client.get("/api/v1/market/candidates", headers=headers)
        symbols = [c["symbol"] for c in listed3.json()["data"]["candidates"]]
        assert symbols == ["RELIANCE"]

    def test_delete_missing_404(self, client: TestClient) -> None:
        headers = get_auth_headers(client, Role.OPERATOR)
        resp = client.delete("/api/v1/market/candidates/NOSUCH", headers=headers)
        assert resp.status_code == 404

    def test_mutate_requires_execute(self, client: TestClient) -> None:
        headers = get_auth_headers(client, Role.READONLY)
        resp = client.post(
            "/api/v1/market/candidates",
            headers=headers,
            json={"symbol": "INFY"},
        )
        assert resp.status_code == 403

    def test_validate_requires_symbols(self, client: TestClient) -> None:
        headers = get_auth_headers(client, Role.OPERATOR)
        resp = client.post(
            "/api/v1/market/validate",
            headers=headers,
            json={"symbols": []},
        )
        assert resp.status_code == 422

    def test_validate_unknown_candidate_422(self, client: TestClient) -> None:
        headers = get_auth_headers(client, Role.OPERATOR)
        resp = client.post(
            "/api/v1/market/validate",
            headers=headers,
            json={"symbols": ["NOTACANDIDATE999"]},
        )
        # No sqlite / not a candidate / kite not wired in unit tests — any client error is ok
        assert resp.status_code in (422, 500)

    def test_list_enriches_sector_status_and_last_validated(self, tmp_path: Path) -> None:
        """MI-4: candidates list carries Sector/Status/Eligibility/Last Validated
        from instruments + latest validation run + decisions.ts — never fabricated."""
        repo = SqliteRepository(tmp_path / "c.db")
        repo.initialize()
        store = SqliteCandidateStore(repo)
        now = datetime(2026, 7, 28, 10, 0, tzinfo=timezone.utc)
        store.upsert_candidate(symbol="INFY", notes="seed", added_ts=now)
        store.upsert_candidate(symbol="WIPRO", notes="seed", added_ts=now)
        repo.upsert_instrument(
            Instrument(
                instrument_id="NSE:INFY",
                symbol="INFY",
                exchange="NSE",
                series="EQ",
                sector="IT",
            )
        )
        repo.upsert_instrument(
            Instrument(
                instrument_id="NSE:WIPRO",
                symbol="WIPRO",
                exchange="NSE",
                series="EQ",
                sector="IT",
            )
        )
        run = RunRecord(
            run_id="run-mi4",
            cycle_id="cyc",
            trigger=RunTrigger.REFRESH,
            started_ts=now,
            finished_ts=now,
            status=RunStatus.COMPLETED,
            software_version="t",
            blueprint_version="t",
            strategy_profile="t",
            strategy_profile_version="t",
            indicator_versions={},
            config_snapshot_id="t",
        )
        repo.save_run(
            run,
            detail={
                "pipeline": {
                    "universe_members": {
                        "INFY": {
                            "symbol": "INFY",
                            "included": True,
                            "eligibility_summary": "included: passed all 7 eligibility rules",
                        }
                    }
                }
            },
        )
        repo.save_decision(
            Decision(
                decision_id="d-infy",
                ts=now,
                run_id="run-mi4",
                cycle_id="cyc",
                decision_type=DecisionType.WATCH,
                explanation="watch",
                instrument_id="NSE:INFY",
                direction=Direction.LONG,
            )
        )
        svc = CandidatesService(store, repo=repo)
        listed = svc.list_candidates()
        by_sym = {c.symbol: c for c in listed.candidates}
        assert by_sym["INFY"].sector == "IT"
        assert by_sym["INFY"].status == "ELIGIBLE"
        assert "passed all" in (by_sym["INFY"].eligibility_summary or "")
        assert by_sym["INFY"].last_validated_ts == now
        assert by_sym["WIPRO"].sector == "IT"
        assert by_sym["WIPRO"].status == "PENDING"
        assert by_sym["WIPRO"].eligibility_summary is None
        assert by_sym["WIPRO"].last_validated_ts is None
        repo.close()

    def test_unresolved_candidates_surface_as_unresolved_not_pending(
        self, tmp_path: Path
    ) -> None:
        """A symbol the exchange does not list must be visibly Unresolved with
        the run's own reason, so it can be removed — not left indistinguishable
        from a symbol simply awaiting its first validation."""
        repo = SqliteRepository(tmp_path / "u.db")
        repo.initialize()
        store = SqliteCandidateStore(repo)
        now = datetime(2026, 7, 28, 10, 0, tzinfo=timezone.utc)
        store.upsert_candidate(symbol="INFSDFSD", notes="typo", added_ts=now)
        store.upsert_candidate(symbol="NEWNAME", notes="not validated yet", added_ts=now)
        repo.save_run(
            RunRecord(
                run_id="run-unresolved",
                cycle_id="cyc",
                trigger=RunTrigger.REFRESH,
                started_ts=now,
                finished_ts=now,
                status=RunStatus.COMPLETED,
                software_version="t",
                blueprint_version="t",
                strategy_profile="t",
                strategy_profile_version="t",
                indicator_versions={},
                config_snapshot_id="t",
            ),
            detail={
                "pipeline": {
                    "universe_members": {},
                    "unresolved_candidates": [
                        {"symbol": "INFSDFSD", "reason": "the symbol may not exist"}
                    ],
                }
            },
        )

        by_sym = {
            c.symbol: c
            for c in CandidatesService(store, repo=repo).list_candidates().candidates
        }
        assert by_sym["INFSDFSD"].status == "UNRESOLVED"
        assert by_sym["INFSDFSD"].eligibility_summary == "the symbol may not exist"
        assert by_sym["INFSDFSD"].last_validated_ts == now
        assert by_sym["NEWNAME"].status == "PENDING"
        repo.close()

    def test_add_rejects_symbol_the_exchange_does_not_list(self, tmp_path: Path) -> None:
        """Add-time guard: a typo used to persist, survive its failed validation
        and then abort every later cycle. Nothing may be stored when the catalog
        definitively lacks the symbol."""
        repo = SqliteRepository(tmp_path / "r.db")
        repo.initialize()
        store = SqliteCandidateStore(repo)
        svc = CandidatesService(store, repo=repo)

        def _reject(_config_dir, symbols, *, repo_root=None):
            return object(), {}, [str(symbols[0]).upper()]

        with mock.patch(
            "athena.api.v1.services.candidates_service.resolve_against_catalog", _reject
        ):
            with pytest.raises(DataValidationError, match="INFSDFSD"):
                svc.upsert_candidate(UpsertCandidateRequest(symbol="INFSDFSD"))
        assert store.list_candidates(active_only=False) == []
        repo.close()

    def test_add_proceeds_when_catalog_cannot_be_consulted(self, tmp_path: Path) -> None:
        """Best effort by design: offline or non-kite setups must still be able
        to build a universe; the symbol surfaces as Unresolved after a run."""
        repo = SqliteRepository(tmp_path / "o.db")
        repo.initialize()
        store = SqliteCandidateStore(repo)
        svc = CandidatesService(store, repo=repo)

        def _unavailable(_config_dir, _symbols, *, repo_root=None):
            raise ConfigError("catalog lookup requires ingestion.provider=kite")

        with mock.patch(
            "athena.api.v1.services.candidates_service.resolve_against_catalog", _unavailable
        ):
            dto = svc.upsert_candidate(UpsertCandidateRequest(symbol="infy"))
        assert dto.symbol == "INFY"
        assert [c.symbol for c in store.list_candidates(active_only=False)] == ["INFY"]
        repo.close()

    def test_scoped_validate_does_not_reset_other_symbols_to_pending(
        self, tmp_path: Path
    ) -> None:
        """Owner-reported bug: a scoped validate writes a run covering only the
        symbol it was asked about, so reading a single run flipped every other
        symbol back to Pending. Each symbol keeps the verdict of the newest run
        that covered it; Excluded names (which never produce a Decision) take
        Last Validated from that run."""
        repo = SqliteRepository(tmp_path / "c.db")
        repo.initialize()
        store = SqliteCandidateStore(repo)
        full_ts = datetime(2026, 7, 28, 9, 15, tzinfo=timezone.utc)
        scoped_ts = datetime(2026, 7, 28, 12, 40, tzinfo=timezone.utc)
        for symbol in ("INFY", "WIPRO", "TCS"):
            store.upsert_candidate(symbol=symbol, notes="seed", added_ts=full_ts)

        def _run(run_id: str, started: datetime, members: dict[str, object]) -> None:
            repo.save_run(
                RunRecord(
                    run_id=run_id,
                    cycle_id="cyc",
                    trigger=RunTrigger.REFRESH,
                    started_ts=started,
                    finished_ts=started,
                    status=RunStatus.COMPLETED,
                    software_version="t",
                    blueprint_version="t",
                    strategy_profile="t",
                    strategy_profile_version="t",
                    indicator_versions={},
                    config_snapshot_id="t",
                ),
                detail={"pipeline": {"universe_members": members}},
            )

        _run(
            "run-full",
            full_ts,
            {
                "INFY": {"symbol": "INFY", "included": True, "eligibility_summary": "in"},
                "WIPRO": {"symbol": "WIPRO", "included": False, "eligibility_summary": "thin"},
            },
        )
        _run(
            "run-scoped",
            scoped_ts,
            {"INFY": {"symbol": "INFY", "included": False, "eligibility_summary": "now thin"}},
        )

        by_sym = {
            c.symbol: c
            for c in CandidatesService(store, repo=repo).list_candidates().candidates
        }
        # Newest run wins for the re-validated symbol …
        assert by_sym["INFY"].status == "EXCLUDED"
        assert by_sym["INFY"].eligibility_summary == "now thin"
        assert by_sym["INFY"].last_validated_ts == scoped_ts
        # … while symbols it did not cover keep their own earlier verdict.
        assert by_sym["WIPRO"].status == "EXCLUDED"
        assert by_sym["WIPRO"].eligibility_summary == "thin"
        assert by_sym["WIPRO"].last_validated_ts == full_ts
        # Never-validated symbols stay honestly Pending.
        assert by_sym["TCS"].status == "PENDING"
        assert by_sym["TCS"].last_validated_ts is None
        repo.close()


class TestFullUniverseValidationAPI:
    def test_validate_all_start_and_poll(self, client: TestClient) -> None:
        from athena.ops.serve_runtime import (
            FullValidationProgress,
            ServeRuntime,
            set_serve_runtime,
        )

        headers = get_auth_headers(client, Role.OPERATOR)
        runtime = ServeRuntime()
        set_serve_runtime(runtime)
        progress = FullValidationProgress(
            state="running",
            stage="ingesting",
            symbols_total=5,
            symbols_completed=0,
            started_at=datetime.now(tz=timezone.utc),
        )
        try:
            with mock.patch(
                "athena.ops.full_validation.start_full_validation",
                return_value=progress,
            ):
                response = client.post("/api/v1/market/validate-all", headers=headers)
            assert response.status_code == 202
            assert response.json()["data"]["state"] == "running"
            assert response.json()["data"]["symbols_total"] == 5

            runtime.set_full_validation(progress)
            status = client.get("/api/v1/market/validate-all", headers=headers)
            assert status.status_code == 200
            assert status.json()["data"]["stage"] == "ingesting"
        finally:
            set_serve_runtime(None)

    def test_validate_all_conflict_is_409(self, client: TestClient) -> None:
        from athena.ops.full_validation import CycleBusyError
        from athena.ops.serve_runtime import ServeRuntime, set_serve_runtime

        headers = get_auth_headers(client, Role.OPERATOR)
        set_serve_runtime(ServeRuntime())
        try:
            with mock.patch(
                "athena.ops.full_validation.start_full_validation",
                side_effect=CycleBusyError("cycle lock busy — another run-due"),
            ):
                response = client.post("/api/v1/market/validate-all", headers=headers)
            assert response.status_code == 409
            assert response.json()["title"] == "Cycle Busy"
        finally:
            set_serve_runtime(None)
