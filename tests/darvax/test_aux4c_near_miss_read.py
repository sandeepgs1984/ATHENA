"""AUX-4c (DarvaX side): reading AUX-4b's already-persisted near-miss digest.

A pure read of whatever the most recent completed sweep already wrote --
never a recomputation of near-miss detection. Mirrors write_digest's own
fixtures (tests/darvax/test_aux4b_near_miss.py) for the writer half of this
read/write pair.
"""

from __future__ import annotations

import time
from datetime import datetime, timezone
from decimal import Decimal
from pathlib import Path

from athena.darvax.digest import read_latest_digest, resolve_output_dir, write_digest
from athena.darvax.screening.models import DarvasRule, DarvaxSignalType, DarvaxTier, ScreenResult
from athena.darvax.screening.near_miss import near_miss_candidates

BASE = datetime(2026, 8, 20, tzinfo=timezone.utc)


def _result(instrument_id: str = "NSE:VSSL") -> ScreenResult:
    return ScreenResult(
        sweep_id="swp-1", instrument_id=instrument_id, signal_id=f"s-{instrument_id}",
        tier=DarvaxTier.WATCH, signal_type=DarvaxSignalType.INSIDE_TOPMOST_BOX,
        darvas_rule=DarvasRule.A_HOLD_WHILE_IN_TOPMOST_BOX, rank=1,
        close=Decimal("330.00"), explanation="e",
        trigger_price=None,
        box_top=Decimal("335.95"),
        breakout_reference="box_top",
        distance_to_breakout_pct=Decimal("1.5"),
    )


def test_resolve_output_dir_leaves_absolute_paths_untouched(tmp_path):
    assert resolve_output_dir(str(tmp_path)) == tmp_path


def test_resolve_output_dir_resolves_relative_against_cwd():
    resolved = resolve_output_dir("some/relative/dir")
    assert resolved == Path.cwd() / "some/relative/dir"


def test_no_directory_yields_the_empty_shape(tmp_path):
    digest = read_latest_digest(tmp_path / "does-not-exist")
    assert digest == {"sweep_id": None, "as_of": None, "near_miss_count": 0, "near_misses": []}


def test_reads_a_real_written_digest(tmp_path):
    candidates = near_miss_candidates([_result()], max_pct=Decimal("2"))
    write_digest(tmp_path, "swp-1", BASE, candidates)

    digest = read_latest_digest(tmp_path)

    assert digest["sweep_id"] == "swp-1"
    assert digest["near_miss_count"] == 1
    assert digest["near_misses"][0]["symbol"] == "VSSL"


def test_picks_the_most_recently_written_sweeps_digest(tmp_path):
    """sweep_id "swp-a-older" is written FIRST and "swp-z-newer" SECOND --
    deliberately the reverse of alphabetical order, so this only passes if
    the reader actually sorts by mtime rather than by filename."""
    candidates = near_miss_candidates([_result()], max_pct=Decimal("2"))
    write_digest(tmp_path, "swp-a-older", BASE, candidates)
    time.sleep(0.01)
    write_digest(tmp_path, "swp-z-newer", BASE, candidates)

    digest = read_latest_digest(tmp_path)

    assert digest["sweep_id"] == "swp-z-newer"


def test_corrupt_digest_file_degrades_to_empty_rather_than_raising(tmp_path):
    (tmp_path / "near-miss-swp-broken.json").write_text("{not valid json", encoding="utf-8")

    digest = read_latest_digest(tmp_path)

    assert digest == {"sweep_id": None, "as_of": None, "near_miss_count": 0, "near_misses": []}
