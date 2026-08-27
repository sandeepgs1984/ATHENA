"""EM-3 v1: univariate, checkpoint-level, TRAIN-only conditional
analysis. Joins EM-2's evidence (session-invariant + checkpoint-dynamic)
with EM-1b's checkpoint-level forward labels, against EM-1c's own
checkpoint-specific unconditional base rates.

Read-only against EM-1b/EM-1c/EM-2's already-approved outputs;
write-only against `artifacts/research/em3/` (git-ignored). Formal
ranking operates on CANDIDATE_FEATURE fields only (22 of 28); the 6
EVIDENCE_ONLY fields (ATR14, MACD_HIST, CUM_VOLUME_C, HIGH_SO_FAR_C,
LOW_SO_FAR_C, VWAP_THROUGH_C) are excluded from this analysis entirely,
per the owner's classification.
"""

from __future__ import annotations

import argparse
import gzip
import hashlib
import json
import time as time_module
from collections import Counter, defaultdict
from decimal import Decimal, InvalidOperation
from pathlib import Path

from athena.explosive_move.conditional_analysis import (
    BIN_EDGE_CONTRACT_VERSION,
    UNKNOWN_HANDLING_POLICY,
    Shape,
    SupportLabel,
    assign_bin,
    bin_label,
    classify_shape,
    compute_conditional_cell,
    compute_quintile_edges,
)
from athena.explosive_move.evidence_contract import ALL_FIELDS, Classification, Timing

FAMILIES = ("TOUCH", "CLOSE", "OPEN_TO_HIGH")
THRESHOLDS = (5, 8, 10, 12, 15, 20)
CHECKPOINTS = ("09:20", "09:30", "09:45", "10:00", "10:30", "11:00", "12:00", "13:00", "14:00")

_CATEGORICAL_FIELDS = {"regime_trend", "regime_volatility", "regime_gap"}
_REGIME_FIELD_STRATUM = {
    "regime_trend": "TREND", "regime_volatility": "VOLATILITY", "regime_gap": "GAP",
}


def _field_key(name: str) -> str:
    return name.lower()


def candidate_fields() -> tuple[tuple[str, Timing], ...]:
    return tuple(
        (_field_key(f.name), f.timing)
        for f in ALL_FIELDS
        if f.classification is Classification.CANDIDATE_FEATURE
    )


def _read_jsonl_gz(path: Path):
    with gzip.open(path, "rt", encoding="utf-8") as f:
        for line in f:
            yield json.loads(line)


def _grouped_by_instrument(path: Path):
    """Yield (instrument_id, list[row]) -- valid ONLY because every EM-1b/
    EM-2 generator in this workstream iterates instruments in the same
    sorted() order over the same EM-1r3-derived instrument set, so all of
    one instrument's rows are contiguous."""

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


def main() -> None:
    parser = argparse.ArgumentParser(description="EM-3 v1 conditional analysis (TRAIN only).")
    parser.add_argument("--em2-dir", type=Path, default=Path("artifacts/research/em2"))
    parser.add_argument("--em1b-labels-dir", type=Path, default=Path("artifacts/research/em1b/labels"))
    parser.add_argument("--em1c-report", type=Path, default=Path("artifacts/research/em1c/base_rate_report.json"))
    parser.add_argument("--out-dir", type=Path, default=Path("artifacts/research/em3"))
    args = parser.parse_args()

    started = time_module.monotonic()
    em1c_report = json.loads(args.em1c_report.read_text(encoding="utf-8"))
    checkpoint_baselines = em1c_report["by_family_threshold_checkpoint"]

    fields = candidate_fields()
    invariant_fields = tuple(name for name, timing in fields if timing.name == "SESSION_INVARIANT")
    dynamic_fields = tuple(name for name, timing in fields if timing.name == "CHECKPOINT_DYNAMIC")

    # ------------------------------------------------------------------ #
    # Pass 0: bin edges, derived solely from each continuous candidate
    # feature's own real, known-only TRAIN distribution -- never from
    # labels. Categorical fields skip this (analyzed by real category).
    # ------------------------------------------------------------------ #
    print("pass 0/2: deriving bin edges from real TRAIN distributions")
    values_by_field: dict[str, list[Decimal]] = defaultdict(list)
    for name in invariant_fields:
        if name in _CATEGORICAL_FIELDS:
            continue
        values_by_field[name] = []
    for row in _read_jsonl_gz(args.em2_dir / "TRAIN_session_invariant.jsonl.gz"):
        for name in invariant_fields:
            if name in _CATEGORICAL_FIELDS:
                continue
            v = row[name]["value"]
            if v is not None:
                values_by_field[name].append(_to_decimal(v))
    for row in _read_jsonl_gz(args.em2_dir / "TRAIN_checkpoint_dynamic.jsonl.gz"):
        for name in dynamic_fields:
            v = row[name]["value"]
            if v is not None:
                values_by_field.setdefault(name, []).append(_to_decimal(v))

    bin_edges: dict[str, tuple[Decimal, ...]] = {}
    for name, values in values_by_field.items():
        bin_edges[name] = compute_quintile_edges(values)
        print(f"  {name}: {len(values)} known values -> {len(bin_edges[name]) + 1} real bins")
    values_by_field.clear()  # release the large value lists before pass 1

    # ------------------------------------------------------------------ #
    # Pass 1: join EM-2 evidence with EM-1b labels, per instrument, and
    # accumulate (feature, bin/category, family, threshold, checkpoint,
    # stratum) -> Counter(label). stratum in {"ALL", "TREND:<v>",
    # "VOLATILITY:<v>", "GAP:<v>"} (regime stratification is skipped for
    # a regime field stratified by itself).
    # ------------------------------------------------------------------ #
    print("pass 1/2: joining EM-2 evidence with EM-1b labels and aggregating")
    counts: dict[tuple, Counter] = defaultdict(Counter)
    rows_processed = 0

    em1b_groups = _grouped_by_instrument(args.em1b_labels_dir / "TRAIN_checkpoint.jsonl.gz")
    invariant_groups = _grouped_by_instrument(args.em2_dir / "TRAIN_session_invariant.jsonl.gz")
    dynamic_groups = _grouped_by_instrument(args.em2_dir / "TRAIN_checkpoint_dynamic.jsonl.gz")

    def _advance(gen):
        try:
            return next(gen)
        except StopIteration:
            return None

    em1b_cur = _advance(em1b_groups)
    inv_cur = _advance(invariant_groups)
    dyn_cur = _advance(dynamic_groups)

    while em1b_cur is not None and inv_cur is not None and dyn_cur is not None:
        ids = (em1b_cur[0], inv_cur[0], dyn_cur[0])
        target = min(ids)
        if em1b_cur[0] != target:
            em1b_cur = _advance(em1b_groups)
            continue
        if inv_cur[0] != target:
            inv_cur = _advance(invariant_groups)
            continue
        if dyn_cur[0] != target:
            dyn_cur = _advance(dynamic_groups)
            continue

        # all three streams agree on `target` -- join this instrument.
        label_by_key: dict[tuple, str] = {}
        for row in em1b_cur[1]:
            if row["label"] is None:
                continue
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

            field_bins: dict[str, str] = {}
            for name in dynamic_fields:
                v = dyn_row[name]["value"]
                if name in _CATEGORICAL_FIELDS:
                    field_bins[name] = v if v is not None else "UNKNOWN"
                elif v is None:
                    field_bins[name] = "UNKNOWN"
                else:
                    idx = assign_bin(_to_decimal(v), bin_edges[name])
                    field_bins[name] = bin_label(idx, bin_edges[name])
            for name in invariant_fields:
                v = inv_row[name]["value"]
                if name in _CATEGORICAL_FIELDS:
                    field_bins[name] = v if v is not None else "UNKNOWN"
                elif v is None:
                    field_bins[name] = "UNKNOWN"
                else:
                    idx = assign_bin(_to_decimal(v), bin_edges[name])
                    field_bins[name] = bin_label(idx, bin_edges[name])

            regime_strata = []
            for regime_field, stratum_prefix in _REGIME_FIELD_STRATUM.items():
                v = inv_row[regime_field]["value"]
                if v is not None:
                    regime_strata.append(f"{stratum_prefix}:{v}")

            for family in FAMILIES:
                for threshold in THRESHOLDS:
                    label = label_by_key.get((d, cp, family, threshold))
                    if label is None:
                        continue
                    for feature_name, feature_bin in field_bins.items():
                        base_key = (feature_name, feature_bin, family, threshold, cp)
                        counts[(*base_key, "ALL")][label] += 1
                        for stratum in regime_strata:
                            regime_dim = stratum.split(":", 1)[0]
                            if _REGIME_FIELD_STRATUM.get(feature_name) == regime_dim:
                                continue  # never self-stratify a regime field by itself
                            counts[(*base_key, stratum)][label] += 1

        em1b_cur = _advance(em1b_groups)
        inv_cur = _advance(invariant_groups)
        dyn_cur = _advance(dynamic_groups)

    elapsed = time_module.monotonic() - started
    print(f"  {rows_processed} joined checkpoint rows; {len(counts)} aggregation cells; {elapsed:.1f}s elapsed")

    # ------------------------------------------------------------------ #
    # Assemble output reports.
    # ------------------------------------------------------------------ #
    print("assembling reports")
    feature_conditional: dict[str, dict] = {}
    shape_report: dict[str, dict] = {}
    checkpoint_evolution: dict[str, list] = defaultdict(list)
    regime_stability: dict[str, dict] = {}
    unsupported_report: dict[str, dict] = {}
    candidate_register: list[dict] = []

    all_bin_keys = sorted({k[:5] for k in counts if k[5] == "ALL"})

    # group_totals[(feature,family,threshold,cp)] = (pos,neg) summed over
    # every KNOWN (non-UNKNOWN) bin of that feature in that group -- lets
    # complement be computed as group_total - this_bin in O(1), instead of
    # an O(bins-per-group) rescan per cell.
    group_totals: dict[tuple, tuple[int, int]] = defaultdict(lambda: (0, 0))
    for feature_name, feature_bin, family, threshold, cp in all_bin_keys:
        if feature_bin == "UNKNOWN":
            continue
        c = counts[(feature_name, feature_bin, family, threshold, cp, "ALL")]
        gp, gn = group_totals[(feature_name, family, threshold, cp)]
        group_totals[(feature_name, family, threshold, cp)] = (
            gp + c.get("POSITIVE", 0), gn + c.get("NEGATIVE", 0),
        )

    for feature_name, feature_bin, family, threshold, cp in all_bin_keys:
        baseline_key = f"{family}:{threshold}:{cp}"
        baseline = checkpoint_baselines.get(baseline_key, {"rate": 0.0})
        c = counts[(feature_name, feature_bin, family, threshold, cp, "ALL")]
        pos, neg = c.get("POSITIVE", 0), c.get("NEGATIVE", 0)

        if feature_bin == "UNKNOWN":
            complement_pos = complement_neg = 0
        else:
            group_pos, group_neg = group_totals[(feature_name, family, threshold, cp)]
            complement_pos, complement_neg = group_pos - pos, group_neg - neg

        cell = compute_conditional_cell(
            positive_k=pos, negative_n=neg, baseline_rate=baseline["rate"],
            complement_positive_k=complement_pos, complement_negative_n=complement_neg,
        )

        row_key = f"{feature_name}:{feature_bin}:{family}:{threshold}:{cp}"
        is_unknown_bin = feature_bin == "UNKNOWN"
        record = {
            "feature": feature_name, "bin": feature_bin, "family": family, "threshold": threshold,
            "checkpoint": cp, "eligible_n": cell.eligible_n, "positive_k": cell.positive_k,
            "rate": cell.rate, "wilson_95_lower": cell.wilson_95_lower, "wilson_95_upper": cell.wilson_95_upper,
            "baseline_rate": cell.baseline_rate, "absolute_difference": cell.absolute_difference,
            "lift": cell.lift, "complement_n": cell.complement_n, "complement_k": cell.complement_k,
            "complement_rate": cell.complement_rate, "risk_ratio": cell.risk_ratio,
            "already_occurred": c.get("ALREADY_OCCURRED", 0),
        }

        if is_unknown_bin:
            record["classification"] = SupportLabel.MISSINGNESS_DIAGNOSTIC.value
            unsupported_report[row_key] = record
        elif cell.support_label is SupportLabel.INSUFFICIENT_SUPPORT:
            record["classification"] = SupportLabel.INSUFFICIENT_SUPPORT.value
            unsupported_report[row_key] = record
        else:
            record["classification"] = SupportLabel.EXPLORATORY_CANDIDATE.value
            record["provenance"] = "TRAIN-DISCOVERED / UNVALIDATED"
            feature_conditional[row_key] = record
            checkpoint_evolution[f"{feature_name}:{feature_bin}:{family}:{threshold}"].append(
                {"checkpoint": cp, "rate": cell.rate, "lift": cell.lift, "eligible_n": cell.eligible_n}
            )

    # shape analysis: per (feature, family, threshold, checkpoint), across
    # the real ordered quintile bins (Q1..Qn), for continuous features only.
    by_ordered_group: dict[tuple, dict[int, float]] = defaultdict(dict)
    for feature_name, feature_bin, family, threshold, cp in all_bin_keys:
        if feature_name in _CATEGORICAL_FIELDS or feature_bin == "UNKNOWN":
            continue
        c = counts[(feature_name, feature_bin, family, threshold, cp, "ALL")]
        pos, neg = c.get("POSITIVE", 0), c.get("NEGATIVE", 0)
        n = pos + neg
        rate = pos / n if n else 0.0
        q_index = int(feature_bin.split("(")[0][1:]) - 1  # "Q3(...)" -> 2
        by_ordered_group[(feature_name, family, threshold, cp)][q_index] = rate
    for (feature_name, family, threshold, cp), by_q in by_ordered_group.items():
        ordered = [by_q[i] for i in sorted(by_q)]
        shape_report[f"{feature_name}:{family}:{threshold}:{cp}"] = {
            "ordered_bin_rates": ordered, "shape": classify_shape(ordered).value,
        }

    # regime stability: for every EXPLORATORY_CANDIDATE cell, its behavior
    # under each real regime stratum it has data for. Index once (O(total
    # count keys)) instead of rescanning `counts` per candidate.
    strata_by_base5: dict[tuple, dict[str, Counter]] = defaultdict(dict)
    for full_key, c in counts.items():
        stratum = full_key[5]
        if stratum == "ALL":
            continue
        strata_by_base5[full_key[:5]][stratum] = c

    for row_key in feature_conditional:
        feature_name, feature_bin, family, threshold_str, cp = row_key.split(":", 4)
        threshold = int(threshold_str)
        strata_results = {}
        for stratum, sc in strata_by_base5.get((feature_name, feature_bin, family, threshold, cp), {}).items():
            spos, sneg = sc.get("POSITIVE", 0), sc.get("NEGATIVE", 0)
            n = spos + sneg
            supported = n >= 1000 and spos >= 10
            strata_results[stratum] = {
                "eligible_n": n, "positive_k": spos,
                "rate": (spos / n) if n else 0.0,
                "support": SupportLabel.EXPLORATORY_CANDIDATE.value if supported
                else SupportLabel.INSUFFICIENT_SUPPORT.value,
            }
        if strata_results:
            regime_stability[row_key] = strata_results

    for row_key, record in feature_conditional.items():
        feature_name, feature_bin, family, threshold_str, cp = row_key.split(":", 4)
        candidate_register.append({
            **record,
            "regime_behavior": regime_stability.get(row_key, {}),
            "shape": shape_report.get(f"{feature_name}:{family}:{threshold_str}:{cp}", {}).get(
                "shape", Shape.NOT_APPLICABLE.value
            ),
            "checkpoint_evolution_key": f"{feature_name}:{feature_bin}:{family}:{threshold_str}",
        })

    output = {
        "contract_version": "em3-conditional-analysis-v1",
        "bin_edge_contract_version": BIN_EDGE_CONTRACT_VERSION,
        "unknown_handling_policy": UNKNOWN_HANDLING_POLICY,
        "partition": "TRAIN",
        "rows_processed": rows_processed,
        "aggregation_cell_count": len(counts),
        "elapsed_seconds": round(elapsed, 1),
        "bin_edges": {name: [str(e) for e in edges] for name, edges in bin_edges.items()},
        "deferred_scope": [
            "pairwise feature interactions", "multi-way combinations", "rule mining",
            "ML models", "decision trees", "automatic feature crossing",
            "feature-weight optimization",
        ],
    }

    args.out_dir.mkdir(parents=True, exist_ok=True)
    (args.out_dir / "A_feature_conditional_analysis.json").write_text(
        json.dumps(feature_conditional, indent=2), encoding="utf-8"
    )
    (args.out_dir / "B_feature_shape_report.json").write_text(
        json.dumps(shape_report, indent=2), encoding="utf-8"
    )
    (args.out_dir / "C_checkpoint_evolution_report.json").write_text(
        json.dumps(dict(checkpoint_evolution), indent=2), encoding="utf-8"
    )
    (args.out_dir / "D_regime_stability_report.json").write_text(
        json.dumps(regime_stability, indent=2), encoding="utf-8"
    )
    (args.out_dir / "E_unsupported_unknown_report.json").write_text(
        json.dumps(unsupported_report, indent=2), encoding="utf-8"
    )
    (args.out_dir / "F_exploratory_candidate_register.json").write_text(
        json.dumps(candidate_register, indent=2), encoding="utf-8"
    )

    # elapsed_seconds is a genuine wall-clock measurement (varies run to
    # run even when the output data is byte-identical) -- excluded from
    # the fingerprint, matching the created_at exclusion convention
    # established in EM-1b/EM-1c/EM-2's own manifests.
    fingerprint = hashlib.sha256(
        json.dumps(
            {k: v for k, v in output.items() if k != "elapsed_seconds"},
            sort_keys=True, separators=(",", ":"),
        ).encode("utf-8")
    ).hexdigest()
    output["run_id"] = f"em3-conditional-{fingerprint}"
    (args.out_dir / "manifest.json").write_text(json.dumps(output, indent=2), encoding="utf-8")
    print(json.dumps({
        "run_id": output["run_id"], "rows_processed": rows_processed,
        "aggregation_cell_count": len(counts),
        "exploratory_candidates": len(feature_conditional),
        "insufficient_or_missingness": len(unsupported_report),
        "elapsed_seconds": round(elapsed, 1),
    }, indent=2))


if __name__ == "__main__":
    main()
