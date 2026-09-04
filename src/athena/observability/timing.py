"""ID-7P0: orthogonal, observational-only wall-clock cycle timing.

Answers a different question than `athena.ops.owner_validation`'s own
deterministic per-stage `_MonoClock`: not "is business replay
deterministic" (untouched here), but "where does one REAL production
cycle's wall-clock time actually go" (ingestion vs. analytical scan vs.
everything else). Never read by business logic, never influences a
Decision/EntryQualification/TradePlan result, safe to omit entirely --
every consumer of this module treats it as purely additive diagnostics.

Per-call timing is aggregated to summary statistics before being exposed;
individual call samples are never persisted or logged per-instrument.
"""

from __future__ import annotations

import time
from collections.abc import Callable, Iterator
from contextlib import contextmanager
from dataclasses import dataclass, field

Clock = Callable[[], float]


def _percentile(sorted_values: list[float], p: float) -> float:
    if not sorted_values:
        return 0.0
    idx = min(len(sorted_values) - 1, max(0, round(p * (len(sorted_values) - 1))))
    return sorted_values[idx]


@dataclass(frozen=True, slots=True)
class _CallSample:
    label: str
    duration_seconds: float
    ok: bool


@dataclass(slots=True)
class CallTimings:
    """In-memory-only per-call durations for one named operation group
    (e.g. one provider loop). Reduced to aggregate statistics via
    `summary()` before ever being exposed -- individual samples never
    leave this object except as the bounded `slowest` diagnostic list."""

    samples: list[_CallSample] = field(default_factory=list)

    def record(self, label: str, duration_seconds: float, *, ok: bool = True) -> None:
        if duration_seconds < 0:
            raise ValueError("duration_seconds must be non-negative")
        self.samples.append(_CallSample(label, duration_seconds, ok))

    def summary(self, *, slowest_n: int = 5) -> dict[str, object]:
        if not self.samples:
            return {"count": 0, "ok_count": 0, "failed_count": 0}
        durations = sorted(s.duration_seconds for s in self.samples)
        ok_count = sum(1 for s in self.samples if s.ok)
        slowest = sorted(self.samples, key=lambda s: s.duration_seconds, reverse=True)[:slowest_n]
        return {
            "count": len(self.samples),
            "ok_count": ok_count,
            "failed_count": len(self.samples) - ok_count,
            "total_seconds": round(sum(durations), 3),
            "min_seconds": round(durations[0], 4),
            "median_seconds": round(_percentile(durations, 0.5), 4),
            "p90_seconds": round(_percentile(durations, 0.90), 4),
            "p95_seconds": round(_percentile(durations, 0.95), 4),
            "max_seconds": round(durations[-1], 4),
            "slowest": [
                {"label": s.label, "duration_seconds": round(s.duration_seconds, 4), "ok": s.ok}
                for s in slowest
            ],
        }


@dataclass(slots=True)
class CycleTimingRecorder:
    """Collects orthogonal wall-clock phase/call durations for one
    production cycle. Discarded and recreated fresh per cycle by the
    caller -- never shared or reused across cycles."""

    clock: Clock = time.monotonic
    phases: dict[str, float] = field(default_factory=dict)
    _call_timings: dict[str, CallTimings] = field(default_factory=dict)

    @contextmanager
    def phase(self, name: str) -> Iterator[None]:
        start = self.clock()
        try:
            yield
        finally:
            elapsed = max(0.0, self.clock() - start)
            self.phases[name] = self.phases.get(name, 0.0) + elapsed

    def record_call(
        self, group: str, label: str, duration_seconds: float, *, ok: bool = True,
    ) -> None:
        self._call_timings.setdefault(group, CallTimings()).record(label, duration_seconds, ok=ok)

    def as_dict(self, *, slowest_n: int = 5) -> dict[str, object]:
        return {
            "phases_seconds": {k: round(v, 3) for k, v in self.phases.items()},
            "call_groups": {
                group: timings.summary(slowest_n=slowest_n)
                for group, timings in self._call_timings.items()
            },
        }
