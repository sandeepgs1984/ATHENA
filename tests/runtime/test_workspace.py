"""Unified Intelligence Workspace tests (P6.7).

Covers unified aggregation, filtering by artifact type, lookup by ID,
deterministic replay, immutable outputs, workspace history, configuration validation,
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
    load_workspace_config,
)
from athena.config.models import ExportFormat, WorkspaceConfig
from athena.dashboard import DashboardEngine
from athena.domain.decision import Decision, TradePlan
from athena.domain.enums import DecisionType, Direction
from athena.errors import ConfigError, WorkspaceError
from athena.execution import OrderLifecycleEngine
from athena.explainability import ExplainabilityEngine
from athena.export import ExportPresentationEngine
from athena.monitoring import OperationalMonitoringEngine
from athena.orders import OrderPlanningEngine
from athena.portfolio import PortfolioConfig, PortfolioEngine
from athena.reporting import ReportingEngine
from athena.sizing import PositionSizingEngine
from athena.timeline import TimelineAuditEngine
from athena.workspace import UnifiedIntelligenceWorkspace

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
def full_phase6_artifacts(config_dir):
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

    exp_pres_eng = ExportPresentationEngine()
    export_art = exp_pres_eng.export_report(rep_port, ExportFormat.JSON, as_of=T1)
    export_snap = exp_pres_eng.create_snapshot([export_art], as_of=T1)

    return rep_port, dash_snap, exp_snap, tl_snap, mon_snap, export_snap


class TestWorkspaceAggregation:
    def test_assemble_workspace_all_phase6_artifacts(self, full_phase6_artifacts):
        rep_port, dash_snap, exp_snap, tl_snap, mon_snap, export_snap = full_phase6_artifacts
        workspace = UnifiedIntelligenceWorkspace()

        ws_snap = workspace.assemble_workspace(
            reports=[rep_port],
            dashboard_snapshot=dash_snap,
            explanation_snapshot=exp_snap,
            timeline_snapshot=tl_snap,
            monitoring_snapshot=mon_snap,
            export_snapshot=export_snap,
            as_of=T1,
        )

        assert ws_snap.summary.total_entries == 6
        assert ws_snap.summary.overall_health == "HEALTHY"
        assert ws_snap.summary.artifact_counts["REPORT"] == 1
        assert ws_snap.summary.artifact_counts["DASHBOARD"] == 1

        reports_view = ws_snap.filter_by_type("REPORT")
        assert len(reports_view) == 1
        assert reports_view[0].references.report_id == rep_port.report_id

        entry = ws_snap.find_by_id(f"entry-rep-{rep_port.report_id}")
        assert entry is not None
        assert entry.title == rep_port.title


class TestReplayAndImmutability:
    def test_deterministic_replay(self, full_phase6_artifacts):
        rep_port, dash_snap, _, _, _, _ = full_phase6_artifacts
        cfg = WorkspaceConfig()

        ws1 = UnifiedIntelligenceWorkspace(cfg)
        snap1 = ws1.assemble_workspace(reports=[rep_port], dashboard_snapshot=dash_snap, as_of=T1)

        ws2 = UnifiedIntelligenceWorkspace(cfg)
        snap2 = ws2.assemble_workspace(reports=[rep_port], dashboard_snapshot=dash_snap, as_of=T1)

        assert snap1.to_dict() == snap2.to_dict()
        assert snap1.to_json() == snap2.to_json()

    def test_immutable_outputs(self, full_phase6_artifacts):
        rep_port, _, _, _, _, _ = full_phase6_artifacts
        workspace = UnifiedIntelligenceWorkspace()
        snap = workspace.assemble_workspace(reports=[rep_port], as_of=T1)

        with pytest.raises(dataclasses.FrozenInstanceError):
            snap.snapshot_id = "MUTATED"

    def test_append_only_history(self, full_phase6_artifacts):
        rep_port, _, _, _, _, _ = full_phase6_artifacts
        workspace = UnifiedIntelligenceWorkspace()
        workspace.assemble_workspace(reports=[rep_port], as_of=T1)
        workspace.assemble_workspace(reports=[rep_port], as_of=DAY2)

        hist = workspace.history
        assert len(hist.records) == 2

        with pytest.raises(dataclasses.FrozenInstanceError):
            hist.records = ()


class TestConfigValidation:
    def test_unknown_key_rejected(self):
        with pytest.raises(Exception, match=r"Extra inputs|extra"):
            WorkspaceConfig.model_validate({"bogus": 1})

    def test_production_config_loads(self, config_dir):
        cfg = load_workspace_config(config_dir)
        assert cfg.include_unified_summary is True
        assert cfg.record_history is True

    def test_missing_config_fails_loudly(self, tmp_path):
        with pytest.raises(ConfigError):
            load_workspace_config(tmp_path)


class TestEndToEndIntegration:
    def test_unified_intelligence_workspace_across_all_phase6_artifacts(
        self, full_phase6_artifacts
    ):
        """Integration test: assembling UnifiedIntelligenceWorkspace across all Phase 6 artifacts."""
        rep_port, dash_snap, exp_snap, tl_snap, mon_snap, export_snap = full_phase6_artifacts
        workspace = UnifiedIntelligenceWorkspace()

        ws_snap = workspace.assemble_workspace(
            reports=[rep_port],
            dashboard_snapshot=dash_snap,
            explanation_snapshot=exp_snap,
            timeline_snapshot=tl_snap,
            monitoring_snapshot=mon_snap,
            export_snapshot=export_snap,
            as_of=T1,
        )

        assert ws_snap.references.dashboard_snapshot_id == dash_snap.snapshot_id
        assert ws_snap.references.explanation_snapshot_id == exp_snap.snapshot_id
        assert ws_snap.references.timeline_snapshot_id == tl_snap.snapshot_id
        assert ws_snap.references.monitoring_snapshot_id == mon_snap.snapshot_id
        assert ws_snap.references.export_snapshot_id == export_snap.snapshot_id
        assert ws_snap.summary.total_entries == 6
