"""Gap Context (ID-5C).

Answers: "how did this instrument open today relative to the previous
settled trading session's close?" — descriptive only, never "should I
enter." A session-open PRICE TRANSITION measurement
(previous trading-session close -> current session open), not an
intraday-return measurement (that is `RelativeStrengthContext`'s job,
which measures FROM the current open onward) and not a gap-fill/-hold/
-rejection/-continuation judgement (none of those exist here — this stops
at the session-open transition itself).

Reuses, never duplicates:
- `athena.data.validation.calendar_expectations.latest_trading_day_on_or_before`
  (already used by gap/session-freshness validation elsewhere) to resolve
  the immediately preceding trading session — correctly handles weekends,
  holidays, and multi-day closures via the real calendar, never hardcoded
  weekday arithmetic.
- The existing daily (`D1`) candle series every instrument already has
  fetched once per cycle (`OwnerValidationPipeline.run`'s own
  `list_candles_recent(..., Timeframe.D1, ...)`) for the previous
  session's close AND the current session's open — no new repository
  read, no M5 dependency of any kind (so this is independent of ID-5B's
  still-open current-session M5 semantics question by construction, not
  by convention).

Pure, immutable, explainable (ADR-005). No BUY/SELL, no probability, no
magnitude-threshold label (`GAP_UP`/`GAP_DOWN`/`FLAT` only — a zero-
threshold sign read, matching the raw `gap_pct`; no SMALL/LARGE/
SIGNIFICANT band anywhere).
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime
from decimal import Decimal
from enum import Enum, unique


@unique
class GapDirection(str, Enum):
    """Zero-threshold sign-of-`gap_pct` direction — no magnitude band.
    Presentation-layer/EM-internal gap conventions elsewhere in ATHENA are
    NOT imported into this contract; only the sign of the raw percentage."""

    GAP_UP = "GAP_UP"
    GAP_DOWN = "GAP_DOWN"
    FLAT = "FLAT"
    UNKNOWN = "UNKNOWN"


@dataclass(frozen=True, slots=True)
class GapContext:
    """Session-open price-transition evidence for one instrument — NOT a
    scoring input, NOT a Decision gate, NOT gap-fill/-hold/-rejection/
    -continuation. Fixed for the entire session once both authoritative
    prices exist (previous close never changes retroactively; the
    current session's own open, once traded, is a historical fact) — it
    cannot change because price moves later, VWAP changes, ORB completes,
    or later M5 bars (canonical or off-grid) arrive."""

    instrument_id: str
    session_date: date
    as_of: datetime

    previous_session_date: date | None
    previous_session_close: Decimal | None
    current_session_open: Decimal | None

    gap_pct: Decimal | None
    direction: GapDirection
    available: bool

    explanation: str

    def __post_init__(self) -> None:
        if not self.instrument_id:
            raise ValueError("GapContext.instrument_id is mandatory")
        if self.as_of.tzinfo is None:
            raise ValueError("GapContext.as_of must be timezone-aware")
        if not self.explanation:
            raise ValueError("GapContext.explanation is mandatory (ADR-005)")
