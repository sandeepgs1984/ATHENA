"""Signal drift monitor tests (M-X10): baseline capture/round-trip, drift
detection — file-based, no new persisted schema."""

from __future__ import annotations

from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

from athena.config.loader import load_decision_config, load_scoring_config
from athena.diagnostics.weight_drift import (
    WeightSnapshot,
    capture_baseline,
    detect_drift,
    read_baseline,
    write_baseline,
)

IST = ZoneInfo("Asia/Kolkata")
AS_OF = datetime(2026, 2, 13, 16, 0, tzinfo=IST)


class TestBaselineCaptureAndRoundTrip:
    def test_capture_matches_config(self, config_dir):
        scoring = load_scoring_config(config_dir)
        decision = load_decision_config(config_dir)
        snapshot = capture_baseline(scoring, decision, as_of=AS_OF)
        assert snapshot.scoring_weights == scoring.weights.model_dump()
        assert snapshot.decision_min_composite_for_trade == decision.thresholds.min_composite_for_trade
        assert snapshot.captured_at == AS_OF.isoformat()

    def test_json_round_trip(self, config_dir):
        scoring = load_scoring_config(config_dir)
        decision = load_decision_config(config_dir)
        snapshot = capture_baseline(scoring, decision, as_of=AS_OF)
        restored = WeightSnapshot.from_json(snapshot.to_json())
        assert restored == snapshot

    def test_write_and_read_baseline(self, tmp_path: Path, config_dir):
        scoring = load_scoring_config(config_dir)
        decision = load_decision_config(config_dir)
        snapshot = capture_baseline(scoring, decision, as_of=AS_OF)
        path = tmp_path / "diag" / "weight_baseline.json"
        write_baseline(path, snapshot)
        assert path.exists()
        restored = read_baseline(path)
        assert restored == snapshot

    def test_read_missing_baseline_returns_none(self, tmp_path: Path):
        assert read_baseline(tmp_path / "does-not-exist.json") is None


class TestDetectDrift:
    def test_no_drift_when_config_unchanged(self, config_dir):
        scoring = load_scoring_config(config_dir)
        decision = load_decision_config(config_dir)
        baseline = capture_baseline(scoring, decision, as_of=AS_OF)
        assert detect_drift(baseline, scoring, decision) == []

    def test_detects_scoring_weight_drift(self, config_dir):
        scoring = load_scoring_config(config_dir)
        decision = load_decision_config(config_dir)
        baseline = capture_baseline(scoring, decision, as_of=AS_OF)
        moved = scoring.model_copy(
            update={"weights": scoring.weights.model_copy(update={
                "trend": scoring.weights.trend + 10,
                "momentum": scoring.weights.momentum - 10,
            })}
        )
        drifts = detect_drift(baseline, moved, decision)
        assert any("weights.trend" in d for d in drifts)
        assert any("weights.momentum" in d for d in drifts)

    def test_detects_decision_threshold_drift(self, config_dir):
        scoring = load_scoring_config(config_dir)
        decision = load_decision_config(config_dir)
        baseline = capture_baseline(scoring, decision, as_of=AS_OF)
        moved_thresholds = decision.thresholds.model_copy(
            update={"min_composite_for_trade": decision.thresholds.min_composite_for_trade + 5}
        )
        moved_decision = decision.model_copy(update={"thresholds": moved_thresholds})
        drifts = detect_drift(baseline, scoring, moved_decision)
        assert any("min_composite_for_trade" in d for d in drifts)

    def test_unrelated_dimension_unchanged_not_flagged(self, config_dir):
        scoring = load_scoring_config(config_dir)
        decision = load_decision_config(config_dir)
        baseline = capture_baseline(scoring, decision, as_of=AS_OF)
        moved = scoring.model_copy(
            update={"weights": scoring.weights.model_copy(update={
                "trend": scoring.weights.trend + 5,
                "liquidity": scoring.weights.liquidity - 5,
            })}
        )
        drifts = detect_drift(baseline, moved, decision)
        assert not any("market_quality" in d for d in drifts)
        assert not any("sector_quality" in d for d in drifts)
