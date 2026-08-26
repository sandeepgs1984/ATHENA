"""Real-provider canary gate for EM-1r3 production intraday capture.

Owner-mandated 2026-08-24, after the 2026-08-22 production sweep ran to
completion (~49 hours, real Kite quota) against a defective provider
boundary and produced zero usable admitted sessions -- a systemic defect
that a cheap, real, small-scale check would have caught in seconds instead
of two days. The rule going forward (see CLAUDE.md): every expensive
external-data-provider operation must pass a real-provider canary with an
explicit admission/quality threshold and automatic fail-fast before
scaling out to the full run.

This canary makes a small number of real Kite API calls -- a handful of
liquid instruments across a handful of representative dates spanning the
study window -- and requires the *genuinely-complete* dates to admit at a
high rate before the full cohort capture is allowed to proceed. It never
penalizes the known, separately-diagnosed recent-history-truncation tail
(that is real, expected, and reported for visibility, not as a failure
signal) -- the threshold exists to catch systemic defects (like the
2026-08-22 incident, which showed ~0% admission), not to demand perfection
on a data source with a documented recent-tail limitation.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, timedelta

from athena.calendar.engine import CalendarEngine
from athena.data.intraday_reconstruction_ingestion import (
    IntradayReconstructionIngestionService,
)
from athena.domain.enums import SessionType

#: Below this admission rate on genuinely-complete (non-recent-tail) canary
#: sessions, treat the provider as systemically defective and refuse to
#: proceed. Set below 100% to tolerate a rare, isolated real network
#: hiccup -- the 2026-08-22 incident showed ~0%, nowhere near this line.
MIN_HISTORICAL_ADMISSION_RATE = 0.8

_CAPTURABLE_SESSION_TYPES = (SessionType.NORMAL, SessionType.SPECIAL)


@dataclass(frozen=True)
class CanarySessionOutcome:
    session_date: date
    is_recent_tail: bool
    requested: int
    admitted: int


@dataclass(frozen=True)
class CanaryResult:
    outcomes: tuple[CanarySessionOutcome, ...]
    historical_requested: int
    historical_admitted: int
    recent_tail_requested: int
    recent_tail_admitted: int
    threshold: float = MIN_HISTORICAL_ADMISSION_RATE

    @property
    def historical_admission_rate(self) -> float:
        if self.historical_requested == 0:
            return 0.0
        return self.historical_admitted / self.historical_requested

    @property
    def passed(self) -> bool:
        return self.historical_requested > 0 and self.historical_admission_rate >= self.threshold

    def to_dict(self) -> dict:
        return {
            "passed": self.passed,
            "threshold": self.threshold,
            "historical_admission_rate": round(self.historical_admission_rate, 4),
            "historical_requested": self.historical_requested,
            "historical_admitted": self.historical_admitted,
            "recent_tail_requested": self.recent_tail_requested,
            "recent_tail_admitted": self.recent_tail_admitted,
            "outcomes": [
                {
                    "session_date": o.session_date.isoformat(),
                    "is_recent_tail": o.is_recent_tail,
                    "requested": o.requested,
                    "admitted": o.admitted,
                }
                for o in self.outcomes
            ],
        }


def canary_dates(calendar: CalendarEngine, study_start: date, study_end: date) -> dict[date, bool]:
    """Representative dates -> is_recent_tail, walked to the nearest
    capturable session so a canary never lands on a weekend/holiday.

    Covers: the oldest date in the window (must be fully admittable),
    a mid-window date (same), and the newest date in the window (the
    known recent-truncation tail -- tracked, never penalized). A caller
    may pass additional fixed dates (e.g. a known SPECIAL full-session
    day) via `extra_dates`.
    """

    def _walk_to_capturable(start: date, step: int, bound: date) -> date | None:
        cursor = start
        while (step > 0 and cursor <= bound) or (step < 0 and cursor >= bound):
            if calendar.context_for(cursor).session_type in _CAPTURABLE_SESSION_TYPES:
                return cursor
            cursor += timedelta(days=step)
        return None

    midpoint = study_start + (study_end - study_start) // 2
    dates: dict[date, bool] = {}

    oldest = _walk_to_capturable(study_start, 1, study_end)
    if oldest is not None:
        dates[oldest] = False

    mid = _walk_to_capturable(midpoint, 1, study_end)
    if mid is not None and mid not in dates:
        dates[mid] = False

    newest = _walk_to_capturable(study_end, -1, study_start)
    if newest is not None and newest not in dates:
        dates[newest] = True  # the known recent-history-truncation tail

    return dates


def run_canary(
    *,
    service: IntradayReconstructionIngestionService,
    calendar: CalendarEngine,
    instrument_ids: tuple[str, ...],
    study_start: date,
    study_end: date,
    extra_dates: dict[date, bool] | None = None,  # date -> is_recent_tail
) -> CanaryResult:
    """Run a small, real capture over a handful of dates and instruments,
    and report whether the provider is admitting genuinely-complete
    sessions at a healthy rate. Raises nothing -- callers decide what to
    do with a failed `CanaryResult` (the CLI fails fast and refuses to
    launch the full sweep)."""

    dates = dict(canary_dates(calendar, study_start, study_end))
    dates.update(extra_dates or {})

    outcomes = []
    for session_date, is_recent_tail in sorted(dates.items()):
        result = service.capture(
            cohort=_canary_cohort(instrument_ids, session_date),
            study_start=session_date,
            study_end=session_date,
        )
        outcomes.append(
            CanarySessionOutcome(
                session_date=session_date,
                is_recent_tail=is_recent_tail,
                requested=len(result.manifest.sessions),
                admitted=result.manifest.admitted_session_count,
            )
        )

    historical = [o for o in outcomes if not o.is_recent_tail]
    recent = [o for o in outcomes if o.is_recent_tail]
    return CanaryResult(
        outcomes=tuple(outcomes),
        historical_requested=sum(o.requested for o in historical),
        historical_admitted=sum(o.admitted for o in historical),
        recent_tail_requested=sum(o.requested for o in recent),
        recent_tail_admitted=sum(o.admitted for o in recent),
    )


def _canary_cohort(instrument_ids: tuple[str, ...], resolution_date: date):
    from athena.explosive_move.corporate_action_coverage import (
        SURVIVOR_COHORT_LIMITATION,
        SURVIVOR_COHORT_NAME,
        SurvivorCohort,
    )

    return SurvivorCohort(
        name=SURVIVOR_COHORT_NAME,
        universe_name="em1r3_canary",
        resolution_date=resolution_date,
        instrument_ids=tuple(sorted(set(instrument_ids))),
        group_effective_dates=(("em1r3_canary", resolution_date),),
        limitation=SURVIVOR_COHORT_LIMITATION,
    )
