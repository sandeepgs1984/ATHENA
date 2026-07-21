"""Pipeline Runner Integration runtime tests (P7.4).

Covers end-to-end system cycle execution across Execution Pipeline (P7.2),
symmetric contract validation (PipelineContract), Intelligence Pipeline (P7.3),
and Workspace Assembly (WorkspaceAssembler).

Tests explicit failure handling matrix, deterministic replayability, and immutability.
"""

from __future__ import annotations

import dataclasses
from datetime import datetime, timedelta
from decimal import Decimal
from zoneinfo import ZoneInfo

import pytest

from athena.allocation import CapitalAllocationEngine
from athena.analytics.portfolio import PortfolioAnalyticsEngine
from athena.brokers import BrokerManager
from athena.config import PortfolioConfig
from athena.config.loader import (
    load_allocation_config,
    load_broker_config,
    load_execution_config,
    load_order_planning_config,
    load_portfolio_analytics_config,
    load_sizing_config,
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
    EXECUTION_PIPELINE_CONTRACT,
    INTELLIGENCE_PIPELINE_CONTRACT,
    ExecutionArtifactKey,
    IntelligenceArtifactKey,
    PipelineContext,
    PipelineContract,
    PipelineCoordinator,
    PipelineRunner,
    PipelineStatus,
    SystemPipelineResult,
    SystemPipelineRunner,
    WorkspaceAssembler,
    create_execution_pipeline,
    create_intelligence_pipeline,
    validate_contract,
)
from athena.orchestration.stages import (
    BrokerTranslationStage,
    CapitalAllocationStage,
    DashboardStage,
    DecisionsLoadStage,
    ExplainabilityStage,
    ExportStage,
    MonitoringStage,
    OrderLifecycleStage,
    OrderPlanningStage,
    PortfolioAnalyticsStage,
    PortfolioSnapshotStage,
    PositionSizingStage,
    ReportingStage,
    TimelineStage,
)
from athena.orders import OrderPlanningEngine
from athena.portfolio import PortfolioEngine
from athena.reporting.engine import ReportingEngine
from athena.sizing import PositionSizingEngine
from athena.timeline.engine import TimelineAuditEngine

IST = ZoneInfo("Asia/Kolkata")
AS_OF = datetime(2026, 3, 2, 8, 30, tzinfo=IST)
T1 = AS_OF + timedelta(days=1)


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
        valid_until=T1,
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


def _make_intelligence_stages() -> list:
    return [
        ReportingStage(ReportingEngine()),
        ExplainabilityStage(ExplainabilityEngine()),
        DashboardStage(DashboardEngine()),
        MonitoringStage(OperationalMonitoringEngine()),
        TimelineStage(TimelineAuditEngine()),
        ExportStage(ExportPresentationEngine()),
    ]


@pytest.fixture()
def system_pipelines(config_dir):
    exec_def = create_execution_pipeline(_make_execution_stages(config_dir))
    intel_def = create_intelligence_pipeline(_make_intelligence_stages())
    return exec_def, intel_def


@pytest.fixture()
def initial_context():
    return PipelineContext(
        run_id="run-sys-001",
        as_of=T1,
        data={
            ExecutionArtifactKey.DECISIONS.value: [_decision("INFY")],
            ExecutionArtifactKey.CURRENT_PRICES.value: {"INFY": Decimal("1600.00")},
        },
    )


class TestPipelineContractAndValidation:
    def test_pipeline_contract_initialization(self):
        contract = PipelineContract(
            name="Test Contract",
            version="1.0.0",
            required_inputs=frozenset({"req_key"}),
            optional_inputs=frozenset({"opt_key"}),
            produced_outputs=frozenset({"out_key"}),
        )
        assert contract.name == "Test Contract"
        assert contract.version == "1.0.0"

    def test_overlapping_required_and_optional_inputs_rejected(self):
        with pytest.raises(ValueError, match="overlap"):
            PipelineContract(
                name="Bad Contract",
                version="1.0.0",
                required_inputs=frozenset({"key1"}),
                optional_inputs=frozenset({"key1"}),
            )

    def test_validate_contract_success_when_all_inputs_present(self, initial_context):
        # EXECUTION_PIPELINE_CONTRACT requires DECISIONS and CURRENT_PRICES
        validate_contract(EXECUTION_PIPELINE_CONTRACT, initial_context)

    def test_validate_contract_raises_orchestration_error_on_missing_key(self):
        ctx = PipelineContext(run_id="r1", as_of=T1, data={})
        with pytest.raises(OrchestrationError, match="missing or None"):
            validate_contract(EXECUTION_PIPELINE_CONTRACT, ctx)


class TestPipelineCoordinator:
    def test_coordinator_executes_valid_sequence(self, system_pipelines, initial_context):
        exec_def, intel_def = system_pipelines
        coordinator = PipelineCoordinator()

        pairs = [
            (exec_def, EXECUTION_PIPELINE_CONTRACT),
            (intel_def, INTELLIGENCE_PIPELINE_CONTRACT),
        ]

        runs, status, final_ctx = coordinator.execute_sequence(pairs, initial_context)

        assert status == PipelineStatus.SUCCESS
        assert len(runs) == 2
        assert final_ctx.get(IntelligenceArtifactKey.EXPORT_SNAPSHOT.value) is not None

    def test_coordinator_halts_on_contract_failure(self, system_pipelines):
        exec_def, _intel_def = system_pipelines
        coordinator = PipelineCoordinator()

        # Context missing DECISIONS -> EXECUTION_PIPELINE_CONTRACT validation will fail immediately
        empty_ctx = PipelineContext(run_id="r-empty", as_of=T1, data={})
        pairs = [(exec_def, EXECUTION_PIPELINE_CONTRACT)]

        with pytest.raises(OrchestrationError, match="validation failed"):
            coordinator.execute_sequence(pairs, empty_ctx)


class TestWorkspaceAssembler:
    def test_workspace_assembler_extracts_and_assembles(self, system_pipelines, initial_context):
        exec_def, intel_def = system_pipelines
        runner = PipelineRunner()

        exec_ctx = runner.run(exec_def, initial_context).final_context
        intel_ctx = runner.run(intel_def, exec_ctx).final_context

        assembler = WorkspaceAssembler()
        ws_snap = assembler.assemble(intel_ctx)

        assert ws_snap is not None
        assert ws_snap.summary.total_entries > 0


class TestSystemPipelineRunner:
    def test_end_to_end_system_cycle_success(self, system_pipelines, initial_context):
        exec_def, intel_def = system_pipelines
        system_runner = SystemPipelineRunner()

        result = system_runner.run_system_cycle(exec_def, intel_def, initial_context)

        assert isinstance(result, SystemPipelineResult)
        assert result.overall_status == PipelineStatus.SUCCESS
        assert len(result.pipeline_runs) == 2
        assert result.workspace_snapshot is not None
        assert result.workspace_snapshot.summary.total_entries > 0

    def test_execution_failure_terminates_early(self, config_dir, initial_context):
        # Build execution stages but force CapitalAllocationStage to fail cleanly by passing bad input
        stages = _make_execution_stages(config_dir)
        exec_def = create_execution_pipeline(stages)
        intel_def = create_intelligence_pipeline(_make_intelligence_stages())

        # Bad context with invalid DECISIONS type causes stage failure in CapitalAllocationStage
        bad_ctx = PipelineContext(
            run_id="run-bad-decisions",
            as_of=T1,
            data={
                ExecutionArtifactKey.DECISIONS.value: "NOT_A_SEQUENCE",
                ExecutionArtifactKey.CURRENT_PRICES.value: {"INFY": Decimal("1600.00")},
            },
        )

        system_runner = SystemPipelineRunner()
        result = system_runner.run_system_cycle(exec_def, intel_def, bad_ctx)

        assert result.overall_status == PipelineStatus.FAILED
        # Early exit: execution pipeline failed -> intelligence pipeline not run, workspace snapshot None
        assert len(result.pipeline_runs) == 1
        assert result.workspace_snapshot is None

    def test_workspace_failure_handled_gracefully(self, system_pipelines, initial_context, monkeypatch):
        exec_def, intel_def = system_pipelines
        system_runner = SystemPipelineRunner()

        # Monkeypatch WorkspaceAssembler.assemble to simulate a workspace assembly failure
        def mock_fail(ctx):
            raise RuntimeError("Simulated workspace assembly crash")

        monkeypatch.setattr(system_runner._workspace_assembler, "assemble", mock_fail)

        result = system_runner.run_system_cycle(exec_def, intel_def, initial_context)

        # Pipelines succeeded, but workspace assembly failed -> overall_status FAILED, snapshot None
        assert result.overall_status == PipelineStatus.FAILED
        assert len(result.pipeline_runs) == 2
        assert result.workspace_snapshot is None

    def test_deterministic_replay(self, config_dir, initial_context):
        exec_def1 = create_execution_pipeline(_make_execution_stages(config_dir))
        intel_def1 = create_intelligence_pipeline(_make_intelligence_stages())

        exec_def2 = create_execution_pipeline(_make_execution_stages(config_dir))
        intel_def2 = create_intelligence_pipeline(_make_intelligence_stages())

        runner1 = SystemPipelineRunner()
        runner2 = SystemPipelineRunner()

        res1 = runner1.run_system_cycle(exec_def1, intel_def1, initial_context)
        res2 = runner2.run_system_cycle(exec_def2, intel_def2, initial_context)

        assert res1.to_dict() == res2.to_dict()
        assert res1.to_json() == res2.to_json()


    def test_immutability_of_system_pipeline_result(self, system_pipelines, initial_context):
        exec_def, intel_def = system_pipelines
        system_runner = SystemPipelineRunner()

        result = system_runner.run_system_cycle(exec_def, intel_def, initial_context)

        with pytest.raises(dataclasses.FrozenInstanceError):
            result.run_id = "MUTATED"
