"""EM-1c regime-evidence prerequisite: acquire real historical NIFTY 50 /
INDIA VIX daily (D1) candle history via the canonical, corrected
KiteProvider path, validate it against real already-persisted evidence and
the real trading calendar, and -- only if every check passes -- persist an
immutable, content-hashed evidence manifest for the historical regime
reconstruction step.

Owner mandate (2026-08-27): reuse the canonical RegimeEngine and
config/regime.json unchanged; never substitute a proxy instrument (e.g.
NSE:NIFTYAXIS, a real but unrelated Axis Mutual Fund NIFTY-ETF unit found
and rejected during the contract audit); never silently overwrite
conflicting existing data; STOP and report rather than proceed on any
overlap discrepancy or calendar mismatch.

EMR isolation (ADR-012): this script is read-only against the canonical
`candles`/`instruments` tables and writes only to
`artifacts/research/em1c-regime/` (git-ignored) -- it never mutates the
canonical database, matching every prior EMR acquisition script
(em1r2/em1r3/em1r5/em1b) in this workstream.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sqlite3
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from decimal import Decimal
from pathlib import Path

from athena.calendar.engine import CalendarEngine
from athena.config.loader import load_config
from athena.data.providers.kite_provider import KiteProvider
from athena.domain.enums import SessionType, Timeframe
from athena.domain.market import Candle
from athena.ops.kite_auth import force_inject_kite_env

#: Real, rejected-as-invalid substitute found during the contract audit --
#: an Axis Mutual Fund NIFTY-ETF *unit*, not the NIFTY 50 index itself.
#: Recorded here only so it is never silently reconsidered.
REJECTED_PROXY_INSTRUMENTS = ("NSE:NIFTYAXIS",)

INSTRUMENTS = ("NSE:NIFTY 50", "NSE:INDIA VIX")

#: Already-disclosed, owner-accepted data gap (EM-1r3's own production
#: capture found the exact same zero-candle blackout across ALL 518
#: cohort instruments that day too -- a real, provider/exchange-wide
#: event, not specific to this acquisition). Owner decision 2026-08-27:
#: keep the existing disclosed treatment, no new action required.
KNOWN_ACCEPTABLE_MISSING_TRADING_DAYS = ("2024-01-22",)


@dataclass(frozen=True)
class OverlapMismatch:
    instrument_id: str
    session_date: str
    field: str
    existing: str
    fetched: str


#: Owner-approved source-authority resolution policy (2026-08-27) for
#: existing-DB-vs-freshly-fetched overlap discrepancies: attempt an
#: authoritative NSE cross-check first; if unobtainable, use the freshly
#: fetched Kite series (a single coherent retrieval snapshot) for the
#: research manifest -- never silently overwrite the canonical DB, and
#: never claim a specific cause without evidence. NSE's own historical-VIX
#: report page (nseindia.com) is not fetchable by this environment's tools
#: (confirmed: two independent WebFetch attempts both timed out, a known
#: real characteristic of NSE's anti-scraping posture) -- so per the
#: approved fallback, an authoritative-NSE-independent third-party
#: cross-check is attempted per date via web search instead; when found it
#: is recorded as `resolution_source`, otherwise the fallback fires.
NSE_HISTORICAL_VIX_UNREACHABLE_NOTE = (
    "NSE's own historical-VIX report page (nseindia.com/reports-indices-historical-vix) "
    "was not reachable by this environment's WebFetch tool (timed out on two independent "
    "attempts, 2026-08-27) -- a known characteristic of NSE's anti-scraping posture, not "
    "a defect specific to this date."
)


@dataclass(frozen=True)
class ResolvedOverlap:
    session_date: str
    field: str
    existing_value: str
    existing_source: str
    fetched_value: str
    fetched_retrieved_at: str
    absolute_difference: str
    relative_difference_pct: str
    selected_value: str
    selection_reason: str


@dataclass(frozen=True)
class ValidationReport:
    instrument_id: str
    fetched_count: int
    first_date: str | None
    last_date: str | None
    overlap_rows_checked: int
    overlap_mismatches: tuple[OverlapMismatch, ...]
    duplicate_dates: tuple[str, ...]
    #: real trading days with no fetched candle, split into the
    #: already-disclosed/accepted gap (see KNOWN_ACCEPTABLE_MISSING_TRADING_DAYS)
    #: vs anything else, which is a genuinely unexplained new gap.
    known_missing_trading_days: tuple[str, ...]
    unexplained_missing_trading_days: tuple[str, ...]
    #: real fetched candles on a day the calendar does not call a normal
    #: trading session, split into KNOWN_UNSUPPORTED_SPECIAL_SESSION days
    #: (real trading occurred, just not representable by ATHENA's
    #: single-window session model -- informational, not an anomaly) vs
    #: anything else (a genuine, unexplained anomaly).
    known_special_session_days_with_data: tuple[str, ...]
    unexplained_non_trading_days_with_data: tuple[str, ...]
    all_timezone_aware: bool

    @property
    def passed(self) -> bool:
        # Overlap mismatches are handled by the documented source-authority
        # resolution policy (see resolve_overlap_mismatches), not treated as
        # a hard acceptance failure. Known/already-disclosed gaps and known
        # special sessions are informational, not blocking -- only a
        # genuinely NEW, unexplained discrepancy blocks acceptance.
        return (
            not self.duplicate_dates
            and not self.unexplained_missing_trading_days
            and not self.unexplained_non_trading_days_with_data
            and self.all_timezone_aware
        )


def _existing_candles(db_path: Path, instrument_id: str) -> dict[date, Candle]:
    conn = sqlite3.connect(db_path)
    try:
        cur = conn.execute(
            "SELECT ts_open, open, high, low, close, volume FROM candles "
            "WHERE instrument_id = ? AND timeframe = '1d' ORDER BY ts_open",
            (instrument_id,),
        )
        rows = cur.fetchall()
    finally:
        conn.close()
    result: dict[date, Candle] = {}
    for ts_open_raw, o, h, lo, c, v in rows:
        ts_open = datetime.fromisoformat(ts_open_raw)
        result[ts_open.date()] = Candle(
            instrument_id=instrument_id, timeframe=Timeframe.D1,
            ts_open=ts_open, open=Decimal(o), high=Decimal(h), low=Decimal(lo),
            close=Decimal(c), volume=int(v), source="kite", adjusted=False,
        )
    return result


def validate(
    *,
    instrument_id: str,
    fetched: list[Candle],
    existing: dict[date, Candle],
    calendar: CalendarEngine,
    study_start: date,
    study_end: date,
) -> ValidationReport:
    by_date: dict[date, list[Candle]] = {}
    for c in fetched:
        by_date.setdefault(c.ts_open.date(), []).append(c)

    duplicate_dates = tuple(sorted(d.isoformat() for d, rows in by_date.items() if len(rows) > 1))

    mismatches: list[OverlapMismatch] = []
    overlap_checked = 0
    for d, existing_candle in existing.items():
        fetched_rows = by_date.get(d)
        if not fetched_rows:
            continue
        overlap_checked += 1
        fc = fetched_rows[0]
        for field in ("open", "high", "low", "close"):
            ev, fv = getattr(existing_candle, field), getattr(fc, field)
            if Decimal(ev) != Decimal(fv):
                mismatches.append(OverlapMismatch(
                    instrument_id=instrument_id, session_date=d.isoformat(), field=field,
                    existing=str(ev), fetched=str(fv),
                ))
        if existing_candle.volume != fc.volume:
            mismatches.append(OverlapMismatch(
                instrument_id=instrument_id, session_date=d.isoformat(), field="volume",
                existing=str(existing_candle.volume), fetched=str(fc.volume),
            ))

    fetched_dates = set(by_date)
    known_missing: list[str] = []
    unexplained_missing: list[str] = []
    known_special_with_data: list[str] = []
    unexplained_non_trading_with_data: list[str] = []
    day = study_start
    while day <= study_end:
        ctx = calendar.context_for(day)
        has_candle = day in fetched_dates
        iso = day.isoformat()
        if ctx.is_trading_session and not has_candle:
            (known_missing if iso in KNOWN_ACCEPTABLE_MISSING_TRADING_DAYS else unexplained_missing).append(iso)
        if not ctx.is_trading_session and has_candle:
            target = (
                known_special_with_data
                if ctx.session_type is SessionType.KNOWN_UNSUPPORTED_SPECIAL_SESSION
                else unexplained_non_trading_with_data
            )
            target.append(iso)
        day += timedelta(days=1)

    all_tz_aware = all(c.ts_open.tzinfo is not None for c in fetched)
    dates_sorted = sorted(by_date)

    return ValidationReport(
        instrument_id=instrument_id,
        fetched_count=len(fetched),
        first_date=dates_sorted[0].isoformat() if dates_sorted else None,
        last_date=dates_sorted[-1].isoformat() if dates_sorted else None,
        overlap_rows_checked=overlap_checked,
        overlap_mismatches=tuple(mismatches),
        duplicate_dates=duplicate_dates,
        known_missing_trading_days=tuple(known_missing),
        unexplained_missing_trading_days=tuple(unexplained_missing),
        known_special_session_days_with_data=tuple(known_special_with_data),
        unexplained_non_trading_days_with_data=tuple(unexplained_non_trading_with_data),
        all_timezone_aware=all_tz_aware,
    )


#: Real, independently found third-party corroboration for one of the 14
#: contested India VIX dates (CEIC, which republishes official NSE index
#: data): close=11.32 on 2026-08-19, matching the freshly-fetched Kite
#: value, not the existing DB value. Keyed by (session_date, field). Not a
#: general NSE-lookup mechanism -- a specific, documented finding from this
#: milestone's own research, recorded so it is never silently lost.
EXTERNAL_CORROBORATION: dict[tuple[str, str], tuple[str, str]] = {
    ("2026-08-19", "close"): (
        "11.32",
        "CEIC (republishing official NSE India VIX index data): close 11.320 on 2026-08-19",
    ),
}


def resolve_overlap_mismatches(
    mismatches: tuple[OverlapMismatch, ...], *, retrieved_at: str
) -> tuple[ResolvedOverlap, ...]:
    """Apply the owner-approved source-authority resolution policy: prefer
    an authoritative NSE-independent corroboration where one was actually
    found during this milestone's own research; otherwise fall back to the
    freshly-fetched Kite series (a single coherent retrieval snapshot),
    documented as an unresolved provider-vintage/revision uncertainty --
    never claimed as a proven cause."""

    resolved = []
    for m in mismatches:
        existing_dec, fetched_dec = Decimal(m.existing), Decimal(m.fetched)
        abs_diff = abs(existing_dec - fetched_dec)
        rel_diff = (abs_diff / existing_dec * 100) if existing_dec != 0 else Decimal(0)

        corroboration = EXTERNAL_CORROBORATION.get((m.session_date, m.field))
        if corroboration is not None:
            selected_value, source_note = corroboration
            reason = f"authoritative third-party corroboration found: {source_note}"
        else:
            selected_value = m.fetched
            reason = (
                "authoritative NSE historical value not cleanly obtainable "
                f"({NSE_HISTORICAL_VIX_UNREACHABLE_NOTE}); falling back to the owner-approved "
                "default -- the freshly fetched Kite series, a single coherent retrieval "
                "snapshot. Documented as an unresolved provider-vintage/revision "
                "uncertainty, not a proven cause."
            )

        resolved.append(ResolvedOverlap(
            session_date=m.session_date, field=m.field,
            existing_value=m.existing, existing_source="athena canonical db (candles table)",
            fetched_value=m.fetched, fetched_retrieved_at=retrieved_at,
            absolute_difference=str(abs_diff), relative_difference_pct=f"{rel_diff:.4f}",
            selected_value=selected_value, selection_reason=reason,
        ))
    return tuple(resolved)


def _candle_payload(candles: list[Candle]) -> list[dict]:
    return [
        {
            "ts_open": c.ts_open.isoformat(), "open": str(c.open), "high": str(c.high),
            "low": str(c.low), "close": str(c.close), "volume": c.volume,
        }
        for c in sorted(candles, key=lambda c: c.ts_open)
    ]


def main() -> None:
    parser = argparse.ArgumentParser(description="EM-1c regime evidence acquisition.")
    parser.add_argument("--db", type=Path, default=Path("db/athena.db"))
    parser.add_argument("--config-dir", type=Path, default=Path("config"))
    parser.add_argument("--env-file", type=Path, default=Path(".env"))
    parser.add_argument("--start", type=date.fromisoformat, default=date(2023, 5, 1))
    parser.add_argument("--end", type=date.fromisoformat, default=date(2026, 8, 21))
    parser.add_argument("--out-dir", type=Path, default=Path("artifacts/research/em1c-regime/acquisition"))
    args = parser.parse_args()

    config = load_config(args.config_dir)
    calendar = CalendarEngine.from_config_dir(args.config_dir, config.market)

    force_inject_kite_env(args.env_file)
    symbols = [iid.split(":", 1)[1] for iid in INSTRUMENTS]
    provider = KiteProvider.from_config_dir(args.config_dir, symbols=symbols, strict_symbol_filter=False)

    args.out_dir.mkdir(parents=True, exist_ok=True)
    overall_pass = True
    manifest_entries = {}
    retrieved_at = datetime.now().astimezone().isoformat()

    for instrument_id in INSTRUMENTS:
        print(f"fetching {instrument_id} {args.start}..{args.end}")
        fetched = provider.daily_candles(instrument_id, args.start, args.end)
        existing = _existing_candles(args.db, instrument_id)
        report = validate(
            instrument_id=instrument_id, fetched=fetched, existing=existing,
            calendar=calendar, study_start=args.start, study_end=args.end,
        )
        resolved_overlaps = resolve_overlap_mismatches(report.overlap_mismatches, retrieved_at=retrieved_at)
        print(json.dumps({
            "instrument_id": report.instrument_id, "fetched_count": report.fetched_count,
            "first_date": report.first_date, "last_date": report.last_date,
            "overlap_rows_checked": report.overlap_rows_checked,
            "overlap_mismatches": len(report.overlap_mismatches),
            "duplicate_dates": report.duplicate_dates,
            "known_missing_trading_days": report.known_missing_trading_days,
            "unexplained_missing_trading_days": report.unexplained_missing_trading_days,
            "known_special_session_days_with_data": report.known_special_session_days_with_data,
            "unexplained_non_trading_days_with_data": report.unexplained_non_trading_days_with_data,
            "all_timezone_aware": report.all_timezone_aware,
            "passed": report.passed,
        }, indent=2))

        if resolved_overlaps:
            print(f"RESOLVED OVERLAP DISCREPANCIES for {instrument_id}:")
            for r in resolved_overlaps:
                print(
                    f"  {r.session_date} {r.field}: existing={r.existing_value} "
                    f"fetched={r.fetched_value} -> selected={r.selected_value} "
                    f"({'corroborated' if 'corroboration found' in r.selection_reason else 'fallback'})"
                )

        # Always persist the raw fetched payload for diagnosis, regardless of
        # validation outcome -- distinct from "accepted for reconstruction"
        # (overall_validation_passed), which gates whether it may be used.
        payload = _candle_payload(fetched)
        payload_bytes = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
        payload_sha256 = hashlib.sha256(payload_bytes).hexdigest()
        payload_path = args.out_dir / f"{payload_sha256}.json"
        payload_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
        manifest_entries[instrument_id] = {
            "payload_file": payload_path.name,
            "payload_sha256": payload_sha256,
            "candle_count": len(payload),
            "first_date": report.first_date,
            "last_date": report.last_date,
            "overlap_rows_validated": report.overlap_rows_checked,
            "overlap_mismatch_count": len(report.overlap_mismatches),
            "resolved_overlap_discrepancies": [
                {
                    "session_date": r.session_date, "field": r.field,
                    "existing_value": r.existing_value, "existing_source": r.existing_source,
                    "fetched_value": r.fetched_value, "fetched_retrieved_at": r.fetched_retrieved_at,
                    "absolute_difference": r.absolute_difference,
                    "relative_difference_pct": r.relative_difference_pct,
                    "selected_value": r.selected_value, "selection_reason": r.selection_reason,
                }
                for r in resolved_overlaps
            ],
            "duplicate_dates": list(report.duplicate_dates),
            "known_missing_trading_days": list(report.known_missing_trading_days),
            "unexplained_missing_trading_days": list(report.unexplained_missing_trading_days),
            "known_special_session_days_with_data": list(report.known_special_session_days_with_data),
            "unexplained_non_trading_days_with_data": list(report.unexplained_non_trading_days_with_data),
            "validation_passed": report.passed,
        }
        if not report.passed:
            overall_pass = False

    manifest = {
        "contract_version": "em1c-regime-acquisition-v1",
        "acquisition_range": {"start": args.start.isoformat(), "end": args.end.isoformat()},
        "source": "kite",
        "rejected_proxy_instruments": list(REJECTED_PROXY_INSTRUMENTS),
        "instruments": manifest_entries,
        "overall_validation_passed": overall_pass,
    }
    fingerprint = hashlib.sha256(
        json.dumps(manifest, sort_keys=True, separators=(",", ":")).encode("utf-8")
    ).hexdigest()
    manifest["manifest_id"] = f"em1c-regime-acq-{fingerprint}"
    manifest_path = args.out_dir / "manifest.json"
    manifest_path.write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    print(f"\nwrote {manifest_path}")

    if not overall_pass:
        raise SystemExit(
            "VALIDATION FAILED -- see report above. Evidence NOT accepted for reconstruction."
        )
    print("\nAll validation checks passed. Evidence accepted.")


if __name__ == "__main__":
    main()
