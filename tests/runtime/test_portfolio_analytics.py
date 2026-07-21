"""Portfolio Analytics & Performance Engine tests (P5.7).

Covers realized P&L, unrealized P&L, win/loss accounting, average gain/loss,
portfolio valuation, drawdown calculation, replay reconstruction, immutable outputs,
analytics history, configuration validation, and an end-to-end integration test
consuming a real ExecutionState produced by OrderLifecycleEngine.
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
    load_execution_config,
    load_order_planning_config,
    load_portfolio_analytics_config,
    load_sizing_config,
)
from athena.config.models import OrderLifecycleState, PortfolioAnalyticsConfig
from athena.domain.decision import Decision, TradePlan
from athena.domain.enums import DecisionType, Direction
from athena.errors import ConfigError, PortfolioAnalyticsError
from athena.execution import OrderLifecycleEngine
from athena.orders import OrderPlanningEngine
from athena.config import PortfolioConfig
from athena.portfolio import PortfolioEngine
from athena.sizing import PositionSizingEngine

IST = ZoneInfo("Asia/Kolkata")
AS_OF = datetime(2026, 3, 2, 8, 30, tzinfo=IST)
T1 = AS_OF + timedelta(days=5)
T2 = AS_OF + timedelta(days=10)
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
def full_pipeline_state(config_dir):
    p_cfg = PortfolioConfig(initial_cash=Decimal("1000000.00"))
    p_eng = PortfolioEngine(p_cfg, initial_as_of=AS_OF)
    p_eng.open_position("INFY", quantity=100, price=Decimal("1500.00"), as_of=AS_OF)
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
    b_plan = b_mgr.translate_plan(exec_plan, as_of=AS_OF)

    lc_cfg = load_execution_config(config_dir)
    lc_eng = OrderLifecycleEngine(lc_cfg)
    exec_state = lc_eng.initialize_from_plan(b_plan, as_of=AS_OF)

    return p_eng, p_snap, exec_state


class TestPortfolioAnalyticsMetrics:
    def test_unrealized_pnl_and_valuation(self, full_pipeline_state):
        p_eng, p_snap, exec_state = full_pipeline_state
        engine = PortfolioAnalyticsEngine()

        prices = {"INFY": Decimal("1600.00")}  # +100 gain per share * 100 shares = +10,000
        snap = engine.analyze(p_snap, exec_state, current_prices=prices, as_of=T1)

        perf = snap.portfolio_performance
        assert perf.unrealized_pnl == Decimal("10000.00")
        assert perf.realized_pnl == Decimal("0.00")
        assert perf.total_pnl == Decimal("10000.00")
        assert perf.gross_exposure == Decimal("160000.00")
        assert perf.net_exposure == Decimal("160000.00")

    def test_win_loss_accounting_and_realized_pnl(self):
        p_cfg = PortfolioConfig(initial_cash=Decimal("1000000.00"))
        p_eng = PortfolioEngine(p_cfg, initial_as_of=AS_OF)
        # Open and close INFY for a gain (+10,000)
        p_eng.open_position("INFY", quantity=100, price=Decimal("1500.00"), as_of=AS_OF)
        p_eng.close_position("INFY", Decimal("1600.00"), as_of=T1)

        # Open and close TCS for a loss (-5,000)
        p_eng.open_position("TCS", quantity=50, price=Decimal("3000.00"), as_of=T1)
        p_eng.close_position("TCS", Decimal("2900.00"), as_of=T2)

        engine = PortfolioAnalyticsEngine()
        snap = engine.analyze(p_eng.current_snapshot, as_of=T2)

        summary = snap.summary
        assert summary.total_trades == 2
        assert summary.winning_trades == 1
        assert summary.losing_trades == 1
        assert summary.win_rate_pct == Decimal("50.00")
        assert summary.avg_gain == Decimal("10000.00")
        assert summary.avg_loss == Decimal("5000.00")
        assert summary.win_loss_ratio == Decimal("2.00")

    def test_drawdown_calculation(self):
        p_cfg = PortfolioConfig(initial_cash=Decimal("1000000.00"))
        p_eng = PortfolioEngine(p_cfg, initial_as_of=AS_OF)
        engine = PortfolioAnalyticsEngine()

        # Step 1: Gain to 1,100,000 (new peak)
        p_eng.open_position("INFY", quantity=1000, price=Decimal("1000.00"), as_of=AS_OF)
        p_eng.close_position("INFY", Decimal("1100.00"), as_of=T1)
        snap1 = engine.analyze(p_eng.current_snapshot, as_of=T1)
        assert snap1.portfolio_performance.peak_portfolio_value == Decimal("1100000.00")
        assert snap1.portfolio_performance.drawdown == Decimal("0.00")

        # Step 2: Loss to 1,050,000 (50,000 drawdown from peak 1,100,000 -> 4.55% DD)
        p_eng.open_position("TCS", quantity=500, price=Decimal("2000.00"), as_of=T1)
        p_eng.close_position("TCS", Decimal("1900.00"), as_of=T2)
        snap2 = engine.analyze(p_eng.current_snapshot, as_of=T2)

        perf2 = snap2.portfolio_performance
        assert perf2.peak_portfolio_value == Decimal("1100000.00")
        assert perf2.drawdown == Decimal("50000.00")
        assert perf2.drawdown_pct == Decimal("4.55")
        assert perf2.max_drawdown_pct == Decimal("4.55")


class TestReplayAndImmutability:
    def test_deterministic_replay(self, full_pipeline_state):
        _, p_snap, exec_state = full_pipeline_state
        cfg = PortfolioAnalyticsConfig()

        eng1 = PortfolioAnalyticsEngine(cfg)
        snap1 = eng1.analyze(p_snap, exec_state, current_prices={"INFY": Decimal("1600.00")}, as_of=T1)

        eng2 = PortfolioAnalyticsEngine(cfg)
        snap2 = eng2.analyze(p_snap, exec_state, current_prices={"INFY": Decimal("1600.00")}, as_of=T1)

        assert snap1.to_dict() == snap2.to_dict()
        assert snap1.to_json() == snap2.to_json()

    def test_immutable_outputs(self, full_pipeline_state):
        _, p_snap, exec_state = full_pipeline_state
        engine = PortfolioAnalyticsEngine()
        snap = engine.analyze(p_snap, exec_state, as_of=T1)

        with pytest.raises(dataclasses.FrozenInstanceError):
            snap.snapshot_id = "MUTATED"

        with pytest.raises(dataclasses.FrozenInstanceError):
            snap.portfolio_performance.realized_pnl = Decimal("999999.00")

    def test_append_only_history(self, full_pipeline_state):
        _, p_snap, exec_state = full_pipeline_state
        engine = PortfolioAnalyticsEngine()
        engine.analyze(p_snap, exec_state, as_of=T1)
        engine.analyze(p_snap, exec_state, as_of=T2)

        hist = engine.history
        assert len(hist.records) == 2
        with pytest.raises(dataclasses.FrozenInstanceError):
            hist.records = ()


class TestConfigValidation:
    def test_unknown_key_rejected(self):
        with pytest.raises(Exception, match=r"Extra inputs|extra"):
            PortfolioAnalyticsConfig.model_validate({"bogus": 1})

    def test_negative_capital_rejected(self):
        with pytest.raises(Exception, match="must be >= 0"):
            PortfolioAnalyticsConfig.model_validate({"initial_capital": Decimal("-10.00")})

    def test_production_config_loads(self, config_dir):
        cfg = load_portfolio_analytics_config(config_dir)
        assert cfg.initial_capital == Decimal("1000000.00")
        assert cfg.risk_free_rate_pct == Decimal("6.00")

    def test_missing_config_fails_loudly(self, tmp_path):
        with pytest.raises(ConfigError):
            load_portfolio_analytics_config(tmp_path)


class TestEndToEndIntegration:
    def test_full_phase_5_pipeline_driving_portfolio_analytics(self, config_dir):
        """Integration test: driving PortfolioAnalyticsEngine through the entire Phase 5 pipeline!

        PortfolioEngine -> CapitalAllocationEngine -> PositionSizingEngine -> OrderPlanningEngine ->
        BrokerManager -> OrderLifecycleEngine -> PortfolioAnalyticsEngine.
        """
        # 1. Portfolio Engine
        p_cfg = PortfolioConfig(initial_cash=Decimal("1000000.00"))
        p_eng = PortfolioEngine(p_cfg, initial_as_of=AS_OF)
        p_eng.open_position("INFY", quantity=100, price=Decimal("1500.00"), as_of=AS_OF)
        p_snap = p_eng.current_snapshot

        # 2. Allocation
        alloc_cfg = load_allocation_config(config_dir)
        alloc_eng = CapitalAllocationEngine(alloc_cfg)
        d_infy = _decision("INFY", dtype=DecisionType.TRADE)
        d_tcs = _decision("TCS", dtype=DecisionType.TRADE)
        alloc_plan = alloc_eng.allocate(p_snap, [d_infy, d_tcs], as_of=AS_OF)

        # 3. Position Sizing
        sz_cfg = load_sizing_config(config_dir)
        sz_eng = PositionSizingEngine(sz_cfg)
        prices = {"INFY": Decimal("1500.00"), "TCS": Decimal("3000.00")}
        sz_plan = sz_eng.size_plan(alloc_plan, prices, as_of=AS_OF)

        # 4. Order Planning
        ord_cfg = load_order_planning_config(config_dir)
        ord_eng = OrderPlanningEngine(ord_cfg)
        exec_plan = ord_eng.plan_execution(sz_plan, as_of=AS_OF, decisions=[d_infy, d_tcs])

        # 5. Broker Abstraction
        b_cfg = load_broker_config(config_dir)
        b_mgr = BrokerManager(b_cfg)
        b_plan = b_mgr.translate_plan(exec_plan, as_of=AS_OF)

        # 6. Order Lifecycle Engine
        lc_cfg = load_execution_config(config_dir)
        lc_eng = OrderLifecycleEngine(lc_cfg)
        exec_state = lc_eng.initialize_from_plan(b_plan, as_of=AS_OF)

        # 7. Portfolio Analytics Engine
        analytics_cfg = load_portfolio_analytics_config(config_dir)
        analytics_eng = PortfolioAnalyticsEngine(analytics_cfg)
        snap = analytics_eng.analyze(
            p_snap,
            exec_state,
            current_prices={"INFY": Decimal("1600.00")},
            as_of=T1,
        )

        assert snap.portfolio_performance.realized_pnl == Decimal("0.00")
        assert snap.portfolio_performance.unrealized_pnl == Decimal("10000.00")
        assert snap.portfolio_performance.total_pnl == Decimal("10000.00")
        assert snap.portfolio_performance.portfolio_value == Decimal("1010000.00")
        assert snap.portfolio_performance.total_return_pct == Decimal("1.00")
        assert snap.references.execution_state_id == exec_state.state_id
        assert snap.references.portfolio_snapshot_id == p_snap.snapshot_id
