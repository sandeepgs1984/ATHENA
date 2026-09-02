"""ID-6B.1B quality-adjusted policy analysis.

Two responsibilities, both read-only research:

1. ``analyze_observations`` -- re-derives quality-adjusted evaluability and
   two candidate-rule variants (dual-timeframe trend, matching the existing
   aggregate ``BULLISH`` label; and an M5-only trend variant) directly from
   an existing ID-6B.1-format ``id6b1_observations.jsonl`` file. No replay
   needed -- ID-6B.1's own harness already records ``five_min_bullish``/
   ``fifteen_min_bullish`` as explicit component fields alongside the
   aggregate label.
2. ``main`` -- optionally drives a FRESH replay for a new session window via
   ID-6B.1's own unmodified ``run_baseline`` (no harness changes), then
   applies the same analysis to the new observations.

No production code is imported or altered beyond what ID-6B.1's own
harness already imports. No DB writes, no provider calls.
"""

from __future__ import annotations

import argparse
import json
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any


def _dual_timeframe_evaluable(row: dict[str, Any]) -> bool:
    """VWAP, M5 trend leg, M15 trend leg, and at least one of RS/RVOL must
    each be genuinely available -- matches the current candidate rule's own
    four named input groups (owner §5)."""
    vwap_ok = bool(row["vwap_available"])
    m5_ok = bool(row["five_min_available"])
    m15_ok = bool(row["fifteen_min_available"])
    rs_or_rvol_ok = (
        row["rs_stock_vs_market"] != "UNKNOWN"
        or row["rs_stock_vs_sector"] != "UNKNOWN"
        or bool(row["rvol_available"])
    )
    return vwap_ok and m5_ok and m15_ok and rs_or_rvol_ok


def _m5_only_evaluable(row: dict[str, Any]) -> bool:
    """Same as above but WITHOUT requiring the M15 leg -- the relaxed
    single-timeframe research variant (owner §7)."""
    vwap_ok = bool(row["vwap_available"])
    m5_ok = bool(row["five_min_available"])
    rs_or_rvol_ok = (
        row["rs_stock_vs_market"] != "UNKNOWN"
        or row["rs_stock_vs_sector"] != "UNKNOWN"
        or bool(row["rvol_available"])
    )
    return vwap_ok and m5_ok and rs_or_rvol_ok


def _dual_timeframe_match(row: dict[str, Any]) -> bool:
    """Identical, by construction, to the existing ``candidate_policy_match``
    field -- the aggregate ``BULLISH`` label already requires both 5m and
    15m to independently be bullish (``_aggregate_trend``, verified by
    source inspection)."""
    return bool(row["candidate_policy_match"])


def _m5_only_match(row: dict[str, Any]) -> bool:
    m5_bullish = row["five_min_bullish"] is True
    rs_or_rvol = bool(row["rs_support"]) or bool(row["rvol_support"])
    return bool(row["vwap_positive"]) and m5_bullish and rs_or_rvol


def analyze_observations(rows: list[dict[str, Any]]) -> dict[str, Any]:
    total = len(rows)

    def _rate(pred, population):
        matched = [r for r in population if pred(r)]
        return {
            "count": len(matched),
            "total": len(population),
            "pct": round(len(matched) / len(population) * 100, 2) if population else 0.0,
        }

    dual_evaluable = [r for r in rows if _dual_timeframe_evaluable(r)]
    m5_only_evaluable = [r for r in rows if _m5_only_evaluable(r)]
    dual_unavailable = total - len(dual_evaluable)

    reason_counts: Counter[str] = Counter()
    for r in rows:
        if _dual_timeframe_evaluable(r):
            continue
        reasons = []
        if not r["vwap_available"]:
            reasons.append("vwap_unavailable")
        if not r["five_min_available"]:
            reasons.append("m5_trend_unavailable")
        if not r["fifteen_min_available"]:
            reasons.append("m15_trend_unavailable")
        if (
            r["rs_stock_vs_market"] == "UNKNOWN"
            and r["rs_stock_vs_sector"] == "UNKNOWN"
            and not r["rvol_available"]
        ):
            reasons.append("rs_and_rvol_both_unavailable")
        reason_counts["+".join(reasons)] += 1

    by_type: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for r in rows:
        by_type[r["decision_type"]].append(r)

    def _type_block(population: list[dict[str, Any]]) -> dict[str, Any]:
        evaluable = [r for r in population if _dual_timeframe_evaluable(r)]
        return {
            "observations": len(population),
            "evaluable": len(evaluable),
            "evaluable_pct": round(len(evaluable) / len(population) * 100, 2) if population else 0.0,
            "vwap_positive_rate": _rate(lambda r: bool(r["vwap_positive"]), population),
            "m5_bullish_rate": _rate(lambda r: r["five_min_bullish"] is True, population),
            "m15_bullish_available_rate": _rate(
                lambda r: r["fifteen_min_available"], population
            ),
            "m15_bullish_rate_when_available": _rate(
                lambda r: r["fifteen_min_bullish"] is True,
                [r for r in population if r["fifteen_min_available"]],
            ),
            "dual_timeframe_bullish_rate": _rate(
                lambda r: r["trend_label"] == "BULLISH", population
            ),
            "rs_support_rate": _rate(lambda r: bool(r["rs_support"]), population),
            "rvol_support_rate": _rate(lambda r: bool(r["rvol_support"]), population),
            "candidate_match_population_rate": _rate(_dual_timeframe_match, population),
            "candidate_match_evaluable_rate": _rate(_dual_timeframe_match, evaluable),
        }

    by_checkpoint: dict[str, dict[str, Any]] = {}
    for cp in sorted({r["checkpoint"] for r in rows}):
        cp_rows = [r for r in rows if r["checkpoint"] == cp]
        evaluable = [r for r in cp_rows if _dual_timeframe_evaluable(r)]
        by_checkpoint[cp] = {
            "observations": len(cp_rows),
            "evaluable": len(evaluable),
            "evaluable_pct": round(len(evaluable) / len(cp_rows) * 100, 2) if cp_rows else 0.0,
            "match_population_pct": _rate(_dual_timeframe_match, cp_rows)["pct"],
            "match_evaluable_pct": _rate(_dual_timeframe_match, evaluable)["pct"],
        }

    # Flicker, recomputed under corrected match definition (identical to
    # candidate_policy_match, included for completeness/parity check).
    groups: dict[tuple[str, str, str], list[dict[str, Any]]] = defaultdict(list)
    for r in rows:
        groups[(r["instrument_id"], r["session_date"], r["decision_type"])].append(r)
    multi = 0
    true_then_false = 0
    for group_rows in groups.values():
        ordered = sorted(group_rows, key=lambda r: r["checkpoint"])
        if len(ordered) < 2:
            continue
        multi += 1
        values = [_dual_timeframe_match(r) for r in ordered]
        if True in values:
            idx = values.index(True)
            if any(not v for v in values[idx + 1 :]):
                true_then_false += 1

    return {
        "total_observations": total,
        "dual_timeframe_evaluable": len(dual_evaluable),
        "dual_timeframe_evaluable_pct": round(len(dual_evaluable) / total * 100, 2) if total else 0.0,
        "dual_timeframe_unavailable": dual_unavailable,
        "dual_timeframe_unavailable_pct": round(dual_unavailable / total * 100, 2) if total else 0.0,
        "non_evaluability_reasons": dict(reason_counts.most_common()),
        "m5_only_evaluable": len(m5_only_evaluable),
        "m5_only_evaluable_pct": round(len(m5_only_evaluable) / total * 100, 2) if total else 0.0,
        "candidate_match_dual_population": _rate(_dual_timeframe_match, rows),
        "candidate_match_dual_evaluable": _rate(_dual_timeframe_match, dual_evaluable),
        "candidate_match_m5_only_population": _rate(_m5_only_match, rows),
        "candidate_match_m5_only_evaluable": _rate(_m5_only_match, m5_only_evaluable),
        "by_decision_type": {t: _type_block(rows_) for t, rows_ in by_type.items()},
        "by_checkpoint": by_checkpoint,
        "flicker_dual_evaluable_definition": {
            "multi_checkpoint_groups": multi,
            "true_then_later_false": true_then_false,
            "true_then_later_false_pct": round(true_then_false / multi * 100, 2) if multi else 0.0,
        },
    }


def analyze_jsonl(path: Path) -> dict[str, Any]:
    rows = []
    with path.open() as fh:
        for line in fh:
            line = line.strip()
            if line:
                rows.append(json.loads(line))
    return analyze_observations(rows)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--observations", type=Path, required=True)
    parser.add_argument("--output", type=Path, default=None)
    args = parser.parse_args()
    result = analyze_jsonl(args.observations)
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        with args.output.open("w") as fh:
            json.dump(result, fh, indent=2, sort_keys=True)
    print(json.dumps(result, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
