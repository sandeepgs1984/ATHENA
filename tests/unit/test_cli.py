"""CLI acceptance: `athena today` prints correct context (Phase 0 exit criterion)."""

from __future__ import annotations

import pytest

from athena.cli import main


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
