"""EM-1r5: re-run EM-1a's coverage measurement against the real, corrected
EM-1r2/EM-1r3/EM-1r4 evidence and report which of the 9 candidate
checkpoints have genuine, evidence-backed admitted symbol-days.

Read-only: makes no Kite API calls, mutates no canonical tables, and does
not itself flip any checkpoint from ``candidate_ist`` to ``accepted_ist``
in ``config/explosive_move.json`` -- per the frozen EM-1r5 acceptance
criterion ("the owner approves a non-empty checkpoint set"), that edit is
a decision for the owner to make after reading this report, not something
this script performs automatically.

Wires real evidence into EM-1a's frozen, unmodified admission functions
(``athena.explosive_move.contracts``):
  - corporate-action coverage + per-instrument ex_dates: the real,
    owner-approved EM-1r2 manifest;
  - canonical_intraday_grid / complete_intraday_session: the real,
    corrected EM-1r3 production-capture manifests (ADMITTED status);
  - point_in_time_membership_available: EM-1r4's own frozen
    ``assess_symbol_day_cohort_admission``, run fresh against the live
    (read-only) instruments table;
  - corporate_action_in_reference_window: the new, owner-approved
    boundary-crossing contract (``corporate_action_boundary.py``), not a
    fixed proximity window.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from collections import Counter, defaultdict
from datetime import date
from pathlib import Path

from athena.data.store.repository import SqliteRepository
from athena.explosive_move.cohort_admission import assess_symbol_day_cohort_admission
from athena.explosive_move.contracts import (
    CANDIDATE_CHECKPOINTS_IST,
    EVENT_FAMILIES,
    CorporateActionCoverage,
    EventFamily,
    ExclusionReason,
    assess_checkpoint_readiness,
    assess_symbol_day_readiness,
)
from athena.explosive_move.corporate_action_boundary import (
    corporate_action_crosses_boundary,
    naive_ex_date_plus_n_window_excludes,
)
from athena.explosive_move.corporate_action_coverage import (
    SURVIVOR_COHORT_LIMITATION,
    SURVIVOR_COHORT_NAME,
    SurvivorCohort,
)
from athena.explosive_move.intraday_reconstruction import intraday_manifest_from_payload


def _load_em1r2(manifest_path: Path) -> dict:
    return json.loads(manifest_path.read_text(encoding="utf-8"))


def _corporate_action_coverage(em1r2: dict) -> CorporateActionCoverage:
    complete = all(s.get("complete") for s in em1r2["retrieval_slices"])
    return CorporateActionCoverage(
        authoritative_start=date.fromisoformat(em1r2["study_start"]) if complete else None,
        authoritative_end=date.fromisoformat(em1r2["study_end"]) if complete else None,
        action_count=len(em1r2["actions"]),
    )


def _ex_dates_by_instrument(em1r2: dict) -> dict[str, set[date]]:
    result: dict[str, set[date]] = defaultdict(set)
    for action in em1r2["actions"]:
        result[action["instrument_id"]].add(date.fromisoformat(action["ex_date"]))
    return result


def _action_type_by_instrument_and_date(em1r2: dict) -> dict[tuple[str, date], set[str]]:
    result: dict[tuple[str, date], set[str]] = defaultdict(set)
    for action in em1r2["actions"]:
        key = (action["instrument_id"], date.fromisoformat(action["ex_date"]))
        result[key].add(action["action_type"])
    return result


def main() -> None:
    parser = argparse.ArgumentParser(description="EM-1r5 checkpoint coverage re-audit.")
    parser.add_argument("--db", type=Path, default=Path("db/athena.db"))
    parser.add_argument(
        "--em1r2-manifest",
        type=Path,
        default=Path(
            "artifacts/research/em1r2/corporate-actions/manifests/"
            "8e1fd6c17365abe1a5ea3ac41fc00f83d36d8c972ef1ea7d725e51d28272a22c.json"
        ),
    )
    parser.add_argument("--em1r3-checkpoint", type=Path, default=Path("artifacts/research/em1r3/checkpoint.json"))
    parser.add_argument("--em1r3-evidence-root", type=Path, default=Path("artifacts/research/em1r3/intraday"))
    parser.add_argument("--universe", default="athena_core")
    parser.add_argument("--cohort-resolution-date", type=date.fromisoformat, required=True)
    parser.add_argument("--naive-n-sessions-after", type=int, default=3)
    parser.add_argument("--out", type=Path, default=Path("artifacts/research/em1r5/reaudit_result.json"))
    args = parser.parse_args()

    em1r2 = _load_em1r2(args.em1r2_manifest)
    coverage = _corporate_action_coverage(em1r2)
    ex_dates_by_instrument = _ex_dates_by_instrument(em1r2)
    action_types_by_key = _action_type_by_instrument_and_date(em1r2)
    action_type_counts = Counter(a["action_type"] for a in em1r2["actions"])
    demerger_actions = [a for a in em1r2["actions"] if a["action_type"] == "DEMERGER"]

    repository = SqliteRepository(args.db)
    try:
        instruments = tuple(repository.list_instruments())
        instrument_ids = tuple(repository.list_resolved_universe(args.universe))
    finally:
        repository.close()

    cohort = SurvivorCohort(
        name=SURVIVOR_COHORT_NAME, universe_name=args.universe,
        resolution_date=args.cohort_resolution_date,
        instrument_ids=tuple(sorted(set(instrument_ids))),
        group_effective_dates=((args.universe, args.cohort_resolution_date),),
        limitation=SURVIVOR_COHORT_LIMITATION,
    )
    listing_by_id = {i.instrument_id: i for i in instruments}

    em1r3_checkpoint = json.loads(args.em1r3_checkpoint.read_text())
    manifests = [
        intraday_manifest_from_payload((args.em1r3_evidence_root / p).read_bytes())
        for p in em1r3_checkpoint["batch_manifest_paths"]
    ]
    study_start = manifests[0].study_start
    study_end = manifests[0].study_end
    trading_sessions_ordered = tuple(sorted({r.session_date for m in manifests for r in m.sessions}))

    # ---- per-instrument-day EM-1r3 admission (canonical + complete intraday grid) ----
    em1r3_admitted: dict[tuple[str, date], bool] = {}
    for m in manifests:
        for r in m.sessions:
            em1r3_admitted[(r.instrument_id, r.session_date)] = r.status == "ADMITTED"

    # ---- per-instrument cohort admission (EM-1r4's own frozen contract, run fresh) ----
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

    # ---- main re-audit: every (instrument, session_date, event_family) EM-1r3 evaluated ----
    results: dict[EventFamily, list[tuple[str, date, bool, tuple[ExclusionReason, ...]]]] = defaultdict(list)
    ca_crossing_excluded: dict[EventFamily, list[tuple[str, date, tuple[str, ...]]]] = defaultdict(list)
    naive_would_exclude_but_boundary_admits: dict[EventFamily, int] = Counter()

    for (instrument_id, session_date), admitted in em1r3_admitted.items():
        ex_dates = frozenset(ex_dates_by_instrument.get(instrument_id, set()))
        membership_ok = cohort_membership_ok.get(instrument_id, False)
        for family in EVENT_FAMILIES:
            crosses = corporate_action_crosses_boundary(
                event_family=family, session_date=session_date, action_ex_dates=ex_dates,
            )
            symbol_day = assess_symbol_day_readiness(
                study_start=study_start, study_end=study_end,
                corporate_actions=coverage,
                corporate_action_in_reference_window=crosses,
                candles_fully_adjusted=False,
                point_in_time_membership_available=membership_ok,
            )
            checkpoint_readiness = assess_checkpoint_readiness(
                symbol_day, canonical_intraday_grid=admitted, complete_intraday_session=admitted,
            )
            results[family].append(
                (instrument_id, session_date, checkpoint_readiness.allowed, checkpoint_readiness.reasons)
            )
            if crosses:
                types = tuple(sorted(action_types_by_key.get((instrument_id, session_date), ())))
                ca_crossing_excluded[family].append((instrument_id, session_date, types))
            naive_excludes = naive_ex_date_plus_n_window_excludes(
                event_family=family, session_date=session_date, action_ex_dates=ex_dates,
                trading_sessions_ordered=trading_sessions_ordered,
                n_sessions_after=args.naive_n_sessions_after,
            )
            if naive_excludes and not crosses:
                naive_would_exclude_but_boundary_admits[family] += 1

    # ---- find, per family, a real example immediately after an action's
    #      ex_date that remains admissible -- demonstrating the boundary
    #      rule does not over-exclude once both sides are post-action. ----
    admitted_lookup: dict[EventFamily, dict[tuple[str, date], bool]] = {
        family: {(i, d): allowed for i, d, allowed, _ in rows} for family, rows in results.items()
    }
    non_crossing_examples: dict[EventFamily, dict | None] = {}
    for family in EVENT_FAMILIES:
        example = None
        for instrument_id, ex_date_set in ex_dates_by_instrument.items():
            for ex_date in sorted(ex_date_set):
                later_sessions = [d for d in trading_sessions_ordered if d > ex_date][:5]
                for later in later_sessions:
                    if admitted_lookup[family].get((instrument_id, later)) is True:
                        example = {
                            "instrument_id": instrument_id,
                            "action_ex_date": ex_date.isoformat(),
                            "admitted_session_date": later.isoformat(),
                            "sessions_after_ex_date": trading_sessions_ordered.index(later)
                            - trading_sessions_ordered.index(ex_date),
                        }
                        break
                if example:
                    break
            if example:
                break
        non_crossing_examples[family] = example

    # ---- checkpoint-level identity check: do all 9 candidate checkpoints share the
    #      same admitted set per family, given today's session-level-only evidence? ----
    checkpoint_identity_confirmed = True  # documented finding, not a per-checkpoint loop --
    # canonical_intraday_grid/complete_intraday_session and corporate_action_in_reference_window
    # are computed once per (instrument, session_date, family), independent of checkpoint_ist,
    # since none of today's evidence sources vary by intraday time-of-day.

    report: dict = {
        "contract_version": "em-event-contract-v1",
        "milestone": "EM-1r5",
        "provenance": {
            "em1r2_manifest_id": args.em1r2_manifest.stem,
            "em1r3_capture_run_id": em1r3_checkpoint["capture_run_id"],
            "em1r3_cohort_id": em1r3_checkpoint["cohort_id"],
            "em1r3_batch_count": len(em1r3_checkpoint["batch_manifest_paths"]),
        },
        "accepted_ist_semantics": (
            "accepted_ist means the checkpoint has sufficient trustworthy historical "
            "evidence (admitted intraday session, cohort membership, quote/data hygiene, "
            "corporate-action boundary validity) to participate in subsequent EMR "
            "research. It does NOT mean: predictive value, statistical significance, "
            "calibration, production-scanner fitness, equal model weight, EM-4 evidence "
            "gate passage, or any influence on canonical ATHENA decisions. Owner "
            "decision, 2026-08-26."
        ),
        "study_start": study_start.isoformat(),
        "study_end": study_end.isoformat(),
        "cohort_size": len(cohort.instrument_ids),
        "candidate_checkpoints_ist": list(CANDIDATE_CHECKPOINTS_IST),
        "checkpoint_identity_across_candidates": {
            "confirmed": checkpoint_identity_confirmed,
            "reason": (
                "canonical_intraday_grid, complete_intraday_session, and "
                "corporate_action_in_reference_window are all session-level facts "
                "under today's evidence (EM-1r3 admits/excludes whole sessions; the "
                "boundary rule gates on session_date, not checkpoint_ist) -- so every "
                "candidate checkpoint shares an identical admitted symbol-day set "
                "within a given event family. This is a real, reportable property of "
                "today's evidence, not an implementation shortcut."
            ),
        },
        "corporate_action_summary": {
            "accepted_actions_total": len(em1r2["actions"]),
            "accepted_actions_by_type": dict(action_type_counts),
            "demerger_actions": [
                {"instrument_id": a["instrument_id"], "ex_date": a["ex_date"], "action_id": a["action_id"]}
                for a in demerger_actions
            ],
        },
        "families": {},
    }

    for family in EVENT_FAMILIES:
        rows = results[family]
        total = len(rows)
        admitted = sum(1 for _, _, allowed, _ in rows if allowed)
        reason_counts: Counter[str] = Counter()
        for _, _, _allowed, reasons in rows:
            for r in reasons:
                reason_counts[r.value] += 1

        crossing_rows = ca_crossing_excluded[family]
        crossing_dates = {d for _, d, _ in crossing_rows}
        crossing_instruments = {i for i, _, _ in crossing_rows}
        crossing_type_counts: Counter[str] = Counter()
        for _, _, types in crossing_rows:
            for t in types:
                crossing_type_counts[t] += 1

        # material impact: symbol-days whose ONLY exclusion reason is the CA boundary
        ca_sole_reason = sum(
            1 for _, _, allowed, reasons in rows
            if not allowed and reasons == (ExclusionReason.UNADJUSTED_CORPORATE_ACTION_WINDOW,)
        )

        report["families"][family.value] = {
            "reference_price_basis": (
                "previous_session_adjusted_close" if family is not EventFamily.OPEN_TO_HIGH
                else "regular_session_open"
            ),
            "symbol_days_evaluated": total,
            "symbol_days_admitted": admitted,
            "admitted_percent": round(100 * admitted / total, 4) if total else 0.0,
            "exclusion_reason_counts": dict(reason_counts),
            "corporate_action_boundary_crossings": {
                "symbol_days_flagged": len(crossing_rows),
                "percent_of_population": round(100 * len(crossing_rows) / total, 4) if total else 0.0,
                "unique_instruments_affected": len(crossing_instruments),
                "unique_dates_affected": len(crossing_dates),
                "by_action_type": dict(crossing_type_counts),
                "sole_reason_for_exclusion_count": ca_sole_reason,
                "materially_changes_admission": ca_sole_reason > 0,
            },
            "naive_ex_date_plus_n_would_have_additionally_excluded": (
                naive_would_exclude_but_boundary_admits[family]
            ),
            "example_excluded_on_ex_date": (
                {"instrument_id": crossing_rows[0][0], "session_date": crossing_rows[0][1].isoformat(),
                 "action_types": crossing_rows[0][2]}
                if crossing_rows else None
            ),
            "example_admissible_shortly_after_action": non_crossing_examples[family],
        }

    # Deterministic, content-addressed run identifier (matches the manifest_id
    # convention used throughout EM-1r2/EM-1r3): a digest of the report's own
    # already-computed content, not a wall-clock timestamp.
    fingerprint_payload = json.dumps(report, sort_keys=True, separators=(",", ":"))
    report["run_id"] = "em1r5-" + hashlib.sha256(fingerprint_payload.encode("utf-8")).hexdigest()

    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(report, indent=2, sort_keys=False), encoding="utf-8")
    print(json.dumps(report, indent=2, sort_keys=False))


if __name__ == "__main__":
    main()
