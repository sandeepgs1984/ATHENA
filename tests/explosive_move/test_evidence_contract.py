"""EM-2 evidence contract: locks down the owner-corrected exact field
count (15 invariant + 13 dynamic = 28, not 29) and structural invariants
the manifest and the computation modules must never silently drift from."""

from __future__ import annotations

from athena.explosive_move.evidence_contract import (
    ALL_FIELDS,
    CHECKPOINT_DYNAMIC_FIELD_COUNT,
    EVIDENCE_CONTRACT_VERSION,
    SESSION_INVARIANT_FIELD_COUNT,
    TOTAL_FIELD_COUNT,
    Classification,
    Provenance,
    Timing,
)


def test_exact_field_counts():
    assert SESSION_INVARIANT_FIELD_COUNT == 15
    assert CHECKPOINT_DYNAMIC_FIELD_COUNT == 13
    assert TOTAL_FIELD_COUNT == 28
    assert len(ALL_FIELDS) == 28


def test_field_names_are_unique():
    names = [f.name for f in ALL_FIELDS]
    assert len(names) == len(set(names))


def test_contract_version_frozen():
    assert EVIDENCE_CONTRACT_VERSION == "em2-evidence-v1"


def test_every_field_has_a_timing():
    for f in ALL_FIELDS:
        assert f.timing in (Timing.SESSION_INVARIANT, Timing.CHECKPOINT_DYNAMIC)


def test_checkpoint_dynamic_fields_have_not_applicable_provenance():
    for f in ALL_FIELDS:
        if f.timing is Timing.CHECKPOINT_DYNAMIC:
            assert f.provenance is Provenance.NOT_APPLICABLE


def test_session_invariant_fields_have_a_real_provenance_subtype():
    for f in ALL_FIELDS:
        if f.timing is Timing.SESSION_INVARIANT:
            assert f.provenance in (Provenance.PRIOR_HISTORY, Provenance.SESSION_OPEN_CONTEXT)


def test_gap_pct_and_regime_gap_are_session_open_context():
    by_name = {f.name: f for f in ALL_FIELDS}
    assert by_name["GAP_PCT"].provenance is Provenance.SESSION_OPEN_CONTEXT
    assert by_name["REGIME_GAP"].provenance is Provenance.SESSION_OPEN_CONTEXT


def test_owner_named_evidence_only_fields():
    by_name = {f.name: f for f in ALL_FIELDS}
    for name in ("ATR14", "CUM_VOLUME_C", "HIGH_SO_FAR_C", "LOW_SO_FAR_C", "VWAP_THROUGH_C"):
        assert by_name[name].classification is Classification.EVIDENCE_ONLY, name


def test_owner_named_candidate_feature_fields():
    by_name = {f.name: f for f in ALL_FIELDS}
    for name in ("ATR14_NORM", "REL_VOLUME_C", "RANGE_SO_FAR_C", "DIST_FROM_HIGH_SO_FAR_C", "VWAP_REL_C"):
        assert by_name[name].classification is Classification.CANDIDATE_FEATURE, name


def test_every_field_has_at_least_one_unknown_reason_or_is_never_unknown():
    for f in ALL_FIELDS:
        # every field in this contract can be UNKNOWN under some real
        # condition (no field is exempt from the possibility)
        assert len(f.unknown_reasons) >= 1, f.name


def test_range_compression_20_lookback_is_exact_not_approximate():
    by_name = {f.name: f for f in ALL_FIELDS}
    assert by_name["RANGE_COMPRESSION_20"].minimum_lookback_sessions == 34
