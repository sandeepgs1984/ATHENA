"""EM-5 live evidence assembly -- builds one candidate's full flat
observation row, in exactly the shape the frozen EM-4B preprocessing
contract expects (`session_date`, `checkpoint_ist`, plus the 22
`CANDIDATE_FEATURE` fields), by calling EM-2's own frozen
`session_invariant_evidence`/`checkpoint_dynamic_evidence` computation
modules completely unmodified.

Live checkpoint-price substitution (Owner-accepted 2026-08-28, EM-5
contract Section 2): the frozen model was trained on
`price_at_checkpoint(C)` = the OPEN of the candle whose `ts_open`
exactly equals C. In live operation that candle does not exist yet at
scan time. Rather than modifying the frozen `event_labels.py`/
`checkpoint_dynamic_evidence.py` (never touched -- enforced by
`test_em5_isolation.py`), this module injects one synthetic `Candle`
with `ts_open == checkpoint_instant` and `open` set to the live
`FIRST_OBSERVED_POST_CHECKPOINT_TRADE` price into the `session_candles`
tuple handed to the frozen computation. `price_at_checkpoint` only ever
matches on `candle.ts_open == checkpoint_instant` and returns
`candle.open` (confirmed by reading it) -- so this reproduces the
frozen formulas exactly, using the real frozen code, with the one
input substitution the live diagnostic proved acceptable. Every
"closed candle" aggregation (`ts_open < checkpoint_instant`) uses the
strict `<` boundary and therefore never sees the synthetic candle at
all -- only the 7 price-dependent fields are affected, exactly the set
the contract's audit identified.

`checkpoint_ist`/candidate-feature-name conventions mirror
`athena.data.em4b_logistic_fitting`'s row-building exactly (lowercase
field names from `evidence_contract.ALL_FIELDS`, `checkpoint_ist` key)
-- re-derived locally from the same pure metadata rather than imported
from that module, because `em4b_logistic_fitting` transitively imports
`em4b_model`, which imports numpy/scikit-learn (EM-5 Section 12: no
model-fitting dependency anywhere in the live path).
"""

from __future__ import annotations

from datetime import date, datetime, time
from decimal import Decimal

from athena.domain.enums import Timeframe
from athena.domain.market import Candle
from athena.explosive_move.checkpoint_dynamic_evidence import (
    compute_checkpoint_dynamic_evidence,
    cumulative_volume_so_far,
)
from athena.explosive_move.evidence_contract import ALL_FIELDS, Classification
from athena.explosive_move.evidence_values import DailyBar, EvidenceValue
from athena.explosive_move.session_invariant_evidence import compute_session_invariant_evidence

_CATEGORICAL_FIELDS = frozenset({"regime_trend", "regime_volatility", "regime_gap"})
_CANDIDATE_FIELD_NAMES: tuple[str, ...] = tuple(
    f.name.lower() for f in ALL_FIELDS if f.classification is Classification.CANDIDATE_FEATURE
)
CONTINUOUS_FIELDS: tuple[str, ...] = tuple(n for n in _CANDIDATE_FIELD_NAMES if n not in _CATEGORICAL_FIELDS)
CATEGORICAL_FIELDS: tuple[str, ...] = tuple(n for n in _CANDIDATE_FIELD_NAMES if n in _CATEGORICAL_FIELDS)
CHECKPOINT_FIELD = "checkpoint_ist"

assert len(_CANDIDATE_FIELD_NAMES) == 22, f"expected 22 CANDIDATE_FEATURE fields, got {len(_CANDIDATE_FIELD_NAMES)}"

_SYNTHETIC_CANDLE_SOURCE = "em5-live-checkpoint-price-substitution"


def _prior_bars(daily_bars: tuple[DailyBar, ...], session_date: date) -> tuple[DailyBar, ...]:
    ordered = sorted(daily_bars, key=lambda b: b.session_date)
    return tuple(b for b in ordered if b.session_date < session_date)


def _synthetic_price_candle(instrument_id: str, checkpoint_instant: datetime, live_price: Decimal) -> Candle:
    return Candle(
        instrument_id=instrument_id, timeframe=Timeframe.M5, ts_open=checkpoint_instant,
        open=live_price, high=live_price, low=live_price, close=live_price, volume=0,
        source=_SYNTHETIC_CANDLE_SOURCE,
    )


def historical_cumulative_volumes_through_checkpoint(
    *, checkpoint_time: time, prior_sessions_m5: dict[date, tuple[Candle, ...]], lookback_sessions: int = 20,
) -> tuple[int, ...]:
    """The REL_VOLUME_C baseline: cumulative same-time-of-day volume for
    the trailing `lookback_sessions` prior sessions that actually have
    at least one M5 candle before that time-of-day, most-recent-first
    input order, returned oldest-of-the-window-first (matching
    `checkpoint_dynamic_evidence`'s own trailing-window convention).
    Sessions with zero comparable-time-of-day data are skipped, not
    counted as zero -- exactly the field's own "have at least one M5
    candle at that time-of-day" requirement."""

    volumes: list[int] = []
    for session_date in sorted(prior_sessions_m5, reverse=True):
        if len(volumes) >= lookback_sessions:
            break
        candles = prior_sessions_m5[session_date]
        instant = datetime.combine(session_date, checkpoint_time, tzinfo=next(iter(candles)).ts_open.tzinfo) \
            if candles else None
        vol = cumulative_volume_so_far(instant, candles) if instant is not None else None
        if vol is not None:
            volumes.append(vol)
    return tuple(reversed(volumes))


def assemble_candidate_row(
    *,
    instrument_id: str,
    session_date: date,
    checkpoint: str,
    checkpoint_instant: datetime,
    daily_bars: tuple[DailyBar, ...],
    today_m5_candles: tuple[Candle, ...],
    checkpoint_reference_price: Decimal | None,
    historical_checkpoint_volumes: tuple[int, ...],
    regime_row: dict | None,
) -> dict[str, Decimal | str | None]:
    """One instrument's full observation row at one checkpoint, in the
    exact flat shape `em4b_preprocessing.transform_row` expects.

    `checkpoint_reference_price` is the live `FIRST_OBSERVED_POST_CHECKPOINT_TRADE`
    price from `checkpoint_reference_price.collect_checkpoint_reference_prices`
    (`None` if this instrument never qualified -- callers must have
    already excluded it via hard eligibility before calling this, since
    an observation with no checkpoint price cannot be scored)."""

    prior = _prior_bars(daily_bars, session_date)
    prev_close = prior[-1].close if prior else None
    session_open = today_m5_candles[0].open if today_m5_candles else None
    if session_open is None:
        raise ValueError(f"{instrument_id}: no M5 candles for {session_date.isoformat()} -- no session open known")

    session_candles = today_m5_candles
    if checkpoint_reference_price is not None:
        session_candles = (
            *today_m5_candles,
            _synthetic_price_candle(instrument_id, checkpoint_instant, checkpoint_reference_price),
        )

    invariant = compute_session_invariant_evidence(
        session_date=session_date, daily_bars=daily_bars, session_open=session_open, regime=regime_row,
    )
    dynamic = compute_checkpoint_dynamic_evidence(
        checkpoint_instant=checkpoint_instant, session_candles=session_candles, session_open=session_open,
        prior_daily_bars=prior, prev_close=prev_close,
        historical_checkpoint_volumes=historical_checkpoint_volumes,
    )

    row: dict[str, Decimal | str | None] = {"session_date": session_date.isoformat(), CHECKPOINT_FIELD: checkpoint}
    for name in _CANDIDATE_FIELD_NAMES:
        value: EvidenceValue = getattr(invariant, name) if hasattr(invariant, name) else getattr(dynamic, name)
        row[name] = value.value if value.is_known else None
    return row
