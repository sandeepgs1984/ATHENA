"""EM-4C evaluation scaffolding: result schema, evaluation manifest and
versioning, and report-generation plumbing.

Owner/Chief Architect decision, 2026-08-27 (evaluation-scaffolding
scope). ``CrossSectionResult`` is the one record shape every EM-4C
metric (Precision@K, Lift@K, base rate, PR-AUC, Brier, MFE/MAE/
time-to-target aggregates) ultimately reports into, per real
session-date x checkpoint cross-section (never pooled), matching the
EM-4 Modeling Contract's evaluation requirement.

``build_evaluation_manifest`` follows the exact fingerprinting
convention already established by em2_evidence_generation.py and
em3_conditional_analysis.py: a sha256 over the deterministic content
only (sorted keys, no whitespace), with any genuine wall-clock field
(elapsed_seconds) excluded from what gets hashed -- the same lesson
EM-3's own run_id determinism bug taught this workstream. Two manifests
built from identical results always get an identical manifest_id
(replay-safe); this is exercised directly by the test suite rather than
requiring a real pipeline run.

Pure: no I/O. Callers own reading/writing the manifest to disk.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import asdict, dataclass

EM4C_EVALUATION_CONTRACT_VERSION = "em4c-evaluation-v1"


@dataclass(frozen=True, slots=True)
class CrossSectionResult:
    model_name: str  # e.g. "base-rate", "deterministic-v1", "logistic-v1"
    family: str
    threshold: int
    checkpoint: str
    session_date: str  # ISO date -- one real trading session, never pooled across sessions
    eligible_n: int
    base_rate: float | None
    precision_at_5: float | None
    precision_at_10: float | None
    precision_at_20: float | None
    lift_at_5: float | None
    lift_at_10: float | None
    lift_at_20: float | None
    pr_auc: float | None
    brier: float | None  # None for any model whose output is not a calibrated probability


def cross_section_result_to_dict(result: CrossSectionResult) -> dict:
    return asdict(result)


def _fingerprint(payload: dict) -> str:
    canonical = json.dumps(payload, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def build_evaluation_manifest(
    *,
    results: tuple[dict, ...],
    model_names: tuple[str, ...],
    source_run_ids: dict[str, str],
    elapsed_seconds: float | None = None,
    notes: str | None = None,
) -> dict:
    """``results`` are already-built CrossSectionResult dicts (via
    cross_section_result_to_dict). ``source_run_ids`` names the upstream
    manifest_ids this evaluation run consumed (e.g. the EM-2 VALIDATION
    evidence manifest, the EM-3 register run_id, a future EM-4B model
    artifact id) -- required, since an evaluation result is meaningless
    without knowing exactly which frozen inputs produced it.

    ``elapsed_seconds`` is accepted for operational logging but
    deliberately excluded from the fingerprinted content (wall-clock,
    not reproducible) -- it is attached to the returned manifest
    afterward, alongside manifest_id, not before."""

    content = {
        "contract_version": EM4C_EVALUATION_CONTRACT_VERSION,
        "model_names": sorted(model_names),
        "source_run_ids": source_run_ids,
        "result_count": len(results),
        "results": sorted(
            results, key=lambda r: (r["model_name"], r["family"], r["threshold"], r["checkpoint"], r["session_date"])
        ),
    }
    if notes is not None:
        content["notes"] = notes

    manifest = dict(content)
    manifest["manifest_id"] = f"em4c-evaluation-{_fingerprint(content)}"
    if elapsed_seconds is not None:
        manifest["elapsed_seconds"] = elapsed_seconds
    return manifest
