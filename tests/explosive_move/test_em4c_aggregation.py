"""EM-4C aggregation scaffolding: regime/checkpoint grouping with a real
Wilson-bounded rate per group -- tested against synthetic fixtures."""

from __future__ import annotations

from dataclasses import dataclass

from athena.explosive_move.em4c_aggregation import aggregate_by_group, aggregate_by_two_keys


@dataclass(frozen=True, slots=True)
class _Obs:
    checkpoint: str
    regime: str
    label: bool


FIXTURE = (
    _Obs("09:20", "BULL_TREND", True),
    _Obs("09:20", "BULL_TREND", False),
    _Obs("09:20", "BEAR_TREND", False),
    _Obs("09:50", "BULL_TREND", True),
    _Obs("09:50", "BULL_TREND", True),
)


def test_aggregate_by_group_computes_rate_and_wilson_interval():
    summaries = aggregate_by_group(FIXTURE, group_key_fn=lambda o: o.checkpoint, label_fn=lambda o: o.label)
    assert summaries["09:20"].eligible_n == 3
    assert summaries["09:20"].positive_k == 1
    assert summaries["09:20"].rate == 1 / 3
    assert summaries["09:20"].wilson_95.lower >= 0.0
    assert summaries["09:50"].eligible_n == 2
    assert summaries["09:50"].positive_k == 2
    assert summaries["09:50"].rate == 1.0


def test_aggregate_by_group_covers_every_distinct_key():
    summaries = aggregate_by_group(FIXTURE, group_key_fn=lambda o: o.checkpoint, label_fn=lambda o: o.label)
    assert set(summaries.keys()) == {"09:20", "09:50"}


def test_aggregate_by_group_empty_input_produces_no_groups():
    summaries = aggregate_by_group((), group_key_fn=lambda o: o, label_fn=lambda o: True)
    assert summaries == {}


def test_aggregate_by_two_keys_nests_checkpoint_then_regime():
    nested = aggregate_by_two_keys(
        FIXTURE, primary_key_fn=lambda o: o.checkpoint,
        secondary_key_fn=lambda o: o.regime, label_fn=lambda o: o.label,
    )
    assert set(nested.keys()) == {"09:20", "09:50"}
    assert set(nested["09:20"].keys()) == {"BULL_TREND", "BEAR_TREND"}
    assert nested["09:20"]["BULL_TREND"].eligible_n == 2
    assert nested["09:20"]["BULL_TREND"].positive_k == 1
    assert set(nested["09:50"].keys()) == {"BULL_TREND"}
    assert nested["09:50"]["BULL_TREND"].positive_k == 2
