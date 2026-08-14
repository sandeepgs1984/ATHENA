"""Screening engine (DX-6a, ADR-010 Amendment 2).

Pure functions over already-computed :class:`DarvaxSignal` objects. No clock, no
config, no IO, no market-data access — a screen is a deterministic reading of
signals the DX-3 engine already produced, so the same signals always yield the
same screen.

**No new methodology.** Nothing here builds a box, evaluates a stop, or decides
a state. It classifies what DX-3 concluded and measures two quantities from
fields DX-3 already persisted.

## Why only two ranking quantities

The approved design named four: distance-to-trigger, box height, bars-in-box,
and volume expansion. Only the first two are derivable from a stored signal —
``DarvaxSignal`` carries ``close``, ``trigger_price``, ``box_top`` and
``box_bottom`` as structured fields, but records neither bars-in-box nor volume
expansion. (The signal's evidence trace holds ``bars_examined``, which is the
lookback window size, not time spent inside the box.)

The two missing quantities would require extending the DX-3 engine to measure
and persist them — a change to an approved milestone, needing its own approval,
and one that could not backfill signals stored before it. They are therefore
**deferred rather than faked**: parsing them out of evidence prose, or
recomputing them here from candles this module deliberately cannot see, would
both be worse than shipping the two that are exact.
"""

from __future__ import annotations

from collections.abc import Iterable, Sequence
from decimal import Decimal

from athena.darvax.screening.models import (
    _TIER_BY_STATE,
    DarvaxTier,
    ScreenResult,
)
from athena.darvax.signals.models import DarvaxSignal, DarvaxSignalType
from athena.errors import AthenaError

#: Tier display/ordering precedence: what can be acted on comes first, then what
#: is worth watching, then what only matters if held. Mirrors how the screen is
#: read — "is there anything to act on?" is always the first question.
TIER_ORDER: tuple[DarvaxTier, ...] = (
    DarvaxTier.ACTIONABLE,
    DarvaxTier.WATCH,
    DarvaxTier.EXIT_RELEVANT,
    DarvaxTier.NOT_ELIGIBLE,
)

_HUNDRED = Decimal(100)


def tier_for(signal_type: DarvaxSignalType) -> DarvaxTier:
    """Map a structural state onto its eligibility tier.

    Raises rather than defaulting on an unknown state: a new signal type must be
    classified deliberately, not silently swept into NOT_ELIGIBLE where it would
    disappear from the screen without anyone noticing.
    """
    try:
        return _TIER_BY_STATE[signal_type]
    except KeyError as exc:  # pragma: no cover - guards a future enum addition
        raise AthenaError(
            f"no screening tier defined for signal type {signal_type!r}; "
            "add it to _TIER_BY_STATE rather than letting it default"
        ) from exc


def distance_to_trigger_pct(signal: DarvaxSignal) -> Decimal | None:
    """How far price is from its entry trigger, as a percentage of close.

    The trigger is the prior bar's high (deck p.44, "Enter above the Previous
    Day High Price"), already persisted on the signal. A negative result means
    price is *through* the trigger, which is information, not an error.
    """
    if signal.trigger_price is None or signal.close <= 0:
        return None
    return (signal.trigger_price - signal.close) / signal.close * _HUNDRED


def box_height_pct(signal: DarvaxSignal) -> Decimal | None:
    """Box height as a percentage of its floor — Darvas favoured tight boxes."""
    if signal.box_top is None or signal.box_bottom is None:
        return None
    if signal.box_bottom <= 0:
        return None
    return (signal.box_top - signal.box_bottom) / signal.box_bottom * _HUNDRED


def screen_signal(signal: DarvaxSignal, *, sweep_id: str, rank: int = 0) -> ScreenResult:
    """Classify and measure one signal. ``rank`` is assigned by :func:`rank_tier`."""
    return ScreenResult(
        sweep_id=sweep_id,
        instrument_id=signal.instrument_id,
        signal_id=signal.signal_id,
        tier=tier_for(signal.signal_type),
        signal_type=signal.signal_type,
        darvas_rule=signal.darvas_rule,
        rank=rank,
        close=signal.close,
        explanation=signal.explanation,
        box_top=signal.box_top,
        box_bottom=signal.box_bottom,
        trigger_price=signal.trigger_price,
        distance_to_trigger_pct=distance_to_trigger_pct(signal),
        box_height_pct=box_height_pct(signal),
    )


def _default_key(result: ScreenResult) -> tuple[int, Decimal, str]:
    """Default ordering key within a tier.

    Ascending ``distance_to_trigger_pct`` — closest to breaking out, first —
    because that answers the question the tier poses. Results with no trigger
    sort last rather than being treated as distance zero, which would put them
    at the top of the screen for a value they do not have. ``instrument_id``
    breaks ties so the order is total and therefore deterministic.
    """
    if result.distance_to_trigger_pct is None:
        return (1, Decimal(0), result.instrument_id)
    return (0, result.distance_to_trigger_pct, result.instrument_id)


def rank_tier(results: Iterable[ScreenResult]) -> tuple[ScreenResult, ...]:
    """Order one tier's results and assign 1-based ranks."""
    ordered = sorted(results, key=_default_key)
    return tuple(
        ScreenResult(
            sweep_id=r.sweep_id,
            instrument_id=r.instrument_id,
            signal_id=r.signal_id,
            tier=r.tier,
            signal_type=r.signal_type,
            darvas_rule=r.darvas_rule,
            rank=position,
            close=r.close,
            explanation=r.explanation,
            box_top=r.box_top,
            box_bottom=r.box_bottom,
            trigger_price=r.trigger_price,
            distance_to_trigger_pct=r.distance_to_trigger_pct,
            box_height_pct=r.box_height_pct,
        )
        for position, r in enumerate(ordered, start=1)
    )


def screen_signals(
    signals: Sequence[DarvaxSignal], *, sweep_id: str
) -> tuple[ScreenResult, ...]:
    """Screen a batch of signals: classify, measure, then rank within each tier.

    Returned in tier precedence order, ranked within each tier. Ranks are
    per-tier, so the first ACTIONABLE and the first WATCH are both rank 1.
    """
    screened = [screen_signal(s, sweep_id=sweep_id) for s in signals]
    output: list[ScreenResult] = []
    for tier in TIER_ORDER:
        output.extend(rank_tier(r for r in screened if r.tier is tier))
    return tuple(output)


def tier_counts(results: Iterable[ScreenResult]) -> dict[DarvaxTier, int]:
    """Count per tier, with every tier present — including the empty ones.

    A missing key would render as a blank where the screen should say zero, and
    "no actionable names today" is a real answer the owner needs to see stated.
    """
    counts = dict.fromkeys(TIER_ORDER, 0)
    for result in results:
        counts[result.tier] += 1
    return counts
