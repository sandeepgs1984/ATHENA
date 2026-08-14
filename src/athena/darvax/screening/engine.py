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

#: Percentages are quantised before they are persisted or shown. Decimal
#: division yields 28 significant digits — a real screen was emitting
#: ``10.44041450777202072538860104`` for a box height, which reads as precision
#: the measurement does not have. Four places is well past anything actionable
#: on a percentage while staying exact enough to sort on.
_PCT = Decimal("0.0001")


def _pct(numerator: Decimal, denominator: Decimal) -> Decimal | None:
    if denominator <= 0:
        return None
    return (numerator / denominator * _HUNDRED).quantize(_PCT)


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
    if signal.trigger_price is None:
        return None
    return _pct(signal.trigger_price - signal.close, signal.close)


def distance_to_breakout(signal: DarvaxSignal) -> tuple[Decimal | None, str | None]:
    """Distance to the level that would satisfy Darvas rule B, and which level.

    Prefers the deck's p.44 entry trigger when DX-3 recorded one, and otherwise
    falls back to the box ceiling. That fallback is the point: DX-3 only sets
    ``trigger_price`` alongside a stop, so every ``INSIDE_TOPMOST_BOX`` signal
    has none — and ranking the WATCH tier on the trigger alone left the entire
    breakout-candidate list sorted alphabetically, which is no ranking at all.

    Returns ``(percentage, reference)`` so the reference can be persisted and
    shown rather than inferred.
    """
    if signal.trigger_price is not None:
        return _pct(signal.trigger_price - signal.close, signal.close), "trigger_price"
    if signal.box_top is not None:
        return _pct(signal.box_top - signal.close, signal.close), "box_top"
    return None, None


def box_height_pct(signal: DarvaxSignal) -> Decimal | None:
    """Box height as a percentage of its floor — Darvas favoured tight boxes."""
    if signal.box_top is None or signal.box_bottom is None:
        return None
    return _pct(signal.box_top - signal.box_bottom, signal.box_bottom)


def screen_signal(signal: DarvaxSignal, *, sweep_id: str, rank: int = 0) -> ScreenResult:
    """Classify and measure one signal. ``rank`` is assigned by :func:`rank_tier`."""
    breakout_pct, breakout_ref = distance_to_breakout(signal)
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
        distance_to_breakout_pct=breakout_pct,
        breakout_reference=breakout_ref,
        box_height_pct=box_height_pct(signal),
    )


def _default_key(result: ScreenResult) -> tuple[int, Decimal, str]:
    """Default ordering key within a tier.

    Ascending ``distance_to_breakout_pct`` — closest to clearing the rule-B
    level, first — because that answers the question each tier poses. Uses
    distance-to-breakout rather than distance-to-trigger because DX-3 leaves the
    trigger unset for inside-the-box signals, which left the whole WATCH tier
    ordered alphabetically.

    Results with no measurable distance sort last rather than being treated as
    zero, which would put them at the top of the screen for a value they do not
    have. ``instrument_id`` breaks ties so the order is total and deterministic.
    """
    if result.distance_to_breakout_pct is None:
        return (1, Decimal(0), result.instrument_id)
    return (0, result.distance_to_breakout_pct, result.instrument_id)


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
            distance_to_breakout_pct=r.distance_to_breakout_pct,
            breakout_reference=r.breakout_reference,
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
