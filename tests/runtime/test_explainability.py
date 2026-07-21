"""Explainability Engine tests (P6.3).

Covers explanation generation across 9 canonical domains, deterministic replay,
immutable outputs, explanation history, configuration validation, and an end-to-end integration test.
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
    load_order_planning_config,
    load_portfolio_analytics_config,
    load_sizing_config,
)
from athena.config.models import ExplainabilityConfig, ExplanationDomain
from athena.dashboard import DashboardEngine
from athena.domain.decision import Decision, TradePlan
from athena.domain.enums import DecisionType, Direction
from athena.errors import ConfigError, ExplainabilityError
from athena.execution import OrderLifecycleEngine
from athena.explainability import ExplainabilityEngine
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

    return dec, p_snap, alloc_plan, sz_plan, exec_plan, b_plan, exec_state, perf_snap, rep_port, dash_snap


class TestExplanationGeneration:
    def test_explain_all_9_domains(self, full_pipeline_artifacts):
        dec, p_snap, alloc_plan, sz_plan, exec_plan, b_plan, exec_state, perf_snap, rep_port, _ = full_pipeline_artifacts
        engine = ExplainabilityEngine()

        exp_dec = engine.explain_decision(dec, as_of=T1)
        assert exp_dec.domain is ExplanationDomain.DECISION
        assert exp_dec.references.decision_id == dec.decision_id

        exp_port = engine.explain_portfolio(p_snap, as_of=T1)
        assert exp_port.domain is ExplanationDomain.PORTFOLIO
        assert exp_port.references.portfolio_snapshot_id == p_snap.snapshot_id

        exp_alloc = engine.explain_allocation(alloc_plan, as_of=T1)
        assert exp_alloc.domain is ExplanationDomain.ALLOCATION
        assert exp_alloc.references.allocation_plan_id == alloc_plan.plan_id

        exp_sz = engine.explain_sizing(sz_plan, as_of=T1)
        assert exp_sz.domain is ExplanationDomain.SIZING
        assert exp_sz.references.position_sizing_plan_id == sz_plan.plan_id

        exp_ord = engine.explain_order_planning(exec_plan, as_of=T1)
        assert exp_ord.domain is ExplanationDomain.ORDER_PLANNING
        assert exp_ord.references.execution_plan_id == exec_plan.plan_id

        exp_b = engine.explain_broker_translation(b_plan, as_of=T1)
        assert exp_b.domain is ExplanationDomain.BROKER_TRANSLATION
        assert exp_b.references.broker_execution_plan_id == b_plan.broker_plan_id

        exp_lc = engine.explain_lifecycle(exec_state, as_of=T1)
        assert exp_lc.domain is ExplanationDomain.LIFECYCLE
        assert exp_lc.references.execution_state_id == exec_state.state_id

        exp_analytics = engine.explain_analytics(perf_snap, as_of=T1)
        assert exp_analytics.domain is ExplanationDomain.ANALYTICS
        assert exp_analytics.references.performance_snapshot_id == perf_snap.snapshot_id

        exp_rep = engine.explain_reporting(rep_port, as_of=T1)
        assert exp_rep.domain is ExplanationDomain.REPORTING
        assert exp_rep.references.report_id == rep_port.report_id


class TestReplayAndImmutability:
    def test_deterministic_replay(self, full_pipeline_artifacts):
        dec, p_snap, _, _, _, _, _, _, _, _ = full_pipeline_artifacts
        cfg = ExplainabilityConfig()

        eng1 = ExplainabilityEngine(cfg)
        exp1 = eng1.explain_decision(dec, as_of=T1)

        eng2 = ExplainabilityEngine(cfg)
        exp2 = eng2.explain_decision(dec, as_of=T1)

        assert exp1.to_dict() == exp2.to_dict()

    def test_immutable_outputs(self, full_pipeline_artifacts):
        dec, _, _, _, _, _, _, _, _, _ = full_pipeline_artifacts
        engine = ExplainabilityEngine()
        exp = engine.explain_decision(dec, as_of=T1)

        with pytest.raises(dataclasses.FrozenInstanceError):
            exp.explanation_id = "MUTATED"

    def test_append_only_history(self, full_pipeline_artifacts):
        dec, p_snap, _, _, _, _, _, _, _, _ = full_pipeline_artifacts
        engine = ExplainabilityEngine()
        e1 = engine.explain_decision(dec, as_of=T1)
        e2 = engine.explain_portfolio(p_snap, as_of=T1)
        engine.create_snapshot([e1, e2], as_of=T1)

        hist = engine.history
        assert len(hist.records) == 1
        dec_exps = hist.for_domain(ExplanationDomain.DECISION)
        assert len(dec_exps) == 1


class TestConfigValidation:
    def test_unknown_key_rejected(self):
        with pytest.raises(Exception, match=r"Extra inputs|extra"):
            ExplainabilityConfig.model_validate({"bogus": 1})

    def test_production_config_loads(self, config_dir):
        cfg = load_explainability_config(config_dir)
        assert cfg.detail_level == "detailed"
        assert cfg.include_facts is True

    def test_missing_config_fails_loudly(self, tmp_path):
        with pytest.raises(ConfigError):
            load_explainability_config(tmp_path)


class TestEndToEndIntegration:
    def test_explainability_engine_across_full_execution_pipeline_and_reporting_dashboard(
        self, full_pipeline_artifacts
    ):
        """Integration test: driving ExplainabilityEngine across all platform artifacts."""
        dec, p_snap, alloc_plan, sz_plan, exec_plan, b_plan, exec_state, perf_snap, rep_port, dash_snap = full_pipeline_artifacts
        engine = ExplainabilityEngine()

        e_dec = engine.explain_decision(dec, as_of=T1)
        e_port = engine.explain_portfolio(p_snap, as_of=T1)
        e_alloc = engine.explain_allocation(alloc_plan, as_of=T1)
        e_sz = engine.explain_sizing(sz_plan, as_of=T1)
        e_ord = engine.explain_order_planning(exec_plan, as_of=T1)
        e_b = engine.explain_broker_translation(b_plan, as_of=T1)
        e_lc = engine.explain_lifecycle(exec_state, as_of=T1)
        e_analytics = engine.explain_analytics(perf_snap, as_of=T1)
        e_rep = engine.explain_reporting(rep_port, as_of=T1)

        all_exps = [e_dec, e_port, e_alloc, e_sz, e_ord, e_b, e_lc, e_analytics, e_rep]
        snap = engine.create_snapshot(all_exps, as_of=T1)

        assert len(snap.explanations) == 9
        assert "DECISION" in snap.summary_text
        assert snap.explanation_by_domain(ExplanationDomain.DECISION) is not None
        assert snap.explanation_by_domain(ExplanationDomain.REPORTING) is not None
