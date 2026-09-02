"""ID-6E: Entry Qualification replay & shadow validation harness.

Read-only, research-only. Reuses ID-6B.1's own `ReadOnlyStore`/
`candidates_at` (per-instrument, ranked, WATCH/TRADE-only, market-time
Decision selection at or before each checkpoint — unmodified) and its
exact SessionContext/IntradaySignalSet construction pattern, but — unlike
ID-6B.1/1A/1B, which computed a research-only `candidate_policy_match`
boolean — this module calls the real, owner-closed
`EntryQualificationEngine.evaluate()` and `resolve_evidence_finality()`
for every observation. The v0 formula is never re-derived here.

This is a settled historical MARKET-TIME replay, not a live knowledge-time
reconstruction: conclusions describe how the frozen methodology behaves
when evaluated at historical checkpoints using the data representation the
replay store holds now — never a claim about what ATHENA would have known
live at that historical instant.
"""

from __future__ import annotations

import hashlib
import json
import sqlite3
import time
from collections import Counter, defaultdict
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from datetime import time as dtime
from decimal import Decimal
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

from athena.calendar.engine import CalendarEngine
from athena.config.loader import (
    load_config,
    load_index_intelligence_config,
    load_scoring_config,
    load_sector_index_mapping_config,
)
from athena.data.id6b1_entry_qualification_baseline import ReadOnlyStore, _direction
from athena.data.store import serialization as ser
from athena.data.validation.calendar_expectations import latest_trading_day_on_or_before
from athena.domain.decision import Decision
from athena.domain.enums import DecisionType, Timeframe
from athena.domain.market import Candle
from athena.indicators import IndicatorEngine, IndicatorName, IndicatorStatus
from athena.intraday import (
    EntryQualificationEngine,
    EntryQualificationPolicy,
    GapEngine,
    IntradayAnalyticsEngine,
    OpeningRangeEngine,
    OpeningRangeWindow,
    RelativeStrengthEngine,
    RelativeVolumeEngine,
    resolve_evidence_finality,
)
from athena.scoring import ConfluenceInputs
from athena.session import SessionContextEngine, completed_candles, session_day_start

#: Identical to ID-6B.1B's own deterministically-selected wider window —
#: reused verbatim for direct real-engine-vs-research-baseline
#: comparability (owner §11/§48), not re-selected here.
DEFAULT_SESSION_DATES = (
    "2026-08-14",
    "2026-08-17",
    "2026-08-18",
    "2026-08-19",
    "2026-08-20",
    "2026-08-21",
    "2026-08-24",
    "2026-08-25",
    "2026-08-26",
    "2026-08-27",
)
DEFAULT_CHECKPOINTS = ("09:30", "09:45", "10:00", "11:00", "13:00", "14:30")

_DECISION_COLUMNS = (
    "decision_id, ts, run_id, cycle_id, decision_type, explanation, "
    "instrument_id, direction, score_ref, confidence_ref, risk_ref, "
    "gate_results_json, trade_plan_json"
)


def pct(part: int, whole: int) -> float:
    return round((part / whole * 100.0), 2) if whole else 0.0


@dataclass(frozen=True, slots=True)
class HarnessDefect:
    """A replay-harness-level failure — never silently folded into UNKNOWN."""

    instrument_id: str
    session_date: str
    checkpoint: str
    decision_id: str
    kind: str
    detail: str


def _get_decision(store: ReadOnlyStore, decision_id: str) -> Decision | None:
    row = store.conn.execute(
        f"SELECT {_DECISION_COLUMNS} FROM decisions WHERE decision_id=?", (decision_id,)
    ).fetchone()
    return ser.row_to_decision(tuple(row)) if row is not None else None


def _reason_values(reason_codes: tuple) -> list[str]:
    return [code.value for code in reason_codes]


def run_replay(
    *,
    db_path: Path,
    config_dir: Path,
    output_dir: Path,
    session_dates: tuple[str, ...] = DEFAULT_SESSION_DATES,
    checkpoints: tuple[str, ...] = DEFAULT_CHECKPOINTS,
    per_type: int = 1000,
) -> dict[str, Any]:
    started = time.perf_counter()
    cfg = load_config(config_dir)
    scoring_cfg = load_scoring_config(config_dir)
    calendar = CalendarEngine.from_config_dir(config_dir, cfg.market)
    tzinfo = ZoneInfo(cfg.market.timezone)
    indicator_engine = IndicatorEngine(cfg.indicators)
    session_engine = SessionContextEngine()
    intraday_engine = IntradayAnalyticsEngine()
    opening_range_engine = OpeningRangeEngine()
    rs_engine = RelativeStrengthEngine()
    rvol_engine = RelativeVolumeEngine()
    gap_engine = GapEngine()
    eq_engine = EntryQualificationEngine()
    eq_policy = EntryQualificationPolicy()

    index_cfg = load_index_intelligence_config(config_dir)
    market_benchmark_id = next(
        item.instrument_id for item in index_cfg.tracked_indices if item.key == "nifty_50"
    )
    instrument_by_key = {item.key: item.instrument_id for item in index_cfg.tracked_indices}
    sector_mapping_cfg = load_sector_index_mapping_config(config_dir)
    sector_to_index = {
        mapping.sector: instrument_by_key[mapping.index_key]
        for mapping in sector_mapping_cfg.mappings
        if mapping.index_key in instrument_by_key
    }

    store = ReadOnlyStore(db_path)
    rows: list[dict[str, Any]] = []
    defects: list[HarnessDefect] = []
    candidate_counts: Counter[str] = Counter()
    try:
        for session_date_raw in session_dates:
            session_date = date.fromisoformat(session_date_raw)
            previous_date = latest_trading_day_on_or_before(calendar, session_date - timedelta(days=1))
            for checkpoint_raw in checkpoints:
                hour, minute = (int(part) for part in checkpoint_raw.split(":"))
                as_of = datetime.combine(session_date, dtime(hour, minute), tzinfo=tzinfo)
                day_start = session_day_start(as_of, tzinfo)
                market_m5 = store.candles(market_benchmark_id, Timeframe.M5, day_start, as_of)
                candidates = store.candidates_at(session_date, as_of, per_type=per_type)
                candidate_counts[f"{session_date_raw} {checkpoint_raw}"] = len(candidates)
                sector_m5_cache: dict[str, list[Candle]] = {}
                for sector, sector_index_id in sector_to_index.items():
                    sector_m5_cache[sector] = store.candles(
                        sector_index_id, Timeframe.M5, day_start, as_of
                    )
                for candidate in candidates:
                    instrument_id = candidate.instrument_id
                    decision = _get_decision(store, candidate.decision_id)
                    if decision is None:
                        defects.append(HarnessDefect(
                            instrument_id=instrument_id, session_date=session_date_raw,
                            checkpoint=checkpoint_raw, decision_id=candidate.decision_id,
                            kind="missing_decision",
                            detail="candidates_at returned a decision_id absent from decisions",
                        ))
                        continue

                    five_min = store.candles(instrument_id, Timeframe.M5, day_start, as_of)
                    fifteen_min = store.candles(instrument_id, Timeframe.M15, day_start, as_of)
                    latest_quote_ts = store.latest_quote_ts(instrument_id, as_of)
                    session_context = session_engine.assess(
                        instrument_id, as_of=as_of, exchange=cfg.market.exchange,
                        calendar=calendar, sessions=cfg.market.sessions, tzinfo=tzinfo,
                        five_min_candles=five_min, fifteen_min_candles=fifteen_min,
                        latest_quote_ts=latest_quote_ts,
                    )
                    completed_five = completed_candles(five_min, Timeframe.M5, as_of=as_of)
                    vwap_result = (
                        indicator_engine.compute(IndicatorName.VWAP, completed_five, as_of=as_of)
                        if completed_five else None
                    )
                    daily = store.recent_candles(instrument_id, Timeframe.D1, as_of=as_of, limit=500)
                    daily_indicators = indicator_engine.compute_all([IndicatorName.SMA], daily, as_of=as_of)
                    confluence = None
                    daily_sma = daily_indicators.get(IndicatorName.SMA)
                    if daily_sma is not None and daily_sma.status is IndicatorStatus.OK:
                        daily_last_close = daily_sma.evidence.inputs.get("last_close")
                        if daily_last_close is not None:
                            confluence_cfg = scoring_cfg.confluence
                            daily_bullish = Decimal(daily_last_close) >= daily_sma.values["value"]
                            confluence = ConfluenceInputs(
                                daily_bullish=daily_bullish,
                                five_min_bullish=_direction(
                                    completed_candles(
                                        store.recent_candles(instrument_id, Timeframe.M5, as_of=as_of, limit=100),
                                        Timeframe.M5, as_of=as_of,
                                    ),
                                    confluence_cfg.five_min_sma_period,
                                ),
                                fifteen_min_bullish=_direction(
                                    completed_candles(
                                        store.recent_candles(instrument_id, Timeframe.M15, as_of=as_of, limit=100),
                                        Timeframe.M15, as_of=as_of,
                                    ),
                                    confluence_cfg.fifteen_min_sma_period,
                                ),
                            )
                    orb = opening_range_engine.assess(
                        instrument_id, as_of=as_of, session_context=session_context,
                        five_min_candles=five_min, calendar=calendar, tzinfo=tzinfo,
                    )
                    sector = store.instrument_sector(instrument_id)
                    sector_index_id = sector_to_index.get(sector) if sector else None
                    rs = rs_engine.assess(
                        instrument_id, as_of=as_of, session_context=session_context, sector=sector,
                        market_benchmark_id=market_benchmark_id, sector_benchmark_id=sector_index_id,
                        stock_five_min_candles=five_min, market_five_min_candles=market_m5,
                        sector_five_min_candles=sector_m5_cache.get(sector, []),
                        calendar=calendar, tzinfo=tzinfo,
                    )
                    current_d1 = store.d1_candle_on(instrument_id, session_date)
                    previous_d1 = (
                        store.d1_candle_on(instrument_id, previous_date)
                        if previous_date is not None else None
                    )
                    gap = gap_engine.assess(
                        instrument_id, as_of=as_of, session_date=session_date,
                        previous_session_date=previous_date,
                        previous_session_close=previous_d1.close if previous_d1 else None,
                        current_session_open=current_d1.open if current_d1 else None,
                    )
                    rvol = rvol_engine.assess(
                        instrument_id, as_of=as_of, session_context=session_context,
                        five_min_candles=store.wide_m5(instrument_id, as_of),
                        calendar=calendar, tzinfo=tzinfo,
                    )
                    signal_set = intraday_engine.assess(
                        instrument_id, as_of=as_of, session_date=session_date,
                        session_context=session_context, vwap=vwap_result, confluence=confluence,
                        five_min_sma_period=scoring_cfg.confluence.five_min_sma_period,
                        fifteen_min_sma_period=scoring_cfg.confluence.fifteen_min_sma_period,
                        or15=orb[OpeningRangeWindow.OR15], or30=orb[OpeningRangeWindow.OR30],
                        relative_strength=rs, gap=gap, relative_volume=rvol,
                    )

                    try:
                        evidence_finality = resolve_evidence_finality(decision, session_context)
                        eq = eq_engine.evaluate(
                            decision=decision, session_context=session_context,
                            signal_set=signal_set, evidence_finality=evidence_finality,
                            policy=eq_policy,
                        )
                    except ValueError as exc:
                        defects.append(HarnessDefect(
                            instrument_id=instrument_id, session_date=session_date_raw,
                            checkpoint=checkpoint_raw, decision_id=candidate.decision_id,
                            kind="input_coherence_failure", detail=f"{type(exc).__name__}: {exc}",
                        ))
                        continue

                    rows.append({
                        "session_date": session_date.isoformat(),
                        "checkpoint": checkpoint_raw,
                        "as_of": as_of.isoformat(),
                        "instrument_id": instrument_id,
                        "decision_id": candidate.decision_id,
                        "decision_type": candidate.decision_type,
                        "is_trade": candidate.decision_type == DecisionType.TRADE.value,
                        "session_phase": session_context.phase.value,
                        "data_quality": session_context.data_quality.value,
                        "fifteen_min_available": signal_set.trend.fifteen_min.bullish is not None,
                        "state": eq.state.value,
                        "evidence_finality": eq.evidence_finality.value,
                        "confirmation": eq.confirmation.value,
                        "reason_codes": _reason_values(eq.reason_codes),
                        "methodology_version": eq.methodology_version,
                        "config_snapshot_id": eq.config_snapshot_id,
                        "explanation": eq.explanation,
                    })
    finally:
        store.close()

    return _summarize(
        rows=rows, defects=defects, candidate_counts=candidate_counts,
        session_dates=session_dates, checkpoints=checkpoints, per_type=per_type,
        started=started, output_dir=output_dir,
    )


# --------------------------------------------------------------------------- #
# Analysis
# --------------------------------------------------------------------------- #


def _counter_payload(counter: Counter[str], total: int) -> dict[str, dict[str, float | int]]:
    return {key: {"count": value, "pct": pct(value, total)} for key, value in sorted(counter.items())}


def _state_block(rows: list[dict[str, Any]]) -> dict[str, Any]:
    total = len(rows)
    counts = Counter(row["state"] for row in rows)
    return {
        "total": total,
        "distribution": _counter_payload(counts, total),
        "qualified_pct": pct(counts.get("QUALIFIED", 0), total),
        "not_yet_pct": pct(counts.get("NOT_YET", 0), total),
        "unknown_pct": pct(counts.get("UNKNOWN", 0), total),
    }


def _reason_root_causes(rows: list[dict[str, Any]], state: str) -> dict[str, Any]:
    subset = [row for row in rows if row["state"] == state]
    counts: Counter[str] = Counter()
    for row in subset:
        for reason in row["reason_codes"]:
            counts[reason] += 1
    return {"observations": len(subset), "reason_code_counts": dict(sorted(counts.items()))}


def _checkpoint_distribution(rows: list[dict[str, Any]]) -> dict[str, Any]:
    out: dict[str, Any] = {}
    for checkpoint in sorted({row["checkpoint"] for row in rows}):
        subset = [row for row in rows if row["checkpoint"] == checkpoint]
        out[checkpoint] = _state_block(subset)
    return out


def _watch_trade_comparison(rows: list[dict[str, Any]]) -> dict[str, Any]:
    return {dtype: _state_block([r for r in rows if r["decision_type"] == dtype]) for dtype in ("WATCH", "TRADE")}


def _transitions(rows: list[dict[str, Any]]) -> dict[str, Any]:
    groups: dict[tuple[str, str, str], list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        groups[(row["instrument_id"], row["session_date"], row["decision_type"])].append(row)
    pattern_counts: Counter[str] = Counter()
    multi_checkpoint_groups = 0
    qualified_then_not = 0
    for group_rows in groups.values():
        ordered = sorted(group_rows, key=lambda r: r["checkpoint"])
        if len(ordered) < 2:
            continue
        multi_checkpoint_groups += 1
        states = [r["state"] for r in ordered]
        compact: list[str] = []
        for value in states:
            if not compact or compact[-1] != value:
                compact.append(value)
        pattern_counts[" -> ".join(compact)] += 1
        if "QUALIFIED" in states:
            idx = states.index("QUALIFIED")
            if any(v != "QUALIFIED" for v in states[idx + 1:]):
                qualified_then_not += 1
    return {
        "multi_checkpoint_candidate_groups": multi_checkpoint_groups,
        "patterns": dict(sorted(pattern_counts.items())),
        "qualified_then_later_not_qualified_groups": qualified_then_not,
        "qualified_then_later_not_qualified_pct": pct(qualified_then_not, multi_checkpoint_groups),
    }


def _qualified_duration(rows: list[dict[str, Any]]) -> dict[str, Any]:
    groups: dict[tuple[str, str, str], list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        groups[(row["instrument_id"], row["session_date"], row["decision_type"])].append(row)
    counts: Counter[str] = Counter()
    for group_rows in groups.values():
        ordered = sorted(group_rows, key=lambda r: r["checkpoint"])
        n = sum(1 for r in ordered if r["state"] == "QUALIFIED")
        if n == 0:
            counts["never_qualified"] += 1
        elif n == 1:
            counts["qualified_at_exactly_one_checkpoint"] += 1
        elif n == len(ordered):
            counts["qualified_at_every_observed_checkpoint"] += 1
        else:
            counts["qualified_at_some_but_not_all_checkpoints"] += 1
    return dict(sorted(counts.items()))


def _option_c_validation(rows: list[dict[str, Any]]) -> dict[str, Any]:
    flagged = [r for r in rows if r["data_quality"] == "EXPECTED_BAR_MISSING"]
    return {
        "observations_with_expected_bar_missing": len(flagged),
        "state_distribution_within_flagged": _counter_payload(
            Counter(r["state"] for r in flagged), len(flagged)
        ),
    }


def _m15_impact(rows: list[dict[str, Any]]) -> dict[str, Any]:
    unknown_rows = [r for r in rows if r["state"] == "UNKNOWN"]
    trend_unavailable = [r for r in unknown_rows if "TREND_EVIDENCE_UNAVAILABLE" in r["reason_codes"]]
    m15_unavailable_and_decisive = [r for r in trend_unavailable if not r["fifteen_min_available"]]
    return {
        "unknown_observations": len(unknown_rows),
        "unknown_due_to_trend_evidence_unavailable": len(trend_unavailable),
        "of_those_with_fifteen_min_unavailable": len(m15_unavailable_and_decisive),
        "pct_of_all_observations": pct(len(m15_unavailable_and_decisive), len(rows)),
    }


def _finality_distribution(rows: list[dict[str, Any]]) -> dict[str, Any]:
    return _counter_payload(Counter(row["evidence_finality"] for row in rows), len(rows))


def _qualified_evidence_composition(rows: list[dict[str, Any]]) -> dict[str, Any]:
    qualified = [r for r in rows if r["state"] == "QUALIFIED"]
    counts: Counter[str] = Counter()
    for row in qualified:
        for reason in row["reason_codes"]:
            counts[reason] += 1
    return {"observations": len(qualified), "reason_code_counts": dict(sorted(counts.items()))}


def _invariant_checks(rows: list[dict[str, Any]]) -> dict[str, Any]:
    disqualified = sum(1 for r in rows if r["state"] == "DISQUALIFIED_FOR_SESSION")
    confirmed_by_policy = sum(1 for r in rows if r["confirmation"] == "CONFIRMED_BY_POLICY")
    not_evaluated = sum(1 for r in rows if r["confirmation"] == "NOT_EVALUATED")
    non_v0_methodology = sum(1 for r in rows if r["methodology_version"] != "entry-qualification-v0")
    return {
        "disqualified_for_session_count": disqualified,
        "disqualified_for_session_invariant_holds": disqualified == 0,
        "confirmed_by_policy_count": confirmed_by_policy,
        "confirmed_by_policy_invariant_holds": confirmed_by_policy == 0,
        "not_evaluated_confirmation_count": not_evaluated,
        "not_evaluated_confirmation_invariant_holds": not_evaluated == len(rows),
        "non_v0_methodology_version_count": non_v0_methodology,
        "methodology_version_invariant_holds": non_v0_methodology == 0,
    }


def _analysis_digest(summary: dict[str, Any]) -> str:
    stable = json.loads(json.dumps(summary, sort_keys=True))
    stable["metadata"].pop("runtime_seconds", None)
    stable.pop("artifacts", None)
    payload = json.dumps(stable, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def _summarize(
    *,
    rows: list[dict[str, Any]],
    defects: list[HarnessDefect],
    candidate_counts: Counter[str],
    session_dates: tuple[str, ...],
    checkpoints: tuple[str, ...],
    per_type: int,
    started: float,
    output_dir: Path,
) -> dict[str, Any]:
    total = len(rows)
    output_dir.mkdir(parents=True, exist_ok=True)
    rows_path = output_dir / "id6e_observations.jsonl"
    with rows_path.open("w", encoding="utf-8") as fh:
        for row in rows:
            fh.write(json.dumps(row, sort_keys=True) + "\n")
    defects_path = output_dir / "id6e_defects.jsonl"
    with defects_path.open("w", encoding="utf-8") as fh:
        for defect in defects:
            fh.write(json.dumps({
                "instrument_id": defect.instrument_id, "session_date": defect.session_date,
                "checkpoint": defect.checkpoint, "decision_id": defect.decision_id,
                "kind": defect.kind, "detail": defect.detail,
            }, sort_keys=True) + "\n")

    summary: dict[str, Any] = {
        "metadata": {
            "milestone": "ID-6E",
            "label": "settled historical market-time replay via the real EntryQualificationEngine",
            "session_dates": list(session_dates),
            "checkpoints": list(checkpoints),
            "per_type_cap": per_type,
            "read_only": "SQLite URI mode=ro with PRAGMA query_only=ON",
            "runtime_seconds": round(time.perf_counter() - started, 3),
        },
        "sample": {
            "candidate_checkpoint_observations": total,
            "distinct_sessions": len({row["session_date"] for row in rows}),
            "distinct_instruments": len({row["instrument_id"] for row in rows}),
            "candidate_counts_by_checkpoint": dict(sorted(candidate_counts.items())),
            "harness_defects": len(defects),
        },
        "state_distribution": _state_block(rows),
        "checkpoint_distribution": _checkpoint_distribution(rows),
        "watch_trade_comparison": _watch_trade_comparison(rows),
        "transitions": _transitions(rows),
        "qualified_duration": _qualified_duration(rows),
        "unknown_root_causes": _reason_root_causes(rows, "UNKNOWN"),
        "not_yet_root_causes": _reason_root_causes(rows, "NOT_YET"),
        "qualified_evidence_composition": _qualified_evidence_composition(rows),
        "option_c_validation": _option_c_validation(rows),
        "m15_impact": _m15_impact(rows),
        "finality_distribution": _finality_distribution(rows),
        "invariants": _invariant_checks(rows),
    }
    summary_path = output_dir / "id6e_summary.json"
    analysis_digest = _analysis_digest(summary)
    summary["artifacts"] = {
        "summary_path": str(summary_path),
        "observations_path": str(rows_path),
        "defects_path": str(defects_path),
        "analysis_sha256": analysis_digest,
    }
    summary_path.write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return summary


# --------------------------------------------------------------------------- #
# Shadow (persisted runtime) audit — read-only, no writes, no mutation.
# --------------------------------------------------------------------------- #

_ENTRY_QUALIFICATION_COLUMNS = (
    "instrument_id, session_date, as_of, decision_id, methodology_version, "
    "run_id, cycle_id, decision_type, state, evidence_finality, confirmation, "
    "reason_codes_json, evidence_refs_json, config_snapshot_id, explanation, persisted_at"
)


def _table_exists(conn, name: str) -> bool:
    row = conn.execute(
        "SELECT 1 FROM sqlite_master WHERE type='table' AND name=?", (name,)
    ).fetchone()
    return row is not None


def _percentile(sorted_values: list[float], p: float) -> float | None:
    if not sorted_values:
        return None
    idx = min(len(sorted_values) - 1, max(0, round(p * (len(sorted_values) - 1))))
    return sorted_values[idx]


def run_shadow_audit(*, db_path: Path) -> dict[str, Any]:
    """Read-only audit of persisted, real `entry_qualifications` runtime
    observations. Never mutates the database; never fabricates rows if the
    table is empty or missing — reports that honestly instead."""
    uri = f"file:{db_path}?mode=ro"
    conn = sqlite3.connect(uri, uri=True)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA query_only=ON")
    try:
        if not _table_exists(conn, "entry_qualifications"):
            return {
                "status": "SHADOW_OBSERVATIONS_NOT_YET_AVAILABLE",
                "reason": "entry_qualifications table does not exist in this database "
                          "(schema not yet migrated against it)",
                "observation_count": 0,
            }
        rows = conn.execute(
            f"SELECT {_ENTRY_QUALIFICATION_COLUMNS} FROM entry_qualifications"
        ).fetchall()
        if not rows:
            return {
                "status": "SHADOW_OBSERVATIONS_NOT_YET_AVAILABLE",
                "reason": "entry_qualifications table exists but contains zero rows",
                "observation_count": 0,
            }

        total = len(rows)
        state_counts: Counter[str] = Counter()
        finality_counts: Counter[str] = Counter()
        confirmation_counts: Counter[str] = Counter()
        methodology_counts: Counter[str] = Counter()
        decision_types: Counter[str] = Counter()
        sessions: set[str] = set()
        instruments: set[str] = set()
        seen_identity: set[tuple] = set()
        duplicate_identities = 0
        naive_persisted_at = 0
        latencies_seconds: list[float] = []
        negative_latency_count = 0
        for row in rows:
            state_counts[row["state"]] += 1
            finality_counts[row["evidence_finality"]] += 1
            confirmation_counts[row["confirmation"]] += 1
            methodology_counts[row["methodology_version"]] += 1
            decision_types[row["decision_type"]] += 1
            sessions.add(row["session_date"])
            instruments.add(row["instrument_id"])
            identity = (
                row["instrument_id"], row["session_date"], row["as_of"],
                row["decision_id"], row["methodology_version"],
            )
            if identity in seen_identity:
                duplicate_identities += 1
            seen_identity.add(identity)

            persisted_at = datetime.fromisoformat(row["persisted_at"])
            if persisted_at.tzinfo is None:
                naive_persisted_at += 1
            else:
                as_of_dt = datetime.fromisoformat(row["as_of"])
                latency = (persisted_at - as_of_dt).total_seconds()
                latencies_seconds.append(latency)
                if latency < 0:
                    negative_latency_count += 1

        latencies_sorted = sorted(latencies_seconds)
        earliest = min(row["persisted_at"] for row in rows)
        latest = max(row["persisted_at"] for row in rows)

        return {
            "status": "SHADOW_OBSERVATIONS_AVAILABLE",
            "observation_count": total,
            "earliest_persisted_at": earliest,
            "latest_persisted_at": latest,
            "distinct_sessions": len(sessions),
            "distinct_instruments": len(instruments),
            "decision_type_counts": dict(sorted(decision_types.items())),
            "state_counts": dict(sorted(state_counts.items())),
            "finality_counts": dict(sorted(finality_counts.items())),
            "confirmation_counts": dict(sorted(confirmation_counts.items())),
            "methodology_version_counts": dict(sorted(methodology_counts.items())),
            "integrity": {
                "duplicate_logical_identity_count": duplicate_identities,
                "naive_persisted_at_count": naive_persisted_at,
                "disqualified_for_session_count": state_counts.get("DISQUALIFIED_FOR_SESSION", 0),
                "confirmed_by_policy_count": confirmation_counts.get("CONFIRMED_BY_POLICY", 0),
                "non_not_evaluated_confirmation_count": total - confirmation_counts.get("NOT_EVALUATED", 0),
            },
            "persistence_latency_seconds": {
                "sample_size": len(latencies_seconds),
                "median": _percentile(latencies_sorted, 0.5),
                "p90": _percentile(latencies_sorted, 0.9),
                "p95": _percentile(latencies_sorted, 0.95),
                "max": latencies_sorted[-1] if latencies_sorted else None,
                "negative_latency_count": negative_latency_count,
            },
        }
    finally:
        conn.close()
