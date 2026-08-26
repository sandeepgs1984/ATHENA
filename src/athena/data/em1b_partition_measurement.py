"""EM-1b partition-proposal measurement: real per-date eligible/positive/
ALREADY_OCCURRED counts across the full frozen study window, broken down
by event family, threshold, and checkpoint -- the evidence the owner
requires before proposing chronological TRAIN/VALIDATION/CALIBRATION/
FINAL_TEST cutoff dates. Does not persist a full labeled dataset; produces
only the aggregate distribution needed to choose partition boundaries.

Read-only: no Kite calls, no canonical-table writes. Reuses, unmodified:
EM-1a's frozen readiness contract (`contracts.py`), EM-1r4's frozen
cohort-admission contract, the EM-1r5 corporate-action boundary contract,
and the EM-1b forward-label contract (`event_labels.py`).

Performance note: for each (instrument, session_date, event_family,
threshold) combination, TOUCH/OPEN_TO_HIGH compute a single first-touch
time via one forward candle scan, then derive all 9 checkpoints' outcomes
from that single value (ALREADY_OCCURRED iff touch_time < checkpoint_ist;
POSITIVE iff touch_time >= checkpoint_ist; NEGATIVE iff no touch) --
mathematically identical to calling `evaluate_touch_label` nine times
independently (proven by a dedicated equivalence test), just ~9x cheaper.
"""

from __future__ import annotations

import argparse
import json
from collections import Counter, defaultdict
from datetime import date, datetime, time
from pathlib import Path
from zoneinfo import ZoneInfo

from athena.data.store.repository import SqliteRepository
from athena.explosive_move.cohort_admission import assess_symbol_day_cohort_admission
from athena.explosive_move.contracts import (
    CANDIDATE_CHECKPOINTS_IST,
    EVENT_FAMILIES,
    EVENT_THRESHOLDS_PERCENT,
    CorporateActionCoverage,
    EventFamily,
    assess_checkpoint_readiness,
    assess_symbol_day_readiness,
)
from athena.explosive_move.corporate_action_boundary import corporate_action_crosses_boundary
from athena.explosive_move.corporate_action_coverage import (
    SURVIVOR_COHORT_LIMITATION,
    SURVIVOR_COHORT_NAME,
    SurvivorCohort,
)
from athena.explosive_move.event_labels import (
    ForwardLabelOutcome,
    first_touch_time,
    outcome_from_touch_time,
    threshold_price,
)
from athena.explosive_move.intraday_reconstruction import (
    candles_from_payload,
    intraday_manifest_from_payload,
)

IST = ZoneInfo("Asia/Kolkata")


def main() -> None:
    parser = argparse.ArgumentParser(description="EM-1b partition-proposal measurement.")
    parser.add_argument("--db", type=Path, default=Path("db/athena.db"))
    parser.add_argument(
        "--em1r2-manifest", type=Path,
        default=Path(
            "artifacts/research/em1r2/corporate-actions/manifests/"
            "8e1fd6c17365abe1a5ea3ac41fc00f83d36d8c972ef1ea7d725e51d28272a22c.json"
        ),
    )
    parser.add_argument("--em1r3-checkpoint", type=Path, default=Path("artifacts/research/em1r3/checkpoint.json"))
    parser.add_argument("--em1r3-evidence-root", type=Path, default=Path("artifacts/research/em1r3/intraday"))
    parser.add_argument("--universe", default="athena_core")
    parser.add_argument("--cohort-resolution-date", type=date.fromisoformat, required=True)
    parser.add_argument("--out", type=Path, default=Path("artifacts/research/em1b/partition_measurement.json"))
    args = parser.parse_args()

    em1r2 = json.loads(args.em1r2_manifest.read_text(encoding="utf-8"))
    complete = all(s.get("complete") for s in em1r2["retrieval_slices"])
    coverage = CorporateActionCoverage(
        authoritative_start=date.fromisoformat(em1r2["study_start"]) if complete else None,
        authoritative_end=date.fromisoformat(em1r2["study_end"]) if complete else None,
        action_count=len(em1r2["actions"]),
    )
    ex_dates_by_instrument: dict[str, set[date]] = defaultdict(set)
    for action in em1r2["actions"]:
        ex_dates_by_instrument[action["instrument_id"]].add(date.fromisoformat(action["ex_date"]))

    repository = SqliteRepository(args.db)
    try:
        instruments = tuple(repository.list_instruments())
        instrument_ids = tuple(repository.list_resolved_universe(args.universe))
    finally:
        repository.close()
    listing_by_id = {i.instrument_id: i for i in instruments}

    em1r3_checkpoint = json.loads(args.em1r3_checkpoint.read_text())
    manifests = [
        intraday_manifest_from_payload((args.em1r3_evidence_root / p).read_bytes())
        for p in em1r3_checkpoint["batch_manifest_paths"]
    ]
    study_start = manifests[0].study_start
    study_end = manifests[0].study_end

    cohort = SurvivorCohort(
        name=SURVIVOR_COHORT_NAME, universe_name=args.universe,
        resolution_date=args.cohort_resolution_date,
        instrument_ids=tuple(sorted(set(instrument_ids))),
        group_effective_dates=((args.universe, args.cohort_resolution_date),),
        limitation=SURVIVOR_COHORT_LIMITATION,
    )
    cohort_membership_ok: dict[str, bool] = {}
    for instrument_id in cohort.instrument_ids:
        listing = listing_by_id.get(instrument_id)
        admission = assess_symbol_day_cohort_admission(
            instrument_id=instrument_id, session_date=study_end,
            listed_date=listing.listed_date if listing else None,
            delisted_date=listing.delisted_date if listing else None,
            cohort=cohort,
        )
        cohort_membership_ok[instrument_id] = admission.admitted

    admitted_dates_by_instrument: dict[str, list[date]] = defaultdict(list)
    for m in manifests:
        for r in m.sessions:
            if r.status == "ADMITTED":
                admitted_dates_by_instrument[r.instrument_id].append(r.session_date)
    for instrument_id in admitted_dates_by_instrument:
        admitted_dates_by_instrument[instrument_id].sort()

    checkpoint_instants = tuple(
        (cp, time.fromisoformat(cp)) for cp in CANDIDATE_CHECKPOINTS_IST
    )

    # per-date -> per-(scope) -> Counter(outcome/excluded)
    # scope key: f"{family}:{threshold}:{checkpoint_ist_or_SYMBOLDAY}"
    by_date: dict[str, Counter] = defaultdict(Counter)
    dates_seen: set[date] = set()

    for m in manifests:
        for artifact in m.normalized_artifacts:
            instrument_id = artifact.instrument_id
            admitted_dates = admitted_dates_by_instrument.get(instrument_id, [])
            if len(admitted_dates) < 2:
                continue
            candles = candles_from_payload(
                (args.em1r3_evidence_root / artifact.artifact).read_bytes()
            )
            by_session_date: dict[date, list] = defaultdict(list)
            for c in candles:
                by_session_date[c.ts_open.date()].append(c)
            for d in by_session_date:
                by_session_date[d].sort(key=lambda c: c.ts_open)

            ex_dates = frozenset(ex_dates_by_instrument.get(instrument_id, set()))
            membership_ok = cohort_membership_ok.get(instrument_id, False)

            for idx in range(1, len(admitted_dates)):
                d = admitted_dates[idx]
                prev_d = admitted_dates[idx - 1]
                if prev_d not in by_session_date or d not in by_session_date:
                    continue
                session_candles = by_session_date[d]
                prev_close = by_session_date[prev_d][-1].close
                session_open = session_candles[0].open
                session_close = session_candles[-1].close
                dates_seen.add(d)
                date_key = d.isoformat()

                for family in EVENT_FAMILIES:
                    crosses = corporate_action_crosses_boundary(
                        event_family=family, session_date=d, action_ex_dates=ex_dates,
                    )
                    symbol_day = assess_symbol_day_readiness(
                        study_start=study_start, study_end=study_end,
                        corporate_actions=coverage,
                        corporate_action_in_reference_window=crosses,
                        candles_fully_adjusted=False,
                        point_in_time_membership_available=membership_ok,
                    )
                    readiness = assess_checkpoint_readiness(
                        symbol_day, canonical_intraday_grid=True, complete_intraday_session=True,
                    )
                    if not readiness.allowed:
                        for threshold in EVENT_THRESHOLDS_PERCENT:
                            scope = f"{family.value}:{threshold}:SYMBOLDAY"
                            by_date[date_key][f"{scope}:EXCLUDED"] += 1
                            for cp_str, _ in checkpoint_instants:
                                by_date[date_key][f"{family.value}:{threshold}:{cp_str}:EXCLUDED"] += 1
                        continue

                    reference = prev_close if family is not EventFamily.OPEN_TO_HIGH else session_open

                    for threshold in EVENT_THRESHOLDS_PERCENT:
                        if family is EventFamily.CLOSE:
                            price = threshold_price(reference, threshold)
                            outcome = (
                                ForwardLabelOutcome.POSITIVE if session_close >= price
                                else ForwardLabelOutcome.NEGATIVE
                            )
                            by_date[date_key][f"CLOSE:{threshold}:SYMBOLDAY:{outcome.value}"] += 1
                            for cp_str, _ in checkpoint_instants:
                                by_date[date_key][f"CLOSE:{threshold}:{cp_str}:{outcome.value}"] += 1
                        else:
                            touch_time = first_touch_time(reference, threshold, session_candles)
                            symbolday_outcome = (
                                ForwardLabelOutcome.POSITIVE if touch_time is not None
                                else ForwardLabelOutcome.NEGATIVE
                            )
                            by_date[date_key][
                                f"{family.value}:{threshold}:SYMBOLDAY:{symbolday_outcome.value}"
                            ] += 1
                            for cp_str, cp_t in checkpoint_instants:
                                cp_instant = datetime.combine(d, cp_t, tzinfo=IST)
                                cp_outcome = outcome_from_touch_time(touch_time, cp_instant)
                                by_date[date_key][
                                    f"{family.value}:{threshold}:{cp_str}:{cp_outcome.value}"
                                ] += 1

    report = {
        "study_start": study_start.isoformat(),
        "study_end": study_end.isoformat(),
        "cohort_size": len(cohort.instrument_ids),
        "trading_dates_with_eligible_evidence": len(dates_seen),
        "candidate_checkpoints_ist": list(CANDIDATE_CHECKPOINTS_IST),
        "per_date_counters": {d: dict(c) for d, c in sorted(by_date.items())},
    }
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(report, indent=2, sort_keys=False), encoding="utf-8")
    print(f"wrote {args.out} -- {len(dates_seen)} trading dates, {sum(len(c) for c in by_date.values())} counter cells")


if __name__ == "__main__":
    main()
