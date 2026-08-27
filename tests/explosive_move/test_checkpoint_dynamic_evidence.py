"""EM-2 CHECKPOINT_DYNAMIC evidence: candle cutoff semantics, exact
warm-up boundaries, and the owner-required leakage mutation tests --
mutate everything after C and assert the snapshot at C is unchanged;
mutate before/at C and assert it changes where mathematically expected;
confirm session-invariant-shaped fields (via the 20D baseline) remain
identical across checkpoints for the same symbol-session.
"""

from __future__ import annotations

from datetime import datetime, timedelta
from decimal import Decimal
from zoneinfo import ZoneInfo

from athena.domain.enums import Timeframe
from athena.domain.market import Candle
from athena.explosive_move.checkpoint_dynamic_evidence import (
    compute_checkpoint_dynamic_evidence,
    cumulative_volume_so_far,
    session_low_so_far,
)
from athena.explosive_move.evidence_values import DailyBar

IST = ZoneInfo("Asia/Kolkata")
DAY = datetime(2024, 6, 20, tzinfo=IST)
SESSION_OPEN = Decimal("100")


def _t(hour: int, minute: int) -> datetime:
    return DAY.replace(hour=hour, minute=minute)


def _candle(ts_open: datetime, *, open_: str, high: str, low: str, close: str, volume: int = 1000) -> Candle:
    return Candle(
        instrument_id="NSE:AAA", timeframe=Timeframe.M5, ts_open=ts_open,
        open=Decimal(open_), high=Decimal(high), low=Decimal(low), close=Decimal(close),
        volume=volume, source="kite", adjusted=False,
    )


def _quiet_session() -> tuple[Candle, ...]:
    return tuple(
        _candle(_t(9, 15) + timedelta(minutes=5 * i), open_="100", high="101", low="99", close="100")
        for i in range(75)
    )


def _prior_bars(n: int) -> tuple[DailyBar, ...]:
    out = []
    for i in range(n):
        d = DAY.date() - timedelta(days=n - i)
        out.append(DailyBar(
            session_date=d, open=Decimal("95"), high=Decimal("105"),
            low=Decimal("90"), close=Decimal("98"), volume=50000,
        ))
    return tuple(out)


def _compute(session_candles, *, checkpoint=None, prior_bars=(), prev_close=Decimal("98"), hist_vol=()):
    return compute_checkpoint_dynamic_evidence(
        checkpoint_instant=checkpoint or _t(10, 30), session_candles=session_candles,
        session_open=SESSION_OPEN, prior_daily_bars=prior_bars, prev_close=prev_close,
        historical_checkpoint_volumes=hist_vol,
    )


# --------------------------------------------------------------------------- #
# Candle cutoff semantics (owner item 8): ts_open < C is eligible, the
# candle beginning exactly at C is not.
# --------------------------------------------------------------------------- #

def test_candle_beginning_exactly_at_c_is_excluded():
    session = _quiet_session()
    result = _compute(session, checkpoint=_t(10, 30))
    manual = sum(c.volume for c in session if c.ts_open < _t(10, 30))
    assert result.cum_volume_c.value == Decimal(manual)
    including_boundary = sum(c.volume for c in session if c.ts_open <= _t(10, 30))
    assert manual != including_boundary  # sanity: the boundary candle really does contribute volume
    assert result.cum_volume_c.value != Decimal(including_boundary)


def test_cumulative_volume_so_far_helper_matches_direct_filter():
    session = _quiet_session()
    assert cumulative_volume_so_far(_t(9, 20), session) == sum(
        c.volume for c in session if c.ts_open < _t(9, 20)
    )


def test_session_low_so_far_mirrors_high_so_far_boundary():
    session = list(_quiet_session())
    session[2] = _candle(_t(9, 25), open_="100", high="101", low="80", close="100")  # spike low at 09:25
    session = tuple(session)
    at_0925 = session_low_so_far(_t(9, 25), session)  # 09:25 candle not yet closed
    at_0930 = session_low_so_far(_t(9, 30), session)  # now closed
    assert at_0925 != Decimal("80")
    assert at_0930 == Decimal("80")


# --------------------------------------------------------------------------- #
# Warm-up boundaries
# --------------------------------------------------------------------------- #

def test_20d_high_low_range_position_warmup_boundary():
    session = _quiet_session()
    short = _compute(session, prior_bars=_prior_bars(19))
    exact = _compute(session, prior_bars=_prior_bars(20))
    assert short.dist_from_20d_high_c.is_known is False
    assert short.dist_from_20d_low_c.is_known is False
    assert short.range_position_20d_c.is_known is False
    assert exact.dist_from_20d_high_c.is_known is True
    assert exact.dist_from_20d_low_c.is_known is True
    assert exact.range_position_20d_c.is_known is True


def test_rel_volume_c_warmup_boundary():
    session = _quiet_session()
    short = _compute(session, hist_vol=tuple([100000] * 19))
    exact = _compute(session, hist_vol=tuple([100000] * 20))
    assert short.rel_volume_c.is_known is False
    assert exact.rel_volume_c.is_known is True


def test_return_from_prev_close_needs_prev_close():
    session = _quiet_session()
    with_prev = _compute(session, prev_close=Decimal("98"))
    without_prev = _compute(session, prev_close=None)
    assert with_prev.return_from_prev_close_c.is_known
    assert without_prev.return_from_prev_close_c.is_known is False


def test_price_at_checkpoint_missing_makes_dependent_fields_unknown():
    """If no candle opens exactly at C (e.g. C is off the 5-minute grid),
    every field that needs price_at_checkpoint must be UNKNOWN, not a
    silently-substituted nearby price."""
    session = _quiet_session()
    off_grid = _t(9, 21)
    result = _compute(session, checkpoint=off_grid, prior_bars=_prior_bars(20))
    assert result.return_from_open_c.is_known is False
    assert result.return_from_prev_close_c.is_known is False
    assert result.dist_from_20d_high_c.is_known is False
    assert result.vwap_rel_c.is_known is False


# --------------------------------------------------------------------------- #
# Leakage mutation tests (owner item 9) -- across every dynamic family.
# --------------------------------------------------------------------------- #

def _mutate_after(session_candles, checkpoint, wild="999999"):
    """Mutates every candle STRICTLY after the checkpoint. The candle
    whose ts_open exactly equals the checkpoint is legitimately observable
    (its OPEN is the current price at that instant, per
    event_labels.price_at_checkpoint's own already-approved contract) and
    must NOT be touched, or this test would be checking sensitivity to
    real information rather than a real leak."""
    out = []
    for c in session_candles:
        if c.ts_open > checkpoint:
            out.append(_candle(c.ts_open, open_=wild, high=wild, low="1", close=wild, volume=999999))
        else:
            out.append(c)
    return tuple(out)


def test_mutating_everything_after_c_does_not_change_the_snapshot_at_c():
    session = _quiet_session()
    checkpoint = _t(11, 0)
    prior_bars = _prior_bars(20)
    baseline = _compute(session, checkpoint=checkpoint, prior_bars=prior_bars, hist_vol=tuple([100000] * 20))
    mutated_session = _mutate_after(session, checkpoint)
    mutated = _compute(mutated_session, checkpoint=checkpoint, prior_bars=prior_bars, hist_vol=tuple([100000] * 20))

    assert mutated.cum_volume_c.value == baseline.cum_volume_c.value
    assert mutated.high_so_far_c.value == baseline.high_so_far_c.value
    assert mutated.low_so_far_c.value == baseline.low_so_far_c.value
    assert mutated.vwap_through_c.value == baseline.vwap_through_c.value
    assert mutated.return_from_open_c.value == baseline.return_from_open_c.value
    assert mutated.dist_from_20d_high_c.value == baseline.dist_from_20d_high_c.value
    assert mutated.range_so_far_c.value == baseline.range_so_far_c.value


def test_mutating_data_before_c_changes_evidence_where_expected():
    session = list(_quiet_session())
    checkpoint = _t(11, 0)
    baseline = _compute(tuple(session), checkpoint=checkpoint)

    session[10] = _candle(session[10].ts_open, open_="100", high="150", low="99", close="100")  # a real pre-C spike
    mutated = _compute(tuple(session), checkpoint=checkpoint)

    assert mutated.high_so_far_c.value != baseline.high_so_far_c.value
    assert mutated.high_so_far_c.value == Decimal("150")


def test_later_checkpoint_information_cannot_alter_an_earlier_snapshot():
    session = list(_quiet_session())
    early = _t(9, 30)
    # a wild spike far in the future (well after `early`)
    session[40] = _candle(session[40].ts_open, open_="1", high="999999", low="1", close="999999", volume=999999)
    session = tuple(session)

    clean_early = _compute(_quiet_session(), checkpoint=early)
    mutated_early = _compute(session, checkpoint=early)
    assert clean_early.cum_volume_c.value == mutated_early.cum_volume_c.value
    assert clean_early.high_so_far_c.value == mutated_early.high_so_far_c.value


def test_session_invariant_shaped_baseline_is_identical_across_checkpoints():
    """The 20D high/low baseline (from prior_daily_bars, which doesn't
    depend on the checkpoint itself) must be identical regardless of
    which checkpoint is being evaluated for the same symbol-session."""
    session = _quiet_session()
    prior_bars = _prior_bars(20)
    at_0920 = _compute(session, checkpoint=_t(9, 20), prior_bars=prior_bars)
    at_1400 = _compute(session, checkpoint=_t(14, 0), prior_bars=prior_bars)
    high_20d = Decimal("105")  # from _prior_bars' constant construction
    low_20d = Decimal("90")
    # both checkpoints derive DIST_FROM_20D_HIGH_C from the identical
    # baseline, differing only via price_at_checkpoint -- verify the
    # baseline values implied by each are the same: dist = price/high-1,
    # so (1+dist)*high == price for both (price is constant at 100 across
    # this quiet synthetic session).
    # Decimal division on 100/90 is a non-terminating repeating fraction,
    # truncated at 28 significant digits -- compare with a tiny tolerance
    # rather than exact equality, which a truncated repeating decimal
    # cannot satisfy even though the two checkpoints' underlying baseline
    # really is identical.
    tolerance = Decimal("1E-20")
    price_0920 = Decimal("100")
    price_1400 = Decimal("100")
    assert abs((1 + at_0920.dist_from_20d_high_c.value) * high_20d - price_0920) < tolerance
    assert abs((1 + at_1400.dist_from_20d_high_c.value) * high_20d - price_1400) < tolerance
    assert abs((1 + at_0920.dist_from_20d_low_c.value) * low_20d - price_0920) < tolerance
    assert abs((1 + at_1400.dist_from_20d_low_c.value) * low_20d - price_1400) < tolerance
    assert at_0920.dist_from_20d_high_c.value == at_1400.dist_from_20d_high_c.value
    assert at_0920.dist_from_20d_low_c.value == at_1400.dist_from_20d_low_c.value
