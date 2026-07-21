"""Export & Presentation Layer tests (P6.6).

Covers export generation across all formats (JSON, Markdown, Text, CSV),
deterministic serialization, immutable outputs, export history, configuration validation,
and an end-to-end integration test.
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
    load_export_config,
    load_monitoring_config,
    load_order_planning_config,
    load_portfolio_analytics_config,
    load_sizing_config,
    load_timeline_config,
)
from athena.config.models import ExportConfig, ExportFormat
from athena.dashboard import DashboardEngine
from athena.domain.decision import Decision, TradePlan
from athena.domain.enums import DecisionType, Direction
from athena.errors import ConfigError, ExportError
from athena.execution import OrderLifecycleEngine
from athena.explainability import ExplainabilityEngine
from athena.export import ExportPresentationEngine
from athena.monitoring import OperationalMonitoringEngine
from athena.orders import OrderPlanningEngine
from athena.portfolio import PortfolioConfig, PortfolioEngine
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
def full_intelligence_artifacts(config_dir):
    dec = _decision("INFY")

    p_cfg = PortfolioConfig(initial_cash=Decimal("1000000.00"))
    p_eng = PortfolioEngine(p_cfg, initial_as_of=AS_OF)
    p_eng.open_position("INFY", quantity=Decimal("100"), cost_price=Decimal("1500.00"), as_of=AS_OF)
    p_snap = p_eng.current_snapshot

    alloc_cfg = load_allocation_config(config_dir)
    alloc_eng = CapitalAllocationEngine(alloc_cfg)
    alloc_plan = alloc_eng.allocate(p_snap, [dec], as_of=AS_OF)

    sz_cfg = load_sizing_config(config_dir)
    sz_eng = PositionSizingEngine(sz_cfg)
    sz_plan = sz_eng.size_plan(alloc_plan, {"INFY": Decimal("1500.00")}, as_of=AS_OF)

    ord_cfg = load_order_planning_config(config_dir)
    ord_eng = OrderPlanningEngine(ord_cfg)
    exec_plan = ord_eng.plan_execution(sz_plan, as_of=AS_OF)

    b_cfg = load_broker_config(config_dir)
    b_mgr = BrokerManager(b_cfg)
    b_plan = b_mgr.translate_plan(exec_plan, as_of=AS_OF)

    lc_cfg = load_execution_config(config_dir)
    lc_eng = OrderLifecycleEngine(lc_cfg)
    exec_state = lc_eng.initialize_from_plan(b_plan, as_of=AS_OF)

    analytics_cfg = load_portfolio_analytics_config(config_dir)
    analytics_eng = PortfolioAnalyticsEngine(analytics_cfg)
    perf_snap = analytics_eng.analyze(p_snap, exec_state, current_prices={"INFY": Decimal("1600.00")}, as_of=T1)

    rep_eng = ReportingEngine()
    rep_port = rep_eng.generate_portfolio_report(p_snap, as_of=T1)

    dash_eng = DashboardEngine()
    dash_snap = dash_eng.create_snapshot(p_snap, alloc_plan, exec_state, perf_snap, [rep_port], as_of=T1)

    exp_eng = ExplainabilityEngine()
    exp_dec = exp_eng.explain_decision(dec, as_of=T1)
    exp_snap = exp_eng.create_snapshot([exp_dec], as_of=T1)

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

    mon_eng = OperationalMonitoringEngine()
    mon_snap = mon_eng.evaluate_health(
        portfolio_snapshot=p_snap,
        execution_state=exec_state,
        performance_snapshot=perf_snap,
        reports=[rep_port],
        dashboard_snapshot=dash_snap,
        explanation_snapshot=exp_snap,
        timeline_snapshot=tl_snap,
        as_of=T1,
    )

    return rep_port, dash_snap, exp_snap, tl_snap, mon_snap


class TestExportFormats:
    def test_export_report_formats(self, full_intelligence_artifacts):
        rep_port, _, _, _, _ = full_intelligence_artifacts
        engine = ExportPresentationEngine()

        # JSON
        exp_json = engine.export_report(rep_port, ExportFormat.JSON, as_of=T1)
        assert exp_json.content_type == "application/json"
        assert "rep-" in exp_json.payload

        # Markdown
        exp_md = engine.export_report(rep_port, ExportFormat.MARKDOWN, as_of=T1)
        assert exp_md.content_type == "text/markdown"
        assert "# ATHENA EXPORT" in exp_md.payload

        # Text
        exp_txt = engine.export_report(rep_port, ExportFormat.TEXT, as_of=T1)
        assert exp_txt.content_type == "text/plain"

        # CSV
        exp_csv = engine.export_report(rep_port, ExportFormat.CSV, as_of=T1)
        assert exp_csv.content_type == "text/csv"

    def test_export_all_intelligence_artifacts(self, full_intelligence_artifacts):
        rep_port, dash_snap, exp_snap, tl_snap, mon_snap = full_intelligence_artifacts
        engine = ExportPresentationEngine()

        e1 = engine.export_report(rep_port, ExportFormat.JSON, as_of=T1)
        e2 = engine.export_dashboard(dash_snap, ExportFormat.MARKDOWN, as_of=T1)
        e3 = engine.export_explanation(exp_snap, ExportFormat.TEXT, as_of=T1)
        e4 = engine.export_timeline(tl_snap, ExportFormat.CSV, as_of=T1)
        e5 = engine.export_monitoring(mon_snap, ExportFormat.CSV, as_of=T1)

        batch_snap = engine.create_snapshot([e1, e2, e3, e4, e5], as_of=T1)
        assert batch_snap.summary.total_exports == 5
        assert len(batch_snap.summary.formats_used) == 4


class TestReplayAndImmutability:
    def test_deterministic_replay(self, full_intelligence_artifacts):
        rep_port, _, _, _, _ = full_intelligence_artifacts
        cfg = ExportConfig()

        eng1 = ExportPresentationEngine(cfg)
        exp1 = eng1.export_report(rep_port, ExportFormat.JSON, as_of=T1)

        eng2 = ExportPresentationEngine(cfg)
        exp2 = eng2.export_report(rep_port, ExportFormat.JSON, as_of=T1)

        assert exp1.to_dict() == exp2.to_dict()
        assert exp1.payload == exp2.payload

    def test_immutable_outputs(self, full_intelligence_artifacts):
        rep_port, _, _, _, _ = full_intelligence_artifacts
        engine = ExportPresentationEngine()
        exp = engine.export_report(rep_port, ExportFormat.JSON, as_of=T1)

        with pytest.raises(dataclasses.FrozenInstanceError):
            exp.export_id = "MUTATED"

    def test_append_only_history(self, full_intelligence_artifacts):
        rep_port, _, _, _, _ = full_intelligence_artifacts
        engine = ExportPresentationEngine()
        e = engine.export_report(rep_port, ExportFormat.JSON, as_of=T1)
        engine.create_snapshot([e], as_of=T1)

        hist = engine.history
        assert len(hist.records) == 1

        with pytest.raises(dataclasses.FrozenInstanceError):
            hist.records = ()


class TestConfigValidation:
    def test_unknown_key_rejected(self):
        with pytest.raises(Exception, match=r"Extra inputs|extra"):
            ExportConfig.model_validate({"bogus": 1})

    def test_production_config_loads(self, config_dir):
        cfg = load_export_config(config_dir)
        assert cfg.default_format == ExportFormat.JSON
        assert cfg.record_history is True

    def test_missing_config_fails_loudly(self, tmp_path):
        with pytest.raises(ConfigError):
            load_export_config(tmp_path)


class TestEndToEndIntegration:
    def test_export_engine_across_all_phase_6_intelligence_artifacts(
        self, full_intelligence_artifacts
    ):
        """Integration test: exporting all Phase 6 intelligence artifacts across all 4 formats."""
        rep_port, dash_snap, exp_snap, tl_snap, mon_snap = full_intelligence_artifacts
        engine = ExportPresentationEngine()

        exports = []
        for fmt in (ExportFormat.JSON, ExportFormat.MARKDOWN, ExportFormat.TEXT, ExportFormat.CSV):
            exports.append(engine.export_report(rep_port, fmt, as_of=T1))
            exports.append(engine.export_dashboard(dash_snap, fmt, as_of=T1))
            exports.append(engine.export_explanation(exp_snap, fmt, as_of=T1))
            exports.append(engine.export_timeline(tl_snap, fmt, as_of=T1))
            exports.append(engine.export_monitoring(mon_snap, fmt, as_of=T1))

        batch = engine.create_snapshot(exports, as_of=T1)
        assert batch.summary.total_exports == 20
        assert len(batch.summary.formats_used) == 4
        assert batch.summary.total_bytes > 0
