"""EM-1r2 end-to-end official evidence materialization tests."""

from __future__ import annotations

import json
from datetime import UTC, date, datetime
from pathlib import Path

import pytest

from athena.data.corporate_action_ingestion import CorporateActionIngestionService
from athena.data.providers.nse_corporate_actions_provider import (
    RetrievedCorporateActionPayload,
    parse_official_nse_payload,
)
from athena.data.store import SqliteRepository
from athena.domain.market import Instrument

SOURCE_URL = (
    "https://www.nseindia.com/api/corporates-corporateActions"
    "?index=equities&from_date=01-06-2024&to_date=30-06-2024"
)


class _Provider:
    def __init__(self, payload: bytes) -> None:
        self._payload = payload

    def retrieve(self, start: date, end: date) -> RetrievedCorporateActionPayload:
        parsed = parse_official_nse_payload(
            self._payload,
            source_url=SOURCE_URL,
            content_type="application/json",
        )
        return RetrievedCorporateActionPayload(
            requested_start=start,
            requested_end=end,
            retrieved_at=datetime(2026, 8, 21, 6, tzinfo=UTC),
            source_url=SOURCE_URL,
            content_type="application/json",
            body=self._payload,
            parsed=parsed,
            complete=True,
            completeness_basis="exact official interval",
        )


@pytest.fixture()
def repo(tmp_path: Path):
    repository = SqliteRepository(tmp_path / "athena.db")
    repository.initialize()
    repository.upsert_instrument(
        Instrument(
            instrument_id="nse:AAA",
            symbol="AAA",
            exchange="NSE",
            series="EQ",
            isin="INE000A01001",
        )
    )
    repository.save_resolved_universe(
        "athena_core",
        ["nse:AAA"],
        resolved_at=datetime(2026, 8, 21, tzinfo=UTC),
    )
    yield repository
    repository.close()


def _run(repo, provider, evidence_root: Path):
    return CorporateActionIngestionService(
        repository=repo,
        provider=provider,
        evidence_root=evidence_root,
    ).run(
        study_start=date(2024, 6, 1),
        study_end=date(2024, 6, 30),
        universe_name="athena_core",
        cohort_resolution_date=date(2026, 8, 21),
    )


def test_complete_official_evidence_is_immutable_persisted_and_replay_stable(
    repo, tmp_path: Path
) -> None:
    payload = json.dumps(
        [
            {
                "symbol": "AAA",
                "series": "EQ",
                "isin": "INE000A01001",
                "exDate": "03-Jun-2024",
                "subject": "Bonus 1:1",
            }
        ]
    ).encode()
    provider = _Provider(payload)

    first = _run(repo, provider, tmp_path / "evidence")
    second = _run(repo, provider, tmp_path / "evidence")

    assert first.manifest.authoritative_for_research is True
    assert first.inserted_actions == 1
    assert second.inserted_actions == 0
    assert first.manifest.replay_id == second.manifest.replay_id
    assert first.manifest_path == second.manifest_path
    raw = tmp_path / "evidence" / first.manifest.retrieval_slices[0].raw_artifact
    assert raw.read_bytes() == payload
    assert len(repo.get_corporate_actions("nse:AAA")) == 1


def test_malformed_official_row_is_manifested_and_blocks_all_persistence(
    repo, tmp_path: Path
) -> None:
    payload = json.dumps(
        [
            {
                "symbol": "AAA",
                "series": "EQ",
                "exDate": "not-a-date",
                "subject": "Bonus 1:1",
            }
        ]
    ).encode()

    result = _run(repo, _Provider(payload), tmp_path / "evidence")

    assert result.manifest.coverage_complete is True
    assert result.manifest.authoritative_for_research is False
    assert result.inserted_actions == 0
    assert result.manifest.exclusion_count == 1
    assert repo.get_corporate_actions("nse:AAA") == []
