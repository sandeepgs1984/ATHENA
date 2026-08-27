"""EM-4C evaluation scaffolding: regime/checkpoint aggregation --
grouping already-scored observations by an arbitrary key (checkpoint,
regime category, family/threshold, or any combination) and reporting a
real Wilson-bounded rate per group, matching EM-1c/EM-3's established
per-group uncertainty convention rather than a bare point estimate.

Owner/Chief Architect decision, 2026-08-27 (evaluation-scaffolding
scope). This is genuinely reused, not duplicated: it delegates to the
same wilson_interval used throughout EM-1c/EM-3.

Pure: no I/O, no randomness. Grouping is caller-driven (a key function),
so this module has no opinion on what "regime" or "checkpoint" mean --
that stays wherever the real evidence schema defines those fields.
"""

from __future__ import annotations

from collections import defaultdict
from collections.abc import Callable, Hashable
from dataclasses import dataclass
from typing import Generic, TypeVar

from athena.explosive_move.wilson_interval import WilsonInterval, wilson_interval

EM4C_AGGREGATION_CONTRACT_VERSION = "em4c-aggregation-v1"

T = TypeVar("T")
K = TypeVar("K", bound=Hashable)


@dataclass(frozen=True, slots=True)
class GroupSummary(Generic[K]):
    group_key: K
    eligible_n: int
    positive_k: int
    rate: float
    wilson_95: WilsonInterval


def aggregate_by_group(
    observations: tuple[T, ...],
    *,
    group_key_fn: Callable[[T], K],
    label_fn: Callable[[T], bool],
) -> dict[K, GroupSummary[K]]:
    """Groups are formed in first-seen order internally but returned as
    a plain dict keyed by group_key -- callers needing a deterministic
    iteration order should sort the returned dict's keys themselves
    (group_key types vary by caller, so no single sort rule is imposed
    here)."""

    buckets: dict[K, list[bool]] = defaultdict(list)
    for obs in observations:
        buckets[group_key_fn(obs)].append(label_fn(obs))

    summaries: dict[K, GroupSummary[K]] = {}
    for key, labels in buckets.items():
        n = len(labels)
        positives = sum(1 for label in labels if label)
        summaries[key] = GroupSummary(
            group_key=key, eligible_n=n, positive_k=positives,
            rate=positives / n, wilson_95=wilson_interval(positives, n),
        )
    return summaries


def aggregate_by_two_keys(
    observations: tuple[T, ...],
    *,
    primary_key_fn: Callable[[T], K],
    secondary_key_fn: Callable[[T], Hashable],
    label_fn: Callable[[T], bool],
) -> dict[K, dict[Hashable, GroupSummary]]:
    """Nested aggregation, e.g. checkpoint -> regime_category -> summary,
    for the EM-4 Modeling Contract's checkpoint-stability and
    regime-stability diagnostics. Built on aggregate_by_group, not a
    reimplementation."""

    by_primary: dict[K, list[T]] = defaultdict(list)
    for obs in observations:
        by_primary[primary_key_fn(obs)].append(obs)

    return {
        primary: aggregate_by_group(
            tuple(group), group_key_fn=secondary_key_fn, label_fn=label_fn,
        )
        for primary, group in by_primary.items()
    }
