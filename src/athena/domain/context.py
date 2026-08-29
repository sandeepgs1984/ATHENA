"""PipelineContext — DORMANT/LEGACY (ADR-003 Amendment 1, ID-P0, 2026-08-29).

ID-0's runtime audit found zero non-test callers of ``PipelineContext``,
``ContextDelta``, or the ``IntelligenceModule`` Protocol anywhere in ATHENA's
production code. ATHENA's actual, live, production pipeline runtime is
``athena.runtime.workflow`` (``WorkflowContext``/``WorkflowStage``/
``WorkflowDefinition``/``WorkflowEngine``), wired inside
``OwnerValidationPipeline._scan_eligible``. See ADR-003 Amendment 1 for the
full history and the canonical rule for writing new pipeline stages.

DO NOT use these types for any new production stage, including Intraday
Intelligence (ID-1+) work. They remain here, not deleted, only because
removal has not yet been verified completely safe and trivial — that is a
separate future cleanup milestone's job, not this one's.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from types import MappingProxyType
from typing import Any

from athena.domain.market import CalendarContext
from athena.domain.run import ConfigurationSnapshot, RunRecord


@dataclass(frozen=True, slots=True)
class ContextDelta:
    """A module's contribution to the cycle: the context keys it produces."""

    producer: str
    outputs: Mapping[str, Any]

    def __post_init__(self) -> None:
        if not self.producer:
            raise ValueError("ContextDelta.producer is mandatory")


@dataclass(frozen=True, slots=True)
class PipelineContext:
    """Immutable snapshot of the cycle so far (F-1).

    Modules read what they declared in ``consumes`` and return a ContextDelta
    for what they declared in ``produces``. The orchestrator (Phase 3) applies
    deltas in DAG order via :meth:`with_delta`. No module mutates anything.
    """

    run: RunRecord
    calendar: CalendarContext
    config_snapshot: ConfigurationSnapshot
    data: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        # Freeze the data mapping so no module can mutate shared state.
        object.__setattr__(self, "data", MappingProxyType(dict(self.data)))

    def get(self, key: str) -> Any:
        """Read a produced value; missing keys fail loudly with the producer hint."""
        if key not in self.data:
            raise KeyError(
                f"PipelineContext has no '{key}' yet — check module ordering/'consumes' declaration"
            )
        return self.data[key]

    def has(self, key: str) -> bool:
        return key in self.data

    def with_delta(self, delta: ContextDelta) -> PipelineContext:
        """Return a NEW context with the delta applied. Re-producing a key is a bug."""
        overlap = set(delta.outputs) & set(self.data)
        if overlap:
            raise ValueError(
                f"Module '{delta.producer}' attempted to re-produce existing keys: {sorted(overlap)}"
            )
        merged = dict(self.data)
        merged.update(delta.outputs)
        return PipelineContext(
            run=self.run,
            calendar=self.calendar,
            config_snapshot=self.config_snapshot,
            data=merged,
        )
