"""Observability skeleton (F-7, F-11): timings now, richer metrics as phases land.

Time is injected (a callable returning seconds) so metric-using code stays
deterministic and testable — no hidden clock reads in business logic (§13).
"""

from __future__ import annotations

import time as _time
from contextlib import contextmanager
from dataclasses import dataclass, field
from typing import Callable, Dict, Iterator, List, Mapping, Tuple


@dataclass(frozen=True, slots=True)
class BudgetViolation:
    operation: str
    budget_seconds: float
    actual_seconds: float

    def __str__(self) -> str:
        return (f"performance budget exceeded: {self.operation} took "
                f"{self.actual_seconds:.2f}s (budget {self.budget_seconds:.0f}s)")


@dataclass
class MetricsRegistry:
    """Collects named durations for one run; queried for budget violations (§8.7)."""

    clock: Callable[[], float] = _time.monotonic
    _durations: Dict[str, List[float]] = field(default_factory=dict)

    @contextmanager
    def timer(self, operation: str) -> Iterator[None]:
        start = self.clock()
        try:
            yield
        finally:
            self.record(operation, self.clock() - start)

    def record(self, operation: str, seconds: float) -> None:
        if seconds < 0:
            raise ValueError(f"negative duration for {operation}: {seconds}")
        self._durations.setdefault(operation, []).append(seconds)

    def total(self, operation: str) -> float:
        return sum(self._durations.get(operation, []))

    def summary(self) -> Mapping[str, float]:
        return {op: sum(vals) for op, vals in sorted(self._durations.items())}

    def budget_violations(self, budgets: Mapping[str, float]) -> Tuple[BudgetViolation, ...]:
        violations = []
        for operation, budget in budgets.items():
            actual = self.total(operation)
            if actual > budget:
                violations.append(BudgetViolation(operation, budget, actual))
        return tuple(violations)
