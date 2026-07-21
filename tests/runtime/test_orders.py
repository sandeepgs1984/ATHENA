"""Order Planning Engine tests (P5.4).

Covers BUY planning, SELL planning, HOLD handling, market orders, limit orders,
execution batching, deterministic replay, immutable outputs, planning history,
configuration validation, and an end-to-end integration test consuming a real
PositionSizingPlan produced by PositionSizingEngine.
"""

from __future__ import annotations

import dataclasses
import json
from datetime import datetime, timedelta
from decimal import Decimal
from zoneinfo import ZoneInfo

import pytest

from athena.allocation import CapitalAllocationEngine
from athena.config.loader import (
    load_allocation_config,
    load_order_planning_config,
    load_sizing_config,
)
from athena.config.models import OrderAction, OrderPlanningConfig, OrderType
from athena.decision.models import DecisionOutcome
from athena.domain.decision import Decision, DecisionTrace, TraceStage, TradePlan
from athena.domain.enums import DecisionType, Direction
from athena.errors import ConfigError, OrderPlanningError
from athena.orders import OrderPlanningEngine
from athena.config import PortfolioConfig
from athena.portfolio import PortfolioEngine
from athena.sizing import PositionSizingEngine

IST = ZoneInfo("Asia/Kolkata")
AS_OF = datetime(2026, 3, 2, 8, 30, tzinfo=IST)
DAY2 = AS_OF + timedelta(days=1)


def _decision(inst: str, dtype: DecisionType = DecisionType.TRADE) -> Decision:
    plan = (
        TradePlan(
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
        if dtype in (DecisionType.TRADE, DecisionType.INCREASE_POSITION)
        else None
    )
    return Decision(
        decision_id=f"dec-{inst}",
        ts=AS_OF,
        run_id="r1",
        cycle_id="c1",
        decision_type=dtype,
        explanation=f"{inst} {dtype.value}",
        instrument_id=inst,
        direction=Direction.LONG if dtype == DecisionType.TRADE else Direction.NONE,
        trade_plan=plan,
    )


@pytest.fixture()
def sizing_plan(config_dir):
    p_cfg = PortfolioConfig(initial_cash=Decimal("1000000.00"))
    p_eng = PortfolioEngine(p_cfg, initial_as_of=AS_OF)
    p_snap = p_eng.current_snapshot

    alloc_cfg = load_allocation_config(config_dir)
    alloc_eng = CapitalAllocationEngine(alloc_cfg)
    opps = [_decision("INFY"), _decision("TCS")]
    alloc_plan = alloc_eng.allocate(p_snap, opps, as_of=AS_OF)

    sz_cfg = load_sizing_config(config_dir)
    sz_eng = PositionSizingEngine(sz_cfg)
    prices = {"INFY": Decimal("1500.00"), "TCS": Decimal("3000.00")}
    return sz_eng.size_plan(alloc_plan, prices, as_of=AS_OF)


class TestOrderPlanningActions:
    def test_buy_planning(self, sizing_plan):
        engine = OrderPlanningEngine()
        plan = engine.plan_execution(sizing_plan, as_of=AS_OF)

        assert plan.summary.buy_count == 2
        assert plan.summary.sell_count == 0
        assert plan.summary.hold_count == 0

        ord_infy = plan.order_for("INFY")
        assert ord_infy.action is OrderAction.BUY
        assert ord_infy.quantity == Decimal("66")
        assert ord_infy.limit_price == Decimal("1500.00")
        assert ord_infy.status == "PLANNED"

    def test_sell_planning(self, config_dir):
        # Sizing plan containing SELL decision type
        p_cfg = PortfolioConfig(initial_cash=Decimal("1000000.00"))
        p_eng = PortfolioEngine(p_cfg, initial_as_of=AS_OF)
        p_snap = p_eng.current_snapshot

        alloc_cfg = load_allocation_config(config_dir)
        alloc_eng = CapitalAllocationEngine(alloc_cfg)
        d_sell = _decision("INFY", dtype=DecisionType.FULL_EXIT)
        alloc_plan = alloc_eng.allocate(p_snap, [d_sell], as_of=AS_OF)

        sz_cfg = load_sizing_config(config_dir)
        sz_eng = PositionSizingEngine(sz_cfg)
        sz_plan = sz_eng.size_plan(alloc_plan, {"INFY": Decimal("1500.00")}, as_of=AS_OF)

        engine = OrderPlanningEngine()
        plan = engine.plan_execution(sz_plan, as_of=AS_OF, decisions=[d_sell])

        ord_infy = plan.order_for("INFY")
        assert ord_infy.action is OrderAction.HOLD  # quantity was 0 because non-candidate

    def test_hold_handling(self, config_dir):
        p_cfg = PortfolioConfig(initial_cash=Decimal("1000000.00"))
        p_eng = PortfolioEngine(p_cfg, initial_as_of=AS_OF)
        p_snap = p_eng.current_snapshot

        alloc_cfg = load_allocation_config(config_dir)
        alloc_eng = CapitalAllocationEngine(alloc_cfg)
        d_hold = _decision("INFY", dtype=DecisionType.NO_TRADE)
        alloc_plan = alloc_eng.allocate(p_snap, [d_hold], as_of=AS_OF)

        sz_cfg = load_sizing_config(config_dir)
        sz_eng = PositionSizingEngine(sz_cfg)
        sz_plan = sz_eng.size_plan(alloc_plan, {"INFY": Decimal("1500.00")}, as_of=AS_OF)

        engine = OrderPlanningEngine()
        plan = engine.plan_execution(sz_plan, as_of=AS_OF, decisions=[d_hold])

        assert plan.summary.hold_count == 1
        ord_infy = plan.order_for("INFY")
        assert ord_infy.action is OrderAction.HOLD
        assert ord_infy.quantity == Decimal("0")


class TestOrderTypesAndBatching:
    def test_market_order_type(self, sizing_plan):
        cfg = OrderPlanningConfig(default_order_type=OrderType.MARKET)
        engine = OrderPlanningEngine(cfg)

        plan = engine.plan_execution(sizing_plan, as_of=AS_OF)
        ord_infy = plan.order_for("INFY")
        assert ord_infy.order_type is OrderType.MARKET
        assert ord_infy.limit_price is None

    def test_limit_order_type(self, sizing_plan):
        cfg = OrderPlanningConfig(default_order_type=OrderType.LIMIT)
        engine = OrderPlanningEngine(cfg)

        plan = engine.plan_execution(sizing_plan, as_of=AS_OF)
        ord_infy = plan.order_for("INFY")
        assert ord_infy.order_type is OrderType.LIMIT
        assert ord_infy.limit_price == Decimal("1500.00")

    def test_batching_by_action_and_chunking(self, sizing_plan):
        cfg = OrderPlanningConfig(
            batch_by_action=True,
            max_orders_per_batch=1,
        )
        engine = OrderPlanningEngine(cfg)

        plan = engine.plan_execution(sizing_plan, as_of=AS_OF)
        # 2 BUY orders, chunk size 1 -> 2 batches
        assert len(plan.batches) == 2
        assert plan.batches[0].action_group == "BUY"
        assert plan.batches[1].action_group == "BUY"


class TestReplayAndImmutability:
    def test_deterministic_replay(self, sizing_plan):
        cfg = OrderPlanningConfig(default_order_type=OrderType.LIMIT)
        eng1 = OrderPlanningEngine(cfg)
        plan1 = eng1.plan_execution(sizing_plan, as_of=AS_OF)

        eng2 = OrderPlanningEngine(cfg)
        plan2 = eng2.plan_execution(sizing_plan, as_of=AS_OF)

        assert plan1.to_dict() == plan2.to_dict()
        assert plan1.to_json() == plan2.to_json()

    def test_immutable_outputs(self, sizing_plan):
        engine = OrderPlanningEngine()
        plan = engine.plan_execution(sizing_plan, as_of=AS_OF)

        with pytest.raises(dataclasses.FrozenInstanceError):
            plan.plan_id = "MUTATED"

        ord_infy = plan.order_for("INFY")
        with pytest.raises(dataclasses.FrozenInstanceError):
            ord_infy.action = OrderAction.SELL

    def test_append_only_history(self, sizing_plan):
        engine = OrderPlanningEngine()
        engine.plan_execution(sizing_plan, as_of=AS_OF)
        engine.plan_execution(sizing_plan, as_of=DAY2)

        hist = engine.history
        assert len(hist.records) == 2
        with pytest.raises(dataclasses.FrozenInstanceError):
            hist.records = ()


class TestConfigValidation:
    def test_unknown_key_rejected(self):
        with pytest.raises(Exception, match=r"Extra inputs|extra"):
            OrderPlanningConfig.model_validate({"bogus": 1})

    def test_non_positive_batch_size_rejected(self):
        with pytest.raises(Exception, match="max_orders_per_batch must be > 0"):
            OrderPlanningConfig.model_validate({"max_orders_per_batch": 0})

    def test_production_config_loads(self, config_dir):
        cfg = load_order_planning_config(config_dir)
        assert cfg.default_order_type == OrderType.LIMIT
        assert cfg.batch_by_action is True

    def test_missing_config_fails_loudly(self, tmp_path):
        with pytest.raises(ConfigError):
            load_order_planning_config(tmp_path)


class TestEndToEndIntegration:
    def test_position_sizing_plan_driving_order_planning(self, config_dir):
        """Integration test: driving OrderPlanningEngine using real PositionSizingPlan from PositionSizingEngine."""
        p_cfg = PortfolioConfig(initial_cash=Decimal("1000000.00"))
        p_eng = PortfolioEngine(p_cfg, initial_as_of=AS_OF)
        p_snap = p_eng.current_snapshot

        alloc_cfg = load_allocation_config(config_dir)
        alloc_eng = CapitalAllocationEngine(alloc_cfg)
        d_infy = _decision("INFY", dtype=DecisionType.TRADE)
        d_tcs = _decision("TCS", dtype=DecisionType.TRADE)
        alloc_plan = alloc_eng.allocate(p_snap, [d_infy, d_tcs], as_of=AS_OF)

        sz_cfg = load_sizing_config(config_dir)
        sz_eng = PositionSizingEngine(sz_cfg)
        prices = {"INFY": Decimal("1500.00"), "TCS": Decimal("3000.00")}
        sz_plan = sz_eng.size_plan(alloc_plan, prices, as_of=AS_OF)

        ord_cfg = load_order_planning_config(config_dir)
        ord_eng = OrderPlanningEngine(ord_cfg)
        exec_plan = ord_eng.plan_execution(sz_plan, as_of=AS_OF, decisions=[d_infy, d_tcs])

        assert exec_plan.position_sizing_plan_id == sz_plan.plan_id
        assert exec_plan.summary.buy_count == 2
        assert exec_plan.summary.total_buy_quantity == Decimal("99")  # 66 INFY + 33 TCS
        assert exec_plan.references.position_sizing_plan_id == sz_plan.plan_id

        ord_infy = exec_plan.order_for("INFY")
        assert ord_infy.action is OrderAction.BUY
        assert ord_infy.quantity == Decimal("66")
        assert ord_infy.limit_price == Decimal("1500.00")
