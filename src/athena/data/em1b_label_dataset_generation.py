"""EM-1b: generate the deterministic, replayable production label dataset
and assign the Owner/Chief-Architect-approved (2026-08-26) chronological
partitions (TRAIN/VALIDATION/CALIBRATION/FINAL_TEST -- frozen in
``athena.explosive_move.partitions``).

Read-only against upstream evidence, write-only against
``artifacts/research/em1b/`` (git-ignored). No Kite calls, no canonical
ATHENA table writes. Reuses, unmodified: EM-1a's frozen readiness
contract, EM-1r4's cohort-admission contract, the EM-1r5 corporate-action
boundary rule, and the EM-1b forward-label contract.

Output shape, one pass over the real corrected EM-1r3 candle evidence:
  artifacts/research/em1b/labels/{PARTITION}_symbol_day.jsonl.gz
    -- one row per (instrument, session_date, event_family,
       threshold_percent), fields = config/explosive_move.json's frozen
       ``symbol_day_fields``.
  artifacts/research/em1b/labels/{PARTITION}_checkpoint.jsonl.gz
    -- one row per (instrument, session_date, checkpoint_ist,
       event_family, threshold_percent), fields = the frozen
       ``checkpoint_fields``.
  artifacts/research/em1b/manifests/{manifest_id}.json
    -- one per partition, fields = the frozen ``manifest_fields``;
       manifest_id is a content-hash of the manifest's own already-
       computed fields (created_at excepted -- see below), matching the
       deterministic-provenance convention used throughout EM-1r2/3/5.
  artifacts/research/em1b/dataset_index.json
    -- convenience index: the 4 manifest_ids plus a compact summary.

``created_at``: the frozen ``manifest_fields`` schema (declared in
config/explosive_move.json before this milestone) names a created_at
field, but ATHENA's own architecture bans wall-clock reads inside
analytical/generation code (no ``datetime.now()`` -- determinism and
replayability). Both constraints are honoured by setting created_at to
the real, already-fixed ``finished_at`` timestamp recorded in the EM-1r3
capture checkpoint that this dataset is built from -- a genuine
historical fact about the upstream evidence, not a runtime clock read,
and therefore itself part of the deterministic input.

All decimal prices are serialized as strings (``str(Decimal(...))``),
never floats, to preserve exact precision -- consistent with ATHENA's
Decimal-money convention everywhere else in the codebase.
"""

from __future__ import annotations

import argparse
import gzip
import hashlib
import io
import json
from collections import Counter, defaultdict
from contextlib import ExitStack
from datetime import date, datetime, time, timedelta
from decimal import Decimal
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
    evaluate_close_label,
    evaluate_touch_label,
    first_touch_time,
    outcome_from_touch_time,
    price_at_checkpoint,
    session_high_so_far,
)
from athena.explosive_move.intraday_reconstruction import (
    candles_from_payload,
    intraday_manifest_from_payload,
)
from athena.explosive_move.partitions import (
    PARTITION_BOUNDARIES,
    PARTITION_CONTRACT_VERSION,
    PartitionRole,
    partition_for_session_date,
)

IST = ZoneInfo("Asia/Kolkata")
LABEL_CONTRACT_VERSION = "em1b-label-v1"
CANDLE_INTERVAL_MINUTES = 5


def _decimal_str(value: Decimal | None) -> str | None:
    return str(value) if value is not None else None


def _manifest_row_counts(
    family_session_pairs: int, *, threshold_count: int, checkpoint_count: int
) -> dict[str, int]:
    """Scale a raw (family, session) pair count -- counted exactly ONCE per
    pair during generation, never per threshold/checkpoint -- up to the
    actual symbol_day and checkpoint row counts persisted for that count.
    A single named place for this arithmetic, so the two real row-count
    multipliers (thresholds; thresholds*checkpoints) can't silently drift
    apart or get applied twice to an already-scaled counter."""

    return {
        "symbol_day": family_session_pairs * threshold_count,
        "checkpoint": family_session_pairs * threshold_count * checkpoint_count,
    }


def _deterministic_gzip_writer(path: Path) -> io.TextIOWrapper:
    """A text-mode gzip writer whose compressed bytes are a pure function
    of content -- ``gzip.open`` embeds the current wall-clock time in the
    gzip header by default (mtime=None), so two runs over byte-identical
    JSONL content produce DIFFERENT compressed files and therefore
    different sha256/manifest_id, breaking replayability. mtime=0 pins the
    header field instead of reading the clock."""

    return io.TextIOWrapper(
        gzip.GzipFile(filename=path.name, mode="wb", fileobj=path.open("wb"), mtime=0),
        encoding="utf-8",
    )


def main() -> None:
    parser = argparse.ArgumentParser(description="EM-1b production label dataset generation.")
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
    parser.add_argument("--out-dir", type=Path, default=Path("artifacts/research/em1b"))
    parser.add_argument(
        "--only-instruments", type=str, default=None,
        help="comma-separated instrument_ids -- restricts the run for canary/testing only",
    )
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

    artifact_by_instrument: dict[str, str] = {}
    for m in manifests:
        for artifact in m.normalized_artifacts:
            artifact_by_instrument[artifact.instrument_id] = artifact.artifact

    only = set(args.only_instruments.split(",")) if args.only_instruments else None
    ordered_instruments = sorted(artifact_by_instrument)
    if only is not None:
        ordered_instruments = [i for i in ordered_instruments if i in only]

    checkpoint_instants = tuple((cp, time.fromisoformat(cp)) for cp in CANDIDATE_CHECKPOINTS_IST)

    args.out_dir.mkdir(parents=True, exist_ok=True)
    labels_dir = args.out_dir / "labels"
    manifests_dir = args.out_dir / "manifests"
    labels_dir.mkdir(exist_ok=True)
    manifests_dir.mkdir(exist_ok=True)

    included_by_role: Counter[tuple[PartitionRole, str]] = Counter()
    excluded_by_role: Counter[tuple[PartitionRole, str]] = Counter()
    exclusion_counts_by_role: dict[PartitionRole, Counter[str]] = defaultdict(Counter)
    dates_by_role: dict[PartitionRole, set[date]] = defaultdict(set)

    with ExitStack() as stack:
        symbol_day_files = {
            role: stack.enter_context(
                _deterministic_gzip_writer(labels_dir / f"{role.value}_symbol_day.jsonl.gz")
            )
            for role in PartitionRole
        }
        checkpoint_files = {
            role: stack.enter_context(
                _deterministic_gzip_writer(labels_dir / f"{role.value}_checkpoint.jsonl.gz")
            )
            for role in PartitionRole
        }

        for instrument_id in ordered_instruments:
            listing = listing_by_id.get(instrument_id)
            exchange = listing.exchange if listing else ""
            symbol = listing.symbol if listing else ""

            admitted_dates = admitted_dates_by_instrument.get(instrument_id, [])
            if len(admitted_dates) < 2:
                continue
            candles = candles_from_payload(
                (args.em1r3_evidence_root / artifact_by_instrument[instrument_id]).read_bytes()
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
                session_candles = tuple(by_session_date[d])
                prev_close = by_session_date[prev_d][-1].close
                session_open = session_candles[0].open
                session_high = max(c.high for c in session_candles)
                session_close = session_candles[-1].close
                session_close_instant = session_candles[-1].ts_open + timedelta(
                    minutes=CANDLE_INTERVAL_MINUTES
                )

                role = partition_for_session_date(d)
                dates_by_role[role].add(d)
                session_date_str = d.isoformat()

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
                    reference = prev_close if family is not EventFamily.OPEN_TO_HIGH else session_open
                    exclusion_reasons = [r.value for r in readiness.reasons]

                    # counted once per (family, session) -- NOT per threshold; the
                    # manifest scales these up by EVENT_THRESHOLDS_PERCENT/checkpoint
                    # counts to get actual row counts, so double-scaling here would
                    # silently 6x/54x-inflate the reported totals.
                    row_key = (role, family.value)
                    if readiness.allowed:
                        included_by_role[row_key] += 1
                    else:
                        excluded_by_role[row_key] += 1
                        for reason in exclusion_reasons:
                            exclusion_counts_by_role[role][reason] += 1

                    for threshold in EVENT_THRESHOLDS_PERCENT:
                        if not readiness.allowed:
                            symbol_day_label = None
                        else:
                            if family is EventFamily.CLOSE:
                                symbol_day_label = evaluate_close_label(
                                    reference_price=reference, threshold_percent=threshold,
                                    session_close=session_close,
                                ).outcome.value
                            else:
                                symbol_day_label = evaluate_touch_label(
                                    reference_price=reference, threshold_percent=threshold,
                                    checkpoint_instant=session_candles[0].ts_open,
                                    session_candles=session_candles,
                                ).outcome.value

                        symbol_day_files[role].write(json.dumps({
                            "instrument_id": instrument_id, "exchange": exchange, "symbol": symbol,
                            "session_date": session_date_str,
                            "membership_as_of": study_end.isoformat(),
                            "reference_close": _decimal_str(reference),
                            "session_open": _decimal_str(session_open),
                            "session_high": _decimal_str(session_high),
                            "session_close": _decimal_str(session_close),
                            "event_family": family.value, "threshold_percent": threshold,
                            "label": symbol_day_label, "exclusion_reasons": exclusion_reasons,
                        }, separators=(",", ":")) + "\n")

                        touch_time = (
                            None if family is EventFamily.CLOSE or not readiness.allowed
                            else first_touch_time(reference, threshold, session_candles)
                        )
                        for cp_str, cp_t in checkpoint_instants:
                            cp_instant = datetime.combine(d, cp_t, tzinfo=IST)
                            remaining_minutes = (
                                session_close_instant - cp_instant
                            ).total_seconds() / 60
                            price_cp = price_at_checkpoint(cp_instant, session_candles)
                            high_so_far = session_high_so_far(cp_instant, session_candles)

                            if not readiness.allowed:
                                cp_label = None
                            elif family is EventFamily.CLOSE:
                                cp_label = symbol_day_label
                            else:
                                cp_label = outcome_from_touch_time(touch_time, cp_instant).value

                            checkpoint_files[role].write(json.dumps({
                                "instrument_id": instrument_id, "session_date": session_date_str,
                                "checkpoint_ist": cp_str,
                                "remaining_session_minutes": remaining_minutes,
                                "price_at_checkpoint": _decimal_str(price_cp),
                                "session_high_so_far": _decimal_str(high_so_far),
                                "event_family": family.value, "threshold_percent": threshold,
                                "label": cp_label, "exclusion_reasons": exclusion_reasons,
                            }, separators=(",", ":")) + "\n")

    manifest_ids: dict[str, str] = {}
    for role in PartitionRole:
        sd_path = labels_dir / f"{role.value}_symbol_day.jsonl.gz"
        cp_path = labels_dir / f"{role.value}_checkpoint.jsonl.gz"
        sd_sha256 = hashlib.sha256(sd_path.read_bytes()).hexdigest()
        cp_sha256 = hashlib.sha256(cp_path.read_bytes()).hexdigest()

        boundary = next(b for b in PARTITION_BOUNDARIES if b.role is role)
        manifest = {
            "contract_version": LABEL_CONTRACT_VERSION,
            "partition_contract_version": PARTITION_CONTRACT_VERSION,
            "created_at": em1r3_checkpoint["finished_at"],
            "study_start": study_start.isoformat(),
            "study_end": study_end.isoformat(),
            "universe_name": args.universe,
            "membership_snapshot_ids": [em1r3_checkpoint["cohort_id"]],
            "source_provenance": {
                "em1r2_manifest_id": args.em1r2_manifest.stem,
                "em1r3_capture_run_id": em1r3_checkpoint["capture_run_id"],
                "em1r3_cohort_id": em1r3_checkpoint["cohort_id"],
                "em1r3_batch_count": len(em1r3_checkpoint["batch_manifest_paths"]),
            },
            "corporate_action_coverage": {
                "authoritative_start": coverage.authoritative_start.isoformat()
                if coverage.authoritative_start else None,
                "authoritative_end": coverage.authoritative_end.isoformat()
                if coverage.authoritative_end else None,
                "action_count": coverage.action_count,
            },
            "accepted_checkpoints": list(CANDIDATE_CHECKPOINTS_IST),
            "partition_role": role.value,
            "partition_boundary": {
                "start_date": boundary.start_date.isoformat(),
                "end_date": boundary.end_date.isoformat(),
            },
            "trading_sessions_in_partition": len(dates_by_role.get(role, ())),
            "included_row_count": _manifest_row_counts(
                sum(v for (r, _fam), v in included_by_role.items() if r is role),
                threshold_count=len(EVENT_THRESHOLDS_PERCENT),
                checkpoint_count=len(CANDIDATE_CHECKPOINTS_IST),
            ),
            "excluded_row_count": _manifest_row_counts(
                sum(v for (r, _fam), v in excluded_by_role.items() if r is role),
                threshold_count=len(EVENT_THRESHOLDS_PERCENT),
                checkpoint_count=len(CANDIDATE_CHECKPOINTS_IST),
            ),
            "exclusion_counts": dict(exclusion_counts_by_role.get(role, {})),
            "payload_files": {
                "symbol_day": {"path": sd_path.name, "sha256": sd_sha256},
                "checkpoint": {"path": cp_path.name, "sha256": cp_sha256},
            },
        }
        fingerprint_payload = json.dumps(
            {k: v for k, v in manifest.items() if k != "created_at"},
            sort_keys=True, separators=(",", ":"),
        )
        manifest_id = "em1b-" + hashlib.sha256(fingerprint_payload.encode("utf-8")).hexdigest()
        manifest["manifest_id"] = manifest_id
        manifest_ids[role.value] = manifest_id

        (manifests_dir / f"{manifest_id}.json").write_text(
            json.dumps(manifest, indent=2, sort_keys=False), encoding="utf-8"
        )
        print(
            f"{role.value}: sessions={manifest['trading_sessions_in_partition']} "
            f"symbol_day included={manifest['included_row_count']['symbol_day']} "
            f"excluded={manifest['excluded_row_count']['symbol_day']} "
            f"checkpoint included={manifest['included_row_count']['checkpoint']} "
            f"excluded={manifest['excluded_row_count']['checkpoint']}"
        )

    index = {
        "label_contract_version": LABEL_CONTRACT_VERSION,
        "partition_contract_version": PARTITION_CONTRACT_VERSION,
        "manifest_ids": manifest_ids,
    }
    (args.out_dir / "dataset_index.json").write_text(
        json.dumps(index, indent=2, sort_keys=False), encoding="utf-8"
    )
    print("wrote", args.out_dir / "dataset_index.json")


if __name__ == "__main__":
    main()
