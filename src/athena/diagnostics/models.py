"""Immutable playbook diagnostic artifacts (M10.4). Propose only — never apply."""

from __future__ import annotations

import json
from collections.abc import Mapping
from dataclasses import dataclass
from datetime import datetime
from enum import Enum, unique
from types import MappingProxyType


@unique
class DiagnosticStatus(str, Enum):
    OK = "OK"
    DEGRADED = "DEGRADED"
    INSUFFICIENT_DATA = "INSUFFICIENT_DATA"


@dataclass(frozen=True, slots=True)
class DiagnosticFinding:
    finding_id: str
    category: str
    severity: str
    summary: str
    evidence: Mapping[str, object]

    def __post_init__(self) -> None:
        if not self.finding_id or not self.summary:
            raise ValueError("DiagnosticFinding requires finding_id and summary")
        object.__setattr__(self, "evidence", MappingProxyType(dict(self.evidence)))

    def to_dict(self) -> dict[str, object]:
        return {
            "finding_id": self.finding_id,
            "category": self.category,
            "severity": self.severity,
            "summary": self.summary,
            "evidence": dict(self.evidence),
        }


@dataclass(frozen=True, slots=True)
class TuningProposal:
    """A human-reviewed config change suggestion. Never auto-applied."""

    proposal_id: str
    target_config: str
    parameter_path: str
    current_value: int | float | str
    proposed_value: int | float | str
    delta: int | float | None
    rationale: str
    sample_size: int
    metric_name: str
    metric_value: str
    blocked: bool = False
    block_reason: str = ""

    def __post_init__(self) -> None:
        if not self.proposal_id or not self.rationale:
            raise ValueError("TuningProposal requires proposal_id and rationale")
        if self.blocked and not self.block_reason:
            raise ValueError("blocked TuningProposal must carry block_reason")

    def to_dict(self) -> dict[str, object]:
        return {
            "proposal_id": self.proposal_id,
            "target_config": self.target_config,
            "parameter_path": self.parameter_path,
            "current_value": self.current_value,
            "proposed_value": self.proposed_value,
            "delta": self.delta,
            "rationale": self.rationale,
            "sample_size": self.sample_size,
            "metric_name": self.metric_name,
            "metric_value": self.metric_value,
            "blocked": self.blocked,
            "block_reason": self.block_reason,
        }


@dataclass(frozen=True, slots=True)
class DiagnosticReport:
    report_id: str
    as_of: datetime
    status: DiagnosticStatus
    findings: tuple[DiagnosticFinding, ...]
    proposals: tuple[TuningProposal, ...]
    input_digest: str
    degradation_reasons: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        if not self.report_id:
            raise ValueError("DiagnosticReport.report_id is mandatory")
        if self.as_of.tzinfo is None:
            raise ValueError("DiagnosticReport.as_of must be timezone-aware")
        if self.status is DiagnosticStatus.DEGRADED and not self.degradation_reasons:
            raise ValueError("DEGRADED report must carry degradation_reasons")
        if self.status is DiagnosticStatus.OK and self.degradation_reasons:
            raise ValueError("OK report cannot carry degradation_reasons")

    def to_dict(self) -> dict[str, object]:
        return {
            "report_id": self.report_id,
            "as_of": self.as_of.isoformat(),
            "status": self.status.value,
            "findings": [f.to_dict() for f in self.findings],
            "proposals": [p.to_dict() for p in self.proposals],
            "input_digest": self.input_digest,
            "degradation_reasons": list(self.degradation_reasons),
            "actionable_proposals": sum(1 for p in self.proposals if not p.blocked),
            "blocked_proposals": sum(1 for p in self.proposals if p.blocked),
        }

    def to_json(self) -> str:
        return json.dumps(self.to_dict(), sort_keys=True, indent=2)

    def to_text(self) -> str:
        lines = [
            f"ATHENA Playbook Diagnostics {self.report_id}",
            f"as_of: {self.as_of.isoformat()}",
            f"status: {self.status.value}",
            f"input_digest: {self.input_digest}",
            "",
            f"Findings ({len(self.findings)}):",
        ]
        if not self.findings:
            lines.append("  (none)")
        else:
            for f in self.findings:
                lines.append(f"  - [{f.severity}] {f.category}: {f.summary}")
        lines.append("")
        lines.append(f"Proposals ({len(self.proposals)}):")
        if not self.proposals:
            lines.append("  (none)")
        else:
            for p in self.proposals:
                flag = "BLOCKED" if p.blocked else "REVIEW"
                lines.append(
                    f"  - [{flag}] {p.proposal_id} {p.target_config}:{p.parameter_path} "
                    f"{p.current_value} -> {p.proposed_value}: {p.rationale}"
                )
                if p.blocked:
                    lines.append(f"      block: {p.block_reason}")
        if self.degradation_reasons:
            lines.append("")
            lines.append("Degradation:")
            for reason in self.degradation_reasons:
                lines.append(f"  - {reason}")
        lines.append("")
        lines.append("IMPORTANT: Proposals are never auto-applied. Human review required.")
        return "\n".join(lines) + "\n"
