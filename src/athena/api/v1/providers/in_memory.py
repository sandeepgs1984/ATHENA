"""In-memory default provider implementations (P8.3).

Exposes mock/seeded datasets for development and testing. Filtering, sorting, and
pagination logic are executed using pure-Python collection query evaluation.
"""

from __future__ import annotations

import contextlib
from collections.abc import Callable
from datetime import datetime, timezone
from decimal import Decimal
from typing import Any, TypeVar

from athena.api.v1.dtos import CollectionResult, QuerySpecification
from athena.domain.decision import Decision, GateResult, Portfolio, Position
from athena.domain.enums import DecisionType, Direction, QualityGate
from athena.orchestration.models import SystemPipelineResult
from athena.orchestration.schedule_models import PipelineScheduleRun
from athena.workspace.models import WorkspaceSnapshot, WorkspaceSummary

T = TypeVar("T")
F = TypeVar("F")


def apply_query_spec(
    items: list[T],
    spec: QuerySpecification[Any],
    filter_func: Callable[[T], bool],
    sort_key_func: Callable[[T], Any] | None = None,
) -> CollectionResult[T]:
    """Generic helper evaluating QuerySpecification constraints against a list."""
    # 1. Apply filtering
    filtered_items = [x for x in items if filter_func(x)]

    # 2. Apply sorting
    if spec.sort.sort_by and sort_key_func:
        reverse = spec.sort.sort_dir == "desc"
        with contextlib.suppress(Exception):
            filtered_items = sorted(
                filtered_items, key=sort_key_func, reverse=reverse
            )

    # 3. Apply pagination
    total = len(filtered_items)
    start = (spec.pagination.page - 1) * spec.pagination.page_size
    end = start + spec.pagination.page_size
    sliced = filtered_items[start:end]

    return CollectionResult(
        items=tuple(sliced),
        total_count=total,
        page=spec.pagination.page,
        page_size=spec.pagination.page_size,
    )


class InMemoryDecisionProvider:
    """In-memory provider for Decisions."""

    def __init__(self) -> None:
        self.decisions: list[Decision] = []

    def get_decisions(
        self, spec: QuerySpecification[Any]
    ) -> CollectionResult[Decision]:
        def filter_func(d: Decision) -> bool:
            f = spec.filters
            if f.instrument_id and d.instrument_id != f.instrument_id:
                return False
            if f.decision_type and d.decision_type != f.decision_type:
                return False
            if f.direction and d.direction != f.direction:
                return False
            if f.from_date and d.ts < f.from_date:
                return False
            return not (f.to_date and d.ts > f.to_date)

        def sort_func(d: Decision) -> Any:
            sort_by = spec.sort.sort_by
            if sort_by == "ts":
                return d.ts
            if sort_by == "instrument_id":
                return d.instrument_id or ""
            return d.decision_id

        return apply_query_spec(self.decisions, spec, filter_func, sort_func)

    def get_decision(self, decision_id: str) -> Decision | None:
        for d in self.decisions:
            if d.decision_id == decision_id:
                return d
        return None


class InMemoryPortfolioProvider:
    """In-memory provider for Portfolio."""

    def __init__(self) -> None:
        self.portfolio: Portfolio | None = None

    def get_portfolio(self) -> Portfolio | None:
        return self.portfolio


class InMemoryPipelineRunProvider:
    """In-memory provider for Pipeline runs."""

    def __init__(self) -> None:
        self.runs: list[SystemPipelineResult] = []

    def get_runs(
        self, spec: QuerySpecification[Any]
    ) -> CollectionResult[SystemPipelineResult]:
        def filter_func(r: SystemPipelineResult) -> bool:
            f = spec.filters
            if f.overall_status and r.overall_status != f.overall_status:
                return False
            if f.from_date and r.as_of < f.from_date:
                return False
            return not (f.to_date and r.as_of > f.to_date)

        def sort_func(r: SystemPipelineResult) -> Any:
            if spec.sort.sort_by == "as_of":
                return r.as_of
            return r.run_id

        return apply_query_spec(self.runs, spec, filter_func, sort_func)

    def get_run(self, run_id: str) -> SystemPipelineResult | None:
        for r in self.runs:
            if r.run_id == run_id:
                return r
        return None


class InMemorySchedulerHistoryProvider:
    """In-memory provider for Scheduler executions."""

    def __init__(self) -> None:
        self.runs: list[PipelineScheduleRun] = []

    def get_history(
        self, spec: QuerySpecification[Any]
    ) -> CollectionResult[PipelineScheduleRun]:
        def filter_func(r: PipelineScheduleRun) -> bool:
            f = spec.filters
            if f.job_id and r.job_id != f.job_id:
                return False
            if (
                f.overall_status
                and r.system_result.overall_status != f.overall_status
            ):
                return False
            if f.from_date and r.system_result.as_of < f.from_date:
                return False
            return not (f.to_date and r.system_result.as_of > f.to_date)

        def sort_func(r: PipelineScheduleRun) -> Any:
            if spec.sort.sort_by == "as_of":
                return r.system_result.as_of
            return r.schedule_run_id

        return apply_query_spec(self.runs, spec, filter_func, sort_func)

    def get_run(self, schedule_run_id: str) -> PipelineScheduleRun | None:
        for r in self.runs:
            if r.schedule_run_id == schedule_run_id:
                return r
        return None


class InMemoryWorkspaceProvider:
    """In-memory provider for Workspace snapshots."""

    def __init__(self) -> None:
        self.snapshots: list[WorkspaceSnapshot] = []

    def get_snapshots(
        self, spec: QuerySpecification[Any]
    ) -> CollectionResult[WorkspaceSnapshot]:
        def filter_func(s: WorkspaceSnapshot) -> bool:
            f = spec.filters
            if f.overall_health and s.summary.overall_health != f.overall_health:
                return False
            if f.from_date and s.as_of < f.from_date:
                return False
            return not (f.to_date and s.as_of > f.to_date)

        def sort_func(s: WorkspaceSnapshot) -> Any:
            if spec.sort.sort_by == "as_of":
                return s.as_of
            return s.snapshot_id

        return apply_query_spec(self.snapshots, spec, filter_func, sort_func)

    def get_snapshot(self, snapshot_id: str) -> WorkspaceSnapshot | None:
        for s in self.snapshots:
            if s.snapshot_id == snapshot_id:
                return s
        return None


# ---------------------------------------------------------------------------
# Default Sample Data Seed Functions (P8.3 scaffolding)
# ---------------------------------------------------------------------------

def seed_sample_data(
    decision_prov: InMemoryDecisionProvider,
    portfolio_prov: InMemoryPortfolioProvider,
    pipeline_prov: InMemoryPipelineRunProvider,
    scheduler_prov: InMemorySchedulerHistoryProvider,
    workspace_prov: InMemoryWorkspaceProvider,
) -> None:
    """Seeds in-memory providers with compliant sample data for Swagger/CLI usage."""
    now = datetime.now(tz=timezone.utc)

    # 1. Seed Decisions
    dec = Decision(
        decision_id="dec-sample-1",
        ts=now,
        run_id="run-sample-1",
        cycle_id="cycle-sample-1",
        instrument_id="SBIN",
        direction=Direction.LONG,
        decision_type=DecisionType.WATCH,
        explanation="Bullish crossover with strong score support",
        score_ref="score-sample-1",
        confidence_ref="conf-sample-1",
        risk_ref="risk-sample-1",
        gate_results=(
            GateResult(gate=QualityGate.DATA, passed=True, detail="Daily volume ok"),
        ),
        trade_plan=None,
    )
    decision_prov.decisions.append(dec)

    # 2. Seed Portfolio
    pos = Position(
        position_id="pos-sample-1",
        instrument_id="SBIN",
        opened_ts=now,
        quantity=100,
        avg_price=Decimal("750.50"),
    )
    port = Portfolio(
        ts=now,
        positions=(pos,),
        cash=Decimal("50000.00"),
        exposure_by_sector={"Financials": Decimal("75050.00")},
    )
    portfolio_prov.portfolio = port

    # 3. Seed Workspace Snapshot
    summary = WorkspaceSummary(
        total_entries=1,
        artifact_counts={"report": 1},
        overall_health="HEALTHY",
    )
    ws_snap = WorkspaceSnapshot(
        snapshot_id="ws-sample-1",
        as_of=now,
        summary=summary,
        entries=(),
        references=None,
    )
    workspace_prov.snapshots.append(ws_snap)
