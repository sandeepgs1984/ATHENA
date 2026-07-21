"""Explainability Engine artifacts (P6.3).

Immutable rationale and explanation models for platform artifacts. The Explainability
Engine provides human-readable explanations describing why decisions, allocations, sizing,
execution plans, lifecycle outcomes, and analytics were produced.

It performs NO state mutation, NO decision altering, NO LLM generation, and NO market analysis.
"""

from __future__ import annotations

import json
from collections.abc import Mapping
from dataclasses import dataclass, field
from datetime import datetime
from types import MappingProxyType

from athena.config.models import ExplanationDomain


@dataclass(frozen=True, slots=True)
class ExplanationReferences:
    """Cross-references back to originating platform artifacts."""

    decision_id: str | None = None
    portfolio_snapshot_id: str | None = None
    allocation_plan_id: str | None = None
    position_sizing_plan_id: str | None = None
    execution_plan_id: str | None = None
    broker_execution_plan_id: str | None = None
    execution_state_id: str | None = None
    performance_snapshot_id: str | None = None
    report_id: str | None = None
    schedule_execution_id: str | None = None

    def to_dict(self) -> dict[str, object]:
        return {
            "decision_id": self.decision_id,
            "portfolio_snapshot_id": self.portfolio_snapshot_id,
            "allocation_plan_id": self.allocation_plan_id,
            "position_sizing_plan_id": self.position_sizing_plan_id,
            "execution_plan_id": self.execution_plan_id,
            "broker_execution_plan_id": self.broker_execution_plan_id,
            "execution_state_id": self.execution_state_id,
            "performance_snapshot_id": self.performance_snapshot_id,
            "report_id": self.report_id,
            "schedule_execution_id": self.schedule_execution_id,
        }


@dataclass(frozen=True, slots=True)
class ExplanationSection:
    """A single section of rationale within an Explanation."""

    section_id: str
    title: str
    domain: ExplanationDomain
    rationale: str
    facts: Mapping[str, object]

    def __post_init__(self) -> None:
        if not self.section_id or not self.title or not self.rationale:
            raise ValueError("ExplanationSection mandatory fields missing")
        object.__setattr__(self, "facts", MappingProxyType(dict(self.facts)))

    def to_dict(self) -> dict[str, object]:
        return {
            "section_id": self.section_id,
            "title": self.title,
            "domain": self.domain.value,
            "rationale": self.rationale,
            "facts": json.loads(json.dumps(dict(self.facts))),
        }


@dataclass(frozen=True, slots=True)
class Explanation:
    """An immutable explanation artifact for a specific domain outcome."""

    explanation_id: str
    domain: ExplanationDomain
    title: str
    summary: str
    sections: tuple[ExplanationSection, ...]
    as_of: datetime
    references: ExplanationReferences = field(default_factory=ExplanationReferences)

    def __post_init__(self) -> None:
        if not self.explanation_id or not self.title or not self.summary:
            raise ValueError("Explanation mandatory fields missing")
        if self.as_of.tzinfo is None:
            raise ValueError("Explanation.as_of must be timezone-aware")

    def to_dict(self) -> dict[str, object]:
        return {
            "explanation_id": self.explanation_id,
            "domain": self.domain.value,
            "title": self.title,
            "summary": self.summary,
            "sections": [s.to_dict() for s in self.sections],
            "as_of": self.as_of.isoformat(),
            "references": self.references.to_dict(),
        }

    def to_text(self) -> str:
        lines = [f"[{self.domain.value}] {self.title}", f"Summary: {self.summary}"]
        for s in self.sections:
            lines.append(f"\n--- {s.title} ---\n{s.rationale}")
        return "\n".join(lines)


@dataclass(frozen=True, slots=True)
class ExplanationSnapshot:
    """Aggregated snapshot of explanations across multiple domains."""

    snapshot_id: str
    as_of: datetime
    explanations: tuple[Explanation, ...]
    summary_text: str
    references: ExplanationReferences = field(default_factory=ExplanationReferences)

    def __post_init__(self) -> None:
        if not self.snapshot_id or not self.summary_text:
            raise ValueError("ExplanationSnapshot mandatory fields missing")
        if self.as_of.tzinfo is None:
            raise ValueError("ExplanationSnapshot.as_of must be timezone-aware")

    def explanation_by_domain(self, domain: ExplanationDomain) -> Explanation | None:
        """Find explanation by domain."""
        return next((e for e in self.explanations if e.domain == domain), None)

    def to_dict(self) -> dict[str, object]:
        return {
            "snapshot_id": self.snapshot_id,
            "as_of": self.as_of.isoformat(),
            "explanations": [e.to_dict() for e in self.explanations],
            "summary_text": self.summary_text,
            "references": self.references.to_dict(),
        }

    def to_json(self) -> str:
        """Deterministic JSON representation."""
        return json.dumps(self.to_dict(), sort_keys=True, indent=2)


@dataclass(frozen=True, slots=True)
class ExplanationHistory:
    """Append-only record of explanation snapshots."""

    records: tuple[ExplanationSnapshot, ...] = ()

    def record(self, snapshot: ExplanationSnapshot) -> ExplanationHistory:
        """Return a new history with snapshot appended."""
        return ExplanationHistory(records=self.records + (snapshot,))

    def for_domain(self, domain: ExplanationDomain) -> tuple[Explanation, ...]:
        """Collect all explanations for a domain across history."""
        res = []
        for snap in self.records:
            exp = snap.explanation_by_domain(domain)
            if exp is not None:
                res.append(exp)
        return tuple(res)

    def to_dict(self) -> dict[str, object]:
        return {"records": [s.to_dict() for s in self.records]}
