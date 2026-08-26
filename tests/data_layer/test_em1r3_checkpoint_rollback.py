"""EM-1r3 checkpoint rollback after a Kite token-expiry incident
(2026-08-22): a batch whose manifest shows majority token-auth failures
must be un-checkpointed so a resume genuinely re-fetches it, while a
genuinely healthy batch must never be rolled back."""

from __future__ import annotations

import json
from datetime import date, datetime, timezone
from pathlib import Path

from athena.data.em1r3_checkpoint_rollback import rollback_token_failure_batches
from athena.explosive_move.corporate_action_coverage import (
    SURVIVOR_COHORT_LIMITATION,
    SURVIVOR_COHORT_NAME,
)
from athena.explosive_move.intraday_reconstruction import (
    IntradayReconstructionManifest,
    NormalizedArtifact,
    SessionExclusionReason,
    SessionRecord,
    SourceCapture,
    write_immutable_manifest,
)

DAY = date(2026, 8, 22)
NOW = datetime(2026, 8, 22, 12, 0, tzinfo=timezone.utc)


def _source_capture(instrument_id: str, retrieval_error: str | None) -> SourceCapture:
    return SourceCapture(
        instrument_id=instrument_id, session_date=DAY,
        requested_start=NOW, requested_end=NOW, captured_at=NOW,
        provider="kite", artifact="unused", payload_sha256="0" * 64,
        row_count=0, retrieval_error=retrieval_error,
    )


def _excluded(instrument_id: str, detail: str) -> SessionRecord:
    return SessionRecord(
        instrument_id=instrument_id, session_date=DAY, status="EXCLUDED",
        expected_slots=75, source_rows=0, admitted_rows=0,
        identical_duplicates_collapsed=0, content_sha256=None,
        exclusion_reason=SessionExclusionReason.RETRIEVAL_FAILED,
        exclusion_detail=detail,
    )


def _admitted(instrument_id: str) -> SessionRecord:
    return SessionRecord(
        instrument_id=instrument_id, session_date=DAY, status="ADMITTED",
        expected_slots=75, source_rows=75, admitted_rows=75,
        identical_duplicates_collapsed=0, content_sha256="a" * 64,
    )


def _normalized_artifact(instrument_id: str) -> NormalizedArtifact:
    return NormalizedArtifact(
        instrument_id=instrument_id, artifact="unused", payload_sha256="0" * 64,
        admitted_sessions=0, row_count=0,
    )


def _manifest(instrument_ids: tuple[str, ...], sessions: tuple[SessionRecord, ...]) -> IntradayReconstructionManifest:
    return IntradayReconstructionManifest(
        study_start=DAY, study_end=DAY,
        cohort_name=SURVIVOR_COHORT_NAME, cohort_id="fake-cohort-id",
        cohort_instrument_ids=instrument_ids,
        population_basis="SURVIVOR_COHORT", population_limitation=SURVIVOR_COHORT_LIMITATION,
        source_captures=tuple(_source_capture(i, None) for i in instrument_ids),
        normalized_artifacts=tuple(_normalized_artifact(i) for i in instrument_ids),
        sessions=sessions,
    )


def _checkpoint(evidence_root: Path, manifest_paths: list[str], completed_ids: list[str]) -> Path:
    checkpoint = evidence_root.parent / "checkpoint.json"
    checkpoint.write_text(json.dumps({
        "capture_run_id": "test-run", "cohort_name": SURVIVOR_COHORT_NAME,
        "cohort_id": "fake-cohort-id", "universe_name": "athena_core",
        "study_start": DAY.isoformat(), "study_end": DAY.isoformat(),
        "started_at": NOW.isoformat(),
        "completed_instrument_ids": completed_ids,
        "batch_manifest_paths": manifest_paths,
        "finished_at": None,
    }))
    return checkpoint


def test_rollback_removes_a_fully_token_corrupted_trailing_batch(tmp_path: Path):
    evidence_root = tmp_path / "intraday"
    manifests_dir = evidence_root / "intraday-manifests"

    clean = _manifest(("NSE:AAA", "NSE:BBB"), (_admitted("NSE:AAA"), _admitted("NSE:BBB")))
    corrupted = _manifest(
        ("NSE:CCC", "NSE:DDD"),
        (
            _excluded("NSE:CCC", "RuntimeError: kite HTTP 403: Incorrect `api_key` or `access_token`."),
            _excluded("NSE:DDD", "RuntimeError: TokenException: session expired"),
        ),
    )
    clean_path = write_immutable_manifest(manifests_dir, clean)
    corrupted_path = write_immutable_manifest(manifests_dir, corrupted)

    checkpoint = _checkpoint(
        evidence_root,
        manifest_paths=[
            str(clean_path.relative_to(evidence_root)),
            str(corrupted_path.relative_to(evidence_root)),
        ],
        completed_ids=["NSE:AAA", "NSE:BBB", "NSE:CCC", "NSE:DDD"],
    )

    result = rollback_token_failure_batches(checkpoint, evidence_root)

    assert result.rolled_back_batches == 1
    assert result.rolled_back_instrument_ids == ("NSE:CCC", "NSE:DDD")
    data = json.loads(checkpoint.read_text())
    assert data["completed_instrument_ids"] == ["NSE:AAA", "NSE:BBB"]
    assert data["batch_manifest_paths"] == [str(clean_path.relative_to(evidence_root))]

    backup = checkpoint.with_name("checkpoint.pre-rollback-1batches.json")
    assert backup.exists()
    assert json.loads(backup.read_text())["completed_instrument_ids"] == [
        "NSE:AAA", "NSE:BBB", "NSE:CCC", "NSE:DDD"
    ]


def test_rollback_never_touches_a_genuinely_healthy_batch(tmp_path: Path):
    """A batch with a normal, low, non-token failure rate must survive
    untouched -- this is what proves the guard is not simply nuking the
    last batch unconditionally."""

    evidence_root = tmp_path / "intraday"
    manifests_dir = evidence_root / "intraday-manifests"

    healthy = _manifest(
        ("NSE:AAA", "NSE:BBB"),
        (_admitted("NSE:AAA"), _excluded("NSE:BBB", "RuntimeError: kite network failure: timed out")),
    )
    healthy_path = write_immutable_manifest(manifests_dir, healthy)

    checkpoint = _checkpoint(
        evidence_root,
        manifest_paths=[str(healthy_path.relative_to(evidence_root))],
        completed_ids=["NSE:AAA", "NSE:BBB"],
    )

    result = rollback_token_failure_batches(checkpoint, evidence_root)

    assert result.rolled_back_batches == 0
    assert result.rolled_back_instrument_ids == ()
    data = json.loads(checkpoint.read_text())
    assert data["completed_instrument_ids"] == ["NSE:AAA", "NSE:BBB"]
    assert not checkpoint.with_name("checkpoint.pre-rollback-1batches.json").exists()


def test_rollback_stops_at_the_first_clean_batch_scanning_backward(tmp_path: Path):
    evidence_root = tmp_path / "intraday"
    manifests_dir = evidence_root / "intraday-manifests"

    clean = _manifest(("NSE:AAA",), (_admitted("NSE:AAA"),))
    corrupted_1 = _manifest(
        ("NSE:BBB",), (_excluded("NSE:BBB", "TokenException: expired"),)
    )
    corrupted_2 = _manifest(
        ("NSE:CCC",), (_excluded("NSE:CCC", "TokenException: expired"),)
    )
    clean_path = write_immutable_manifest(manifests_dir, clean)
    corrupted_1_path = write_immutable_manifest(manifests_dir, corrupted_1)
    corrupted_2_path = write_immutable_manifest(manifests_dir, corrupted_2)

    checkpoint = _checkpoint(
        evidence_root,
        manifest_paths=[
            str(clean_path.relative_to(evidence_root)),
            str(corrupted_1_path.relative_to(evidence_root)),
            str(corrupted_2_path.relative_to(evidence_root)),
        ],
        completed_ids=["NSE:AAA", "NSE:BBB", "NSE:CCC"],
    )

    result = rollback_token_failure_batches(checkpoint, evidence_root)

    assert result.rolled_back_batches == 2
    assert set(result.rolled_back_instrument_ids) == {"NSE:BBB", "NSE:CCC"}
    data = json.loads(checkpoint.read_text())
    assert data["completed_instrument_ids"] == ["NSE:AAA"]


def test_rollback_is_a_no_op_when_checkpoint_missing(tmp_path: Path):
    result = rollback_token_failure_batches(tmp_path / "missing.json", tmp_path / "evidence")
    assert result.rolled_back_batches == 0
    assert result.rolled_back_instrument_ids == ()
