"""Authoritative freshness for persisted DarvaX daily sweeps (AUX-1b).

Freshness is a market-session fact, not a browser-clock guess.  This module is
pure apart from the injected Calendar Engine: callers provide the sweep, the
current methodology digest, and the reference time; the result is immutable
and directly serialisable by DarvaX's API.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import date, datetime, time, timedelta
from typing import Literal, Protocol
from zoneinfo import ZoneInfo

from athena.darvax.screening.models import SweepRecord
from athena.errors import CalendarError

DarvaxFreshnessStatus = Literal["CURRENT", "STALE", "UNAVAILABLE"]


class SessionTypePort(Protocol):
    """The one session-type value freshness needs from the host calendar."""

    value: str


class SessionContextPort(Protocol):
    """Read-only session facts consumed by the DarvaX freshness classifier."""

    is_trading_session: bool
    open_time: time | None
    close_time: time | None
    session_type: SessionTypePort


class DarvaxSessionCalendarPort(Protocol):
    """Minimal host calendar surface injected through the ADR-010 seam."""

    def context_for(self, session_date: date) -> SessionContextPort: ...


@dataclass(frozen=True, slots=True)
class DarvaxSweepFreshness:
    """One explainable freshness reading for the latest persisted sweep."""

    status: DarvaxFreshnessStatus
    headline: str
    explanation: str
    source: str = "darvax_sweep"
    observed_at: datetime | None = None
    age_seconds: int | None = None
    data_through: date | None = None
    expected_session: date | None = None
    market_session: str | None = None
    next_live_at: datetime | None = None
    sweep_state: str | None = None
    warnings: tuple[str, ...] = ()

    def to_payload(self) -> dict[str, object]:
        payload = asdict(self)
        for key in ("observed_at", "next_live_at"):
            value = payload[key]
            payload[key] = value.isoformat() if isinstance(value, datetime) else None
        for key in ("data_through", "expected_session"):
            value = payload[key]
            payload[key] = value.isoformat() if isinstance(value, date) else None
        payload["warnings"] = list(self.warnings)
        return payload


class DarvaxSweepFreshnessClassifier:
    """Classify daily sweep coverage against NSE's configured calendar."""

    def __init__(
        self,
        *,
        calendar: DarvaxSessionCalendarPort | None,
        timezone_name: str,
        setup_error: str | None = None,
    ) -> None:
        self._calendar = calendar
        self._timezone = ZoneInfo(timezone_name)
        self._setup_error = setup_error

    def classify(
        self,
        *,
        sweep: SweepRecord | None,
        current_methodology_digest: str,
        reference_time: datetime,
    ) -> DarvaxSweepFreshness:
        if reference_time.tzinfo is None:
            raise ValueError("reference_time must be timezone-aware")
        local_now = reference_time.astimezone(self._timezone)

        if self._calendar is None:
            return self._unavailable(
                sweep=sweep,
                explanation=self._setup_error
                or "The configured trading calendar could not be loaded.",
            )

        try:
            expected = self._latest_completed_session(local_now)
            next_live = self._next_live(local_now)
            context = self._calendar.context_for(local_now.date())
        except CalendarError as exc:
            return self._unavailable(sweep=sweep, explanation=str(exc))

        session_label = context.session_type.value
        if sweep is None:
            return DarvaxSweepFreshness(
                status="UNAVAILABLE",
                headline="No completed sweep yet",
                explanation=(
                    "Run the DarvaX screener to create the first persisted daily sweep."
                ),
                expected_session=expected,
                market_session=session_label,
                next_live_at=next_live,
            )

        warnings = self._integrity_warnings(sweep, current_methodology_digest)
        common = dict(
            observed_at=sweep.finished_at,
            age_seconds=self._age_seconds(sweep.finished_at, local_now),
            data_through=(
                sweep.as_of.astimezone(self._timezone).date()
                if sweep.as_of is not None and sweep.as_of.tzinfo is not None
                else None
            ),
            expected_session=expected,
            market_session=session_label,
            next_live_at=next_live,
            sweep_state=sweep.state,
            warnings=warnings,
        )

        if sweep.state not in {"completed", "cancelled"}:
            return DarvaxSweepFreshness(
                status="UNAVAILABLE",
                headline="Sweep freshness unavailable",
                explanation=(
                    f"The latest persisted sweep is {sweep.state}; only completed or "
                    "cancelled sweeps have stable daily coverage."
                ),
                **common,
            )
        if common["data_through"] is None:
            return DarvaxSweepFreshness(
                status="UNAVAILABLE",
                headline="Sweep coverage unavailable",
                explanation="The latest sweep has no timezone-aware market date.",
                **common,
            )
        if expected is None:
            return DarvaxSweepFreshness(
                status="UNAVAILABLE",
                headline="Expected session unavailable",
                explanation="No completed trading session exists in calendar coverage.",
                **common,
            )

        data_through = common["data_through"]
        if data_through < expected:
            return DarvaxSweepFreshness(
                status="STALE",
                headline=f"Stale · data through {data_through.strftime('%d %b %Y')}",
                explanation=(
                    "This sweep does not cover the latest completed trading session "
                    f"({expected.strftime('%d %b %Y')})."
                ),
                **common,
            )

        return DarvaxSweepFreshness(
            status="CURRENT",
            headline=f"Current · data through {data_through.strftime('%d %b %Y')}",
            explanation="This sweep covers the latest completed trading session.",
            **common,
        )

    def _latest_completed_session(self, local_now: datetime) -> date | None:
        for offset in range(0, 370):
            candidate = local_now.date() - timedelta(days=offset)
            context = self._calendar.context_for(candidate)  # type: ignore[union-attr]
            if not context.is_trading_session or context.close_time is None:
                continue
            close_at = datetime.combine(candidate, context.close_time, self._timezone)
            if close_at <= local_now:
                return candidate
        return None

    def _next_live(self, local_now: datetime) -> datetime | None:
        for offset in range(0, 370):
            candidate = local_now.date() + timedelta(days=offset)
            context = self._calendar.context_for(candidate)  # type: ignore[union-attr]
            if not context.is_trading_session or context.open_time is None:
                continue
            open_at = datetime.combine(candidate, context.open_time, self._timezone)
            if open_at > local_now:
                return open_at
        return None

    @staticmethod
    def _age_seconds(observed_at: datetime | None, now: datetime) -> int | None:
        if observed_at is None or observed_at.tzinfo is None:
            return None
        return max(0, int((now - observed_at).total_seconds()))

    @staticmethod
    def _integrity_warnings(
        sweep: SweepRecord, current_methodology_digest: str
    ) -> tuple[str, ...]:
        warnings: list[str] = []
        if sweep.partial or sweep.state == "cancelled":
            warnings.append("Partial coverage: the sweep was cancelled.")
        if sweep.methodology_digest != current_methodology_digest:
            warnings.append("Methodology changed after this sweep was produced.")
        if sweep.evaluated < sweep.requested:
            warnings.append(
                f"Coverage incomplete: evaluated {sweep.evaluated} of {sweep.requested}."
            )
        return tuple(warnings)

    def _unavailable(
        self, *, sweep: SweepRecord | None, explanation: str
    ) -> DarvaxSweepFreshness:
        return DarvaxSweepFreshness(
            status="UNAVAILABLE",
            headline="Sweep freshness unavailable",
            explanation=explanation,
            observed_at=sweep.finished_at if sweep else None,
            sweep_state=sweep.state if sweep else None,
        )


__all__ = [
    "DarvaxSessionCalendarPort",
    "DarvaxSweepFreshness",
    "DarvaxSweepFreshnessClassifier",
]
