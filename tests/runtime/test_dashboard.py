"""Dashboard & Snapshot Engine tests (P6.2).

Covers dashboard generation, section aggregation, portfolio summaries,
execution summaries, analytics summaries, deterministic replay, immutable outputs,
dashboard history, configuration validation, and an end-to-end integration test.
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
    load_order_planning_config,
    load_portfolio_analytics_config,
    load_sizing_config,
)
from athena.config.models import DashboardConfig
from athena.dashboard import DashboardEngine
from athena.domain.decision import Decision, TradePlan
from athena.domain.enums import DecisionType, Direction
from athena.errors import ConfigError, DashboardError
from athena.execution import OrderLifecycleEngine
from athena.orders import OrderPlanningEngine
from athena.config import PortfolioConfig
from athena.portfolio import PortfolioEngine
from athena.reporting import ReportingEngine
from athena.sizing import PositionSizingEngine

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
def full_pipeline_artifacts(config_dir):
    # 1. Portfolio Engine
    p_cfg = PortfolioConfig(initial_cash=Decimal("1000000.00"))
    p_eng = PortfolioEngine(p_cfg, initial_as_of=AS_OF)
    p_eng.open_position("INFY", quantity=100, price=Decimal("1500.00"), as_of=AS_OF)
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

    # 8. Reporting Framework
    rep_eng = ReportingEngine()
    rep_port = rep_eng.generate_portfolio_report(p_snap, as_of=T1)

    return p_snap, alloc_plan, exec_state, perf_snap, [rep_port]


class TestDashboardGeneration:
    def test_create_snapshot_all_sections(self, full_pipeline_artifacts):
        p_snap, alloc_plan, exec_state, perf_snap, reports = full_pipeline_artifacts
        engine = DashboardEngine()

        snap = engine.create_snapshot(
            portfolio_snapshot=p_snap,
            allocation_plan=alloc_plan,
            execution_state=exec_state,
            performance_snapshot=perf_snap,
            reports=reports,
            as_of=T1,
        )

        assert len(snap.sections) == 9
        assert snap.summary.portfolio_value == Decimal("1000000.00")
        assert snap.summary.health_status == "OK"

        sec_port = snap.section_by_id("portfolio_overview")
        assert sec_port.status == "HEALTHY"
        assert sec_port.metrics["total_value"] == "1000000.00"

        sec_health = snap.section_by_id("platform_health")
        assert sec_health.status == "OK"
        assert sec_health.metrics["pipeline_status"] == "OK"

    def test_create_snapshot_partial_artifacts(self, full_pipeline_artifacts):
        p_snap, _, _, _, _ = full_pipeline_artifacts
        engine = DashboardEngine()

        snap = engine.create_snapshot(portfolio_snapshot=p_snap, as_of=T1)
        assert len(snap.sections) == 4  # portfolio, positions, reporting, health
        assert snap.summary.portfolio_value == Decimal("1000000.00")


class TestReplayAndImmutability:
    def test_deterministic_replay(self, full_pipeline_artifacts):
        p_snap, alloc_plan, exec_state, perf_snap, reports = full_pipeline_artifacts
        cfg = DashboardConfig()

        eng1 = DashboardEngine(cfg)
        snap1 = eng1.create_snapshot(p_snap, alloc_plan, exec_state, perf_snap, reports, as_of=T1)

        eng2 = DashboardEngine(cfg)
        snap2 = eng2.create_snapshot(p_snap, alloc_plan, exec_state, perf_snap, reports, as_of=T1)

        assert snap1.to_dict() == snap2.to_dict()
        assert snap1.to_json() == snap2.to_json()

    def test_immutable_outputs(self, full_pipeline_artifacts):
        p_snap, _, _, _, _ = full_pipeline_artifacts
        engine = DashboardEngine()
        snap = engine.create_snapshot(p_snap, as_of=T1)

        with pytest.raises(dataclasses.FrozenInstanceError):
            snap.snapshot_id = "MUTATED"

        sec = snap.sections[0]
        with pytest.raises(dataclasses.FrozenInstanceError):
            sec.status = "MUTATED"

    def test_append_only_history(self, full_pipeline_artifacts):
        p_snap, _, _, _, _ = full_pipeline_artifacts
        engine = DashboardEngine()
        engine.create_snapshot(p_snap, as_of=T1)
        engine.create_snapshot(p_snap, as_of=DAY2)

        hist = engine.history
        assert len(hist.records) == 2

        with pytest.raises(dataclasses.FrozenInstanceError):
            hist.records = ()


class TestConfigValidation:
    def test_unknown_key_rejected(self):
        with pytest.raises(Exception, match=r"Extra inputs|extra"):
            DashboardConfig.model_validate({"bogus": 1})

    def test_production_config_loads(self, config_dir):
        cfg = load_dashboard_config(config_dir)
        assert cfg.default_theme == "dark"
        assert cfg.include_text_rendering is True

    def test_missing_config_fails_loudly(self, tmp_path):
        with pytest.raises(ConfigError):
            load_dashboard_config(tmp_path)


class TestEndToEndIntegration:
    def test_dashboard_engine_consuming_phase_5_and_reporting_artifacts(self, full_pipeline_artifacts):
        """Integration test: driving DashboardEngine using outputs from Phase 5 pipeline and Reporting Framework."""
        p_snap, alloc_plan, exec_state, perf_snap, reports = full_pipeline_artifacts
        engine = DashboardEngine()

        snap = engine.create_snapshot(
            portfolio_snapshot=p_snap,
            allocation_plan=alloc_plan,
            execution_state=exec_state,
            performance_snapshot=perf_snap,
            reports=reports,
            as_of=T1,
        )

        assert snap.references.portfolio_snapshot_id == p_snap.snapshot_id
        assert snap.references.allocation_plan_id == alloc_plan.plan_id
        assert snap.references.execution_state_id == exec_state.state_id
        assert snap.references.performance_snapshot_id == perf_snap.snapshot_id
        assert len(snap.sections) == 9
