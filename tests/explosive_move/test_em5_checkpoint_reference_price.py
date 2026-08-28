"""EM-5's checkpoint-reference-price collector: FIRST_OBSERVED_POST_
CHECKPOINT_TRADE semantics, the frozen 300s bound, batched (never
per-symbol) requests -- tested entirely against injected fake fetch/
clock/sleep, never a live Kite call."""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from zoneinfo import ZoneInfo

from athena.data.em5_checkpoint_price_diagnostic import DualTimestampObservation
from athena.explosive_move.live.checkpoint_reference_price import (
    CHECKPOINT_PRICE_SEMANTIC,
    MAX_CHECKPOINT_OBSERVATION_DELAY_SECONDS,
    collect_checkpoint_reference_prices,
)

IST = ZoneInfo("Asia/Kolkata")


def _t(h, m, s=0):
    return datetime(2026, 8, 28, h, m, s, tzinfo=IST)


def _obs(iid, ltt, price="100.0", api_ts=None):
    return DualTimestampObservation(
        instrument_id=iid, poll_request_ts=_t(12, 0, 1), api_timestamp=api_ts or _t(12, 0, 1),
        last_trade_time=ltt, last_price=Decimal(price),
        raw_fields_present=("timestamp", "last_trade_time", "last_price"),
    )


def _fake_fetch(sequence):
    calls = {"i": 0, "batch_sizes": []}

    def fetch(instrument_ids, poll_ts):
        calls["batch_sizes"].append(len(instrument_ids))
        idx = min(calls["i"], len(sequence) - 1)
        calls["i"] += 1
        return {iid: sequence[idx][iid] for iid in instrument_ids if iid in sequence[idx]}

    return fetch, calls


def test_frozen_bound_is_300_seconds():
    assert MAX_CHECKPOINT_OBSERVATION_DELAY_SECONDS == 300.0


def test_qualifies_only_on_last_trade_time_ge_checkpoint():
    checkpoint = _t(12, 0)
    sequence = [{"A": _obs("A", _t(12, 0, 1))}]
    fetch, _ = _fake_fetch(sequence)
    clock = {"t": 0.0}
    qualified, no_price, requests = collect_checkpoint_reference_prices(
        instrument_ids=("A",), checkpoint_instant=checkpoint,
        fetch=fetch, now=lambda: clock["t"], sleep=lambda s: clock.__setitem__("t", clock["t"] + s),
    )
    assert "A" in qualified
    assert qualified["A"].reference_price_semantic == CHECKPOINT_PRICE_SEMANTIC
    assert qualified["A"].latency_seconds == 1.0
    assert no_price == ()
    assert requests == 1


def test_never_falls_back_to_a_pre_checkpoint_trade():
    checkpoint = _t(12, 0)
    sequence = [{"A": _obs("A", _t(11, 59, 59))}]  # strictly before C, forever
    fetch, _ = _fake_fetch(sequence)
    clock = {"t": 0.0}
    qualified, no_price, _ = collect_checkpoint_reference_prices(
        instrument_ids=("A",), checkpoint_instant=checkpoint, max_delay_seconds=3.0, poll_interval_seconds=1.0,
        fetch=fetch, now=lambda: clock["t"], sleep=lambda s: clock.__setitem__("t", clock["t"] + s),
    )
    assert qualified == {}
    assert no_price == ("A",)


def test_no_checkpoint_price_never_fabricated_within_bound():
    checkpoint = _t(12, 0)
    sequence = [{}]  # instrument never appears in any response at all
    fetch, _ = _fake_fetch(sequence)
    clock = {"t": 0.0}
    qualified, no_price, _ = collect_checkpoint_reference_prices(
        instrument_ids=("A",), checkpoint_instant=checkpoint, max_delay_seconds=2.0, poll_interval_seconds=1.0,
        fetch=fetch, now=lambda: clock["t"], sleep=lambda s: clock.__setitem__("t", clock["t"] + s),
    )
    assert "A" not in qualified
    assert no_price == ("A",)


def test_stops_polling_an_instrument_once_qualified():
    checkpoint = _t(12, 0)
    sequence = [
        {"A": _obs("A", _t(11, 59, 0)), "B": _obs("B", _t(12, 0, 5))},
        {"A": _obs("A", _t(12, 0, 10))},
    ]
    fetch, calls = _fake_fetch(sequence)
    clock = {"t": 0.0}
    qualified, _no_price, requests = collect_checkpoint_reference_prices(
        instrument_ids=("A", "B"), checkpoint_instant=checkpoint,
        fetch=fetch, now=lambda: clock["t"], sleep=lambda s: clock.__setitem__("t", clock["t"] + s),
    )
    assert set(qualified) == {"A", "B"}
    assert requests == 2
    assert calls["batch_sizes"] == [2, 1]  # B dropped from the second poll's batch


def test_every_poll_is_one_batched_request_never_per_symbol():
    checkpoint = _t(12, 0)
    sequence = [{"A": _obs("A", _t(12, 0, 1)), "B": _obs("B", _t(12, 0, 1)), "C": _obs("C", _t(12, 0, 1))}]
    fetch, calls = _fake_fetch(sequence)
    clock = {"t": 0.0}
    collect_checkpoint_reference_prices(
        instrument_ids=("A", "B", "C"), checkpoint_instant=checkpoint,
        fetch=fetch, now=lambda: clock["t"], sleep=lambda s: clock.__setitem__("t", clock["t"] + s),
    )
    assert calls["batch_sizes"] == [3]  # one request covering all three, not three requests


def test_snapshot_timestamp_kept_separate_from_last_trade_time():
    checkpoint = _t(12, 0)
    sequence = [{"A": _obs("A", _t(12, 0, 1), api_ts=_t(12, 0, 4))}]
    fetch, _ = _fake_fetch(sequence)
    clock = {"t": 0.0}
    qualified, _, _ = collect_checkpoint_reference_prices(
        instrument_ids=("A",), checkpoint_instant=checkpoint,
        fetch=fetch, now=lambda: clock["t"], sleep=lambda s: clock.__setitem__("t", clock["t"] + s),
    )
    ref = qualified["A"]
    assert ref.last_trade_time == _t(12, 0, 1)
    assert ref.snapshot_timestamp == _t(12, 0, 4)
    assert ref.last_trade_time != ref.snapshot_timestamp
