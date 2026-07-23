"""R1: file-backed daily ops smoke checklist must pass on fixtures."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
SMOKE = REPO / "scripts" / "smoke_file_backed_day.sh"


def test_smoke_script_exists_and_is_executable():
    assert SMOKE.is_file()
    assert SMOKE.stat().st_mode & 0o111, "smoke_file_backed_day.sh must be executable"


def test_file_backed_daily_smoke_passes():
    """Owner mock trading day on tests/data/fileprovider (R1 exit criterion)."""
    result = subprocess.run(
        [str(SMOKE)],
        cwd=REPO,
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0, (
        f"smoke failed ({result.returncode})\n"
        f"stdout:\n{result.stdout}\nstderr:\n{result.stderr}"
    )
    assert "R1 smoke checklist: PASS" in result.stdout


def test_sop_document_exists():
    sop = REPO / "docs" / "ops" / "FILE_BACKED_DAILY_OPS.md"
    text = sop.read_text(encoding="utf-8")
    assert "athena cycle" in text
    assert "athena brief" in text
    assert "smoke_file_backed_day.sh" in text
