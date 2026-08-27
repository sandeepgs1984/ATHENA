"""EM-4B: fit the 18 approved logistic baselines (3 event families x 6
thresholds, each pooling all 9 checkpoints via a one-hot covariate) on
real TRAIN data only, per the EM-4 Modeling Contract (owner-approved
2026-08-27).

Read-only against EM-2's real TRAIN evidence and EM-1b's real TRAIN
labels; write-only against `artifacts/research/em4b/` (git-ignored).
VALIDATION/CALIBRATION/FINAL_TEST are never read here -- this script
only ever opens TRAIN, matching every other EM-4A/EM-4B module in this
workstream.

Join pattern mirrors em3_conditional_analysis.py's own established
merge-join (three streams already sorted by the same instrument
ordering EM-1b/EM-2 both use) -- reused deliberately, not
reimplemented differently.
"""

from __future__ import annotations

import argparse
import gzip
import hashlib
import json
import time as time_module
from array import array
from datetime import date
from decimal import Decimal, InvalidOperation
from pathlib import Path

from athena.explosive_move.contracts import CANDIDATE_CHECKPOINTS_IST, EVENT_THRESHOLDS_PERCENT, EventFamily
from athena.explosive_move.em4_config import (
    EM4_CONFIG_VERSION,
    L2_REGULARIZATION_GRID,
    TEMPORAL_CV_FOLDS,
    fold_for_session,
)
from athena.explosive_move.em4b_model import (
    EM4B_MODEL_CONTRACT_VERSION,
    evaluate_fold,
    fit_final_model,
    replay_final_model,
    select_regularization,
)
from athena.explosive_move.em4b_preprocessing import (
    PreprocessingSpec,
)
from athena.explosive_move.evidence_contract import ALL_FIELDS, Classification

FAMILIES_THRESHOLDS: tuple[tuple[str, int], ...] = tuple(
    (family.value, threshold) for family in EventFamily for threshold in EVENT_THRESHOLDS_PERCENT
)  # 18 combos, TOUCH first (matches em3's own FAMILIES ordering convention)

_CATEGORICAL_FIELDS = {"regime_trend", "regime_volatility", "regime_gap"}
_CANDIDATE_FIELD_NAMES = tuple(
    f.name.lower() for f in ALL_FIELDS if f.classification is Classification.CANDIDATE_FEATURE
)
CONTINUOUS_FIELDS = tuple(n for n in _CANDIDATE_FIELD_NAMES if n not in _CATEGORICAL_FIELDS)
CATEGORICAL_FIELDS = tuple(n for n in _CANDIDATE_FIELD_NAMES if n in _CATEGORICAL_FIELDS)
CHECKPOINT_FIELD = "checkpoint_ist"

_NOT_ELIGIBLE = -1  # array('b') sentinel: label is None or ALREADY_OCCURRED


def _read_jsonl_gz(path: Path):
    with gzip.open(path, "rt", encoding="utf-8") as f:
        for line in f:
            yield json.loads(line)


def _grouped_by_instrument(path: Path):
    current_id = None
    buffer: list[dict] = []
    for row in _read_jsonl_gz(path):
        iid = row["instrument_id"]
        if current_id is not None and iid != current_id:
            yield current_id, buffer
            buffer = []
        current_id = iid
        buffer.append(row)
    if current_id is not None:
        yield current_id, buffer


def _to_decimal(value) -> Decimal | None:
    if value is None:
        return None
    try:
        return Decimal(str(value))
    except InvalidOperation:
        return None


def _advance(gen):
    try:
        return next(gen)
    except StopIteration:
        return None


def _build_joined_dataset(
    *, em2_dir: Path, em1b_labels_dir: Path,
) -> tuple[list[dict], dict[tuple[str, int], array], int]:
    """One pass over TRAIN's real EM-2 evidence + EM-1b labels. Returns
    ``(rows, label_arrays, rows_processed)`` -- ``rows`` is one evidence
    dict per joined (instrument, session_date, checkpoint) observation
    (Decimal/str/None values, plus session_date/checkpoint_ist), shared
    by reference across every (family, threshold) model rather than
    copied 18x. ``label_arrays[(family, threshold)][i]`` is 1
    (POSITIVE), 0 (NEGATIVE), or ``_NOT_ELIGIBLE`` (None/ALREADY_OCCURRED)
    for ``rows[i]`` -- the same eligible-population definition EM-1c/
    EM-3 already established."""

    rows: list[dict] = []
    label_arrays: dict[tuple[str, int], array] = {
        ft: array("b") for ft in FAMILIES_THRESHOLDS
    }
    rows_processed = 0

    em1b_groups = _grouped_by_instrument(em1b_labels_dir / "TRAIN_checkpoint.jsonl.gz")
    invariant_groups = _grouped_by_instrument(em2_dir / "TRAIN_session_invariant.jsonl.gz")
    dynamic_groups = _grouped_by_instrument(em2_dir / "TRAIN_checkpoint_dynamic.jsonl.gz")

    em1b_cur = _advance(em1b_groups)
    inv_cur = _advance(invariant_groups)
    dyn_cur = _advance(dynamic_groups)

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

        label_by_key: dict[tuple, str | None] = {}
        for row in em1b_cur[1]:
            key = (row["session_date"], row["checkpoint_ist"], row["event_family"], row["threshold_percent"])
            label_by_key[key] = row["label"]

        invariant_by_date: dict[str, dict] = {r["session_date"]: r for r in inv_cur[1]}

        for dyn_row in dyn_cur[1]:
            d = dyn_row["session_date"]
            cp = dyn_row["checkpoint_ist"]
            inv_row = invariant_by_date.get(d)
            if inv_row is None:
                continue
            rows_processed += 1

            observation: dict = {"session_date": d, CHECKPOINT_FIELD: cp}
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
                    label_arrays[(family, threshold)].append(1)
                elif label == "NEGATIVE":
                    label_arrays[(family, threshold)].append(0)
                else:  # None (excluded readiness) or ALREADY_OCCURRED
                    label_arrays[(family, threshold)].append(_NOT_ELIGIBLE)

        em1b_cur = _advance(em1b_groups)
        inv_cur = _advance(invariant_groups)
        dyn_cur = _advance(dynamic_groups)

    return rows, label_arrays, rows_processed


def _serialize_preprocessing(spec: PreprocessingSpec) -> dict:
    return {
        "contract_version": spec.contract_version,
        "continuous_fields": list(spec.continuous_fields),
        "categorical_fields": list(spec.categorical_fields),
        "checkpoint_field": spec.checkpoint_field,
        "continuous_stats": {
            name: {"median": s.median, "mean": s.mean, "std": s.std, "known_n": s.known_n}
            for name, s in spec.continuous_stats.items()
        },
        "categorical_specs": {
            name: list(s.categories) for name, s in spec.categorical_specs.items()
        },
        "checkpoint_categories": list(spec.checkpoint_spec.categories),
        "feature_names": list(spec.feature_names),
        "dropped_zero_variance_columns": list(spec.dropped_zero_variance_columns),
        "fit_row_count": spec.fit_row_count,
    }


def _fit_one_model(
    *, family: str, threshold: int, rows: list[dict], labels: array, source_run_ids: dict[str, str],
):
    """Runs the frozen chronological CV to select C, fits the final
    TRAIN-wide model, and verifies deterministic reproduction -- all for
    exactly one (family, threshold) combination."""

    dates = [row["session_date"] for row in rows]
    fold_index = [fold_for_session(date.fromisoformat(d)) for d in dates]

    fold_evaluations = []
    for fold in TEMPORAL_CV_FOLDS:
        # fit window: every row strictly BEFORE this fold's eval block --
        # the base window (fid is None) plus any earlier fold's eval block.
        fit_idx = [i for i, fid in enumerate(fold_index) if fid is None or fid < fold.fold_id]
        eval_idx = [i for i, fid in enumerate(fold_index) if fid == fold.fold_id]

        fit_rows = [rows[i] for i in fit_idx]
        fit_labels = [labels[i] for i in fit_idx]
        eval_rows = [rows[i] for i in eval_idx]
        eval_labels = [labels[i] for i in eval_idx]

        for c_value in L2_REGULARIZATION_GRID:
            fold_evaluations.append(evaluate_fold(
                fold, fit_rows=fit_rows, eval_rows=eval_rows,
                labels_by_row_fit=fit_labels, labels_by_row_eval=eval_labels,
                continuous_fields=CONTINUOUS_FIELDS, categorical_fields=CATEGORICAL_FIELDS,
                checkpoint_field=CHECKPOINT_FIELD, checkpoint_categories=CANDIDATE_CHECKPOINTS_IST,
                c_value=c_value,
            ))

    cv_selection = select_regularization(tuple(fold_evaluations), c_grid=L2_REGULARIZATION_GRID)

    train_labels = list(labels)
    artifact = fit_final_model(
        train_rows=rows, train_labels=train_labels,
        continuous_fields=CONTINUOUS_FIELDS, categorical_fields=CATEGORICAL_FIELDS,
        checkpoint_field=CHECKPOINT_FIELD, checkpoint_categories=CANDIDATE_CHECKPOINTS_IST,
        family=family, threshold_percent=threshold, cv_selection=cv_selection,
        source_run_ids=source_run_ids,
    )
    replay_ok = replay_final_model(artifact, train_rows=rows, train_labels=train_labels)
    return artifact, replay_ok


def _artifact_to_dict(artifact) -> dict:
    return {
        "contract_version": artifact.contract_version,
        "family": artifact.family,
        "threshold_percent": artifact.threshold_percent,
        "sklearn_version": artifact.sklearn_version,
        "numpy_version": artifact.numpy_version,
        "solver": artifact.solver,
        "penalty": artifact.penalty,
        "c_value": artifact.c_value,
        "max_iter": artifact.max_iter,
        "tol": artifact.tol,
        "n_iter": artifact.n_iter,
        "converged": artifact.converged,
        "feature_names": list(artifact.feature_names),
        "coefficients": list(artifact.coefficients),
        "intercept": artifact.intercept,
        "preprocessing": _serialize_preprocessing(artifact.preprocessing),
        "train_row_count": artifact.train_row_count,
        "train_positive_count": artifact.train_positive_count,
        "cv_selection": {
            "selected_c": artifact.cv_selection.selected_c,
            "mean_pr_auc_by_c": {str(c): v for c, v in artifact.cv_selection.mean_pr_auc_by_c.items()},
            "fold_evaluations": [
                {
                    "fold_id": fe.fold_id, "c_value": fe.c_value, "fit_row_count": fe.fit_row_count,
                    "eval_row_count": fe.eval_row_count, "eval_positive_count": fe.eval_positive_count,
                    "pr_auc": fe.pr_auc,
                }
                for fe in artifact.cv_selection.fold_evaluations
            ],
        },
        "source_run_ids": artifact.source_run_ids,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="EM-4B logistic baseline fitting (TRAIN only).")
    parser.add_argument("--em2-dir", type=Path, default=Path("artifacts/research/em2"))
    parser.add_argument("--em1b-labels-dir", type=Path, default=Path("artifacts/research/em1b/labels"))
    parser.add_argument("--em1b-dataset-index", type=Path, default=Path("artifacts/research/em1b/dataset_index.json"))
    parser.add_argument("--out-dir", type=Path, default=Path("artifacts/research/em4b"))
    parser.add_argument(
        "--only", type=str, default=None,
        help="Comma-separated FAMILY:THRESHOLD pairs to fit (e.g. TOUCH:10) -- for a fast canary run.",
    )
    args = parser.parse_args()

    started = time_module.monotonic()
    em2_manifest = json.loads((args.em2_dir / "manifest.json").read_text(encoding="utf-8"))
    em1b_index = json.loads(args.em1b_dataset_index.read_text(encoding="utf-8"))
    source_run_ids = {
        "em2_train_manifest_id": em2_manifest["manifest_id"],
        "em1b_train_manifest_id": em1b_index["manifest_ids"]["TRAIN"],
        "em4_config_version": EM4_CONFIG_VERSION,
    }

    print("joining EM-2 TRAIN evidence with EM-1b TRAIN labels (one pass, all 18 combos)")
    rows, label_arrays, rows_processed = _build_joined_dataset(
        em2_dir=args.em2_dir, em1b_labels_dir=args.em1b_labels_dir,
    )
    print(f"  {rows_processed} joined checkpoint rows")

    targets = FAMILIES_THRESHOLDS
    if args.only:
        wanted = set()
        for pair in args.only.split(","):
            fam, thr = pair.split(":")
            wanted.add((fam, int(thr)))
        targets = tuple(ft for ft in FAMILIES_THRESHOLDS if ft in wanted)

    args.out_dir.mkdir(parents=True, exist_ok=True)
    summary: dict[str, dict] = {}
    for family, threshold in targets:
        model_started = time_module.monotonic()
        labels = label_arrays[(family, threshold)]
        eligible_n = sum(1 for v in labels if v != _NOT_ELIGIBLE)
        eligible_rows = [rows[i] for i, v in enumerate(labels) if v != _NOT_ELIGIBLE]
        eligible_labels = array("b", [v for v in labels if v != _NOT_ELIGIBLE])
        print(f"fitting {family}_{threshold}: {eligible_n} eligible rows")

        artifact, replay_ok = _fit_one_model(
            family=family, threshold=threshold, rows=eligible_rows, labels=eligible_labels,
            source_run_ids=source_run_ids,
        )
        elapsed = time_module.monotonic() - model_started
        payload = _artifact_to_dict(artifact)
        payload["replay_verified"] = replay_ok
        payload["elapsed_seconds"] = round(elapsed, 1)

        fingerprint = hashlib.sha256(
            json.dumps({k: v for k, v in payload.items() if k != "elapsed_seconds"},
                       sort_keys=True, separators=(",", ":")).encode("utf-8")
        ).hexdigest()
        payload["run_id"] = f"{EM4B_MODEL_CONTRACT_VERSION}-{family}-{threshold}-{fingerprint}"

        out_path = args.out_dir / f"{family}_{threshold}.json"
        out_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")

        summary[f"{family}_{threshold}"] = {
            "selected_c": artifact.cv_selection.selected_c, "converged": artifact.converged,
            "train_row_count": artifact.train_row_count, "train_positive_count": artifact.train_positive_count,
            "replay_verified": replay_ok, "elapsed_seconds": round(elapsed, 1),
        }
        print(f"  done in {elapsed:.1f}s -- C={artifact.cv_selection.selected_c}, "
              f"converged={artifact.converged}, replay_verified={replay_ok}")

    total_elapsed = time_module.monotonic() - started
    (args.out_dir / "SUMMARY.json").write_text(json.dumps({
        "contract_version": EM4B_MODEL_CONTRACT_VERSION, "source_run_ids": source_run_ids,
        "models_fit": summary, "rows_processed": rows_processed, "elapsed_seconds": round(total_elapsed, 1),
    }, indent=2), encoding="utf-8")
    print(f"all done in {total_elapsed:.1f}s")


if __name__ == "__main__":
    main()
