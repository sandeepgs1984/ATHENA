"""Daily Market Scanner (M4.2).

Answers one question: "What does ATHENA conclude today for every eligible
instrument?" It executes ATHENA's complete analytical workflow across the
approved universe — one workflow per instrument through the shared
WorkflowEngine — and collects the results into an immutable DailyScanReport.

The scanner COORDINATES ONLY. It reuses WorkflowEngine and
DecisionReportingEngine, invokes analytical engines only inside workflow stages
(supplied by the caller's per-instrument pipeline builder), duplicates no
orchestration logic, and recalculates nothing.

Deterministic: instruments scan in stable sorted order. Failure isolation: one
instrument's failure never terminates the scan.
"""

from __future__ import annotations

from collections.abc import Sequence
from datetime import datetime

from athena.reporting.engine import DecisionReportingEngine
from athena.runtime.models import ExecutionStatus
from athena.runtime.workflow import WorkflowEngine
from athena.scanner.models import (
    DailyScanReport,
    InstrumentScanResult,
    PipelineBuilder,
    ScanStatistics,
    ScanSummary,
)


class DailyMarketScanner:
    """Coordinates full-universe workflow execution into a daily scan report."""

    def __init__(
        self,
        workflow_engine: WorkflowEngine,
        reporting_engine: DecisionReportingEngine | None = None,
    ) -> None:
        self._workflow_engine = workflow_engine
        self._reporting = reporting_engine or DecisionReportingEngine()

    def scan(
        self,
        universe: Sequence[str],
        *,
        as_of: datetime,
        pipeline_builder: PipelineBuilder,
    ) -> DailyScanReport:
        results: list[InstrumentScanResult] = []
        for instrument_id in sorted(set(universe)):
            results.append(self._scan_one(instrument_id, as_of, pipeline_builder))

        successful = sum(1 for r in results if r.status is ExecutionStatus.COMPLETED)
        failed = sum(1 for r in results if r.status is ExecutionStatus.FAILED)
        skipped = sum(1 for r in results if r.status is ExecutionStatus.SKIPPED)
        statistics = ScanStatistics(total=len(results), successful=successful,
                                    failed=failed, skipped=skipped)

        counts: dict[str, int] = {}
        for r in results:
            if r.status is ExecutionStatus.COMPLETED and r.decision_type is not None:
                counts[r.decision_type] = counts.get(r.decision_type, 0) + 1
        summary = ScanSummary(decision_counts=counts)

        return DailyScanReport(
            scan_id=f"scan-{as_of.isoformat()}", as_of=as_of, results=tuple(results),
            statistics=statistics, summary=summary)

    # ------------------------------------------------------------- internals

    def _scan_one(self, instrument_id, as_of, pipeline_builder) -> InstrumentScanResult:
        # Building or executing one instrument must never abort the whole scan.
        try:
            plan = pipeline_builder(instrument_id)
        except Exception as exc:
            return InstrumentScanResult(
                instrument_id=instrument_id, status=ExecutionStatus.FAILED,
                decision_type=None, workflow_execution=None, report=None,
                note=f"pipeline build failed: {type(exc).__name__}: {exc}")

        if plan is None:
            return InstrumentScanResult(
                instrument_id=instrument_id, status=ExecutionStatus.SKIPPED,
                decision_type=None, workflow_execution=None, report=None,
                note="skipped: no pipeline for instrument")

        try:
            execution = self._workflow_engine.execute(plan.definition, as_of=as_of)
        except Exception as exc:
            return InstrumentScanResult(
                instrument_id=instrument_id, status=ExecutionStatus.FAILED,
                decision_type=None, workflow_execution=None, report=None,
                note=f"workflow execution error: {type(exc).__name__}: {exc}")

        if execution.status is not ExecutionStatus.COMPLETED:
            return InstrumentScanResult(
                instrument_id=instrument_id, status=ExecutionStatus.FAILED,
                decision_type=None, workflow_execution=execution, report=None,
                note=f"workflow did not complete ({execution.status.value})")

        try:
            capture = plan.collect()
        except Exception as exc:
            return InstrumentScanResult(
                instrument_id=instrument_id, status=ExecutionStatus.FAILED,
                decision_type=None, workflow_execution=execution, report=None,
                note=f"result collection failed: {type(exc).__name__}: {exc}")

        if capture is None:
            return InstrumentScanResult(
                instrument_id=instrument_id, status=ExecutionStatus.FAILED,
                decision_type=None, workflow_execution=execution, report=None,
                note="workflow completed but produced no decision outcome")

        report = self._reporting.report(
            capture.outcome, scoring=capture.scoring, confidence=capture.confidence,
            risk=capture.risk, evidence_bundle=capture.evidence_bundle,
            indicators=capture.indicators)
        return InstrumentScanResult(
            instrument_id=instrument_id, status=ExecutionStatus.COMPLETED,
            decision_type=capture.outcome.decision.decision_type.value,
            workflow_execution=execution, report=report,
            note=f"scanned: {capture.outcome.decision.decision_type.value}")
