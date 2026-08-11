"""DarvaX signal engine: box breakout / retest state machine (DX-3).

Evaluates where price stands relative to its **topmost** Darvas box at the final
bar of a series, and emits a :class:`DarvaxSignal` carrying its own computed
explanation and evidence trace.

**The reference box is the topmost box, not the latest completed one.** Darvas'
rules A, B and D are all phrased against "its topmost box", and using the most
recently completed box instead inverts the meaning whenever price has run above
every box it ever formed: a stock trading well clear of all its ceilings is in
the *strongest* Darvas condition, yet a latest-box reading would report rule D
("no reason to HOLD or BUY") simply because the last box to complete during a
pullback sat lower. Real-data check that caught this: TVSMOTOR closing 4398 with
its highest box ceiling at 3807.90.

State resolution, in strict priority order (each state cites the DAR-CARD rule
it corresponds to, deck p.67):

1. **NO_BOX** — no box has completed yet. Nothing can be said.
2. **BREAKOUT_RETEST** (rule B + deck p.28) — close above the *topmost* ceiling,
   and since the breakout price returned into the ceiling zone and still closed
   above it. The deck's #TRENT example: "Broke 400 Darvas / Retested it in July".
3. **BREAKOUT** (rule B) — close above the topmost ceiling, no retest yet.
4. **INSIDE_TOPMOST_BOX** (rule A) — within the topmost box; Darvas says
   fluctuation there should be ignored.
5. **BELOW_BOX_BOTTOM** (rule C) — close beneath the topmost box's floor while
   that box is also the most recently completed one, i.e. the "new higher box"
   whose bottom Darvas describes being broken.
6. **NOT_IN_TOPMOST_BOX** (rule D) — close beneath the topmost box's floor and a
   *different*, lower box has completed since: price has left the topmost box and
   is trading in lower territory.

Determinism and replayability (ADR-010 §10): the engine takes no clock. ``as_of``
is the final bar's own timestamp, ``signal_id`` is derived from instrument +
``as_of``, and the methodology digest is persisted alongside — so re-running over
the same data reproduces the same signal exactly, and persistence is idempotent.

Breakout is measured on **close**, not intraday high, matching the deck's
daily-closing-basis ("DCB") discipline for exits (p.9) and avoiding a wick
through the ceiling reading as a breakout.
"""

from __future__ import annotations

from collections.abc import Sequence
from decimal import Decimal

from athena.darvax import __version__ as darvax_version
from athena.darvax.config import DarvaxMethodologyConfig, methodology_digest
from athena.darvax.primitives import (
    DarvasBox,
    darvas_boxes,
    distance_to_ath,
)
from athena.darvax.primitives._guards import require_chronological_candles
from athena.darvax.signals.models import (
    DAR_CARD_TEXT,
    DarvasRule,
    DarvaxSignal,
    DarvaxSignalType,
    SignalEvidence,
)
from athena.darvax.signals.stops import compute_stop
from athena.domain.market import Candle


def _signal_id(instrument_id: str, as_of_iso: str) -> str:
    return f"darvax-{instrument_id}-{as_of_iso}"


def _retest_observed(
    candles: Sequence[Candle],
    box: DarvasBox,
    *,
    tolerance_pct: Decimal,
) -> bool:
    """Whether price returned to the ceiling zone after breaking out and held.

    Scans bars after the given box completed — the box passed in is the *topmost*
    one, so the scan starts where that ceiling became authoritative. Once a close
    clears the ceiling, a subsequent bar counts as a retest when its **low** dips
    into the ceiling zone (``low <= ceiling * (1 + tolerance)``) while its
    **close** stays above the ceiling: price came back and the level held. A close
    back below the ceiling is a failed retest, not a retest, and resets the
    breakout.
    """
    ceiling = box.top
    zone_cap = ceiling * (Decimal(1) + tolerance_pct / Decimal(100))
    broken_out = False
    for bar in candles[box.bottom_confirmed_index + 1 :]:
        if not broken_out:
            if bar.close > ceiling:
                broken_out = True
            continue
        if bar.close <= ceiling:
            broken_out = False  # gave the level back; no longer a live breakout
            continue
        if bar.low <= zone_cap:
            return True
    return False


def evaluate_signal(
    candles: Sequence[Candle],
    methodology: DarvaxMethodologyConfig | None = None,
) -> DarvaxSignal:
    """Evaluate DarvaX's structural state at the final bar of ``candles``.

    Args:
        candles: oldest-first, single instrument, single timeframe.
        methodology: DarvaX-owned settings; defaults are used when omitted.

    Returns:
        A signal that always carries a persisted explanation and evidence trace,
        including for the NO_BOX case — "nothing can be said yet" is itself an
        explainable outcome, not a silent empty result.
    """
    require_chronological_candles(candles, minimum=1, what="evaluate_signal")
    config = methodology or DarvaxMethodologyConfig()
    digest = methodology_digest(config)

    latest = candles[-1]
    as_of = latest.ts_open
    close = latest.close
    instrument_id = latest.instrument_id
    trigger_price = candles[-2].high if len(candles) >= 2 else None

    evidence: list[SignalEvidence] = [
        SignalEvidence(
            name="bars_examined",
            value=str(len(candles)),
            detail=(
                f"{len(candles)} {latest.timeframe.value} candles through "
                f"{as_of.isoformat()}."
            ),
        )
    ]

    boxes = darvas_boxes(candles, confirmation_bars=config.box.confirmation_bars)
    evidence.append(
        SignalEvidence(
            name="boxes_completed",
            value=str(len(boxes)),
            detail=(
                f"{len(boxes)} Darvas box(es) completed with "
                f"confirmation_bars={config.box.confirmation_bars}."
            ),
        )
    )

    def _build(
        signal_type: DarvaxSignalType,
        rule: DarvasRule | None,
        explanation: str,
        *,
        box: DarvasBox | None = None,
        include_stop: bool = False,
    ) -> DarvaxSignal:
        stop = None
        if include_stop:
            reference = trigger_price if trigger_price is not None else close
            stop = compute_stop(candles, config, reference_price=reference)
            if stop is not None:
                evidence.append(
                    SignalEvidence(
                        name="stop", value=str(stop.price), detail=stop.detail
                    )
                )
            else:
                evidence.append(
                    SignalEvidence(
                        name="stop",
                        value="UNAVAILABLE",
                        detail=(
                            "EMA-ladder stop selected but history is shorter than "
                            "the configured EMA period, so no level can be stated."
                        ),
                    )
                )
        if rule is not None:
            evidence.append(
                SignalEvidence(
                    name="dar_card_rule",
                    value=rule.value,
                    detail=DAR_CARD_TEXT[rule],
                )
            )
        return DarvaxSignal(
            signal_id=_signal_id(instrument_id, as_of.isoformat()),
            instrument_id=instrument_id,
            as_of=as_of,
            signal_type=signal_type,
            darvas_rule=rule,
            close=close,
            explanation=explanation,
            evidence=tuple(evidence),
            methodology_digest=digest,
            darvax_version=darvax_version,
            box_top=box.top if box else None,
            box_bottom=box.bottom if box else None,
            box_is_topmost=box.is_topmost if box else None,
            trigger_price=trigger_price if include_stop else None,
            stop=stop,
        )

    # ---- 1. No structure yet -------------------------------------------------
    if not boxes:
        return _build(
            DarvaxSignalType.NO_BOX,
            None,
            (
                f"No Darvas box has completed in the {len(candles)} candles "
                f"examined, so there is no ceiling or floor to judge price "
                f"against. Close {close}."
            ),
        )

    latest_box = boxes[-1]
    # Rules A/B/D are phrased against "its topmost box", so that is the
    # reference. Ties resolve to the most recent box, which is why max() scans
    # in order with >= semantics via the reversed search below.
    box = max(reversed(boxes), key=lambda candidate: candidate.top)
    ath = distance_to_ath(candles)
    evidence.append(
        SignalEvidence(
            name="box",
            value=f"{box.bottom}-{box.top}",
            detail=(
                f"Topmost box: floor {box.bottom} (bar {box.bottom_index}), "
                f"ceiling {box.top} (bar {box.top_index}). This is the reference "
                f"for Darvas rules A/B/D, which are phrased against the topmost "
                f"box rather than the most recently completed one."
            ),
        )
    )
    if latest_box is not box:
        evidence.append(
            SignalEvidence(
                name="latest_completed_box",
                value=f"{latest_box.bottom}-{latest_box.top}",
                detail=(
                    f"The most recently completed box ({latest_box.bottom}-"
                    f"{latest_box.top}) sits below the topmost box, so price has "
                    f"formed lower structure since the topmost ceiling was set."
                ),
            )
        )
    evidence.append(
        SignalEvidence(
            name="distance_to_observed_ath",
            value=f"{ath.distance_pct:.2f}%",
            detail=(
                f"Close {ath.close} is {ath.distance_pct:.2f}% below the highest "
                f"high in the {ath.bars_examined} candles examined ({ath.ath}). "
                "This is the observed high in ingested history, not necessarily a "
                "true all-time high."
            ),
        )
    )

    # ---- 2/3. Rule B: above the topmost ceiling -----------------------------
    if close > box.top:
        retested = _retest_observed(
            candles, box, tolerance_pct=config.breakout.retest_tolerance_pct
        )
        if retested:
            return _build(
                DarvaxSignalType.BREAKOUT_RETEST,
                DarvasRule.B_BUY_ABOVE_TOPMOST_BOX,
                (
                    f"Close {close} is above the topmost box ceiling {box.top}, "
                    f"and price has since returned into the ceiling zone "
                    f"(within {config.breakout.retest_tolerance_pct}%) and still "
                    f"closed above it — the breakout-retest the deck illustrates "
                    f"on p.28."
                ),
                box=box,
                include_stop=True,
            )
        return _build(
            DarvaxSignalType.BREAKOUT,
            DarvasRule.B_BUY_ABOVE_TOPMOST_BOX,
            (
                f"Close {close} cleared the topmost box ceiling {box.top}, which "
                f"is the condition Darvas' rule B describes as a BUY. No retest "
                f"of the ceiling has been observed since the breakout."
            ),
            box=box,
            include_stop=True,
        )

    # ---- 4. Rule A: inside the topmost box ----------------------------------
    if close >= box.bottom:
        return _build(
            DarvaxSignalType.INSIDE_TOPMOST_BOX,
            DarvasRule.A_HOLD_WHILE_IN_TOPMOST_BOX,
            (
                f"Close {close} sits inside the topmost box "
                f"({box.bottom}-{box.top}). Darvas' rule A says fluctuation "
                f"within the topmost box should be ignored."
            ),
            box=box,
        )

    # ---- 5. Rule C: the topmost box is also the newest, and its floor broke --
    if latest_box is box:
        return _build(
            DarvaxSignalType.BELOW_BOX_BOTTOM,
            DarvasRule.C_SELL_BELOW_NEW_BOX_BOTTOM,
            (
                f"Close {close} is below the floor {box.bottom} of the topmost "
                f"box, which is also the most recently formed one — the "
                f"condition Darvas' rule C describes as a SELL."
            ),
            box=box,
        )

    # ---- 6. Rule D: price has left the topmost box for lower structure ------
    return _build(
        DarvaxSignalType.NOT_IN_TOPMOST_BOX,
        DarvasRule.D_NO_REASON_OUTSIDE_TOPMOST_BOX,
        (
            f"Close {close} is below the topmost box floor {box.bottom}, and a "
            f"lower box ({latest_box.bottom}-{latest_box.top}) has completed "
            f"since. Price is not in its topmost box, so Darvas' rule D applies: "
            f"there is no reason to hold or buy here."
        ),
        box=box,
    )
