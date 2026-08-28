"""EM-5 checkpoint-price parity diagnostic: dual-timestamp parsing and
the canary/capture polling loops -- tested entirely against injected
fake fetch/clock/sleep functions, never a live Kite call."""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from zoneinfo import ZoneInfo

from athena.data.em5_checkpoint_price_diagnostic import (
    DualTimestampObservation,
    capture_checkpoint_observations,
    parse_dual_timestamp_row,
    run_semantic_canary,
)

IST = ZoneInfo("Asia/Kolkata")


def _t(h, m, s=0):
    return datetime(2026, 8, 28, h, m, s, tzinfo=IST)


def test_parse_dual_timestamp_row_keeps_both_fields_separate():
    row = {"timestamp": "2026-08-28 10:30:02", "last_trade_time": "2026-08-28 10:29:58", "last_price": "101.50"}
    obs = parse_dual_timestamp_row("NSE:INFY", row, _t(10, 30, 5))
    assert obs.api_timestamp == _t(10, 30, 2)
    assert obs.last_trade_time == _t(10, 29, 58)
    assert obs.api_timestamp != obs.last_trade_time
    assert obs.last_price == Decimal("101.50")
    assert set(obs.raw_fields_present) == {"timestamp", "last_trade_time", "last_price"}


def test_parse_dual_timestamp_row_tolerates_missing_last_trade_time():
    row = {"timestamp": "2026-08-28 10:30:02", "last_price": "101.50"}
    obs = parse_dual_timestamp_row("NSE:INFY", row, _t(10, 30, 5))
    assert obs.last_trade_time is None
    assert obs.api_timestamp is not None
    assert "last_trade_time" not in obs.raw_fields_present


def test_parse_dual_timestamp_row_handles_none_row():
    obs = parse_dual_timestamp_row("NSE:INFY", None, _t(10, 30, 5))
    assert obs.api_timestamp is None
    assert obs.last_trade_time is None
    assert obs.last_price is None
    assert obs.raw_fields_present == ()


def _fake_fetch_sequence(sequence: list[dict[str, DualTimestampObservation]]):
    calls = {"i": 0}

    def fetch(instrument_ids, poll_ts):
        idx = min(calls["i"], len(sequence) - 1)
        calls["i"] += 1
        return {iid: sequence[idx][iid] for iid in instrument_ids if iid in sequence[idx]}

    return fetch, calls


def _obs(iid, ltt, price="100.0"):
    return DualTimestampObservation(
        instrument_id=iid, poll_request_ts=_t(10, 30, 1), api_timestamp=_t(10, 30, 1),
        last_trade_time=ltt, last_price=Decimal(price),
        raw_fields_present=("timestamp", "last_trade_time", "last_price"),
    )


def test_capture_stops_polling_an_instrument_once_it_qualifies(tmp_path):
    checkpoint = _t(10, 30)
    # Poll 1: A not-yet-qualifying (pre-C), B qualifying (post-C). Poll 2: A qualifies.
    sequence = [
        {"A": _obs("A", _t(10, 29, 50)), "B": _obs("B", _t(10, 30, 5))},
        {"A": _obs("A", _t(10, 30, 10))},
    ]
    fetch, calls = _fake_fetch_sequence(sequence)
    clock_state = {"t": 0.0}
    result = capture_checkpoint_observations(
        fetch=fetch, instrument_ids=("A", "B"), checkpoint_instant=checkpoint,
        window_seconds=60, poll_interval_seconds=1.0,
        now=lambda: clock_state["t"], sleep=lambda s: clock_state.__setitem__("t", clock_state["t"] + s),
        out_path=tmp_path / "capture.jsonl", checkpoint_label="10:30", session_date="2026-08-28",
    )
    assert set(result.qualified) == {"A", "B"}
    assert result.no_checkpoint_price == ()
    assert result.qualified["B"].last_trade_time == _t(10, 30, 5)
    assert result.qualified["A"].last_trade_time == _t(10, 30, 10)
    # B should not appear in the fetch call args after poll 1 (it already qualified)
    assert calls["i"] == 2


def test_capture_reports_no_checkpoint_price_when_window_expires():
    checkpoint = _t(10, 30)
    sequence = [{"A": _obs("A", _t(10, 29, 0))}]  # never advances past C
    fetch, _ = _fake_fetch_sequence(sequence)
    clock_state = {"t": 0.0}

    def now():
        return clock_state["t"]

    def sleep(s):
        clock_state["t"] += s

    import tempfile
    from pathlib import Path

    with tempfile.TemporaryDirectory() as d:
        result = capture_checkpoint_observations(
            fetch=fetch, instrument_ids=("A",), checkpoint_instant=checkpoint,
            window_seconds=3.0, poll_interval_seconds=1.0, now=now, sleep=sleep,
            out_path=Path(d) / "capture.jsonl", checkpoint_label="10:30", session_date="2026-08-28",
        )
    assert result.qualified == {}
    assert result.no_checkpoint_price == ("A",)


def test_capture_never_uses_a_pre_checkpoint_trade_as_qualifying(tmp_path):
    checkpoint = _t(10, 30)
    # last_trade_time strictly before C on every poll -- must never qualify.
    sequence = [{"A": _obs("A", _t(10, 29, 59))}]
    fetch, _ = _fake_fetch_sequence(sequence)
    clock_state = {"t": 0.0}
    result = capture_checkpoint_observations(
        fetch=fetch, instrument_ids=("A",), checkpoint_instant=checkpoint,
        window_seconds=2.0, poll_interval_seconds=1.0,
        now=lambda: clock_state["t"], sleep=lambda s: clock_state.__setitem__("t", clock_state["t"] + s),
        out_path=tmp_path / "capture.jsonl", checkpoint_label="10:30", session_date="2026-08-28",
    )
    assert "A" not in result.qualified
    assert result.no_checkpoint_price == ("A",)


def test_capture_persists_every_poll_including_non_qualifying(tmp_path):
    checkpoint = _t(10, 30)
    sequence = [
        {"A": _obs("A", _t(10, 29, 0))},
        {"A": _obs("A", _t(10, 30, 1))},
    ]
    fetch, _ = _fake_fetch_sequence(sequence)
    clock_state = {"t": 0.0}
    out_path = tmp_path / "capture.jsonl"
    capture_checkpoint_observations(
        fetch=fetch, instrument_ids=("A",), checkpoint_instant=checkpoint,
        window_seconds=60, poll_interval_seconds=1.0,
        now=lambda: clock_state["t"], sleep=lambda s: clock_state.__setitem__("t", clock_state["t"] + s),
        out_path=out_path, checkpoint_label="10:30", session_date="2026-08-28",
    )
    lines = out_path.read_text().strip().split("\n")
    assert len(lines) == 2  # one non-qualifying, one qualifying -- both persisted


def test_semantic_canary_persists_every_observation_across_duration(tmp_path):
    sequence = [
        {"A": _obs("A", _t(10, 29, 0))},
        {"A": _obs("A", _t(10, 29, 0))},  # unchanged -- no new trade
        {"A": _obs("A", _t(10, 29, 30))},  # advanced -- new trade
    ]
    fetch, _ = _fake_fetch_sequence(sequence)
    clock_state = {"t": 0.0}
    out_path = tmp_path / "canary.jsonl"
    observations = run_semantic_canary(
        fetch=fetch, instrument_ids=("A",), duration_seconds=3.0, poll_interval_seconds=1.0,
        now=lambda: clock_state["t"], sleep=lambda s: clock_state.__setitem__("t", clock_state["t"] + s),
        out_path=out_path,
    )
    assert len(observations) == 3
    lines = out_path.read_text().strip().split("\n")
    assert len(lines) == 3
