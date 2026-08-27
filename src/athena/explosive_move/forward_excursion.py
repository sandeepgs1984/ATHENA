"""EM-4C: MFE / MAE / time-to-target -- exact formulas frozen in
``em4_config.py`` (owner-approved 2026-08-27), derived directly from
already-frozen EM-1a/EM-1b conventions (reference_price, the
same_regular_session horizon, and the ``ts_open >= checkpoint_instant``
forward boundary already tested in EM-1b's ``event_labels.py``). No new
market-data acquisition, no new semantics.

Pure: no I/O. Reuses ``event_labels.threshold_price`` unchanged.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal

from athena.domain.market import Candle
from athena.explosive_move.em4_config import TIME_TO_TARGET_APPLICABLE_FAMILIES
from athena.explosive_move.event_labels import threshold_price


@dataclass(frozen=True, slots=True)
class ForwardExcursionResult:
    mfe_percent: Decimal | None
    mae_percent: Decimal | None
    time_to_target_minutes: Decimal | None
    time_to_target_applicable: bool
    unknown_reason: str | None


def compute_forward_excursion(
    *,
    checkpoint_instant: datetime,
    session_candles: tuple[Candle, ...],
    reference_price: Decimal,
    threshold_percent: int,
    event_family: str,
    is_positive_label: bool,
) -> ForwardExcursionResult:
    """``session_candles`` may be the full session; forward-filtering to
    ``ts_open >= checkpoint_instant`` happens here, so the leakage
    boundary lives in one place, matching this workstream's convention."""

    forward = tuple(c for c in session_candles if c.ts_open >= checkpoint_instant)
    applicable = event_family in TIME_TO_TARGET_APPLICABLE_FAMILIES

    if not forward:
        return ForwardExcursionResult(
            mfe_percent=None, mae_percent=None, time_to_target_minutes=None,
            time_to_target_applicable=applicable,
            unknown_reason="no forward candles (checkpoint at/after the session's last candle)",
        )

    mfe = (max(c.high for c in forward) / reference_price - 1) * Decimal(100)
    mae = (min(c.low for c in forward) / reference_price - 1) * Decimal(100)

    time_to_target: Decimal | None = None
    if applicable and is_positive_label:
        price = threshold_price(reference_price, threshold_percent)
        touch = next((c for c in forward if c.high >= price), None)
        if touch is not None:
            time_to_target = Decimal((touch.ts_open - checkpoint_instant).total_seconds()) / Decimal(60)

    return ForwardExcursionResult(
        mfe_percent=mfe, mae_percent=mae, time_to_target_minutes=time_to_target,
        time_to_target_applicable=applicable, unknown_reason=None,
    )
