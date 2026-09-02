"""ID-6B.1A read-only session-data-quality root-cause diagnostic.

Extends ID-6B.1's own observation set with per-timeframe provenance detail
(``SessionContext.five_min``/``.fifteen_min``: quality, bar_count, and an
independently-computed due/present/missing M5 and M15 timestamp set,
mirroring ``SessionContextEngine._timeframe_quality``'s own logic exactly,
never a re-derived copy of the completion formula). Reuses ID-6B.1's own
``ReadOnlyStore``, candidate selection, and default sessions/checkpoints for
an apples-to-apples comparison. Research only: no production code changed,
no DB writes, no provider calls.
"""

from __future__ import annotations

import argparse
import json
from collections import Counter, defaultdict
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from datetime import time as dtime
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

from athena.calendar.engine import CalendarEngine
from athena.config.loader import load_config
from athena.data.id6b1_entry_qualification_baseline import (
    DEFAULT_CHECKPOINTS,
    DEFAULT_SESSION_DATES,
    ReadOnlyStore,
)
from athena.data.validation.calendar_expectations import expected_intraday_opens
from athena.domain.enums import Timeframe
from athena.session import SessionContextEngine

_STEP_MINUTES = {Timeframe.M5: 5, Timeframe.M15: 15}


@dataclass(frozen=True, slots=True)
class TimeframeAudit:
    quality: str
    bar_count: int
    expected_due_count: int
    present_due_count: int
    missing_count: int
    missing_ts: tuple[str, ...]
    latest_missing_is_terminal_bar: bool  # missing bar is the LAST due slot (adjacent to as_of)


def _timeframe_audit(
    candles, timeframe: Timeframe, *, calendar: CalendarEngine, session_date: date,
    as_of: datetime, tzinfo: ZoneInfo, quality: str, bar_count: int,
) -> TimeframeAudit:
    step = _STEP_MINUTES[timeframe]
    expected = expected_intraday_opens(calendar, session_date, step, tzinfo)
    due = [ts for ts in expected if ts + timedelta(minutes=step) <= as_of]
    present = {c.ts_open for c in candles if c.ts_open.date() == session_date}
    missing = [ts for ts in due if ts not in present]
    latest_missing_is_terminal = bool(missing) and missing[-1] == due[-1]
    return TimeframeAudit(
        quality=quality,
        bar_count=bar_count,
        expected_due_count=len(due),
        present_due_count=len(due) - len(missing),
        missing_count=len(missing),
        missing_ts=tuple(ts.isoformat() for ts in missing),
        latest_missing_is_terminal_bar=latest_missing_is_terminal,
    )


def run_audit(
    *,
    db_path: Path,
    config_dir: Path,
    output_dir: Path,
    session_dates: tuple[str, ...] = DEFAULT_SESSION_DATES,
    checkpoints: tuple[str, ...] = DEFAULT_CHECKPOINTS,
    per_type: int = 10,
) -> dict[str, Any]:
    cfg = load_config(config_dir)
    calendar = CalendarEngine.from_config_dir(config_dir, cfg.market)
    tzinfo = ZoneInfo(cfg.market.timezone)
    session_engine = SessionContextEngine()

    store = ReadOnlyStore(db_path)
    rows: list[dict[str, Any]] = []
    try:
        for session_date_raw in session_dates:
            session_date = date.fromisoformat(session_date_raw)
            for checkpoint_raw in checkpoints:
                hour, minute = (int(part) for part in checkpoint_raw.split(":"))
                as_of = datetime.combine(session_date, dtime(hour, minute), tzinfo=tzinfo)
                candidates = store.candidates_at(session_date, as_of, per_type=per_type)
                for candidate in candidates:
                    instrument_id = candidate.instrument_id
                    day_start = datetime.combine(session_date, dtime(9, 15), tzinfo=tzinfo)
                    five_min = store.candles(instrument_id, Timeframe.M5, day_start, as_of)
                    fifteen_min = store.candles(instrument_id, Timeframe.M15, day_start, as_of)
                    latest_quote_ts = store.latest_quote_ts(instrument_id, as_of)
                    session_context = session_engine.assess(
                        instrument_id,
                        as_of=as_of,
                        exchange=cfg.market.exchange,
                        calendar=calendar,
                        sessions=cfg.market.sessions,
                        tzinfo=tzinfo,
                        five_min_candles=five_min,
                        fifteen_min_candles=fifteen_min,
                        latest_quote_ts=latest_quote_ts,
                    )
                    m5_audit = _timeframe_audit(
                        five_min, Timeframe.M5, calendar=calendar, session_date=session_date,
                        as_of=as_of, tzinfo=tzinfo,
                        quality=session_context.five_min.quality.value,
                        bar_count=session_context.five_min.bar_count,
                    )
                    m15_audit = _timeframe_audit(
                        fifteen_min, Timeframe.M15, calendar=calendar, session_date=session_date,
                        as_of=as_of, tzinfo=tzinfo,
                        quality=session_context.fifteen_min.quality.value,
                        bar_count=session_context.fifteen_min.bar_count,
                    )
                    root_cause = "NONE"
                    if session_context.data_quality.value == "EXPECTED_BAR_MISSING":
                        m5_bad = m5_audit.quality == "EXPECTED_BAR_MISSING"
                        m15_bad = m15_audit.quality == "EXPECTED_BAR_MISSING"
                        if m5_bad and m15_bad:
                            root_cause = "BOTH_M5_AND_M15"
                        elif m5_bad:
                            root_cause = "M5_ONLY"
                        elif m15_bad:
                            root_cause = "M15_ONLY"
                        else:
                            root_cause = "UNEXPLAINED"  # combine logic surprise -- flag, don't hide
                    rows.append({
                        "session_date": session_date_raw,
                        "checkpoint": checkpoint_raw,
                        "decision_type": candidate.decision_type,
                        "instrument_id": instrument_id,
                        "combined_quality": session_context.data_quality.value,
                        "root_cause": root_cause,
                        "quote_ts_present": latest_quote_ts is not None,
                        "m5": {
                            "quality": m5_audit.quality,
                            "bar_count": m5_audit.bar_count,
                            "expected_due": m5_audit.expected_due_count,
                            "present_due": m5_audit.present_due_count,
                            "missing_count": m5_audit.missing_count,
                            "missing_ts": m5_audit.missing_ts,
                            "latest_missing_is_terminal_bar": m5_audit.latest_missing_is_terminal_bar,
                        },
                        "m15": {
                            "quality": m15_audit.quality,
                            "bar_count": m15_audit.bar_count,
                            "expected_due": m15_audit.expected_due_count,
                            "present_due": m15_audit.present_due_count,
                            "missing_count": m15_audit.missing_count,
                            "missing_ts": m15_audit.missing_ts,
                            "latest_missing_is_terminal_bar": m15_audit.latest_missing_is_terminal_bar,
                        },
                    })
    finally:
        store.close()

    total = len(rows)
    bad_rows = [r for r in rows if r["combined_quality"] == "EXPECTED_BAR_MISSING"]

    root_cause_counts = Counter(r["root_cause"] for r in bad_rows)
    by_checkpoint: dict[str, Counter] = defaultdict(Counter)
    by_session: dict[str, Counter] = defaultdict(Counter)
    by_type: dict[str, Counter] = defaultdict(Counter)
    by_instrument: Counter = Counter()
    m5_missing_terminal_only = 0
    m15_missing_terminal_only = 0
    for r in bad_rows:
        by_checkpoint[r["checkpoint"]][r["root_cause"]] += 1
        by_session[r["session_date"]][r["root_cause"]] += 1
        by_type[r["decision_type"]][r["root_cause"]] += 1
        by_instrument[r["instrument_id"]] += 1
        m5_single = r["m5"]["latest_missing_is_terminal_bar"] and r["m5"]["missing_count"] == 1
        if r["root_cause"] == "M5_ONLY" and m5_single:
            m5_missing_terminal_only += 1
        m15_single = r["m15"]["latest_missing_is_terminal_bar"] and r["m15"]["missing_count"] == 1
        if r["root_cause"] == "M15_ONLY" and m15_single:
            m15_missing_terminal_only += 1

    # M5/M15 expected-vs-actual by checkpoint, across ALL rows (not just bad ones)
    m5_by_checkpoint: dict[str, dict[str, list[int]]] = defaultdict(lambda: {"expected": [], "present": []})
    m15_by_checkpoint: dict[str, dict[str, list[int]]] = defaultdict(lambda: {"expected": [], "present": []})
    for r in rows:
        m5_by_checkpoint[r["checkpoint"]]["expected"].append(r["m5"]["expected_due"])
        m5_by_checkpoint[r["checkpoint"]]["present"].append(r["m5"]["present_due"])
        m15_by_checkpoint[r["checkpoint"]]["expected"].append(r["m15"]["expected_due"])
        m15_by_checkpoint[r["checkpoint"]]["present"].append(r["m15"]["present_due"])

    def _avg(values: list[int]) -> float:
        return round(sum(values) / len(values), 3) if values else 0.0

    summary = {
        "total_observations": total,
        "expected_bar_missing_count": len(bad_rows),
        "expected_bar_missing_pct": round(len(bad_rows) / total * 100, 2) if total else 0.0,
        "root_cause_counts": dict(root_cause_counts),
        "root_cause_pct_of_bad": {
            k: round(v / len(bad_rows) * 100, 2) for k, v in root_cause_counts.items()
        } if bad_rows else {},
        "single_terminal_bar_missing_only": {
            "m5_only_single_terminal_missing": m5_missing_terminal_only,
            "m15_only_single_terminal_missing": m15_missing_terminal_only,
        },
        "by_checkpoint": {k: dict(v) for k, v in by_checkpoint.items()},
        "by_session": {k: dict(v) for k, v in by_session.items()},
        "by_decision_type": {k: dict(v) for k, v in by_type.items()},
        "distinct_instruments_affected": len(by_instrument),
        "instrument_concentration_top10": by_instrument.most_common(10),
        "m5_expected_vs_present_by_checkpoint": {
            cp: {"avg_expected": _avg(v["expected"]), "avg_present": _avg(v["present"])}
            for cp, v in m5_by_checkpoint.items()
        },
        "m15_expected_vs_present_by_checkpoint": {
            cp: {"avg_expected": _avg(v["expected"]), "avg_present": _avg(v["present"])}
            for cp, v in m15_by_checkpoint.items()
        },
        "quote_ts_present_among_bad_rows": sum(1 for r in bad_rows if r["quote_ts_present"]),
    }

    output_dir.mkdir(parents=True, exist_ok=True)
    with (output_dir / "id6b1a_quality_observations.jsonl").open("w") as f:
        for r in rows:
            f.write(json.dumps(r, sort_keys=True) + "\n")
    with (output_dir / "id6b1a_quality_summary.json").open("w") as f:
        json.dump(summary, f, indent=2, sort_keys=True)

    return summary


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--db", type=Path, default=Path("db/athena.db"))
    parser.add_argument("--config-dir", type=Path, default=Path("config"))
    parser.add_argument("--output-dir", type=Path, default=Path("artifacts/research/id6b1a"))
    parser.add_argument("--per-type", type=int, default=10)
    args = parser.parse_args()
    summary = run_audit(
        db_path=args.db, config_dir=args.config_dir, output_dir=args.output_dir,
        per_type=args.per_type,
    )
    print(json.dumps(summary, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
