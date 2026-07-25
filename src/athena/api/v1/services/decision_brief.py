"""Deterministic Decision Brief export composition (M-D4).

Composes already-persisted Decision + Depth + Context DTOs into one immutable,
presentation-only snapshot. Adds no analysis, no recomputation, no news.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime

from athena.api.v1.dtos.decisions import (
    DecisionContextDTO,
    DecisionDepthDTO,
    DecisionDTO,
)


@dataclass(frozen=True, slots=True)
class DecisionBriefSnapshot:
    """Immutable, faithful composition of a decision's brief for export."""

    brief_id: str
    as_of: datetime
    decision: DecisionDTO
    depth: DecisionDepthDTO
    context: DecisionContextDTO

    def __post_init__(self) -> None:
        if not self.brief_id:
            raise ValueError("DecisionBriefSnapshot.brief_id is mandatory")
        if self.as_of.tzinfo is None:
            raise ValueError("DecisionBriefSnapshot.as_of must be timezone-aware")

    def to_dict(self) -> dict[str, object]:
        return {
            "brief_id": self.brief_id,
            "as_of": self.as_of.isoformat(),
            "decision": json.loads(self.decision.model_dump_json()),
            "depth": json.loads(self.depth.model_dump_json()),
            "context": json.loads(self.context.model_dump_json()),
        }

    def to_json(self) -> str:
        return json.dumps(self.to_dict(), sort_keys=True, indent=2)

    def to_text(self) -> str:
        d, depth, ctx = self.decision, self.depth, self.context
        lines = [
            "ATHENA DECISION BRIEF",
            "=" * 60,
            f"Decision   : {d.metadata.decision_type} ({d.metadata.direction})",
            f"Instrument : {d.metadata.instrument_id}",
            f"Timestamp  : {d.metadata.ts.isoformat()}",
            f"Reasoning  : {d.explanation}",
            "",
            "ELIGIBILITY",
            "-" * 60,
            f"  {depth.eligibility.status}: {depth.eligibility.summary}",
            "",
            "SCORE / CONFIDENCE / RISK",
            "-" * 60,
            f"  score: {depth.score.value} ({depth.score.status})",
            f"  confidence: {depth.confidence.value} ({depth.confidence.status})",
            f"  risk: {depth.risk.value} ({depth.risk.status})",
            "",
            "SESSION CONTEXT",
            "-" * 60,
            f"  {ctx.calendar.session_type} on {ctx.calendar.context_date} "
            f"({ctx.calendar.exchange})",
            "",
            "REGIME / MARKET HEALTH",
            "-" * 60,
            f"  regime: {ctx.regime.status} {', '.join(ctx.regime.labels)}",
            f"  market health: {ctx.market_health.status}",
            "",
            "EXTERNAL LINKS",
            "-" * 60,
        ]
        if not ctx.external_links:
            lines.append("  (none)")
        for link in ctx.external_links:
            lines.append(f"  - {link.title} ({link.source}): {link.url}")
        return "\n".join(lines)
