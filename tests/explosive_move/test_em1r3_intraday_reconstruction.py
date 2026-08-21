from datetime import date, datetime
from decimal import Decimal
from zoneinfo import ZoneInfo

import pytest

from athena.domain.enums import Timeframe
from athena.domain.market import Candle
from athena.explosive_move.intraday_reconstruction import (
    SessionExclusionReason,
    candles_from_payload,
    canonical_candle_payload,
    reconstruct_regular_session,
)

DAY = date(2026, 8, 20)
TZ = ZoneInfo("Asia/Kolkata")
SLOTS = (
    datetime(2026, 8, 20, 9, 15, tzinfo=TZ),
    datetime(2026, 8, 20, 9, 20, tzinfo=TZ),
)


def _candle(
    ts_open: datetime,
    *,
    instrument_id: str = "NSE:AAA",
    close: str = "100",
) -> Candle:
    return Candle(
        instrument_id=instrument_id,
        timeframe=Timeframe.M5,
        ts_open=ts_open,
        open=Decimal("100"),
        high=Decimal("102"),
        low=Decimal("99"),
        close=Decimal(close),
        volume=1_000,
        source="kite",
        adjusted=False,
    )


def test_exact_complete_session_is_admitted_and_round_trips() -> None:
    rows = tuple(_candle(slot) for slot in SLOTS)

    result = reconstruct_regular_session(
        instrument_id="NSE:AAA",
        session_date=DAY,
        expected_slots=SLOTS,
        source_rows=rows,
    )

    assert result.record.status == "ADMITTED"
    assert result.record.admitted_rows == 2
    assert result.record.identical_duplicates_collapsed == 0
    assert result.candles == rows
    assert candles_from_payload(canonical_candle_payload(rows)) == rows


def test_identical_duplicates_collapse_without_inventing_values() -> None:
    first = _candle(SLOTS[0])
    second = _candle(SLOTS[1])

    result = reconstruct_regular_session(
        instrument_id="NSE:AAA",
        session_date=DAY,
        expected_slots=SLOTS,
        source_rows=(first, first, second),
    )

    assert result.record.status == "ADMITTED"
    assert result.record.source_rows == 3
    assert result.record.identical_duplicates_collapsed == 1
    assert result.candles == (first, second)


@pytest.mark.parametrize(
    ("rows", "retrieval_error", "reason"),
    [
        ((), "ProviderError: unavailable", SessionExclusionReason.RETRIEVAL_FAILED),
        ((_candle(SLOTS[0]),), None, SessionExclusionReason.MISSING_SLOT),
        (
            (_candle(datetime(2026, 8, 20, 9, 16, tzinfo=TZ)),),
            None,
            SessionExclusionReason.OFF_GRID_TIMESTAMP,
        ),
        (
            (_candle(SLOTS[0]), _candle(SLOTS[0], close="101"), _candle(SLOTS[1])),
            None,
            SessionExclusionReason.CONFLICTING_SLOT,
        ),
    ],
)
def test_incomplete_or_ambiguous_sessions_are_excluded(
    rows: tuple[Candle, ...],
    retrieval_error: str | None,
    reason: SessionExclusionReason,
) -> None:
    result = reconstruct_regular_session(
        instrument_id="NSE:AAA",
        session_date=DAY,
        expected_slots=SLOTS,
        source_rows=rows,
        retrieval_error=retrieval_error,
    )

    assert result.record.status == "EXCLUDED"
    assert result.record.exclusion_reason is reason
    assert result.record.admitted_rows == 0
    assert result.candles == ()
