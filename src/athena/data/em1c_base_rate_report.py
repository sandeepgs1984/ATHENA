"""EM-1c: TRAIN-only base-rate research report.

Owner-approved scope (2026-08-26): TRAIN partition only -- VALIDATION,
CALIBRATION, and FINAL_TEST remain untouched by any reporting at this
stage. Reads directly from EM-1b's own approved, persisted output
(``artifacts/research/em1b/labels/TRAIN_*.jsonl.gz``) -- the frozen,
already-generated dataset, not a parallel re-derivation.

Marginal (single-dimension) breakdowns only, per the roadmap's own EM-1c
scope ("No feature lift is claimed here" -- multi-way interactions are
EM-3's job): base rates by event family, threshold, checkpoint, TRAIN-
period year, sector, and canonical regime (trend/volatility/gap).

Sector comes from the canonical `instruments` table (read-only); regime
comes from EM-1c's own prerequisite evidence
(``artifacts/research/em1c-regime/regime_by_session.json``). Neither
canonical table nor regime evidence is mutated. Every reported rate
carries its Wilson 95% confidence interval and raw support (n, k).
"""

from __future__ import annotations

import argparse
import gzip
import json
import sqlite3
from collections import Counter, defaultdict
from pathlib import Path

from athena.explosive_move.wilson_interval import meets_minimum_support, wilson_interval

FAMILIES = ("TOUCH", "CLOSE", "OPEN_TO_HIGH")
THRESHOLDS = (5, 8, 10, 12, 15, 20)
CHECKPOINTS = ("09:20", "09:30", "09:45", "10:00", "10:30", "11:00", "12:00", "13:00", "14:00")


def _sector_by_instrument(db_path: Path, instrument_ids: set[str]) -> dict[str, str]:
    conn = sqlite3.connect(db_path)
    try:
        placeholders = ",".join("?" for _ in instrument_ids)
        cur = conn.execute(
            f"SELECT instrument_id, sector FROM instruments WHERE instrument_id IN ({placeholders})",
            tuple(instrument_ids),
        )
        return {iid: (sector or "UNKNOWN") for iid, sector in cur.fetchall()}
    finally:
        conn.close()


def _regime_by_session(path: Path) -> dict[str, dict]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    return {row["session_date"]: row for row in payload["sessions"]}


def _rate_record(counters: dict[tuple, Counter], key: tuple) -> dict:
    c = counters[key]
    pos, neg = c.get("POSITIVE", 0), c.get("NEGATIVE", 0)
    n = pos + neg
    interval = wilson_interval(pos, n) if n else wilson_interval(0, 0)
    return {
        "eligible_n": n, "positive_k": pos, "negative_n": neg,
        "rate": interval.point_estimate, "wilson_95_lower": interval.lower,
        "wilson_95_upper": interval.upper, "wilson_95_half_width": interval.half_width,
        "meets_minimum_support": meets_minimum_support(eligible_n=n, positive_k=pos),
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="EM-1c TRAIN-only base-rate report.")
    parser.add_argument("--db", type=Path, default=Path("db/athena.db"))
    parser.add_argument("--em1b-labels-dir", type=Path, default=Path("artifacts/research/em1b/labels"))
    parser.add_argument(
        "--regime-evidence", type=Path,
        default=Path("artifacts/research/em1c-regime/regime_by_session.json"),
    )
    parser.add_argument("--out", type=Path, default=Path("artifacts/research/em1c/base_rate_report.json"))
    args = parser.parse_args()

    regime_by_session = _regime_by_session(args.regime_evidence)

    # ---- pass 1: symbol_day level -- family x threshold, x year, x sector, x regime ----
    by_family_threshold: dict[tuple, Counter] = defaultdict(Counter)
    by_family_threshold_year: dict[tuple, Counter] = defaultdict(Counter)
    by_family_threshold_sector: dict[tuple, Counter] = defaultdict(Counter)
    by_family_threshold_trend: dict[tuple, Counter] = defaultdict(Counter)
    by_family_threshold_volatility: dict[tuple, Counter] = defaultdict(Counter)
    by_family_threshold_gap: dict[tuple, Counter] = defaultdict(Counter)

    instrument_ids: set[str] = set()
    sd_path = args.em1b_labels_dir / "TRAIN_symbol_day.jsonl.gz"
    print(f"pass 1/3: scanning {sd_path} for instrument ids")
    with gzip.open(sd_path, "rt", encoding="utf-8") as f:
        for line in f:
            row = json.loads(line)
            instrument_ids.add(row["instrument_id"])
    sector_by_instrument = _sector_by_instrument(args.db, instrument_ids)

    print(f"pass 2/3: aggregating {sd_path}")
    row_count = 0
    with gzip.open(sd_path, "rt", encoding="utf-8") as f:
        for line in f:
            row = json.loads(line)
            row_count += 1
            label = row["label"]
            if label is None:
                continue
            fam, th = row["event_family"], row["threshold_percent"]
            year = row["session_date"][:4]
            sector = sector_by_instrument.get(row["instrument_id"], "UNKNOWN")
            regime = regime_by_session.get(row["session_date"])

            by_family_threshold[(fam, th)][label] += 1
            by_family_threshold_year[(fam, th, year)][label] += 1
            by_family_threshold_sector[(fam, th, sector)][label] += 1
            if regime is not None:
                by_family_threshold_trend[(fam, th, regime["trend"])][label] += 1
                by_family_threshold_volatility[(fam, th, regime["volatility"])][label] += 1
                by_family_threshold_gap[(fam, th, regime["gap"])][label] += 1

    print(f"  {row_count} symbol_day rows scanned")

    # ---- pass 3: checkpoint level -- family x threshold x checkpoint (incl. ALREADY_OCCURRED) ----
    by_family_threshold_checkpoint: dict[tuple, Counter] = defaultdict(Counter)
    cp_path = args.em1b_labels_dir / "TRAIN_checkpoint.jsonl.gz"
    print(f"pass 3/3: aggregating {cp_path}")
    cp_row_count = 0
    with gzip.open(cp_path, "rt", encoding="utf-8") as f:
        for line in f:
            row = json.loads(line)
            cp_row_count += 1
            label = row["label"]
            if label is None:
                continue
            key = (row["event_family"], row["threshold_percent"], row["checkpoint_ist"])
            by_family_threshold_checkpoint[key][label] += 1
    print(f"  {cp_row_count} checkpoint rows scanned")

    # ---- build report ----
    report: dict = {
        "contract_version": "em1c-base-rate-report-v1",
        "partition": "TRAIN",
        "instrument_count": len(instrument_ids),
        "by_family_threshold": {},
        "by_family_threshold_year": {},
        "by_family_threshold_sector": {},
        "by_family_threshold_checkpoint": {},
        "by_family_threshold_regime_trend": {},
        "by_family_threshold_regime_volatility": {},
        "by_family_threshold_regime_gap": {},
    }

    for fam in FAMILIES:
        for th in THRESHOLDS:
            report["by_family_threshold"][f"{fam}:{th}"] = _rate_record(by_family_threshold, (fam, th))

    for (fam, th, year), _ in by_family_threshold_year.items():
        report["by_family_threshold_year"][f"{fam}:{th}:{year}"] = _rate_record(
            by_family_threshold_year, (fam, th, year)
        )
    for (fam, th, sector), _ in by_family_threshold_sector.items():
        report["by_family_threshold_sector"][f"{fam}:{th}:{sector}"] = _rate_record(
            by_family_threshold_sector, (fam, th, sector)
        )
    for fam in FAMILIES:
        for th in THRESHOLDS:
            for cp in CHECKPOINTS:
                key = (fam, th, cp)
                c = by_family_threshold_checkpoint[key]
                pos, neg, already = c.get("POSITIVE", 0), c.get("NEGATIVE", 0), c.get("ALREADY_OCCURRED", 0)
                n = pos + neg
                interval = wilson_interval(pos, n) if n else wilson_interval(0, 0)
                report["by_family_threshold_checkpoint"][f"{fam}:{th}:{cp}"] = {
                    "eligible_forward_n": n, "positive_k": pos, "negative_n": neg,
                    "already_occurred": already,
                    "rate": interval.point_estimate, "wilson_95_lower": interval.lower,
                    "wilson_95_upper": interval.upper,
                    "meets_minimum_support": meets_minimum_support(eligible_n=n, positive_k=pos),
                }
    for (fam, th, label), _ in by_family_threshold_trend.items():
        report["by_family_threshold_regime_trend"][f"{fam}:{th}:{label}"] = _rate_record(
            by_family_threshold_trend, (fam, th, label)
        )
    for (fam, th, label), _ in by_family_threshold_volatility.items():
        report["by_family_threshold_regime_volatility"][f"{fam}:{th}:{label}"] = _rate_record(
            by_family_threshold_volatility, (fam, th, label)
        )
    for (fam, th, label), _ in by_family_threshold_gap.items():
        report["by_family_threshold_regime_gap"][f"{fam}:{th}:{label}"] = _rate_record(
            by_family_threshold_gap, (fam, th, label)
        )

    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(report, indent=2, sort_keys=False), encoding="utf-8")
    print(f"wrote {args.out}")


if __name__ == "__main__":
    main()
