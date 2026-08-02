"""Synthetic canary decision tests (M-X8): real-pipeline regression check,
never touching the real repository or a real owner candidate."""

from __future__ import annotations

import dataclasses
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

import pytest

from athena.domain.enums import DecisionType
from athena.ops.canary import CANARY_INSTRUMENT_ID, CanaryResult, run_canary
from athena.scoring.models import ScoreStatus

IST = ZoneInfo("Asia/Kolkata")
AS_OF = datetime(2026, 3, 2, 10, 0, tzinfo=IST)
REPO_CONFIG = Path(__file__).resolve().parents[2] / "config"


class TestRunCanary:
    def test_ok_against_real_production_config(self):
        """Runs the fixed synthetic instrument through the real
        OwnerValidationPipeline against the real production config/ — the
        pipeline must complete cleanly and produce a fully-explained
        (status OK) score/confidence/risk plus a recognized decision type."""
        result = run_canary(REPO_CONFIG, as_of=AS_OF, run_id="test-canary")
        assert result.ok, result.reasons
        assert result.decision_type in {t.value for t in DecisionType}
        assert result.composite_value is not None

    def test_deterministic_repeat(self):
        a = run_canary(REPO_CONFIG, as_of=AS_OF, run_id="test-canary-a")
        b = run_canary(REPO_CONFIG, as_of=AS_OF, run_id="test-canary-b")
        assert a.ok == b.ok
        assert a.decision_type == b.decision_type
        assert a.composite_value == b.composite_value

    def test_missing_config_dir_is_a_reported_regression_not_a_crash(self, tmp_path: Path):
        """An empty config_dir makes `load_config` raise inside the real
        pipeline — the canary must catch that and report it, never let it
        propagate (a canary regression must never itself become a new
        source of failure for the caller)."""
        result = run_canary(tmp_path, as_of=AS_OF, run_id="test-canary-broken")
        assert result.ok is False
        assert result.reasons
        assert "pipeline raised" in result.reasons[0]

    def test_result_immutable(self):
        result = run_canary(REPO_CONFIG, as_of=AS_OF, run_id="test-canary-immutable")
        with pytest.raises(dataclasses.FrozenInstanceError):
            result.ok = False  # type: ignore[misc]

    def test_synthetic_instrument_id_is_clearly_not_a_real_symbol(self):
        assert CANARY_INSTRUMENT_ID.startswith("NSE:ATHENACANARY")


class TestCanaryResultConstruction:
    def test_failed_result_shape(self):
        result = CanaryResult(
            ok=False, reasons=("score status UNKNOWN (expected OK)",),
            decision_type=None, composite_value=None,
        )
        assert not result.ok
        assert result.reasons

    def test_ok_result_matches_score_status_ok(self):
        # Sanity: the module's own comparison target is the real enum value,
        # not a hardcoded string that could silently drift from ScoreStatus.
        assert ScoreStatus.OK.value == "OK"
