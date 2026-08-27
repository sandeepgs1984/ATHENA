"""EM-2: generate the versioned, checkpoint-level evidence dataset --
SessionInvariantEvidence + CheckpointDynamicEvidence -> EvidenceSnapshot
-- for the TRAIN partition only, per the owner's explicit scope
restriction (feature usefulness is never evaluated against VALIDATION/
CALIBRATION/FINAL_TEST during EM-2; that is EM-3's job).

Read-only against EM-1r3's already-audited intraday evidence and EM-1c's
own regime evidence; write-only against `artifacts/research/em2/`
(git-ignored). Daily bars are derived from EM-1r3's M5 candles directly
(see the EM-2 Evidence Contract's warm-up discussion) -- never read from
the separate, unaudited canonical D1 table.
"""

from __future__ import annotations

import argparse
import gzip
import hashlib
import io
import json
from collections import defaultdict, deque
from datetime import date, datetime, time
from decimal import Decimal
from pathlib import Path
from zoneinfo import ZoneInfo

from athena.explosive_move.checkpoint_dynamic_evidence import compute_checkpoint_dynamic_evidence
from athena.explosive_move.contracts import CANDIDATE_CHECKPOINTS_IST
from athena.explosive_move.evidence_contract import EVIDENCE_CONTRACT_VERSION
from athena.explosive_move.evidence_values import DailyBar, daily_bar_from_session_candles
from athena.explosive_move.intraday_reconstruction import (
    candles_from_payload,
    intraday_manifest_from_payload,
)
from athena.explosive_move.partitions import PartitionRole, partition_for_session_date
from athena.explosive_move.session_invariant_evidence import compute_session_invariant_evidence

IST = ZoneInfo("Asia/Kolkata")

#: Trailing prior-session window for REL_VOLUME_C and the 20D high/low
#: baselines -- frozen at 20, matching the evidence contract.
BASELINE_WINDOW = 20


def _deterministic_gzip_writer(path: Path) -> io.TextIOWrapper:
    return io.TextIOWrapper(
        gzip.GzipFile(filename=path.name, mode="wb", fileobj=path.open("wb"), mtime=0),
        encoding="utf-8",
    )


def _ev_to_dict(ev) -> dict:
    if ev.is_known:
        v = ev.value
        return {"value": str(v) if isinstance(v, Decimal) else v, "unknown_reason": None}
    return {"value": None, "unknown_reason": ev.unknown_reason}


def main() -> None:
    parser = argparse.ArgumentParser(description="EM-2 evidence dataset generation (TRAIN only).")
    parser.add_argument("--em1r3-checkpoint", type=Path, default=Path("artifacts/research/em1r3/checkpoint.json"))
    parser.add_argument("--em1r3-evidence-root", type=Path, default=Path("artifacts/research/em1r3/intraday"))
    parser.add_argument(
        "--regime-evidence", type=Path,
        default=Path("artifacts/research/em1c-regime/regime_by_session.json"),
    )
    parser.add_argument("--out-dir", type=Path, default=Path("artifacts/research/em2"))
    parser.add_argument("--only-instruments", type=str, default=None)
    args = parser.parse_args()

    regime_payload = json.loads(args.regime_evidence.read_text(encoding="utf-8"))
    regime_by_date = {row["session_date"]: row for row in regime_payload["sessions"]}

    em1r3_checkpoint = json.loads(args.em1r3_checkpoint.read_text(encoding="utf-8"))
    manifests = [
        intraday_manifest_from_payload((args.em1r3_evidence_root / p).read_bytes())
        for p in em1r3_checkpoint["batch_manifest_paths"]
    ]

    admitted_dates_by_instrument: dict[str, list[date]] = defaultdict(list)
    for m in manifests:
        for r in m.sessions:
            if r.status == "ADMITTED":
                admitted_dates_by_instrument[r.instrument_id].append(r.session_date)
    for iid in admitted_dates_by_instrument:
        admitted_dates_by_instrument[iid].sort()

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
    invariant_path = args.out_dir / "TRAIN_session_invariant.jsonl.gz"
    dynamic_path = args.out_dir / "TRAIN_checkpoint_dynamic.jsonl.gz"

    invariant_rows = 0
    dynamic_rows = 0
    train_sessions_seen: set[date] = set()

    with _deterministic_gzip_writer(invariant_path) as inv_f, _deterministic_gzip_writer(dynamic_path) as dyn_f:
        for instrument_id in ordered_instruments:
            admitted_dates = admitted_dates_by_instrument.get(instrument_id, [])
            if not admitted_dates:
                continue
            candles = candles_from_payload(
                (args.em1r3_evidence_root / artifact_by_instrument[instrument_id]).read_bytes()
            )
            by_session_date: dict[date, list] = defaultdict(list)
            for c in candles:
                by_session_date[c.ts_open.date()].append(c)
            for d in by_session_date:
                by_session_date[d].sort(key=lambda c: c.ts_open)

            # Derive one DailyBar per admitted session, in chronological
            # order -- the full history available (not just TRAIN), so
            # early TRAIN sessions get whatever real prior warm-up exists.
            daily_bars: list[DailyBar] = []
            for d in admitted_dates:
                if d not in by_session_date:
                    continue
                daily_bars.append(daily_bar_from_session_candles(d, tuple(by_session_date[d])))
            daily_bars_tuple = tuple(daily_bars)
            bars_by_date = {b.session_date: b for b in daily_bars_tuple}
            index_by_date = {b.session_date: i for i, b in enumerate(daily_bars_tuple)}

            # rolling per-checkpoint cumulative-volume-through-C history,
            # advanced session by session in chronological order.
            checkpoint_volume_history: dict[str, deque] = {
                cp: deque(maxlen=BASELINE_WINDOW) for cp, _ in checkpoint_instants
            }

            for d in admitted_dates:
                try:
                    role = partition_for_session_date(d)
                except ValueError:
                    role = None
                if d not in by_session_date:
                    continue
                session_candles = tuple(by_session_date[d])
                bar = bars_by_date.get(d)
                if bar is None:
                    continue

                if role is PartitionRole.TRAIN:
                    train_sessions_seen.add(d)
                    idx = index_by_date[d]
                    prior_bars = daily_bars_tuple[:idx]
                    prev_close = daily_bars_tuple[idx - 1].close if idx > 0 else None

                    regime_row = regime_by_date.get(d.isoformat())
                    invariant = compute_session_invariant_evidence(
                        session_date=d, daily_bars=prior_bars, session_open=bar.open, regime=regime_row,
                    )
                    inv_f.write(json.dumps({
                        "instrument_id": instrument_id, "session_date": d.isoformat(),
                        "contract_version": EVIDENCE_CONTRACT_VERSION,
                        **{name: _ev_to_dict(getattr(invariant, name)) for name in invariant.__dataclass_fields__},
                    }, separators=(",", ":")) + "\n")
                    invariant_rows += 1

                    for cp_str, cp_t in checkpoint_instants:
                        cp_instant = datetime.combine(d, cp_t, tzinfo=IST)
                        hist_vol = tuple(checkpoint_volume_history[cp_str])
                        dynamic = compute_checkpoint_dynamic_evidence(
                            checkpoint_instant=cp_instant, session_candles=session_candles,
                            session_open=bar.open, prior_daily_bars=prior_bars, prev_close=prev_close,
                            historical_checkpoint_volumes=hist_vol,
                        )
                        dyn_f.write(json.dumps({
                            "instrument_id": instrument_id, "session_date": d.isoformat(),
                            "checkpoint_ist": cp_str, "contract_version": EVIDENCE_CONTRACT_VERSION,
                            **{name: _ev_to_dict(getattr(dynamic, name)) for name in dynamic.__dataclass_fields__},
                        }, separators=(",", ":")) + "\n")
                        dynamic_rows += 1

                # advance the rolling per-checkpoint volume baseline with
                # THIS session's own volume-through-C, for future sessions
                # (regardless of partition -- TRAIN's own early sessions
                # still need a real trailing-20 baseline drawn from
                # whatever prior sessions exist, which may themselves be
                # pre-TRAIN).
                for cp_str, cp_t in checkpoint_instants:
                    cp_instant = datetime.combine(d, cp_t, tzinfo=IST)
                    vol = sum(c.volume for c in session_candles if c.ts_open < cp_instant)
                    checkpoint_volume_history[cp_str].append(vol)

    manifest = {
        "contract_version": EVIDENCE_CONTRACT_VERSION,
        "partition": "TRAIN",
        "instrument_count": len(ordered_instruments),
        "session_count": len(train_sessions_seen),
        "session_invariant_row_count": invariant_rows,
        "checkpoint_dynamic_row_count": dynamic_rows,
        "payload_files": {
            "session_invariant": {
                "path": invariant_path.name,
                "sha256": hashlib.sha256(invariant_path.read_bytes()).hexdigest(),
            },
            "checkpoint_dynamic": {
                "path": dynamic_path.name,
                "sha256": hashlib.sha256(dynamic_path.read_bytes()).hexdigest(),
            },
        },
    }
    fingerprint = hashlib.sha256(
        json.dumps(manifest, sort_keys=True, separators=(",", ":")).encode("utf-8")
    ).hexdigest()
    manifest["manifest_id"] = f"em2-evidence-{fingerprint}"
    manifest_path = args.out_dir / "manifest.json"
    manifest_path.write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    print(json.dumps(manifest, indent=2))


if __name__ == "__main__":
    main()
