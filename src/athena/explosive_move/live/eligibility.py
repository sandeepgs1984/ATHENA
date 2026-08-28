"""EM-5 candidate eligibility -- hard vs. contextual, exactly per
`docs/design/EM-5-LIVE-SCANNER-CONTRACT.md` Section 4 (Blocker 4,
corrected and Owner-approved). `UNKNOWN` on a hard input excludes a
candidate; `UNKNOWN` on a contextual input never does -- it is
persisted honestly and the candidate stays scored and ranked.

Pure: no I/O, no clock, no fabricated defaults. Every input this module
needs is supplied by the caller (the scan orchestration layer), which
is the only place that talks to `EmrMarketDataPort`, the calendar
engine, or the checkpoint-reference-price collector.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from enum import Enum

from athena.domain.enums import SessionType

#: The one place EM-5 decides which session types are real trading
#: data worth scanning -- mirrors EM-1r3's own already-established
#: `_CAPTURABLE_SESSION_TYPES` (`em1r3_production_capture_cli.py`,
#: `em1r3_production_canary.py`): NORMAL and SPECIAL only. MUHURAT is
#: deliberately excluded (a short, symbolic evening session, not
#: comparable intraday liquidity), matching the "Muhurat/truncated
#: sessions excluded from scanning entirely" contract requirement.
SCANNABLE_SESSION_TYPES: frozenset[SessionType] = frozenset({SessionType.NORMAL, SessionType.SPECIAL})


class HardIneligibilityReason(str, Enum):
    NOT_IN_UNIVERSE = "NOT_IN_UNIVERSE"
    STALE_DATA = "STALE_DATA"
    NO_OBSERVABLE_PRICE_AT_CHECKPOINT = "NO_OBSERVABLE_PRICE_AT_CHECKPOINT"
    PRICE_BAND_IMPOSSIBLE = "PRICE_BAND_IMPOSSIBLE"


class Feasibility(str, Enum):
    FEASIBLE = "FEASIBLE"
    FEASIBILITY_UNKNOWN = "FEASIBILITY_UNKNOWN"
    PRICE_BAND_IMPOSSIBLE = "PRICE_BAND_IMPOSSIBLE"


@dataclass(frozen=True, slots=True)
class PriceBand:
    """An authoritative reachable-price band for the remainder of the
    session (e.g. exchange circuit limits). No source of this exists
    anywhere in ATHENA today (confirmed: no circuit-limit/price-band
    provider is implemented) -- this type exists so eligibility's 3-way
    rule is already correct the day one is wired in, without EM-5
    fabricating a data source that does not exist yet. Until then,
    every candidate's `price_band` is `None` and feasibility is
    honestly `FEASIBILITY_UNKNOWN` for all of EM-5 v1."""

    lower_limit: Decimal
    upper_limit: Decimal


@dataclass(frozen=True, slots=True)
class EligibilityResult:
    hard_eligible: bool
    hard_ineligible_reason: HardIneligibilityReason | None
    feasibility: Feasibility


def session_is_scannable(session_type: SessionType) -> bool:
    return session_type in SCANNABLE_SESSION_TYPES


def _evaluate_feasibility(price_band: PriceBand | None, target_price: Decimal | None) -> Feasibility:
    if price_band is None or target_price is None:
        return Feasibility.FEASIBILITY_UNKNOWN
    if target_price > price_band.upper_limit:
        return Feasibility.PRICE_BAND_IMPOSSIBLE
    return Feasibility.FEASIBLE


def evaluate_candidate_eligibility(
    *,
    in_universe: bool,
    most_recent_candle_ts: datetime | None,
    as_of: datetime,
    max_staleness_minutes: float,
    has_checkpoint_reference_price: bool,
    price_band: PriceBand | None = None,
    target_price: Decimal | None = None,
) -> EligibilityResult:
    """One candidate's hard/contextual eligibility at one checkpoint.

    `max_staleness_minutes` is supplied by the caller (config-driven,
    e.g. `config/emr/scanner_thresholds.json`), never a number picked
    inside this module -- what counts as "stale" is an operational
    tuning knob, not evidence.
    """

    if not in_universe:
        return EligibilityResult(False, HardIneligibilityReason.NOT_IN_UNIVERSE, Feasibility.FEASIBILITY_UNKNOWN)

    if most_recent_candle_ts is None:
        return EligibilityResult(False, HardIneligibilityReason.STALE_DATA, Feasibility.FEASIBILITY_UNKNOWN)
    staleness_minutes = (as_of - most_recent_candle_ts).total_seconds() / 60.0
    if staleness_minutes > max_staleness_minutes:
        return EligibilityResult(False, HardIneligibilityReason.STALE_DATA, Feasibility.FEASIBILITY_UNKNOWN)

    if not has_checkpoint_reference_price:
        return EligibilityResult(
            False, HardIneligibilityReason.NO_OBSERVABLE_PRICE_AT_CHECKPOINT, Feasibility.FEASIBILITY_UNKNOWN
        )

    feasibility = _evaluate_feasibility(price_band, target_price)
    if feasibility is Feasibility.PRICE_BAND_IMPOSSIBLE:
        return EligibilityResult(False, HardIneligibilityReason.PRICE_BAND_IMPOSSIBLE, feasibility)

    return EligibilityResult(True, None, feasibility)
