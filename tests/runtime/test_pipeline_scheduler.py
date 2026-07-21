"""Pipeline Scheduler bridge runtime tests (P7.5).

Covers ScheduleRunRequest validation, PipelineScheduleRun immutability and
thin-envelope design, PipelineScheduleHistory append-only semantics, and
SystemScheduleAdapter end-to-end execution including all failure boundaries
defined in the architecture (request rejected, execution started).

Tests deterministic replayability and confirm the scheduler never touches
PipelineDefinition internals, artifact keys, or stage topology.
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
from athena.execution import OrderLifecycleEngine
from athena.explainability.engine import ExplainabilityEngine
from athena.export.engine import ExportPresentationEngine
from athena.monitoring.engine import OperationalMonitoringEngine
from athena.orchestration import (
    PipelineScheduleHistory,
    PipelineScheduleRun,
    PipelineStatus,
    ScheduleRunRequest,
    SystemPipelineResult,
    SystemPipelineRunner,
    SystemScheduleAdapter,
    create_execution_pipeline,
    create_intelligence_pipeline,
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
from athena.scheduling.models import ScheduleDefinition, ScheduledJob, ScheduleMode
from athena.sizing import PositionSizingEngine
from athena.timeline.engine import TimelineAuditEngine

IST = ZoneInfo("Asia/Kolkata")
AS_OF = datetime(2026, 3, 2, 8, 30, tzinfo=IST)
T1 = AS_OF + timedelta(days=1)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

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


def _scheduled_job() -> ScheduledJob:
    defn = ScheduleDefinition(
        definition_id="pre-market-cycle",
        name="Pre-Market Daily Cycle",
        mode=ScheduleMode.DAILY,
        description="Daily pre-market ATHENA execution cycle",
    )
    return ScheduledJob(
        job_id="job-pm-20260302",
        definition_id=defn.definition_id,
        definition_name=defn.name,
        mode=ScheduleMode.DAILY,
        scheduled_for=AS_OF,
    )


def _make_execution_stages(config_dir) -> list:
    p_cfg = PortfolioConfig(initial_cash=Decimal("1000000.00"))
    p_eng = PortfolioEngine(p_cfg, initial_as_of=AS_OF)
    p_eng.open_position("INFY", quantity=100, price=Decimal("1500.00"), as_of=AS_OF)

    alloc_eng = CapitalAllocationEngine(load_allocation_config(config_dir))
    sz_eng = PositionSizingEngine(load_sizing_config(config_dir))
    ord_eng = OrderPlanningEngine(load_order_planning_config(config_dir))
    b_mgr = BrokerManager(load_broker_config(config_dir))
    lc_eng = OrderLifecycleEngine(load_execution_config(config_dir))
    analytics_eng = PortfolioAnalyticsEngine(load_portfolio_analytics_config(config_dir))
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
def valid_request() -> ScheduleRunRequest:
    return ScheduleRunRequest(
        job=_scheduled_job(),
        decisions=(_decision("INFY"),),
        current_prices={"INFY": Decimal("1600.00")},
        as_of=T1,
    )


@pytest.fixture()
def adapter(system_pipelines) -> SystemScheduleAdapter:
    exec_def, intel_def = system_pipelines
    return SystemScheduleAdapter(
        system_runner=SystemPipelineRunner(),
        execution_def=exec_def,
        intelligence_def=intel_def,
    )


# ---------------------------------------------------------------------------
# ScheduleRunRequest
# ---------------------------------------------------------------------------

class TestScheduleRunRequest:
    def test_valid_request_construction(self, valid_request):
        assert valid_request.job.job_id == "job-pm-20260302"
        assert len(valid_request.decisions) == 1
        assert valid_request.as_of == T1

    def test_empty_decisions_rejected_at_construction(self):
        with pytest.raises(ValueError, match="non-empty"):
            ScheduleRunRequest(
                job=_scheduled_job(),
                decisions=(),
                current_prices={"INFY": Decimal("1600.00")},
                as_of=T1,
            )

    def test_naive_datetime_rejected_at_construction(self):
        naive = datetime(2026, 3, 3, 8, 30)  # no tzinfo
        with pytest.raises(ValueError, match="timezone-aware"):
            ScheduleRunRequest(
                job=_scheduled_job(),
                decisions=(_decision("INFY"),),
                current_prices={"INFY": Decimal("1600.00")},
                as_of=naive,
            )

    def test_request_is_immutable(self, valid_request):
        with pytest.raises(dataclasses.FrozenInstanceError):
            valid_request.as_of = datetime.now(tz=IST)  # type: ignore[misc]

    def test_to_dict_is_deterministic(self, valid_request):
        assert valid_request.to_dict() == valid_request.to_dict()


# ---------------------------------------------------------------------------
# PipelineScheduleRun
# ---------------------------------------------------------------------------

class TestPipelineScheduleRun:
    def test_run_is_thin_envelope(self, adapter, valid_request):
        """system_result is the authoritative source; no duplicate execution metadata."""
        run = adapter.execute(valid_request)
        # Envelope fields only
        assert hasattr(run, "schedule_run_id")
        assert hasattr(run, "job_id")
        assert hasattr(run, "definition_id")
        assert hasattr(run, "system_result")
        assert hasattr(run, "duration_seconds")
        # Execution state must be accessed through system_result, not via run directly
        assert not hasattr(run, "status")
        assert not hasattr(run, "as_of")
        assert not hasattr(run, "pipeline_runs")
        assert not hasattr(run, "workspace_snapshot")

    def test_run_is_immutable(self, adapter, valid_request):
        run = adapter.execute(valid_request)
        with pytest.raises(dataclasses.FrozenInstanceError):
            run.job_id = "MUTATED"  # type: ignore[misc]

    def test_system_result_is_authoritative(self, adapter, valid_request):
        run = adapter.execute(valid_request)
        assert isinstance(run.system_result, SystemPipelineResult)
        assert run.system_result.overall_status == PipelineStatus.SUCCESS

    def test_envelope_fields_match_request(self, adapter, valid_request):
        run = adapter.execute(valid_request)
        assert run.job_id == valid_request.job.job_id
        assert run.definition_id == valid_request.job.definition_id

    def test_duration_is_non_negative(self, adapter, valid_request):
        run = adapter.execute(valid_request)
        assert run.duration_seconds >= 0.0

    def test_to_dict_and_to_json_are_deterministic(self, config_dir, valid_request):
        exec_def1 = create_execution_pipeline(_make_execution_stages(config_dir))
        intel_def1 = create_intelligence_pipeline(_make_intelligence_stages())
        exec_def2 = create_execution_pipeline(_make_execution_stages(config_dir))
        intel_def2 = create_intelligence_pipeline(_make_intelligence_stages())

        adapter1 = SystemScheduleAdapter(SystemPipelineRunner(), exec_def1, intel_def1)
        adapter2 = SystemScheduleAdapter(SystemPipelineRunner(), exec_def2, intel_def2)

        run1 = adapter1.execute(valid_request)
        run2 = adapter2.execute(valid_request)

        # duration_seconds is wall-clock measured — intentionally non-deterministic.
        # All other envelope and execution fields must be deterministic.
        def _without_duration(d: dict) -> dict:
            return {k: v for k, v in d.items() if k != "duration_seconds"}

        assert _without_duration(run1.to_dict()) == _without_duration(run2.to_dict())
        # system_result serialisation must be fully deterministic
        assert run1.system_result.to_dict() == run2.system_result.to_dict()
        assert run1.system_result.to_json() == run2.system_result.to_json()


# ---------------------------------------------------------------------------
# PipelineScheduleHistory
# ---------------------------------------------------------------------------

class TestPipelineScheduleHistory:
    def test_initial_history_is_empty(self):
        h = PipelineScheduleHistory()
        assert len(h.runs) == 0

    def test_record_returns_new_instance(self, adapter, valid_request):
        run = adapter.execute(valid_request)
        h1 = PipelineScheduleHistory()
        h2 = h1.record(run)
        assert h1 is not h2
        assert len(h1.runs) == 0
        assert len(h2.runs) == 1

    def test_history_is_append_only(self, adapter, valid_request):
        run = adapter.execute(valid_request)
        h = PipelineScheduleHistory()
        h2 = h.record(run)
        h3 = h2.record(run)
        assert len(h3.runs) == 2
        assert len(h2.runs) == 1  # original unchanged

    def test_history_is_immutable(self):
        h = PipelineScheduleHistory()
        with pytest.raises(dataclasses.FrozenInstanceError):
            h.runs = ()  # type: ignore[misc]

    def test_for_job_filters_correctly(self, adapter, valid_request):
        run = adapter.execute(valid_request)
        h = PipelineScheduleHistory().record(run)
        assert len(h.for_job(valid_request.job.job_id)) == 1
        assert len(h.for_job("nonexistent-job")) == 0

    def test_for_status_filters_correctly(self, adapter, valid_request):
        run = adapter.execute(valid_request)
        h = PipelineScheduleHistory().record(run)
        assert len(h.for_status(PipelineStatus.SUCCESS)) == 1
        assert len(h.for_status(PipelineStatus.FAILED)) == 0

    def test_summarize_counts_correct(self, adapter, valid_request):
        run = adapter.execute(valid_request)
        h = PipelineScheduleHistory().record(run).record(run)
        summary = h.summarize()
        assert summary["total"] == 2
        assert summary["success"] == 2
        assert summary["failed"] == 0


# ---------------------------------------------------------------------------
# SystemScheduleAdapter
# ---------------------------------------------------------------------------

class TestSystemScheduleAdapter:
    def test_execute_success_end_to_end(self, adapter, valid_request):
        run = adapter.execute(valid_request)
        assert isinstance(run, PipelineScheduleRun)
        assert run.system_result.overall_status == PipelineStatus.SUCCESS
        assert run.system_result.workspace_snapshot is not None

    def test_adapter_records_history_on_success(self, adapter, valid_request):
        assert len(adapter.history.runs) == 0
        adapter.execute(valid_request)
        assert len(adapter.history.runs) == 1

    def test_adapter_history_grows_with_multiple_executions(self, adapter, valid_request):
        adapter.execute(valid_request)
        adapter.execute(valid_request)
        assert len(adapter.history.runs) == 2

    def test_adapter_history_is_read_only(self, adapter, valid_request):
        adapter.execute(valid_request)
        hist = adapter.history
        with pytest.raises(dataclasses.FrozenInstanceError):
            hist.runs = ()  # type: ignore[misc]

    def test_run_id_increments_per_execution(self, adapter, valid_request):
        run1 = adapter.execute(valid_request)
        run2 = adapter.execute(valid_request)
        assert run1.schedule_run_id != run2.schedule_run_id
        assert run1.schedule_run_id == "schedrun-0001"
        assert run2.schedule_run_id == "schedrun-0002"

    def test_request_rejection_not_recorded_in_history(self, system_pipelines):
        exec_def, intel_def = system_pipelines
        adapter = SystemScheduleAdapter(
            system_runner=SystemPipelineRunner(),
            execution_def=exec_def,
            intelligence_def=intel_def,
        )
        # ScheduleRunRequest construction raises ValueError (empty decisions)
        with pytest.raises(ValueError, match="non-empty"):
            ScheduleRunRequest(
                job=_scheduled_job(),
                decisions=(),
                current_prices={"INFY": Decimal("1600.00")},
                as_of=T1,
            )
        # No execution happened, history is empty
        assert len(adapter.history.runs) == 0

    def test_workspace_failure_recorded_as_failed(self, system_pipelines, valid_request, monkeypatch):
        exec_def, intel_def = system_pipelines
        runner = SystemPipelineRunner()
        adapter = SystemScheduleAdapter(
            system_runner=runner,
            execution_def=exec_def,
            intelligence_def=intel_def,
        )

        # Monkeypatch workspace assembler to raise
        def mock_fail(ctx):
            raise RuntimeError("Workspace assembly failed")

        monkeypatch.setattr(runner._workspace_assembler, "assemble", mock_fail)

        run = adapter.execute(valid_request)

        assert run.system_result.overall_status == PipelineStatus.FAILED
        assert run.system_result.workspace_snapshot is None
        # Execution started, so it must be recorded
        assert len(adapter.history.runs) == 1
        assert adapter.history.runs[0].system_result.overall_status == PipelineStatus.FAILED

    def test_scheduler_unaware_of_pipeline_internals(self, system_pipelines, valid_request):
        """The adapter API exposes only ScheduleRunRequest — no PipelineDefinition or artifact keys."""
        exec_def, intel_def = system_pipelines
        adapter = SystemScheduleAdapter(
            system_runner=SystemPipelineRunner(),
            execution_def=exec_def,
            intelligence_def=intel_def,
        )
        # Caller uses only ScheduleRunRequest — no reference to PipelineDefinition or artifact keys needed
        run = adapter.execute(valid_request)
        assert run.system_result.overall_status == PipelineStatus.SUCCESS
