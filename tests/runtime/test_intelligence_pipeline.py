"""Intelligence Pipeline Registration runtime tests (P7.3).

Covers pipeline definition construction, topology validation, end-to-end execution
across all 6 registered intelligence stages, failure propagation, deterministic replay,
and artifact immutability.

The tests construct a pre-populated PipelineContext with execution artifacts
(simulating the Execution Pipeline's output) and verify that each intelligence stage
produces the expected artifact under its typed IntelligenceArtifactKey.
"""

from __future__ import annotations

import dataclasses
from datetime import datetime, timedelta
from decimal import Decimal
from zoneinfo import ZoneInfo

import pytest

from athena.analytics.portfolio import PortfolioAnalyticsEngine
from athena.brokers import BrokerManager
from athena.config import PortfolioConfig
from athena.config.loader import (
    load_broker_config,
    load_execution_config,
    load_portfolio_analytics_config,
)
from athena.dashboard.engine import DashboardEngine
from athena.domain.decision import Decision, TradePlan
from athena.domain.enums import DecisionType, Direction
from athena.errors import OrchestrationError
from athena.execution import OrderLifecycleEngine
from athena.explainability.engine import ExplainabilityEngine
from athena.export.engine import ExportPresentationEngine
from athena.monitoring.engine import OperationalMonitoringEngine
from athena.orchestration import (
    INTELLIGENCE_PIPELINE_OPTIONAL_INPUTS,
    INTELLIGENCE_PIPELINE_REQUIRED_INPUTS,
    ExecutionArtifactKey,
    IntelligenceArtifactKey,
    IntelligenceStageId,
    PipelineContext,
    PipelineDefinition,
    PipelineResult,
    PipelineRunner,
    StageStatus,
    create_execution_pipeline,
    create_intelligence_pipeline,
    validate_intelligence_pipeline,
)
from athena.orchestration.stages import (
    DashboardStage,
    ExplainabilityStage,
    ExportStage,
    MonitoringStage,
    ReportingStage,
    TimelineStage,
)
from athena.portfolio import PortfolioEngine
from athena.reporting.engine import ReportingEngine
from athena.timeline.engine import TimelineAuditEngine

IST = ZoneInfo("Asia/Kolkata")
AS_OF = datetime(2026, 3, 2, 8, 30, tzinfo=IST)


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
        valid_until=AS_OF + timedelta(days=1),
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

def _make_execution_stages(config_dir) -> list:
    from athena.allocation import CapitalAllocationEngine
    from athena.config.loader import (
        load_allocation_config,
        load_order_planning_config,
        load_sizing_config,
    )
    from athena.orchestration.stages import (
        BrokerTranslationStage,
        CapitalAllocationStage,
        DecisionsLoadStage,
        OrderLifecycleStage,
        OrderPlanningStage,
        PortfolioAnalyticsStage,
        PortfolioSnapshotStage,
        PositionSizingStage,
    )
    from athena.orders import OrderPlanningEngine
    from athena.sizing import PositionSizingEngine

    p_cfg = PortfolioConfig(initial_cash=Decimal("1000000.00"))
    p_eng = PortfolioEngine(p_cfg, initial_as_of=AS_OF)
    p_eng.open_position("INFY", quantity=100, price=Decimal("1500.00"), as_of=AS_OF)

    alloc_cfg = load_allocation_config(config_dir)
    alloc_eng = CapitalAllocationEngine(alloc_cfg)

    sz_cfg = load_sizing_config(config_dir)
    sz_eng = PositionSizingEngine(sz_cfg)

    ord_cfg = load_order_planning_config(config_dir)
    ord_eng = OrderPlanningEngine(ord_cfg)

    b_cfg = load_broker_config(config_dir)
    b_mgr = BrokerManager(b_cfg)

    lc_cfg = load_execution_config(config_dir)
    lc_eng = OrderLifecycleEngine(lc_cfg)

    analytics_cfg = load_portfolio_analytics_config(config_dir)
    analytics_eng = PortfolioAnalyticsEngine(analytics_cfg)

    dec = _decision("INFY")
    return [
        PortfolioSnapshotStage(p_eng),
        DecisionsLoadStage([dec]),
        CapitalAllocationStage(alloc_eng),
        PositionSizingStage(sz_eng),
        OrderPlanningStage(ord_eng),
        BrokerTranslationStage(b_mgr),
        OrderLifecycleStage(lc_eng),
        PortfolioAnalyticsStage(analytics_eng),
    ]

def _build_execution_context(config_dir) -> PipelineContext:
    """Build a context pre-populated with execution pipeline outputs."""
    stages = _make_execution_stages(config_dir)
    definition = create_execution_pipeline(stages)
    runner = PipelineRunner()
    initial_context = PipelineContext(
        run_id="run-p73-setup",
        as_of=AS_OF + timedelta(days=1),
        data={
            ExecutionArtifactKey.DECISIONS.value: [_decision("INFY")],
            ExecutionArtifactKey.CURRENT_PRICES.value: {"INFY": Decimal("1600.00")},
        },
    )
    res = runner.run(definition, initial_context)
    return res.final_context


def _make_intelligence_stages() -> list:
    """Instantiate all six intelligence stage adapters with their engines."""
    return [
        ReportingStage(ReportingEngine()),
        ExplainabilityStage(ExplainabilityEngine()),
        DashboardStage(DashboardEngine()),
        MonitoringStage(OperationalMonitoringEngine()),
        TimelineStage(TimelineAuditEngine()),
        ExportStage(ExportPresentationEngine()),
    ]


@pytest.fixture()
def intelligence_stages():
    return _make_intelligence_stages()


@pytest.fixture()
def execution_context(config_dir):
    return _build_execution_context(config_dir)


class TestIntelligencePipelineRegistrationAndValidation:
    def test_create_intelligence_pipeline_returns_definition(self, intelligence_stages):
        definition = create_intelligence_pipeline(intelligence_stages)

        assert isinstance(definition, PipelineDefinition)
        assert definition.metadata.definition_id == "intelligence-pipeline"
        assert definition.metadata.version == "1.0.0"
        assert len(definition.stages) == 6

    def test_pipeline_has_correct_stage_count(self, intelligence_stages):
        definition = create_intelligence_pipeline(intelligence_stages)
        assert len(definition.stages) == 6

    def test_pipeline_has_four_independent_producer_stage_ids(self, intelligence_stages):
        definition = create_intelligence_pipeline(intelligence_stages)
        stage_ids = {s.stage_id for s in definition.stages}

        assert IntelligenceStageId.REPORTING.value in stage_ids
        assert IntelligenceStageId.EXPLAINABILITY.value in stage_ids
        assert IntelligenceStageId.DASHBOARD.value in stage_ids
        assert IntelligenceStageId.MONITORING.value in stage_ids

    def test_pipeline_has_terminal_export_stage(self, intelligence_stages):
        definition = create_intelligence_pipeline(intelligence_stages)
        stage_ids = {s.stage_id for s in definition.stages}
        assert IntelligenceStageId.EXPORT.value in stage_ids

    def test_validate_intelligence_pipeline_passes_on_valid_definition(self, intelligence_stages):
        definition = create_intelligence_pipeline(intelligence_stages)
        # Must not raise
        validate_intelligence_pipeline(definition)

    def test_duplicate_stage_id_rejected(self, intelligence_stages):
        dup = list(intelligence_stages)
        dup[5] = dup[0]  # keep length 6 but duplicate stage[0] in place of stage[5]
        with pytest.raises(OrchestrationError, match="Duplicate stage_id"):
            create_intelligence_pipeline(dup)

    def test_empty_stages_rejected(self):
        with pytest.raises(OrchestrationError, match="empty stages"):
            create_intelligence_pipeline([])

    def test_wrong_stage_count_rejected(self):
        # Provide only 5 stages — validator should reject
        stages = _make_intelligence_stages()[:5]
        with pytest.raises(OrchestrationError, match="expects 6 stages"):
            create_intelligence_pipeline(stages)

    def test_input_contract_constants_are_frozen_sets(self):
        assert isinstance(INTELLIGENCE_PIPELINE_REQUIRED_INPUTS, frozenset)
        assert isinstance(INTELLIGENCE_PIPELINE_OPTIONAL_INPUTS, frozenset)

    def test_required_inputs_contains_expected_keys(self):
        assert ExecutionArtifactKey.PORTFOLIO_SNAPSHOT in INTELLIGENCE_PIPELINE_REQUIRED_INPUTS
        assert ExecutionArtifactKey.PERFORMANCE_SNAPSHOT in INTELLIGENCE_PIPELINE_REQUIRED_INPUTS
        assert ExecutionArtifactKey.EXECUTION_STATE in INTELLIGENCE_PIPELINE_REQUIRED_INPUTS
        assert ExecutionArtifactKey.ALLOCATION_PLAN in INTELLIGENCE_PIPELINE_REQUIRED_INPUTS

    def test_optional_inputs_do_not_overlap_with_required(self):
        overlap = INTELLIGENCE_PIPELINE_REQUIRED_INPUTS & INTELLIGENCE_PIPELINE_OPTIONAL_INPUTS
        assert len(overlap) == 0


class TestIntelligencePipelineRunner:
    def test_end_to_end_intelligence_pipeline_success(self, intelligence_stages, execution_context):
        definition = create_intelligence_pipeline(intelligence_stages)
        runner = PipelineRunner()

        result = runner.run(definition, execution_context)

        assert isinstance(result, PipelineResult)
        assert len(result.stages) == 6
        assert all(sr.status == StageStatus.SUCCESS for sr in result.stages)

        final_ctx = result.final_context
        assert final_ctx.get(IntelligenceArtifactKey.REPORTS.value) is not None
        assert final_ctx.get(IntelligenceArtifactKey.EXPLANATION_SNAPSHOT.value) is not None
        assert final_ctx.get(IntelligenceArtifactKey.DASHBOARD_SNAPSHOT.value) is not None
        assert final_ctx.get(IntelligenceArtifactKey.MONITORING_SNAPSHOT.value) is not None
        assert final_ctx.get(IntelligenceArtifactKey.TIMELINE_SNAPSHOT.value) is not None
        assert final_ctx.get(IntelligenceArtifactKey.EXPORT_SNAPSHOT.value) is not None

    def test_reporting_stage_produces_report_list(self, execution_context):
        stage = ReportingStage(ReportingEngine())
        exec_result = stage.execute(execution_context)

        assert exec_result.stage_result.status == StageStatus.SUCCESS
        reports = exec_result.context.get(IntelligenceArtifactKey.REPORTS.value)
        assert isinstance(reports, list)
        assert len(reports) > 0

    def test_explainability_stage_produces_explanation_snapshot(self, execution_context):
        stage = ExplainabilityStage(ExplainabilityEngine())
        exec_result = stage.execute(execution_context)

        assert exec_result.stage_result.status == StageStatus.SUCCESS
        exp_snap = exec_result.context.get(IntelligenceArtifactKey.EXPLANATION_SNAPSHOT.value)
        assert exp_snap is not None
        assert hasattr(exp_snap, "snapshot_id")

    def test_dashboard_stage_produces_dashboard_snapshot(self, execution_context):
        stage = DashboardStage(DashboardEngine())
        exec_result = stage.execute(execution_context)

        assert exec_result.stage_result.status == StageStatus.SUCCESS
        dash_snap = exec_result.context.get(IntelligenceArtifactKey.DASHBOARD_SNAPSHOT.value)
        assert dash_snap is not None
        assert hasattr(dash_snap, "snapshot_id")

    def test_monitoring_stage_produces_monitoring_snapshot(self, execution_context):
        stage = MonitoringStage(OperationalMonitoringEngine())
        exec_result = stage.execute(execution_context)

        assert exec_result.stage_result.status == StageStatus.SUCCESS
        mon_snap = exec_result.context.get(IntelligenceArtifactKey.MONITORING_SNAPSHOT.value)
        assert mon_snap is not None
        assert hasattr(mon_snap, "snapshot_id")

    def test_timeline_stage_produces_timeline_snapshot(self, execution_context):
        # Pre-populate intelligence artifacts that Timeline aggregates
        ctx = execution_context
        ctx = ReportingStage(ReportingEngine()).execute(ctx).context
        ctx = ExplainabilityStage(ExplainabilityEngine()).execute(ctx).context
        ctx = DashboardStage(DashboardEngine()).execute(ctx).context

        stage = TimelineStage(TimelineAuditEngine())
        exec_result = stage.execute(ctx)

        assert exec_result.stage_result.status == StageStatus.SUCCESS
        tl_snap = exec_result.context.get(IntelligenceArtifactKey.TIMELINE_SNAPSHOT.value)
        assert tl_snap is not None
        assert hasattr(tl_snap, "snapshot_id")

    def test_export_stage_produces_export_snapshot(self, execution_context):
        # Run all upstream stages first
        ctx = execution_context
        ctx = ReportingStage(ReportingEngine()).execute(ctx).context
        ctx = ExplainabilityStage(ExplainabilityEngine()).execute(ctx).context
        ctx = DashboardStage(DashboardEngine()).execute(ctx).context
        ctx = MonitoringStage(OperationalMonitoringEngine()).execute(ctx).context
        ctx = TimelineStage(TimelineAuditEngine()).execute(ctx).context

        stage = ExportStage(ExportPresentationEngine())
        exec_result = stage.execute(ctx)

        assert exec_result.stage_result.status == StageStatus.SUCCESS
        export_snap = exec_result.context.get(IntelligenceArtifactKey.EXPORT_SNAPSHOT.value)
        assert export_snap is not None
        assert export_snap.summary.total_exports > 0

    def test_failure_isolation_empty_context(self):
        # ReportingStage should succeed on empty context (all inputs optional)
        stage = ReportingStage(ReportingEngine())
        ctx = PipelineContext(run_id="run-fail-test", as_of=AS_OF)
        exec_result = stage.execute(ctx)

        assert exec_result.stage_result.status == StageStatus.SUCCESS
        reports = exec_result.context.get(IntelligenceArtifactKey.REPORTS.value)
        assert isinstance(reports, list)
        assert len(reports) == 0

    def test_deterministic_replay(self, config_dir):
        ctx = _build_execution_context(config_dir)

        def1 = create_intelligence_pipeline(_make_intelligence_stages())
        def2 = create_intelligence_pipeline(_make_intelligence_stages())
        runner1 = PipelineRunner()
        runner2 = PipelineRunner()

        res1 = runner1.run(def1, ctx)
        res2 = runner2.run(def2, ctx)

        assert res1.to_dict() == res2.to_dict()
        assert res1.to_json() == res2.to_json()

    def test_immutability_of_pipeline_outputs(self, intelligence_stages, execution_context):
        definition = create_intelligence_pipeline(intelligence_stages)
        runner = PipelineRunner()

        result = runner.run(definition, execution_context)

        with pytest.raises(dataclasses.FrozenInstanceError):
            result.pipeline_run_id = "MUTATED"
