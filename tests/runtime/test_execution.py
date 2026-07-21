"""Order Lifecycle Engine tests (P5.6).

Covers legal state transitions, illegal transition rejection, partial fills,
full fills, cancellation, replay reconstruction, immutable outputs, lifecycle history,
configuration validation, and an end-to-end integration test consuming a real
BrokerExecutionPlan produced by BrokerManager.
"""

from __future__ import annotations

import dataclasses
import json
from datetime import datetime, timedelta
from decimal import Decimal
from zoneinfo import ZoneInfo

import pytest

from athena.allocation import CapitalAllocationEngine
from athena.brokers import BrokerManager
from athena.config.loader import (
    load_allocation_config,
    load_broker_config,
    load_execution_config,
    load_order_planning_config,
    load_sizing_config,
)
from athena.config.models import ExecutionConfig, OrderLifecycleState
from athena.domain.decision import Decision, TradePlan
from athena.domain.enums import DecisionType, Direction
from athena.errors import ConfigError, LifecycleError
from athena.execution import OrderLifecycleEngine
from athena.orders import OrderPlanningEngine
from athena.portfolio import PortfolioConfig, PortfolioEngine
from athena.sizing import PositionSizingEngine

IST = ZoneInfo("Asia/Kolkata")
AS_OF = datetime(2026, 3, 2, 8, 30, tzinfo=IST)
T1 = AS_OF + timedelta(minutes=5)
T2 = AS_OF + timedelta(minutes=10)
T3 = AS_OF + timedelta(minutes=15)
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
        if dtype == DecisionType.TRADE
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
def broker_plan(config_dir):
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
    sz_plan = sz_eng.size_plan(alloc_plan, prices, as_of=AS_OF)

    ord_cfg = load_order_planning_config(config_dir)
    ord_eng = OrderPlanningEngine(ord_cfg)
    exec_plan = ord_eng.plan_execution(sz_plan, as_of=AS_OF)

    b_cfg = load_broker_config(config_dir)
    b_mgr = BrokerManager(b_cfg)
    return b_mgr.translate_plan(exec_plan, as_of=AS_OF)


class TestLifecycleTransitions:
    def test_legal_state_transitions(self, broker_plan):
        engine = OrderLifecycleEngine()
        state0 = engine.initialize_from_plan(broker_plan, as_of=AS_OF)
        req_infy = broker_plan.request_for("INFY")
        order_id = req_infy.request_id

        assert state0.summary.total_orders == 2
        assert state0.summary.active_orders == 2

        # CREATED -> ACCEPTED
        state1 = engine.record_event(order_id, OrderLifecycleState.ACCEPTED, as_of=T1)
        lc1 = engine.get_order_lifecycle(order_id)
        assert lc1.current_state is OrderLifecycleState.ACCEPTED

        # ACCEPTED -> SUBMITTED
        state2 = engine.record_event(order_id, OrderLifecycleState.SUBMITTED, as_of=T2)
        lc2 = engine.get_order_lifecycle(order_id)
        assert lc2.current_state is OrderLifecycleState.SUBMITTED

        # SUBMITTED -> FILLED
        state3 = engine.record_event(
            order_id,
            OrderLifecycleState.FILLED,
            as_of=T3,
            fill_quantity=Decimal("66"),
            fill_price=Decimal("1500.00"),
        )
        lc3 = engine.get_order_lifecycle(order_id)
        assert lc3.current_state is OrderLifecycleState.FILLED
        assert lc3.filled_quantity == Decimal("66")
        assert lc3.avg_fill_price == Decimal("1500.00")
        assert state3.summary.filled_orders == 1

    def test_illegal_transition_rejection(self, broker_plan):
        engine = OrderLifecycleEngine()
        engine.initialize_from_plan(broker_plan, as_of=AS_OF)
        req_infy = broker_plan.request_for("INFY")
        order_id = req_infy.request_id

        # CREATED -> FILLED is illegal (must go through SUBMITTED)
        with pytest.raises(LifecycleError, match="Illegal state transition"):
            engine.record_event(
                order_id,
                OrderLifecycleState.FILLED,
                as_of=T1,
                fill_quantity=Decimal("66"),
                fill_price=Decimal("1500.00"),
            )

    def test_terminal_state_transition_rejection(self, broker_plan):
        engine = OrderLifecycleEngine()
        engine.initialize_from_plan(broker_plan, as_of=AS_OF)
        req_infy = broker_plan.request_for("INFY")
        order_id = req_infy.request_id

        engine.record_event(order_id, OrderLifecycleState.SUBMITTED, as_of=T1)
        engine.record_event(
            order_id,
            OrderLifecycleState.FILLED,
            as_of=T2,
            fill_quantity=Decimal("66"),
            fill_price=Decimal("1500.00"),
        )

        # Transitioning out of FILLED is illegal
        with pytest.raises(LifecycleError, match="Illegal state transition"):
            engine.record_event(order_id, OrderLifecycleState.SUBMITTED, as_of=T3)

    def test_partial_fills_and_weighted_avg_price(self, broker_plan):
        engine = OrderLifecycleEngine()
        engine.initialize_from_plan(broker_plan, as_of=AS_OF)
        req_infy = broker_plan.request_for("INFY")  # quantity 66
        order_id = req_infy.request_id

        engine.record_event(order_id, OrderLifecycleState.SUBMITTED, as_of=T1)

        # Partial fill 1: 30 shares at 1500
        engine.record_event(
            order_id,
            OrderLifecycleState.PARTIALLY_FILLED,
            as_of=T2,
            fill_quantity=Decimal("30"),
            fill_price=Decimal("1500.00"),
        )
        lc1 = engine.get_order_lifecycle(order_id)
        assert lc1.current_state is OrderLifecycleState.PARTIALLY_FILLED
        assert lc1.filled_quantity == Decimal("30")
        assert lc1.avg_fill_price == Decimal("1500.00")

        # Partial fill 2: 36 shares at 1510 (completes order -> auto-promotes to FILLED)
        engine.record_event(
            order_id,
            OrderLifecycleState.PARTIALLY_FILLED,
            as_of=T3,
            fill_quantity=Decimal("36"),
            fill_price=Decimal("1510.00"),
        )
        lc2 = engine.get_order_lifecycle(order_id)
        assert lc2.current_state is OrderLifecycleState.FILLED
        assert lc2.filled_quantity == Decimal("66")
        # Weighted avg: (30*1500 + 36*1510) / 66 = (45000 + 54360) / 66 = 99360 / 66 = 1505.45
        assert lc2.avg_fill_price == Decimal("1505.45")

    def test_cancellation(self, broker_plan):
        engine = OrderLifecycleEngine()
        engine.initialize_from_plan(broker_plan, as_of=AS_OF)
        req_infy = broker_plan.request_for("INFY")
        order_id = req_infy.request_id

        engine.record_event(order_id, OrderLifecycleState.SUBMITTED, as_of=T1)
        state = engine.record_event(order_id, OrderLifecycleState.CANCELLED, as_of=T2)

        lc = engine.get_order_lifecycle(order_id)
        assert lc.current_state is OrderLifecycleState.CANCELLED
        assert state.summary.cancelled_orders == 1


class TestReplayAndImmutability:
    def test_deterministic_replay(self, broker_plan):
        cfg = ExecutionConfig()

        eng1 = OrderLifecycleEngine(cfg)
        eng1.initialize_from_plan(broker_plan, as_of=AS_OF)
        req = broker_plan.request_for("INFY")
        eng1.record_event(req.request_id, OrderLifecycleState.SUBMITTED, as_of=T1)
        state1 = eng1.record_event(
            req.request_id, OrderLifecycleState.FILLED, as_of=T2, fill_quantity=Decimal("66"), fill_price=Decimal("1500.00")
        )

        eng2 = OrderLifecycleEngine(cfg)
        eng2.initialize_from_plan(broker_plan, as_of=AS_OF)
        eng2.record_event(req.request_id, OrderLifecycleState.SUBMITTED, as_of=T1)
        state2 = eng2.record_event(
            req.request_id, OrderLifecycleState.FILLED, as_of=T2, fill_quantity=Decimal("66"), fill_price=Decimal("1500.00")
        )

        assert state1.to_dict() == state2.to_dict()
        assert state1.to_json() == state2.to_json()

    def test_immutable_outputs(self, broker_plan):
        engine = OrderLifecycleEngine()
        state = engine.initialize_from_plan(broker_plan, as_of=AS_OF)

        with pytest.raises(dataclasses.FrozenInstanceError):
            state.state_id = "MUTATED"

        req = broker_plan.request_for("INFY")
        lc = engine.get_order_lifecycle(req.request_id)
        with pytest.raises(dataclasses.FrozenInstanceError):
            lc.current_state = OrderLifecycleState.FILLED

    def test_append_only_history(self, broker_plan):
        engine = OrderLifecycleEngine()
        engine.initialize_from_plan(broker_plan, as_of=AS_OF)
        req = broker_plan.request_for("INFY")
        engine.record_event(req.request_id, OrderLifecycleState.SUBMITTED, as_of=T1)

        hist = engine.history
        assert len(hist.records) == 2
        with pytest.raises(dataclasses.FrozenInstanceError):
            hist.records = ()


class TestConfigValidation:
    def test_unknown_key_rejected(self):
        with pytest.raises(Exception, match=r"Extra inputs|extra"):
            ExecutionConfig.model_validate({"bogus": 1})

    def test_production_config_loads(self, config_dir):
        cfg = load_execution_config(config_dir)
        assert cfg.allow_partial_fills is True
        assert cfg.enforce_strict_transitions is True

    def test_missing_config_fails_loudly(self, tmp_path):
        with pytest.raises(ConfigError):
            load_execution_config(tmp_path)


class TestEndToEndIntegration:
    def test_broker_execution_plan_driving_order_lifecycle(self, config_dir):
        """Integration test: driving OrderLifecycleEngine using real BrokerExecutionPlan from BrokerManager."""
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

        b_cfg = load_broker_config(config_dir)
        b_mgr = BrokerManager(b_cfg)
        b_plan = b_mgr.translate_plan(exec_plan, as_of=AS_OF)

        lc_cfg = load_execution_config(config_dir)
        lc_eng = OrderLifecycleEngine(lc_cfg)
        state = lc_eng.initialize_from_plan(b_plan, as_of=AS_OF)

        assert state.broker_execution_plan_id == b_plan.broker_plan_id
        assert state.summary.total_orders == 2
        assert state.summary.active_orders == 2

        req_infy = b_plan.request_for("INFY")
        req_tcs = b_plan.request_for("TCS")

        lc_eng.record_event(req_infy.request_id, OrderLifecycleState.SUBMITTED, as_of=T1)
        lc_eng.record_event(
            req_infy.request_id,
            OrderLifecycleState.FILLED,
            as_of=T2,
            fill_quantity=Decimal("66"),
            fill_price=Decimal("1500.00"),
        )

        lc_eng.record_event(req_tcs.request_id, OrderLifecycleState.SUBMITTED, as_of=T1)
        lc_eng.record_event(req_tcs.request_id, OrderLifecycleState.CANCELLED, as_of=T3)

        final_state = lc_eng.current_state
        assert final_state.summary.filled_orders == 1
        assert final_state.summary.cancelled_orders == 1
        assert final_state.summary.active_orders == 0
        assert final_state.summary.total_filled_quantity == Decimal("66")
        assert final_state.summary.total_filled_value == Decimal("99000.00")
