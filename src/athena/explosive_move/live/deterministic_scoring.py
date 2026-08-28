"""EM-5's optional deterministic-score companion (EM-4A) -- loaded from
the promoted EM-3 register/manifest, persisted purely for comparison/
explainability alongside the calibrated logistic probability that
actually drives ranking and state (EM-4's GO decision: logistic beat
deterministic on PR-AUC in 18/18 real VALIDATION and FINAL_TEST
combinations). Reuses `deterministic_score.compile_deterministic_rules`/
`score_observation` completely unmodified.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from decimal import Decimal
from pathlib import Path

from athena.explosive_move.deterministic_score import (
    DeterministicScoreResult,
    VoteRule,
    compile_deterministic_rules,
    score_observation,
)

_REGISTER_FILENAME = "F_exploratory_candidate_register.json"
_MANIFEST_FILENAME = "manifest.json"


class DeterministicRulesIntegrityError(Exception):
    """The promoted EM-3 register/manifest bytes no longer match the
    SHA256 recorded for them in FROZEN_MODEL_MANIFEST.json."""


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _verify(path: Path, expected_sha256: dict[str, str]) -> None:
    expected = expected_sha256.get(path.name)
    if expected is None:
        raise DeterministicRulesIntegrityError(f"{path.name} not recorded in FROZEN_MODEL_MANIFEST.json")
    try:
        actual = _sha256(path)
    except OSError as exc:
        raise DeterministicRulesIntegrityError(f"{path} could not be read: {exc}") from exc
    if actual != expected:
        raise DeterministicRulesIntegrityError(f"{path} sha256 mismatch: manifest says {expected}, file is {actual}")


@dataclass(frozen=True, slots=True)
class DeterministicRuleSet:
    rules_by_key: dict[tuple[str, int, str], tuple[VoteRule, ...]]
    bin_edges: dict[str, tuple[Decimal, ...]]

    def score(
        self, *, family: str, threshold_percent: int, checkpoint: str, evidence: dict,
    ) -> DeterministicScoreResult:
        rules = self.rules_by_key.get((family, threshold_percent, checkpoint), ())
        return score_observation(rules=rules, evidence=evidence, bin_edges=self.bin_edges)


def load_deterministic_rules(*, config_dir: Path, version: str) -> DeterministicRuleSet:
    """Loads and integrity-verifies the promoted EM-3 register + its bin
    edges, then compiles the deterministic vote rules -- the same
    two-step (verify bytes, then apply frozen logic) as
    `frozen_inference.load_frozen_model`."""

    root = Path(config_dir) / "emr" / "frozen_models" / version
    try:
        frozen_manifest = json.loads((root / "FROZEN_MODEL_MANIFEST.json").read_text(encoding="utf-8"))
        expected_sha256 = frozen_manifest["sources"]["em3"]["sha256"]
    except (OSError, json.JSONDecodeError, KeyError) as exc:
        raise DeterministicRulesIntegrityError(f"cannot read manifest at {root}: {exc}") from exc

    register_path = root / "em3" / _REGISTER_FILENAME
    manifest_path = root / "em3" / _MANIFEST_FILENAME
    _verify(register_path, expected_sha256)
    _verify(manifest_path, expected_sha256)

    register = json.loads(register_path.read_text(encoding="utf-8"))
    em3_manifest = json.loads(manifest_path.read_text(encoding="utf-8"))

    rules_by_key = compile_deterministic_rules(register)
    bin_edges = {
        feature: tuple(Decimal(str(edge)) for edge in edges)
        for feature, edges in em3_manifest["bin_edges"].items()
    }
    return DeterministicRuleSet(rules_by_key=rules_by_key, bin_edges=bin_edges)
