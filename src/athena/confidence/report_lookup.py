"""Shared persisted DecisionReport confidence lookup helpers.

Confidence artifacts are stored inside run detail JSON, keyed by decision id.
These helpers keep the persisted shape in one place for read-side services.
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from athena.confidence.models import ConfidenceLevel
from athena.domain.decision import Decision


def pipeline_from_run_detail(detail: Mapping[str, Any]) -> Mapping[str, Any]:
    raw_pipeline = detail.get("pipeline", detail)
    return raw_pipeline if isinstance(raw_pipeline, Mapping) else {}


def decision_report_from_pipeline(
    decision: Decision,
    *,
    pipeline: Mapping[str, Any],
) -> Mapping[str, Any]:
    reports = pipeline.get("decision_reports")
    if not isinstance(reports, Mapping):
        return {}
    candidate = reports.get(decision.decision_id)
    return candidate if isinstance(candidate, Mapping) else {}


def confidence_level_from_report(report: Mapping[str, Any]) -> ConfidenceLevel | None:
    confidence = report.get("confidence")
    if not isinstance(confidence, Mapping) or confidence.get("status") != "OK":
        return None
    try:
        return ConfidenceLevel(str(confidence.get("level")))
    except ValueError:
        return None
