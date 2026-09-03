"""Portfolio Conviction confidence retrieval adapter (PS-P7B).

The adapter owns the persisted run-detail representation and returns compact,
typed evidence for the pure Portfolio interpreter.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from enum import Enum, unique
from typing import Any

from athena.confidence.models import ConfidenceLevel
from athena.confidence.report_lookup import (
    confidence_level_from_report,
    decision_report_from_pipeline,
    pipeline_from_run_detail,
)
from athena.data.store.repository import SqliteRepository
from athena.domain.decision import Decision


@unique
class PortfolioConfidenceReason(str, Enum):
    FROM_CONFIDENCE = "CONVICTION_FROM_CONFIDENCE"
    UNAVAILABLE = "CONVICTION_CONFIDENCE_UNAVAILABLE"
    INCOHERENT = "CONVICTION_CONFIDENCE_INCOHERENT"


@dataclass(frozen=True, slots=True)
class PortfolioConfidenceEvidence:
    decision_id: str | None
    run_id: str | None
    level: ConfidenceLevel | None
    is_coherent: bool
    reason: PortfolioConfidenceReason
    source: str = "decision_report.confidence"


class PortfolioConfidenceAdapter:
    """Resolve ConfidenceAssessment level for an already-accepted Decision."""

    def __init__(self, repo: SqliteRepository) -> None:
        self._repo = repo
        self._pipeline_by_run_id: dict[str, Mapping[str, Any] | None] = {}

    def resolve(
        self,
        *,
        decision: Decision | None,
        instrument_id: str,
        decision_is_coherent: bool,
    ) -> PortfolioConfidenceEvidence:
        if decision is None:
            return self._unavailable()
        if not decision_is_coherent or decision.instrument_id != instrument_id:
            return PortfolioConfidenceEvidence(
                decision_id=decision.decision_id,
                run_id=decision.run_id,
                level=None,
                is_coherent=False,
                reason=PortfolioConfidenceReason.INCOHERENT,
            )
        pipeline = self._pipeline_for_run(decision.run_id)
        if pipeline is None:
            return PortfolioConfidenceEvidence(
                decision_id=decision.decision_id,
                run_id=decision.run_id,
                level=None,
                is_coherent=True,
                reason=PortfolioConfidenceReason.UNAVAILABLE,
            )
        report = decision_report_from_pipeline(decision, pipeline=pipeline)
        level = confidence_level_from_report(report)
        if level is None:
            return PortfolioConfidenceEvidence(
                decision_id=decision.decision_id,
                run_id=decision.run_id,
                level=None,
                is_coherent=True,
                reason=PortfolioConfidenceReason.UNAVAILABLE,
            )
        return PortfolioConfidenceEvidence(
            decision_id=decision.decision_id,
            run_id=decision.run_id,
            level=level,
            is_coherent=True,
            reason=PortfolioConfidenceReason.FROM_CONFIDENCE,
        )

    def _pipeline_for_run(self, run_id: str) -> Mapping[str, Any] | None:
        if run_id not in self._pipeline_by_run_id:
            try:
                self._pipeline_by_run_id[run_id] = pipeline_from_run_detail(
                    self._repo.get_run_detail(run_id)
                )
            except Exception:
                self._pipeline_by_run_id[run_id] = None
        return self._pipeline_by_run_id[run_id]

    @staticmethod
    def _unavailable() -> PortfolioConfidenceEvidence:
        return PortfolioConfidenceEvidence(
            decision_id=None,
            run_id=None,
            level=None,
            is_coherent=False,
            reason=PortfolioConfidenceReason.UNAVAILABLE,
        )
