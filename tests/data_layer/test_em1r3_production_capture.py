"""EM-1r3 production capture: resumable, checkpointed batching, and the
retry wrapper for transient provider failures. Owner-authorized 2026-08-22
for a real run against the live Kite API across the full survivor cohort
and study window -- this file proves the orchestration is correct against
fakes before any real network call is made.

Does not touch EM-1r3's own frozen admission contract
(intraday_reconstruction.py) or its existing ingestion service
(intraday_reconstruction_ingestion.py) -- both are exercised exactly as
already approved, through this new resumable wrapper.
"""

from __future__ import annotations

from datetime import date, datetime, time
from decimal import Decimal
from pathlib import Path
from zoneinfo import ZoneInfo

import pytest

from athena.data.intraday_production_capture import (
    ProductionCaptureCheckpoint,
    ProductionIntradayCaptureRunner,
    _classify_failure_detail,
    _is_truncation_marker,
)
from athena.data.intraday_reconstruction_ingestion import (
    IntradayReconstructionIngestionService,
)
from athena.data.retrying_provider import RetryingMarketDataProvider
from athena.domain.enums import SessionType, Timeframe
from athena.domain.market import CalendarContext, Candle
from athena.errors import ProviderError
from athena.explosive_move.corporate_action_coverage import (
    SURVIVOR_COHORT_LIMITATION,
    SURVIVOR_COHORT_NAME,
    SurvivorCohort,
)

DAY = date(2026, 8, 20)
TZ = ZoneInfo("Asia/Kolkata")


class _Calendar:
    def context_for(self, session_date: date) -> CalendarContext:
        return CalendarContext(
            context_date=session_date, session_type=SessionType.NORMAL,
            exchange="NSE", timezone="Asia/Kolkata",
            open_time=time(9, 15), close_time=time(9, 25),
        )


def _candle(instrument_id: str, ts_open: datetime) -> Candle:
    return Candle(
        instrument_id=instrument_id, timeframe=Timeframe.M5, ts_open=ts_open,
        open=Decimal("100"), high=Decimal("102"), low=Decimal("99"),
        close=Decimal("100"), volume=1_000, source="kite", adjusted=False,
    )


class _ScriptedProvider:
    """Returns a full clean session for every instrument by default, except
    for ids named in ``fail_ids`` (raise, modeling a retrieval failure) or
    ``fail_until_call`` (raise ProviderError on the Nth call for that id,
    modeling a transient failure the retry wrapper should recover from)."""

    name = "fake-kite"

    def __init__(self, fail_ids: set[str] | None = None, transient_fail_ids: dict[str, int] | None = None):
        self.calls: list[str] = []
        self._fail_ids = fail_ids or set()
        self._transient_fail_ids = dict(transient_fail_ids or {})
        self._attempt_counts: dict[str, int] = {}

    def intraday_candles(self, instrument_id, timeframe, start, end):
        del timeframe, end
        self.calls.append(instrument_id)
        if instrument_id in self._fail_ids:
            raise RuntimeError("permanent retrieval failure")
        remaining = self._transient_fail_ids.get(instrument_id, 0)
        if remaining > 0:
            self._transient_fail_ids[instrument_id] = remaining - 1
            raise ProviderError("kite network failure on /historical: timed out")
        # The fake calendar's 9:15-9:25 window expects slots at :15 and :20
        # (see expected_intraday_opens) -- both must be returned or the
        # session excludes as MISSING_SLOT instead of admitting, exactly
        # like test_em1r3_intraday_reconstruction_ingestion.py's own fixture.
        return [_candle(instrument_id, start), _candle(instrument_id, start.replace(minute=20))]


def _cohort(instrument_ids: tuple[str, ...]) -> SurvivorCohort:
    return SurvivorCohort(
        name=SURVIVOR_COHORT_NAME, universe_name="athena_core", resolution_date=DAY,
        instrument_ids=instrument_ids, group_effective_dates=(("athena_core", DAY),),
        limitation=SURVIVOR_COHORT_LIMITATION,
    )


def _runner(
    tmp_path: Path, provider, batch_size: int = 2
) -> tuple[ProductionIntradayCaptureRunner, RetryingMarketDataProvider]:
    wrapper = RetryingMarketDataProvider(inner=provider, sleep=lambda s: None)
    service = IntradayReconstructionIngestionService(
        calendar=_Calendar(), evidence_root=tmp_path / "evidence",
        timezone_name="Asia/Kolkata", provider=wrapper,
        clock=lambda: datetime(2026, 8, 21, 12, 0, tzinfo=TZ),
    )
    runner = ProductionIntradayCaptureRunner(
        service=service, provider_stats=wrapper,
        checkpoint_path=tmp_path / "checkpoint.json",
        evidence_root=tmp_path / "evidence", batch_size=batch_size,
    )
    return runner, wrapper


# --------------------------------------------------------------------------- #
# 1. Basic batched run
# --------------------------------------------------------------------------- #


def test_run_processes_the_whole_cohort_across_multiple_batches(tmp_path: Path):
    provider = _ScriptedProvider()
    runner, _ = _runner(tmp_path, provider, batch_size=2)
    cohort = _cohort(("NSE:AAA", "NSE:BBB", "NSE:CCC", "NSE:DDD", "NSE:EEE"))

    summary = runner.run(
        capture_run_id="em1r3-prod-test", cohort=cohort,
        study_start=DAY, study_end=DAY, expected_session_count=5,
    )

    assert summary.expected_symbol_count == 5
    assert set(summary.symbols_attempted) == set(cohort.instrument_ids)
    assert summary.admitted_sessions == 5
    assert summary.missing_sessions == 0
    assert len(summary.batch_manifest_paths) == 3  # 2 + 2 + 1
    assert summary.resumption_count == 0
    assert set(provider.calls) == set(cohort.instrument_ids)


# --------------------------------------------------------------------------- #
# 2. Resumability -- the actual point of this whole layer
# --------------------------------------------------------------------------- #


class _SimulatedCrash(Exception):
    """Stands in for the process dying mid-run (killed, OOM, network drop
    at the orchestration level) -- something that stops the loop between
    batches, not a per-session provider failure (which capture() already
    tolerates on its own and is tested separately)."""


def test_run_resumes_and_never_re_requests_already_completed_instruments(tmp_path: Path):
    cohort = _cohort(("NSE:AAA", "NSE:BBB", "NSE:CCC", "NSE:DDD"))

    # First "attempt": the SAME full cohort both times -- a real restart
    # always re-requests the same population, so the crash must happen
    # mid-loop, not because the caller passed a smaller cohort. Interrupt
    # right after the first batch (AAA, BBB) checkpoints, before the second
    # batch (CCC, DDD) would run.
    provider1 = _ScriptedProvider()
    runner1, _ = _runner(tmp_path, provider1, batch_size=2)

    def _crash_after_first_batch(batch_ids, checkpoint):
        if batch_ids == ("NSE:AAA", "NSE:BBB"):
            raise _SimulatedCrash("process died right after checkpointing batch 1")

    with pytest.raises(_SimulatedCrash):
        runner1.run(
            capture_run_id="em1r3-prod-resume-test", cohort=cohort,
            study_start=DAY, study_end=DAY, expected_session_count=4,
            on_batch_complete=_crash_after_first_batch,
        )
    assert provider1.calls == ["NSE:AAA", "NSE:BBB"]

    checkpoint_before = ProductionCaptureCheckpoint.from_dict(
        __import__("json").loads((tmp_path / "checkpoint.json").read_text())
    )
    assert set(checkpoint_before.completed_instrument_ids) == {"NSE:AAA", "NSE:BBB"}
    assert checkpoint_before.finished_at is None  # never reached the end of run()

    # "Resume": a fresh provider and runner (a real restarted process would
    # rebuild both), the SAME checkpoint file, the SAME full cohort.
    provider2 = _ScriptedProvider()
    runner2, _ = _runner(tmp_path, provider2, batch_size=2)
    summary = runner2.run(
        capture_run_id="em1r3-prod-resume-test", cohort=cohort,
        study_start=DAY, study_end=DAY, expected_session_count=4,
    )

    # The resumed provider must NEVER see the already-completed instruments.
    assert "NSE:AAA" not in provider2.calls
    assert "NSE:BBB" not in provider2.calls
    assert set(provider2.calls) == {"NSE:CCC", "NSE:DDD"}
    assert set(summary.symbols_attempted) == set(cohort.instrument_ids)
    assert summary.admitted_sessions == 4
    assert summary.resumption_count == 1
    assert summary.finished_at is not None


def test_checkpoint_rejects_a_different_cohort_at_the_same_path(tmp_path: Path):
    provider = _ScriptedProvider()
    runner, _ = _runner(tmp_path, provider)
    runner.run(
        capture_run_id="run-x", cohort=_cohort(("NSE:AAA",)),
        study_start=DAY, study_end=DAY, expected_session_count=1,
    )
    different_cohort = _cohort(("NSE:ZZZ",))
    with pytest.raises(ValueError, match="different capture_run_id/cohort"):
        runner.run(
            capture_run_id="run-x", cohort=different_cohort,
            study_start=DAY, study_end=DAY, expected_session_count=1,
        )


# --------------------------------------------------------------------------- #
# 3. Summary correctly classifies admitted / missing / partial / rejected
# --------------------------------------------------------------------------- #


def test_summary_counts_missing_sessions_from_retrieval_failures(tmp_path: Path):
    provider = _ScriptedProvider(fail_ids={"NSE:BBB"})
    runner, _ = _runner(tmp_path, provider, batch_size=5)
    cohort = _cohort(("NSE:AAA", "NSE:BBB"))

    summary = runner.run(
        capture_run_id="run-missing", cohort=cohort,
        study_start=DAY, study_end=DAY, expected_session_count=2,
    )
    assert summary.admitted_sessions == 1
    assert summary.missing_sessions == 1
    assert summary.partial_sessions == 0
    assert summary.rejected_sessions == 0
    assert summary.provider_failure_counts == {"other": 1}


# --------------------------------------------------------------------------- #
# 4. Retry stats flow through from the wrapped provider into the summary
# --------------------------------------------------------------------------- #


def test_summary_reports_retries_from_the_wrapped_provider(tmp_path: Path):
    provider = _ScriptedProvider(transient_fail_ids={"NSE:AAA": 2})
    runner, wrapper = _runner(tmp_path, provider, batch_size=5)
    cohort = _cohort(("NSE:AAA", "NSE:BBB"))

    summary = runner.run(
        capture_run_id="run-retry", cohort=cohort,
        study_start=DAY, study_end=DAY, expected_session_count=2,
    )
    assert summary.admitted_sessions == 2  # AAA recovers after 2 transient failures
    assert summary.retries_performed == 2
    assert summary.kite_requests_issued == 4  # 3 for AAA (2 fail + 1 success) + 1 for BBB
    assert summary.missing_sessions == 0
    assert wrapper.stats.retry_exhausted_failures == 0


# --------------------------------------------------------------------------- #
# 5. Recent-history-truncation observation (owner-authorized 2026-08-22
#    diagnostic pattern): a neutral, evidence-only classification, never
#    asserted as confirmed Kite behavior.
# --------------------------------------------------------------------------- #


@pytest.mark.parametrize(
    "detail,expected",
    [
        ("missing exact slot 2026-08-17T15:15:00+05:30", True),
        ("missing exact slot 2026-08-17T15:20:00+05:30", True),
        ("missing exact slot 2026-08-17T15:25:00+05:30", True),
        ("missing exact slot 2026-08-17T15:10:00+05:30", False),
        ("missing exact slot 2026-08-17T11:00:00+05:30", False),  # mid-session gap, unrelated
        (None, False),
        ("", False),
    ],
)
def test_is_truncation_marker_matches_only_the_late_session_pattern(detail, expected):
    assert _is_truncation_marker(detail) is expected


@pytest.mark.parametrize(
    "detail,expected",
    [
        ("ProviderError: kite network failure on /historical/123/5minute: timed out", "network_failure"),
        ("ProviderError: kite HTTP 502 on /historical/123/5minute: bad gateway", "http_5xx"),
        ("ProviderError: kite HTTP 403 on /historical/123/5minute: forbidden", "http_4xx"),
        ("RuntimeError: something else entirely", "other"),
    ],
)
def test_classify_failure_detail_groups_meaningfully(detail, expected):
    assert _classify_failure_detail(detail) == expected


class _WideCalendar:
    """A real-shaped 09:15-15:30 session, unlike the other tests' tiny
    9:15-9:25 fixture -- needed here because the truncation marker is
    defined by absolute clock time (>= 15:15), not by session width."""

    def context_for(self, session_date: date) -> CalendarContext:
        return CalendarContext(
            context_date=session_date, session_type=SessionType.NORMAL,
            exchange="NSE", timezone="Asia/Kolkata",
            open_time=time(9, 15), close_time=time(15, 30),
        )


class _TruncatingProvider:
    """Returns every expected slot except the last three (15:15, 15:20,
    15:25) for every instrument/session -- mirroring exactly the pattern
    the 2026-08-22 diagnostic measured against the real Kite API."""

    name = "fake-kite"

    def intraday_candles(self, instrument_id, timeframe, start, end):
        del timeframe
        candles = []
        cursor = start
        while cursor <= end and cursor.time() < time(15, 15):
            candles.append(_candle(instrument_id, cursor))
            cursor = cursor.replace(minute=(cursor.minute + 5) % 60, hour=cursor.hour + (cursor.minute + 5) // 60)
        return candles


def test_summary_reports_recent_history_truncation_as_a_neutral_observation(tmp_path: Path):
    provider = _TruncatingProvider()
    wrapper = RetryingMarketDataProvider(inner=provider, sleep=lambda s: None)
    service = IntradayReconstructionIngestionService(
        calendar=_WideCalendar(), evidence_root=tmp_path / "evidence",
        timezone_name="Asia/Kolkata", provider=wrapper,
        clock=lambda: datetime(2026, 8, 21, 12, 0, tzinfo=TZ),
    )
    runner = ProductionIntradayCaptureRunner(
        service=service, provider_stats=wrapper,
        checkpoint_path=tmp_path / "checkpoint.json",
        evidence_root=tmp_path / "evidence", batch_size=5,
    )
    cohort = _cohort(("NSE:AAA", "NSE:BBB"))

    summary = runner.run(
        capture_run_id="run-truncation", cohort=cohort,
        study_start=DAY, study_end=DAY, expected_session_count=2,
    )

    assert summary.admitted_sessions == 0
    assert summary.partial_sessions == 2
    observation = summary.recent_history_truncation
    assert observation.label == "RECENT_PROVIDER_HISTORY_TRUNCATION"
    assert "hypothesis" in observation.hypothesis.lower()
    assert "not confirmed" in observation.hypothesis.lower()
    assert observation.affected_session_count == 2
    assert set(observation.affected_instrument_ids) == {"NSE:AAA", "NSE:BBB"}
    assert observation.earliest_affected_date == DAY.isoformat()
    assert observation.latest_affected_date == DAY.isoformat()
    assert observation.consistent_across_symbols is True
    assert summary.recent_truncation_percent_of_population == 100.0
