"""EM-5 frozen inference -- loads one promoted (family, threshold)
EM-4B logistic artifact and its EM-4D Platt calibration from
`config/emr/frozen_models/{version}/`, integrity-verifies each file's
bytes against `FROZEN_MODEL_MANIFEST.json` before trusting it, and
scores real observations by calling `em4c_scoring.score_logit` +
`em4d_calibration.apply_platt_scaling` -- the exact frozen, pure-Python
application functions research already used, never refit.

No `numpy`/`scikit-learn` import anywhere in this module or its
dependency chain (Section 12: enforced by `test_em5_no_model_learning.py`)
-- `em4b_preprocessing`, `em4c_scoring`, and `em4d_calibration` are all
hand-rolled pure Python by the same design discipline.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from pathlib import Path

from athena.explosive_move.em4b_preprocessing import PreprocessingSpec, deserialize_preprocessing
from athena.explosive_move.em4c_scoring import score_logit
from athena.explosive_move.em4d_calibration import PlattParams, apply_platt_scaling


class FrozenModelIntegrityError(Exception):
    """A promoted artifact's on-disk bytes no longer match the SHA256
    recorded for it in `FROZEN_MODEL_MANIFEST.json` at promotion time."""


@dataclass(frozen=True, slots=True)
class ScoredCandidate:
    family: str
    threshold_percent: int
    checkpoint: str
    raw_logit: float
    calibrated_probability: float
    calibration_level: str


@dataclass(frozen=True, slots=True)
class FrozenModel:
    family: str
    threshold_percent: int
    feature_names: tuple[str, ...]
    coefficients: tuple[float, ...]
    intercept: float
    preprocessing: PreprocessingSpec
    platt_by_checkpoint: dict[str, PlattParams]
    calibration_level_by_checkpoint: dict[str, str]

    def score(self, observation: dict, *, checkpoint: str) -> ScoredCandidate:
        logit = score_logit(
            observation, feature_names=self.feature_names, coefficients=self.coefficients,
            intercept=self.intercept, preprocessing=self.preprocessing,
        )
        params = self.platt_by_checkpoint.get(checkpoint)
        if params is None:
            raise ValueError(
                f"no Platt calibration for checkpoint {checkpoint!r} "
                f"(family={self.family}, threshold={self.threshold_percent})"
            )
        probability = apply_platt_scaling(logit, params)
        return ScoredCandidate(
            family=self.family, threshold_percent=self.threshold_percent, checkpoint=checkpoint,
            raw_logit=logit, calibrated_probability=probability,
            calibration_level=self.calibration_level_by_checkpoint[checkpoint],
        )


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _verify(path: Path, expected_sha256: dict[str, str], filename: str) -> None:
    expected = expected_sha256.get(filename)
    if expected is None:
        raise FrozenModelIntegrityError(f"{filename} not recorded in FROZEN_MODEL_MANIFEST.json")
    actual = _sha256(path)
    if actual != expected:
        raise FrozenModelIntegrityError(f"{path} sha256 mismatch: manifest says {expected}, file is {actual}")


def _platt_params(entry: dict) -> PlattParams:
    if entry["level"] == "CHECKPOINT_SPECIFIC":
        fit_n, fit_k = entry["checkpoint_support_n"], entry["checkpoint_support_k"]
    else:
        fit_n, fit_k = entry["pooled_support_n"], entry["pooled_support_k"]
    return PlattParams(
        a=entry["platt_a"], b=entry["platt_b"], n_iter=entry["platt_n_iter"],
        converged=entry["platt_converged"], fit_n=fit_n, fit_positive_k=fit_k,
    )


def load_frozen_model(*, config_dir: Path, version: str, family: str, threshold_percent: int) -> FrozenModel:
    """Loads and integrity-verifies one (family, threshold) frozen model
    plus its calibration. Raises `FrozenModelIntegrityError` if the
    promoted artifact's bytes no longer match what was promoted --
    never silently trusts a drifted file."""

    root = Path(config_dir) / "emr" / "frozen_models" / version
    manifest = json.loads((root / "FROZEN_MODEL_MANIFEST.json").read_text(encoding="utf-8"))

    filename = f"{family}_{threshold_percent}.json"
    em4b_path = root / "em4b" / filename
    em4d_path = root / "em4d" / filename
    _verify(em4b_path, manifest["sources"]["em4b"]["sha256"], filename)
    _verify(em4d_path, manifest["sources"]["em4d"]["sha256"], filename)

    em4b = json.loads(em4b_path.read_text(encoding="utf-8"))
    em4d = json.loads(em4d_path.read_text(encoding="utf-8"))

    preprocessing = deserialize_preprocessing(em4b["preprocessing"])
    platt_by_checkpoint = {cp: _platt_params(entry) for cp, entry in em4d.items()}
    level_by_checkpoint = {cp: entry["level"] for cp, entry in em4d.items()}

    return FrozenModel(
        family=family, threshold_percent=threshold_percent,
        feature_names=tuple(em4b["feature_names"]), coefficients=tuple(em4b["coefficients"]),
        intercept=em4b["intercept"], preprocessing=preprocessing,
        platt_by_checkpoint=platt_by_checkpoint, calibration_level_by_checkpoint=level_by_checkpoint,
    )
