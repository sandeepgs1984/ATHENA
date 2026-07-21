"""Capital Allocation Engine tests (P5.2).

Covers fixed amount, fixed percentage, and equal weight allocation models;
cash reserve threshold enforcement; insufficient capital handling;
deterministic replay; immutable outputs; allocation history; configuration validation;
and an end-to-end integration test consuming a real PortfolioSnapshot from PortfolioEngine.
"""

from __future__ import annotations

import dataclasses
import json
from datetime import datetime, timedelta
from decimal import Decimal
from zoneinfo import ZoneInfo

import pytest

from athena.allocation import CapitalAllocationEngine
from athena.config.loader import load_allocation_config
from athena.config.models import AllocationConfig, AllocationModel
from athena.domain.decision import Decision, TradePlan
from athena.domain.enums import DecisionType, Direction
from athena.errors import ConfigError
from athena.portfolio import PortfolioConfig, PortfolioEngine

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
def portfolio_snap():
    p_cfg = PortfolioConfig(initial_cash=Decimal("1000000.00"))
    eng = PortfolioEngine(p_cfg, initial_as_of=AS_OF)
    return eng.current_snapshot


class TestAllocationPolicies:
    def test_fixed_percentage_allocation(self, portfolio_snap):
        # 10% of 10L = 100,000 per opportunity
        cfg = AllocationConfig(
            default_model=AllocationModel.FIXED_PERCENTAGE,
            fixed_percentage=Decimal("10.0"),
            min_cash_reserve_pct=Decimal("20.0"),  # Floor 200,000. Pool 800,000.
        )
        engine = CapitalAllocationEngine(cfg)
        opps = [_decision("INFY"), _decision("TCS")]

        plan = engine.allocate(portfolio_snap, opps, as_of=AS_OF)
        assert plan.summary.allocated_count == 2
        assert plan.summary.total_allocated_capital == Decimal("200000.00")
        assert plan.allocation_for("INFY").allocated_amount == Decimal("100000.00")
        assert plan.allocation_for("TCS").allocated_amount == Decimal("100000.00")
        assert plan.allocation_for("INFY").status == "ALLOCATED"

    def test_fixed_amount_allocation(self, portfolio_snap):
        cfg = AllocationConfig(
            default_model=AllocationModel.FIXED_AMOUNT,
            fixed_amount=Decimal("150000.00"),
            min_cash_reserve_pct=Decimal("20.0"),
        )
        engine = CapitalAllocationEngine(cfg)
        opps = [_decision("INFY"), _decision("TCS")]

        plan = engine.allocate(portfolio_snap, opps, as_of=AS_OF)
        assert plan.summary.total_allocated_capital == Decimal("300000.00")
        assert plan.allocation_for("INFY").allocated_amount == Decimal("150000.00")

    def test_equal_weight_allocation(self, portfolio_snap):
        # Pool: 1,000,000 - 200,000 (20% reserve) = 800,000.
        # 4 opportunities -> 800,000 / 4 = 200,000 per opportunity.
        cfg = AllocationConfig(
            default_model=AllocationModel.EQUAL_WEIGHT,
            min_cash_reserve_pct=Decimal("20.0"),
            max_opportunities=5,
        )
        engine = CapitalAllocationEngine(cfg)
        opps = [_decision("AAA"), _decision("BBB"), _decision("CCC"), _decision("DDD")]

        plan = engine.allocate(portfolio_snap, opps, as_of=AS_OF)
        assert plan.summary.allocated_count == 4
        assert plan.summary.total_allocated_capital == Decimal("800000.00")
        assert plan.allocation_for("AAA").allocated_amount == Decimal("200000.00")
        assert plan.allocation_for("DDD").allocated_amount == Decimal("200000.00")


class TestReserveThresholdAndCashLimits:
    def test_cash_reserve_floor_enforcement(self, portfolio_snap):
        # Initial cash: 1,000,000. 50% reserve = 500,000 floor. Pool: 500,000.
        # Fixed amount: 300,000.
        # Opp 1: 300,000 (rem pool: 200,000)
        # Opp 2: 200,000 (PARTIAL, rem pool: 0)
        # Opp 3: 0 (REJECTED_INSUFFICIENT_CASH)
        cfg = AllocationConfig(
            default_model=AllocationModel.FIXED_AMOUNT,
            fixed_amount=Decimal("300000.00"),
            min_cash_reserve_pct=Decimal("50.0"),
        )
        engine = CapitalAllocationEngine(cfg)
        opps = [_decision("AAA"), _decision("BBB"), _decision("CCC")]

        plan = engine.allocate(portfolio_snap, opps, as_of=AS_OF)
        assert plan.summary.allocated_count == 2
        assert plan.summary.rejected_count == 1
        assert plan.summary.total_allocated_capital == Decimal("500000.00")

        alloc_a = plan.allocation_for("AAA")
        alloc_b = plan.allocation_for("BBB")
        alloc_c = plan.allocation_for("CCC")

        assert alloc_a.status == "ALLOCATED" and alloc_a.allocated_amount == Decimal("300000.00")
        assert alloc_b.status == "PARTIAL" and alloc_b.allocated_amount == Decimal("200000.00")
        assert alloc_c.status == "REJECTED_INSUFFICIENT_CASH" and alloc_c.allocated_amount == Decimal("0.00")

    def test_max_opportunities_limit(self, portfolio_snap):
        cfg = AllocationConfig(
            default_model=AllocationModel.FIXED_AMOUNT,
            fixed_amount=Decimal("50000.00"),
            max_opportunities=2,
        )
        engine = CapitalAllocationEngine(cfg)
        opps = [_decision("AAA"), _decision("BBB"), _decision("CCC")]

        plan = engine.allocate(portfolio_snap, opps, as_of=AS_OF)
        assert plan.allocation_for("AAA").status == "ALLOCATED"
        assert plan.allocation_for("BBB").status == "ALLOCATED"
        assert plan.allocation_for("CCC").status == "REJECTED_MAX_OPPORTUNITIES"


class TestReplayAndImmutability:
    def test_deterministic_replay(self, portfolio_snap):
        cfg = AllocationConfig(default_model=AllocationModel.FIXED_PERCENTAGE)
        eng1 = CapitalAllocationEngine(cfg)
        plan1 = eng1.allocate(portfolio_snap, [_decision("INFY"), _decision("TCS")], as_of=AS_OF)

        eng2 = CapitalAllocationEngine(cfg)
        plan2 = eng2.allocate(portfolio_snap, [_decision("INFY"), _decision("TCS")], as_of=AS_OF)

        assert plan1.to_dict() == plan2.to_dict()
        assert plan1.to_json() == plan2.to_json()

    def test_immutable_outputs(self, portfolio_snap):
        engine = CapitalAllocationEngine()
        plan = engine.allocate(portfolio_snap, [_decision("INFY")], as_of=AS_OF)
        with pytest.raises(dataclasses.FrozenInstanceError):
            plan.plan_id = "MUTATED"

        alloc = plan.allocation_for("INFY")
        with pytest.raises(dataclasses.FrozenInstanceError):
            alloc.allocated_amount = Decimal("999.99")

    def test_append_only_history(self, portfolio_snap):
        engine = CapitalAllocationEngine()
        engine.allocate(portfolio_snap, [_decision("INFY")], as_of=AS_OF)
        engine.allocate(portfolio_snap, [_decision("TCS")], as_of=DAY2)

        hist = engine.history
        assert len(hist.records) == 2
        with pytest.raises(dataclasses.FrozenInstanceError):
            hist.records = ()


class TestConfigValidation:
    def test_unknown_key_rejected(self):
        with pytest.raises(Exception, match=r"Extra inputs|extra"):
            AllocationConfig.model_validate({"bogus": 1})

    def test_negative_values_rejected(self):
        with pytest.raises(Exception, match="must be >= 0"):
            AllocationConfig.model_validate({"fixed_amount": "-500.00"})

    def test_production_config_loads(self, config_dir):
        cfg = load_allocation_config(config_dir)
        assert cfg.default_model == AllocationModel.FIXED_PERCENTAGE
        assert cfg.min_cash_reserve_pct == Decimal("20.0")

    def test_missing_config_fails_loudly(self, tmp_path):
        with pytest.raises(ConfigError):
            load_allocation_config(tmp_path)


class TestEndToEndIntegration:
    def test_portfolio_snapshot_driving_allocation(self, config_dir):
        """Integration test: driving CapitalAllocationEngine using real PortfolioSnapshot from PortfolioEngine."""
        p_cfg = PortfolioConfig(initial_cash=Decimal("1000000.00"))
        p_engine = PortfolioEngine(p_cfg, initial_as_of=AS_OF)

        # Open one position to change cash state
        p_snap = p_engine.open_position("RELIANCE", 100, Decimal("2000.00"), as_of=AS_OF)
        # Remaining cash: available = 800,000. allocated = 200,000. total = 1,000,000.

        # Capital Allocation Engine
        alloc_cfg = load_allocation_config(config_dir)
        alloc_engine = CapitalAllocationEngine(alloc_cfg)

        opps = [_decision("INFY"), _decision("TCS")]
        plan = alloc_engine.allocate(p_snap, opps, as_of=AS_OF, strategy="breakout")

        assert plan.portfolio_snapshot_id == p_snap.snapshot_id
        # Total cash = 10L. Min 20% reserve = 200,000 floor.
        # Available cash = 800,000.
        # Allocatable pool = available cash - reserve floor = 800,000 - 200,000 = 600,000.
        # 10% of total cash (10L) = 100,000 per opportunity.
        # INFY gets 100,000, TCS gets 100,000. Total allocated: 200,000.
        assert plan.summary.total_allocated_capital == Decimal("200000.00")
        assert plan.allocation_for("INFY").allocated_amount == Decimal("100000.00")
        assert plan.allocation_for("TCS").allocated_amount == Decimal("100000.00")
        assert plan.references.portfolio_snapshot_id == p_snap.snapshot_id
