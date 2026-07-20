"""DatasetValidator — orchestrates the individual validators into one summary (M1.3).

Provider-agnostic: it consumes canonical Candle objects and the Calendar Engine,
and returns an immutable ValidationSummary. No file/SQLite/broker awareness.
"""

from __future__ import annotations

from collections.abc import Sequence
from datetime import date, datetime

from athena.calendar.engine import CalendarEngine
from athena.config.models import ValidationConfig
from athena.data.validation.reports import ValidationReport, ValidationSummary
from athena.data.validation.validators import (
    validate_daily_gaps,
    validate_duplicates,
    validate_freshness,
    validate_intraday_gaps,
    validate_ohlc,
)
from athena.domain.enums import Timeframe
from athena.domain.market import Candle


class DatasetValidator:
    """Runs the full validation battery over one instrument/timeframe dataset."""

    def __init__(self, calendar: CalendarEngine, config: ValidationConfig, tzinfo) -> None:
        self._calendar = calendar
        self._config = config
        self._tzinfo = tzinfo

    def validate_daily(
        self, dataset_id: str, candles: Sequence[Candle], *,
        start: date, end: date, as_of: datetime,
    ) -> ValidationSummary:
        reports: list[ValidationReport] = [
            validate_ohlc(candles, as_of=as_of),
            validate_duplicates(candles, as_of=as_of),
            validate_freshness(candles, Timeframe.D1, self._calendar, self._config, as_of=as_of),
        ]
        if self._config.gaps.daily_enabled:
            reports.append(
                validate_daily_gaps(candles, self._calendar, start=start, end=end, as_of=as_of)
            )
        return ValidationSummary(dataset_id=dataset_id, reports=tuple(reports), ts=as_of)

    def validate_intraday(
        self, dataset_id: str, timeframe: Timeframe, candles: Sequence[Candle], *,
        start: date, end: date, as_of: datetime,
    ) -> ValidationSummary:
        reports: list[ValidationReport] = [
            validate_ohlc(candles, as_of=as_of),
            validate_duplicates(candles, as_of=as_of),
            validate_freshness(candles, timeframe, self._calendar, self._config, as_of=as_of),
        ]
        if self._config.gaps.intraday_enabled:
            reports.append(
                validate_intraday_gaps(candles, timeframe, self._calendar,
                                       start=start, end=end, as_of=as_of, tzinfo=self._tzinfo)
            )
        return ValidationSummary(dataset_id=dataset_id, reports=tuple(reports), ts=as_of)
