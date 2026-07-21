"""Broker Abstraction Layer tests (P5.5).

Covers capability validation, supported order types, unsupported capability rejection,
broker request and mock response generation, deterministic replay, immutable outputs,
broker history, configuration validation, and an end-to-end integration test
consuming a real ExecutionPlan produced by OrderPlanningEngine.
"""

from __future__ import annotations

import dataclasses
import json
from datetime import datetime, timedelta
from decimal import Decimal
from zoneinfo import ZoneInfo

import pytest

from athena.allocation import CapitalAllocationEngine
from athena.brokers import (
    BrokerCapabilities,
    BrokerDefinition,
    BrokerManager,
)
from athena.config.loader import (
    load_allocation_config,
    load_broker_config,
    load_order_planning_config,
    load_sizing_config,
)
from athena.config.models import BrokerConfig, OrderAction, OrderType, TimeInForce
from athena.domain.decision import Decision, TradePlan
from athena.domain.enums import DecisionType, Direction
from athena.errors import BrokerError, ConfigError
from athena.orders import OrderPlanningEngine
from athena.portfolio import PortfolioConfig, PortfolioEngine
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
def execution_plan(config_dir):
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
    return ord_eng.plan_execution(sz_plan, as_of=AS_OF)


class TestBrokerTranslationAndCapabilities:
    def test_canonical_translation(self, execution_plan):
        mgr = BrokerManager()
        b_plan = mgr.translate_plan(execution_plan, as_of=AS_OF)

        assert b_plan.broker_id == "paper_broker"
        assert b_plan.summary.accepted_count == 2
        assert b_plan.summary.total_requests == 2

        req_infy = b_plan.request_for("INFY")
        assert req_infy.action is OrderAction.BUY
        assert req_infy.order_type is OrderType.LIMIT
        assert req_infy.quantity == Decimal("66")
        assert req_infy.time_in_force is TimeInForce.DAY
        assert req_infy.status == "ACCEPTED"

    def test_unsupported_order_type_rejection(self, execution_plan):
        # Broker that supports ONLY MARKET orders
        limited_caps = BrokerCapabilities(
            supported_order_types=(OrderType.MARKET,),
            supports_fractional=True,
            supports_shorting=True,
            supported_time_in_force=(TimeInForce.DAY,),
        )
        mgr = BrokerManager()
        mgr.register_broker(
            BrokerDefinition("limit_only", "Market Only Broker", limited_caps)
        )

        # Execution plan contains LIMIT orders -> status should be REJECTED_UNSUPPORTED_ORDER_TYPE
        b_plan = mgr.translate_plan(execution_plan, broker_id="limit_only", as_of=AS_OF)
        assert b_plan.summary.rejected_count == 2
        req = b_plan.request_for("INFY")
        assert req.status == "REJECTED_UNSUPPORTED_ORDER_TYPE"

    def test_unsupported_fractional_rejection(self, config_dir):
        p_cfg = PortfolioConfig(initial_cash=Decimal("1000000.00"))
        p_eng = PortfolioEngine(p_cfg, initial_as_of=AS_OF)
        p_snap = p_eng.current_snapshot

        alloc_cfg = load_allocation_config(config_dir)
        alloc_eng = CapitalAllocationEngine(alloc_cfg)
        alloc_plan = alloc_eng.allocate(p_snap, [_decision("INFY")], as_of=AS_OF)

        # Force fractional sizing model
        sz_cfg = load_sizing_config(config_dir)
        sz_cfg.default_model = "FRACTIONAL"
        sz_eng = PositionSizingEngine(sz_cfg)
        sz_plan = sz_eng.size_plan(alloc_plan, {"INFY": Decimal("1500.00")}, as_of=AS_OF)

        ord_cfg = load_order_planning_config(config_dir)
        ord_eng = OrderPlanningEngine(ord_cfg)
        exec_plan = ord_eng.plan_execution(sz_plan, as_of=AS_OF)

        # Broker that does NOT support fractional trading
        no_frac_caps = BrokerCapabilities(
            supported_order_types=(OrderType.LIMIT,),
            supports_fractional=False,
            supported_time_in_force=(TimeInForce.DAY,),
        )
        mgr = BrokerManager()
        mgr.register_broker(
            BrokerDefinition("no_frac", "No Fractional Broker", no_frac_caps)
        )

        b_plan = mgr.translate_plan(exec_plan, broker_id="no_frac", as_of=AS_OF)
        req = b_plan.request_for("INFY")
        assert req.status == "REJECTED_UNSUPPORTED_FRACTIONAL"

    def test_unsupported_time_in_force_fails_loudly(self, execution_plan):
        mgr = BrokerManager()
        with pytest.raises(BrokerError, match="does not support TimeInForce"):
            mgr.translate_plan(execution_plan, as_of=AS_OF, time_in_force=TimeInForce.GTC)


class TestMockResponsesAndRegistration:
    def test_create_mock_response(self, execution_plan):
        mgr = BrokerManager()
        b_plan = mgr.translate_plan(execution_plan, as_of=AS_OF)
        req_infy = b_plan.request_for("INFY")

        resp = mgr.create_mock_response(req_infy, success=True, message="Executed on mock exchange")
        assert resp.request_id == req_infy.request_id
        assert resp.broker_id == "paper_broker"
        assert resp.success is True
        assert resp.broker_order_ref == f"mock-ref-{req_infy.request_id}"

    def test_unregistered_broker_fails_loudly(self, execution_plan):
        mgr = BrokerManager()
        with pytest.raises(BrokerError, match="is not registered"):
            mgr.translate_plan(execution_plan, broker_id="unknown_broker", as_of=AS_OF)

    def test_disabled_broker_fails_loudly(self, execution_plan):
        disabled_def = BrokerDefinition(
            "disabled_broker", "Disabled", BrokerCapabilities(), enabled=False
        )
        mgr = BrokerManager()
        mgr.register_broker(disabled_def)

        with pytest.raises(BrokerError, match="is disabled"):
            mgr.translate_plan(execution_plan, broker_id="disabled_broker", as_of=AS_OF)


class TestReplayAndImmutability:
    def test_deterministic_replay(self, execution_plan):
        cfg = BrokerConfig()
        eng1 = BrokerManager(cfg)
        plan1 = eng1.translate_plan(execution_plan, as_of=AS_OF)

        eng2 = BrokerManager(cfg)
        plan2 = eng2.translate_plan(execution_plan, as_of=AS_OF)

        assert plan1.to_dict() == plan2.to_dict()
        assert plan1.to_json() == plan2.to_json()

    def test_immutable_outputs(self, execution_plan):
        mgr = BrokerManager()
        b_plan = mgr.translate_plan(execution_plan, as_of=AS_OF)

        with pytest.raises(dataclasses.FrozenInstanceError):
            b_plan.broker_plan_id = "MUTATED"

        req = b_plan.request_for("INFY")
        with pytest.raises(dataclasses.FrozenInstanceError):
            req.status = "MUTATED"

    def test_append_only_history(self, execution_plan):
        mgr = BrokerManager()
        mgr.translate_plan(execution_plan, as_of=AS_OF)
        mgr.translate_plan(execution_plan, as_of=DAY2)

        hist = mgr.history
        assert len(hist.records) == 2
        with pytest.raises(dataclasses.FrozenInstanceError):
            hist.records = ()


class TestConfigValidation:
    def test_unknown_key_rejected(self):
        with pytest.raises(Exception, match=r"Extra inputs|extra"):
            BrokerConfig.model_validate({"bogus": 1})

    def test_production_config_loads(self, config_dir):
        cfg = load_broker_config(config_dir)
        assert cfg.default_broker_id == "paper_broker"
        assert cfg.default_time_in_force == TimeInForce.DAY

    def test_missing_config_fails_loudly(self, tmp_path):
        with pytest.raises(ConfigError):
            load_broker_config(tmp_path)


class TestEndToEndIntegration:
    def test_execution_plan_driving_broker_translation(self, config_dir):
        """Integration test: driving BrokerManager using real ExecutionPlan from OrderPlanningEngine."""
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

        assert b_plan.execution_plan_id == exec_plan.plan_id
        assert b_plan.summary.accepted_count == 2
        assert b_plan.summary.total_quantity == Decimal("99")
        assert b_plan.references.execution_plan_id == exec_plan.plan_id

        req_infy = b_plan.request_for("INFY")
        assert req_infy.broker_id == "paper_broker"
        assert req_infy.action is OrderAction.BUY
        assert req_infy.quantity == Decimal("66")
        assert req_infy.limit_price == Decimal("1500.00")
        assert req_infy.time_in_force is TimeInForce.DAY
        assert req_infy.status == "ACCEPTED"
