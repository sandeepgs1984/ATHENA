"""Provider-independent data validators (M1.3).

Pure functions over canonical ``Candle`` objects. Time is always injected as
``as_of`` — no clock reads — so validation is deterministic and replayable.
Nothing here knows about files, SQLite, or brokers.

Separation of responsibility (ATHENA-002 §7 / M1.3 authorization):
- The provider guarantees parsing, structural OHLC relations (High >= Open/Close,
  Low <= Open/Close, High >= Low are enforced by the Candle domain object), and
  no duplicate timestamps within a single request.
- This layer validates higher-level *business* quality the contract does NOT
  guarantee: positive prices, dataset freshness, cross-dataset duplicates, and
  completeness against the trading calendar.
"""

from __future__ import annotations

from collections.abc import Sequence
from datetime import date, datetime
from decimal import Decimal

from athena.calendar.engine import CalendarEngine
from athena.config.models import ValidationConfig
from athena.data.validation.calendar_expectations import (
    expected_intraday_opens,
    latest_trading_day_on_or_before,
    trading_days_between,
)
from athena.data.validation.reports import (
    Severity,
    ValidationReport,
    ValidationResult,
    ValidationType,
)
from athena.domain.enums import Timeframe
from athena.domain.market import Candle

_EVIDENCE_CAP = 20  # keep reports bounded and reviewable
_STEP_MINUTES = {Timeframe.M1: 1, Timeframe.M5: 5, Timeframe.M15: 15}


def _instant(ts: datetime) -> int:
    return int(ts.timestamp())


def _passed(vt: ValidationType, explanation: str, as_of: datetime, stats: dict) -> ValidationReport:
    return ValidationReport(
        validation_type=vt, result=ValidationResult.PASSED, severity=Severity.INFO,
        explanation=explanation, ts=as_of, statistics=stats,
    )


def _failed(vt, severity, explanation, as_of, stats, evidence=()) -> ValidationReport:
    return ValidationReport(
        validation_type=vt, result=ValidationResult.FAILED, severity=severity,
        explanation=explanation, ts=as_of, evidence=tuple(evidence), statistics=stats,
    )


# --------------------------------------------------------------------------- OHLC

def validate_ohlc(candles: Sequence[Candle], *, as_of: datetime) -> ValidationReport:
    """Validate business rules not guaranteed by the Candle contract: strictly
    positive prices. (High/Low ordering is already enforced structurally.)"""
    offenders: list[str] = []
    for c in candles:
        if min(c.open, c.high, c.low, c.close) <= Decimal(0):
            offenders.append(
                f"{c.ts_open.isoformat()} non-positive price "
                f"O={c.open} H={c.high} L={c.low} C={c.close}"
            )
    stats = {"candles_checked": len(candles), "non_positive_price_count": len(offenders)}
    if offenders:
        return _failed(ValidationType.OHLC, Severity.CRITICAL,
                       f"{len(offenders)} candle(s) have non-positive prices",
                       as_of, stats, offenders[:_EVIDENCE_CAP])
    return _passed(ValidationType.OHLC, f"all {len(candles)} candle(s) have positive prices",
                   as_of, stats)


# ---------------------------------------------------------------------- duplicates

def validate_duplicates(candles: Sequence[Candle], *, as_of: datetime) -> ValidationReport:
    """Detect duplicate (instrument_id, timeframe, ts_open) across the dataset —
    e.g. from merging datasets or crossing ingestion boundaries."""
    seen: set[tuple[str, str, int]] = set()
    dups: list[str] = []
    for c in candles:
        key = (c.instrument_id, c.timeframe.value, _instant(c.ts_open))
        if key in seen:
            dups.append(f"{c.instrument_id} {c.timeframe.value} {c.ts_open.isoformat()}")
        seen.add(key)
    stats = {"candles_checked": len(candles), "duplicate_count": len(dups)}
    if dups:
        return _failed(ValidationType.DUPLICATE, Severity.ERROR,
                       f"{len(dups)} duplicate candle record(s) detected",
                       as_of, stats, dups[:_EVIDENCE_CAP])
    return _passed(ValidationType.DUPLICATE, "no duplicate candle records", as_of, stats)


# ---------------------------------------------------------------------- freshness

def validate_freshness(
    candles: Sequence[Candle], timeframe: Timeframe, calendar: CalendarEngine,
    config: ValidationConfig, *, as_of: datetime,
) -> ValidationReport:
    """Detect stale datasets relative to the trading calendar (daily) or the
    injected reference time (intraday)."""
    vt = ValidationType.FRESHNESS
    if not candles:
        return _failed(vt, Severity.CRITICAL, "dataset is empty — no data to assess freshness",
                       as_of, {"candle_count": 0})

    latest = max(c.ts_open for c in candles)

    if timeframe is Timeframe.D1:
        expected = latest_trading_day_on_or_before(calendar, as_of.date())
        if expected is None:
            return _failed(vt, Severity.ERROR,
                           "cannot determine the expected latest trading day from the calendar",
                           as_of, {"as_of": as_of.date().isoformat()})
        behind = len(trading_days_between(calendar, latest.date(), expected)) - 1
        behind = max(behind, 0)
        stats = {
            "latest_data_date": latest.date().isoformat(),
            "expected_latest_trading_day": expected.isoformat(),
            "trading_days_behind": behind,
            "threshold": config.freshness.max_trading_days_behind,
        }
        if behind > config.freshness.max_trading_days_behind:
            return _failed(vt, Severity.ERROR,
                           f"data is {behind} trading day(s) behind the expected "
                           f"{expected.isoformat()} (threshold {config.freshness.max_trading_days_behind})",
                           as_of, stats)
        return _passed(vt, f"daily data current to {latest.date().isoformat()}", as_of, stats)

    # Intraday: minutes behind the injected reference time.
    minutes_behind = (as_of - latest).total_seconds() / 60.0
    stats = {
        "latest_data_ts": latest.isoformat(),
        "as_of": as_of.isoformat(),
        "minutes_behind": round(minutes_behind, 2),
        "threshold_minutes": config.freshness.intraday_max_minutes_behind,
    }
    if minutes_behind > config.freshness.intraday_max_minutes_behind:
        return _failed(vt, Severity.ERROR,
                       f"intraday data is {minutes_behind:.1f} min behind as_of "
                       f"(threshold {config.freshness.intraday_max_minutes_behind} min)",
                       as_of, stats)
    return _passed(vt, f"intraday data current to {latest.isoformat()}", as_of, stats)


# ---------------------------------------------------------------------------- gaps

def validate_daily_gaps(
    candles: Sequence[Candle], calendar: CalendarEngine, *,
    start: date, end: date, as_of: datetime,
) -> ValidationReport:
    """Missing trading sessions in [start, end], per the calendar (weekends and
    holidays are never counted as gaps)."""
    expected = trading_days_between(calendar, start, end)
    present = {c.ts_open.date() for c in candles}
    missing = [d for d in expected if d not in present]
    stats = {
        "range": f"{start.isoformat()}..{end.isoformat()}",
        "expected_sessions": len(expected),
        "present_sessions": len(present & set(expected)),
        "missing_sessions": len(missing),
    }
    if missing:
        return _failed(ValidationType.GAP, Severity.ERROR,
                       f"{len(missing)} expected trading session(s) missing in range",
                       as_of, stats, [d.isoformat() for d in missing[:_EVIDENCE_CAP]])
    return _passed(ValidationType.GAP,
                   f"all {len(expected)} expected trading session(s) present", as_of, stats)


def validate_intraday_gaps(
    candles: Sequence[Candle], timeframe: Timeframe, calendar: CalendarEngine, *,
    start: date, end: date, as_of: datetime, tzinfo,
) -> ValidationReport:
    """Missing intraday intervals across each trading session in [start, end]."""
    if timeframe not in _STEP_MINUTES:
        raise ValueError(f"intraday gap check needs an intraday timeframe, got {timeframe}")
    step = _STEP_MINUTES[timeframe]
    present = {_instant(c.ts_open) for c in candles}
    missing: list[str] = []
    expected_count = 0
    for day in trading_days_between(calendar, start, end):
        for open_ts in expected_intraday_opens(calendar, day, step, tzinfo):
            expected_count += 1
            if _instant(open_ts) not in present:
                missing.append(open_ts.isoformat())
    stats = {
        "range": f"{start.isoformat()}..{end.isoformat()}",
        "timeframe": timeframe.value,
        "expected_intervals": expected_count,
        "missing_intervals": len(missing),
    }
    if missing:
        return _failed(ValidationType.GAP, Severity.ERROR,
                       f"{len(missing)} expected {timeframe.value} interval(s) missing",
                       as_of, stats, missing[:_EVIDENCE_CAP])
    return _passed(ValidationType.GAP,
                   f"all {expected_count} expected {timeframe.value} interval(s) present",
                   as_of, stats)
