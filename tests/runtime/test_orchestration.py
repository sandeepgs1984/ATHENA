"""Generic Pipeline Infrastructure tests (P7.1).

Covers stage protocol implementation, functional context propagation,
status enums, pipeline metadata, deterministic replay, failure isolation,
immutability, history accumulation, configuration validation, and domain independence.
"""

from __future__ import annotations

import dataclasses
import importlib
import json
import pkgutil
from datetime import datetime
from zoneinfo import ZoneInfo

import pytest

from athena.config.loader import load_orchestration_config
from athena.config.models import OrchestrationConfig
from athena.errors import ConfigError, OrchestrationError
from athena.orchestration import (
    PipelineContext,
    PipelineDefinition,
    PipelineHistory,
    PipelineMetadata,
    PipelineResult,
    PipelineRunner,
    PipelineStage,
    PipelineStatus,
    StageExecutionResult,
    StageResult,
    StageStatus,
)

IST = ZoneInfo("Asia/Kolkata")
AS_OF = datetime(2026, 3, 2, 8, 30, tzinfo=IST)


class DummyIncrementStage:
    """A generic dummy stage that increments a counter in context."""

    def __init__(self, stage_id: str, name: str, increment: int = 1) -> None:
        self._stage_id = stage_id
        self._name = name
        self._increment = increment

    @property
    def stage_id(self) -> str:
        return self._stage_id

    @property
    def name(self) -> str:
        return self._name

    def execute(self, context: PipelineContext) -> StageExecutionResult:
        current_val = int(context.get("counter", 0))
        new_val = current_val + self._increment
        new_ctx = context.with_value("counter", new_val)

        stage_res = StageResult(
            stage_id=self.stage_id,
            status=StageStatus.SUCCESS,
            message=f"Incremented counter from {current_val} to {new_val}",
            output_key="counter",
        )
        return StageExecutionResult(stage_result=stage_res, context=new_ctx)


class DummyFailingStage:
    """A generic dummy stage that intentionally fails."""

    def __init__(self, stage_id: str = "fail-stage") -> None:
        self._stage_id = stage_id

    @property
    def stage_id(self) -> str:
        return self._stage_id

    @property
    def name(self) -> str:
        return "Failing Stage"

    def execute(self, context: PipelineContext) -> StageExecutionResult:
        stage_res = StageResult(
            stage_id=self.stage_id,
            status=StageStatus.FAILED,
            message="Intentional failure for testing",
        )
        return StageExecutionResult(stage_result=stage_res, context=context)


@pytest.fixture()
def sample_pipeline_def():
    meta = PipelineMetadata(
        definition_id="def-dummy",
        version="1.0.0",
        name="Dummy Test Pipeline",
        description="A generic test pipeline",
    )
    s1 = DummyIncrementStage("s1", "First Stage", increment=5)
    s2 = DummyIncrementStage("s2", "Second Stage", increment=10)
    return PipelineDefinition(metadata=meta, stages=(s1, s2))


class TestGenericPipelineExecution:
    def test_pipeline_runner_success(self, sample_pipeline_def):
        runner = PipelineRunner()
        init_ctx = PipelineContext(run_id="run-001", as_of=AS_OF, data={"counter": 0})

        result = runner.run(sample_pipeline_def, init_ctx)

        assert result.overall_status == PipelineStatus.SUCCESS
        assert len(result.stages) == 2
        assert result.stages[0].status == StageStatus.SUCCESS
        assert result.final_context.get("counter") == 15

    def test_functional_context_propagation(self, sample_pipeline_def):
        runner = PipelineRunner()
        init_ctx = PipelineContext(run_id="run-001", as_of=AS_OF, data={"counter": 0})

        result = runner.run(sample_pipeline_def, init_ctx)

        # Verify initial context remains unmutated
        assert init_ctx.get("counter") == 0
        assert result.final_context.get("counter") == 15

    def test_failure_isolation_and_stop_policy(self, sample_pipeline_def):
        fail_stage = DummyFailingStage("fail-1")
        meta = PipelineMetadata("def-fail", "1.0", "Fail Pipeline", "Testing failure")
        pip_def = PipelineDefinition(meta, (sample_pipeline_def.stages[0], fail_stage, sample_pipeline_def.stages[1]))

        runner = PipelineRunner(OrchestrationConfig(stop_on_stage_failure=True))
        init_ctx = PipelineContext(run_id="run-fail", as_of=AS_OF)

        result = runner.run(pip_def, init_ctx)

        assert result.overall_status == PipelineStatus.FAILED
        assert len(result.stages) == 2  # Third stage skipped due to stop_on_stage_failure
        assert result.stages[1].status == StageStatus.FAILED


class TestReplayAndImmutability:
    def test_deterministic_replay(self, sample_pipeline_def):
        runner1 = PipelineRunner()
        init_ctx1 = PipelineContext(run_id="run-rep", as_of=AS_OF, data={"counter": 0})
        res1 = runner1.run(sample_pipeline_def, init_ctx1)

        runner2 = PipelineRunner()
        init_ctx2 = PipelineContext(run_id="run-rep", as_of=AS_OF, data={"counter": 0})
        res2 = runner2.run(sample_pipeline_def, init_ctx2)

        assert res1.to_dict() == res2.to_dict()
        assert res1.to_json() == res2.to_json()

    def test_immutable_outputs(self, sample_pipeline_def):
        runner = PipelineRunner()
        init_ctx = PipelineContext(run_id="run-001", as_of=AS_OF)
        res = runner.run(sample_pipeline_def, init_ctx)

        with pytest.raises(dataclasses.FrozenInstanceError):
            res.pipeline_run_id = "MUTATED"

    def test_append_only_history(self, sample_pipeline_def):
        runner = PipelineRunner()
        init_ctx = PipelineContext(run_id="run-001", as_of=AS_OF)
        runner.run(sample_pipeline_def, init_ctx)

        hist = runner.history
        assert len(hist.records) == 1

        with pytest.raises(dataclasses.FrozenInstanceError):
            hist.records = ()


class TestConfigValidation:
    def test_unknown_key_rejected(self):
        with pytest.raises(Exception, match=r"Extra inputs|extra"):
            OrchestrationConfig.model_validate({"bogus": 1})

    def test_production_config_loads(self, config_dir):
        cfg = load_orchestration_config(config_dir)
        assert cfg.stop_on_stage_failure is True
        assert cfg.record_history is True

    def test_missing_config_fails_loudly(self, tmp_path):
        with pytest.raises(ConfigError):
            load_orchestration_config(tmp_path)


class TestDomainIndependence:
    def test_orchestration_package_has_zero_business_domain_dependencies(self):
        """Strict architecture check: verify athena.orchestration imports zero business domain modules."""
        import athena.orchestration.engine as eng
        import athena.orchestration.models as mod

        forbidden_domains = {
            "calendar",
            "data",
            "context",
            "decision",
            "allocation",
            "sizing",
            "orders",
            "brokers",
            "execution",
            "analytics",
            "reporting",
            "dashboard",
            "explainability",
            "timeline",
            "monitoring",
            "export",
            "workspace",
        }

        for module in (eng, mod):
            for attr in dir(module):
                obj = getattr(module, attr)
                if hasattr(obj, "__module__") and obj.__module__:
                    mod_name = obj.__module__
                    if mod_name.startswith("athena."):
                        parts = mod_name.split(".")
                        domain = parts[1]
                        assert domain not in forbidden_domains, (
                            f"Illegal business domain dependency found: {mod_name} in {module.__name__}"
                        )
