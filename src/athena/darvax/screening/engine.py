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

from collections.abc import Iterable, Mapping, Sequence
from dataclasses import replace
from decimal import Decimal

from athena.darvax.positions.models import DarvaxPosition
from athena.darvax.screening.models import (
    _ACTION_BY_STATE,
    _TIER_BY_STATE,
    DarvaxAction,
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


def action_for(signal_type: DarvaxSignalType) -> DarvaxAction:
    """Map a structural state onto the action it implies (DX-7a).

    Raises on an unknown state for the same reason :func:`tier_for` does, but
    the stakes are higher: an unmapped state defaulting to ``ENTER`` would
    propose risking money on a state nobody classified.
    """
    try:
        return _ACTION_BY_STATE[signal_type]
    except KeyError as exc:  # pragma: no cover - guards a future enum addition
        raise AthenaError(
            f"no action defined for signal type {signal_type!r}; add it to "
            "_ACTION_BY_STATE rather than letting it default"
        ) from exc


def action_for_held(
    signal: DarvaxSignal, *, stop_price: Decimal | None
) -> tuple[DarvaxAction, str, str]:
    """Action and reason for an instrument the owner **holds** (DX-7b).

    Every branch is the DAR-CARD text applied literally, in the order the rules
    take precedence. Nothing here is invented:

    * **stop breached** — rule B mandates the stop (*"A 10 percent stop-loss
      should be set on the first breakout"*), so a close at or under it is an
      exit regardless of what the box is doing.
    * **rule C** — *"if the price falls below the bottom … the stock is a SELL."*
    * **rule D** — *"There is no reason to HOLD or BUY a stock that is not in
      its topmost box."* A held instrument that has fallen out of its topmost
      box is therefore an exit, not a wait.
    * **rule A** — *"…its price fluctuations should be ignored and the stock is
      a HOLD."*

    A breakout on an instrument already held stays ``HOLD``. Darvas did pyramid
    into new boxes, but the DAR-CARD does not say so and DarvaX must not invent
    add-to-position advice the deck never states (ADR-010).

    Returns ``(action, technical_reason, plain_reason)``. The plain sentence is
    produced here rather than delegated because these branches are specific —
    "your stop was hit" and "it left its range" are different news to a holder,
    and a generic sentence would flatten them (DX-8a).
    """
    if stop_price is not None and signal.close <= stop_price:
        return (
            DarvaxAction.EXIT,
            f"Closed at {_money(signal.close)}, at or below the stop "
            f"{_money(stop_price)} — rule B's mandated stop-loss.",
            f"Price fell to {_money(signal.close)}, through your stop at "
            f"{_money(stop_price)}. Time to close it.",
        )

    state = signal.signal_type
    if state is DarvaxSignalType.BELOW_BOX_BOTTOM:
        return (
            DarvaxAction.EXIT,
            f"Fell below the box floor at {_money(signal.box_bottom)} — rule C: "
            f'"if the price falls below the bottom … the stock is a SELL."',
            f"Price dropped below {_money(signal.box_bottom)}, the floor of its "
            f"range. Time to close it.",
        )
    if state in (DarvaxSignalType.NOT_IN_TOPMOST_BOX, DarvaxSignalType.NO_BOX):
        return (
            DarvaxAction.EXIT,
            'No longer in its topmost box — rule D: "There is no reason to HOLD '
            'or BUY a stock that is not in its topmost box."',
            "It has fallen out of the range it was climbing. The method says "
            "close it.",
        )
    if state is DarvaxSignalType.INSIDE_TOPMOST_BOX:
        stop = (
            f" Stop stands at {_money(stop_price)}." if stop_price is not None else ""
        )
        plain_stop = (
            f" Your stop is {_money(stop_price)}." if stop_price is not None else ""
        )
        return (
            DarvaxAction.HOLD,
            f"Still inside its topmost box — rule A: price fluctuations should "
            f"be ignored while it remains there.{stop}",
            f"Holding up well inside its range. Nothing to do.{plain_stop}",
        )
    # BREAKOUT / BREAKOUT_RETEST while already held.
    return (
        DarvaxAction.HOLD,
        f"Cleared {_money(signal.box_top)} into a new box — a rule B buy signal, "
        f"but this is already held, so rule A applies: hold while it remains in "
        f"its topmost box.",
        f"Pushed above {_money(signal.box_top)} into new highs. You already own "
        f"it — keep holding.",
    )


def _money(value: Decimal | None) -> str:
    return f"₹{value:,}" if value is not None else "an unrecorded level"


#: Prose rounding for percentages. The stored field keeps `_PCT`'s four places
#: because ranking sorts on it; a sentence does not. A real screen produced
#: "1.3333% below the box ceiling", which reads as measured precision that a
#: distance-to-a-price simply does not have.
_PROSE_PCT = Decimal("0.01")


def _percent(value: Decimal) -> str:
    return f"{abs(value).quantize(_PROSE_PCT)}%"


def action_reason(
    signal: DarvaxSignal,
    action: DarvaxAction,
    *,
    breakout_pct: Decimal | None,
    breakout_ref: str | None,
) -> str:
    """Plain-language justification for ``action``, with the numbers behind it.

    Built here, beside the rule that chose the action, and persisted with it —
    ADR-005. The alternative, assembling this sentence in the browser, lets the
    words drift from the rule while still looking authoritative.

    Every branch names the DAR-CARD rule, so a reader can always trace advice
    back to the methodology rather than to DarvaX's phrasing.
    """
    if action is DarvaxAction.ENTER:
        trigger = (
            f" Entry trigger is {_money(signal.trigger_price)}, the prior day's high."
            if signal.trigger_price is not None
            else ""
        )
        return (
            f"Cleared the topmost box ceiling at {_money(signal.box_top)} — "
            f"Darvas rule B, a buy signal.{trigger}"
        )
    if action is DarvaxAction.ENTER_ON_RETEST:
        return (
            f"Broke out above {_money(signal.box_top)} and has come back to test "
            f"that ceiling as support — rule B, on the retest."
        )
    if action is DarvaxAction.WAIT:
        if breakout_pct is not None:
            where = (
                "already through"
                if breakout_pct < 0
                else f"{_percent(breakout_pct)} below"
            )
            level = "the entry trigger" if breakout_ref == "trigger_price" else "the box ceiling"
            return (
                f"Consolidating inside the topmost box — rule A. Price is {where} "
                f"{level} at {_money(signal.box_top)}; nothing to do until it clears."
            )
        return (
            "Consolidating inside the topmost box — rule A. Nothing to do until "
            "price clears the ceiling."
        )
    if action is DarvaxAction.EXIT_IF_HELD:
        return (
            f"Closed beneath the box floor at {_money(signal.box_bottom)} — "
            f"rule C, the methodology's own exit. Relevant only if this is held."
        )
    return (
        "No topmost box to trade — rule D. Neither an entry nor an exit follows "
        "from the current structure."
    )


def plain_reason(
    signal: DarvaxSignal,
    action: DarvaxAction,
    *,
    breakout_pct: Decimal | None,
) -> str:
    """The same conclusion as :func:`action_reason`, in plain English (DX-8a).

    **Names no rule and no Darvas vocabulary.** "Topmost box", "rule B" and
    "DAR-CARD" are precise and are not English; the reader who wants them has
    ``action_reason`` and ``explanation`` one disclosure away.

    Kept beside the technical version, and called from the same place, because
    two sentences about one trade are only safe while nothing can produce one
    without the other.
    """
    if action is DarvaxAction.ENTER:
        where = (
            f" Buy above {_money(signal.trigger_price)}."
            if signal.trigger_price is not None
            else ""
        )
        return f"Price broke above its recent high range.{where}"
    if action is DarvaxAction.ENTER_ON_RETEST:
        return (
            f"Price broke out and has dipped back to test "
            f"{_money(signal.box_top)}, the level it cleared."
        )
    if action is DarvaxAction.WAIT:
        if breakout_pct is not None and breakout_pct > 0:
            return (
                f"Still inside its recent range, {_percent(breakout_pct)} below "
                f"the {_money(signal.box_top)} level it needs to clear."
            )
        return "Still inside its recent trading range — nothing to act on yet."
    if action is DarvaxAction.HOLD:
        return "Holding up inside its range. Nothing to do."
    if action is DarvaxAction.EXIT:
        return "Time to close this one."
    if action is DarvaxAction.EXIT_IF_HELD:
        return (
            f"Price dropped below {_money(signal.box_bottom)}, the floor of its "
            f"range. If you own this, the method says sell."
        )
    return "No clear pattern to trade right now."


def stop_vs_ceiling(
    signal: DarvaxSignal,
) -> tuple[Decimal | None, str]:
    """Where the stop lands relative to the level price broke out from (DX-9c).

    Returns ``(signed_delta, sentence)`` — positive when the stop is above the
    ceiling. ``(None, "")`` whenever either level is absent, which is every row
    that is not an entry: there is no stop for a trade nobody is in.

    **States a fact and attaches no advice.** The methodology says 10% below
    entry; this reports where that lands against a level the engine already
    recorded, because the same rule produces materially different trades:

    * stop **above** the ceiling — a stop-out still exits above the breakout;
    * stop **below** it — a stop-out gives the whole breakout back.

    Whether either is acceptable is the owner's judgement, not DarvaX's, so no
    branch here says "good" or "risky".
    """
    if signal.stop is None or signal.box_top is None:
        return None, ""
    delta = (signal.stop.price - signal.box_top).quantize(Decimal("0.01"))
    if delta == 0:
        return delta, (
            f"The stop sits exactly at the breakout level of "
            f"{_money(signal.box_top)}."
        )
    side = "above" if delta > 0 else "below"
    tail = (
        ""
        if delta > 0
        else " — a stop-out would give back the whole breakout"
    )
    return delta, (
        f"The stop sits {_money(abs(delta))} {side} the breakout level of "
        f"{_money(signal.box_top)}{tail}."
    )


def screen_signal(
    signal: DarvaxSignal,
    *,
    sweep_id: str,
    rank: int = 0,
    position: DarvaxPosition | None = None,
    liquidity: Decimal | None = None,
) -> ScreenResult:
    """Classify and measure one signal. ``rank`` is assigned by :func:`rank_tier`.

    ``position`` is **passed in, never looked up**. This module has no store and
    no IO by design — a screen is a deterministic reading of signals — so the
    caller resolves holdings once and hands them down. Reading the position
    store from here would make the screen depend on hidden state and stop it
    being replayable from its inputs.
    """
    breakout_pct, breakout_ref = distance_to_breakout(signal)
    vs_ceiling, vs_ceiling_note = stop_vs_ceiling(signal)
    if position is not None and position.is_open:
        action, reason, plain = action_for_held(
            signal, stop_price=position.stop_price
        )
    else:
        action = action_for(signal.signal_type)
        # Both sentences from one call site: nothing can produce a technical
        # reason without its plain counterpart (design decision 1b).
        reason = action_reason(
            signal, action, breakout_pct=breakout_pct, breakout_ref=breakout_ref
        )
        plain = plain_reason(signal, action, breakout_pct=breakout_pct)
    return ScreenResult(
        action=action,
        action_reason=reason,
        action_reason_plain=plain,
        # Copied from the signal, never recomputed — rule B mandates a stop and
        # the screener previously could not show one at all.
        stop_price=signal.stop.price if signal.stop else None,
        stop_basis=signal.stop.basis.value if signal.stop else None,
        stop_vs_ceiling=vs_ceiling,
        stop_vs_ceiling_note=vs_ceiling_note,
        # Passed in, never measured here: liquidity needs candles and this module
        # has no market-data access by design (the purity property DX-7b tests).
        liquidity_value=liquidity,
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
    """Order one tier's results and assign 1-based ranks.

    Uses ``replace`` rather than re-listing every field: the previous
    field-by-field rebuild meant any field added to ``ScreenResult`` was
    silently dropped during ranking unless someone remembered to add it here.
    ``action`` and ``action_reason`` would have been the first casualties.
    """
    ordered = sorted(results, key=_default_key)
    return tuple(
        replace(r, rank=position) for position, r in enumerate(ordered, start=1)
    )


def screen_signals(
    signals: Sequence[DarvaxSignal],
    *,
    sweep_id: str,
    positions: Mapping[str, DarvaxPosition] | None = None,
    liquidity: Mapping[str, Decimal] | None = None,
) -> tuple[ScreenResult, ...]:
    """Screen a batch of signals: classify, measure, then rank within each tier.

    Returned in tier precedence order, ranked within each tier. Ranks are
    per-tier, so the first ACTIONABLE and the first WATCH are both rank 1.

    ``positions`` maps ``instrument_id`` to an open holding. Defaulting to
    ``None`` keeps every existing caller — and every sweep run before DX-7b —
    behaving exactly as it did.
    """
    held = positions or {}
    liq = liquidity or {}
    screened = [
        screen_signal(
            s,
            sweep_id=sweep_id,
            position=held.get(s.instrument_id),
            liquidity=liq.get(s.instrument_id),
        )
        for s in signals
    ]
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
