"""Timeline & Audit Engine implementation (P6.4).

Reconstructs chronological timelines and audit entries from immutable platform artifacts.
Performs NO state mutation, NO live streaming, NO decision altering, and NO market analysis.
"""

from __future__ import annotations

from collections.abc import Sequence
from datetime import datetime

from athena.allocation.models import AllocationPlan
from athena.analytics.portfolio.models import PerformanceSnapshot
from athena.brokers.models import BrokerExecutionPlan
from athena.config.models import TimelineConfig, TimelineDomain
from athena.dashboard.models import DashboardSnapshot
from athena.decision.models import Decision
from athena.errors import TimelineAuditError
from athena.execution.models import ExecutionState
from athena.explainability.models import ExplanationSnapshot
from athena.orders.models import ExecutionPlan
from athena.portfolio.models import PortfolioSnapshot
from athena.reporting.models import GenericReport
from athena.sizing.models import PositionSizingPlan
from athena.timeline.models import (
    AuditEntry,
    TimelineEvent,
    TimelineHistory,
    TimelineReferences,
    TimelineSnapshot,
    TimelineSummary,
)


class TimelineAuditEngine:
    """Deterministic, read-only Timeline & Audit Engine."""

    def __init__(self, config: TimelineConfig | None = None) -> None:
        self._config = config or TimelineConfig()
        self._counter = 0
        self._history = TimelineHistory()

    @property
    def history(self) -> TimelineHistory:
        """Get accumulated timeline history."""
        return self._history

    def build_timeline(
        self,
        decisions: Sequence[Decision] | None = None,
        portfolio_snapshot: PortfolioSnapshot | None = None,
        allocation_plan: AllocationPlan | None = None,
        sizing_plan: PositionSizingPlan | None = None,
        execution_plan: ExecutionPlan | None = None,
        broker_plan: BrokerExecutionPlan | None = None,
        execution_state: ExecutionState | None = None,
        performance_snapshot: PerformanceSnapshot | None = None,
        reports: Sequence[GenericReport] | None = None,
        dashboard_snapshot: DashboardSnapshot | None = None,
        explanation_snapshot: ExplanationSnapshot | None = None,
        *,
        as_of: datetime,
    ) -> TimelineSnapshot:
        """Reconstruct chronological timeline and audit log from platform artifacts."""
        if as_of.tzinfo is None:
            raise ValueError("build_timeline as_of datetime must be timezone-aware")

        raw_events: list[TimelineEvent] = []

        # 1. Decisions
        if decisions:
            for d in decisions:
                raw_events.append(
                    TimelineEvent(
                        event_id=f"evt-dec-{d.decision_id}",
                        ts=d.ts,
                        domain=TimelineDomain.DECISION,
                        event_type="DECISION_PRODUCED",
                        summary=f"Decision {d.decision_type.value} produced for {d.instrument_id}",
                        details={"decision_id": d.decision_id, "type": d.decision_type.value, "direction": d.direction.value},
                    )
                )

        # 2. Portfolio Snapshot
        if portfolio_snapshot:
            raw_events.append(
                TimelineEvent(
                    event_id=f"evt-port-{portfolio_snapshot.snapshot_id}",
                    ts=portfolio_snapshot.as_of,
                    domain=TimelineDomain.PORTFOLIO,
                    event_type="PORTFOLIO_SNAPSHOT_CREATED",
                    summary=f"Portfolio snapshot created with value {portfolio_snapshot.total_value}",
                    details={"snapshot_id": portfolio_snapshot.snapshot_id, "total_value": str(portfolio_snapshot.total_value)},
                )
            )

        # 3. Capital Allocation Plan
        if allocation_plan:
            raw_events.append(
                TimelineEvent(
                    event_id=f"evt-alloc-{allocation_plan.plan_id}",
                    ts=allocation_plan.as_of,
                    domain=TimelineDomain.ALLOCATION,
                    event_type="ALLOCATION_PLAN_CREATED",
                    summary=f"Capital allocation plan created using model {allocation_plan.summary.model_name}",
                    details={"plan_id": allocation_plan.plan_id, "allocated_capital": str(allocation_plan.summary.allocated_capital)},
                )
            )

        # 4. Position Sizing Plan
        if sizing_plan:
            raw_events.append(
                TimelineEvent(
                    event_id=f"evt-sz-{sizing_plan.plan_id}",
                    ts=sizing_plan.as_of,
                    domain=TimelineDomain.SIZING,
                    event_type="POSITION_SIZING_COMPLETED",
                    summary=f"Position sizing completed for {len(sizing_plan.sizes)} position(s)",
                    details={"plan_id": sizing_plan.plan_id, "total_actual_cost": str(sizing_plan.summary.total_actual_cost)},
                )
            )

        # 5. Execution Plan
        if execution_plan:
            raw_events.append(
                TimelineEvent(
                    event_id=f"evt-ord-{execution_plan.plan_id}",
                    ts=execution_plan.as_of,
                    domain=TimelineDomain.ORDER_PLANNING,
                    event_type="EXECUTION_PLAN_GENERATED",
                    summary=f"Execution plan generated with {execution_plan.summary.total_candidates} order candidate(s)",
                    details={"plan_id": execution_plan.plan_id, "total_planned_value": str(execution_plan.summary.total_planned_value)},
                )
            )

        # 6. Broker Plan
        if broker_plan:
            raw_events.append(
                TimelineEvent(
                    event_id=f"evt-b-{broker_plan.broker_plan_id}",
                    ts=broker_plan.as_of,
                    domain=TimelineDomain.BROKER_TRANSLATION,
                    event_type="BROKER_PLAN_TRANSLATED",
                    summary=f"Broker plan translated for broker {broker_plan.broker_id}",
                    details={"broker_plan_id": broker_plan.broker_plan_id, "accepted_count": broker_plan.summary.accepted_count},
                )
            )

        # 7. Order Lifecycle State
        if execution_state:
            raw_events.append(
                TimelineEvent(
                    event_id=f"evt-lc-{execution_state.state_id}",
                    ts=execution_state.as_of,
                    domain=TimelineDomain.LIFECYCLE,
                    event_type="EXECUTION_STATE_INITIALIZED",
                    summary=f"Execution state initialized with {execution_state.summary.total_orders} order(s)",
                    details={"state_id": execution_state.state_id, "filled_orders": execution_state.summary.filled_orders},
                )
            )

        # 8. Portfolio Performance Snapshot
        if performance_snapshot:
            raw_events.append(
                TimelineEvent(
                    event_id=f"evt-perf-{performance_snapshot.snapshot_id}",
                    ts=performance_snapshot.as_of,
                    domain=TimelineDomain.ANALYTICS,
                    event_type="PERFORMANCE_ANALYZED",
                    summary=f"Portfolio performance analyzed with total PnL {performance_snapshot.portfolio_performance.total_pnl}",
                    details={"snapshot_id": performance_snapshot.snapshot_id, "total_pnl": str(performance_snapshot.portfolio_performance.total_pnl)},
                )
            )

        # 9. Reports
        if reports:
            for r in reports:
                raw_events.append(
                    TimelineEvent(
                        event_id=f"evt-rep-{r.report_id}",
                        ts=r.as_of,
                        domain=TimelineDomain.REPORTING,
                        event_type="REPORT_GENERATED",
                        summary=f"Operational report {r.report_type.value} generated: {r.title}",
                        details={"report_id": r.report_id, "report_type": r.report_type.value},
                    )
                )

        # 10. Dashboard Snapshot
        if dashboard_snapshot:
            raw_events.append(
                TimelineEvent(
                    event_id=f"evt-dash-{dashboard_snapshot.snapshot_id}",
                    ts=dashboard_snapshot.as_of,
                    domain=TimelineDomain.DASHBOARD,
                    event_type="DASHBOARD_SNAPSHOT_CREATED",
                    summary=f"Dashboard snapshot created with {len(dashboard_snapshot.sections)} section(s)",
                    details={"snapshot_id": dashboard_snapshot.snapshot_id, "health_status": dashboard_snapshot.summary.health_status},
                )
            )

        # 11. Explanation Snapshot
        if explanation_snapshot:
            raw_events.append(
                TimelineEvent(
                    event_id=f"evt-exp-{explanation_snapshot.snapshot_id}",
                    ts=explanation_snapshot.as_of,
                    domain=TimelineDomain.EXPLAINABILITY,
                    event_type="EXPLANATION_SNAPSHOT_CREATED",
                    summary=f"Explanation snapshot created covering {len(explanation_snapshot.explanations)} explanation(s)",
                    details={"snapshot_id": explanation_snapshot.snapshot_id},
                )
            )

        # Causal & chronological sort: (ts, domain, event_type, event_id)
        sorted_events = sorted(raw_events, key=lambda e: (e.ts, e.domain.value, e.event_type, e.event_id))

        audit_entries: list[AuditEntry] = []
        for seq, evt in enumerate(sorted_events, start=1):
            audit_entries.append(
                AuditEntry(
                    audit_id=f"aud-{seq:04d}",
                    sequence_number=seq,
                    event=evt,
                )
            )

        domains_covered = tuple(sorted(list({evt.domain for evt in sorted_events}), key=lambda d: d.value))
        start_time = sorted_events[0].ts if sorted_events else None
        end_time = sorted_events[-1].ts if sorted_events else None

        summary = TimelineSummary(
            total_events=len(sorted_events),
            domains_covered=domains_covered,
            start_time=start_time,
            end_time=end_time,
        )

        refs = TimelineReferences(
            portfolio_snapshot_id=portfolio_snapshot.snapshot_id if portfolio_snapshot else None,
            allocation_plan_id=allocation_plan.plan_id if allocation_plan else None,
            position_sizing_plan_id=sizing_plan.plan_id if sizing_plan else None,
            execution_plan_id=execution_plan.plan_id if execution_plan else None,
            broker_execution_plan_id=broker_plan.broker_plan_id if broker_plan else None,
            execution_state_id=execution_state.state_id if execution_state else None,
            performance_snapshot_id=performance_snapshot.snapshot_id if performance_snapshot else None,
            dashboard_snapshot_id=dashboard_snapshot.snapshot_id if dashboard_snapshot else None,
            explanation_snapshot_id=explanation_snapshot.snapshot_id if explanation_snapshot else None,
        )

        snapshot_id = f"tlsnap-{self._next_counter():04d}"
        snapshot = TimelineSnapshot(
            snapshot_id=snapshot_id,
            as_of=as_of,
            entries=tuple(audit_entries),
            summary=summary,
            references=refs,
        )

        if self._config.record_history:
            self._history = self._history.record(snapshot)

        return snapshot

    def _next_counter(self) -> int:
        self._counter += 1
        return self._counter
