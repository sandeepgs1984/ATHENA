"""Portfolio Opening Range Setup adapter (PS-P9D).

Adapts ATHENA's frozen OR15/OR30 OpeningRangeEngine evidence into the My
Portfolio Setup label. This module is structural only: it does not consume
Decision, EntryQualification, Conviction, D1 Trend, TradePlan, EQ, or any trade
recommendation field.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import date, datetime
from enum import Enum, unique
from pathlib import Path
from typing import TYPE_CHECKING
from zoneinfo import ZoneInfo

from athena.calendar.engine import CalendarEngine
from athena.config.loader import load_config
from athena.domain.enums import Timeframe
from athena.domain.market import Candle
from athena.intraday.opening_range_engine import OpeningRangeEngine
from athena.intraday.opening_range_models import (
    BreakoutEvent,
    OpeningRangeEvidence,
    OpeningRangeFormationStatus,
    OpeningRangeWindow,
)
from athena.session.engine import SessionContextEngine, completed_candles, session_day_start

if TYPE_CHECKING:
    from athena.data.store.repository import SqliteRepository


@unique
class PortfolioSetup(str, Enum):
    BREAKOUT = "BREAKOUT"
    BREAKDOWN = "BREAKDOWN"


@unique
class PortfolioSetupReason(str, Enum):
    BREAKOUT_FROM_OPENING_RANGE_AGREEMENT = (
        "SETUP_BREAKOUT_FROM_OPENING_RANGE_AGREEMENT"
    )
    BREAKDOWN_FROM_OPENING_RANGE_AGREEMENT = (
        "SETUP_BREAKDOWN_FROM_OPENING_RANGE_AGREEMENT"
    )
    EVIDENCE_INCOHERENT = "SETUP_EVIDENCE_INCOHERENT"
    EVIDENCE_STALE = "SETUP_EVIDENCE_STALE"
    EVIDENCE_UNAVAILABLE = "SETUP_EVIDENCE_UNAVAILABLE"
    OR_INCOMPLETE = "SETUP_OR_INCOMPLETE"
    OR_WINDOWS_CONFLICT = "SETUP_OR_WINDOWS_CONFLICT"
    RETURNED_INSIDE_RANGE = "SETUP_RETURNED_INSIDE_RANGE"
    SINGLE_WINDOW_ONLY = "SETUP_SINGLE_WINDOW_ONLY"
    NOT_PRESENT = "SETUP_NOT_PRESENT"


@dataclass(frozen=True, slots=True)
class PortfolioSetupWindowEvidence:
    status: OpeningRangeFormationStatus | None
    event: BreakoutEvent | None
    returned_inside_range: bool | None
    first_event_ts: datetime | None


@dataclass(frozen=True, slots=True)
class PortfolioSetupEvidence:
    setup: PortfolioSetup | None
    reason: PortfolioSetupReason
    instrument_id: str
    session_date: date | None
    analysis_as_of: datetime | None
    evidence_as_of: datetime | None
    latest_completed_m5_slot: datetime | None
    is_coherent: bool
    or15: PortfolioSetupWindowEvidence | None
    or30: PortfolioSetupWindowEvidence | None


class PortfolioSetupAdapter:
    """Resolve optional Opening Range Setup evidence for one Portfolio holding."""

    def __init__(
        self,
        repo: SqliteRepository,
        *,
        config_dir: Path | str = "config",
    ) -> None:
        self._repo = repo
        self._config_dir = Path(config_dir)
        self._cfg = load_config(self._config_dir)
        self._calendar = CalendarEngine.from_config_dir(self._config_dir, self._cfg.market)
        self._tzinfo = ZoneInfo(self._cfg.market.timezone)
        self._session_engine = SessionContextEngine()
        self._opening_range_engine = OpeningRangeEngine()

    def resolve(
        self,
        *,
        instrument_id: str,
        accepted_price_as_of: datetime | None,
        expected_analysis_as_of: datetime | None,
        market_timezone: ZoneInfo,
    ) -> PortfolioSetupEvidence:
        if accepted_price_as_of is None:
            return self._unavailable(instrument_id, None)
        if accepted_price_as_of.tzinfo is None:
            raise ValueError("accepted_price_as_of must be timezone-aware")
        if expected_analysis_as_of is not None and expected_analysis_as_of.tzinfo is None:
            raise ValueError("expected_analysis_as_of must be timezone-aware")

        analysis_as_of = expected_analysis_as_of or accepted_price_as_of
        accepted_session = accepted_price_as_of.astimezone(market_timezone).date()
        analysis_session = analysis_as_of.astimezone(market_timezone).date()
        if accepted_session != analysis_session:
            return self._stale(instrument_id, analysis_session, analysis_as_of)

        day_start = session_day_start(analysis_as_of, self._tzinfo)
        five_min = self._repo.get_candles(
            instrument_id, Timeframe.M5, day_start, analysis_as_of
        )
        fifteen_min = self._repo.get_candles(
            instrument_id, Timeframe.M15, day_start, analysis_as_of
        )
        return self.classify_candles(
            instrument_id=instrument_id,
            five_min_candles=five_min,
            fifteen_min_candles=fifteen_min,
            accepted_price_as_of=accepted_price_as_of,
            expected_analysis_as_of=expected_analysis_as_of,
            market_timezone=market_timezone,
        )

    def classify_candles(
        self,
        *,
        instrument_id: str,
        five_min_candles: Sequence[Candle],
        fifteen_min_candles: Sequence[Candle] = (),
        accepted_price_as_of: datetime | None,
        expected_analysis_as_of: datetime | None,
        market_timezone: ZoneInfo,
    ) -> PortfolioSetupEvidence:
        if accepted_price_as_of is None:
            return self._unavailable(instrument_id, None)
        if accepted_price_as_of.tzinfo is None:
            raise ValueError("accepted_price_as_of must be timezone-aware")
        if expected_analysis_as_of is not None and expected_analysis_as_of.tzinfo is None:
            raise ValueError("expected_analysis_as_of must be timezone-aware")

        analysis_as_of = expected_analysis_as_of or accepted_price_as_of
        accepted_session = accepted_price_as_of.astimezone(market_timezone).date()
        analysis_session = analysis_as_of.astimezone(market_timezone).date()
        if accepted_session != analysis_session:
            return self._stale(instrument_id, analysis_session, analysis_as_of)

        eligible_m5 = self._eligible_candles(
            five_min_candles, timeframe=Timeframe.M5, as_of=analysis_as_of
        )
        eligible_m15 = self._eligible_candles(
            fifteen_min_candles, timeframe=Timeframe.M15, as_of=analysis_as_of
        )
        if any(candle.instrument_id != instrument_id for candle in eligible_m5 + eligible_m15):
            return self._incoherent(instrument_id, analysis_session, analysis_as_of)

        latest_completed = completed_candles(
            eligible_m5, Timeframe.M5, as_of=analysis_as_of
        )
        latest_completed_slot = (
            max((candle.ts_open for candle in latest_completed), default=None)
        )
        session_context = self._session_engine.assess(
            instrument_id,
            as_of=analysis_as_of,
            exchange=self._cfg.market.exchange,
            calendar=self._calendar,
            sessions=self._cfg.market.sessions,
            tzinfo=self._tzinfo,
            five_min_candles=eligible_m5,
            fifteen_min_candles=eligible_m15,
            latest_quote_ts=None,
        )
        evidence = self._opening_range_engine.assess(
            instrument_id,
            as_of=analysis_as_of,
            session_context=session_context,
            five_min_candles=eligible_m5,
            calendar=self._calendar,
            tzinfo=self._tzinfo,
        )
        return self.classify_opening_range_evidence(
            instrument_id=instrument_id,
            session_date=analysis_session,
            analysis_as_of=analysis_as_of,
            opening_range=evidence,
            latest_completed_m5_slot=latest_completed_slot,
        )

    def classify_opening_range_evidence(
        self,
        *,
        instrument_id: str,
        session_date: date,
        analysis_as_of: datetime,
        opening_range: Mapping[OpeningRangeWindow, OpeningRangeEvidence],
        latest_completed_m5_slot: datetime | None = None,
    ) -> PortfolioSetupEvidence:
        if analysis_as_of.tzinfo is None:
            raise ValueError("analysis_as_of must be timezone-aware")
        or15 = opening_range.get(OpeningRangeWindow.OR15)
        or30 = opening_range.get(OpeningRangeWindow.OR30)
        if or15 is None or or30 is None:
            return self._unavailable(instrument_id, session_date)
        if not self._or_evidence_is_coherent(
            instrument_id, session_date, analysis_as_of, (or15, or30)
        ):
            return self._incoherent(instrument_id, session_date, analysis_as_of)

        window_15 = self._window(or15)
        window_30 = self._window(or30)
        if (
            or15.formation.status is not OpeningRangeFormationStatus.COMPLETE
            or or30.formation.status is not OpeningRangeFormationStatus.COMPLETE
        ):
            return self._classified(
                instrument_id=instrument_id,
                session_date=session_date,
                analysis_as_of=analysis_as_of,
                latest_completed_m5_slot=latest_completed_m5_slot,
                or15=window_15,
                or30=window_30,
                setup=None,
                reason=PortfolioSetupReason.OR_INCOMPLETE,
            )

        event_15 = self._active_event(or15)
        event_30 = self._active_event(or30)
        if self._is_conflict(event_15, event_30):
            return self._classified(
                instrument_id=instrument_id,
                session_date=session_date,
                analysis_as_of=analysis_as_of,
                latest_completed_m5_slot=latest_completed_m5_slot,
                or15=window_15,
                or30=window_30,
                setup=None,
                reason=PortfolioSetupReason.OR_WINDOWS_CONFLICT,
            )
        if bool(or15.returned_inside_range) or bool(or30.returned_inside_range):
            return self._classified(
                instrument_id=instrument_id,
                session_date=session_date,
                analysis_as_of=analysis_as_of,
                latest_completed_m5_slot=latest_completed_m5_slot,
                or15=window_15,
                or30=window_30,
                setup=None,
                reason=PortfolioSetupReason.RETURNED_INSIDE_RANGE,
            )
        if (
            event_15 is BreakoutEvent.UPSIDE_BREAKOUT_EVENT
            and event_30 is BreakoutEvent.UPSIDE_BREAKOUT_EVENT
        ):
            return self._classified(
                instrument_id=instrument_id,
                session_date=session_date,
                analysis_as_of=analysis_as_of,
                latest_completed_m5_slot=latest_completed_m5_slot,
                or15=window_15,
                or30=window_30,
                setup=PortfolioSetup.BREAKOUT,
                reason=PortfolioSetupReason.BREAKOUT_FROM_OPENING_RANGE_AGREEMENT,
            )
        if (
            event_15 is BreakoutEvent.DOWNSIDE_BREAKDOWN_EVENT
            and event_30 is BreakoutEvent.DOWNSIDE_BREAKDOWN_EVENT
        ):
            return self._classified(
                instrument_id=instrument_id,
                session_date=session_date,
                analysis_as_of=analysis_as_of,
                latest_completed_m5_slot=latest_completed_m5_slot,
                or15=window_15,
                or30=window_30,
                setup=PortfolioSetup.BREAKDOWN,
                reason=PortfolioSetupReason.BREAKDOWN_FROM_OPENING_RANGE_AGREEMENT,
            )
        if event_15 is not None or event_30 is not None:
            return self._classified(
                instrument_id=instrument_id,
                session_date=session_date,
                analysis_as_of=analysis_as_of,
                latest_completed_m5_slot=latest_completed_m5_slot,
                or15=window_15,
                or30=window_30,
                setup=None,
                reason=PortfolioSetupReason.SINGLE_WINDOW_ONLY,
            )
        return self._classified(
            instrument_id=instrument_id,
            session_date=session_date,
            analysis_as_of=analysis_as_of,
            latest_completed_m5_slot=latest_completed_m5_slot,
            or15=window_15,
            or30=window_30,
            setup=None,
            reason=PortfolioSetupReason.NOT_PRESENT,
        )

    @staticmethod
    def _classified(
        *,
        instrument_id: str,
        session_date: date,
        analysis_as_of: datetime,
        latest_completed_m5_slot: datetime | None,
        or15: PortfolioSetupWindowEvidence,
        or30: PortfolioSetupWindowEvidence,
        setup: PortfolioSetup | None,
        reason: PortfolioSetupReason,
    ) -> PortfolioSetupEvidence:
        return PortfolioSetupEvidence(
            setup=setup,
            reason=reason,
            instrument_id=instrument_id,
            session_date=session_date,
            analysis_as_of=analysis_as_of,
            evidence_as_of=analysis_as_of,
            latest_completed_m5_slot=latest_completed_m5_slot,
            is_coherent=True,
            or15=or15,
            or30=or30,
        )

    @staticmethod
    def _eligible_candles(
        candles: Sequence[Candle], *, timeframe: Timeframe, as_of: datetime
    ) -> list[Candle]:
        return [
            candle
            for candle in candles
            if candle.timeframe is timeframe and candle.ts_open <= as_of
        ]

    @staticmethod
    def _active_event(evidence: OpeningRangeEvidence) -> BreakoutEvent | None:
        if evidence.breakout_event in (
            BreakoutEvent.UPSIDE_BREAKOUT_EVENT,
            BreakoutEvent.DOWNSIDE_BREAKDOWN_EVENT,
        ):
            return evidence.breakout_event
        return None

    @staticmethod
    def _is_conflict(
        event_15: BreakoutEvent | None,
        event_30: BreakoutEvent | None,
    ) -> bool:
        if event_15 is None or event_30 is None:
            return False
        return event_15 is not event_30

    @staticmethod
    def _window(evidence: OpeningRangeEvidence) -> PortfolioSetupWindowEvidence:
        return PortfolioSetupWindowEvidence(
            status=evidence.formation.status,
            event=evidence.breakout_event,
            returned_inside_range=evidence.returned_inside_range,
            first_event_ts=evidence.first_breakout_ts,
        )

    @staticmethod
    def _or_evidence_is_coherent(
        instrument_id: str,
        session_date: date,
        analysis_as_of: datetime,
        windows: Sequence[OpeningRangeEvidence],
    ) -> bool:
        return all(
            evidence.instrument_id == instrument_id
            and evidence.session_date == session_date
            and evidence.as_of == analysis_as_of
            for evidence in windows
        )

    @staticmethod
    def _unavailable(
        instrument_id: str,
        session_date: date | None,
    ) -> PortfolioSetupEvidence:
        return PortfolioSetupEvidence(
            setup=None,
            reason=PortfolioSetupReason.EVIDENCE_UNAVAILABLE,
            instrument_id=instrument_id,
            session_date=session_date,
            analysis_as_of=None,
            evidence_as_of=None,
            latest_completed_m5_slot=None,
            is_coherent=False,
            or15=None,
            or30=None,
        )

    @staticmethod
    def _stale(
        instrument_id: str,
        session_date: date,
        analysis_as_of: datetime,
    ) -> PortfolioSetupEvidence:
        return PortfolioSetupEvidence(
            setup=None,
            reason=PortfolioSetupReason.EVIDENCE_STALE,
            instrument_id=instrument_id,
            session_date=session_date,
            analysis_as_of=analysis_as_of,
            evidence_as_of=None,
            latest_completed_m5_slot=None,
            is_coherent=False,
            or15=None,
            or30=None,
        )

    @staticmethod
    def _incoherent(
        instrument_id: str,
        session_date: date,
        analysis_as_of: datetime,
    ) -> PortfolioSetupEvidence:
        return PortfolioSetupEvidence(
            setup=None,
            reason=PortfolioSetupReason.EVIDENCE_INCOHERENT,
            instrument_id=instrument_id,
            session_date=session_date,
            analysis_as_of=analysis_as_of,
            evidence_as_of=None,
            latest_completed_m5_slot=None,
            is_coherent=False,
            or15=None,
            or30=None,
        )
