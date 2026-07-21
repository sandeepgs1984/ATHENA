"""Explainability Engine implementation (P6.3).

Generates deterministic, human-readable explanations describing why decisions, allocations, sizing,
execution plans, lifecycle outcomes, and analytics were produced.
Performs NO state mutation, NO decision altering, NO LLM generation, and NO market analysis.
"""

from __future__ import annotations

from collections.abc import Sequence
from datetime import datetime

from athena.allocation.models import AllocationPlan
from athena.analytics.portfolio.models import PerformanceSnapshot
from athena.brokers.models import BrokerExecutionPlan
from athena.config.models import ExplainabilityConfig, ExplanationDomain
from athena.decision.models import Decision
from athena.errors import ExplainabilityError
from athena.execution.models import ExecutionState
from athena.explainability.models import (
    Explanation,
    ExplanationHistory,
    ExplanationReferences,
    ExplanationSection,
    ExplanationSnapshot,
)
from athena.orders.models import ExecutionPlan
from athena.portfolio.models import PortfolioSnapshot
from athena.reporting.models import GenericReport
from athena.sizing.models import PositionSizingPlan


class ExplainabilityEngine:
    """Deterministic, read-only Explainability Engine."""

    def __init__(self, config: ExplainabilityConfig | None = None) -> None:
        self._config = config or ExplainabilityConfig()
        self._counter = 0
        self._history = ExplanationHistory()

    @property
    def history(self) -> ExplanationHistory:
        """Get accumulated explanation history."""
        return self._history

    def explain_decision(self, decision: Decision, *, as_of: datetime) -> Explanation:
        """Explain decision rationale."""
        if as_of.tzinfo is None:
            raise ValueError("explain_decision as_of datetime must be timezone-aware")

        sec = ExplanationSection(
            section_id="decision_rationale",
            title="Decision Rationale",
            domain=ExplanationDomain.DECISION,
            rationale=f"Decision {decision.decision_type.value} was produced for {decision.instrument_id} ({decision.direction.value}): {decision.explanation}",
            facts={
                "decision_id": decision.decision_id,
                "instrument_id": decision.instrument_id,
                "decision_type": decision.decision_type.value,
                "direction": decision.direction.value,
            },
        )
        refs = ExplanationReferences(decision_id=decision.decision_id)
        return Explanation(
            explanation_id=f"exp-{self._next_counter():04d}",
            domain=ExplanationDomain.DECISION,
            title=f"Decision Explanation ({decision.decision_id})",
            summary=f"{decision.instrument_id} evaluated to {decision.decision_type.value}",
            sections=(sec,),
            as_of=as_of,
            references=refs,
        )

    def explain_portfolio(self, portfolio_snapshot: PortfolioSnapshot, *, as_of: datetime) -> Explanation:
        """Explain portfolio state & ledger."""
        if as_of.tzinfo is None:
            raise ValueError("explain_portfolio as_of datetime must be timezone-aware")

        total_val = portfolio_snapshot.portfolio.cash.total_cash
        sec = ExplanationSection(
            section_id="portfolio_state",
            title="Portfolio Ledger State",
            domain=ExplanationDomain.PORTFOLIO,
            rationale=f"Portfolio value is {total_val} with {portfolio_snapshot.portfolio.cash.total_cash} cash, {portfolio_snapshot.summary.total_reserved_cash} reserved, and {portfolio_snapshot.summary.total_holdings} active position(s).",
            facts={
                "snapshot_id": portfolio_snapshot.snapshot_id,
                "total_value": str(total_val),
                "cash_balance": str(portfolio_snapshot.portfolio.cash.total_cash),
                "positions_count": portfolio_snapshot.summary.total_holdings,
            },
        )
        refs = ExplanationReferences(portfolio_snapshot_id=portfolio_snapshot.snapshot_id)
        return Explanation(
            explanation_id=f"exp-{self._next_counter():04d}",
            domain=ExplanationDomain.PORTFOLIO,
            title=f"Portfolio Explanation ({portfolio_snapshot.snapshot_id})",
            summary=f"Total Value: {total_val}, Cash: {portfolio_snapshot.portfolio.cash.total_cash}",
            sections=(sec,),
            as_of=as_of,
            references=refs,
        )

    def explain_allocation(self, allocation_plan: AllocationPlan, *, as_of: datetime) -> Explanation:
        """Explain capital allocation outcomes."""
        if as_of.tzinfo is None:
            raise ValueError("explain_allocation as_of datetime must be timezone-aware")

        sum_alloc = allocation_plan.summary
        model_name = (
            allocation_plan.allocations[0].model_used.value
            if allocation_plan.allocations
            else "EQUAL_WEIGHT"
        )
        sec = ExplanationSection(
            section_id="allocation_policy",
            title="Capital Allocation Rationale",
            domain=ExplanationDomain.ALLOCATION,
            rationale=f"Capital allocation model '{model_name}' allocated {sum_alloc.total_allocated_capital} across {sum_alloc.allocated_count} candidate(s) while maintaining a cash reserve floor of {sum_alloc.min_cash_reserve_floor}.",
            facts={
                "plan_id": allocation_plan.plan_id,
                "model": model_name,
                "allocated_capital": str(sum_alloc.total_allocated_capital),
                "reserve_capital": str(sum_alloc.min_cash_reserve_floor),
            },
        )
        refs = ExplanationReferences(allocation_plan_id=allocation_plan.plan_id)
        return Explanation(
            explanation_id=f"exp-{self._next_counter():04d}",
            domain=ExplanationDomain.ALLOCATION,
            title=f"Capital Allocation Explanation ({allocation_plan.plan_id})",
            summary=f"Allocated {sum_alloc.total_allocated_capital} using model {model_name}",
            sections=(sec,),
            as_of=as_of,
            references=refs,
        )

    def explain_sizing(self, sizing_plan: PositionSizingPlan, *, as_of: datetime) -> Explanation:
        """Explain position sizing unit calculations."""
        if as_of.tzinfo is None:
            raise ValueError("explain_sizing as_of datetime must be timezone-aware")

        sum_sz = sizing_plan.summary
        model_name = (
            sizing_plan.sizes[0].sizing_model.value
            if sizing_plan.sizes
            else "WHOLE_SHARE"
        )
        rounding_mode = (
            sizing_plan.sizes[0].rounding_mode.value
            if sizing_plan.sizes
            else "ROUND_DOWN"
        )
        sec = ExplanationSection(
            section_id="sizing_calculation",
            title="Position Sizing Calculation",
            domain=ExplanationDomain.SIZING,
            rationale=f"Position sizing converted allocated capital into executable quantities using model '{model_name}' and rounding policy '{rounding_mode}', sizing {len(sizing_plan.sizes)} position(s) with total planned cost {sum_sz.total_actual_cost}.",
            facts={
                "plan_id": sizing_plan.plan_id,
                "model": model_name,
                "rounding_mode": rounding_mode,
                "total_actual_cost": str(sum_sz.total_actual_cost),
            },
        )
        refs = ExplanationReferences(position_sizing_plan_id=sizing_plan.plan_id)
        return Explanation(
            explanation_id=f"exp-{self._next_counter():04d}",
            domain=ExplanationDomain.SIZING,
            title=f"Position Sizing Explanation ({sizing_plan.plan_id})",
            summary=f"Sized {len(sizing_plan.sizes)} item(s) using {model_name} / {rounding_mode}",
            sections=(sec,),
            as_of=as_of,
            references=refs,
        )

    def explain_order_planning(self, execution_plan: ExecutionPlan, *, as_of: datetime) -> Explanation:
        """Explain broker-neutral execution instruction planning."""
        if as_of.tzinfo is None:
            raise ValueError("explain_order_planning as_of datetime must be timezone-aware")

        sum_ord = execution_plan.summary
        sec = ExplanationSection(
            section_id="order_planning_instructions",
            title="Execution Plan Rationale",
            domain=ExplanationDomain.ORDER_PLANNING,
            rationale=f"Order Planning Engine prepared {sum_ord.total_candidates} planned order(s) ({sum_ord.buy_count} BUY, {sum_ord.sell_count} SELL, {sum_ord.hold_count} HOLD) grouped into {len(execution_plan.batches)} batch(es) with total planned value {sum_ord.total_planned_value}.",
            facts={
                "plan_id": execution_plan.plan_id,
                "buy_count": sum_ord.buy_count,
                "sell_count": sum_ord.sell_count,
                "hold_count": sum_ord.hold_count,
                "total_planned_value": str(sum_ord.total_planned_value),
            },
        )
        refs = ExplanationReferences(execution_plan_id=execution_plan.plan_id)
        return Explanation(
            explanation_id=f"exp-{self._next_counter():04d}",
            domain=ExplanationDomain.ORDER_PLANNING,
            title=f"Execution Plan Explanation ({execution_plan.plan_id})",
            summary=f"Planned {sum_ord.buy_count} BUY / {sum_ord.sell_count} SELL orders into {len(execution_plan.batches)} batch(es)",
            sections=(sec,),
            as_of=as_of,
            references=refs,
        )

    def explain_broker_translation(self, broker_plan: BrokerExecutionPlan, *, as_of: datetime) -> Explanation:
        """Explain broker translation & capability validation."""
        if as_of.tzinfo is None:
            raise ValueError("explain_broker_translation as_of datetime must be timezone-aware")

        sum_b = broker_plan.summary
        sec = ExplanationSection(
            section_id="broker_validation",
            title="Broker Capability Validation",
            domain=ExplanationDomain.BROKER_TRANSLATION,
            rationale=f"Broker contract '{broker_plan.broker_id}' validated {sum_b.total_requests} order request(s): {sum_b.accepted_count} ACCEPTED, {sum_b.rejected_count} REJECTED, {sum_b.skipped_count} SKIPPED_HOLD.",
            facts={
                "broker_plan_id": broker_plan.broker_plan_id,
                "broker_id": broker_plan.broker_id,
                "accepted_count": sum_b.accepted_count,
                "rejected_count": sum_b.rejected_count,
            },
        )
        refs = ExplanationReferences(broker_execution_plan_id=broker_plan.broker_plan_id)
        return Explanation(
            explanation_id=f"exp-{self._next_counter():04d}",
            domain=ExplanationDomain.BROKER_TRANSLATION,
            title=f"Broker Translation Explanation ({broker_plan.broker_plan_id})",
            summary=f"Translated for broker {broker_plan.broker_id}: {sum_b.accepted_count} ACCEPTED, {sum_b.rejected_count} REJECTED",
            sections=(sec,),
            as_of=as_of,
            references=refs,
        )

    def explain_lifecycle(self, execution_state: ExecutionState, *, as_of: datetime) -> Explanation:
        """Explain order lifecycle state transitions."""
        if as_of.tzinfo is None:
            raise ValueError("explain_lifecycle as_of datetime must be timezone-aware")

        sum_lc = execution_state.summary
        sec = ExplanationSection(
            section_id="lifecycle_state_transitions",
            title="Order Lifecycle Rationale",
            domain=ExplanationDomain.LIFECYCLE,
            rationale=f"Order Lifecycle Engine tracked {sum_lc.total_orders} order(s): {sum_lc.filled_orders} FILLED, {sum_lc.partially_filled_orders} PARTIALLY_FILLED, {sum_lc.cancelled_orders} CANCELLED, with total filled value {sum_lc.total_filled_value}.",
            facts={
                "state_id": execution_state.state_id,
                "total_orders": sum_lc.total_orders,
                "filled_orders": sum_lc.filled_orders,
                "total_filled_value": str(sum_lc.total_filled_value),
            },
        )
        refs = ExplanationReferences(execution_state_id=execution_state.state_id)
        return Explanation(
            explanation_id=f"exp-{self._next_counter():04d}",
            domain=ExplanationDomain.LIFECYCLE,
            title=f"Lifecycle Explanation ({execution_state.state_id})",
            summary=f"Tracked {sum_lc.total_orders} order(s): {sum_lc.filled_orders} FILLED, {sum_lc.cancelled_orders} CANCELLED",
            sections=(sec,),
            as_of=as_of,
            references=refs,
        )

    def explain_analytics(self, performance_snapshot: PerformanceSnapshot, *, as_of: datetime) -> Explanation:
        """Explain portfolio analytics & performance."""
        if as_of.tzinfo is None:
            raise ValueError("explain_analytics as_of datetime must be timezone-aware")

        perf = performance_snapshot.portfolio_performance
        sum_p = performance_snapshot.summary
        sec = ExplanationSection(
            section_id="performance_analytics_rationale",
            title="Portfolio Performance Rationale",
            domain=ExplanationDomain.ANALYTICS,
            rationale=f"Portfolio Analytics Engine computed total PnL {perf.total_pnl} ({perf.total_return_pct}% return) with win rate {sum_p.win_rate_pct}% across {sum_p.total_trades} trade(s) and max drawdown {perf.max_drawdown_pct}%.",
            facts={
                "snapshot_id": performance_snapshot.snapshot_id,
                "total_pnl": str(perf.total_pnl),
                "total_return_pct": str(perf.total_return_pct),
                "win_rate_pct": str(sum_p.win_rate_pct),
                "max_drawdown_pct": str(perf.max_drawdown_pct),
            },
        )
        refs = ExplanationReferences(performance_snapshot_id=performance_snapshot.snapshot_id)
        return Explanation(
            explanation_id=f"exp-{self._next_counter():04d}",
            domain=ExplanationDomain.ANALYTICS,
            title=f"Analytics Explanation ({performance_snapshot.snapshot_id})",
            summary=f"Total PnL {perf.total_pnl} ({perf.total_return_pct}% return), Win Rate {sum_p.win_rate_pct}%",
            sections=(sec,),
            as_of=as_of,
            references=refs,
        )

    def explain_reporting(self, report: GenericReport, *, as_of: datetime) -> Explanation:
        """Explain reporting outputs."""
        if as_of.tzinfo is None:
            raise ValueError("explain_reporting as_of datetime must be timezone-aware")

        sec = ExplanationSection(
            section_id="reporting_rationale",
            title="Reporting Rationale",
            domain=ExplanationDomain.REPORTING,
            rationale=f"Reporting Framework generated read-only report '{report.title}' of type {report.report_type.value}.",
            facts={
                "report_id": report.report_id,
                "report_type": report.report_type.value,
                "title": report.title,
            },
        )
        refs = ExplanationReferences(report_id=report.report_id)
        return Explanation(
            explanation_id=f"exp-{self._next_counter():04d}",
            domain=ExplanationDomain.REPORTING,
            title=f"Reporting Explanation ({report.report_id})",
            summary=f"Generated {report.report_type.value} report: {report.title}",
            sections=(sec,),
            as_of=as_of,
            references=refs,
        )

    def create_snapshot(
        self, explanations: Sequence[Explanation], *, as_of: datetime
    ) -> ExplanationSnapshot:
        """Aggregate multiple explanations into an ExplanationSnapshot."""
        if as_of.tzinfo is None:
            raise ValueError("create_snapshot as_of datetime must be timezone-aware")

        domains_present = [e.domain.value for e in explanations]
        summary_text = f"Aggregated {len(explanations)} explanation(s) across domains: {', '.join(domains_present)}"

        snapshot_id = f"expsnap-{self._next_counter():04d}"
        snapshot = ExplanationSnapshot(
            snapshot_id=snapshot_id,
            as_of=as_of,
            explanations=tuple(explanations),
            summary_text=summary_text,
        )

        if self._config.record_history:
            self._history = self._history.record(snapshot)

        return snapshot

    def _next_counter(self) -> int:
        self._counter += 1
        return self._counter
