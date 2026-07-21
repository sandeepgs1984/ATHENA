"""Portfolio Engine tests (P5.1).

Covers opening, increasing, reducing, closing, holding positions; reserving/releasing capital;
duplicate/error handling; portfolio replay; immutable snapshots; append-only history;
deterministic reruns; configuration validation; and an end-to-end integration test consuming
the operational pipeline via SchedulingFramework.
"""

from __future__ import annotations

import dataclasses
import json
from datetime import datetime, timedelta
from decimal import Decimal
from zoneinfo import ZoneInfo

import pytest

from athena.analytics import ReportingAnalyticsEngine
from athena.backtest import BacktestingEngine
from athena.config.loader import (
    load_analytics_config,
    load_portfolio_config,
    load_scheduling_config,
    load_strategy_config,
    load_watchlist_config,
)
from athena.config.models import PortfolioConfig
from athena.decision.models import DecisionOutcome
from athena.domain.decision import Decision, DecisionTrace, TraceStage, TradePlan
from athena.domain.enums import DecisionType, Direction
from athena.errors import ConfigError, PortfolioError
from athena.portfolio import (
    CashBalance,
    ClosedPosition,
    Holding,
    PortfolioEngine,
    PortfolioReferences,
)
from athena.runtime import ExecutionStatus, WorkflowEngine, WorkflowStage, build_definition
from athena.scanner import DailyMarketScanner, InstrumentPlan, ScanCapture
from athena.scheduling import ScheduleDefinition, ScheduleMode, SchedulingFramework
from athena.strategy import StrategyFramework
from athena.watchlist import WatchlistManager

IST = ZoneInfo("Asia/Kolkata")
AS_OF = datetime(2026, 3, 2, 8, 30, tzinfo=IST)
DAY2 = AS_OF + timedelta(days=1)
DAY3 = AS_OF + timedelta(days=2)


class FakeClock:
    def __init__(self, step=1.0):
        self._t = 0.0
        self._step = step

    def __call__(self):
        self._t += self._step
        return self._t


@pytest.fixture()
def engine():
    cfg = PortfolioConfig(initial_cash=Decimal("1000000.00"))
    return PortfolioEngine(cfg, initial_as_of=AS_OF)


class TestPortfolioOperations:
    def test_open_position(self, engine):
        refs = PortfolioReferences(decision_id="dec-1", strategy="momentum")
        snap = engine.open_position(
            "INFY", 100, Decimal("1500.00"), as_of=AS_OF, references=refs
        )
        assert snap.operation == "OPEN"
        assert "INFY" in snap.portfolio.holdings
        h = snap.portfolio.holdings["INFY"]
        assert h.quantity == 100
        assert h.avg_price == Decimal("1500.00")
        assert h.total_cost == Decimal("150000.00")
        assert h.references.decision_id == "dec-1"
        assert snap.portfolio.cash.allocated_cash == Decimal("150000.00")
        assert snap.portfolio.cash.available_cash == Decimal("850000.00")

    def test_increase_position(self, engine):
        engine.open_position("INFY", 100, Decimal("1500.00"), as_of=AS_OF)
        snap = engine.increase_position("INFY", 50, Decimal("1800.00"), as_of=DAY2)
        assert snap.operation == "INCREASE"
        h = snap.portfolio.holdings["INFY"]
        assert h.quantity == 150
        # Total cost: 150,000 + 90,000 = 240,000. Avg price: 240,000 / 150 = 1600.00
        assert h.total_cost == Decimal("240000.00")
        assert h.avg_price == Decimal("1600.00")
        assert snap.portfolio.cash.allocated_cash == Decimal("240000.00")
        assert snap.portfolio.cash.available_cash == Decimal("760000.00")

    def test_reduce_position(self, engine):
        engine.open_position("INFY", 100, Decimal("1500.00"), as_of=AS_OF)
        snap = engine.reduce_position("INFY", 40, Decimal("1600.00"), as_of=DAY2)
        assert snap.operation == "REDUCE"
        h = snap.portfolio.holdings["INFY"]
        assert h.quantity == 60
        assert h.avg_price == Decimal("1500.00")
        assert h.total_cost == Decimal("90000.00")
        # Proceeds: 40 * 1600 = 64,000. Cost reduced: 40 * 1500 = 60,000.
        # Cash: available = 850,000 + 64,000 = 914,000. allocated = 90,000.
        assert snap.portfolio.cash.allocated_cash == Decimal("90000.00")
        assert snap.portfolio.cash.available_cash == Decimal("914000.00")

    def test_close_position(self, engine):
        engine.open_position("INFY", 100, Decimal("1500.00"), as_of=AS_OF)
        snap = engine.close_position("INFY", Decimal("1700.00"), as_of=DAY2)
        assert snap.operation == "CLOSE"
        assert "INFY" not in snap.portfolio.holdings
        assert len(snap.portfolio.closed_positions) == 1
        cp = snap.portfolio.closed_positions[0]
        assert cp.instrument_id == "INFY"
        assert cp.quantity == 100
        assert cp.avg_entry_price == Decimal("1500.00")
        assert cp.avg_exit_price == Decimal("1700.00")
        assert cp.total_cost == Decimal("150000.00")
        assert cp.total_proceeds == Decimal("170000.00")
        # Cash: available = 850,000 + 170,000 = 1,020,000. allocated = 0.
        assert snap.portfolio.cash.allocated_cash == Decimal("0.00")
        assert snap.portfolio.cash.available_cash == Decimal("1020000.00")

    def test_hold_position(self, engine):
        engine.open_position("INFY", 100, Decimal("1500.00"), as_of=AS_OF)
        snap = engine.hold_position("INFY", as_of=DAY2)
        assert snap.operation == "HOLD"
        assert snap.portfolio.holdings["INFY"].last_updated_as_of == DAY2

    def test_reserve_and_release_capital(self, engine):
        snap1 = engine.reserve_capital("res-1", "margin reserve", Decimal("200000.00"), as_of=AS_OF)
        assert snap1.operation == "RESERVE"
        assert snap1.portfolio.cash.reserved_cash == Decimal("200000.00")
        assert snap1.portfolio.cash.available_cash == Decimal("800000.00")
        assert len(snap1.portfolio.reservations) == 1

        snap2 = engine.release_capital("res-1", as_of=DAY2)
        assert snap2.operation == "RELEASE"
        assert snap2.portfolio.cash.reserved_cash == Decimal("0.00")
        assert snap2.portfolio.cash.available_cash == Decimal("1000000.00")
        assert len(snap2.portfolio.reservations) == 0


class TestApplyDecision:
    def test_apply_trade_and_exit_decisions(self, engine):
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

        d_trade = Decision(
            decision_id="dec-trade-1",
            ts=AS_OF,
            run_id="run-1",
            cycle_id="c1",
            decision_type=DecisionType.TRADE,
            explanation="Strong momentum buy",
            instrument_id="INFY",
            direction=Direction.LONG,
            trade_plan=plan,
        )

        snap1 = engine.apply_decision(
            d_trade, Decimal("1500.00"), 100, as_of=AS_OF, strategy="momentum"
        )
        assert snap1.operation == "OPEN"
        assert "INFY" in snap1.portfolio.holdings

        d_exit = Decision(
            decision_id="dec-exit-1",
            ts=DAY2,
            run_id="run-2",
            cycle_id="c2",
            decision_type=DecisionType.FULL_EXIT,
            explanation="Target reached",
            instrument_id="INFY",
            direction=Direction.LONG,
        )

        snap2 = engine.apply_decision(
            d_exit, Decimal("1600.00"), 100, as_of=DAY2, strategy="momentum"
        )
        assert snap2.operation == "CLOSE"
        assert "INFY" not in snap2.portfolio.holdings


class TestDuplicateAndErrorHandling:
    def test_duplicate_open_raises_error(self, engine):
        engine.open_position("INFY", 100, Decimal("1500.00"), as_of=AS_OF)
        with pytest.raises(PortfolioError, match="already exists"):
            engine.open_position("INFY", 50, Decimal("1550.00"), as_of=DAY2)

    def test_increase_nonexistent_raises_error(self, engine):
        with pytest.raises(PortfolioError, match="No existing holding"):
            engine.increase_position("TCS", 50, Decimal("3000.00"), as_of=AS_OF)

    def test_reduce_over_quantity_raises_error(self, engine):
        engine.open_position("INFY", 100, Decimal("1500.00"), as_of=AS_OF)
        with pytest.raises(PortfolioError, match="Cannot reduce"):
            engine.reduce_position("INFY", 150, Decimal("1600.00"), as_of=DAY2)

    def test_insufficient_cash_raises_error(self, engine):
        with pytest.raises(PortfolioError, match="Insufficient available cash"):
            engine.open_position("INFY", 1000, Decimal("1500.00"), as_of=AS_OF)

    def test_backdated_as_of_raises_error(self, engine):
        engine.open_position("INFY", 100, Decimal("1500.00"), as_of=DAY2)
        with pytest.raises(PortfolioError, match="earlier than portfolio as_of"):
            engine.hold_position("INFY", as_of=AS_OF)


class TestReplayAndImmutability:
    def test_deterministic_replay(self, config_dir):
        cfg = load_portfolio_config(config_dir)
        eng1 = PortfolioEngine(cfg, initial_as_of=AS_OF)
        eng1.open_position("INFY", 100, Decimal("1500.00"), as_of=AS_OF)
        eng1.increase_position("INFY", 50, Decimal("1600.00"), as_of=DAY2)
        eng1.close_position("INFY", Decimal("1700.00"), as_of=DAY3)

        eng2 = PortfolioEngine(cfg, initial_as_of=AS_OF)
        eng2.open_position("INFY", 100, Decimal("1500.00"), as_of=AS_OF)
        eng2.increase_position("INFY", 50, Decimal("1600.00"), as_of=DAY2)
        eng2.close_position("INFY", Decimal("1700.00"), as_of=DAY3)

        assert eng1.current_snapshot.to_dict() == eng2.current_snapshot.to_dict()
        assert eng1.history.to_dict() == eng2.history.to_dict()

    def test_immutable_snapshot(self, engine):
        snap = engine.open_position("INFY", 100, Decimal("1500.00"), as_of=AS_OF)
        with pytest.raises(dataclasses.FrozenInstanceError):
            snap.operation = "MUTATED"

    def test_append_only_history(self, engine):
        engine.open_position("INFY", 100, Decimal("1500.00"), as_of=AS_OF)
        engine.increase_position("INFY", 50, Decimal("1600.00"), as_of=DAY2)
        hist = engine.history
        assert len(hist.records) == 3  # INIT + OPEN + INCREASE
        with pytest.raises(dataclasses.FrozenInstanceError):
            hist.records = ()


class TestConfigValidation:
    def test_unknown_key_rejected(self):
        with pytest.raises(Exception, match=r"Extra inputs|extra"):
            PortfolioConfig.model_validate({"bogus": 1})

    def test_negative_cash_rejected(self):
        with pytest.raises(Exception, match="initial_cash must be >= 0"):
            PortfolioConfig.model_validate({"initial_cash": "-1000.00"})

    def test_production_config_loads(self, config_dir):
        cfg = load_portfolio_config(config_dir)
        assert cfg.initial_cash == Decimal("1000000.00")
        assert cfg.currency == "INR"

    def test_missing_config_fails_loudly(self, tmp_path):
        with pytest.raises(ConfigError):
            load_portfolio_config(tmp_path)


class TestEndToEndIntegration:
    def test_scheduled_pipeline_driving_portfolio(self, config_dir):
        """Integration test consuming SchedulingFramework operational pipeline output."""

        def builder_factory(decisions):
            def builder(instrument_id):
                dtype = decisions.get(instrument_id)
                if dtype is None:
                    return None
                box: dict = {}

                def decide(ctx):
                    plan = TradePlan(
                        entry_low=Decimal("1490.00"),
                        entry_high=Decimal("1510.00"),
                        stop_loss=Decimal("1450.00"),
                        targets=(Decimal("1600.00"),),
                        position_size=100,
                        risk_amount=Decimal("5000.00"),
                        risk_reward=Decimal("2.0"),
                        valid_from=ctx.as_of,
                        valid_until=ctx.as_of + timedelta(days=1),
                    )
                    decision = Decision(
                        decision_id=f"d-{instrument_id}-{ctx.as_of.date()}",
                        ts=ctx.as_of,
                        run_id="sched-p51",
                        cycle_id="c1",
                        decision_type=dtype,
                        instrument_id=instrument_id,
                        direction=Direction.LONG if dtype == DecisionType.TRADE else Direction.NONE,
                        trade_plan=plan if dtype == DecisionType.TRADE else None,
                        explanation=f"{instrument_id} {dtype.value}",
                    )
                    trace = DecisionTrace(
                        decision_ref=decision.decision_id,
                        stages=(TraceStage("decision", (decision.decision_id,), "real"),),
                    )
                    box["cap"] = ScanCapture(
                        outcome=DecisionOutcome(decision=decision, trace=trace)
                    )
                    return {"decided": True}

                defn = build_definition(
                    f"pipe-{instrument_id}",
                    [WorkflowStage("decide", decide, produces=("decided",))],
                )
                return InstrumentPlan(definition=defn, collect=lambda: box.get("cap"))

            return builder

        clock = FakeClock()
        scanner = DailyMarketScanner(WorkflowEngine(clock=clock))
        wl = WatchlistManager(load_watchlist_config(config_dir))
        fw = StrategyFramework.from_config(load_strategy_config(config_dir))
        bt = BacktestingEngine(scanner, wl, fw)
        analytics = ReportingAnalyticsEngine(load_analytics_config(config_dir))
        scheduler = SchedulingFramework(scanner, wl, fw, bt, analytics, clock=clock)

        # Execute scheduled daily run
        sched_def = ScheduleDefinition(
            definition_id="daily-p51",
            name="Daily P51 Scan",
            mode=ScheduleMode.DAILY,
            description="Operational run driving portfolio engine",
        )

        decisions = {"INFY": DecisionType.TRADE, "TCS": DecisionType.WATCH}
        exec_record = scheduler.execute(
            sched_def,
            as_of=AS_OF,
            pipeline_builder=builder_factory(decisions),
            universe=("INFY", "TCS"),
        )
        assert exec_record.status is ExecutionStatus.COMPLETED

        # Drive Portfolio Engine using decision outcome from scheduled scan
        scan_report = scanner.scan(
            ("INFY", "TCS"), as_of=AS_OF, pipeline_builder=builder_factory(decisions)
        )
        infy_result = scan_report.result_for("INFY")
        assert infy_result is not None and infy_result.report is not None

        portfolio_eng = PortfolioEngine(
            load_portfolio_config(config_dir), initial_as_of=AS_OF
        )

        # Apply TRADE decision
        d_infy = Decision(
            decision_id=f"dec-INFY-{AS_OF.date()}",
            ts=AS_OF,
            run_id=exec_record.execution_id,
            cycle_id="c1",
            decision_type=DecisionType.TRADE,
            explanation="Scheduled TRADE decision for INFY",
            instrument_id="INFY",
            direction=Direction.LONG,
            trade_plan=TradePlan(
                entry_low=Decimal("1490.00"),
                entry_high=Decimal("1510.00"),
                stop_loss=Decimal("1450.00"),
                targets=(Decimal("1600.00"),),
                position_size=100,
                risk_amount=Decimal("5000.00"),
                risk_reward=Decimal("2.0"),
                valid_from=AS_OF,
                valid_until=DAY2,
            ),
        )

        snap = portfolio_eng.apply_decision(
            d_infy,
            price=Decimal("1500.00"),
            quantity=100,
            as_of=AS_OF,
            schedule_execution_id=exec_record.execution_id,
        )

        assert snap.operation == "OPEN"
        assert "INFY" in snap.portfolio.holdings
        assert snap.portfolio.holdings["INFY"].quantity == 100
        assert snap.references.schedule_execution_id == exec_record.execution_id
        assert snap.references.decision_id == d_infy.decision_id
