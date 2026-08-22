"""EM-1r4: cohort admission and quote-timestamp hygiene contracts.

Applies the EM-1r2 survivor-cohort contract to per-symbol-day research
admission and rejects Unix-epoch and out-of-study/out-of-session quote
timestamps, without ever projecting current membership backward as
point-in-time historical evidence (ADR-012 s6; the remediation plan's
EM-1r4 acceptance criteria).
"""

from __future__ import annotations

import tempfile
from datetime import date, datetime, time, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

import pytest

from athena.domain.market import Quote
from athena.explosive_move.cohort_admission import (
    CohortAdmissionExclusionReason,
    CohortAdmissionManifest,
    InstrumentListingSnapshot,
    QuoteHygieneAssessment,
    QuoteHygieneExclusionReason,
    SymbolDayAdmission,
    assess_quote_timestamp_hygiene,
    assess_symbol_day_cohort_admission,
    cohort_admission_manifest_from_payload,
    write_immutable_manifest,
)
from athena.explosive_move.corporate_action_coverage import build_survivor_cohort

IST = ZoneInfo("Asia/Kolkata")


def _cohort(instrument_ids=("NSE:AAA", "NSE:BBB")):
    return build_survivor_cohort(
        universe_name="athena_core",
        resolution_date=date(2026, 8, 21),
        instrument_ids=instrument_ids,
        group_effective_dates=(("athena_core", date(2026, 8, 21)),),
    )


def _quote(ts: datetime, instrument_id: str = "NSE:AAA") -> Quote:
    from decimal import Decimal

    return Quote(instrument_id=instrument_id, ts=ts, last_price=Decimal("100"), volume=1, source="kite")


# --------------------------------------------------------------------------- #
# 1. Symbol-day cohort admission
# --------------------------------------------------------------------------- #


def test_symbol_day_admitted_when_in_cohort_with_no_listing_conflict():
    cohort = _cohort()
    result = assess_symbol_day_cohort_admission(
        instrument_id="NSE:AAA",
        session_date=date(2024, 1, 2),
        listed_date=None,
        delisted_date=None,
        cohort=cohort,
    )
    assert result.admitted is True
    assert result.reasons == ()


def test_symbol_day_excluded_when_outside_survivor_cohort():
    cohort = _cohort()
    result = assess_symbol_day_cohort_admission(
        instrument_id="NSE:ZZZ",
        session_date=date(2024, 1, 2),
        listed_date=None,
        delisted_date=None,
        cohort=cohort,
    )
    assert result.admitted is False
    assert result.reasons == (CohortAdmissionExclusionReason.SYMBOL_OUTSIDE_SURVIVOR_COHORT,)


def test_symbol_day_excluded_when_listed_after_session_date():
    cohort = _cohort()
    result = assess_symbol_day_cohort_admission(
        instrument_id="NSE:AAA",
        session_date=date(2024, 1, 2),
        listed_date=date(2025, 1, 1),
        delisted_date=None,
        cohort=cohort,
    )
    assert result.admitted is False
    assert result.reasons == (CohortAdmissionExclusionReason.LISTING_DELISTING_AMBIGUOUS,)


def test_symbol_day_excluded_when_delisted_before_session_date():
    cohort = _cohort()
    result = assess_symbol_day_cohort_admission(
        instrument_id="NSE:AAA",
        session_date=date(2024, 1, 2),
        listed_date=None,
        delisted_date=date(2023, 6, 1),
        cohort=cohort,
    )
    assert result.admitted is False
    assert result.reasons == (CohortAdmissionExclusionReason.LISTING_DELISTING_AMBIGUOUS,)


def test_symbol_day_excluded_when_delisted_before_listed():
    """Internally inconsistent source data -- fail closed, never guess which
    date is correct."""
    cohort = _cohort()
    result = assess_symbol_day_cohort_admission(
        instrument_id="NSE:AAA",
        session_date=date(2024, 1, 2),
        listed_date=date(2024, 6, 1),
        delisted_date=date(2024, 1, 1),
        cohort=cohort,
    )
    assert result.admitted is False
    assert result.reasons == (CohortAdmissionExclusionReason.LISTING_DELISTING_AMBIGUOUS,)


def test_symbol_day_admission_never_claims_the_session_date_as_eligibility_evidence():
    """EM-1r4 acceptance: "current membership is never projected backward" --
    the dated evidence backing an admission is always the cohort's own
    resolution date, never the (possibly much older) session date itself."""
    cohort = _cohort()
    result = assess_symbol_day_cohort_admission(
        instrument_id="NSE:AAA",
        session_date=date(2015, 1, 2),
        listed_date=None,
        delisted_date=None,
        cohort=cohort,
    )
    assert result.eligibility_evidence_date == cohort.resolution_date
    assert result.eligibility_evidence_date != result.session_date


def test_symbol_day_admission_always_carries_the_cohort_limitation():
    cohort = _cohort()
    admitted = assess_symbol_day_cohort_admission(
        instrument_id="NSE:AAA", session_date=date(2024, 1, 2),
        listed_date=None, delisted_date=None, cohort=cohort,
    )
    excluded = assess_symbol_day_cohort_admission(
        instrument_id="NSE:ZZZ", session_date=date(2024, 1, 2),
        listed_date=None, delisted_date=None, cohort=cohort,
    )
    assert admitted.cohort_limitation == cohort.limitation
    assert excluded.cohort_limitation == cohort.limitation


def test_symbol_day_admission_sector_is_always_unknown():
    """Sector history is never point-in-time authoritative in this ledger
    (EM-1a) -- every record says so, regardless of admission outcome."""
    cohort = _cohort()
    result = assess_symbol_day_cohort_admission(
        instrument_id="NSE:AAA", session_date=date(2024, 1, 2),
        listed_date=None, delisted_date=None, cohort=cohort,
    )
    assert result.sector == "UNKNOWN"


def test_symbol_day_admission_rejects_a_non_unknown_sector():
    with pytest.raises(ValueError, match="sector"):
        SymbolDayAdmission(
            instrument_id="NSE:AAA", session_date=date(2024, 1, 2),
            cohort_name="X", cohort_id="Y", cohort_limitation="Z",
            eligibility_evidence_date=date(2024, 1, 1), sector="IT",
            admitted=True, reasons=(),
        )


def test_symbol_day_admission_reasons_invariant():
    with pytest.raises(ValueError, match="reasons"):
        SymbolDayAdmission(
            instrument_id="NSE:AAA", session_date=date(2024, 1, 2),
            cohort_name="X", cohort_id="Y", cohort_limitation="Z",
            eligibility_evidence_date=date(2024, 1, 1), sector="UNKNOWN",
            admitted=True, reasons=(CohortAdmissionExclusionReason.SYMBOL_OUTSIDE_SURVIVOR_COHORT,),
        )


# --------------------------------------------------------------------------- #
# 2. Quote-timestamp hygiene
# --------------------------------------------------------------------------- #


def test_quote_rejects_epoch_default_timestamp():
    quote = _quote(datetime(1970, 1, 1, 5, 30, tzinfo=IST))
    result = assess_quote_timestamp_hygiene(
        quote, study_start=date(2023, 1, 1), study_end=date(2026, 1, 1),
        market_timezone=IST, is_trading_session=True,
        session_open=time(9, 15), session_close=time(15, 30),
    )
    assert result.admitted is False
    assert result.reasons == (QuoteHygieneExclusionReason.EPOCH_DEFAULT_TIMESTAMP,)


def test_quote_epoch_check_is_timezone_independent():
    """The same instant expressed in UTC must be caught identically."""
    quote = _quote(datetime(1970, 1, 1, tzinfo=timezone.utc))
    result = assess_quote_timestamp_hygiene(
        quote, study_start=date(2023, 1, 1), study_end=date(2026, 1, 1),
        market_timezone=IST, is_trading_session=True,
        session_open=time(9, 15), session_close=time(15, 30),
    )
    assert result.reasons == (QuoteHygieneExclusionReason.EPOCH_DEFAULT_TIMESTAMP,)


def test_quote_rejects_timestamp_before_study_start():
    quote = _quote(datetime(2020, 1, 1, 10, 0, tzinfo=IST))
    result = assess_quote_timestamp_hygiene(
        quote, study_start=date(2023, 1, 1), study_end=date(2026, 1, 1),
        market_timezone=IST, is_trading_session=True,
        session_open=time(9, 15), session_close=time(15, 30),
    )
    assert result.reasons == (QuoteHygieneExclusionReason.TIMESTAMP_OUTSIDE_STUDY_BOUNDS,)


def test_quote_rejects_timestamp_after_study_end():
    quote = _quote(datetime(2027, 1, 1, 10, 0, tzinfo=IST))
    result = assess_quote_timestamp_hygiene(
        quote, study_start=date(2023, 1, 1), study_end=date(2026, 1, 1),
        market_timezone=IST, is_trading_session=True,
        session_open=time(9, 15), session_close=time(15, 30),
    )
    assert result.reasons == (QuoteHygieneExclusionReason.TIMESTAMP_OUTSIDE_STUDY_BOUNDS,)


def test_quote_rejects_a_non_trading_session_date():
    quote = _quote(datetime(2024, 1, 6, 10, 0, tzinfo=IST))  # a Saturday, say
    result = assess_quote_timestamp_hygiene(
        quote, study_start=date(2023, 1, 1), study_end=date(2026, 1, 1),
        market_timezone=IST, is_trading_session=False,
        session_open=None, session_close=None,
    )
    assert result.reasons == (QuoteHygieneExclusionReason.TIMESTAMP_OUTSIDE_SESSION_BOUNDS,)


def test_quote_rejects_a_timestamp_before_session_open():
    quote = _quote(datetime(2024, 1, 2, 2, 0, tzinfo=IST))
    result = assess_quote_timestamp_hygiene(
        quote, study_start=date(2023, 1, 1), study_end=date(2026, 1, 1),
        market_timezone=IST, is_trading_session=True,
        session_open=time(9, 15), session_close=time(15, 30),
    )
    assert result.reasons == (QuoteHygieneExclusionReason.TIMESTAMP_OUTSIDE_SESSION_BOUNDS,)


def test_quote_rejects_a_timestamp_after_session_close():
    quote = _quote(datetime(2024, 1, 2, 20, 0, tzinfo=IST))
    result = assess_quote_timestamp_hygiene(
        quote, study_start=date(2023, 1, 1), study_end=date(2026, 1, 1),
        market_timezone=IST, is_trading_session=True,
        session_open=time(9, 15), session_close=time(15, 30),
    )
    assert result.reasons == (QuoteHygieneExclusionReason.TIMESTAMP_OUTSIDE_SESSION_BOUNDS,)


def test_quote_admitted_within_study_and_session_bounds():
    quote = _quote(datetime(2024, 1, 2, 10, 0, tzinfo=IST))
    result = assess_quote_timestamp_hygiene(
        quote, study_start=date(2023, 1, 1), study_end=date(2026, 1, 1),
        market_timezone=IST, is_trading_session=True,
        session_open=time(9, 15), session_close=time(15, 30),
    )
    assert result.admitted is True
    assert result.reasons == ()


def test_quote_hygiene_assessment_reasons_invariant():
    with pytest.raises(ValueError, match="reasons"):
        QuoteHygieneAssessment(
            instrument_id="NSE:AAA", ts=datetime(2024, 1, 2, 10, 0, tzinfo=IST),
            admitted=True, reasons=(QuoteHygieneExclusionReason.EPOCH_DEFAULT_TIMESTAMP,),
        )


def test_quote_hygiene_assessment_requires_timezone_aware_ts():
    with pytest.raises(ValueError, match="timezone"):
        QuoteHygieneAssessment(
            instrument_id="NSE:AAA", ts=datetime(2024, 1, 2, 10, 0),
            admitted=True, reasons=(),
        )


# --------------------------------------------------------------------------- #
# 3. Manifest: contract validation, identity, and replay
# --------------------------------------------------------------------------- #


def _manifest(**overrides) -> CohortAdmissionManifest:
    cohort = _cohort()
    defaults = dict(
        study_start=date(2023, 1, 1),
        study_end=date(2026, 1, 1),
        cohort=cohort,
        listing_snapshot=(
            InstrumentListingSnapshot("NSE:AAA", None, None),
            InstrumentListingSnapshot("NSE:BBB", None, None),
        ),
        symbol_day_total=100,
        symbol_day_admitted=100,
        symbol_day_exclusion_counts={
            "SYMBOL_OUTSIDE_SURVIVOR_COHORT": 0,
            "LISTING_DELISTING_AMBIGUOUS": 0,
        },
        symbol_day_admission_digest="digest",
        quote_snapshot_artifact="quote-snapshots/deadbeef.json",
        quote_snapshot_sha256="deadbeef",
        quote_total=10,
        quote_admitted=9,
        quote_exclusion_counts={
            "EPOCH_DEFAULT_TIMESTAMP": 1,
            "TIMESTAMP_OUTSIDE_STUDY_BOUNDS": 0,
            "TIMESTAMP_OUTSIDE_SESSION_BOUNDS": 0,
        },
        quote_rejections=(
            QuoteHygieneAssessment(
                "NSE:AAA", datetime(1970, 1, 1, 5, 30, tzinfo=IST), False,
                (QuoteHygieneExclusionReason.EPOCH_DEFAULT_TIMESTAMP,),
            ),
        ),
    )
    defaults.update(overrides)
    return CohortAdmissionManifest(**defaults)


def test_manifest_rejects_unsupported_contract_version():
    with pytest.raises(ValueError, match="contract"):
        _manifest(contract_version="SOME_OTHER_VERSION")


def test_manifest_rejects_admitted_exceeding_total():
    with pytest.raises(ValueError, match="symbol_day_admitted"):
        _manifest(symbol_day_admitted=101)


def test_manifest_rejects_mismatched_rejection_count():
    with pytest.raises(ValueError, match="quote_rejections"):
        _manifest(quote_total=10, quote_admitted=9, quote_rejections=())


def test_manifest_rejects_unsorted_listing_snapshot():
    with pytest.raises(ValueError, match="listing_snapshot"):
        _manifest(
            listing_snapshot=(
                InstrumentListingSnapshot("NSE:BBB", None, None),
                InstrumentListingSnapshot("NSE:AAA", None, None),
            )
        )


def test_manifest_always_carries_the_cohort_limitation_and_name():
    manifest = _manifest()
    assert manifest.cohort.limitation == manifest.cohort.limitation
    assert "SURVIVOR_COHORT" in manifest.cohort.name


def test_manifest_roundtrip_through_payload_preserves_identity():
    manifest = _manifest()
    with tempfile.TemporaryDirectory() as tmp:
        path = write_immutable_manifest(Path(tmp), manifest)
        reloaded = cohort_admission_manifest_from_payload(path.read_bytes())
    assert reloaded.manifest_id == manifest.manifest_id
    assert reloaded.replay_id == manifest.replay_id
    assert reloaded.cohort == manifest.cohort
    assert reloaded.quote_rejections == manifest.quote_rejections
    assert reloaded.listing_snapshot == manifest.listing_snapshot


def test_write_immutable_manifest_is_idempotent_for_identical_content():
    manifest = _manifest()
    with tempfile.TemporaryDirectory() as tmp:
        first = write_immutable_manifest(Path(tmp), manifest)
        second = write_immutable_manifest(Path(tmp), manifest)
    assert first == second


def test_write_immutable_manifest_detects_conflicting_content():
    """Same manifest_id, different content would mean a broken hash -- this
    proves the atomic-write guard would actually catch that, not just trust
    the filename."""
    manifest = _manifest()
    with tempfile.TemporaryDirectory() as tmp:
        directory = Path(tmp)
        path = write_immutable_manifest(directory, manifest)
        path.write_text('{"tampered": true}\n', encoding="utf-8")
        with pytest.raises(FileExistsError):
            write_immutable_manifest(directory, manifest)
