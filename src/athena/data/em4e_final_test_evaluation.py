"""EM-4E: the sealed, one-shot FINAL_TEST evaluation -- deterministic
(EM-4A) vs. calibrated logistic (EM-4B + EM-4D Platt scaling) vs. the
unconditional base rate. Owner/Chief Architect GO decision, 2026-08-28,
under the exact frozen FINAL_TEST policy recorded in
IMPLEMENTATION_SUMMARY.md's EM-4D entry.

Structurally sealed: this module contains no fitting capability
whatsoever -- it only loads already-frozen EM-4B coefficients/
preprocessing and already-frozen EM-4D Platt (A, B) parameters and
applies them (dot product + sigmoid + a 2-parameter affine transform).
No sklearn, no Newton's method, no regularization grid, nothing that
could "retrain" on FINAL_TEST even by accident.

``--partition`` defaults to FINAL_TEST but accepts any partition name
so this exact code can be dry-run against an already-open partition
(VALIDATION) before the one real, sealed invocation -- verifying
correctness must happen BEFORE FINAL_TEST is ever touched, never by
re-running against FINAL_TEST itself after finding a bug. Real
FINAL_TEST run-once discipline: this script is meant to be invoked
exactly once with ``--partition FINAL_TEST``, producing one immutable
report; no support for partial/incremental re-runs against FINAL_TEST.

Read-only against EM-2's real partition evidence, EM-1b's real
partition labels, EM-3's real TRAIN-discovered register, EM-4B's real
frozen artifacts, EM-4D's real frozen calibration, and EM-1r3's real
intraday evidence (MFE/MAE/time-to-target only); write-only against
`artifacts/research/em4e/` (git-ignored).
"""

from __future__ import annotations

import argparse
import gzip
import json
import time as time_module
from collections import defaultdict
from datetime import date, datetime
from datetime import time as time_cls
from decimal import Decimal, InvalidOperation
from pathlib import Path
from zoneinfo import ZoneInfo

from athena.explosive_move.contracts import CANDIDATE_CHECKPOINTS_IST, EVENT_THRESHOLDS_PERCENT, EventFamily
from athena.explosive_move.deterministic_score import compile_deterministic_rules, score_observation
from athena.explosive_move.em4b_preprocessing import deserialize_preprocessing
from athena.explosive_move.em4c_metrics import BrierResult, average_precision, brier_score, calibration_bins
from athena.explosive_move.em4c_ranking import (
    ScoredObservation,
    base_rate,
    lift_at_k,
    precision_at_k,
    rank_observations,
)
from athena.explosive_move.em4c_scoring import score_logit
from athena.explosive_move.em4d_calibration import apply_platt_scaling
from athena.explosive_move.event_labels import price_at_checkpoint
from athena.explosive_move.evidence_contract import ALL_FIELDS, Classification
from athena.explosive_move.forward_excursion import compute_forward_excursion
from athena.explosive_move.intraday_reconstruction import candles_from_payload, intraday_manifest_from_payload

IST = ZoneInfo("Asia/Kolkata")

FAMILIES_THRESHOLDS: tuple[tuple[str, int], ...] = tuple(
    (family.value, threshold) for family in EventFamily for threshold in EVENT_THRESHOLDS_PERCENT
)
FLAGSHIP = ("TOUCH", 10)
_CATEGORICAL_FIELDS = {"regime_trend", "regime_volatility", "regime_gap"}
_CANDIDATE_FIELD_NAMES = tuple(
    f.name.lower() for f in ALL_FIELDS if f.classification is Classification.CANDIDATE_FEATURE
)
CONTINUOUS_FIELDS = tuple(n for n in _CANDIDATE_FIELD_NAMES if n not in _CATEGORICAL_FIELDS)
CATEGORICAL_FIELDS = tuple(n for n in _CANDIDATE_FIELD_NAMES if n in _CATEGORICAL_FIELDS)
CHECKPOINT_FIELD = "checkpoint_ist"
K_VALUES = (5, 10, 20)


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


def _load_deterministic_rules(em3_dir: Path):
    register = json.loads((em3_dir / "F_exploratory_candidate_register.json").read_text(encoding="utf-8"))
    manifest = json.loads((em3_dir / "manifest.json").read_text(encoding="utf-8"))
    rules = compile_deterministic_rules(register)
    bin_edges = {name: tuple(Decimal(e) for e in edges) for name, edges in manifest["bin_edges"].items()}
    return rules, bin_edges, manifest["run_id"]


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


def _load_calibration_artifacts(em4d_dir: Path) -> dict[tuple[str, int], dict]:
    """Loads EM-4D's frozen per-(family, threshold, checkpoint) Platt
    decisions -- reconstructs the ``PlattParams``-shaped fields needed
    by ``apply_platt_scaling`` directly from the persisted JSON."""

    from athena.explosive_move.em4d_calibration import PlattParams

    calibration = {}
    for family, threshold in FAMILIES_THRESHOLDS:
        payload = json.loads((em4d_dir / f"{family}_{threshold}.json").read_text(encoding="utf-8"))
        per_checkpoint = {}
        for cp, cell in payload.items():
            if cell["platt_a"] is None:
                per_checkpoint[cp] = {"level": cell["level"], "params": None}
            else:
                per_checkpoint[cp] = {
                    "level": cell["level"],
                    "params": PlattParams(
                        a=cell["platt_a"], b=cell["platt_b"], n_iter=cell["platt_n_iter"],
                        converged=cell["platt_converged"], fit_n=0, fit_positive_k=0,
                    ),
                }
        calibration[(family, threshold)] = per_checkpoint
    return calibration


def _build_joined_dataset(*, partition: str, em2_dir: Path, em1b_labels_dir: Path):
    rows: list[dict] = []
    label_by_key_all: dict[tuple[str, int], dict[int, int]] = {ft: {} for ft in FAMILIES_THRESHOLDS}

    em1b_groups = _grouped_by_instrument(em1b_labels_dir / f"{partition}_checkpoint.jsonl.gz")
    invariant_groups = _grouped_by_instrument(em2_dir / f"{partition}_session_invariant.jsonl.gz")
    dynamic_groups = _grouped_by_instrument(em2_dir / f"{partition}_checkpoint_dynamic.jsonl.gz")

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


def _score_combo(
    *, family: str, threshold: int, rows: list[dict], eligible: dict[int, int],
    deterministic_rules: dict, bin_edges: dict, logistic_artifact: dict, calibration_by_checkpoint: dict,
) -> dict:
    det_scored: list[ScoredObservation] = []
    log_scored: list[ScoredObservation] = []
    cross_sections: dict[tuple[str, str], list[int]] = defaultdict(list)
    calibration_levels_used: dict[str, str] = {}

    for row_idx, label in eligible.items():
        row = rows[row_idx]
        cp = row[CHECKPOINT_FIELD]
        rule_key = (family, threshold, cp)
        rules = deterministic_rules.get(rule_key, ())
        det_result = score_observation(rules=rules, evidence=row, bin_edges=bin_edges)

        logit = score_logit(
            row, feature_names=logistic_artifact["feature_names"],
            coefficients=logistic_artifact["coefficients"], intercept=logistic_artifact["intercept"],
            preprocessing=logistic_artifact["preprocessing"],
        )
        cell = calibration_by_checkpoint[cp]
        calibration_levels_used[cp] = cell["level"]
        calibrated_prob = apply_platt_scaling(logit, cell["params"]) if cell["params"] is not None else None

        det_scored.append(
            ScoredObservation(instrument_id=row["instrument_id"], score=det_result.score, label=bool(label))
        )
        log_scored.append(
            ScoredObservation(instrument_id=row["instrument_id"], score=calibrated_prob, label=bool(label))
        )
        cross_sections[(row["session_date"], cp)].append(len(det_scored) - 1)

    return {
        "det_scored": det_scored, "log_scored": log_scored, "cross_sections": dict(cross_sections),
        "calibration_levels_used": calibration_levels_used,
    }


def _cross_section_k_metrics(scored: list[ScoredObservation], cross_sections: dict) -> dict:
    per_k: dict[int, dict[str, list[float]]] = {k: {"precision": [], "lift": []} for k in K_VALUES}
    for indices in cross_sections.values():
        section = tuple(scored[i] for i in indices)
        for k in K_VALUES:
            p = precision_at_k(section, k)
            if p.precision is not None:
                per_k[k]["precision"].append(p.precision)
            lift_result = lift_at_k(section, k)
            if lift_result.lift is not None:
                per_k[k]["lift"].append(lift_result.lift)

    def _summary(values: list[float]) -> dict:
        if not values:
            return {"mean": None, "median": None, "n_cross_sections": 0}
        ordered = sorted(values)
        n = len(ordered)
        median = ordered[n // 2] if n % 2 else (ordered[n // 2 - 1] + ordered[n // 2]) / 2
        return {"mean": sum(values) / n, "median": median, "n_cross_sections": n}

    return {
        f"k={k}": {"precision": _summary(v["precision"]), "lift": _summary(v["lift"])}
        for k, v in per_k.items()
    }


def _pooled_metrics(scored: list[ScoredObservation], *, is_probability: bool) -> dict:
    ranked = rank_observations(tuple(scored))
    ranked_labels = tuple(o.label for o in ranked)
    pr_auc = average_precision(ranked_labels)
    result: dict = {
        "eligible_n": len(scored), "known_score_n": len(ranked), "base_rate": base_rate(tuple(scored)),
        "pr_auc": pr_auc,
    }
    if is_probability:
        pairs = tuple((o.score, o.label) for o in scored if o.score is not None)
        brier: BrierResult = brier_score(pairs)
        result["brier"] = brier.score
        bins = calibration_bins(pairs, num_bins=10)
        result["calibration_bins"] = [
            {
                "bin_index": b.bin_index, "predicted_mean": b.predicted_mean,
                "observed_rate": b.observed_rate, "n": b.n,
            }
            for b in bins
        ]
    else:
        result["brier"] = None
        result["calibration_bins"] = None
    return result


def _checkpoint_stability(scored: list[ScoredObservation], rows: list[dict], row_indices: list[int]) -> dict:
    tagged = [(rows[idx][CHECKPOINT_FIELD], s) for idx, s in zip(row_indices, scored, strict=True)]
    by_cp = defaultdict(list)
    for cp, s in tagged:
        by_cp[cp].append(s)
    result = {}
    for cp in CANDIDATE_CHECKPOINTS_IST:
        section = tuple(by_cp.get(cp, ()))
        if not section:
            continue
        p10 = precision_at_k(section, 10)
        l10 = lift_at_k(section, 10)
        result[cp] = {
            "eligible_n": len(section), "base_rate": base_rate(section),
            "precision_at_10": p10.precision, "lift_at_10": l10.lift,
        }
    return result


def _regime_stability(scored: list[ScoredObservation], rows: list[dict], row_indices: list[int]) -> dict:
    result = {}
    for regime_field in ("regime_trend", "regime_volatility", "regime_gap"):
        tagged = [(rows[idx][regime_field], s) for idx, s in zip(row_indices, scored, strict=True)]
        by_value = defaultdict(list)
        for value, s in tagged:
            if value is not None:
                by_value[value].append(s)
        field_result = {}
        for value, section in by_value.items():
            section = tuple(section)
            p10 = precision_at_k(section, 10)
            l10 = lift_at_k(section, 10)
            field_result[value] = {
                "eligible_n": len(section), "base_rate": base_rate(section),
                "precision_at_10": p10.precision, "lift_at_10": l10.lift,
            }
        result[regime_field] = field_result
    return result


def _compute_flagship_excursion(
    *, family: str, threshold: int, rows: list[dict], eligible: dict[int, int],
    em1r3_checkpoint_path: Path, em1r3_evidence_root: Path,
) -> dict:
    checkpoint = json.loads(em1r3_checkpoint_path.read_text(encoding="utf-8"))
    manifests = [
        intraday_manifest_from_payload((em1r3_evidence_root / p).read_bytes())
        for p in checkpoint["batch_manifest_paths"]
    ]
    artifact_by_instrument: dict[str, str] = {}
    for m in manifests:
        for artifact in m.normalized_artifacts:
            artifact_by_instrument[artifact.instrument_id] = artifact.artifact

    positive_indices = [idx for idx, label in eligible.items() if label == 1]
    by_instrument: dict[str, list[int]] = defaultdict(list)
    for idx in positive_indices:
        by_instrument[rows[idx]["instrument_id"]].append(idx)

    results = []
    for instrument_id, indices in by_instrument.items():
        artifact_path = artifact_by_instrument.get(instrument_id)
        if artifact_path is None:
            continue
        candles = candles_from_payload((em1r3_evidence_root / artifact_path).read_bytes())
        by_session: dict[date, list] = defaultdict(list)
        for c in candles:
            by_session[c.ts_open.date()].append(c)
        for d in by_session:
            by_session[d].sort(key=lambda c: c.ts_open)

        for idx in indices:
            row = rows[idx]
            d = date.fromisoformat(row["session_date"])
            session_candles = by_session.get(d)
            if not session_candles:
                continue
            cp_instant = datetime.combine(d, time_cls.fromisoformat(row[CHECKPOINT_FIELD]), tzinfo=IST)
            checkpoint_price = price_at_checkpoint(cp_instant, tuple(session_candles))
            if checkpoint_price is None:
                continue
            ratio = (
                row.get("return_from_open_c") if family == "OPEN_TO_HIGH"
                else row.get("return_from_prev_close_c")
            )
            reference_price = checkpoint_price / (1 + ratio) if ratio is not None else None
            if reference_price is None:
                continue

            excursion = compute_forward_excursion(
                checkpoint_instant=cp_instant, session_candles=tuple(session_candles),
                reference_price=reference_price, threshold_percent=threshold,
                event_family=family, is_positive_label=True,
            )
            results.append(excursion)

    known_mfe = [float(r.mfe_percent) for r in results if r.mfe_percent is not None]
    known_mae = [float(r.mae_percent) for r in results if r.mae_percent is not None]
    known_ttt = [float(r.time_to_target_minutes) for r in results if r.time_to_target_minutes is not None]

    def _stats(values: list[float]) -> dict:
        if not values:
            return {"n": 0, "mean": None, "median": None}
        ordered = sorted(values)
        n = len(ordered)
        median = ordered[n // 2] if n % 2 else (ordered[n // 2 - 1] + ordered[n // 2]) / 2
        return {"n": n, "mean": sum(values) / n, "median": median}

    return {
        "positive_observations_scanned": len(positive_indices),
        "mfe_percent": _stats(known_mfe), "mae_percent": _stats(known_mae),
        "time_to_target_minutes": _stats(known_ttt),
    }


def main() -> None:
    parser = argparse.ArgumentParser(
        description="EM-4E FINAL_TEST evaluation (deterministic vs calibrated logistic vs base rate)."
    )
    parser.add_argument(
        "--partition", type=str, default="FINAL_TEST",
        help="Override for a pre-flight dry run against an already-open partition (e.g. VALIDATION). "
             "The real, sealed run uses the default: FINAL_TEST.",
    )
    parser.add_argument("--em2-dir", type=Path, default=Path("artifacts/research/em2"))
    parser.add_argument("--em1b-labels-dir", type=Path, default=Path("artifacts/research/em1b/labels"))
    parser.add_argument("--em3-dir", type=Path, default=Path("artifacts/research/em3"))
    parser.add_argument("--em4b-dir", type=Path, default=Path("artifacts/research/em4b"))
    parser.add_argument("--em4d-dir", type=Path, default=Path("artifacts/research/em4d"))
    parser.add_argument("--em1r3-checkpoint", type=Path, default=Path("artifacts/research/em1r3/checkpoint.json"))
    parser.add_argument("--em1r3-evidence-root", type=Path, default=Path("artifacts/research/em1r3/intraday"))
    parser.add_argument("--out-dir", type=Path, default=Path("artifacts/research/em4e"))
    parser.add_argument("--skip-excursion", action="store_true")
    args = parser.parse_args()

    started = time_module.monotonic()
    print(f"[{args.partition}] loading EM-3 register + EM-4B artifacts + EM-4D calibration")
    deterministic_rules, bin_edges, em3_run_id = _load_deterministic_rules(args.em3_dir)
    logistic_artifacts = _load_logistic_artifacts(args.em4b_dir)
    calibration_artifacts = _load_calibration_artifacts(args.em4d_dir)

    print(f"[{args.partition}] joining EM-2 evidence with EM-1b labels")
    rows, label_by_key_all, rows_processed = _build_joined_dataset(
        partition=args.partition, em2_dir=args.em2_dir, em1b_labels_dir=args.em1b_labels_dir,
    )
    print(f"  {rows_processed} joined checkpoint rows")

    args.out_dir.mkdir(parents=True, exist_ok=True)
    for family, threshold in FAMILIES_THRESHOLDS:
        key = f"{family}_{threshold}"
        eligible = label_by_key_all[(family, threshold)]
        print(f"scoring {key}: {len(eligible)} eligible rows")
        scored = _score_combo(
            family=family, threshold=threshold, rows=rows, eligible=eligible,
            deterministic_rules=deterministic_rules, bin_edges=bin_edges,
            logistic_artifact=logistic_artifacts[(family, threshold)],
            calibration_by_checkpoint=calibration_artifacts[(family, threshold)],
        )
        row_indices = list(eligible.keys())

        combo_result = {
            "partition": args.partition,
            "calibration_levels_used": scored["calibration_levels_used"],
            "deterministic": {
                "pooled": _pooled_metrics(scored["det_scored"], is_probability=False),
                "cross_section_k": _cross_section_k_metrics(scored["det_scored"], scored["cross_sections"]),
                "checkpoint_stability": _checkpoint_stability(scored["det_scored"], rows, row_indices),
                "regime_stability": _regime_stability(scored["det_scored"], rows, row_indices),
            },
            "logistic_calibrated": {
                "pooled": _pooled_metrics(scored["log_scored"], is_probability=True),
                "cross_section_k": _cross_section_k_metrics(scored["log_scored"], scored["cross_sections"]),
                "checkpoint_stability": _checkpoint_stability(scored["log_scored"], rows, row_indices),
                "regime_stability": _regime_stability(scored["log_scored"], rows, row_indices),
            },
        }
        (args.out_dir / f"{key}.json").write_text(json.dumps(combo_result, indent=2), encoding="utf-8")

    flagship_excursion = None
    if not args.skip_excursion:
        family, threshold = FLAGSHIP
        print(f"[{args.partition}] computing real MFE/MAE/time-to-target for the flagship (TOUCH_10)")
        flagship_excursion = _compute_flagship_excursion(
            family=family, threshold=threshold, rows=rows, eligible=label_by_key_all[(family, threshold)],
            em1r3_checkpoint_path=args.em1r3_checkpoint, em1r3_evidence_root=args.em1r3_evidence_root,
        )
        (args.out_dir / "FLAGSHIP_EXCURSION.json").write_text(
            json.dumps(flagship_excursion, indent=2), encoding="utf-8"
        )

    elapsed = time_module.monotonic() - started
    summary = {
        "contract_version": "em4e-final-test-v1", "partition": args.partition,
        "source_run_ids": {
            "em3_run_id": em3_run_id,
            "em4b_run_ids": {f"{f}_{t}": logistic_artifacts[(f, t)]["run_id"] for f, t in FAMILIES_THRESHOLDS},
        },
        "rows_processed": rows_processed, "flagship": f"{FLAGSHIP[0]}_{FLAGSHIP[1]}",
        "flagship_excursion_computed": flagship_excursion is not None,
        "elapsed_seconds": round(elapsed, 1),
    }
    (args.out_dir / "SUMMARY.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
    print(f"[{args.partition}] all done in {elapsed:.1f}s")


if __name__ == "__main__":
    main()
