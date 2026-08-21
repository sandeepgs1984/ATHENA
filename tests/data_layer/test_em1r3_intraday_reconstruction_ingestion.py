from datetime import date, datetime, time
from decimal import Decimal
from pathlib import Path
from zoneinfo import ZoneInfo

import pytest

from athena.data.intraday_reconstruction_ingestion import (
    IntradayReconstructionIngestionService,
)
from athena.domain.enums import SessionType, Timeframe
from athena.domain.market import CalendarContext, Candle
from athena.explosive_move.corporate_action_coverage import (
    SURVIVOR_COHORT_LIMITATION,
    SURVIVOR_COHORT_NAME,
    SurvivorCohort,
)
from athena.explosive_move.intraday_reconstruction import (
    RepairType,
    SessionExclusionReason,
)

DAY = date(2026, 8, 20)
TZ = ZoneInfo("Asia/Kolkata")


class _Calendar:
    def context_for(self, session_date: date) -> CalendarContext:
        return CalendarContext(
            context_date=session_date,
            session_type=SessionType.NORMAL,
            exchange="NSE",
            timezone="Asia/Kolkata",
            open_time=time(9, 15),
            close_time=time(9, 25),
        )


class _Provider:
    name = "fake-kite"

    def __init__(self) -> None:
        self.calls: list[str] = []

    def intraday_candles(
        self,
        instrument_id: str,
        timeframe: Timeframe,
        start: datetime,
        end: datetime,
    ) -> list[Candle]:
        del end
        self.calls.append(instrument_id)
        if instrument_id == "NSE:BBB":
            raise RuntimeError("authoritative retrieval failed")
        rows = [_candle(instrument_id, start)]
        if instrument_id == "NSE:AAA":
            rows.extend(
                (
                    _candle(instrument_id, start),
                    _candle(instrument_id, start.replace(minute=20)),
                )
            )
        return rows


def _candle(instrument_id: str, ts_open: datetime) -> Candle:
    return Candle(
        instrument_id=instrument_id,
        timeframe=Timeframe.M5,
        ts_open=ts_open,
        open=Decimal("100"),
        high=Decimal("102"),
        low=Decimal("99"),
        close=Decimal("100"),
        volume=1_000,
        source="kite",
        adjusted=False,
    )


def _cohort() -> SurvivorCohort:
    return SurvivorCohort(
        name=SURVIVOR_COHORT_NAME,
        universe_name="NIFTY_500",
        resolution_date=DAY,
        instrument_ids=("NSE:AAA", "NSE:BBB", "NSE:CCC"),
        group_effective_dates=(("NIFTY_500", DAY),),
        limitation=SURVIVOR_COHORT_LIMITATION,
    )


def _service(
    evidence_root: Path,
    *,
    provider: _Provider | None,
) -> IntradayReconstructionIngestionService:
    return IntradayReconstructionIngestionService(
        calendar=_Calendar(),  # type: ignore[arg-type]
        evidence_root=evidence_root,
        timezone_name="Asia/Kolkata",
        provider=provider,  # type: ignore[arg-type]
        clock=lambda: datetime(2026, 8, 21, 12, 0, tzinfo=TZ),
    )


def test_capture_records_repairs_exclusions_and_provider_free_replay(
    tmp_path: Path,
) -> None:
    provider = _Provider()
    captured = _service(tmp_path, provider=provider).capture(
        cohort=_cohort(),
        study_start=DAY,
        study_end=DAY,
    )

    assert provider.calls == ["NSE:AAA", "NSE:BBB", "NSE:CCC"]
    assert captured.manifest.admitted_session_count == 1
    assert captured.manifest.excluded_session_count == 2
    assert captured.manifest.repair_counts == {
        RepairType.AUTHORITATIVE_REINGESTION.value: 2,
        RepairType.IDENTICAL_DUPLICATE_COLLAPSE.value: 1,
    }
    assert captured.manifest.exclusion_counts[
        SessionExclusionReason.RETRIEVAL_FAILED.value
    ] == 1
    assert captured.manifest.exclusion_counts[
        SessionExclusionReason.MISSING_SLOT.value
    ] == 1
    assert captured.manifest.population_basis == "SURVIVOR_COHORT"

    replayed = _service(tmp_path, provider=None).replay(captured.manifest_path)

    assert replayed.replay_verified is True
    assert replayed.manifest.replay_id == captured.manifest.replay_id


def test_replay_rejects_tampered_source_artifact(tmp_path: Path) -> None:
    captured = _service(tmp_path, provider=_Provider()).capture(
        cohort=_cohort(),
        study_start=DAY,
        study_end=DAY,
    )
    source = captured.manifest.source_captures[0]
    (tmp_path / source.artifact).write_bytes(b"[]\n")

    with pytest.raises(ValueError, match="artifact digest mismatch"):
        _service(tmp_path, provider=None).replay(captured.manifest_path)
