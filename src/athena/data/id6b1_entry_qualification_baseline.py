"""ID-6B.1 read-only Entry Qualification evidence baseline harness.

Reconstructs existing ID evidence for historical WATCH/TRADE candidates using
production analytical engines. This is research only: no Entry Qualification
engine, no persistence, no provider calls, and no writes to ``db/athena.db``.
"""

from __future__ import annotations

import argparse
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
from athena.data.validation.calendar_expectations import latest_trading_day_on_or_before
from athena.domain.enums import DecisionType, Timeframe
from athena.domain.market import Candle
from athena.indicators import IndicatorEngine, IndicatorName, IndicatorStatus
from athena.indicators import calculations as calc
from athena.intraday import (
    GapEngine,
    IntradayAnalyticsEngine,
    OpeningRangeEngine,
    OpeningRangeWindow,
    RelativeStrengthEngine,
    RelativeStrengthRelation,
    RelativeVolumeEngine,
    RelativeVolumeRelation,
)
from athena.intraday.models import IntradayTrendLabel, VwapRelation
from athena.intraday.opening_range_models import (
    BreakoutEvent,
    OpeningRangeFormationStatus,
    OpeningRangeRelation,
)
from athena.scoring import ConfluenceInputs
from athena.session import SessionContextEngine, completed_candles, session_day_start
from athena.session.models import SessionDataQualityStatus

DEFAULT_SESSION_DATES = (
    "2026-08-26",
    "2026-08-27",
    "2026-08-28",
    "2026-08-31",
    "2026-09-01",
)
DEFAULT_CHECKPOINTS = ("09:30", "09:45", "10:00", "11:00", "13:00", "14:30")


@dataclass(frozen=True, slots=True)
class Candidate:
    instrument_id: str
    decision_id: str
    decision_type: str
    decision_ts: datetime


def pct(part: int, whole: int) -> float:
    return round((part / whole * 100.0), 2) if whole else 0.0


def phi(a: bool, b: bool, rows: list[dict[str, Any]]) -> float | None:
    n11 = sum(1 for row in rows if row[a] and row[b])
    n10 = sum(1 for row in rows if row[a] and not row[b])
    n01 = sum(1 for row in rows if not row[a] and row[b])
    n00 = sum(1 for row in rows if not row[a] and not row[b])
    denom = (n11 + n10) * (n01 + n00) * (n11 + n01) * (n10 + n00)
    if denom == 0:
        return None
    return round(((n11 * n00) - (n10 * n01)) / (denom ** 0.5), 4)


class ReadOnlyStore:
    """Tiny read-only adapter for the research harness.

    ``SqliteRepository`` opens a writable connection for normal operation, so
    this harness uses SQLite URI ``mode=ro`` plus ``PRAGMA query_only=ON``.
    """

    def __init__(self, db_path: Path) -> None:
        uri = f"file:{db_path}?mode=ro"
        self.conn = sqlite3.connect(uri, uri=True)
        self.conn.row_factory = sqlite3.Row
        self.conn.execute("PRAGMA query_only=ON")
        self._candle_cache: dict[tuple[str, str, str, str], list[Candle]] = {}
        self._recent_cache: dict[tuple[str, str, str, int], list[Candle]] = {}
        self._wide_cache: dict[tuple[str, str], list[Candle]] = {}
        self._sector_cache: dict[str, str | None] = {}

    def close(self) -> None:
        self.conn.close()

    def candidates_at(
        self, session_date: date, as_of: datetime, *, per_type: int
    ) -> list[Candidate]:
        rows = self.conn.execute(
            """
            WITH ranked AS (
                SELECT instrument_id, decision_id, decision_type, ts,
                       row_number() OVER (
                           PARTITION BY instrument_id
                           ORDER BY ts DESC, decision_id DESC
                       ) AS rn
                FROM decisions
                WHERE instrument_id IS NOT NULL
                  AND substr(ts, 1, 10)=?
                  AND ts<=?
            )
            SELECT instrument_id, decision_id, decision_type, ts
            FROM ranked
            WHERE rn=1 AND decision_type IN ('WATCH','TRADE')
            ORDER BY decision_type, instrument_id
            """,
            (session_date.isoformat(), as_of.isoformat()),
        ).fetchall()
        by_type: dict[str, list[Candidate]] = {"WATCH": [], "TRADE": []}
        for row in rows:
            dtype = str(row["decision_type"])
            if dtype in by_type and len(by_type[dtype]) < per_type:
                by_type[dtype].append(
                    Candidate(
                        instrument_id=str(row["instrument_id"]),
                        decision_id=str(row["decision_id"]),
                        decision_type=dtype,
                        decision_ts=datetime.fromisoformat(str(row["ts"])),
                    )
                )
        return by_type["WATCH"] + by_type["TRADE"]

    def candles(
        self, instrument_id: str, timeframe: Timeframe, start: datetime, end: datetime
    ) -> list[Candle]:
        key = (instrument_id, timeframe.value, start.isoformat(), end.isoformat())
        if key not in self._candle_cache:
            rows = self.conn.execute(
                """
                SELECT instrument_id, timeframe, ts_open, open, high, low, close, volume,
                       source, adjusted
                FROM candles
                WHERE instrument_id=? AND timeframe=? AND ts_open>=? AND ts_open<=?
                ORDER BY ts_open
                """,
                (instrument_id, timeframe.value, start.isoformat(), end.isoformat()),
            ).fetchall()
            self._candle_cache[key] = [self._candle(row) for row in rows]
        return list(self._candle_cache[key])

    def recent_candles(
        self, instrument_id: str, timeframe: Timeframe, *, as_of: datetime, limit: int
    ) -> list[Candle]:
        key = (instrument_id, timeframe.value, as_of.isoformat(), limit)
        if key not in self._recent_cache:
            rows = self.conn.execute(
                """
                SELECT instrument_id, timeframe, ts_open, open, high, low, close, volume,
                       source, adjusted
                FROM candles
                WHERE instrument_id=? AND timeframe=? AND ts_open<=?
                ORDER BY ts_open DESC
                LIMIT ?
                """,
                (instrument_id, timeframe.value, as_of.isoformat(), limit),
            ).fetchall()
            self._recent_cache[key] = [self._candle(row) for row in reversed(rows)]
        return list(self._recent_cache[key])

    def wide_m5(self, instrument_id: str, as_of: datetime) -> list[Candle]:
        key = (instrument_id, as_of.isoformat())
        if key not in self._wide_cache:
            rows = self.conn.execute(
                """
                SELECT instrument_id, timeframe, ts_open, open, high, low, close, volume,
                       source, adjusted
                FROM candles
                WHERE instrument_id=? AND timeframe='5m' AND ts_open<=?
                ORDER BY ts_open
                """,
                (instrument_id, as_of.isoformat()),
            ).fetchall()
            self._wide_cache[key] = [self._candle(row) for row in rows]
        return list(self._wide_cache[key])

    def latest_quote_ts(self, instrument_id: str, as_of: datetime) -> datetime | None:
        row = self.conn.execute(
            """
            SELECT ts FROM quotes
            WHERE instrument_id=? AND ts<=?
            ORDER BY ts DESC
            LIMIT 1
            """,
            (instrument_id, as_of.isoformat()),
        ).fetchone()
        return datetime.fromisoformat(str(row["ts"])) if row else None

    def instrument_sector(self, instrument_id: str) -> str | None:
        if instrument_id not in self._sector_cache:
            row = self.conn.execute(
                "SELECT sector FROM instruments WHERE instrument_id=?",
                (instrument_id,),
            ).fetchone()
            self._sector_cache[instrument_id] = (
                str(row["sector"]) if row and row["sector"] else None
            )
        return self._sector_cache[instrument_id]

    def d1_candle_on(self, instrument_id: str, session_date: date) -> Candle | None:
        rows = self.conn.execute(
            """
            SELECT instrument_id, timeframe, ts_open, open, high, low, close, volume,
                   source, adjusted
            FROM candles
            WHERE instrument_id=? AND timeframe='1d' AND substr(ts_open, 1, 10)=?
            ORDER BY ts_open DESC
            LIMIT 1
            """,
            (instrument_id, session_date.isoformat()),
        ).fetchall()
        return self._candle(rows[0]) if rows else None

    @staticmethod
    def _candle(row: sqlite3.Row) -> Candle:
        return Candle(
            instrument_id=str(row["instrument_id"]),
            timeframe=Timeframe(str(row["timeframe"])),
            ts_open=datetime.fromisoformat(str(row["ts_open"])),
            open=Decimal(str(row["open"])),
            high=Decimal(str(row["high"])),
            low=Decimal(str(row["low"])),
            close=Decimal(str(row["close"])),
            volume=int(row["volume"]),
            source=str(row["source"]),
            adjusted=bool(row["adjusted"]),
        )


def _direction(candles: list[Candle], period: int) -> bool | None:
    if not candles:
        return None
    closes = [c.close for c in candles]
    sma_val = calc.sma(closes, period)
    if sma_val is None:
        return None
    return closes[-1] >= sma_val


def _counter_payload(counter: Counter[str], total: int) -> dict[str, dict[str, float | int]]:
    return {
        key: {"count": value, "pct": pct(value, total)}
        for key, value in sorted(counter.items())
    }


def _bool_rate(rows: list[dict[str, Any]], key: str) -> dict[str, float | int]:
    total = len(rows)
    hits = sum(1 for row in rows if row.get(key))
    return {"count": hits, "total": total, "pct": pct(hits, total)}


def _combo_rows(rows: list[dict[str, Any]]) -> dict[str, dict[str, float | int]]:
    combos = {
        "vwap_only": lambda r: r["vwap_positive"],
        "trend_only": lambda r: r["trend_positive"],
        "vwap_and_trend": lambda r: r["vwap_positive"] and r["trend_positive"],
        "vwap_trend_rs": lambda r: (
            r["vwap_positive"] and r["trend_positive"] and r["rs_support"]
        ),
        "vwap_trend_rvol": lambda r: (
            r["vwap_positive"] and r["trend_positive"] and r["rvol_support"]
        ),
        "candidate_policy_match": lambda r: r["candidate_policy_match"],
        "candidate_policy_match_or15": lambda r: (
            r["candidate_policy_match"] and r["or15_support"]
        ),
        "candidate_policy_match_or30": lambda r: (
            r["candidate_policy_match"] and r["or30_support"]
        ),
        "candidate_policy_match_any_or": lambda r: (
            r["candidate_policy_match"] and r["any_or_support"]
        ),
    }
    return {name: _bool_rate([r | {"_hit": fn(r)} for r in rows], "_hit") for name, fn in combos.items()}


def _grouped_combo(rows: list[dict[str, Any]], group_key: str) -> dict[str, Any]:
    groups: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        groups[str(row[group_key])].append(row)
    return {key: _combo_rows(group_rows) for key, group_rows in sorted(groups.items())}


def _transitions(rows: list[dict[str, Any]]) -> dict[str, Any]:
    groups: dict[tuple[str, str, str], list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        groups[(row["instrument_id"], row["session_date"], row["decision_type"])].append(row)
    pattern_counts: Counter[str] = Counter()
    true_then_false = 0
    first_true_by_checkpoint: Counter[str] = Counter()
    multi_checkpoint_groups = 0
    for group_rows in groups.values():
        ordered = sorted(group_rows, key=lambda r: r["checkpoint"])
        if len(ordered) < 2:
            continue
        multi_checkpoint_groups += 1
        values = [bool(r["candidate_policy_match"]) for r in ordered]
        compact: list[bool] = []
        for value in values:
            if not compact or compact[-1] != value:
                compact.append(value)
        pattern = " -> ".join("true" if value else "false" for value in compact)
        pattern_counts[pattern] += 1
        if True in values:
            first = ordered[values.index(True)]["checkpoint"]
            first_true_by_checkpoint[str(first)] += 1
            if any(not value for value in values[values.index(True) + 1 :]):
                true_then_false += 1
    return {
        "multi_checkpoint_candidate_groups": multi_checkpoint_groups,
        "patterns": dict(sorted(pattern_counts.items())),
        "first_true_by_checkpoint": dict(sorted(first_true_by_checkpoint.items())),
        "true_then_later_false_groups": true_then_false,
        "true_then_later_false_pct": pct(true_then_false, multi_checkpoint_groups),
    }


def _associations(rows: list[dict[str, Any]]) -> dict[str, float | None]:
    pairs = (
        ("vwap_positive", "trend_positive"),
        ("or15_support", "or30_support"),
        ("vwap_trend_positive", "any_or_support"),
        ("rs_support", "rvol_support"),
        ("rs_support", "is_trade"),
        ("rvol_support", "is_trade"),
    )
    return {f"{left}__{right}": phi(left, right, rows) for left, right in pairs}


def _analysis_digest(summary: dict[str, Any]) -> str:
    stable = json.loads(json.dumps(summary, sort_keys=True))
    stable["metadata"].pop("runtime_seconds", None)
    stable.pop("artifacts", None)
    payload = json.dumps(stable, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def run_baseline(
    *,
    db_path: Path,
    config_dir: Path,
    output_dir: Path,
    session_dates: tuple[str, ...] = DEFAULT_SESSION_DATES,
    checkpoints: tuple[str, ...] = DEFAULT_CHECKPOINTS,
    per_type: int = 10,
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
    candidate_counts: Counter[str] = Counter()
    try:
        for session_date_raw in session_dates:
            session_date = date.fromisoformat(session_date_raw)
            previous_date = latest_trading_day_on_or_before(calendar, session_date - timedelta(days=1))
            for checkpoint_raw in checkpoints:
                hour, minute = [int(part) for part in checkpoint_raw.split(":")]
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
                    completed_five = completed_candles(five_min, Timeframe.M5, as_of=as_of)
                    vwap_result = (
                        indicator_engine.compute(IndicatorName.VWAP, completed_five, as_of=as_of)
                        if completed_five
                        else None
                    )

                    daily = store.recent_candles(instrument_id, Timeframe.D1, as_of=as_of, limit=500)
                    daily_indicators = indicator_engine.compute_all(
                        [IndicatorName.SMA], daily, as_of=as_of
                    )
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
                                        store.recent_candles(
                                            instrument_id, Timeframe.M5, as_of=as_of, limit=100
                                        ),
                                        Timeframe.M5,
                                        as_of=as_of,
                                    ),
                                    confluence_cfg.five_min_sma_period,
                                ),
                                fifteen_min_bullish=_direction(
                                    completed_candles(
                                        store.recent_candles(
                                            instrument_id, Timeframe.M15, as_of=as_of, limit=100
                                        ),
                                        Timeframe.M15,
                                        as_of=as_of,
                                    ),
                                    confluence_cfg.fifteen_min_sma_period,
                                ),
                            )

                    orb = opening_range_engine.assess(
                        instrument_id,
                        as_of=as_of,
                        session_context=session_context,
                        five_min_candles=five_min,
                        calendar=calendar,
                        tzinfo=tzinfo,
                    )
                    sector = store.instrument_sector(instrument_id)
                    sector_index_id = sector_to_index.get(sector) if sector else None
                    rs = rs_engine.assess(
                        instrument_id,
                        as_of=as_of,
                        session_context=session_context,
                        sector=sector,
                        market_benchmark_id=market_benchmark_id,
                        sector_benchmark_id=sector_index_id,
                        stock_five_min_candles=five_min,
                        market_five_min_candles=market_m5,
                        sector_five_min_candles=sector_m5_cache.get(sector, []),
                        calendar=calendar,
                        tzinfo=tzinfo,
                    )
                    current_d1 = store.d1_candle_on(instrument_id, session_date)
                    previous_d1 = (
                        store.d1_candle_on(instrument_id, previous_date)
                        if previous_date is not None
                        else None
                    )
                    gap = gap_engine.assess(
                        instrument_id,
                        as_of=as_of,
                        session_date=session_date,
                        previous_session_date=previous_date,
                        previous_session_close=previous_d1.close if previous_d1 else None,
                        current_session_open=current_d1.open if current_d1 else None,
                    )
                    rvol = rvol_engine.assess(
                        instrument_id,
                        as_of=as_of,
                        session_context=session_context,
                        five_min_candles=store.wide_m5(instrument_id, as_of),
                        calendar=calendar,
                        tzinfo=tzinfo,
                    )
                    signal_set = intraday_engine.assess(
                        instrument_id,
                        as_of=as_of,
                        session_date=session_date,
                        session_context=session_context,
                        vwap=vwap_result,
                        confluence=confluence,
                        five_min_sma_period=scoring_cfg.confluence.five_min_sma_period,
                        fifteen_min_sma_period=scoring_cfg.confluence.fifteen_min_sma_period,
                        or15=orb[OpeningRangeWindow.OR15],
                        or30=orb[OpeningRangeWindow.OR30],
                        relative_strength=rs,
                        gap=gap,
                        relative_volume=rvol,
                    )
                    or15 = signal_set.or15
                    or30 = signal_set.or30
                    vwap_positive = signal_set.vwap.relation is VwapRelation.ABOVE_VWAP
                    trend_positive = signal_set.trend.trend_label is IntradayTrendLabel.BULLISH
                    rs_support = (
                        rs.stock_vs_market_relation is RelativeStrengthRelation.OUTPERFORMING
                        or rs.stock_vs_sector_relation is RelativeStrengthRelation.OUTPERFORMING
                    )
                    rvol_support = rvol.relation is RelativeVolumeRelation.ABOVE_BASELINE
                    or15_support = (
                        or15.relation is OpeningRangeRelation.ABOVE_RANGE
                        or or15.breakout_event is BreakoutEvent.UPSIDE_BREAKOUT_EVENT
                    )
                    or30_support = (
                        or30.relation is OpeningRangeRelation.ABOVE_RANGE
                        or or30.breakout_event is BreakoutEvent.UPSIDE_BREAKOUT_EVENT
                    )
                    rows.append(
                        {
                            "session_date": session_date.isoformat(),
                            "checkpoint": checkpoint_raw,
                            "as_of": as_of.isoformat(),
                            "instrument_id": instrument_id,
                            "decision_id": candidate.decision_id,
                            "decision_type": candidate.decision_type,
                            "decision_ts": candidate.decision_ts.isoformat(),
                            "is_trade": candidate.decision_type == DecisionType.TRADE.value,
                            "session_phase": session_context.phase.value,
                            "data_quality": session_context.data_quality.value,
                            "session_context_available": True,
                            "intraday_signal_set_constructible": True,
                            "data_quality_sufficient": (
                                session_context.data_quality is SessionDataQualityStatus.SUFFICIENT
                            ),
                            "vwap_relation": signal_set.vwap.relation.value,
                            "vwap_available": signal_set.vwap.relation
                            is not VwapRelation.VWAP_UNAVAILABLE,
                            "vwap_positive": vwap_positive,
                            "trend_label": signal_set.trend.trend_label.value,
                            "five_min_available": signal_set.trend.five_min.bullish is not None,
                            "fifteen_min_available": signal_set.trend.fifteen_min.bullish is not None,
                            "five_min_bullish": signal_set.trend.five_min.bullish,
                            "fifteen_min_bullish": signal_set.trend.fifteen_min.bullish,
                            "trend_positive": trend_positive,
                            "vwap_trend_positive": vwap_positive and trend_positive,
                            "or15_status": or15.formation.status.value,
                            "or15_relation": or15.relation.value,
                            "or15_breakout": or15.breakout_event.value,
                            "or15_returned_inside": or15.returned_inside_range,
                            "or15_complete": (
                                or15.formation.status is OpeningRangeFormationStatus.COMPLETE
                            ),
                            "or15_support": or15_support,
                            "or30_status": or30.formation.status.value,
                            "or30_relation": or30.relation.value,
                            "or30_breakout": or30.breakout_event.value,
                            "or30_returned_inside": or30.returned_inside_range,
                            "or30_complete": (
                                or30.formation.status is OpeningRangeFormationStatus.COMPLETE
                            ),
                            "or30_support": or30_support,
                            "any_or_support": or15_support or or30_support,
                            "rs_stock_vs_sector": rs.stock_vs_sector_relation.value,
                            "rs_stock_vs_market": rs.stock_vs_market_relation.value,
                            "rs_available": rs.stock_available
                            and (rs.market_available or rs.sector_available),
                            "rs_support": rs_support,
                            "rvol_relation": rvol.relation.value,
                            "rvol_available": rvol.available,
                            "rvol_support": rvol_support,
                            "gap_direction": gap.direction.value,
                            "gap_available": gap.available,
                            "candidate_policy_match": (
                                vwap_positive
                                and trend_positive
                                and (rs_support or rvol_support)
                            ),
                        }
                    )
    finally:
        store.close()

    total = len(rows)
    by_type = {dtype: [row for row in rows if row["decision_type"] == dtype] for dtype in ("WATCH", "TRADE")}
    output_dir.mkdir(parents=True, exist_ok=True)
    rows_path = output_dir / "id6b1_observations.jsonl"
    with rows_path.open("w", encoding="utf-8") as fh:
        for row in rows:
            fh.write(json.dumps(row, sort_keys=True) + "\n")

    summary: dict[str, Any] = {
        "metadata": {
            "milestone": "ID-6B.1",
            "label": "settled historical market-time replay",
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
            "by_decision_type": {
                key: {"count": len(value), "pct": pct(len(value), total)}
                for key, value in by_type.items()
            },
        },
        "availability": {
            key: _bool_rate(rows, key)
            for key in (
                "session_context_available",
                "intraday_signal_set_constructible",
                "data_quality_sufficient",
                "vwap_available",
                "five_min_available",
                "fifteen_min_available",
                "or15_complete",
                "or30_complete",
                "rs_available",
                "rvol_available",
                "gap_available",
            )
        },
        "distributions": {
            "session_phase": _counter_payload(Counter(row["session_phase"] for row in rows), total),
            "data_quality": _counter_payload(Counter(row["data_quality"] for row in rows), total),
            "vwap": _counter_payload(Counter(row["vwap_relation"] for row in rows), total),
            "trend": _counter_payload(Counter(row["trend_label"] for row in rows), total),
            "or15_status": _counter_payload(Counter(row["or15_status"] for row in rows), total),
            "or15_relation": _counter_payload(Counter(row["or15_relation"] for row in rows), total),
            "or15_breakout": _counter_payload(Counter(row["or15_breakout"] for row in rows), total),
            "or30_status": _counter_payload(Counter(row["or30_status"] for row in rows), total),
            "or30_relation": _counter_payload(Counter(row["or30_relation"] for row in rows), total),
            "or30_breakout": _counter_payload(Counter(row["or30_breakout"] for row in rows), total),
            "rs_stock_vs_market": _counter_payload(
                Counter(row["rs_stock_vs_market"] for row in rows), total
            ),
            "rs_stock_vs_sector": _counter_payload(
                Counter(row["rs_stock_vs_sector"] for row in rows), total
            ),
            "rvol": _counter_payload(Counter(row["rvol_relation"] for row in rows), total),
            "gap": _counter_payload(Counter(row["gap_direction"] for row in rows), total),
        },
        "combinations": {
            "overall": _combo_rows(rows),
            "by_decision_type": {key: _combo_rows(value) for key, value in by_type.items()},
            "by_checkpoint": _grouped_combo(rows, "checkpoint"),
        },
        "associations_phi": _associations(rows),
        "transitions": _transitions(rows),
        "forward_outcome_feasibility": {
            "trade_outcomes_not_used": True,
            "note": (
                "Existing candles can support a future neutral MFE/MAE/time-to-target "
                "harness, but this baseline does not optimize against outcomes."
            ),
        },
    }
    summary_path = output_dir / "id6b1_summary.json"
    analysis_digest = _analysis_digest(summary)
    summary["artifacts"] = {
        "summary_path": str(summary_path),
        "observations_path": str(rows_path),
        "analysis_sha256": analysis_digest,
    }
    summary_path.write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return summary


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--db", type=Path, default=Path("db/athena.db"))
    parser.add_argument("--config-dir", type=Path, default=Path("config"))
    parser.add_argument("--output-dir", type=Path, default=Path("artifacts/research/id6b1"))
    parser.add_argument("--per-type", type=int, default=10)
    args = parser.parse_args()
    summary = run_baseline(
        db_path=args.db,
        config_dir=args.config_dir,
        output_dir=args.output_dir,
        per_type=args.per_type,
    )
    print(json.dumps(summary["sample"], indent=2, sort_keys=True))
    print(f"analysis_sha256={summary['artifacts']['analysis_sha256']}")


if __name__ == "__main__":
    main()
