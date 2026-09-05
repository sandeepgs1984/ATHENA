"""PS-P9D Portfolio Opening Range Setup adapter tests."""

from __future__ import annotations

from datetime import date, datetime, timedelta
from decimal import Decimal
from zoneinfo import ZoneInfo

from athena.data.store.repository import SqliteRepository
from athena.domain.enums import Timeframe
from athena.domain.market import Candle
from athena.intraday.opening_range_models import (
    BreakoutEvent,
    OpeningRangeEvidence,
    OpeningRangeFormation,
    OpeningRangeFormationStatus,
    OpeningRangeRelation,
    OpeningRangeWindow,
)
from athena.portfolio.setup_adapter import (
    PortfolioSetup,
    PortfolioSetupAdapter,
    PortfolioSetupReason,
)

TZ = ZoneInfo("Asia/Kolkata")
SESSION = date(2026, 9, 2)
AS_OF = datetime(2026, 9, 2, 10, 0, tzinfo=TZ)
OPEN = datetime(2026, 9, 2, 9, 15, tzinfo=TZ)
IID = "NSE:INFY"


def _adapter(tmp_path) -> PortfolioSetupAdapter:
    repo = SqliteRepository(tmp_path / "athena.db")
    repo.initialize()
    return PortfolioSetupAdapter(repo)


def _formation(
    window: OpeningRangeWindow,
    status: OpeningRangeFormationStatus = OpeningRangeFormationStatus.COMPLETE,
) -> OpeningRangeFormation:
    minutes = 15 if window is OpeningRangeWindow.OR15 else 30
    return OpeningRangeFormation(
        window=window,
        range_start=OPEN,
        range_end=OPEN + timedelta(minutes=minutes),
        high=Decimal("100"),
        low=Decimal("95"),
        high_ts=OPEN,
        low_ts=OPEN,
        range_width=Decimal("5"),
        range_width_pct=Decimal("5.263157894736842105263157895"),
        volume=3000,
        bars_expected=minutes // 5,
        bars_present=minutes // 5,
        status=status,
        explanation="test formation",
    )


def _or(
    window: OpeningRangeWindow,
    event: BreakoutEvent,
    *,
    status: OpeningRangeFormationStatus = OpeningRangeFormationStatus.COMPLETE,
    returned_inside: bool | None = None,
    instrument_id: str = IID,
    session: date = SESSION,
    as_of: datetime = AS_OF,
) -> OpeningRangeEvidence:
    return OpeningRangeEvidence(
        instrument_id=instrument_id,
        session_date=session,
        as_of=as_of,
        formation=_formation(window, status),
        relation=OpeningRangeRelation.ABOVE_RANGE,
        breakout_event=event,
        first_breakout_ts=OPEN + timedelta(minutes=45) if event else None,
        bars_since_breakout=1 if event else None,
        max_extension_from_range_pct=Decimal("1"),
        current_extension_pct=Decimal("1"),
        returned_inside_range=returned_inside,
        explanation="test evidence",
    )


def _classify(
    adapter: PortfolioSetupAdapter,
    or15: OpeningRangeEvidence,
    or30: OpeningRangeEvidence,
):
    return adapter.classify_opening_range_evidence(
        instrument_id=IID,
        session_date=SESSION,
        analysis_as_of=AS_OF,
        opening_range={
            OpeningRangeWindow.OR15: or15,
            OpeningRangeWindow.OR30: or30,
        },
    )


def _m5(ts: datetime, close: str, *, high: str = "100", low: str = "95") -> Candle:
    price = Decimal(close)
    return Candle(
        instrument_id=IID,
        timeframe=Timeframe.M5,
        ts_open=ts,
        open=price,
        high=Decimal(high),
        low=Decimal(low),
        close=price,
        volume=1000,
        source="test",
    )


def test_l1_labels_require_or15_and_or30_directional_agreement(tmp_path) -> None:
    adapter = _adapter(tmp_path)

    breakout = _classify(
        adapter,
        _or(OpeningRangeWindow.OR15, BreakoutEvent.UPSIDE_BREAKOUT_EVENT),
        _or(OpeningRangeWindow.OR30, BreakoutEvent.UPSIDE_BREAKOUT_EVENT),
    )
    breakdown = _classify(
        adapter,
        _or(OpeningRangeWindow.OR15, BreakoutEvent.DOWNSIDE_BREAKDOWN_EVENT),
        _or(OpeningRangeWindow.OR30, BreakoutEvent.DOWNSIDE_BREAKDOWN_EVENT),
    )

    assert breakout.setup is PortfolioSetup.BREAKOUT
    assert breakout.reason is PortfolioSetupReason.BREAKOUT_FROM_OPENING_RANGE_AGREEMENT
    assert breakdown.setup is PortfolioSetup.BREAKDOWN
    assert breakdown.reason is PortfolioSetupReason.BREAKDOWN_FROM_OPENING_RANGE_AGREEMENT


def test_null_reason_precedence_matches_ps_p9c_freeze(tmp_path) -> None:
    adapter = _adapter(tmp_path)

    conflict_over_returned = _classify(
        adapter,
        _or(
            OpeningRangeWindow.OR15,
            BreakoutEvent.DOWNSIDE_BREAKDOWN_EVENT,
            returned_inside=True,
        ),
        _or(
            OpeningRangeWindow.OR30,
            BreakoutEvent.UPSIDE_BREAKOUT_EVENT,
            returned_inside=False,
        ),
    )
    incomplete_over_single = _classify(
        adapter,
        _or(OpeningRangeWindow.OR15, BreakoutEvent.UPSIDE_BREAKOUT_EVENT),
        _or(
            OpeningRangeWindow.OR30,
            BreakoutEvent.NOT_OBSERVED,
            status=OpeningRangeFormationStatus.FORMING,
        ),
    )
    single_window = _classify(
        adapter,
        _or(OpeningRangeWindow.OR15, BreakoutEvent.UPSIDE_BREAKOUT_EVENT),
        _or(OpeningRangeWindow.OR30, BreakoutEvent.NO_EVENT),
    )
    not_present = _classify(
        adapter,
        _or(OpeningRangeWindow.OR15, BreakoutEvent.NO_EVENT),
        _or(OpeningRangeWindow.OR30, BreakoutEvent.NO_EVENT),
    )

    assert conflict_over_returned.setup is None
    assert conflict_over_returned.reason is PortfolioSetupReason.OR_WINDOWS_CONFLICT
    assert incomplete_over_single.reason is PortfolioSetupReason.OR_INCOMPLETE
    assert single_window.reason is PortfolioSetupReason.SINGLE_WINDOW_ONLY
    assert not_present.reason is PortfolioSetupReason.NOT_PRESENT


def test_incoherent_or_window_context_is_rejected(tmp_path) -> None:
    adapter = _adapter(tmp_path)

    result = _classify(
        adapter,
        _or(OpeningRangeWindow.OR15, BreakoutEvent.UPSIDE_BREAKOUT_EVENT),
        _or(
            OpeningRangeWindow.OR30,
            BreakoutEvent.UPSIDE_BREAKOUT_EVENT,
            instrument_id="NSE:TCS",
        ),
    )

    assert result.setup is None
    assert result.reason is PortfolioSetupReason.EVIDENCE_INCOHERENT
    assert result.is_coherent is False


def test_future_m5_candles_do_not_change_classification(tmp_path) -> None:
    adapter = _adapter(tmp_path)
    base = [
        _m5(OPEN + timedelta(minutes=i * 5), "99")
        for i in range(6)
    ] + [
        _m5(OPEN + timedelta(minutes=30), "99"),
        _m5(OPEN + timedelta(minutes=35), "101", high="101"),
    ]
    future_breakdown = _m5(
        OPEN + timedelta(minutes=50), "94", high="101", low="94"
    )

    without_future = adapter.classify_candles(
        instrument_id=IID,
        five_min_candles=base,
        accepted_price_as_of=AS_OF,
        expected_analysis_as_of=AS_OF,
        market_timezone=TZ,
    )
    at_boundary = adapter.classify_candles(
        instrument_id=IID,
        five_min_candles=[*base, future_breakdown],
        accepted_price_as_of=AS_OF,
        expected_analysis_as_of=AS_OF,
        market_timezone=TZ,
    )

    assert without_future.setup is PortfolioSetup.BREAKOUT
    assert at_boundary.setup is PortfolioSetup.BREAKOUT
    assert at_boundary.reason is without_future.reason


def test_stale_and_unavailable_inputs_have_explicit_reasons(tmp_path) -> None:
    adapter = _adapter(tmp_path)

    unavailable = adapter.classify_candles(
        instrument_id=IID,
        five_min_candles=[],
        accepted_price_as_of=None,
        expected_analysis_as_of=AS_OF,
        market_timezone=TZ,
    )
    stale = adapter.classify_candles(
        instrument_id=IID,
        five_min_candles=[],
        accepted_price_as_of=AS_OF - timedelta(days=1),
        expected_analysis_as_of=AS_OF,
        market_timezone=TZ,
    )

    assert unavailable.reason is PortfolioSetupReason.EVIDENCE_UNAVAILABLE
    assert stale.reason is PortfolioSetupReason.EVIDENCE_STALE
