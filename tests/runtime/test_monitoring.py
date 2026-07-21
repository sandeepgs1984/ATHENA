"""Operational Monitoring Engine tests (P6.5).

Covers component health aggregation across 10 domains, overall health calculation,
missing artifact detection, deterministic replay, immutable outputs, monitoring history,
configuration validation, and an end-to-end integration test.
"""

from __future__ import annotations

import dataclasses
import json
from datetime import datetime, timedelta
from decimal import Decimal
from zoneinfo import ZoneInfo

import pytest

from athena.allocation import CapitalAllocationEngine
from athena.analytics.portfolio import PortfolioAnalyticsEngine
from athena.brokers import BrokerManager
from athena.config.loader import (
    load_allocation_config,
    load_broker_config,
    load_dashboard_config,
    load_execution_config,
    load_explainability_config,
    load_monitoring_config,
    load_order_planning_config,
    load_portfolio_analytics_config,
    load_sizing_config,
    load_timeline_config,
)
from athena.config.models import MonitoringConfig, MonitoringDomain
from athena.dashboard import DashboardEngine
from athena.domain.decision import Decision, TradePlan
from athena.domain.enums import DecisionType, Direction
from athena.errors import ConfigError, MonitoringError
from athena.execution import OrderLifecycleEngine
from athena.explainability import ExplainabilityEngine
from athena.monitoring import OperationalMonitoringEngine
from athena.orders import OrderPlanningEngine
from athena.config import PortfolioConfig
from athena.portfolio import PortfolioEngine
from athena.reporting import ReportingEngine
from athena.sizing import PositionSizingEngine
from athena.timeline import TimelineAuditEngine

IST = ZoneInfo("Asia/Kolkata")
AS_OF = datetime(2026, 3, 2, 8, 30, tzinfo=IST)
T1 = AS_OF + timedelta(days=1)
DAY2 = AS_OF + timedelta(days=1)


def _decision(inst: str) -> Decision:
    plan = TradePlan(
        entry_low=Decimal("1490.00"),
        entry_high=Decimal("1510.00"),
        stop_loss=Decimal("1450.00"),
        targets=(Decimal("1600.00"),),
        position_size=100,
        risk_amount=Decimal("5000.00"),
        risk_reward=Decimal("2.0"),
        valid_from=AS_OF,
        valid_until=DAY2,
    )
    return Decision(
        decision_id=f"dec-{inst}",
        ts=AS_OF,
        run_id="r1",
        cycle_id="c1",
        decision_type=DecisionType.TRADE,
        explanation=f"{inst} TRADE",
        instrument_id=inst,
        direction=Direction.LONG,
        trade_plan=plan,
    )


@pytest.fixture()
def full_platform_artifacts(config_dir):
    dec = _decision("INFY")

    # 1. Portfolio Engine
    p_cfg = PortfolioConfig(initial_cash=Decimal("1000000.00"))
    p_eng = PortfolioEngine(p_cfg, initial_as_of=AS_OF)
    p_eng.open_position("INFY", quantity=100, price=Decimal("1500.00"), as_of=AS_OF)
    p_snap = p_eng.current_snapshot

    # 2. Allocation Engine
    alloc_cfg = load_allocation_config(config_dir)
    alloc_eng = CapitalAllocationEngine(alloc_cfg)
    alloc_plan = alloc_eng.allocate(p_snap, [dec], as_of=AS_OF)

    # 3. Position Sizing
    sz_cfg = load_sizing_config(config_dir)
    sz_eng = PositionSizingEngine(sz_cfg)
    sz_plan = sz_eng.size_plan(alloc_plan, {"INFY": Decimal("1500.00")}, as_of=AS_OF)

    # 4. Order Planning
    ord_cfg = load_order_planning_config(config_dir)
    ord_eng = OrderPlanningEngine(ord_cfg)
    exec_plan = ord_eng.plan_execution(sz_plan, as_of=AS_OF)

    # 5. Broker Abstraction
    b_cfg = load_broker_config(config_dir)
    b_mgr = BrokerManager(b_cfg)
    b_plan = b_mgr.translate_plan(exec_plan, as_of=AS_OF)

    # 6. Order Lifecycle Engine
    lc_cfg = load_execution_config(config_dir)
    lc_eng = OrderLifecycleEngine(lc_cfg)
    exec_state = lc_eng.initialize_from_plan(b_plan, as_of=AS_OF)

    # 7. Portfolio Analytics Engine
    analytics_cfg = load_portfolio_analytics_config(config_dir)
    analytics_eng = PortfolioAnalyticsEngine(analytics_cfg)
    perf_snap = analytics_eng.analyze(p_snap, exec_state, current_prices={"INFY": Decimal("1600.00")}, as_of=T1)

    # 8. Reporting Framework
    rep_eng = ReportingEngine()
    rep_port = rep_eng.generate_portfolio_report(p_snap, as_of=T1)

    # 9. Dashboard Engine
    dash_eng = DashboardEngine()
    dash_snap = dash_eng.create_snapshot(p_snap, alloc_plan, exec_state, perf_snap, [rep_port], as_of=T1)

    # 10. Explainability Engine
    exp_eng = ExplainabilityEngine()
    exp_dec = exp_eng.explain_decision(dec, as_of=T1)
    exp_snap = exp_eng.create_snapshot([exp_dec], as_of=T1)

    # 11. Timeline Engine
    tl_eng = TimelineAuditEngine()
    tl_snap = tl_eng.build_timeline(
        decisions=[dec],
        portfolio_snapshot=p_snap,
        allocation_plan=alloc_plan,
        sizing_plan=sz_plan,
        execution_plan=exec_plan,
        broker_plan=b_plan,
        execution_state=exec_state,
        performance_snapshot=perf_snap,
        reports=[rep_port],
        dashboard_snapshot=dash_snap,
        explanation_snapshot=exp_snap,
        as_of=T1,
    )

    return (
        p_snap,
        exec_state,
        perf_snap,
        rep_port,
        dash_snap,
        exp_snap,
        tl_snap,
    )


class TestMonitoringEvaluation:
    def test_evaluate_health_all_healthy(self, full_platform_artifacts):
        (
            p_snap,
            exec_state,
            perf_snap,
            rep_port,
            dash_snap,
            exp_snap,
            tl_snap,
        ) = full_platform_artifacts
        engine = OperationalMonitoringEngine()

        snap = engine.evaluate_health(
            schedule_execution=object(),
            workflow=object(),
            portfolio_snapshot=p_snap,
            execution_state=exec_state,
            performance_snapshot=perf_snap,
            reports=[rep_port],
            dashboard_snapshot=dash_snap,
            explanation_snapshot=exp_snap,
            timeline_snapshot=tl_snap,
            as_of=T1,
        )

        assert len(snap.checks) == 10
        assert snap.summary.overall_status == "HEALTHY"
        assert snap.summary.healthy_checks == 10
        assert snap.summary.missing_checks == 0

        chk_port = snap.check_by_domain(MonitoringDomain.PORTFOLIO)
        assert chk_port.status == "HEALTHY"

        chk_overall = snap.check_by_domain(MonitoringDomain.OVERALL)
        assert chk_overall.status == "HEALTHY"

    def test_evaluate_health_missing_artifacts_detected(self, full_platform_artifacts):
        p_snap, _, _, _, _, _, _ = full_platform_artifacts
        engine = OperationalMonitoringEngine()

        snap = engine.evaluate_health(portfolio_snapshot=p_snap, as_of=T1)

        assert len(snap.checks) == 10
        assert snap.summary.overall_status == "DEGRADED"
        assert snap.summary.missing_checks > 0

        chk_exec = snap.check_by_domain(MonitoringDomain.EXECUTION)
        assert chk_exec.status == "MISSING"


class TestReplayAndImmutability:
    def test_deterministic_replay(self, full_platform_artifacts):
        p_snap, exec_state, _, _, _, _, _ = full_platform_artifacts
        cfg = MonitoringConfig()

        eng1 = OperationalMonitoringEngine(cfg)
        snap1 = eng1.evaluate_health(portfolio_snapshot=p_snap, execution_state=exec_state, as_of=T1)

        eng2 = OperationalMonitoringEngine(cfg)
        snap2 = eng2.evaluate_health(portfolio_snapshot=p_snap, execution_state=exec_state, as_of=T1)

        assert snap1.to_dict() == snap2.to_dict()
        assert snap1.to_json() == snap2.to_json()

    def test_immutable_outputs(self, full_platform_artifacts):
        p_snap, _, _, _, _, _, _ = full_platform_artifacts
        engine = OperationalMonitoringEngine()
        snap = engine.evaluate_health(portfolio_snapshot=p_snap, as_of=T1)

        with pytest.raises(dataclasses.FrozenInstanceError):
            snap.snapshot_id = "MUTATED"

    def test_append_only_history(self, full_platform_artifacts):
        p_snap, _, _, _, _, _, _ = full_platform_artifacts
        engine = OperationalMonitoringEngine()
        engine.evaluate_health(portfolio_snapshot=p_snap, as_of=T1)
        engine.evaluate_health(portfolio_snapshot=p_snap, as_of=DAY2)

        hist = engine.history
        assert len(hist.records) == 2

        with pytest.raises(dataclasses.FrozenInstanceError):
            hist.records = ()


class TestConfigValidation:
    def test_unknown_key_rejected(self):
        with pytest.raises(Exception, match=r"Extra inputs|extra"):
            MonitoringConfig.model_validate({"bogus": 1})

    def test_production_config_loads(self, config_dir):
        cfg = load_monitoring_config(config_dir)
        assert cfg.fail_on_missing_artifacts is False
        assert cfg.record_history is True

    def test_missing_config_fails_loudly(self, tmp_path):
        with pytest.raises(ConfigError):
            load_monitoring_config(tmp_path)


class TestEndToEndIntegration:
    def test_operational_monitoring_engine_across_all_execution_and_intelligence_artifacts(
        self, full_platform_artifacts
    ):
        """Integration test: driving OperationalMonitoringEngine across all platform layers."""
        (
            p_snap,
            exec_state,
            perf_snap,
            rep_port,
            dash_snap,
            exp_snap,
            tl_snap,
        ) = full_platform_artifacts
        engine = OperationalMonitoringEngine()

        snap = engine.evaluate_health(
            schedule_execution=object(),
            workflow=object(),
            portfolio_snapshot=p_snap,
            execution_state=exec_state,
            performance_snapshot=perf_snap,
            reports=[rep_port],
            dashboard_snapshot=dash_snap,
            explanation_snapshot=exp_snap,
            timeline_snapshot=tl_snap,
            as_of=T1,
        )

        assert snap.references.portfolio_snapshot_id == p_snap.snapshot_id
        assert snap.references.execution_state_id == exec_state.state_id
        assert snap.references.performance_snapshot_id == perf_snap.snapshot_id
        assert snap.references.dashboard_snapshot_id == dash_snap.snapshot_id
        assert snap.references.explanation_snapshot_id == exp_snap.snapshot_id
        assert snap.references.timeline_snapshot_id == tl_snap.snapshot_id
        assert snap.summary.overall_status == "HEALTHY"
