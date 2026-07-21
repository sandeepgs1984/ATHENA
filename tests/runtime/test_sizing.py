"""Position Sizing Engine tests (P5.3).

Covers whole-share sizing, fractional unit sizing, rounding policies (round down, round up),
precision handling, zero allocation handling, zero/invalid price handling, deterministic replay,
immutable outputs, sizing history, configuration validation, and an end-to-end integration test
consuming a real AllocationPlan produced by CapitalAllocationEngine.
"""

from __future__ import annotations

import dataclasses
import json
from datetime import datetime, timedelta
from decimal import Decimal
from zoneinfo import ZoneInfo

import pytest

from athena.allocation import CapitalAllocationEngine
from athena.config.loader import load_allocation_config, load_sizing_config
from athena.config.models import RoundingMode, SizingConfig, SizingModel
from athena.domain.decision import Decision, TradePlan
from athena.domain.enums import DecisionType, Direction
from athena.errors import ConfigError, SizingError
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
def allocation_plan(config_dir):
    p_cfg = PortfolioConfig(initial_cash=Decimal("1000000.00"))
    p_eng = PortfolioEngine(p_cfg, initial_as_of=AS_OF)
    p_snap = p_eng.current_snapshot

    alloc_cfg = load_allocation_config(config_dir)
    alloc_eng = CapitalAllocationEngine(alloc_cfg)

    opps = [_decision("INFY"), _decision("TCS")]
    return alloc_eng.allocate(p_snap, opps, as_of=AS_OF)


class TestSizingModelsAndRounding:
    def test_whole_share_round_down(self, allocation_plan):
        # INFY allocated: 100,000. Price: 1500.00 -> 100,000 / 1500 = 66.6666... -> 66 shares
        # Cost: 66 * 1500 = 99,000.00
        cfg = SizingConfig(
            default_model=SizingModel.WHOLE_SHARE,
            default_rounding=RoundingMode.ROUND_DOWN,
        )
        engine = PositionSizingEngine(cfg)
        prices = {"INFY": Decimal("1500.00"), "TCS": Decimal("3200.00")}

        plan = engine.size_plan(allocation_plan, prices, as_of=AS_OF)
        sz_infy = plan.size_for("INFY")
        assert sz_infy.quantity == Decimal("66")
        assert sz_infy.actual_cost == Decimal("99000.00")
        assert sz_infy.status == "SIZED"

    def test_whole_share_round_up(self, allocation_plan):
        # INFY allocated: 100,000. Price: 1500.00 -> ceil(66.6666...) -> 67 shares
        # Cost: 67 * 1500 = 100,500.00
        cfg = SizingConfig(
            default_model=SizingModel.WHOLE_SHARE,
            default_rounding=RoundingMode.ROUND_UP,
        )
        engine = PositionSizingEngine(cfg)
        prices = {"INFY": Decimal("1500.00"), "TCS": Decimal("3200.00")}

        plan = engine.size_plan(allocation_plan, prices, as_of=AS_OF)
        sz_infy = plan.size_for("INFY")
        assert sz_infy.quantity == Decimal("67")
        assert sz_infy.actual_cost == Decimal("100500.00")

    def test_fractional_sizing(self, allocation_plan):
        # INFY allocated: 100,000. Price: 1500.00 -> 100000 / 1500 = 66.666666...
        # Precision: 4 -> 66.6666
        cfg = SizingConfig(
            default_model=SizingModel.FRACTIONAL,
            default_rounding=RoundingMode.ROUND_DOWN,
            decimal_precision=4,
        )
        engine = PositionSizingEngine(cfg)
        prices = {"INFY": Decimal("1500.00"), "TCS": Decimal("3200.00")}

        plan = engine.size_plan(allocation_plan, prices, as_of=AS_OF)
        sz_infy = plan.size_for("INFY")
        assert sz_infy.quantity == Decimal("66.6666")
        # 66.6666 * 1500 = 99999.90
        assert sz_infy.actual_cost == Decimal("99999.90")


class TestEdgeCasesAndPrices:
    def test_zero_allocation_handling(self, config_dir):
        p_cfg = PortfolioConfig(initial_cash=Decimal("1000000.00"))
        p_eng = PortfolioEngine(p_cfg, initial_as_of=AS_OF)
        p_snap = p_eng.current_snapshot

        # Opp with NO_TRADE decision type -> 0 allocation
        alloc_cfg = load_allocation_config(config_dir)
        alloc_eng = CapitalAllocationEngine(alloc_cfg)
        alloc_plan = alloc_eng.allocate(p_snap, [_decision("INFY", dtype=DecisionType.NO_TRADE)], as_of=AS_OF)

        engine = PositionSizingEngine()
        prices = {"INFY": Decimal("1500.00")}
        plan = engine.size_plan(alloc_plan, prices, as_of=AS_OF)

        sz = plan.size_for("INFY")
        assert sz.quantity == Decimal("0")
        assert sz.actual_cost == Decimal("0.00")
        assert sz.status == "ZERO_ALLOCATION"

    def test_missing_price_handling(self, allocation_plan):
        engine = PositionSizingEngine()
        # TCS price missing from mapping
        prices = {"INFY": Decimal("1500.00")}
        plan = engine.size_plan(allocation_plan, prices, as_of=AS_OF)

        sz_tcs = plan.size_for("TCS")
        assert sz_tcs.quantity == Decimal("0")
        assert sz_tcs.status == "REJECTED_ZERO_PRICE"

    def test_size_amount_helper(self):
        engine = PositionSizingEngine()
        sz = engine.size_amount(Decimal("50000.00"), Decimal("1000.00"), "INFY", as_of=AS_OF)
        assert sz.quantity == Decimal("50")
        assert sz.actual_cost == Decimal("50000.00")
        assert sz.status == "SIZED"


class TestReplayAndImmutability:
    def test_deterministic_replay(self, allocation_plan):
        cfg = SizingConfig(default_model=SizingModel.WHOLE_SHARE)
        prices = {"INFY": Decimal("1500.00"), "TCS": Decimal("3200.00")}

        eng1 = PositionSizingEngine(cfg)
        plan1 = eng1.size_plan(allocation_plan, prices, as_of=AS_OF)

        eng2 = PositionSizingEngine(cfg)
        plan2 = eng2.size_plan(allocation_plan, prices, as_of=AS_OF)

        assert plan1.to_dict() == plan2.to_dict()
        assert plan1.to_json() == plan2.to_json()

    def test_immutable_outputs(self, allocation_plan):
        engine = PositionSizingEngine()
        prices = {"INFY": Decimal("1500.00")}
        plan = engine.size_plan(allocation_plan, prices, as_of=AS_OF)

        with pytest.raises(dataclasses.FrozenInstanceError):
            plan.plan_id = "MUTATED"

        sz = plan.size_for("INFY")
        with pytest.raises(dataclasses.FrozenInstanceError):
            sz.quantity = Decimal("999")

    def test_append_only_history(self, allocation_plan):
        engine = PositionSizingEngine()
        prices = {"INFY": Decimal("1500.00"), "TCS": Decimal("3200.00")}

        engine.size_plan(allocation_plan, prices, as_of=AS_OF)
        engine.size_plan(allocation_plan, prices, as_of=DAY2)

        hist = engine.history
        assert len(hist.records) == 2
        with pytest.raises(dataclasses.FrozenInstanceError):
            hist.records = ()


class TestConfigValidation:
    def test_unknown_key_rejected(self):
        with pytest.raises(Exception, match=r"Extra inputs|extra"):
            SizingConfig.model_validate({"bogus": 1})

    def test_negative_precision_rejected(self):
        with pytest.raises(Exception, match="decimal_precision must be >= 0"):
            SizingConfig.model_validate({"decimal_precision": -1})

    def test_production_config_loads(self, config_dir):
        cfg = load_sizing_config(config_dir)
        assert cfg.default_model == SizingModel.WHOLE_SHARE
        assert cfg.default_rounding == RoundingMode.ROUND_DOWN

    def test_missing_config_fails_loudly(self, tmp_path):
        with pytest.raises(ConfigError):
            load_sizing_config(tmp_path)


class TestEndToEndIntegration:
    def test_allocation_plan_driving_sizing(self, config_dir):
        """Integration test: driving PositionSizingEngine using real AllocationPlan from CapitalAllocationEngine."""
        p_cfg = PortfolioConfig(initial_cash=Decimal("1000000.00"))
        p_eng = PortfolioEngine(p_cfg, initial_as_of=AS_OF)
        p_snap = p_eng.current_snapshot

        alloc_cfg = load_allocation_config(config_dir)
        alloc_eng = CapitalAllocationEngine(alloc_cfg)
        alloc_plan = alloc_eng.allocate(p_snap, [_decision("INFY"), _decision("TCS")], as_of=AS_OF)

        sz_cfg = load_sizing_config(config_dir)
        sz_eng = PositionSizingEngine(sz_cfg)

        prices = {"INFY": Decimal("1500.00"), "TCS": Decimal("3000.00")}
        sz_plan = sz_eng.size_plan(alloc_plan, prices, as_of=AS_OF)

        assert sz_plan.allocation_plan_id == alloc_plan.plan_id
        assert sz_plan.summary.sized_count == 2
        # INFY: 100,000 / 1500 = 66 shares -> cost 99,000
        # TCS: 100,000 / 3000 = 33 shares -> cost 99,000
        assert sz_plan.size_for("INFY").quantity == Decimal("66")
        assert sz_plan.size_for("TCS").quantity == Decimal("33")
        assert sz_plan.summary.total_actual_cost == Decimal("198000.00")
        assert sz_plan.references.allocation_plan_id == alloc_plan.plan_id
