"""Signal drift monitor (M-X10).

Detects scoring/decision config values diverging from a captured baseline
snapshot. File-based, mirroring `FailureAlertDispatcher`'s own artifact-
directory pattern — no new persisted schema, no database table. Alerting
reuses the existing DD-9 `FailureAlertDispatcher` (see
`PlaybookDiagnosticsService`), never a new mechanism.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

from athena.config.models import DecisionConfig, ScoringConfig


@dataclass(frozen=True, slots=True)
class WeightSnapshot:
    """A captured baseline of the scoring weights + decision trade
    threshold, at some point in time. Diagnostic-only, never a domain
    object — comparison target for drift detection, nothing else."""

    captured_at: str
    scoring_weights: dict
    decision_min_composite_for_trade: int

    def to_json(self) -> str:
        return json.dumps(
            {
                "captured_at": self.captured_at,
                "scoring_weights": self.scoring_weights,
                "decision_min_composite_for_trade": self.decision_min_composite_for_trade,
            },
            sort_keys=True, indent=2,
        )

    @classmethod
    def from_json(cls, raw: str) -> WeightSnapshot:
        data = json.loads(raw)
        return cls(
            captured_at=data["captured_at"],
            scoring_weights=dict(data["scoring_weights"]),
            decision_min_composite_for_trade=data["decision_min_composite_for_trade"],
        )


def capture_baseline(
    scoring: ScoringConfig, decision: DecisionConfig, *, as_of: datetime
) -> WeightSnapshot:
    return WeightSnapshot(
        captured_at=as_of.isoformat(),
        scoring_weights=scoring.weights.model_dump(),
        decision_min_composite_for_trade=decision.thresholds.min_composite_for_trade,
    )


def write_baseline(path: Path, snapshot: WeightSnapshot) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(snapshot.to_json() + "\n", encoding="utf-8")


def read_baseline(path: Path) -> WeightSnapshot | None:
    if not path.exists():
        return None
    return WeightSnapshot.from_json(path.read_text(encoding="utf-8"))


def detect_drift(
    baseline: WeightSnapshot, scoring: ScoringConfig, decision: DecisionConfig
) -> list[str]:
    """Human-readable drift descriptions, one per changed value; empty if
    nothing has drifted from the baseline."""
    drifts: list[str] = []
    current_weights = scoring.weights.model_dump()
    for dim, base_val in sorted(baseline.scoring_weights.items()):
        cur_val = current_weights.get(dim)
        if cur_val != base_val:
            drifts.append(f"scoring.weights.{dim}: {base_val} -> {cur_val}")
    cur_threshold = decision.thresholds.min_composite_for_trade
    if cur_threshold != baseline.decision_min_composite_for_trade:
        drifts.append(
            "decision.thresholds.min_composite_for_trade: "
            f"{baseline.decision_min_composite_for_trade} -> {cur_threshold}"
        )
    return drifts
