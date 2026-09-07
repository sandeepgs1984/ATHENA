"""ID-8: Full historical entry/risk empirical outcome validation.

Read-only, research-only. Executes the frozen ID-8 empirical contract
(`docs/research/ID-8-ENTRY-RISK-METHODOLOGY-VALIDATION-DISCOVERY.md`) at
historical scale: independently reconstructs the real LONG TRADE+
REPLAYED_QUALIFIED population (ID-7B.1's own methodology, never
literally re-run since that harness was never committed) and then
measures real forward price-path outcomes (MFE/MAE, T1/T2 reachability,
VWAP-loss occurrence/timing, terminal ordering, risk geometry, RR) --
genuinely new code, since no forward-reading capability exists anywhere
else in the repository (ID-6E/ID-7F1 are both backward/PIT-bounded
only).

Two structurally separate phases, enforced by module layout (never by
convention alone -- see the dedicated isolation test in
tests/data_layer/test_id8_entry_risk_outcome_validation.py):

    PHASE A -- POINT-IN-TIME OBSERVATION SELECTION
        Reuses ID-6E's own exact evidence-composition pattern
        (`id6e_replay_shadow_validation.run_replay`'s inner loop,
        generalized here to an arbitrary (Decision, as_of) pair instead
        of a fixed session/checkpoint grid) to replay the real,
        unmodified `EntryQualificationEngine` over real historical TRADE
        Decisions, using ONLY data at-or-before each checkpoint. No
        forward candle is read anywhere in this phase.

    PHASE B -- FORWARD OUTCOME ANALYSIS
        Reads ONLY candles strictly after a frozen, already-selected
        observation's checkpoint, up to the same session's close. Never
        used to select or filter the Phase-A population.

This is RAW_PRICE_PATH_VALIDATION only -- no execution cost data exists
anywhere in the schema (confirmed by the ID-8 discovery milestone), so
no profitability claim is made or implied anywhere in this module.
"""

from __future__ import annotations

import json
import time
from collections import Counter, defaultdict
from dataclasses import dataclass
from datetime import date, datetime, timedelta
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
from athena.domain.enums import DecisionType, Direction, Timeframe
from athena.domain.market import Candle
from athena.indicators import IndicatorEngine, IndicatorName, IndicatorStatus
from athena.intraday import (
    EntryQualificationEngine,
    EntryQualificationPolicy,
    EntryQualificationState,
    GapEngine,
    IntradayAnalyticsEngine,
    OpeningRangeEngine,
    OpeningRangeWindow,
    RelativeStrengthEngine,
    RelativeVolumeEngine,
    resolve_evidence_finality,
)
from athena.intraday.opening_range_models import OpeningRangeFormationStatus
from athena.scoring import ConfluenceInputs
from athena.session import SessionContextEngine, completed_candles, session_day_start

T1_PCT = Decimal("0.01")
T2_PCT = Decimal("0.015")

_DECISION_COLUMNS = (
    "decision_id, ts, run_id, cycle_id, decision_type, explanation, "
    "instrument_id, direction, score_ref, confidence_ref, risk_ref, "
    "gate_results_json, trade_plan_json"
)


def pct(part: int, whole: int) -> float:
    return round((part / whole * 100.0), 2) if whole else 0.0


def _percentile(sorted_values: list[float], p: float) -> float | None:
    if not sorted_values:
        return None
    k = (len(sorted_values) - 1) * p
    f, c = int(k), min(int(k) + 1, len(sorted_values) - 1)
    if f == c:
        return sorted_values[f]
    return sorted_values[f] + (sorted_values[c] - sorted_values[f]) * (k - f)


def _distribution(values: list[float]) -> dict[str, Any]:
    if not values:
        return {"n": 0}
    s = sorted(values)
    return {
        "n": len(values),
        "median": _percentile(s, 0.5), "p25": _percentile(s, 0.25),
        "p75": _percentile(s, 0.75), "p90": _percentile(s, 0.90),
        "p95": _percentile(s, 0.95), "max": s[-1], "min": s[0],
    }


@dataclass(frozen=True, slots=True)
class ReplayDefect:
    instrument_id: str
    session_date: str
    decision_id: str
    kind: str
    detail: str


# --------------------------------------------------------------------------- #
# PHASE A -- point-in-time observation selection (never reads a forward candle)
# --------------------------------------------------------------------------- #


def _get_decision(store: ReadOnlyStore, decision_id: str) -> Decision | None:
    row = store.conn.execute(
        f"SELECT {_DECISION_COLUMNS} FROM decisions WHERE decision_id=?", (decision_id,)
    ).fetchone()
    return ser.row_to_decision(tuple(row)) if row is not None else None


def build_trade_episodes(store: ReadOnlyStore, *, decision_type: str = "TRADE") -> dict[str, Any]:
    """Zero-invented-parameter episode construction, reusing ID-7B.1's own
    published rule exactly: group consecutive-in-time same-`decision_type`
    rows for the same instrument into one episode; a boundary occurs on
    ANY `decision_type` change (an intervening WATCH/NO_TRADE/etc. row
    breaks a TRADE run, even mid-session) or a session-date change.

    This reads the FULL per-instrument decision timeline (every
    `decision_type`, not pre-filtered) precisely so an intervening
    non-`decision_type` row can be detected -- pre-filtering to only
    `decision_type=?` rows before grouping (an earlier draft of this
    function did exactly that) silently discards the very rows needed to
    detect a type-change boundary, over-merging episodes. Only `decision_type`
    runs are emitted as episodes; non-matching runs are consumed for
    boundary detection only, never emitted."""
    rows = store.conn.execute(
        "SELECT decision_id, ts, instrument_id, direction, decision_type "
        "FROM decisions WHERE instrument_id IS NOT NULL ORDER BY instrument_id, ts"
    ).fetchall()
    total_decisions = sum(1 for r in rows if r[4] == decision_type)

    by_instrument: dict[str, list[tuple]] = defaultdict(list)
    for row in rows:
        by_instrument[row[2]].append(tuple(row))

    episodes: list[dict[str, Any]] = []
    for instrument_id, irows in by_instrument.items():
        current: list[tuple] = []
        current_session: str | None = None
        for decision_id, ts, _iid, direction, dtype in irows:
            session_date = ts[:10]
            same_run = (
                current and session_date == current_session and dtype == decision_type
            )
            if same_run:
                current.append((decision_id, ts, direction))
                continue
            if current:
                episodes.append(_episode_from_run(instrument_id, current_session, current))
                current = []
            if dtype == decision_type:
                current = [(decision_id, ts, direction)]
                current_session = session_date
            else:
                current_session = session_date
        if current:
            episodes.append(_episode_from_run(instrument_id, current_session, current))

    accounted = sum(e["episode_length"] for e in episodes)
    return {
        "total_decisions": total_decisions,
        "total_episodes": len(episodes),
        "accounted_rows": accounted,
        "reconciles": accounted == total_decisions,
        "episodes": episodes,
    }


def _episode_from_run(instrument_id: str, session_date: str, run: list[tuple]) -> dict[str, Any]:
    first_decision_id, first_ts, first_direction = run[0]
    return {
        "instrument_id": instrument_id, "session_date": session_date,
        "first_decision_id": first_decision_id, "first_ts": first_ts,
        "first_direction": first_direction, "episode_length": len(run),
    }


def _reconstruct_eq_at_checkpoint(
    *, store: ReadOnlyStore, decision: Decision, as_of: datetime, session_date: date,
    calendar: CalendarEngine, tzinfo: ZoneInfo, cfg, scoring_cfg,
    indicator_engine: IndicatorEngine, session_engine: SessionContextEngine,
    intraday_engine: IntradayAnalyticsEngine, opening_range_engine: OpeningRangeEngine,
    rs_engine: RelativeStrengthEngine, rvol_engine: RelativeVolumeEngine, gap_engine: GapEngine,
    eq_engine: EntryQualificationEngine, eq_policy: EntryQualificationPolicy,
    market_benchmark_id: str, sector_to_index: dict[str, str],
):
    """Generalized extraction of `id6e_replay_shadow_validation.run_replay`'s
    own inner-loop evidence composition -- identical formulas/bounds,
    parameterized by an arbitrary (Decision, as_of) pair instead of a
    fixed session/checkpoint grid. Every candle read here is bounded
    `<= as_of` (backward/PIT only); no forward information can enter."""
    instrument_id = decision.instrument_id
    day_start = session_day_start(as_of, tzinfo)
    previous_date = latest_trading_day_on_or_before(calendar, session_date - timedelta(days=1))

    five_min = store.candles(instrument_id, Timeframe.M5, day_start, as_of)
    fifteen_min = store.candles(instrument_id, Timeframe.M15, day_start, as_of)
    latest_quote_ts = store.latest_quote_ts(instrument_id, as_of)
    session_context = session_engine.assess(
        instrument_id, as_of=as_of, exchange=cfg.market.exchange, calendar=calendar,
        sessions=cfg.market.sessions, tzinfo=tzinfo, five_min_candles=five_min,
        fifteen_min_candles=fifteen_min, latest_quote_ts=latest_quote_ts,
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
                    ), confluence_cfg.five_min_sma_period,
                ),
                fifteen_min_bullish=_direction(
                    completed_candles(
                        store.recent_candles(instrument_id, Timeframe.M15, as_of=as_of, limit=100),
                        Timeframe.M15, as_of=as_of,
                    ), confluence_cfg.fifteen_min_sma_period,
                ),
            )
    orb = opening_range_engine.assess(
        instrument_id, as_of=as_of, session_context=session_context,
        five_min_candles=five_min, calendar=calendar, tzinfo=tzinfo,
    )
    sector = store.instrument_sector(instrument_id)
    sector_index_id = sector_to_index.get(sector) if sector else None
    market_m5 = store.candles(market_benchmark_id, Timeframe.M5, day_start, as_of)
    sector_m5 = store.candles(sector_index_id, Timeframe.M5, day_start, as_of) if sector_index_id else []
    rs = rs_engine.assess(
        instrument_id, as_of=as_of, session_context=session_context, sector=sector,
        market_benchmark_id=market_benchmark_id, sector_benchmark_id=sector_index_id,
        stock_five_min_candles=five_min, market_five_min_candles=market_m5,
        sector_five_min_candles=sector_m5, calendar=calendar, tzinfo=tzinfo,
    )
    current_d1 = store.d1_candle_on(instrument_id, session_date)
    previous_d1 = store.d1_candle_on(instrument_id, previous_date) if previous_date is not None else None
    gap = gap_engine.assess(
        instrument_id, as_of=as_of, session_date=session_date, previous_session_date=previous_date,
        previous_session_close=previous_d1.close if previous_d1 else None,
        current_session_open=current_d1.open if current_d1 else None,
    )
    rvol = rvol_engine.assess(
        instrument_id, as_of=as_of, session_context=session_context,
        five_min_candles=store.wide_m5(instrument_id, as_of), calendar=calendar, tzinfo=tzinfo,
    )
    signal_set = intraday_engine.assess(
        instrument_id, as_of=as_of, session_date=session_date, session_context=session_context,
        vwap=vwap_result, confluence=confluence,
        five_min_sma_period=scoring_cfg.confluence.five_min_sma_period,
        fifteen_min_sma_period=scoring_cfg.confluence.fifteen_min_sma_period,
        or15=orb[OpeningRangeWindow.OR15], or30=orb[OpeningRangeWindow.OR30],
        relative_strength=rs, gap=gap, relative_volume=rvol,
    )
    evidence_finality = resolve_evidence_finality(decision, session_context)
    eq = eq_engine.evaluate(
        decision=decision, session_context=session_context, signal_set=signal_set,
        evidence_finality=evidence_finality, policy=eq_policy,
    )
    checkpoint_vwap = (
        vwap_result.values["vwap"]
        if vwap_result is not None and vwap_result.status is IndicatorStatus.OK else None
    )
    return eq, signal_set, checkpoint_vwap, orb[OpeningRangeWindow.OR15]


# --------------------------------------------------------------------------- #
# PHASE B -- forward outcome analysis (never used to select Phase-A population)
# --------------------------------------------------------------------------- #


def forward_candles(
    store: ReadOnlyStore, *, instrument_id: str, session_date: str, after_ts_open: str,
) -> list[tuple[str, Decimal, Decimal, Decimal]]:
    """Every M5 candle strictly after ``after_ts_open``, same session, same
    instrument. Direct SQL date/timestamp filter only -- never a
    row-count LIMIT, so a forward window can never silently extend past
    the session (mirrors ID-7B.1's own leak-safe §17 pattern). Deliberately
    isolated in this one function, imported by nothing in the PHASE A
    section above (proven by a dedicated source-scan test)."""
    rows = store.conn.execute(
        "SELECT ts_open, high, low, close FROM candles WHERE instrument_id=? AND timeframe='5m' "
        "AND substr(ts_open,1,10)=? AND ts_open>? ORDER BY ts_open ASC",
        (instrument_id, session_date, after_ts_open),
    ).fetchall()
    return [(r[0], Decimal(str(r[1])), Decimal(str(r[2])), Decimal(str(r[3]))) for r in rows]


def _vwap_at(store: ReadOnlyStore, indicator_engine: IndicatorEngine, *,
             instrument_id: str, day_start: datetime, bar_completion: datetime) -> Decimal | None:
    """Session-cumulative VWAP recomputed using every completed M5 bar from
    session start through ``bar_completion`` -- VWAP is, by its own
    frozen definition (`indicators/calculations.py`), a session-cumulative
    running indicator, never a level frozen at one instant; forward
    VWAP-loss evaluation must therefore recompute it at each subsequent
    bar, not compare against the entry checkpoint's own snapshot."""
    five_min = store.candles(instrument_id, Timeframe.M5, day_start, bar_completion)
    completed = completed_candles(five_min, Timeframe.M5, as_of=bar_completion)
    if not completed:
        return None
    result = indicator_engine.compute(IndicatorName.VWAP, completed, as_of=bar_completion)
    return result.values["vwap"] if result.status is IndicatorStatus.OK else None


def analyze_forward_outcome(
    *, store: ReadOnlyStore, indicator_engine: IndicatorEngine, instrument_id: str,
    session_date: str, entry_ts_open: str, entry_price: Decimal, direction: str,
    checkpoint_vwap: Decimal | None, tzinfo: ZoneInfo,
) -> dict[str, Any] | None:
    """PHASE B. Returns None only if zero forward candles exist at all
    (INSUFFICIENT_FORWARD_DATA) -- every other case returns a full result
    dict, never silently dropped."""
    forward = forward_candles(
        store, instrument_id=instrument_id, session_date=session_date, after_ts_open=entry_ts_open,
    )
    if not forward:
        return None

    is_short = direction == "SHORT"
    day_start = datetime.fromisoformat(entry_ts_open).replace(hour=0, minute=0, second=0, microsecond=0)

    if is_short:
        t1_level, t2_level = entry_price * (1 - T1_PCT), entry_price * (1 - T2_PCT)
    else:
        t1_level, t2_level = entry_price * (1 + T1_PCT), entry_price * (1 + T2_PCT)

    mfe = mae = Decimal("0")
    t1_intrabar = t1_close = t2_intrabar = t2_close = None
    vwap_loss_ts = None
    valid_geometry = (
        checkpoint_vwap is not None
        and ((not is_short and checkpoint_vwap < entry_price) or (is_short and checkpoint_vwap > entry_price))
    )
    risk_distance_pct = (
        abs(entry_price - checkpoint_vwap) / entry_price
        if checkpoint_vwap is not None and entry_price != 0 else None
    )

    for ts_open, high, low, close in forward:
        bar_completion = datetime.fromisoformat(ts_open) + timedelta(minutes=5)
        elapsed_min = (bar_completion - (datetime.fromisoformat(entry_ts_open) + timedelta(minutes=5))).total_seconds() / 60.0

        if is_short:
            mfe = max(mfe, (entry_price - low) / entry_price)
            mae = max(mae, (high - entry_price) / entry_price)
            t1_hit_intrabar, t2_hit_intrabar = low <= t1_level, low <= t2_level
            t1_hit_close, t2_hit_close = close <= t1_level, close <= t2_level
        else:
            mfe = max(mfe, (high - entry_price) / entry_price)
            mae = max(mae, (entry_price - low) / entry_price)
            t1_hit_intrabar, t2_hit_intrabar = high >= t1_level, high >= t2_level
            t1_hit_close, t2_hit_close = close >= t1_level, close >= t2_level

        if t1_intrabar is None and t1_hit_intrabar:
            t1_intrabar = elapsed_min
        if t1_close is None and t1_hit_close:
            t1_close = elapsed_min
        if t2_intrabar is None and t2_hit_intrabar:
            t2_intrabar = elapsed_min
        if t2_close is None and t2_hit_close:
            t2_close = elapsed_min

        if valid_geometry and vwap_loss_ts is None:
            bar_vwap = _vwap_at(
                store, indicator_engine, instrument_id=instrument_id,
                day_start=day_start, bar_completion=bar_completion,
            )
            if bar_vwap is not None:
                lost = (close < bar_vwap) if is_short is False else (close > bar_vwap)
                if lost:
                    vwap_loss_ts = elapsed_min

    if t1_intrabar is not None and valid_geometry and vwap_loss_ts is not None:
        terminal = "TARGET_SIDE_NO_LATER_THAN_INVALIDATION" if t1_intrabar <= vwap_loss_ts else "INVALIDATION_FIRST"
    elif t1_intrabar is not None:
        terminal = "TARGET_SIDE_NO_LATER_THAN_INVALIDATION"
    elif valid_geometry and vwap_loss_ts is not None:
        terminal = "INVALIDATION_FIRST"
    else:
        terminal = "SESSION_END_NO_RESOLUTION"

    return {
        "forward_bars": len(forward), "mfe_pct": float(mfe * 100), "mae_pct": float(mae * 100),
        "t1_intrabar_min": t1_intrabar, "t1_close_min": t1_close,
        "t2_intrabar_min": t2_intrabar, "t2_close_min": t2_close,
        "valid_geometry": valid_geometry,
        "risk_distance_pct": float(risk_distance_pct * 100) if risk_distance_pct is not None else None,
        "vwap_loss_min": vwap_loss_ts, "terminal": terminal,
        "rr_to_t1": float(T1_PCT / risk_distance_pct) if valid_geometry and risk_distance_pct not in (None, Decimal(0)) else None,
        "rr_to_t2": float(T2_PCT / risk_distance_pct) if valid_geometry and risk_distance_pct not in (None, Decimal(0)) else None,
    }


def _or15_comparator(or15, direction: str) -> Decimal | None:
    """OR15-boundary as a research comparator only (ID-7B.1 §18's own
    candidate) -- never promoted, never mixed with VWAP-loss's
    close-confirmed-only ambiguity semantics (ID-8 discovery §17)."""
    if or15.formation.status is not OpeningRangeFormationStatus.COMPLETE:
        return None
    return or15.formation.low if direction != "SHORT" else or15.formation.high


# --------------------------------------------------------------------------- #
# Orchestration
# --------------------------------------------------------------------------- #


def run_full_study(
    *, db_path: Path, config_dir: Path, output_dir: Path, decision_type: str = "TRADE",
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
        for mapping in sector_mapping_cfg.mappings if mapping.index_key in instrument_by_key
    }

    store = ReadOnlyStore(db_path)
    schema_version_start = store.conn.execute("SELECT version FROM schema_version").fetchone()
    schema_version_start = int(schema_version_start[0]) if schema_version_start else None

    defects: list[ReplayDefect] = []
    unexpected: list[dict[str, Any]] = []
    observations: list[dict[str, Any]] = []

    try:
        episode_report = build_trade_episodes(store, decision_type=decision_type)
        episodes = episode_report["episodes"]
        rows_attempted = len(episodes)
        direction_counts_episodes = Counter(e["first_direction"] for e in episodes)

        qualified: list[dict[str, Any]] = []
        for ep in episodes:
            decision = _get_decision(store, ep["first_decision_id"])
            if decision is None:
                defects.append(ReplayDefect(
                    instrument_id=ep["instrument_id"], session_date=ep["session_date"],
                    decision_id=ep["first_decision_id"], kind="BINDING_MISMATCH",
                    detail="no Decision row found for episode's first checkpoint",
                ))
                continue
            as_of = datetime.fromisoformat(ep["first_ts"])
            session_date = date.fromisoformat(ep["session_date"])
            try:
                eq, signal_set, checkpoint_vwap, or15 = _reconstruct_eq_at_checkpoint(
                    store=store, decision=decision, as_of=as_of, session_date=session_date,
                    calendar=calendar, tzinfo=tzinfo, cfg=cfg, scoring_cfg=scoring_cfg,
                    indicator_engine=indicator_engine, session_engine=session_engine,
                    intraday_engine=intraday_engine, opening_range_engine=opening_range_engine,
                    rs_engine=rs_engine, rvol_engine=rvol_engine, gap_engine=gap_engine,
                    eq_engine=eq_engine, eq_policy=eq_policy,
                    market_benchmark_id=market_benchmark_id, sector_to_index=sector_to_index,
                )
            except ValueError as exc:
                defects.append(ReplayDefect(
                    instrument_id=ep["instrument_id"], session_date=ep["session_date"],
                    decision_id=ep["first_decision_id"], kind="PIT_EVIDENCE_DEFECT",
                    detail=f"{type(exc).__name__}: {exc}",
                ))
                continue
            except Exception as exc:  # noqa: BLE001 -- deliberate, mirrors ID-7F1.1's own diagnostic
                unexpected.append({
                    "instrument_id": ep["instrument_id"], "session_date": ep["session_date"],
                    "decision_id": ep["first_decision_id"], "exception_type": type(exc).__name__,
                    "detail": str(exc),
                })
                continue

            if eq.state is not EntryQualificationState.QUALIFIED:
                continue

            qualified.append({
                "instrument_id": ep["instrument_id"], "session_date": ep["session_date"],
                "decision_id": ep["first_decision_id"], "as_of": ep["first_ts"],
                "direction": decision.direction.value, "checkpoint_vwap": checkpoint_vwap,
                "or15": or15,
                "rs_pct": (
                    float(signal_set.relative_strength.stock_vs_market_pct)
                    if signal_set.relative_strength.stock_vs_market_pct is not None else None
                ),
                "rvol_ratio": (
                    float(signal_set.relative_volume.rvol_ratio)
                    if signal_set.relative_volume.rvol_ratio is not None else None
                ),
                "session_hour": as_of.hour,
            })

        # PHASE B -- forward outcome analysis, only for the frozen QUALIFIED population.
        for q in qualified:
            entry_row = store.conn.execute(
                "SELECT ts_open, close FROM candles WHERE instrument_id=? AND timeframe='5m' "
                "AND substr(ts_open,1,10)=? AND datetime(ts_open,'+5 minutes')<=datetime(?) "
                "ORDER BY ts_open DESC LIMIT 1",
                (q["instrument_id"], q["session_date"], q["as_of"]),
            ).fetchone()
            if entry_row is None:
                defects.append(ReplayDefect(
                    instrument_id=q["instrument_id"], session_date=q["session_date"],
                    decision_id=q["decision_id"], kind="PIT_EVIDENCE_DEFECT",
                    detail="no completed M5 entry candle at or before checkpoint",
                ))
                continue
            entry_ts_open, entry_close = entry_row
            entry_price = Decimal(str(entry_close))

            outcome = analyze_forward_outcome(
                store=store, indicator_engine=indicator_engine, instrument_id=q["instrument_id"],
                session_date=q["session_date"], entry_ts_open=entry_ts_open, entry_price=entry_price,
                direction=q["direction"], checkpoint_vwap=q["checkpoint_vwap"], tzinfo=tzinfo,
            )
            or15_level = _or15_comparator(q["or15"], q["direction"])
            or15_risk_pct = (
                float(abs(entry_price - or15_level) / entry_price * 100)
                if or15_level is not None and entry_price != 0 else None
            )
            record = {
                "instrument_id": q["instrument_id"], "session_date": q["session_date"],
                "decision_id": q["decision_id"], "direction": q["direction"],
                "entry_price": float(entry_price), "or15_risk_distance_pct": or15_risk_pct,
                "rs_pct": q["rs_pct"], "rvol_ratio": q["rvol_ratio"], "session_hour": q["session_hour"],
            }
            if outcome is None:
                record["terminal"] = "INSUFFICIENT_FORWARD_DATA"
            else:
                record.update(outcome)
            observations.append(record)
    finally:
        schema_version_end = store.conn.execute("SELECT version FROM schema_version").fetchone()
        schema_version_end = int(schema_version_end[0]) if schema_version_end else None
        store.close()

    return _summarize(
        episode_report=episode_report, direction_counts_episodes=direction_counts_episodes,
        qualified_count=len(qualified), observations=observations, defects=defects,
        unexpected=unexpected, rows_attempted=rows_attempted,
        db_path=db_path, schema_version_start=schema_version_start,
        schema_version_end=schema_version_end, started=started, output_dir=output_dir,
    )


def _summarize(
    *, episode_report: dict[str, Any], direction_counts_episodes: Counter,
    qualified_count: int, observations: list[dict[str, Any]], defects: list[ReplayDefect],
    unexpected: list[dict[str, Any]], rows_attempted: int, db_path: Path,
    schema_version_start: int | None, schema_version_end: int | None,
    started: float, output_dir: Path,
) -> dict[str, Any]:
    output_dir.mkdir(parents=True, exist_ok=True)
    obs_path = output_dir / "id8_observations.jsonl"
    with obs_path.open("w", encoding="utf-8") as fh:
        for o in observations:
            fh.write(json.dumps(o, sort_keys=True) + "\n")
    defects_path = output_dir / "id8_defects.jsonl"
    with defects_path.open("w", encoding="utf-8") as fh:
        for d in defects:
            fh.write(json.dumps({
                "instrument_id": d.instrument_id, "session_date": d.session_date,
                "decision_id": d.decision_id, "kind": d.kind, "detail": d.detail,
            }, sort_keys=True) + "\n")
    unexpected_path = output_dir / "id8_unexpected_exceptions.jsonl"
    with unexpected_path.open("w", encoding="utf-8") as fh:
        for u in unexpected:
            fh.write(json.dumps(u, sort_keys=True) + "\n")

    n = len(observations)
    long_obs = [o for o in observations if o["direction"] == "LONG"]

    def _quartile_t1_rate(obs: list[dict[str, Any]], key: str) -> dict[str, Any]:
        scored = [(o[key], o) for o in obs if o.get(key) is not None]
        if len(scored) < 8:
            return {"n": len(scored), "note": "insufficient support for quartile split"}
        scored.sort(key=lambda x: x[0])
        q_size = len(scored) // 4
        quartiles = [scored[i * q_size:(i + 1) * q_size if i < 3 else len(scored)] for i in range(4)]
        out = {}
        for i, qgroup in enumerate(quartiles, start=1):
            rows = [o for _, o in qgroup]
            hits = sum(1 for o in rows if o.get("t1_intrabar_min") is not None)
            out[f"Q{i}"] = {"n": len(rows), "t1_hit_rate_pct": pct(hits, len(rows))}
        return out

    session_hour_buckets: dict[str, Any] = {}
    for o in long_obs:
        h = o.get("session_hour")
        if h is None:
            continue
        bucket = f"{h:02d}h"
        session_hour_buckets.setdefault(bucket, []).append(o)
    session_hour_summary = {
        b: {"n": len(rows), "t1_hit_rate_pct": pct(sum(1 for o in rows if o.get("t1_intrabar_min") is not None), len(rows))}
        for b, rows in sorted(session_hour_buckets.items())
    }

    valid = [o for o in observations if o.get("valid_geometry")]
    mfe_vals = [o["mfe_pct"] for o in observations if "mfe_pct" in o]
    mae_vals = [o["mae_pct"] for o in observations if "mae_pct" in o]
    t1_intrabar = [o for o in observations if o.get("t1_intrabar_min") is not None]
    t1_close = [o for o in observations if o.get("t1_close_min") is not None]
    t2_intrabar = [o for o in observations if o.get("t2_intrabar_min") is not None]
    t2_close = [o for o in observations if o.get("t2_close_min") is not None]
    vwap_loss = [o for o in valid if o.get("vwap_loss_min") is not None]
    terminal_counts = Counter(o.get("terminal") for o in observations)
    risk_dist = [o["risk_distance_pct"] for o in valid if o.get("risk_distance_pct") is not None]
    rr_t1 = [o["rr_to_t1"] for o in valid if o.get("rr_to_t1") is not None]
    rr_t2 = [o["rr_to_t2"] for o in valid if o.get("rr_to_t2") is not None]
    or15_dist = [o["or15_risk_distance_pct"] for o in observations if o.get("or15_risk_distance_pct") is not None]

    defect_kind_counts = Counter(d.kind for d in defects)
    observations_with_defects = len({(d.instrument_id, d.session_date, d.decision_id) for d in defects})

    summary: dict[str, Any] = {
        "metadata": {
            "milestone": "ID-8-FULL", "source_db_path": str(db_path),
            "schema_version_observed_at_start": schema_version_start,
            "schema_version_observed_at_end": schema_version_end,
            "schema_version_unchanged": schema_version_start == schema_version_end,
            "read_only": "SQLite URI mode=ro with PRAGMA query_only=ON; zero writes; zero provider calls",
            "runtime_seconds": round(time.perf_counter() - started, 3),
        },
        "episode_accounting": {
            "total_trade_decisions": episode_report["total_decisions"],
            "total_episodes": episode_report["total_episodes"],
            "accounted_rows": episode_report["accounted_rows"],
            "reconciles": episode_report["reconciles"],
            "direction_distribution_episodes": dict(direction_counts_episodes),
        },
        "rows_attempted": rows_attempted,
        "qualified_population": qualified_count,
        "observations_reconstructed": n,
        "observations_with_defects": observations_with_defects,
        "defect_counts": {"total": len(defects), "by_kind": dict(sorted(defect_kind_counts.items()))},
        "unexpected_exceptions": {"total": len(unexpected)},
        "mfe_distribution_pct": _distribution(mfe_vals),
        "mae_distribution_pct": _distribution(mae_vals),
        "t1_intrabar_reachability": {"n": n, "hit": len(t1_intrabar), "rate_pct": pct(len(t1_intrabar), n),
                                      "time_to_hit_min": _distribution([o["t1_intrabar_min"] for o in t1_intrabar])},
        "t1_close_confirmed_reachability": {"n": n, "hit": len(t1_close), "rate_pct": pct(len(t1_close), n),
                                             "time_to_hit_min": _distribution([o["t1_close_min"] for o in t1_close])},
        "t2_intrabar_reachability": {"n": n, "hit": len(t2_intrabar), "rate_pct": pct(len(t2_intrabar), n),
                                      "time_to_hit_min": _distribution([o["t2_intrabar_min"] for o in t2_intrabar])},
        "t2_close_confirmed_reachability": {"n": n, "hit": len(t2_close), "rate_pct": pct(len(t2_close), n),
                                             "time_to_hit_min": _distribution([o["t2_close_min"] for o in t2_close])},
        "initial_risk_geometry": {"n": n, "valid": len(valid), "valid_rate_pct": pct(len(valid), n),
                                   "risk_distance_pct_distribution": _distribution(risk_dist)},
        "vwap_loss": {"valid_geometry_n": len(valid), "event_n": len(vwap_loss),
                      "event_rate_pct": pct(len(vwap_loss), len(valid)),
                      "time_to_loss_min": _distribution([o["vwap_loss_min"] for o in vwap_loss])},
        "terminal_ordering": {k: {"count": v, "pct": pct(v, n)} for k, v in sorted(terminal_counts.items()) if k},
        "rr_to_t1_distribution": _distribution(rr_t1),
        "rr_to_t2_distribution": _distribution(rr_t2),
        "or15_comparator": {"available_n": len(or15_dist), "risk_distance_pct_distribution": _distribution(or15_dist)},
        "direction_distribution_observations": dict(Counter(o["direction"] for o in observations)),
        "rs_quartile_vs_t1_rate_LONG": _quartile_t1_rate(long_obs, "rs_pct"),
        "rvol_quartile_vs_t1_rate_LONG": _quartile_t1_rate(long_obs, "rvol_ratio"),
        "risk_distance_quartile_vs_t1_rate_LONG": _quartile_t1_rate(
            [o for o in long_obs if o.get("valid_geometry")], "risk_distance_pct"
        ),
        "session_hour_vs_t1_rate_LONG": session_hour_summary,
    }
    summary_path = output_dir / "id8_summary.json"
    summary["artifacts"] = {
        "summary_path": str(summary_path), "observations_path": str(obs_path),
        "defects_path": str(defects_path), "unexpected_exceptions_path": str(unexpected_path),
    }
    summary_path.write_text(json.dumps(summary, indent=2, sort_keys=True, default=str) + "\n", encoding="utf-8")
    return summary
