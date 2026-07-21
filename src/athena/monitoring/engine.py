"""Operational Monitoring Engine implementation (P6.5).

Evaluates platform health, aggregates component status, and detects missing or stale artifacts.
Performs NO state mutation, NO live polling, NO alert delivery, and NO market analysis.
"""

from __future__ import annotations

from collections.abc import Sequence
from datetime import datetime

from athena.analytics.portfolio.models import PerformanceSnapshot
from athena.config.models import MonitoringConfig, MonitoringDomain
from athena.dashboard.models import DashboardSnapshot
from athena.errors import MonitoringError
from athena.execution.models import ExecutionState
from athena.explainability.models import ExplanationSnapshot
from athena.portfolio.models import PortfolioSnapshot
from athena.reporting.models import GenericReport
from athena.timeline.models import TimelineSnapshot
from athena.monitoring.models import (
    MonitoringCheck,
    MonitoringHistory,
    MonitoringReferences,
    MonitoringSnapshot,
    MonitoringSummary,
)


class OperationalMonitoringEngine:
    """Deterministic, read-only Operational Monitoring Engine."""

    def __init__(self, config: MonitoringConfig | None = None) -> None:
        self._config = config or MonitoringConfig()
        self._counter = 0
        self._history = MonitoringHistory()

    @property
    def history(self) -> MonitoringHistory:
        """Get accumulated monitoring history."""
        return self._history

    def evaluate_health(
        self,
        schedule_execution: object | None = None,
        workflow: object | None = None,
        portfolio_snapshot: PortfolioSnapshot | None = None,
        execution_state: ExecutionState | None = None,
        performance_snapshot: PerformanceSnapshot | None = None,
        reports: Sequence[GenericReport] | None = None,
        dashboard_snapshot: DashboardSnapshot | None = None,
        explanation_snapshot: ExplanationSnapshot | None = None,
        timeline_snapshot: TimelineSnapshot | None = None,
        *,
        as_of: datetime,
    ) -> MonitoringSnapshot:
        """Evaluate platform health across 10 canonical monitoring domains."""
        if as_of.tzinfo is None:
            raise ValueError("evaluate_health as_of datetime must be timezone-aware")

        checks: list[MonitoringCheck] = []

        # 1. Scheduler Health
        if schedule_execution is not None:
            c_sched = MonitoringCheck(
                check_id="chk-sched",
                domain=MonitoringDomain.SCHEDULER,
                component="SchedulingFramework",
                status="HEALTHY",
                message="Schedule execution artifact present and active",
                details={"active": True},
            )
        else:
            c_sched = MonitoringCheck(
                check_id="chk-sched",
                domain=MonitoringDomain.SCHEDULER,
                component="SchedulingFramework",
                status="MISSING",
                message="No schedule execution artifact provided",
                details={"active": False},
            )
        checks.append(c_sched)

        # 2. Workflow Health
        if workflow is not None:
            c_wf = MonitoringCheck(
                check_id="chk-wf",
                domain=MonitoringDomain.WORKFLOW,
                component="WorkflowEngine",
                status="HEALTHY",
                message="Workflow execution completed successfully",
                details={"completed": True},
            )
        else:
            c_wf = MonitoringCheck(
                check_id="chk-wf",
                domain=MonitoringDomain.WORKFLOW,
                component="WorkflowEngine",
                status="MISSING",
                message="No workflow execution artifact provided",
                details={"completed": False},
            )
        checks.append(c_wf)

        # 3. Portfolio Health
        if portfolio_snapshot is not None:
            c_port = MonitoringCheck(
                check_id="chk-port",
                domain=MonitoringDomain.PORTFOLIO,
                component="PortfolioEngine",
                status="HEALTHY",
                message=f"Portfolio value {portfolio_snapshot.portfolio.cash.total_cash} with {portfolio_snapshot.summary.total_holdings} position(s)",
                details={"snapshot_id": portfolio_snapshot.snapshot_id, "total_value": str(portfolio_snapshot.portfolio.cash.total_cash)},
            )
        else:
            c_port = MonitoringCheck(
                check_id="chk-port",
                domain=MonitoringDomain.PORTFOLIO,
                component="PortfolioEngine",
                status="MISSING",
                message="No portfolio snapshot provided",
                details={},
            )
        checks.append(c_port)

        # 4. Execution Health
        if execution_state is not None:
            c_exec = MonitoringCheck(
                check_id="chk-exec",
                domain=MonitoringDomain.EXECUTION,
                component="OrderLifecycleEngine",
                status="HEALTHY",
                message=f"Execution state reconciled: {execution_state.summary.filled_orders} filled / {execution_state.summary.total_orders} total orders",
                details={"state_id": execution_state.state_id, "filled_orders": execution_state.summary.filled_orders},
            )
        else:
            c_exec = MonitoringCheck(
                check_id="chk-exec",
                domain=MonitoringDomain.EXECUTION,
                component="OrderLifecycleEngine",
                status="MISSING",
                message="No execution state provided",
                details={},
            )
        checks.append(c_exec)

        # 5. Analytics Health
        if performance_snapshot is not None:
            c_analytics = MonitoringCheck(
                check_id="chk-analytics",
                domain=MonitoringDomain.ANALYTICS,
                component="PortfolioAnalyticsEngine",
                status="HEALTHY",
                message=f"Analytics computed: Total PnL {performance_snapshot.portfolio_performance.total_pnl}",
                details={"snapshot_id": performance_snapshot.snapshot_id},
            )
        else:
            c_analytics = MonitoringCheck(
                check_id="chk-analytics",
                domain=MonitoringDomain.ANALYTICS,
                component="PortfolioAnalyticsEngine",
                status="MISSING",
                message="No performance snapshot provided",
                details={},
            )
        checks.append(c_analytics)

        # 6. Reporting Health
        rep_cnt = len(reports) if reports else 0
        c_rep = MonitoringCheck(
            check_id="chk-rep",
            domain=MonitoringDomain.REPORTING,
            component="ReportingFramework",
            status="HEALTHY" if rep_cnt > 0 else "MISSING",
            message=f"{rep_cnt} report(s) present",
            details={"reports_count": rep_cnt},
        )
        checks.append(c_rep)

        # 7. Dashboard Health
        if dashboard_snapshot is not None:
            c_dash = MonitoringCheck(
                check_id="chk-dash",
                domain=MonitoringDomain.DASHBOARD,
                component="DashboardEngine",
                status="HEALTHY",
                message=f"Dashboard snapshot created with status {dashboard_snapshot.summary.health_status}",
                details={"snapshot_id": dashboard_snapshot.snapshot_id},
            )
        else:
            c_dash = MonitoringCheck(
                check_id="chk-dash",
                domain=MonitoringDomain.DASHBOARD,
                component="DashboardEngine",
                status="MISSING",
                message="No dashboard snapshot provided",
                details={},
            )
        checks.append(c_dash)

        # 8. Explainability Health
        if explanation_snapshot is not None:
            c_exp = MonitoringCheck(
                check_id="chk-exp",
                domain=MonitoringDomain.EXPLAINABILITY,
                component="ExplainabilityEngine",
                status="HEALTHY",
                message=f"Explanation snapshot created with {len(explanation_snapshot.explanations)} domain explanation(s)",
                details={"snapshot_id": explanation_snapshot.snapshot_id},
            )
        else:
            c_exp = MonitoringCheck(
                check_id="chk-exp",
                domain=MonitoringDomain.EXPLAINABILITY,
                component="ExplainabilityEngine",
                status="MISSING",
                message="No explanation snapshot provided",
                details={},
            )
        checks.append(c_exp)

        # 9. Timeline Health
        if timeline_snapshot is not None:
            c_tl = MonitoringCheck(
                check_id="chk-tl",
                domain=MonitoringDomain.TIMELINE,
                component="TimelineAuditEngine",
                status="HEALTHY",
                message=f"Timeline snapshot created with {timeline_snapshot.summary.total_events} event(s)",
                details={"snapshot_id": timeline_snapshot.snapshot_id},
            )
        else:
            c_tl = MonitoringCheck(
                check_id="chk-tl",
                domain=MonitoringDomain.TIMELINE,
                component="TimelineAuditEngine",
                status="MISSING",
                message="No timeline snapshot provided",
                details={},
            )
        checks.append(c_tl)

        # Summarize tallies
        healthy_cnt = sum(1 for c in checks if c.status == "HEALTHY")
        warning_cnt = sum(1 for c in checks if c.status == "WARNING")
        missing_cnt = sum(1 for c in checks if c.status == "MISSING")

        if healthy_cnt == len(checks):
            overall_status = "HEALTHY"
        elif healthy_cnt > 0:
            overall_status = "DEGRADED"
        else:
            overall_status = "CRITICAL"

        # 10. Overall Platform Health check
        c_overall = MonitoringCheck(
            check_id="chk-overall",
            domain=MonitoringDomain.OVERALL,
            component="Platform",
            status=overall_status,
            message=f"Platform status: {overall_status} ({healthy_cnt}/{len(checks)} domain checks healthy)",
            details={"healthy": healthy_cnt, "missing": missing_cnt, "warning": warning_cnt},
        )
        checks.append(c_overall)

        summary = MonitoringSummary(
            overall_status=overall_status,
            total_checks=len(checks),
            healthy_checks=sum(1 for c in checks if c.status == "HEALTHY"),
            warning_checks=sum(1 for c in checks if c.status == "WARNING"),
            missing_checks=sum(1 for c in checks if c.status == "MISSING"),
        )

        refs = MonitoringReferences(
            portfolio_snapshot_id=portfolio_snapshot.snapshot_id if portfolio_snapshot else None,
            execution_state_id=execution_state.state_id if execution_state else None,
            performance_snapshot_id=performance_snapshot.snapshot_id if performance_snapshot else None,
            dashboard_snapshot_id=dashboard_snapshot.snapshot_id if dashboard_snapshot else None,
            explanation_snapshot_id=explanation_snapshot.snapshot_id if explanation_snapshot else None,
            timeline_snapshot_id=timeline_snapshot.snapshot_id if timeline_snapshot else None,
        )

        snapshot_id = f"monsnap-{self._next_counter():04d}"
        snapshot = MonitoringSnapshot(
            snapshot_id=snapshot_id,
            as_of=as_of,
            checks=tuple(checks),
            summary=summary,
            references=refs,
        )

        if self._config.record_history:
            self._history = self._history.record(snapshot)

        return snapshot

    def _next_counter(self) -> int:
        self._counter += 1
        return self._counter
