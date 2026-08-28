"""EM-4D: fit and report Platt-scaling calibration for the frozen EM-4B
logistic baselines, using real CALIBRATION partition data ONLY to fit
the 2-parameter transform. Owner/Chief Architect GO decision,
2026-08-28 (EM-4C comparison approved).

Explicit constraints from that approval, enforced structurally by this
script's own scope: the frozen EM-4B coefficients/preprocessing are
read-only here (never refit, never feature-selected); CALIBRATION is
used only to fit Platt's (A, B); FINAL_TEST is never read, imported,
or referenced anywhere in this module. No exploratory query against
FINAL_TEST -- it is architecturally absent from this script's argument
list.

Read-only against EM-2's real CALIBRATION evidence, EM-1b's real
CALIBRATION labels, and EM-4B's real frozen artifacts; write-only
against `artifacts/research/em4d/` (git-ignored).
"""

from __future__ import annotations

import argparse
import gzip
import json
import time as time_module
from collections import defaultdict
from decimal import Decimal, InvalidOperation
from pathlib import Path

from athena.explosive_move.contracts import CANDIDATE_CHECKPOINTS_IST, EVENT_THRESHOLDS_PERCENT, EventFamily
from athena.explosive_move.em4b_preprocessing import deserialize_preprocessing
from athena.explosive_move.em4c_metrics import brier_score, calibration_bins
from athena.explosive_move.em4c_scoring import score_logit, sigmoid
from athena.explosive_move.em4d_calibration import (
    EM4D_CALIBRATION_CONTRACT_VERSION,
    CalibrationLevel,
    apply_platt_scaling,
    decide_calibration,
)
from athena.explosive_move.evidence_contract import ALL_FIELDS, Classification

FAMILIES_THRESHOLDS: tuple[tuple[str, int], ...] = tuple(
    (family.value, threshold) for family in EventFamily for threshold in EVENT_THRESHOLDS_PERCENT
)
_CATEGORICAL_FIELDS = {"regime_trend", "regime_volatility", "regime_gap"}
_CANDIDATE_FIELD_NAMES = tuple(
    f.name.lower() for f in ALL_FIELDS if f.classification is Classification.CANDIDATE_FEATURE
)
CONTINUOUS_FIELDS = tuple(n for n in _CANDIDATE_FIELD_NAMES if n not in _CATEGORICAL_FIELDS)
CATEGORICAL_FIELDS = tuple(n for n in _CANDIDATE_FIELD_NAMES if n in _CATEGORICAL_FIELDS)
CHECKPOINT_FIELD = "checkpoint_ist"


def _read_jsonl_gz(path: Path):
    with gzip.open(path, "rt", encoding="utf-8") as f:
        for line in f:
            yield json.loads(line)


def _grouped_by_instrument(path: Path):
    current_id, buffer = None, []
    for row in _read_jsonl_gz(path):
        iid = row["instrument_id"]
        if current_id is not None and iid != current_id:
            yield current_id, buffer
            buffer = []
        current_id = iid
        buffer.append(row)
    if current_id is not None:
        yield current_id, buffer


def _advance(gen):
    try:
        return next(gen)
    except StopIteration:
        return None


def _to_decimal(value) -> Decimal | None:
    if value is None:
        return None
    try:
        return Decimal(str(value))
    except InvalidOperation:
        return None


def _load_logistic_artifacts(em4b_dir: Path) -> dict[tuple[str, int], dict]:
    artifacts = {}
    for family, threshold in FAMILIES_THRESHOLDS:
        payload = json.loads((em4b_dir / f"{family}_{threshold}.json").read_text(encoding="utf-8"))
        artifacts[(family, threshold)] = {
            "feature_names": tuple(payload["feature_names"]),
            "coefficients": tuple(payload["coefficients"]),
            "intercept": payload["intercept"],
            "preprocessing": deserialize_preprocessing(payload["preprocessing"]),
            "run_id": payload["run_id"],
        }
    return artifacts


def _build_joined_calibration_dataset(*, em2_dir: Path, em1b_labels_dir: Path):
    rows: list[dict] = []
    label_by_key_all: dict[tuple[str, int], dict[int, int]] = {ft: {} for ft in FAMILIES_THRESHOLDS}

    em1b_groups = _grouped_by_instrument(em1b_labels_dir / "CALIBRATION_checkpoint.jsonl.gz")
    invariant_groups = _grouped_by_instrument(em2_dir / "CALIBRATION_session_invariant.jsonl.gz")
    dynamic_groups = _grouped_by_instrument(em2_dir / "CALIBRATION_checkpoint_dynamic.jsonl.gz")

    em1b_cur, inv_cur, dyn_cur = _advance(em1b_groups), _advance(invariant_groups), _advance(dynamic_groups)
    rows_processed = 0

    while em1b_cur is not None and inv_cur is not None and dyn_cur is not None:
        target = min(em1b_cur[0], inv_cur[0], dyn_cur[0])
        if em1b_cur[0] != target:
            em1b_cur = _advance(em1b_groups)
            continue
        if inv_cur[0] != target:
            inv_cur = _advance(invariant_groups)
            continue
        if dyn_cur[0] != target:
            dyn_cur = _advance(dynamic_groups)
            continue

        instrument_id = target
        label_by_key: dict[tuple, str | None] = {}
        for row in em1b_cur[1]:
            key = (row["session_date"], row["checkpoint_ist"], row["event_family"], row["threshold_percent"])
            label_by_key[key] = row["label"]

        invariant_by_date = {r["session_date"]: r for r in inv_cur[1]}

        for dyn_row in dyn_cur[1]:
            d = dyn_row["session_date"]
            cp = dyn_row["checkpoint_ist"]
            inv_row = invariant_by_date.get(d)
            if inv_row is None:
                continue
            rows_processed += 1
            row_index = len(rows)

            observation: dict = {"instrument_id": instrument_id, "session_date": d, CHECKPOINT_FIELD: cp}
            for name in CONTINUOUS_FIELDS:
                source = dyn_row if name in dyn_row else inv_row
                v = source[name]["value"]
                observation[name] = _to_decimal(v) if v is not None else None
            for name in CATEGORICAL_FIELDS:
                source = dyn_row if name in dyn_row else inv_row
                observation[name] = source[name]["value"]
            rows.append(observation)

            for family, threshold in FAMILIES_THRESHOLDS:
                label = label_by_key.get((d, cp, family, threshold))
                if label == "POSITIVE":
                    label_by_key_all[(family, threshold)][row_index] = 1
                elif label == "NEGATIVE":
                    label_by_key_all[(family, threshold)][row_index] = 0

        em1b_cur, inv_cur, dyn_cur = _advance(em1b_groups), _advance(invariant_groups), _advance(dynamic_groups)

    return rows, label_by_key_all, rows_processed


def _calibrate_combo(
    *, family: str, threshold: int, rows: list[dict], eligible: dict[int, int], artifact: dict,
) -> dict:
    by_checkpoint: dict[str, list[tuple[float, bool]]] = defaultdict(list)
    for row_idx, label in eligible.items():
        row = rows[row_idx]
        logit = score_logit(
            row, feature_names=artifact["feature_names"], coefficients=artifact["coefficients"],
            intercept=artifact["intercept"], preprocessing=artifact["preprocessing"],
        )
        by_checkpoint[row[CHECKPOINT_FIELD]].append((logit, bool(label)))

    pooled_pairs = tuple(pair for pairs in by_checkpoint.values() for pair in pairs)

    checkpoints_result = {}
    for cp in CANDIDATE_CHECKPOINTS_IST:
        cp_pairs = tuple(by_checkpoint.get(cp, ()))
        decision = decide_calibration(checkpoint_pairs=cp_pairs, pooled_pairs=pooled_pairs)

        raw_brier = brier_score(tuple((sigmoid(f), y) for f, y in cp_pairs))
        result = {
            "level": decision.level.value,
            "checkpoint_support_n": decision.checkpoint_support_n,
            "checkpoint_support_k": decision.checkpoint_support_k,
            "pooled_support_n": decision.pooled_support_n,
            "pooled_support_k": decision.pooled_support_k,
            "isotonic_candidate": decision.isotonic_candidate,
            "raw_brier": raw_brier.score,
            "raw_n": raw_brier.n,
        }
        if decision.params is not None:
            result["platt_a"] = decision.params.a
            result["platt_b"] = decision.params.b
            result["platt_converged"] = decision.params.converged
            result["platt_n_iter"] = decision.params.n_iter

            calibrated_pairs = tuple((apply_platt_scaling(f, decision.params), y) for f, y in cp_pairs)
            calibrated_brier = brier_score(calibrated_pairs)
            result["calibrated_brier"] = calibrated_brier.score
            bins = calibration_bins(calibrated_pairs, num_bins=10)
            result["calibrated_reliability_bins"] = [
                {
                    "bin_index": b.bin_index, "predicted_mean": b.predicted_mean,
                    "observed_rate": b.observed_rate, "n": b.n,
                }
                for b in bins
            ]
        else:
            result["platt_a"] = None
            result["platt_b"] = None
            result["platt_converged"] = None
            result["platt_n_iter"] = None
            result["calibrated_brier"] = None
            result["calibrated_reliability_bins"] = None
        checkpoints_result[cp] = result

    return checkpoints_result


def main() -> None:
    parser = argparse.ArgumentParser(description="EM-4D Platt-scaling calibration (CALIBRATION only).")
    parser.add_argument("--em2-dir", type=Path, default=Path("artifacts/research/em2"))
    parser.add_argument("--em1b-labels-dir", type=Path, default=Path("artifacts/research/em1b/labels"))
    parser.add_argument("--em4b-dir", type=Path, default=Path("artifacts/research/em4b"))
    parser.add_argument("--out-dir", type=Path, default=Path("artifacts/research/em4d"))
    args = parser.parse_args()

    started = time_module.monotonic()
    print("loading EM-4B artifacts")
    logistic_artifacts = _load_logistic_artifacts(args.em4b_dir)

    print("joining EM-2 CALIBRATION evidence with EM-1b CALIBRATION labels")
    rows, label_by_key_all, rows_processed = _build_joined_calibration_dataset(
        em2_dir=args.em2_dir, em1b_labels_dir=args.em1b_labels_dir,
    )
    print(f"  {rows_processed} joined checkpoint rows")

    args.out_dir.mkdir(parents=True, exist_ok=True)
    flagged_insufficient: list[str] = []
    flagged_unstable: list[str] = []
    for family, threshold in FAMILIES_THRESHOLDS:
        key = f"{family}_{threshold}"
        eligible = label_by_key_all[(family, threshold)]
        print(f"calibrating {key}: {len(eligible)} eligible CALIBRATION rows")
        checkpoints_result = _calibrate_combo(
            family=family, threshold=threshold, rows=rows, eligible=eligible,
            artifact=logistic_artifacts[(family, threshold)],
        )
        (args.out_dir / f"{key}.json").write_text(json.dumps(checkpoints_result, indent=2), encoding="utf-8")

        for cp, result in checkpoints_result.items():
            if result["level"] == CalibrationLevel.UNCALIBRATED_INSUFFICIENT_SUPPORT.value:
                flagged_insufficient.append(f"{key}:{cp}")
            elif result["platt_converged"] is False:
                flagged_unstable.append(f"{key}:{cp}")

    elapsed = time_module.monotonic() - started
    summary = {
        "contract_version": EM4D_CALIBRATION_CONTRACT_VERSION, "partition": "CALIBRATION",
        "source_run_ids": {
            "em4b_run_ids": {f"{f}_{t}": logistic_artifacts[(f, t)]["run_id"] for f, t in FAMILIES_THRESHOLDS},
        },
        "rows_processed": rows_processed,
        "cells_total": len(FAMILIES_THRESHOLDS) * len(CANDIDATE_CHECKPOINTS_IST),
        "cells_flagged_insufficient_support": flagged_insufficient,
        "cells_flagged_unstable_fit": flagged_unstable,
        "elapsed_seconds": round(elapsed, 1),
    }
    (args.out_dir / "SUMMARY.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
    print(f"all done in {elapsed:.1f}s -- {len(flagged_insufficient)} insufficient-support cells, "
          f"{len(flagged_unstable)} unstable-fit cells")


if __name__ == "__main__":
    main()
