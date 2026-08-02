"""CLI acceptance: `athena today` prints correct context (Phase 0 exit criterion)."""

from __future__ import annotations

import shutil
from datetime import date, datetime, timedelta
from decimal import Decimal
from zoneinfo import ZoneInfo

import pytest

from athena.cli import main
from athena.data.ingestion.models import IngestionResult
from athena.data.store.repository import SqliteRepository
from athena.domain.enums import RunTrigger, Timeframe
from athena.domain.market import Candle, Instrument
from athena.ops.owner_candidates import SqliteCandidateStore
from athena.ops.owner_validation import OwnerValidationPipeline

IST = ZoneInfo("Asia/Kolkata")


@pytest.fixture(autouse=True)
def _point_cli_at_fixture_config(config_dir, monkeypatch):
    monkeypatch.setenv("ATHENA_CONFIG_DIR", str(config_dir))


def test_today_normal_day(capsys):
    assert main(["today", "--date", "2026-07-20"]) == 0
    out = capsys.readouterr().out
    assert "session         : NORMAL" in out
    assert "09:15 - 15:30" in out


def test_today_holiday(capsys):
    assert main(["today", "--date", "2026-01-26"]) == 0
    out = capsys.readouterr().out
    assert "session         : HOLIDAY" in out
    assert "Republic Day" in out


def test_today_muhurat(capsys):
    assert main(["today", "--date", "2026-11-08"]) == 0
    out = capsys.readouterr().out
    assert "session         : MUHURAT" in out
    assert "TBD (see NSE circular)" in out


def test_uncovered_year_exits_nonzero(capsys):
    assert main(["today", "--date", "2027-01-01"]) == 1
    assert "No calendar data for 2027" in capsys.readouterr().err


def test_version(capsys):
    assert main(["version"]) == 0
    assert "ATHENA-002 v1.1" in capsys.readouterr().out


def test_config_preview_reports_zero_changes_for_identical_candidate(
    config_dir, tmp_path, monkeypatch, capsys
):
    """M-X9: `athena config-preview` end-to-end — seeds one real decision,
    points the candidate dir at an unmodified copy of the same config, and
    confirms the CLI reports zero changes (a passthrough sanity check
    before testing an actual weight edit, mirrored in test_config_preview.py)."""
    db_path = tmp_path / "cli-preview.db"
    monkeypatch.setenv("ATHENA_DB_PATH", str(db_path))

    repo = SqliteRepository(db_path)
    repo.initialize()
    store = SqliteCandidateStore(repo)
    store.upsert_candidate(symbol="AAA")
    iid = "NSE:AAA"
    repo.upsert_instrument(
        Instrument(instrument_id=iid, symbol="AAA", exchange="NSE", series="EQ", status="ACTIVE")
    )
    candles = []
    for i in range(80):
        day = date(2025, 11, 1) + timedelta(days=i)
        ts = datetime.combine(day, datetime.min.time(), tzinfo=IST).replace(hour=9, minute=15)
        px = Decimal(str(100 + i))
        candles.append(
            Candle(instrument_id=iid, timeframe=Timeframe.D1, ts_open=ts,
                  open=px, high=px + Decimal("2"), low=px - Decimal("1"), close=px + Decimal("1"),
                  volume=1_000_000, source="test")
        )
    repo.add_candles(candles)
    as_of = datetime(2026, 3, 2, 9, 30, tzinfo=IST)
    pipe = OwnerValidationPipeline(repo, config_dir)
    ingestion = IngestionResult(
        as_of=as_of, instruments_upserted=1, candles_fetched=80, candles_written=80,
        quotes_fetched=0, quotes_written=0, datasets_validated=1, datasets_skipped_empty=0,
    )
    pipe.run(RunTrigger.PREMARKET, as_of=as_of, ingestion=ingestion, run_id="seed-run")
    repo.close()

    candidate_dir = tmp_path / "candidate_config"
    shutil.copytree(config_dir, candidate_dir)

    assert main(["config-preview", str(candidate_dir), "--limit", "5"]) == 0
    out = capsys.readouterr().out
    assert "replayed 1 decision(s), skipped 0" in out
    assert "changed under candidate config: 0/1" in out


def test_config_preview_missing_candidate_dir_exits_nonzero(tmp_path, monkeypatch, capsys):
    monkeypatch.setenv("ATHENA_DB_PATH", str(tmp_path / "unused.db"))
    assert main(["config-preview", str(tmp_path / "does-not-exist")]) == 1
    assert "not found" in capsys.readouterr().out
