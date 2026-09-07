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
        observation's checkpoint, bounded above by the CANONICAL trading
        session close (`CalendarEngine.context_for` +
        `session_open_close_ts`) -- never a same-date-only filter alone.
        Never used to select or filter the Phase-A population.

LONG and SHORT are never pooled anywhere in this module's own summary
output: `_summarize` produces `primary_LONG` and `replayed_SHORT_diagnostic`
as two entirely independent blocks (§54/owner correction, 2026-09-07) --
`LONG_VALIDATED_SHORT_UNVALIDATED` means only the LONG block is ever
used as V0 methodology evidence; SHORT is diagnostic only.

Forward VWAP-loss uses the evolving, session-cumulative VWAP recomputed
at every subsequent completed M5 bar -- not a level frozen at the entry
checkpoint. This is not inferred merely from VWAP being a generically
cumulative indicator; it is grounded in the frozen methodology's own
exact text: `docs/research/ID-7B-ENTRY-RISK-METHODOLOGY.md` (Owner-
accepted, 2026-09-04) lines 303-304 define the primary invalidation as
"price closes back through **session VWAP** ... on a completed M5 bar"
-- "session VWAP" is the same term used throughout this codebase
exclusively for the evolving, session-cumulative indicator (never for a
value frozen at one instant); no frozen source anywhere describes a
"checkpoint VWAP" or "VWAP level recorded at entry" concept for forward
invalidation. This is an unambiguous case per the discovery contract's
own §9 fallback ("If the semantics are unambiguous, proceed without
asking").

Terminal ordering (`TARGET_SIDE_NO_LATER_THAN_INVALIDATION`/
`INVALIDATION_FIRST`/`SESSION_END_NO_RESOLUTION`) is only ever assigned
when the observation's initial VWAP risk geometry is valid -- an invalid-
geometry observation can never contribute a VWAP-vs-target ordering
claim (there is no valid VWAP invalidation to order against), and is
instead tracked via a separate `valid_geometry` coverage field.

This is RAW_PRICE_PATH_VALIDATION only -- no execution cost data exists
anywhere in the schema (confirmed by the ID-8 discovery milestone), so
no profitability claim is made or implied anywhere in this module.
"""

from __future__ import annotations

import json
import random
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
from athena.regime.engine import RegimeEngine
from athena.scoring import ConfluenceInputs
from athena.session import (
    SessionContextEngine,
    completed_candles,
    latest_completed_candle,
    session_day_start,
    session_open_close_ts,
)

T1_PCT = Decimal("0.01")
T2_PCT = Decimal("0.015")
#: Reused verbatim from ID-7B.1's own explicit choice -- "1x, descriptive
#: only", never a proposed stop multiplier. Not re-derived or re-fit here.
D1_ATR_MULTIPLE = Decimal("1")
#: Fixed seed for the session-block bootstrap (§11) -- deterministic,
#: reproducible, never re-rolled to "improve" an interval.
BOOTSTRAP_SEED = 20260907
BOOTSTRAP_RESAMPLES = 2000

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
    daily_indicators = indicator_engine.compute_all([IndicatorName.SMA, IndicatorName.ATR], daily, as_of=as_of)
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
    daily_atr = daily_indicators.get(IndicatorName.ATR)
    atr_value = (
        daily_atr.values["value"]
        if daily_atr is not None and daily_atr.status is IndicatorStatus.OK else None
    )
    return eq, signal_set, checkpoint_vwap, orb[OpeningRangeWindow.OR15], atr_value


def _reconstruct_regime_at_checkpoint(
    store: ReadOnlyStore, regime_engine: RegimeEngine, *, market_benchmark_id: str, as_of: datetime,
) -> str | None:
    """PIT regime reconstruction reusing the real, unmodified, deterministic
    `RegimeEngine` -- no new methodology. Index D1 candles bounded `<=as_of`;
    the latest `market_snapshots` row at-or-before `as_of` (VIX-based
    volatility input), or `None` if none exists yet at that checkpoint
    (the engine itself reports `*_UNKNOWN` rather than failing)."""
    index_candles = store.recent_candles(market_benchmark_id, Timeframe.D1, as_of=as_of, limit=500)
    snap_row = store.conn.execute(
        "SELECT payload_json FROM market_snapshots WHERE ts<=? ORDER BY ts DESC LIMIT 1",
        (as_of.isoformat(),),
    ).fetchone()
    snapshot = ser.payload_to_snapshot(snap_row[0]) if snap_row is not None else None
    result = regime_engine.assess(market_benchmark_id, index_candles, snapshot, as_of=as_of)
    return result.assessment.labels[0] if result.assessment.labels else None


# --------------------------------------------------------------------------- #
# PHASE B -- forward outcome analysis (never used to select Phase-A population)
# --------------------------------------------------------------------------- #


def forward_candles(
    store: ReadOnlyStore, *, instrument_id: str, session_date: str, after_ts_open: str,
    session_close_ts: datetime | None,
) -> list[tuple[str, Decimal, Decimal, Decimal]]:
    """Every M5 candle strictly after ``after_ts_open``, same session, same
    instrument, whose own completion instant (`ts_open + 5min`) is at or
    before the CANONICAL trading session close -- never a same-date-only
    filter alone (a same-date filter cannot exclude a genuine after-hours
    row that happens to share the calendar date). The lower bound is a
    direct SQL date/timestamp filter (never a row-count `LIMIT`, mirroring
    ID-7B.1's own leak-safe §17 pattern); the upper bound is enforced in
    plain Python `datetime` arithmetic against `session_close_ts` (passed
    in by the caller via `CalendarEngine.context_for` +
    `session_open_close_ts`) rather than SQLite's own date functions, to
    avoid any dependence on SQLite's timezone-offset parsing behavior.
    Deliberately isolated in this one function, imported by nothing in the
    PHASE A section above (proven by a dedicated source-scan test)."""
    rows = store.conn.execute(
        "SELECT ts_open, high, low, close FROM candles WHERE instrument_id=? AND timeframe='5m' "
        "AND substr(ts_open,1,10)=? AND ts_open>? ORDER BY ts_open ASC",
        (instrument_id, session_date, after_ts_open),
    ).fetchall()
    out: list[tuple[str, Decimal, Decimal, Decimal]] = []
    for ts_open, high, low, close in rows:
        if session_close_ts is not None:
            bar_completion = datetime.fromisoformat(ts_open) + timedelta(minutes=5)
            if bar_completion > session_close_ts:
                continue
        out.append((ts_open, Decimal(str(high)), Decimal(str(low)), Decimal(str(close))))
    return out


def _vwap_at(store: ReadOnlyStore, indicator_engine: IndicatorEngine, *,
             instrument_id: str, day_start: datetime, bar_completion: datetime) -> Decimal | None:
    """Session-cumulative VWAP recomputed using every completed M5 bar from
    session start through ``bar_completion`` -- VWAP is, by its own
    frozen definition (`indicators/calculations.py`) and by the frozen
    methodology's own exact wording ("closes back through session VWAP",
    `ID-7B-ENTRY-RISK-METHODOLOGY.md:303-304`), a session-cumulative
    running indicator, never a level frozen at one instant."""
    five_min = store.candles(instrument_id, Timeframe.M5, day_start, bar_completion)
    completed = completed_candles(five_min, Timeframe.M5, as_of=bar_completion)
    if not completed:
        return None
    result = indicator_engine.compute(IndicatorName.VWAP, completed, as_of=bar_completion)
    return result.values["vwap"] if result.status is IndicatorStatus.OK else None


def _or15_level(or15, direction: str) -> Decimal | None:
    """OR15-boundary level -- a research comparator only (ID-7B.1 §18's
    own candidate), range low for LONG / range high for SHORT, matching
    ID-7C's own established directional convention. `None` when the
    range has not `COMPLETE`d."""
    if or15.formation.status is not OpeningRangeFormationStatus.COMPLETE:
        return None
    return or15.formation.low if direction != "SHORT" else or15.formation.high


def _d1_atr_level(atr_value: Decimal | None, entry_price: Decimal, direction: str) -> Decimal | None:
    """D1 ATR(1x) static level -- ID-7B.1's own explicit descriptive
    comparator, never a proposed stop multiplier. LONG risk below entry,
    SHORT above, matching the same convention as VWAP/OR15."""
    if atr_value is None:
        return None
    offset = atr_value * D1_ATR_MULTIPLE
    return entry_price - offset if direction != "SHORT" else entry_price + offset


def analyze_forward_outcome(
    *, store: ReadOnlyStore, indicator_engine: IndicatorEngine, instrument_id: str,
    session_date: str, entry_ts_open: str, entry_price: Decimal, direction: str,
    checkpoint_vwap: Decimal | None, or15_lvl: Decimal | None, atr_lvl: Decimal | None,
    session_close_ts: datetime | None,
) -> dict[str, Any] | None:
    """PHASE B. Returns None only if zero forward candles exist at all
    (INSUFFICIENT_FORWARD_DATA) -- every other case returns a full result
    dict, never silently dropped. Terminal ordering
    (`TARGET_SIDE_NO_LATER_THAN_INVALIDATION`/`INVALIDATION_FIRST`/
    `SESSION_END_NO_RESOLUTION`) is only ever populated when
    `valid_geometry` is True -- an invalid-geometry observation can never
    contribute a VWAP-vs-target ordering claim and reports `terminal=None`."""
    forward = forward_candles(
        store, instrument_id=instrument_id, session_date=session_date,
        after_ts_open=entry_ts_open, session_close_ts=session_close_ts,
    )
    if not forward:
        return None

    is_short = direction == "SHORT"
    day_start = datetime.fromisoformat(entry_ts_open).replace(hour=0, minute=0, second=0, microsecond=0)
    entry_completion = datetime.fromisoformat(entry_ts_open) + timedelta(minutes=5)

    if is_short:
        t1_level, t2_level = entry_price * (1 - T1_PCT), entry_price * (1 - T2_PCT)
    else:
        t1_level, t2_level = entry_price * (1 + T1_PCT), entry_price * (1 + T2_PCT)

    mfe = mae = Decimal("0")
    t1_intrabar = t1_close = t2_intrabar = t2_close = None
    mae_before_t1 = mae_before_t2 = None
    running_mae_before_t1 = running_mae_before_t2 = Decimal("0")

    valid_geometry = (
        checkpoint_vwap is not None
        and ((not is_short and checkpoint_vwap < entry_price) or (is_short and checkpoint_vwap > entry_price))
    )
    risk_distance_pct = (
        abs(entry_price - checkpoint_vwap) / entry_price
        if checkpoint_vwap is not None and entry_price != 0 else None
    )

    vwap_loss_min: float | None = None
    mfe_before_vwap_loss: float | None = None
    running_mfe_before_loss = Decimal("0")

    or15_intrabar_min: float | None = None
    or15_ambiguous_with_t1 = False
    atr_close_min: float | None = None

    for ts_open, high, low, close in forward:
        bar_completion = datetime.fromisoformat(ts_open) + timedelta(minutes=5)
        elapsed_min = (bar_completion - entry_completion).total_seconds() / 60.0

        if is_short:
            fav = (entry_price - low) / entry_price
            adv = (high - entry_price) / entry_price
            t1_hit_i, t2_hit_i = low <= t1_level, low <= t2_level
            t1_hit_c, t2_hit_c = close <= t1_level, close <= t2_level
        else:
            fav = (high - entry_price) / entry_price
            adv = (entry_price - low) / entry_price
            t1_hit_i, t2_hit_i = high >= t1_level, high >= t2_level
            t1_hit_c, t2_hit_c = close >= t1_level, close >= t2_level

        mfe, mae = max(mfe, fav), max(mae, adv)

        if t1_intrabar is None:
            running_mae_before_t1 = max(running_mae_before_t1, adv)
        if t2_intrabar is None:
            running_mae_before_t2 = max(running_mae_before_t2, adv)

        if t1_intrabar is None and t1_hit_i:
            t1_intrabar = elapsed_min
            mae_before_t1 = float(running_mae_before_t1 * 100)
        if t1_close is None and t1_hit_c:
            t1_close = elapsed_min
        if t2_intrabar is None and t2_hit_i:
            t2_intrabar = elapsed_min
            mae_before_t2 = float(running_mae_before_t2 * 100)
        if t2_close is None and t2_hit_c:
            t2_close = elapsed_min

        if valid_geometry and vwap_loss_min is None:
            running_mfe_before_loss = max(running_mfe_before_loss, fav)
            bar_vwap = _vwap_at(
                store, indicator_engine, instrument_id=instrument_id,
                day_start=day_start, bar_completion=bar_completion,
            )
            if bar_vwap is not None:
                lost = (close < bar_vwap) if not is_short else (close > bar_vwap)
                if lost:
                    vwap_loss_min = elapsed_min
                    mfe_before_vwap_loss = float(running_mfe_before_loss * 100)

        if or15_lvl is not None and or15_intrabar_min is None:
            or15_hit = (low <= or15_lvl) if not is_short else (high >= or15_lvl)
            if or15_hit:
                or15_intrabar_min = elapsed_min
                if t1_intrabar == elapsed_min:
                    or15_ambiguous_with_t1 = True

        if atr_lvl is not None and atr_close_min is None:
            atr_hit = (close <= atr_lvl) if not is_short else (close >= atr_lvl)
            if atr_hit:
                atr_close_min = elapsed_min

    if valid_geometry:
        if t1_intrabar is not None and vwap_loss_min is not None:
            terminal = "TARGET_SIDE_NO_LATER_THAN_INVALIDATION" if t1_intrabar <= vwap_loss_min else "INVALIDATION_FIRST"
        elif t1_intrabar is not None:
            terminal = "TARGET_SIDE_NO_LATER_THAN_INVALIDATION"
        elif vwap_loss_min is not None:
            terminal = "INVALIDATION_FIRST"
        else:
            terminal = "SESSION_END_NO_RESOLUTION"
    else:
        terminal = None  # not applicable: no valid VWAP invalidation to order against

    return {
        "forward_bars": len(forward), "mfe_pct": float(mfe * 100), "mae_pct": float(mae * 100),
        "t1_intrabar_min": t1_intrabar, "t1_close_min": t1_close,
        "t2_intrabar_min": t2_intrabar, "t2_close_min": t2_close,
        "mae_before_t1_pct": mae_before_t1, "mae_before_t2_pct": mae_before_t2,
        "valid_geometry": valid_geometry,
        "risk_distance_pct": float(risk_distance_pct * 100) if risk_distance_pct is not None else None,
        "vwap_loss_min": vwap_loss_min, "mfe_before_vwap_loss_pct": mfe_before_vwap_loss,
        "terminal": terminal,
        "rr_to_t1": float(T1_PCT / risk_distance_pct) if valid_geometry and risk_distance_pct not in (None, Decimal(0)) else None,
        "rr_to_t2": float(T2_PCT / risk_distance_pct) if valid_geometry and risk_distance_pct not in (None, Decimal(0)) else None,
        "or15_intrabar_min": or15_intrabar_min, "or15_ambiguous_with_t1": or15_ambiguous_with_t1,
        "atr_close_min": atr_close_min,
    }


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
    regime_engine = RegimeEngine(cfg.regime)

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
    session_close_cache: dict[str, datetime | None] = {}

    def _session_close(session_date: date) -> datetime | None:
        key = session_date.isoformat()
        if key not in session_close_cache:
            ctx = calendar.context_for(session_date)
            _open_ts, close_ts = session_open_close_ts(ctx, session_date=session_date, tzinfo=tzinfo)
            session_close_cache[key] = close_ts
        return session_close_cache[key]

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
                eq, signal_set, checkpoint_vwap, or15, atr_value = _reconstruct_eq_at_checkpoint(
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

            regime_label = _reconstruct_regime_at_checkpoint(
                store, regime_engine, market_benchmark_id=market_benchmark_id, as_of=as_of,
            )

            qualified.append({
                "instrument_id": ep["instrument_id"], "session_date": ep["session_date"],
                "decision_id": ep["first_decision_id"], "as_of": ep["first_ts"],
                "direction": decision.direction.value, "checkpoint_vwap": checkpoint_vwap,
                "or15": or15, "atr_value": atr_value,
                "rs_pct": (
                    float(signal_set.relative_strength.stock_vs_market_pct)
                    if signal_set.relative_strength.stock_vs_market_pct is not None else None
                ),
                "rvol_ratio": (
                    float(signal_set.relative_volume.rvol_ratio)
                    if signal_set.relative_volume.rvol_ratio is not None else None
                ),
                "session_hour": as_of.hour, "regime": regime_label,
            })

        # PHASE B -- forward outcome analysis, only for the frozen QUALIFIED population.
        for q in qualified:
            session_date_obj = date.fromisoformat(q["session_date"])
            five_min_entry_window = store.candles(
                q["instrument_id"], Timeframe.M5,
                session_day_start(datetime.fromisoformat(q["as_of"]), tzinfo),
                datetime.fromisoformat(q["as_of"]),
            )
            entry_candle = latest_completed_candle(
                five_min_entry_window, Timeframe.M5, as_of=datetime.fromisoformat(q["as_of"]),
            )
            if entry_candle is None:
                defects.append(ReplayDefect(
                    instrument_id=q["instrument_id"], session_date=q["session_date"],
                    decision_id=q["decision_id"], kind="PIT_EVIDENCE_DEFECT",
                    detail="no completed M5 entry candle at or before checkpoint (canonical helper)",
                ))
                continue
            entry_ts_open = entry_candle.ts_open.isoformat()
            entry_price = entry_candle.close

            close_ts = _session_close(session_date_obj)
            or15_lvl = _or15_level(q["or15"], q["direction"])
            atr_lvl = _d1_atr_level(q["atr_value"], entry_price, q["direction"])

            outcome = analyze_forward_outcome(
                store=store, indicator_engine=indicator_engine, instrument_id=q["instrument_id"],
                session_date=q["session_date"], entry_ts_open=entry_ts_open, entry_price=entry_price,
                direction=q["direction"], checkpoint_vwap=q["checkpoint_vwap"],
                or15_lvl=or15_lvl, atr_lvl=atr_lvl, session_close_ts=close_ts,
            )
            or15_risk_pct = (
                float(abs(entry_price - or15_lvl) / entry_price * 100)
                if or15_lvl is not None and entry_price != 0 else None
            )
            record = {
                "instrument_id": q["instrument_id"], "session_date": q["session_date"],
                "decision_id": q["decision_id"], "direction": q["direction"],
                "entry_price": float(entry_price), "or15_risk_distance_pct": or15_risk_pct,
                "rs_pct": q["rs_pct"], "rvol_ratio": q["rvol_ratio"], "session_hour": q["session_hour"],
                "regime": q["regime"],
            }
            if outcome is None:
                record["terminal"] = "INSUFFICIENT_FORWARD_DATA"
                record["valid_geometry"] = None
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


# --------------------------------------------------------------------------- #
# Summary -- LONG and SHORT are NEVER pooled (owner correction, 2026-09-07)
# --------------------------------------------------------------------------- #


def _rate(rows: list[dict[str, Any]], key: str) -> float:
    if not rows:
        return 0.0
    return pct(sum(1 for o in rows if o.get(key) is not None), len(rows))


def _session_block_bootstrap(
    obs: list[dict[str, Any]], *, metric_fn, seed: int = BOOTSTRAP_SEED,
    resamples: int = BOOTSTRAP_RESAMPLES,
) -> dict[str, Any]:
    """Deterministic, fixed-seed session-block bootstrap: resamples WHOLE
    SESSIONS with replacement (never individual observations), so
    within-session correlation is respected rather than assumed away.
    Evidence characterization only -- never an acceptance threshold."""
    by_session: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for o in obs:
        by_session[o["session_date"]].append(o)
    sessions = sorted(by_session.keys())
    if len(sessions) < 3:
        return {
            "method": "session_block_bootstrap", "sessions": len(sessions),
            "note": "too few distinct sessions for a meaningful interval",
        }
    rng = random.Random(seed)
    stats: list[float] = []
    for _ in range(resamples):
        chosen = [rng.choice(sessions) for _ in sessions]
        pooled: list[dict[str, Any]] = []
        for s in chosen:
            pooled.extend(by_session[s])
        if pooled:
            stats.append(metric_fn(pooled))
    stats.sort()
    return {
        "method": "session_block_bootstrap", "sessions": len(sessions),
        "resamples": resamples, "seed": seed,
        "point_estimate": metric_fn(obs),
        "ci_90_low": _percentile(stats, 0.05), "ci_90_high": _percentile(stats, 0.95),
    }


def _chronological_stability(obs: list[dict[str, Any]]) -> dict[str, Any]:
    """Descriptive-only first-half vs. second-half split of the ordered
    available sessions (no threshold optimization, no fitting) -- answers
    whether headline findings are concentrated in a few sessions."""
    sessions = sorted({o["session_date"] for o in obs})
    if len(sessions) < 4:
        return {"note": "too few sessions for a meaningful split", "sessions": len(sessions)}
    mid = len(sessions) // 2
    first_half, second_half = set(sessions[:mid]), set(sessions[mid:])
    first_obs = [o for o in obs if o["session_date"] in first_half]
    second_obs = [o for o in obs if o["session_date"] in second_half]
    return {
        "sessions_first_half": sorted(first_half), "sessions_second_half": sorted(second_half),
        "first_half": {
            "n": len(first_obs), "t1_intrabar_rate_pct": _rate(first_obs, "t1_intrabar_min"),
            "t2_intrabar_rate_pct": _rate(first_obs, "t2_intrabar_min"),
        },
        "second_half": {
            "n": len(second_obs), "t1_intrabar_rate_pct": _rate(second_obs, "t1_intrabar_min"),
            "t2_intrabar_rate_pct": _rate(second_obs, "t2_intrabar_min"),
        },
        "per_session": {
            s: {
                "n": len([o for o in obs if o["session_date"] == s]),
                "t1_intrabar_rate_pct": _rate([o for o in obs if o["session_date"] == s], "t1_intrabar_min"),
            }
            for s in sessions
        },
    }


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
        out[f"Q{i}"] = {"n": len(rows), "t1_hit_rate_pct": _rate(rows, "t1_intrabar_min")}
    return out


def _direction_block(obs: list[dict[str, Any]]) -> dict[str, Any]:
    """One direction's complete, self-contained summary block -- N,
    MFE/MAE, T1/T2 (both semantics), geometry, VWAP-loss (validity-gated),
    terminal ordering (validity-gated, explicit denominator), RR,
    MFE/MAE-before-event, OR15 full comparator, D1-ATR comparator, context
    associations, chronological stability, and a session-block bootstrap
    for the headline rates. Never mixes another direction's rows."""
    n = len(obs)
    insufficient = [o for o in obs if o.get("terminal") == "INSUFFICIENT_FORWARD_DATA"]
    with_forward = [o for o in obs if o.get("terminal") != "INSUFFICIENT_FORWARD_DATA"]
    valid_geo = [o for o in with_forward if o.get("valid_geometry")]
    invalid_geo = [o for o in with_forward if o.get("valid_geometry") is False]
    # Terminal ordering is only ever populated (non-None) for valid-geometry
    # observations -- this IS the denominator, made explicit here.
    terminal_obs = [o for o in valid_geo if o.get("terminal") is not None]
    terminal_counts = Counter(o["terminal"] for o in terminal_obs)

    mfe_vals = [o["mfe_pct"] for o in with_forward if "mfe_pct" in o]
    mae_vals = [o["mae_pct"] for o in with_forward if "mae_pct" in o]
    t1_intrabar = [o for o in with_forward if o.get("t1_intrabar_min") is not None]
    t1_close = [o for o in with_forward if o.get("t1_close_min") is not None]
    t2_intrabar = [o for o in with_forward if o.get("t2_intrabar_min") is not None]
    t2_close = [o for o in with_forward if o.get("t2_close_min") is not None]
    vwap_loss = [o for o in valid_geo if o.get("vwap_loss_min") is not None]
    risk_dist = [o["risk_distance_pct"] for o in valid_geo if o.get("risk_distance_pct") is not None]
    rr_t1 = [o["rr_to_t1"] for o in valid_geo if o.get("rr_to_t1") is not None]
    rr_t2 = [o["rr_to_t2"] for o in valid_geo if o.get("rr_to_t2") is not None]
    mae_before_t1 = [o["mae_before_t1_pct"] for o in with_forward if o.get("mae_before_t1_pct") is not None]
    mae_before_t2 = [o["mae_before_t2_pct"] for o in with_forward if o.get("mae_before_t2_pct") is not None]
    mfe_before_loss = [o["mfe_before_vwap_loss_pct"] for o in vwap_loss if o.get("mfe_before_vwap_loss_pct") is not None]

    # OR15 full comparator (intrabar barrier -- ambiguous-with-T1-aware)
    or15_avail = [o for o in with_forward if o.get("or15_risk_distance_pct") is not None]
    or15_hits = [o for o in or15_avail if o.get("or15_intrabar_min") is not None]
    or15_ambiguous = [o for o in or15_hits if o.get("or15_ambiguous_with_t1")]
    or15_before_t1 = [
        o for o in or15_hits
        if o.get("t1_intrabar_min") is None or o["or15_intrabar_min"] < o["t1_intrabar_min"]
    ]

    # D1-ATR comparator (close-confirmed, ID-7B.1's own "1x descriptive" candidate)
    atr_avail = [o for o in with_forward]  # level always computable once ATR exists; hit-rate is the real signal
    atr_hits = [o for o in atr_avail if o.get("atr_close_min") is not None]

    def _t1_rate_fn(rows: list[dict[str, Any]]) -> float:
        wf = [o for o in rows if o.get("terminal") != "INSUFFICIENT_FORWARD_DATA"]
        return _rate(wf, "t1_intrabar_min")

    def _vwap_loss_rate_fn(rows: list[dict[str, Any]]) -> float:
        vg = [o for o in rows if o.get("valid_geometry")]
        return _rate(vg, "vwap_loss_min")

    return {
        "n": n,
        "insufficient_forward_data_n": len(insufficient),
        "forward_data_available_n": len(with_forward),
        "valid_geometry_n": len(valid_geo),
        "invalid_geometry_n": len(invalid_geo),
        "mfe_distribution_pct": _distribution(mfe_vals),
        "mae_distribution_pct": _distribution(mae_vals),
        "t1_intrabar_reachability": {
            "n": len(with_forward), "hit": len(t1_intrabar), "rate_pct": _rate(with_forward, "t1_intrabar_min"),
            "time_to_hit_min": _distribution([o["t1_intrabar_min"] for o in t1_intrabar]),
        },
        "t1_close_confirmed_reachability": {
            "n": len(with_forward), "hit": len(t1_close), "rate_pct": _rate(with_forward, "t1_close_min"),
            "time_to_hit_min": _distribution([o["t1_close_min"] for o in t1_close]),
        },
        "t2_intrabar_reachability": {
            "n": len(with_forward), "hit": len(t2_intrabar), "rate_pct": _rate(with_forward, "t2_intrabar_min"),
            "time_to_hit_min": _distribution([o["t2_intrabar_min"] for o in t2_intrabar]),
        },
        "t2_close_confirmed_reachability": {
            "n": len(with_forward), "hit": len(t2_close), "rate_pct": _rate(with_forward, "t2_close_min"),
            "time_to_hit_min": _distribution([o["t2_close_min"] for o in t2_close]),
        },
        "mae_before_t1_pct_distribution": _distribution(mae_before_t1),
        "mae_before_t2_pct_distribution": _distribution(mae_before_t2),
        "initial_risk_geometry": {
            "n": len(with_forward), "valid": len(valid_geo), "valid_rate_pct": pct(len(valid_geo), len(with_forward)),
            "risk_distance_pct_distribution": _distribution(risk_dist),
        },
        "vwap_loss": {
            "valid_geometry_n": len(valid_geo), "event_n": len(vwap_loss),
            "event_rate_pct": pct(len(vwap_loss), len(valid_geo)),
            "time_to_loss_min": _distribution([o["vwap_loss_min"] for o in vwap_loss]),
            "mfe_before_loss_pct_distribution": _distribution(mfe_before_loss),
        },
        "terminal_ordering": {
            "denominator": "valid_geometry observations with forward data",
            "denominator_n": len(terminal_obs),
            "counts": {k: {"count": v, "pct": pct(v, len(terminal_obs))} for k, v in sorted(terminal_counts.items())},
        },
        "rr_to_t1_distribution": _distribution(rr_t1),
        "rr_to_t2_distribution": _distribution(rr_t2),
        "or15_comparator": {
            "available_n": len(or15_avail),
            "risk_distance_pct_distribution": _distribution([o["or15_risk_distance_pct"] for o in or15_avail]),
            "event_n": len(or15_hits), "event_rate_pct": pct(len(or15_hits), len(or15_avail)),
            "time_to_event_min": _distribution([o["or15_intrabar_min"] for o in or15_hits]),
            "event_before_t1_n": len(or15_before_t1),
            "event_before_t1_rate_pct": pct(len(or15_before_t1), len(or15_hits)),
            "ambiguous_same_bar_with_t1_n": len(or15_ambiguous),
            "semantics": "INTRABAR_TOUCH (high/low) -- OR15 is treated as an intrabar barrier per ID-7B.1's own "
                         "fast (~9min) empirical trigger time; AMBIGUOUS_SAME_BAR applies here (two intrabar "
                         "barriers), separate from and never mixed with VWAP-loss's own close-confirmed-only semantics",
        },
        "d1_atr_comparator": {
            "multiple": "1x (ID-7B.1's own explicit descriptive choice, not re-derived)",
            "available_n": len(atr_avail), "event_n": len(atr_hits),
            "event_rate_pct": pct(len(atr_hits), len(atr_avail)),
            "time_to_event_min": _distribution([o["atr_close_min"] for o in atr_hits]),
            "semantics": "CLOSE_CONFIRMED (assumed, by analogy with VWAP-loss's own close-confirmed convention; "
                         "no frozen source specifies intrabar vs. close-confirmed for this descriptive-only "
                         "candidate) -- stated explicitly as an assumption, not a frozen contract element",
        },
        "rs_quartile_vs_t1_rate": _quartile_t1_rate(with_forward, "rs_pct"),
        "rvol_quartile_vs_t1_rate": _quartile_t1_rate(with_forward, "rvol_ratio"),
        "risk_distance_quartile_vs_t1_rate": _quartile_t1_rate(valid_geo, "risk_distance_pct"),
        "session_hour_vs_t1_rate": {
            f"{h:02d}h": {
                "n": len(rows), "t1_hit_rate_pct": _rate(rows, "t1_intrabar_min"),
            }
            for h, rows in sorted(
                {h: [o for o in with_forward if o.get("session_hour") == h] for h in {o.get("session_hour") for o in with_forward if o.get("session_hour") is not None}}.items()
            )
        },
        "regime_association": (
            {
                r: {"n": len(rows), "t1_hit_rate_pct": _rate(rows, "t1_intrabar_min")}
                for r, rows in sorted(
                    {r: [o for o in with_forward if o.get("regime") == r] for r in {o.get("regime") for o in with_forward}}.items()
                )
                if r is not None
            }
        ),
        "chronological_stability": _chronological_stability(with_forward),
        "session_block_bootstrap_t1_intrabar_rate": _session_block_bootstrap(obs, metric_fn=_t1_rate_fn),
        "session_block_bootstrap_vwap_loss_rate": _session_block_bootstrap(obs, metric_fn=_vwap_loss_rate_fn),
    }


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

    long_obs = [o for o in observations if o["direction"] == "LONG"]
    short_obs = [o for o in observations if o["direction"] == "SHORT"]

    # LONG-only episode reconciliation (owner correction #2) -- computed
    # directly from the LONG-only subset of episodes, never from a
    # combined LONG+SHORT mean/count, so it can be compared like-for-like
    # against ID-7B.1's own LONG-only published figures.
    long_episodes = [e for e in episode_report["episodes"] if e["first_direction"] == "LONG"]
    long_episode_lengths = [e["episode_length"] for e in long_episodes]
    long_episode_accounting = {
        "long_trade_decisions": sum(long_episode_lengths),
        "long_episodes": len(long_episodes),
        "long_mean_episode_length": (
            round(sum(long_episode_lengths) / len(long_episode_lengths), 2) if long_episode_lengths else None
        ),
        "long_max_episode_length": max(long_episode_lengths) if long_episode_lengths else None,
    }
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
            "vwap_loss_semantics": "EVOLVING session-cumulative VWAP recomputed at every subsequent completed "
                                    "M5 bar, per ID-7B-ENTRY-RISK-METHODOLOGY.md:303-304's own exact text "
                                    "('closes back through session VWAP ... on a completed M5 bar')",
            "forward_window_bound": "canonical session close via CalendarEngine.context_for + session_open_close_ts",
            "entry_selection": "canonical latest_completed_candle/completed_candles helpers (session module)",
        },
        "episode_accounting": {
            "total_trade_decisions": episode_report["total_decisions"],
            "total_episodes": episode_report["total_episodes"],
            "accounted_rows": episode_report["accounted_rows"],
            "reconciles": episode_report["reconciles"],
            "direction_distribution_episodes": dict(direction_counts_episodes),
            **long_episode_accounting,
        },
        "rows_attempted": rows_attempted,
        "qualified_population": qualified_count,
        "observations_reconstructed": len(observations),
        "observations_with_defects": observations_with_defects,
        "defect_counts": {"total": len(defects), "by_kind": dict(sorted(defect_kind_counts.items()))},
        "unexpected_exceptions": {"total": len(unexpected)},
        "direction_distribution_observations": dict(Counter(o["direction"] for o in observations)),
        # LONG and SHORT are NEVER combined below this point.
        "primary_LONG": _direction_block(long_obs),
        "replayed_SHORT_diagnostic": _direction_block(short_obs) if short_obs else {"n": 0, "note": "no SHORT episode-replay observations this run"},
    }
    summary_path = output_dir / "id8_summary.json"
    summary["artifacts"] = {
        "summary_path": str(summary_path), "observations_path": str(obs_path),
        "defects_path": str(defects_path), "unexpected_exceptions_path": str(unexpected_path),
    }
    summary_path.write_text(json.dumps(summary, indent=2, sort_keys=True, default=str) + "\n", encoding="utf-8")
    return summary
