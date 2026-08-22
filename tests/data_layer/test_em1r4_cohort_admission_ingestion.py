"""EM-1r4: cohort-admission/quote-hygiene orchestration (Data layer).

No provider and no network call is exercised here -- unlike EM-1r2/EM-1r3's
ingestion tests, this service only reads canonical persisted records through
the real repository and resolves calendar facts through a fake calendar,
exactly mirroring test_em1r3_intraday_reconstruction_ingestion.py's own
``_Calendar`` fake convention.
"""

from __future__ import annotations

from datetime import date, datetime, time
from decimal import Decimal
from pathlib import Path
from zoneinfo import ZoneInfo

import pytest

from athena.data.cohort_admission_ingestion import CohortAdmissionIngestionService
from athena.data.store.repository import SqliteRepository
from athena.domain.enums import SessionType
from athena.domain.market import CalendarContext, Instrument, Quote
from athena.errors import CalendarError
from athena.explosive_move.cohort_admission import (
    CohortAdmissionExclusionReason,
    QuoteHygieneExclusionReason,
)

IST = ZoneInfo("Asia/Kolkata")
UNIVERSE = "athena_core"


class _Calendar:
    """NORMAL Mon-Fri 09:15-15:30 IST, WEEKEND Sat/Sun -- deterministic and
    self-contained, same convention as EM-1r3's own fake."""

    def context_for(self, session_date: date) -> CalendarContext:
        is_weekend = session_date.weekday() >= 5
        return CalendarContext(
            context_date=session_date,
            session_type=SessionType.WEEKEND if is_weekend else SessionType.NORMAL,
            exchange="NSE",
            timezone="Asia/Kolkata",
            open_time=None if is_weekend else time(9, 15),
            close_time=None if is_weekend else time(15, 30),
        )


class _CalendarWithLimitedCoverage(_Calendar):
    """Same as _Calendar, but raises CalendarError outside a covered-years
    set -- mirrors the real CalendarEngine's own behavior (it only has
    holiday/expiry data loaded for the years config/calendar/*.json
    actually covers, e.g. just the current year in production)."""

    def __init__(self, covered_years: set[int]) -> None:
        self._covered_years = covered_years

    def context_for(self, session_date: date) -> CalendarContext:
        if session_date.year not in self._covered_years:
            raise CalendarError(f"No calendar data for {session_date.year}")
        return super().context_for(session_date)


@pytest.fixture()
def repository(tmp_path: Path) -> SqliteRepository:
    repo = SqliteRepository(tmp_path / "athena.db")
    repo.initialize()
    yield repo
    repo.close()


def _instrument(instrument_id: str, **overrides) -> Instrument:
    symbol = instrument_id.split(":")[-1]
    defaults = dict(
        instrument_id=instrument_id, symbol=symbol, exchange="NSE", series="EQ",
    )
    defaults.update(overrides)
    return Instrument(**defaults)


def _quote(instrument_id: str, ts: datetime) -> Quote:
    return Quote(instrument_id=instrument_id, ts=ts, last_price=Decimal("100"), volume=1_000, source="kite")


def _seed(repository: SqliteRepository, *, instruments, universe_ids, quotes) -> None:
    for instrument in instruments:
        repository.upsert_instrument(instrument)
    repository.save_resolved_universe(UNIVERSE, universe_ids, resolved_at=datetime(2026, 8, 21, tzinfo=IST))
    repository.add_quotes(quotes)


def _service(repository: SqliteRepository, evidence_root: Path) -> CohortAdmissionIngestionService:
    return CohortAdmissionIngestionService(
        repository=repository, calendar=_Calendar(),
        evidence_root=evidence_root, timezone_name="Asia/Kolkata",
    )


# --------------------------------------------------------------------------- #
# 1. Cohort validation, mirroring corporate_action_ingestion.py's own guard
# --------------------------------------------------------------------------- #


def test_run_raises_when_resolved_universe_references_unknown_instrument(
    repository: SqliteRepository, tmp_path: Path
):
    repository.save_resolved_universe(UNIVERSE, ["NSE:GHOST"], resolved_at=datetime(2026, 8, 21, tzinfo=IST))
    with pytest.raises(ValueError, match="unknown instrument"):
        _service(repository, tmp_path).run(
            universe_name=UNIVERSE, cohort_resolution_date=date(2026, 8, 21),
            study_start=date(2024, 1, 1), study_end=date(2024, 1, 5),
        )


# --------------------------------------------------------------------------- #
# 2. Real end-to-end run: cohort admission + quote hygiene together
# --------------------------------------------------------------------------- #


def test_run_admits_cohort_symbol_days_and_rejects_epoch_and_out_of_bounds_quotes(
    repository: SqliteRepository, tmp_path: Path
):
    _seed(
        repository,
        instruments=[_instrument("NSE:AAA"), _instrument("NSE:BBB")],
        universe_ids=["NSE:AAA", "NSE:BBB"],
        quotes=[
            _quote("NSE:AAA", datetime(1970, 1, 1, 5, 30, tzinfo=IST)),  # epoch
            _quote("NSE:AAA", datetime(2020, 1, 1, 10, 0, tzinfo=IST)),  # before study
            _quote("NSE:AAA", datetime(2024, 1, 2, 2, 0, tzinfo=IST)),  # before session open
            _quote("NSE:AAA", datetime(2024, 1, 2, 10, 0, tzinfo=IST)),  # good
            _quote("NSE:BBB", datetime(2024, 1, 3, 11, 0, tzinfo=IST)),  # good
        ],
    )
    # study window Mon 2024-01-01 .. Fri 2024-01-05: 5 calendar days, weekend
    # excluded by the fake calendar -> Mon-Fri are all NORMAL sessions here.
    result = _service(repository, tmp_path).run(
        universe_name=UNIVERSE, cohort_resolution_date=date(2026, 8, 21),
        study_start=date(2024, 1, 1), study_end=date(2024, 1, 5),
    )
    manifest = result.manifest

    assert manifest.cohort.instrument_ids == ("NSE:AAA", "NSE:BBB")
    # 2 instruments x 5 NORMAL sessions (Mon-Fri) = 10 symbol-days, all admitted
    # (no listed/delisted dates recorded for either instrument).
    assert manifest.symbol_day_total == 10
    assert manifest.symbol_day_admitted == 10
    assert manifest.symbol_day_exclusion_counts == {
        CohortAdmissionExclusionReason.SYMBOL_OUTSIDE_SURVIVOR_COHORT.value: 0,
        CohortAdmissionExclusionReason.LISTING_DELISTING_AMBIGUOUS.value: 0,
    }

    assert manifest.quote_total == 5
    assert manifest.quote_admitted == 2
    assert manifest.quote_exclusion_counts == {
        QuoteHygieneExclusionReason.EPOCH_DEFAULT_TIMESTAMP.value: 1,
        QuoteHygieneExclusionReason.TIMESTAMP_OUTSIDE_STUDY_BOUNDS.value: 1,
        QuoteHygieneExclusionReason.TIMESTAMP_OUTSIDE_SESSION_BOUNDS.value: 1,
    }
    assert len(manifest.quote_rejections) == 3
    rejected_reasons = {r.reasons[0] for r in manifest.quote_rejections}
    assert rejected_reasons == {
        QuoteHygieneExclusionReason.EPOCH_DEFAULT_TIMESTAMP,
        QuoteHygieneExclusionReason.TIMESTAMP_OUTSIDE_STUDY_BOUNDS,
        QuoteHygieneExclusionReason.TIMESTAMP_OUTSIDE_SESSION_BOUNDS,
    }
    # the cohort's own frozen limitation must appear in the manifest, per
    # EM-1r4 acceptance ("the cohort name and limitation appear in every
    # manifest and report").
    assert "not point-in-time historical" in manifest.cohort.limitation


def test_run_excludes_symbol_day_on_listing_delisting_ambiguity(
    repository: SqliteRepository, tmp_path: Path
):
    _seed(
        repository,
        instruments=[
            _instrument("NSE:AAA", listed_date=date(2024, 1, 3)),  # listed mid-window
            _instrument("NSE:BBB"),
        ],
        universe_ids=["NSE:AAA", "NSE:BBB"],
        quotes=[],
    )
    result = _service(repository, tmp_path).run(
        universe_name=UNIVERSE, cohort_resolution_date=date(2026, 8, 21),
        study_start=date(2024, 1, 1), study_end=date(2024, 1, 5),
    )
    manifest = result.manifest
    # NSE:AAA: Mon/Tue (Jan 1-2) excluded (listed_date after session), Wed-Fri admitted.
    # NSE:BBB: all 5 sessions admitted.
    assert manifest.symbol_day_total == 10
    assert manifest.symbol_day_admitted == 8
    assert manifest.symbol_day_exclusion_counts[
        CohortAdmissionExclusionReason.LISTING_DELISTING_AMBIGUOUS.value
    ] == 2


# --------------------------------------------------------------------------- #
# 3. Deterministic, provider-free replay
# --------------------------------------------------------------------------- #


def test_replay_reproduces_identical_manifest_identity(repository: SqliteRepository, tmp_path: Path):
    _seed(
        repository,
        instruments=[_instrument("NSE:AAA"), _instrument("NSE:BBB")],
        universe_ids=["NSE:AAA", "NSE:BBB"],
        quotes=[
            _quote("NSE:AAA", datetime(1970, 1, 1, 5, 30, tzinfo=IST)),
            _quote("NSE:AAA", datetime(2024, 1, 2, 10, 0, tzinfo=IST)),
        ],
    )
    service = _service(repository, tmp_path)
    result = service.run(
        universe_name=UNIVERSE, cohort_resolution_date=date(2026, 8, 21),
        study_start=date(2024, 1, 1), study_end=date(2024, 1, 5),
    )
    replayed = service.replay(result.manifest_path)
    assert replayed.replay_verified is True
    assert replayed.manifest.replay_id == result.manifest.replay_id
    assert replayed.manifest.manifest_id == result.manifest.manifest_id


def test_replay_rejects_tampered_quote_snapshot_artifact(repository: SqliteRepository, tmp_path: Path):
    _seed(
        repository,
        instruments=[_instrument("NSE:AAA")],
        universe_ids=["NSE:AAA"],
        quotes=[_quote("NSE:AAA", datetime(2024, 1, 2, 10, 0, tzinfo=IST))],
    )
    service = _service(repository, tmp_path)
    result = service.run(
        universe_name=UNIVERSE, cohort_resolution_date=date(2026, 8, 21),
        study_start=date(2024, 1, 1), study_end=date(2024, 1, 5),
    )
    artifact_path = tmp_path / result.manifest.quote_snapshot_artifact
    artifact_path.write_bytes(b"[]\n")

    with pytest.raises(ValueError, match="digest mismatch"):
        service.replay(result.manifest_path)


def test_replay_never_re_reads_the_live_mutable_instruments_table(
    repository: SqliteRepository, tmp_path: Path
):
    """Replay must be reproducible even after the live canonical tables have
    since grown -- it recomputes from the manifest's own frozen listing
    snapshot and quote artifact, never a fresh repository read."""

    _seed(
        repository,
        instruments=[_instrument("NSE:AAA")],
        universe_ids=["NSE:AAA"],
        quotes=[_quote("NSE:AAA", datetime(2024, 1, 2, 10, 0, tzinfo=IST))],
    )
    service = _service(repository, tmp_path)
    result = service.run(
        universe_name=UNIVERSE, cohort_resolution_date=date(2026, 8, 21),
        study_start=date(2024, 1, 1), study_end=date(2024, 1, 5),
    )
    # Mutate the live table after the manifest was written: a real listing
    # date now appears where none existed at manifest-build time.
    repository.upsert_instrument(_instrument("NSE:AAA", listed_date=date(2024, 1, 3)))
    repository.add_quotes([_quote("NSE:AAA", datetime(2024, 1, 4, 10, 0, tzinfo=IST))])

    replayed = service.replay(result.manifest_path)
    assert replayed.replay_verified is True
    assert replayed.manifest.symbol_day_total == result.manifest.symbol_day_total
    assert replayed.manifest.quote_total == result.manifest.quote_total


# --------------------------------------------------------------------------- #
# 4. Real-world calendar coverage gaps must exclude, never crash the run
# --------------------------------------------------------------------------- #


def test_quote_outside_calendar_coverage_is_excluded_not_a_crash(
    repository: SqliteRepository, tmp_path: Path
):
    """Owner-environment finding: production's real calendar config only has
    holiday/expiry data loaded for the current year. An epoch-default quote
    (1970) -- or any other timestamp landing in a year the calendar has
    never heard of -- must still be excluded cleanly, not raise CalendarError
    and abort the whole run over one bad row."""

    _seed(
        repository,
        instruments=[_instrument("NSE:AAA")],
        universe_ids=["NSE:AAA"],
        quotes=[
            _quote("NSE:AAA", datetime(1970, 1, 1, 5, 30, tzinfo=IST)),  # epoch, year 1970
            _quote("NSE:AAA", datetime(2024, 1, 2, 10, 0, tzinfo=IST)),  # good
        ],
    )
    service = CohortAdmissionIngestionService(
        repository=repository,
        calendar=_CalendarWithLimitedCoverage({2024}),  # deliberately excludes 1970
        evidence_root=tmp_path,
        timezone_name="Asia/Kolkata",
    )
    result = service.run(
        universe_name=UNIVERSE, cohort_resolution_date=date(2026, 8, 21),
        study_start=date(2024, 1, 1), study_end=date(2024, 1, 5),
    )
    manifest = result.manifest
    assert manifest.quote_total == 2
    assert manifest.quote_admitted == 1
    assert manifest.quote_exclusion_counts[
        QuoteHygieneExclusionReason.EPOCH_DEFAULT_TIMESTAMP.value
    ] == 1
