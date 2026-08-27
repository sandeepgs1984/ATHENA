"""EM-4C report scaffolding: result schema and manifest fingerprinting
-- replay determinism is the load-bearing property (same content twice
-> identical manifest_id, matching the EM-3 run_id-determinism lesson),
tested with synthetic fixtures only."""

from __future__ import annotations

from athena.explosive_move.em4c_report import (
    CrossSectionResult,
    build_evaluation_manifest,
    cross_section_result_to_dict,
)


def _result(**overrides) -> dict:
    base = dict(
        model_name="base-rate", family="TOUCH", threshold=10, checkpoint="09:20",
        session_date="2025-06-02", eligible_n=100, base_rate=0.05,
        precision_at_5=None, precision_at_10=None, precision_at_20=None,
        lift_at_5=None, lift_at_10=None, lift_at_20=None, pr_auc=None, brier=None,
    )
    base.update(overrides)
    return cross_section_result_to_dict(CrossSectionResult(**base))


def test_cross_section_result_round_trips_to_plain_dict():
    d = _result()
    assert d["model_name"] == "base-rate"
    assert d["family"] == "TOUCH"
    assert isinstance(d, dict)


def test_manifest_id_is_deterministic_across_repeated_builds():
    results = (_result(), _result(session_date="2025-06-03"))
    m1 = build_evaluation_manifest(
        results=results, model_names=("base-rate",), source_run_ids={"em2": "abc123"},
    )
    m2 = build_evaluation_manifest(
        results=results, model_names=("base-rate",), source_run_ids={"em2": "abc123"},
    )
    assert m1["manifest_id"] == m2["manifest_id"]


def test_manifest_id_is_order_independent_over_results():
    r1, r2 = _result(session_date="2025-06-02"), _result(session_date="2025-06-03")
    m_forward = build_evaluation_manifest(
        results=(r1, r2), model_names=("base-rate",), source_run_ids={"em2": "abc123"},
    )
    m_reversed = build_evaluation_manifest(
        results=(r2, r1), model_names=("base-rate",), source_run_ids={"em2": "abc123"},
    )
    assert m_forward["manifest_id"] == m_reversed["manifest_id"]


def test_manifest_id_changes_when_a_result_changes():
    results_a = (_result(base_rate=0.05),)
    results_b = (_result(base_rate=0.06),)
    m_a = build_evaluation_manifest(results=results_a, model_names=("base-rate",), source_run_ids={"em2": "abc"})
    m_b = build_evaluation_manifest(results=results_b, model_names=("base-rate",), source_run_ids={"em2": "abc"})
    assert m_a["manifest_id"] != m_b["manifest_id"]


def test_elapsed_seconds_excluded_from_fingerprint():
    results = (_result(),)
    m_fast = build_evaluation_manifest(
        results=results, model_names=("base-rate",), source_run_ids={"em2": "abc"}, elapsed_seconds=1.0,
    )
    m_slow = build_evaluation_manifest(
        results=results, model_names=("base-rate",), source_run_ids={"em2": "abc"}, elapsed_seconds=99.0,
    )
    assert m_fast["manifest_id"] == m_slow["manifest_id"]
    assert m_fast["elapsed_seconds"] == 1.0
    assert m_slow["elapsed_seconds"] == 99.0


def test_manifest_records_contract_version_and_source_run_ids():
    m = build_evaluation_manifest(
        results=(_result(),), model_names=("deterministic-v1",),
        source_run_ids={"em2_validation_manifest_id": "em2-evidence-xyz"},
    )
    assert m["contract_version"] == "em4c-evaluation-v1"
    assert m["source_run_ids"] == {"em2_validation_manifest_id": "em2-evidence-xyz"}
    assert m["result_count"] == 1
