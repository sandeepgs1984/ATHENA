"""Decision Reporting Engine (M3.7).

Answers one question: "How can ATHENA explain its decision completely and
faithfully?" It transforms immutable decision artifacts into deterministic
human- and machine-readable reports. Presentation only — it never modifies,
reinterprets, or recalculates any artifact, and never adds new conclusions.

Pure and replayable: no I/O, no clock reads, no randomness; both views derive
from the same immutable source. UNKNOWN values are displayed explicitly.
"""

from __future__ import annotations

from collections.abc import Mapping
from decimal import Decimal

from athena.confidence.models import ConfidenceAssessment
from athena.decision.models import DecisionOutcome
from athena.evidence.models import EvidenceBundle
from athena.indicators.models import IndicatorName, IndicatorResult
from athena.reporting.models import DecisionReport
from athena.risk.models import RiskAssessment
from athena.scoring.models import ScoringResult

_UNKNOWN = "UNKNOWN"


def _num(value: Decimal | None) -> str | None:
    return str(value) if value is not None else None


def _disp(value: Decimal | None) -> str:
    return str(value) if value is not None else _UNKNOWN


class DecisionReportingEngine:
    """Deterministic, presentation-only rendering of decision artifacts."""

    def report(
        self,
        outcome: DecisionOutcome,
        *,
        scoring: ScoringResult | None = None,
        confidence: ConfidenceAssessment | None = None,
        risk: RiskAssessment | None = None,
        evidence_bundle: EvidenceBundle | None = None,
        indicators: Mapping[IndicatorName, IndicatorResult] | None = None,
    ) -> DecisionReport:
        decision = outcome.decision
        machine: dict[str, object] = {
            "decision": {
                "id": decision.decision_id,
                "ts": decision.ts.isoformat(),
                "instrument_id": decision.instrument_id,
                "type": decision.decision_type.value,
                "direction": decision.direction.value,
                "explanation": decision.explanation,
            },
            "trade_plan": self._plan(decision),
            "gates": [
                {"gate": g.gate.value, "passed": g.passed, "detail": g.detail}
                for g in decision.gate_results
            ],
            "score": self._score(scoring),
            "confidence": self._confidence(confidence),
            "risk": self._risk(risk),
            "evidence": self._evidence(evidence_bundle),
            "indicators": self._indicators(indicators),
            "reasoning": {
                "stages": [
                    {"stage": s.stage, "refs": list(s.ref_ids), "summary": s.summary}
                    for s in outcome.trace.stages
                ]
            },
            "references": {
                "score_ref": decision.score_ref,
                "confidence_ref": decision.confidence_ref,
                "risk_ref": decision.risk_ref,
            },
        }
        text = self._render_text(outcome, machine)
        return DecisionReport(decision_id=decision.decision_id,
                              decision_type=decision.decision_type.value,
                              ts=decision.ts, machine=machine, text=text)

    # ------------------------------------------------------------- sections

    @staticmethod
    def _plan(decision) -> dict | None:
        p = decision.trade_plan
        if p is None:
            return None
        return {
            "entry_low": str(p.entry_low), "entry_high": str(p.entry_high),
            "stop_loss": str(p.stop_loss), "targets": [str(t) for t in p.targets],
            "position_size": p.position_size, "risk_amount": str(p.risk_amount),
            "risk_reward": str(p.risk_reward),
            "valid_from": p.valid_from.isoformat(), "valid_until": p.valid_until.isoformat(),
        }

    @staticmethod
    def _score(scoring) -> dict:
        if scoring is None:
            return {"status": _UNKNOWN}
        comp = scoring.composite
        return {
            "status": comp.status.value,
            "composite": _num(comp.value),
            "completeness": str(comp.completeness),
            "components": [
                {"dimension": item.dimension, "status": item.status.value,
                 "value": _num(item.value), "weight": item.weight,
                 "weighted": _num(item.weighted)}
                for item in comp.breakdown
            ],
        }

    @staticmethod
    def _confidence(confidence) -> dict:
        if confidence is None:
            return {"status": _UNKNOWN}
        return {
            "status": confidence.overall_status.value,
            "overall": _num(confidence.overall_value),
            "level": confidence.overall_level.value if confidence.overall_level else _UNKNOWN,
            "completeness": str(confidence.completeness),
            "dimensions": [
                {"name": name, "status": d.status.value, "value": _num(d.value),
                 "level": d.level.value if d.level else _UNKNOWN}
                for name, d in confidence.dimensions.items()
            ],
        }

    @staticmethod
    def _risk(risk) -> dict:
        if risk is None:
            return {"status": _UNKNOWN}
        return {
            "status": risk.overall_status.value,
            "overall": _num(risk.overall_value),
            "level": risk.overall_level.value if risk.overall_level else _UNKNOWN,
            "completeness": str(risk.completeness),
            "dimensions": [
                {"name": name, "status": d.status.value, "value": _num(d.value),
                 "level": d.level.value if d.level else _UNKNOWN}
                for name, d in risk.dimensions.items()
            ],
        }

    @staticmethod
    def _evidence(bundle) -> dict:
        if bundle is None:
            return {"status": _UNKNOWN}
        return {
            "bundle_id": bundle.bundle_id,
            "complete": bundle.is_complete,
            "present_sources": list(bundle.present_sources),
            "missing_sources": list(bundle.missing_sources),
            "provenance": dict(bundle.provenance),
            "item_count": len(bundle.items),
        }

    @staticmethod
    def _indicators(indicators) -> list[dict]:
        if not indicators:
            return []
        rows = []
        for name in sorted(indicators, key=lambda n: n.value):
            result = indicators[name]
            rows.append({
                "name": name.value, "status": result.status.value,
                "values": {k: str(v) for k, v in result.values.items()},
            })
        return rows

    # ------------------------------------------------------------- text render

    def _render_text(self, outcome, machine: dict) -> str:
        d = machine["decision"]
        lines = [
            "ATHENA DECISION REPORT",
            "=" * 60,
            f"Decision   : {d['type']}  ({d['direction']})",
            f"Instrument : {d['instrument_id']}",
            f"Timestamp  : {d['ts']}",
            f"Decision ID: {d['id']}",
            f"Reasoning  : {d['explanation']}",
            "",
            "GATES",
            "-" * 60,
        ]
        for g in machine["gates"]:
            mark = "PASS" if g["passed"] else "FAIL"
            lines.append(f"  [{mark}] {g['gate']}: {g['detail']}")

        plan = machine["trade_plan"]
        if plan is not None:
            lines += [
                "", "TRADE PLAN (analytical setup — not a capital allocation)", "-" * 60,
                f"  entry {plan['entry_low']}..{plan['entry_high']}  stop {plan['stop_loss']}  "
                f"target {', '.join(plan['targets'])}",
                f"  risk/reward {plan['risk_reward']}  units {plan['position_size']}  "
                f"valid {plan['valid_from']} → {plan['valid_until']}",
            ]

        score = machine["score"]
        lines += ["", "SCORE", "-" * 60,
                  f"  composite: {_disp_from(score.get('composite'))} "
                  f"(status {score['status']}, completeness {score.get('completeness', _UNKNOWN)})"]
        for c in score.get("components", []):
            lines.append(f"    {c['dimension']}: {_disp_from(c['value'])} "
                         f"[{c['status']}, weight {c['weight']}]")

        conf = machine["confidence"]
        lines += ["", "CONFIDENCE", "-" * 60,
                  f"  overall: {_disp_from(conf.get('overall'))} "
                  f"({conf.get('level', _UNKNOWN)}, status {conf['status']})"]
        for dim in conf.get("dimensions", []):
            lines.append(f"    {dim['name']}: {_disp_from(dim['value'])} [{dim['status']}]")

        rk = machine["risk"]
        lines += ["", "RISK", "-" * 60,
                  f"  overall: {_disp_from(rk.get('overall'))} "
                  f"({rk.get('level', _UNKNOWN)}, status {rk['status']})"]
        for dim in rk.get("dimensions", []):
            lines.append(f"    {dim['name']}: {_disp_from(dim['value'])} [{dim['status']}]")

        ev = machine["evidence"]
        lines += ["", "EVIDENCE", "-" * 60]
        if ev.get("status") == _UNKNOWN:
            lines.append("  UNKNOWN (no evidence bundle)")
        else:
            lines.append(f"  bundle {ev['bundle_id']}: {ev['item_count']} item(s), "
                         f"complete={ev['complete']}, missing={ev['missing_sources']}")

        lines += ["", "INDICATORS", "-" * 60]
        if not machine["indicators"]:
            lines.append("  (none provided)")
        for ind in machine["indicators"]:
            lines.append(f"  {ind['name']}: {ind['status']} {ind['values']}")

        lines += ["", "REASONING TRACE", "-" * 60]
        for i, s in enumerate(machine["reasoning"]["stages"], start=1):
            lines.append(f"  {i}. [{s['stage']}] {s['summary']}")

        return "\n".join(lines)


def _disp_from(value) -> str:
    return _UNKNOWN if value is None else str(value)


from collections.abc import Sequence
from datetime import datetime
from athena.allocation.models import AllocationPlan
from athena.analytics.portfolio.models import PerformanceSnapshot
from athena.config.models import ReportType, ReportingFrameworkConfig
from athena.errors import ReportingError
from athena.execution.models import ExecutionState
from athena.portfolio.models import PortfolioSnapshot
from athena.reporting.models import GenericReport, ReportingHistory, ReportingReferences


class ReportingEngine:
    """Generic, read-only Reporting Framework engine (P6.1)."""

    def __init__(self, config: ReportingFrameworkConfig | None = None) -> None:
        self._config = config or ReportingFrameworkConfig()
        self._counter = 0
        self._history = ReportingHistory()

    @property
    def history(self) -> ReportingHistory:
        """Get accumulated reporting history."""
        return self._history

    def generate_portfolio_report(
        self, portfolio_snapshot: PortfolioSnapshot, *, as_of: datetime
    ) -> GenericReport:
        """Generate read-only portfolio status report."""
        if as_of.tzinfo is None:
            raise ValueError("generate_portfolio_report as_of datetime must be timezone-aware")

        content = {
            "snapshot_id": portfolio_snapshot.snapshot_id,
            "total_value": str(portfolio_snapshot.total_value),
            "cash_balance": str(portfolio_snapshot.cash_balance),
            "reserved_capital": str(portfolio_snapshot.reserved_capital),
            "available_cash": str(portfolio_snapshot.available_cash),
            "realized_pnl": str(portfolio_snapshot.realized_pnl),
            "positions_count": len(portfolio_snapshot.positions),
            "closed_positions_count": len(portfolio_snapshot.closed_positions),
        }

        text = (
            f"PORTFOLIO REPORT [{portfolio_snapshot.snapshot_id}]\n"
            f"As Of          : {as_of.isoformat()}\n"
            f"Total Value    : {portfolio_snapshot.total_value}\n"
            f"Cash Balance   : {portfolio_snapshot.cash_balance}\n"
            f"Available Cash : {portfolio_snapshot.available_cash}\n"
            f"Positions      : {len(portfolio_snapshot.positions)}"
        )

        refs = ReportingReferences(portfolio_snapshot_id=portfolio_snapshot.snapshot_id)
        report = GenericReport(
            report_id=f"rep-{self._next_counter():04d}",
            report_type=ReportType.PORTFOLIO,
            title=f"Portfolio Status Report ({portfolio_snapshot.snapshot_id})",
            as_of=as_of,
            content=content,
            text_summary=text,
            references=refs,
        )

        if self._config.record_history:
            self._history = self._history.record(report)
        return report

    def generate_execution_report(
        self, execution_state: ExecutionState, *, as_of: datetime
    ) -> GenericReport:
        """Generate read-only execution state report."""
        if as_of.tzinfo is None:
            raise ValueError("generate_execution_report as_of datetime must be timezone-aware")

        summary = execution_state.summary
        content = {
            "state_id": execution_state.state_id,
            "broker_execution_plan_id": execution_state.broker_execution_plan_id,
            "total_orders": summary.total_orders,
            "active_orders": summary.active_orders,
            "filled_orders": summary.filled_orders,
            "partially_filled_orders": summary.partially_filled_orders,
            "cancelled_orders": summary.cancelled_orders,
            "rejected_orders": summary.rejected_orders,
            "expired_orders": summary.expired_orders,
            "total_filled_quantity": str(summary.total_filled_quantity),
            "total_filled_value": str(summary.total_filled_value),
        }

        text = (
            f"EXECUTION REPORT [{execution_state.state_id}]\n"
            f"As Of         : {as_of.isoformat()}\n"
            f"Broker Plan   : {execution_state.broker_execution_plan_id}\n"
            f"Total Orders  : {summary.total_orders}\n"
            f"Filled Orders : {summary.filled_orders}\n"
            f"Filled Value  : {summary.total_filled_value}"
        )

        refs = ReportingReferences(
            execution_state_id=execution_state.state_id,
            broker_execution_plan_id=execution_state.broker_execution_plan_id,
        )
        report = GenericReport(
            report_id=f"rep-{self._next_counter():04d}",
            report_type=ReportType.EXECUTION,
            title=f"Execution Report ({execution_state.state_id})",
            as_of=as_of,
            content=content,
            text_summary=text,
            references=refs,
        )

        if self._config.record_history:
            self._history = self._history.record(report)
        return report

    def generate_allocation_report(
        self, allocation_plan: AllocationPlan, *, as_of: datetime
    ) -> GenericReport:
        """Generate read-only capital allocation report."""
        if as_of.tzinfo is None:
            raise ValueError("generate_allocation_report as_of datetime must be timezone-aware")

        summary = allocation_plan.summary
        content = {
            "plan_id": allocation_plan.plan_id,
            "model": summary.model_name,
            "total_allocations": summary.total_allocations,
            "allocated_capital": str(summary.allocated_capital),
            "remaining_unallocated": str(summary.remaining_unallocated),
            "reserve_capital": str(summary.reserve_capital),
        }

        text = (
            f"CAPITAL ALLOCATION REPORT [{allocation_plan.plan_id}]\n"
            f"As Of             : {as_of.isoformat()}\n"
            f"Model             : {summary.model_name}\n"
            f"Allocated Capital : {summary.allocated_capital}\n"
            f"Reserve Capital   : {summary.reserve_capital}"
        )

        refs = ReportingReferences(allocation_plan_id=allocation_plan.plan_id)
        report = GenericReport(
            report_id=f"rep-{self._next_counter():04d}",
            report_type=ReportType.ALLOCATION,
            title=f"Capital Allocation Report ({allocation_plan.plan_id})",
            as_of=as_of,
            content=content,
            text_summary=text,
            references=refs,
        )

        if self._config.record_history:
            self._history = self._history.record(report)
        return report

    def generate_analytics_report(
        self, performance_snapshot: PerformanceSnapshot, *, as_of: datetime
    ) -> GenericReport:
        """Generate read-only portfolio analytics report."""
        if as_of.tzinfo is None:
            raise ValueError("generate_analytics_report as_of datetime must be timezone-aware")

        perf = performance_snapshot.portfolio_performance
        sum_obj = performance_snapshot.summary

        content = {
            "snapshot_id": performance_snapshot.snapshot_id,
            "total_pnl": str(perf.total_pnl),
            "realized_pnl": str(perf.realized_pnl),
            "unrealized_pnl": str(perf.unrealized_pnl),
            "total_return_pct": str(perf.total_return_pct),
            "portfolio_value": str(perf.portfolio_value),
            "drawdown_pct": str(perf.drawdown_pct),
            "win_rate_pct": str(sum_obj.win_rate_pct),
            "total_trades": sum_obj.total_trades,
        }

        text = (
            f"PORTFOLIO ANALYTICS REPORT [{performance_snapshot.snapshot_id}]\n"
            f"As Of         : {as_of.isoformat()}\n"
            f"Total PnL     : {perf.total_pnl}\n"
            f"Total Return  : {perf.total_return_pct}%\n"
            f"Win Rate      : {sum_obj.win_rate_pct}%\n"
            f"Drawdown      : {perf.drawdown_pct}%"
        )

        refs = ReportingReferences(performance_snapshot_id=performance_snapshot.snapshot_id)
        report = GenericReport(
            report_id=f"rep-{self._next_counter():04d}",
            report_type=ReportType.ANALYTICS,
            title=f"Portfolio Analytics Report ({performance_snapshot.snapshot_id})",
            as_of=as_of,
            content=content,
            text_summary=text,
            references=refs,
        )

        if self._config.record_history:
            self._history = self._history.record(report)
        return report

    def generate_audit_report(
        self, run_id: str, events: Sequence[dict[str, object]], *, as_of: datetime
    ) -> GenericReport:
        """Generate read-only audit log report."""
        if as_of.tzinfo is None:
            raise ValueError("generate_audit_report as_of datetime must be timezone-aware")

        content = {
            "run_id": run_id,
            "event_count": len(events),
            "events": list(events),
        }

        text = (
            f"AUDIT LOG REPORT [{run_id}]\n"
            f"As Of       : {as_of.isoformat()}\n"
            f"Event Count : {len(events)}"
        )

        refs = ReportingReferences(audit_id=run_id)
        report = GenericReport(
            report_id=f"rep-{self._next_counter():04d}",
            report_type=ReportType.AUDIT,
            title=f"Audit Log Report ({run_id})",
            as_of=as_of,
            content=content,
            text_summary=text,
            references=refs,
        )

        if self._config.record_history:
            self._history = self._history.record(report)
        return report

    def _next_counter(self) -> int:
        self._counter += 1
        return self._counter

