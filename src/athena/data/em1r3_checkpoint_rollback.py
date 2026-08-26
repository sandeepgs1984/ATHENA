"""Automatic checkpoint rollback for EM-1r3 production capture after a
Kite access-token expiry mid-run (2026-08-22 incident and its recurrence
risk: Kite Connect access tokens expire daily and require an interactive
owner re-authentication -- there is no programmatic refresh).

Kite's own transport already retries HTTP 429, and ``RetryingMarketDataProvider``
retries transient network/5xx failures -- neither can recover from an expired
token (a 403 ``TokenException``), which is permanent by definition: retrying
with the same dead token cannot succeed. EM-1r3's own ``capture()`` never
raises on a per-session retrieval failure (it fails closed and records the
exclusion, by design), so a dead token does not stop the runner -- it just
silently checkpoints batch after batch of 100%-failed "completed" instruments
until something notices. This module finds and rolls back exactly those
corrupted trailing batches so a resume genuinely re-fetches them, rather than
leaving them falsely marked done forever.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from pathlib import Path

from athena.explosive_move.intraday_reconstruction import (
    IntradayReconstructionManifest,
    SessionExclusionReason,
    intraday_manifest_from_payload,
)

_TOKEN_FAILURE_PATTERN = re.compile(
    r"TokenException|Incorrect `api_key` or `access_token`", re.IGNORECASE
)
_ROLLBACK_FRACTION_THRESHOLD = 0.5


def _is_token_failure(detail: str | None) -> bool:
    return bool(detail) and bool(_TOKEN_FAILURE_PATTERN.search(detail))


def _batch_is_token_corrupted(manifest: IntradayReconstructionManifest) -> bool:
    if not manifest.sessions:
        return False
    token_failures = sum(
        1
        for record in manifest.sessions
        if record.status == "EXCLUDED"
        and record.exclusion_reason is SessionExclusionReason.RETRIEVAL_FAILED
        and _is_token_failure(record.exclusion_detail)
    )
    return (token_failures / len(manifest.sessions)) >= _ROLLBACK_FRACTION_THRESHOLD


@dataclass(frozen=True)
class RollbackResult:
    rolled_back_batches: int
    rolled_back_instrument_ids: tuple[str, ...]


def rollback_token_failure_batches(checkpoint_path: Path, evidence_root: Path) -> RollbackResult:
    """Truncate trailing batches whose manifests show majority token-auth
    failures. Scans backward from the most recently completed batch and
    stops at the first clean one it finds -- a no-op (0 rolled back) if the
    checkpoint doesn't exist or is already clean.

    The original checkpoint is preserved as a timestamped-by-count backup
    before any write, per this project's "preserve provenance, never
    silently discard" convention.
    """

    checkpoint_path = Path(checkpoint_path)
    if not checkpoint_path.exists():
        return RollbackResult(0, ())

    raw = checkpoint_path.read_text(encoding="utf-8")
    data = json.loads(raw)
    manifest_paths: list[str] = list(data.get("batch_manifest_paths", []))
    completed_ids: list[str] = list(data.get("completed_instrument_ids", []))
    evidence_root = Path(evidence_root).resolve()

    corrupted_batches = 0
    corrupted_ids: list[str] = []
    for path_str in reversed(manifest_paths):
        manifest_path = evidence_root / path_str
        manifest = intraday_manifest_from_payload(manifest_path.read_bytes())
        if not _batch_is_token_corrupted(manifest):
            break
        corrupted_batches += 1
        corrupted_ids.extend(manifest.cohort_instrument_ids)

    if corrupted_batches == 0:
        return RollbackResult(0, ())

    data["batch_manifest_paths"] = manifest_paths[: len(manifest_paths) - corrupted_batches]
    corrupted_id_set = set(corrupted_ids)
    data["completed_instrument_ids"] = [
        instrument_id for instrument_id in completed_ids if instrument_id not in corrupted_id_set
    ]

    backup_path = checkpoint_path.with_name(
        f"{checkpoint_path.stem}.pre-rollback-{corrupted_batches}batches{checkpoint_path.suffix}"
    )
    backup_path.write_text(raw, encoding="utf-8")
    checkpoint_path.write_text(json.dumps(data, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    return RollbackResult(corrupted_batches, tuple(sorted(corrupted_id_set)))


def main() -> None:
    import argparse

    parser = argparse.ArgumentParser(
        description="Roll back EM-1r3 checkpoint batches corrupted by an expired Kite token."
    )
    parser.add_argument("--checkpoint", type=Path, required=True)
    parser.add_argument("--evidence-root", type=Path, required=True)
    args = parser.parse_args()

    result = rollback_token_failure_batches(args.checkpoint, args.evidence_root)
    print(
        json.dumps(
            {
                "rolled_back_batches": result.rolled_back_batches,
                "rolled_back_instrument_ids": list(result.rolled_back_instrument_ids),
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
