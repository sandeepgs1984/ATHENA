"""AUX-1b: authoritative DarvaX daily-sweep freshness."""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

from athena.calendar.engine import CalendarEngine
from athena.config.models import MarketConfig
from athena.darvax.screening.freshness import DarvaxSweepFreshnessClassifier
from athena.darvax.screening.models import SweepRecord

IST = ZoneInfo("Asia/Kolkata")
ROOT = Path(__file__).resolve().parents[2]


def classifier() -> DarvaxSweepFreshnessClassifier:
    payload = json.loads((ROOT / "config/market.nse.json").read_text())
    payload.pop("_meta")
    market = MarketConfig.model_validate(payload)
    return DarvaxSweepFreshnessClassifier(
        calendar=CalendarEngine.from_config_dir(ROOT / "config", market),
        timezone_name=market.timezone,
    )


def sweep(
    *,
    data_through: datetime,
    state: str = "completed",
    partial: bool = False,
    digest: str = "current-digest",
    evaluated: int = 10,
) -> SweepRecord:
    return SweepRecord(
        sweep_id="sweep-1",
        started_at=datetime(2026, 8, 19, 15, 31, tzinfo=IST),
        finished_at=datetime(2026, 8, 19, 15, 35, tzinfo=IST),
        state=state,
        as_of=data_through,
        methodology_digest=digest,
        darvax_version="test",
        requested=10,
        evaluated=evaluated,
        tier_counts={},
        partial=partial,
    )


def classify(record: SweepRecord | None, at: datetime):
    return classifier().classify(
        sweep=record,
        current_methodology_digest="current-digest",
        reference_time=at,
    )


def test_current_after_close_uses_that_sessions_date() -> None:
    result = classify(
        sweep(data_through=datetime(2026, 8, 19, 9, 15, tzinfo=IST)),
        datetime(2026, 8, 19, 18, 0, tzinfo=IST),
    )

    assert result.status == "CURRENT"
    assert result.expected_session.isoformat() == "2026-08-19"
    assert result.data_through == result.expected_session


def test_preopen_uses_the_previous_completed_session() -> None:
    result = classify(
        sweep(data_through=datetime(2026, 8, 19, 9, 15, tzinfo=IST)),
        datetime(2026, 8, 20, 8, 30, tzinfo=IST),
    )

    assert result.status == "CURRENT"
    assert result.expected_session.isoformat() == "2026-08-19"


def test_weekend_uses_fridays_completed_session() -> None:
    result = classify(
        sweep(data_through=datetime(2026, 8, 21, 9, 15, tzinfo=IST)),
        datetime(2026, 8, 22, 12, 0, tzinfo=IST),
    )

    assert result.status == "CURRENT"
    assert result.expected_session.isoformat() == "2026-08-21"
    assert result.market_session == "WEEKEND"
    assert result.next_live_at.isoformat().startswith("2026-08-24T09:15:00")


def test_older_market_date_is_stale() -> None:
    result = classify(
        sweep(data_through=datetime(2026, 8, 18, 9, 15, tzinfo=IST)),
        datetime(2026, 8, 19, 18, 0, tzinfo=IST),
    )

    assert result.status == "STALE"
    assert result.data_through.isoformat() == "2026-08-18"
    assert result.expected_session.isoformat() == "2026-08-19"


def test_partial_and_methodology_mismatch_are_integrity_warnings() -> None:
    result = classify(
        sweep(
            data_through=datetime(2026, 8, 19, 9, 15, tzinfo=IST),
            state="cancelled",
            partial=True,
            digest="old-digest",
            evaluated=7,
        ),
        datetime(2026, 8, 19, 18, 0, tzinfo=IST),
    )

    assert result.status == "CURRENT"
    assert result.warnings == (
        "Partial coverage: the sweep was cancelled.",
        "Methodology changed after this sweep was produced.",
        "Coverage incomplete: evaluated 7 of 10.",
    )


def test_running_sweep_is_not_presented_as_authoritative() -> None:
    result = classify(
        sweep(
            data_through=datetime(2026, 8, 19, 9, 15, tzinfo=IST),
            state="running",
        ),
        datetime(2026, 8, 19, 18, 0, tzinfo=IST),
    )

    assert result.status == "UNAVAILABLE"
    assert "only completed or cancelled" in result.explanation


def test_missing_calendar_fails_closed_without_guessing() -> None:
    result = DarvaxSweepFreshnessClassifier(
        calendar=None,
        timezone_name="Asia/Kolkata",
        setup_error="calendar fixture intentionally absent",
    ).classify(
        sweep=None,
        current_methodology_digest="current-digest",
        reference_time=datetime(2026, 8, 19, 18, 0, tzinfo=IST),
    )

    assert result.status == "UNAVAILABLE"
    assert result.explanation == "calendar fixture intentionally absent"
