"""Versioned index-constituent snapshot contract tests (IX-3)."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from athena.config.loader import load_index_intelligence_config
from athena.data.index_constituents import load_index_constituent_snapshot
from athena.errors import ConfigError


def test_production_snapshot_is_complete_and_checksum_verified() -> None:
    root = Path(__file__).resolve().parents[2]
    config = load_index_intelligence_config(root / "config")
    expected_keys = {item.key for item in config.tracked_indices if item.enabled}
    manifest = root / str(config.constituent_manifest)

    snapshot = load_index_constituent_snapshot(
        manifest,
        expected_index_keys=expected_keys,
    )

    assert snapshot.provider == "NSE Indices Limited"
    assert snapshot.effective_date.isoformat() == "2026-07-31"
    assert {item.key for item in snapshot.indices} == expected_keys
    assert sum(len(item.symbols) for item in snapshot.indices) == 351
    assert all(item.symbols == tuple(sorted(item.symbols)) for item in snapshot.indices)


def test_checksum_drift_fails_loudly(tmp_path: Path) -> None:
    member_file = tmp_path / "members.csv"
    member_file.write_text(
        "Company Name,Industry,Symbol,Series,ISIN Code\nAAA Ltd,Test,AAA,EQ,INE000000001\n",
        encoding="utf-8",
    )
    manifest = tmp_path / "manifest.json"
    manifest.write_text(
        json.dumps(
            {
                "schema_version": 1,
                "provider": "NSE Indices Limited",
                "effective_date": "2026-07-31",
                "retrieved_at": "2026-07-31T05:00:00Z",
                "overlap_policy": "COUNT_ONCE_PER_INDEX_INDEPENDENT_ACROSS_INDICES",
                "indices": [
                    {
                        "key": "test_index",
                        "file": member_file.name,
                        "source_url": "https://archives.nseindia.com/members.csv",
                        "sha256": "0" * 64,
                        "member_count": 1,
                    }
                ],
            }
        ),
        encoding="utf-8",
    )

    with pytest.raises(ConfigError, match="checksum mismatch"):
        load_index_constituent_snapshot(
            manifest,
            expected_index_keys={"test_index"},
        )


def test_catalog_key_drift_fails_loudly(tmp_path: Path) -> None:
    root = Path(__file__).resolve().parents[2]
    manifest = root / "data/index_constituents/2026-07-31/manifest.json"

    with pytest.raises(ConfigError, match="catalog keys differ"):
        load_index_constituent_snapshot(
            manifest,
            expected_index_keys={"nifty_50"},
        )
