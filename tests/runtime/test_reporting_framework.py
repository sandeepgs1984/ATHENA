"""Reporting Framework tests (P6.1).

Covers portfolio reports, execution reports, allocation reports, analytics reports,
audit reports, machine/text views, replay reconstruction, immutable outputs,
reporting history, configuration validation, and an end-to-end integration test.
"""

from __future__ import annotations

import dataclasses
import json
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

import pytest

from athena.allocation import CapitalAllocationEngine
from athena.analytics.portfolio import PortfolioAnalyticsEngine
from athena.brokers import BrokerManager
from athena.config.loader import (
    load_allocation_config,
    load_broker_config,
    load_execution_config,
    load_order_planning_config,
    load_portfolio_analytics_config,
    load_reporting_framework_config,
    load_sizing_config,
)
from athena.config.models import ReportType, ReportingFrameworkConfig
from athena.domain.decision import Decision, TradePlan
from athena.domain.enums import DecisionType, Direction
from athena.errors import ConfigError, ReportingError
from athena.execution import OrderLifecycleEngine
from athena.orders import OrderPlanningEngine
from athena.portfolio import PortfolioConfig, PortfolioEngine
from athena.reporting import ReportingEngine
from athena.sizing import PositionSizingEngine

from decimal import Decimal

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
def full_pipeline_outputs(config_dir):
    # 1. Portfolio Engine
    p_cfg = PortfolioConfig(initial_cash=Decimal("1000000.00"))
    p_eng = PortfolioEngine(p_cfg, initial_as_of=AS_OF)
    p_eng.open_position("INFY", quantity=Decimal("100"), cost_price=Decimal("1500.00"), as_of=AS_OF)
    p_snap = p_eng.current_snapshot

    # 2. Allocation Engine
    alloc_cfg = load_allocation_config(config_dir)
    alloc_eng = CapitalAllocationEngine(alloc_cfg)
    alloc_plan = alloc_eng.allocate(p_snap, [_decision("INFY")], as_of=AS_OF)

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

    return p_snap, alloc_plan, exec_state, perf_snap


class TestReportGeneration:
    def test_portfolio_report(self, full_pipeline_outputs):
        p_snap, _, _, _ = full_pipeline_outputs
        engine = ReportingEngine()

        report = engine.generate_portfolio_report(p_snap, as_of=T1)
        assert report.report_type is ReportType.PORTFOLIO
        assert report.references.portfolio_snapshot_id == p_snap.snapshot_id
        assert "PORTFOLIO REPORT" in report.to_text()
        assert report.content["total_value"] == "1000000.00"

    def test_execution_report(self, full_pipeline_outputs):
        _, _, exec_state, _ = full_pipeline_outputs
        engine = ReportingEngine()

        report = engine.generate_execution_report(exec_state, as_of=T1)
        assert report.report_type is ReportType.EXECUTION
        assert report.references.execution_state_id == exec_state.state_id
        assert "EXECUTION REPORT" in report.to_text()

    def test_allocation_report(self, full_pipeline_outputs):
        _, alloc_plan, _, _ = full_pipeline_outputs
        engine = ReportingEngine()

        report = engine.generate_allocation_report(alloc_plan, as_of=T1)
        assert report.report_type is ReportType.ALLOCATION
        assert report.references.allocation_plan_id == alloc_plan.plan_id
        assert "CAPITAL ALLOCATION REPORT" in report.to_text()

    def test_analytics_report(self, full_pipeline_outputs):
        _, _, _, perf_snap = full_pipeline_outputs
        engine = ReportingEngine()

        report = engine.generate_analytics_report(perf_snap, as_of=T1)
        assert report.report_type is ReportType.ANALYTICS
        assert report.references.performance_snapshot_id == perf_snap.snapshot_id
        assert "PORTFOLIO ANALYTICS REPORT" in report.to_text()

    def test_audit_report(self):
        engine = ReportingEngine()
        events = [{"event": "RUN_STARTED", "run_id": "r100"}]

        report = engine.generate_audit_report("r100", events, as_of=T1)
        assert report.report_type is ReportType.AUDIT
        assert report.references.audit_id == "r100"
        assert "AUDIT LOG REPORT" in report.to_text()


class TestReplayAndImmutability:
    def test_deterministic_replay(self, full_pipeline_outputs):
        p_snap, _, _, _ = full_pipeline_outputs
        cfg = ReportingFrameworkConfig()

        eng1 = ReportingEngine(cfg)
        rep1 = eng1.generate_portfolio_report(p_snap, as_of=T1)

        eng2 = ReportingEngine(cfg)
        rep2 = eng2.generate_portfolio_report(p_snap, as_of=T1)

        assert rep1.to_dict() == rep2.to_dict()
        assert rep1.to_json() == rep2.to_json()

    def test_immutable_outputs(self, full_pipeline_outputs):
        p_snap, _, _, _ = full_pipeline_outputs
        engine = ReportingEngine()
        report = engine.generate_portfolio_report(p_snap, as_of=T1)

        with pytest.raises(dataclasses.FrozenInstanceError):
            report.report_id = "MUTATED"

    def test_append_only_history(self, full_pipeline_outputs):
        p_snap, alloc_plan, _, _ = full_pipeline_outputs
        engine = ReportingEngine()
        engine.generate_portfolio_report(p_snap, as_of=T1)
        engine.generate_allocation_report(alloc_plan, as_of=T1)

        hist = engine.history
        assert len(hist.records) == 2
        port_reps = hist.for_type(ReportType.PORTFOLIO)
        assert len(port_reps) == 1

        with pytest.raises(dataclasses.FrozenInstanceError):
            hist.records = ()


class TestConfigValidation:
    def test_unknown_key_rejected(self):
        with pytest.raises(Exception, match=r"Extra inputs|extra"):
            ReportingFrameworkConfig.model_validate({"bogus": 1})

    def test_production_config_loads(self, config_dir):
        cfg = load_reporting_framework_config(config_dir)
        assert cfg.default_format == "text"
        assert cfg.include_text_rendering is True

    def test_missing_config_fails_loudly(self, tmp_path):
        with pytest.raises(ConfigError):
            load_reporting_framework_config(tmp_path)


class TestEndToEndIntegration:
    def test_reporting_framework_consuming_all_platform_artifacts(self, full_pipeline_outputs):
        """Integration test: driving ReportingEngine across all Phases 1-5 artifacts."""
        p_snap, alloc_plan, exec_state, perf_snap = full_pipeline_outputs
        engine = ReportingEngine()

        r_port = engine.generate_portfolio_report(p_snap, as_of=T1)
        r_alloc = engine.generate_allocation_report(alloc_plan, as_of=T1)
        r_exec = engine.generate_execution_report(exec_state, as_of=T1)
        r_analytics = engine.generate_analytics_report(perf_snap, as_of=T1)

        assert engine.history.to_dict()["records"] is not None
        assert len(engine.history.records) == 4
        assert r_port.references.portfolio_snapshot_id == p_snap.snapshot_id
        assert r_alloc.references.allocation_plan_id == alloc_plan.plan_id
        assert r_exec.references.execution_state_id == exec_state.state_id
        assert r_analytics.references.performance_snapshot_id == perf_snap.snapshot_id
