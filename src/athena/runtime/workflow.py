"""Workflow Orchestration Engine (M4.1).

The central coordinator that executes a pipeline of stages in deterministic
dependency order. It COORDINATES ONLY — each stage's callable invokes the
existing analytical engines; the orchestrator never performs analysis, never
duplicates engine logic, and never modifies an engine.

Guarantees:
- Deterministic execution: stages run in a stable topological order.
- Dependency validation: missing dependencies or cycles are rejected up front.
- Failure isolation: a failed stage is recorded and its downstream dependents
  are skipped; independent branches still run.
- Timing metadata: per-stage offset + duration via an injected clock (a fixed
  clock makes executions bit-identical, i.e. replayable).
- Immutable execution report: returns a frozen WorkflowExecution.
"""

from __future__ import annotations

import time as _time
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass, field
from datetime import datetime

from athena.errors import WorkflowError
from athena.runtime.models import ExecutionStatus, StageResult, WorkflowExecution

StageFn = Callable[["WorkflowContext"], Mapping[str, object]]


class WorkflowContext:
    """Accumulator passed to each stage: read prior outputs, return new ones.

    Stages never mutate the context directly; they return a mapping of outputs
    that the engine merges (rejecting collisions). Read access only here.
    """

    def __init__(self, as_of: datetime, initial: Mapping[str, object] | None = None) -> None:
        self._as_of = as_of
        self._data: dict[str, object] = dict(initial or {})

    @property
    def as_of(self) -> datetime:
        return self._as_of

    def get(self, key: str) -> object:
        if key not in self._data:
            raise KeyError(f"workflow context has no '{key}' yet")
        return self._data[key]

    def has(self, key: str) -> bool:
        return key in self._data

    def keys(self) -> tuple[str, ...]:
        return tuple(self._data)

    def _merge(self, producer: str, outputs: Mapping[str, object]) -> None:
        overlap = set(outputs) & set(self._data)
        if overlap:
            raise WorkflowError(f"stage '{producer}' re-produces existing keys: {sorted(overlap)}")
        self._data.update(outputs)


@dataclass(frozen=True, slots=True)
class WorkflowStage:
    """One coordinated step. ``run`` invokes an analytical engine and returns outputs."""

    name: str
    run: StageFn
    depends_on: tuple[str, ...] = ()
    produces: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        if not self.name:
            raise ValueError("WorkflowStage.name is mandatory")
        if not callable(self.run):
            raise ValueError(f"WorkflowStage '{self.name}'.run must be callable")


@dataclass(frozen=True, slots=True)
class WorkflowDefinition:
    """An ordered, validated set of stages forming a DAG."""

    name: str
    stages: tuple[WorkflowStage, ...]
    _order: tuple[str, ...] = field(default=(), compare=False)

    def __post_init__(self) -> None:
        if not self.name:
            raise ValueError("WorkflowDefinition.name is mandatory")
        if not self.stages:
            raise ValueError("WorkflowDefinition must contain at least one stage")
        names = [s.name for s in self.stages]
        if len(names) != len(set(names)):
            raise WorkflowError(f"duplicate stage names in workflow '{self.name}'")
        known = set(names)
        for stage in self.stages:
            missing = [d for d in stage.depends_on if d not in known]
            if missing:
                raise WorkflowError(
                    f"stage '{stage.name}' depends on unknown stage(s): {missing}")
        object.__setattr__(self, "_order", self._topological_order())

    def _topological_order(self) -> tuple[str, ...]:
        """Deterministic Kahn topological sort; declaration order breaks ties."""
        index = {s.name: i for i, s in enumerate(self.stages)}
        deps = {s.name: set(s.depends_on) for s in self.stages}
        remaining = set(deps)
        order: list[str] = []
        while remaining:
            ready = sorted((n for n in remaining if not deps[n] - set(order)),
                           key=lambda n: index[n])
            if not ready:
                raise WorkflowError(
                    f"cycle detected in workflow '{self.name}' among {sorted(remaining)}")
            order.extend(ready)
            remaining -= set(ready)
        return tuple(order)

    @property
    def execution_order(self) -> tuple[str, ...]:
        return self._order

    def stage(self, name: str) -> WorkflowStage:
        return next(s for s in self.stages if s.name == name)


class WorkflowEngine:
    """Deterministic coordinator of analytical engines. Performs no analysis itself."""

    def __init__(self, clock: Callable[[], float] = _time.monotonic) -> None:
        self._clock = clock

    def execute(
        self,
        definition: WorkflowDefinition,
        *,
        as_of: datetime,
        initial: Mapping[str, object] | None = None,
    ) -> WorkflowExecution:
        ctx = WorkflowContext(as_of, initial)
        results: list[StageResult] = []
        failed_or_skipped: set[str] = set()
        by_name = {s.name: definition.stage(s.name) for s in definition.stages}

        start = self._clock()
        for name in definition.execution_order:
            stage = by_name[name]
            offset = self._clock() - start
            blocking = [d for d in stage.depends_on if d in failed_or_skipped]
            if blocking:
                results.append(StageResult(
                    stage_name=name, status=ExecutionStatus.SKIPPED,
                    started_offset_seconds=offset, duration_seconds=0.0,
                    output_keys=(), error=None,
                    explanation=f"skipped: upstream stage(s) not completed: {blocking}"))
                failed_or_skipped.add(name)
                continue
            t0 = self._clock()
            try:
                outputs = dict(stage.run(ctx))
                if stage.produces and set(outputs) != set(stage.produces):
                    raise WorkflowError(
                        f"stage '{name}' produced {sorted(outputs)} but declared "
                        f"{sorted(stage.produces)}")
                ctx._merge(name, outputs)
            except Exception as exc:
                dur = self._clock() - t0
                results.append(StageResult(
                    stage_name=name, status=ExecutionStatus.FAILED,
                    started_offset_seconds=offset, duration_seconds=dur,
                    output_keys=(), error=f"{type(exc).__name__}: {exc}",
                    explanation=f"stage '{name}' failed during execution"))
                failed_or_skipped.add(name)
                continue
            dur = self._clock() - t0
            results.append(StageResult(
                stage_name=name, status=ExecutionStatus.COMPLETED,
                started_offset_seconds=offset, duration_seconds=dur,
                output_keys=tuple(sorted(outputs)), error=None,
                explanation=f"stage '{name}' completed"))
        total = self._clock() - start

        status = (ExecutionStatus.FAILED
                  if any(r.status is not ExecutionStatus.COMPLETED for r in results)
                  else ExecutionStatus.COMPLETED)
        return WorkflowExecution(
            execution_id=f"wf-{definition.name}-{as_of.isoformat()}",
            workflow_name=definition.name, as_of=as_of, status=status,
            stage_results=tuple(results), total_duration_seconds=total,
            produced_keys=ctx.keys())


def build_definition(name: str, stages: Sequence[WorkflowStage]) -> WorkflowDefinition:
    """Convenience constructor for a workflow definition."""
    return WorkflowDefinition(name=name, stages=tuple(stages))
