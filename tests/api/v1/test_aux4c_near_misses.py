"""Unit tests for DecisionsService.get_near_misses (AUX-4c, ATHENA side).

A pure read of AUX-4a's already-persisted daily briefing file -- never a
recomputation. Isolated from the real artifacts/briefings directory by
pointing notifications.json's channels.file.output_dir at an absolute
tmp_path, the same isolation discipline used throughout this track.
"""

from __future__ import annotations

import json
import time
from pathlib import Path

import pytest
from tests.conftest import rewrite_json

from athena.api.v1.providers.in_memory import InMemoryDecisionProvider
from athena.api.v1.services.decisions_service import DecisionsService


def _point_output_dir_at(config_dir: Path, output_dir: Path) -> None:
    rewrite_json(
        config_dir / "notifications.json",
        lambda d: d["channels"]["file"].__setitem__("output_dir", str(output_dir)),
    )


def _write_briefing(output_dir: Path, filename: str, payload: dict) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)
    (output_dir / filename).write_text(json.dumps(payload), encoding="utf-8")


@pytest.fixture()
def provider() -> InMemoryDecisionProvider:
    return InMemoryDecisionProvider()


def test_no_briefings_dir_yields_empty_digest_with_none_as_of(tmp_path, config_dir, provider):
    _point_output_dir_at(config_dir, tmp_path / "does-not-exist")
    service = DecisionsService(provider, config_dir=config_dir)

    digest = service.get_near_misses()

    assert digest.as_of is None
    assert digest.briefing_id is None
    assert digest.count == 0
    assert digest.items == []


def test_reads_the_persisted_briefing_file(tmp_path, config_dir, provider):
    out = tmp_path / "briefings"
    _point_output_dir_at(config_dir, out)
    _write_briefing(out, "brief-2026-08-20.json", {
        "briefing_id": "brief-2026-08-20",
        "as_of": "2026-08-20T09:00:00+00:00",
        "near_misses": [
            {
                "decision_id": "dec-1",
                "instrument_id": "NSE:FOO",
                "composite": "58.30",
                "score_gap": "1.70",
                "trade_threshold": 60,
            }
        ],
    })
    service = DecisionsService(provider, config_dir=config_dir)

    digest = service.get_near_misses()

    assert digest.briefing_id == "brief-2026-08-20"
    assert digest.count == 1
    assert digest.items[0].decision_id == "dec-1"
    assert digest.items[0].instrument_id == "NSE:FOO"
    assert str(digest.items[0].score_gap) == "1.70"


def test_picks_the_most_recently_modified_file(tmp_path, config_dir, provider):
    out = tmp_path / "briefings"
    _point_output_dir_at(config_dir, out)
    _write_briefing(out, "brief-2026-08-18.json", {
        "briefing_id": "brief-2026-08-18", "as_of": "2026-08-18T09:00:00+00:00", "near_misses": [],
    })
    older = out / "brief-2026-08-18.json"
    time.sleep(0.01)
    _write_briefing(out, "brief-2026-08-20.json", {
        "briefing_id": "brief-2026-08-20", "as_of": "2026-08-20T09:00:00+00:00", "near_misses": [],
    })
    newer = out / "brief-2026-08-20.json"
    assert newer.stat().st_mtime >= older.stat().st_mtime

    service = DecisionsService(provider, config_dir=config_dir)
    digest = service.get_near_misses()

    assert digest.briefing_id == "brief-2026-08-20"


def test_a_briefing_that_ran_and_found_none_is_distinct_from_no_briefing_at_all(tmp_path, config_dir, provider):
    """count == 0 for both cases, but as_of/briefing_id must distinguish
    'ran today, found nothing' from 'never ran'."""
    out = tmp_path / "briefings"
    _point_output_dir_at(config_dir, out)
    _write_briefing(out, "brief-2026-08-20.json", {
        "briefing_id": "brief-2026-08-20", "as_of": "2026-08-20T09:00:00+00:00", "near_misses": [],
    })
    service = DecisionsService(provider, config_dir=config_dir)

    digest = service.get_near_misses()

    assert digest.count == 0
    assert digest.as_of is not None
    assert digest.briefing_id == "brief-2026-08-20"


def test_corrupt_briefing_file_degrades_to_empty_digest_rather_than_raising(tmp_path, config_dir, provider):
    out = tmp_path / "briefings"
    _point_output_dir_at(config_dir, out)
    out.mkdir(parents=True, exist_ok=True)
    (out / "brief-2026-08-20.json").write_text("{not valid json", encoding="utf-8")
    service = DecisionsService(provider, config_dir=config_dir)

    digest = service.get_near_misses()

    assert digest.as_of is None
    assert digest.count == 0
