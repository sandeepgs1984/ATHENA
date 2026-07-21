"""Execution Pipeline Registration runtime tests (P7.2).

Covers pipeline definition construction, topology validation, end-to-end execution
across all 8 registered execution stages, failure propagation, deterministic replay,
and artifact immutability.
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
from athena.domain.decision import Decision, TradePlan
from athena.domain.enums import DecisionType, Direction
from athena.errors import OrchestrationError
from athena.execution import OrderLifecycleEngine
from athena.orchestration import (
    BrokerTranslationStage,
    CapitalAllocationStage,
    DecisionsLoadStage,
    ExecutionArtifactKey,
    ExecutionStageId,
    OrderLifecycleStage,
    OrderPlanningStage,
    PipelineContext,
    PipelineDefinition,
    PipelineResult,
    PipelineRunner,
    PortfolioAnalyticsStage,
    PortfolioSnapshotStage,
    PositionSizingStage,
    StageStatus,
    create_execution_pipeline,
)
from athena.orders import OrderPlanningEngine
from athena.portfolio import PortfolioEngine
from athena.sizing import PositionSizingEngine

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


def _make_stages(config_dir) -> list:
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


@pytest.fixture()
def canonical_stages(config_dir):
    return _make_stages(config_dir)


class TestPipelineRegistrationAndValidation:
    def test_create_execution_pipeline_returns_definition(self, canonical_stages):
        definition = create_execution_pipeline(canonical_stages)

        assert isinstance(definition, PipelineDefinition)
        assert definition.metadata.definition_id == "execution-pipeline"
        assert definition.metadata.version == "1.0.0"
        assert len(definition.stages) == 8

        expected_ids = [
            ExecutionStageId.PORTFOLIO_SNAPSHOT.value,
            ExecutionStageId.DECISIONS_LOAD.value,
            ExecutionStageId.CAPITAL_ALLOCATION.value,
            ExecutionStageId.POSITION_SIZING.value,
            ExecutionStageId.ORDER_PLANNING.value,
            ExecutionStageId.BROKER_TRANSLATION.value,
            ExecutionStageId.ORDER_LIFECYCLE.value,
            ExecutionStageId.PORTFOLIO_ANALYTICS.value,
        ]
        assert [s.stage_id for s in definition.stages] == expected_ids

    def test_duplicate_stage_id_rejected(self, canonical_stages):
        duplicate_stages = [*canonical_stages, canonical_stages[0]]

        with pytest.raises(OrchestrationError, match="Duplicate stage_id"):
            create_execution_pipeline(duplicate_stages)

    def test_empty_stages_rejected(self):
        with pytest.raises(OrchestrationError, match="empty stages"):
            create_execution_pipeline([])


class TestExecutionPipelineRunner:
    def test_end_to_end_execution_pipeline_success(self, canonical_stages):
        definition = create_execution_pipeline(canonical_stages)
        runner = PipelineRunner()

        initial_context = PipelineContext(
            run_id="run-p72-001",
            as_of=T1,
            data={
                ExecutionArtifactKey.DECISIONS.value: [_decision("INFY")],
                ExecutionArtifactKey.CURRENT_PRICES.value: {"INFY": Decimal("1600.00")},
            },
        )

        result = runner.run(definition, initial_context)

        assert isinstance(result, PipelineResult)
        assert len(result.stages) == 8
        assert all(sr.status == StageStatus.SUCCESS for sr in result.stages)

        final_ctx = result.final_context
        assert final_ctx.get(ExecutionArtifactKey.PORTFOLIO_SNAPSHOT.value) is not None
        assert final_ctx.get(ExecutionArtifactKey.DECISIONS.value) is not None
        assert final_ctx.get(ExecutionArtifactKey.ALLOCATION_PLAN.value) is not None
        assert final_ctx.get(ExecutionArtifactKey.SIZING_PLAN.value) is not None
        assert final_ctx.get(ExecutionArtifactKey.EXECUTION_PLAN.value) is not None
        assert final_ctx.get(ExecutionArtifactKey.BROKER_PLAN.value) is not None
        assert final_ctx.get(ExecutionArtifactKey.EXECUTION_STATE.value) is not None
        assert final_ctx.get(ExecutionArtifactKey.PERFORMANCE_SNAPSHOT.value) is not None

    def test_failure_isolation_on_invalid_context(self, canonical_stages):
        definition = create_execution_pipeline(canonical_stages)
        runner = PipelineRunner()

        # Context missing DECISIONS -> DecisionsLoadStage will succeed with default dec,
        # but if we pass empty decisions list [], CapitalAllocationStage will fail cleanly.
        initial_context = PipelineContext(
            run_id="run-p72-fail",
            as_of=T1,
            data={ExecutionArtifactKey.DECISIONS.value: "INVALID_NOT_SEQUENCE"},
        )

        result = runner.run(definition, initial_context)

        # DecisionsLoadStage succeeds (loads decisions) or fails if invalid. CapitalAllocationStage fails.
        alloc_result = next(r for r in result.stages if r.stage_id == ExecutionStageId.CAPITAL_ALLOCATION.value)
        assert alloc_result.status == StageStatus.FAILED

    def test_deterministic_replay_and_json(self, config_dir):
        def1 = create_execution_pipeline(_make_stages(config_dir))
        def2 = create_execution_pipeline(_make_stages(config_dir))
        runner1 = PipelineRunner()
        runner2 = PipelineRunner()

        ctx = PipelineContext(
            run_id="run-replay",
            as_of=T1,
            data={
                ExecutionArtifactKey.DECISIONS.value: [_decision("INFY")],
                ExecutionArtifactKey.CURRENT_PRICES.value: {"INFY": Decimal("1600.00")},
            },
        )

        res1 = runner1.run(def1, ctx)
        res2 = runner2.run(def2, ctx)

        assert res1.to_dict() == res2.to_dict()
        assert res1.to_json() == res2.to_json()

    def test_immutability_of_pipeline_outputs(self, canonical_stages):
        definition = create_execution_pipeline(canonical_stages)
        runner = PipelineRunner()

        ctx = PipelineContext(run_id="run-immut", as_of=T1)
        res = runner.run(definition, ctx)

        with pytest.raises(dataclasses.FrozenInstanceError):
            res.pipeline_run_id = "MUTATED"
