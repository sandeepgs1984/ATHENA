"""Config framework tests — Phase 0 exit criterion:
invariant violations fail with readable errors; snapshots are deterministic."""

from __future__ import annotations

import pytest
from tests.conftest import rewrite_json

from athena.config.loader import (
    load_config,
    load_external_links_file,
    load_kite_provider_config,
    load_sector_index_mapping_config,
    snapshot_config,
)
from athena.errors import ConfigError


def test_valid_config_loads(config_dir):
    config = load_config(config_dir)
    assert config.market.exchange == "NSE"
    assert config.profile.name == "intraday-momentum"
    assert sum(config.profile.weights.values()) == 100


def test_snapshot_is_deterministic(config_dir):
    c1, c2 = load_config(config_dir), load_config(config_dir)
    assert snapshot_config(c1).content_hash == snapshot_config(c2).content_hash


def test_snapshot_changes_when_config_changes(config_dir):
    before = snapshot_config(load_config(config_dir)).content_hash
    rewrite_json(config_dir / "risk.json",
                 lambda d: d.update(max_decisions_per_day=7))
    after = snapshot_config(load_config(config_dir)).content_hash
    assert before != after


def test_per_trade_risk_exceeding_daily_loss_is_rejected(config_dir):
    rewrite_json(config_dir / "risk.json",
                 lambda d: d.update(per_trade_risk_pct=5.0, max_daily_loss_pct=2.0))
    with pytest.raises(ConfigError, match=r"per_trade_risk_pct.*max_daily_loss_pct"):
        load_config(config_dir)


def test_position_cap_exceeding_sector_cap_is_rejected(config_dir):
    rewrite_json(config_dir / "capital.json",
                 lambda d: d.update(max_capital_per_position_pct=50.0,
                                    max_capital_per_sector_pct=30.0))
    with pytest.raises(ConfigError, match=r"max_capital_per_position_pct"):
        load_config(config_dir)


def test_profile_weights_must_sum_to_100(config_dir):
    rewrite_json(config_dir / "profiles" / "intraday-momentum.json",
                 lambda d: d["weights"].update(momentum=99))
    with pytest.raises(ConfigError, match=r"must sum to 100"):
        load_config(config_dir)


def test_unknown_profile_lists_available(config_dir):
    with pytest.raises(ConfigError, match=r"not found.*Available.*intraday-momentum"):
        load_config(config_dir, profile_name="no-such-profile")


def test_unversioned_profile_indicator_is_rejected(config_dir):
    rewrite_json(config_dir / "profiles" / "intraday-momentum.json",
                 lambda d: d["indicators"].append("supertrend"))
    with pytest.raises(ConfigError, match=r"unversioned indicators.*supertrend"):
        load_config(config_dir)


def test_trading_window_outside_session_is_rejected(config_dir):
    rewrite_json(config_dir / "profiles" / "intraday-momentum.json",
                 lambda d: d.update(trading_windows=[{"start": "08:00", "end": "14:00"}]))
    with pytest.raises(ConfigError, match=r"outside market session"):
        load_config(config_dir)


def test_unknown_key_is_rejected_as_typo(config_dir):
    rewrite_json(config_dir / "risk.json", lambda d: d.update(max_dialy_loss_pct=3))
    with pytest.raises(ConfigError, match=r"max_dialy_loss_pct"):
        load_config(config_dir)


def test_missing_file_is_a_readable_error(config_dir):
    (config_dir / "capital.json").unlink()
    with pytest.raises(ConfigError, match=r"Missing configuration file.*capital.json"):
        load_config(config_dir)


def test_external_links_default_empty_when_missing(tmp_path):
    empty_dir = tmp_path / "config"
    empty_dir.mkdir()
    result = load_external_links_file(empty_dir)
    assert result.links == []


def test_external_links_loads_valid_entries(config_dir):
    rewrite_json(config_dir / "external_links.json", lambda d: d["links"].append({
        "instrument_id": "NSE:RELIANCE",
        "title": "Reliance FY26 Investor Day",
        "url": "https://example.com/reliance-investor-day",
        "source": "Company IR",
        "added_by": "owner",
        "date_added": "2026-07-20",
    }))
    result = load_external_links_file(config_dir)
    assert len(result.links) == 1
    assert result.links[0].instrument_id == "NSE:RELIANCE"
    assert result.links[0].title == "Reliance FY26 Investor Day"


def test_external_links_rejects_unknown_field(config_dir):
    rewrite_json(config_dir / "external_links.json", lambda d: d["links"].append({
        "instrument_id": "GLOBAL",
        "title": "x",
        "url": "https://x",
        "source": "x",
        "added_by": "x",
        "date_added": "2026-01-01",
        "unexpected_field": "oops",
    }))
    with pytest.raises(ConfigError, match=r"unexpected_field"):
        load_external_links_file(config_dir)


# SD-2 / DD-12: sector index history ingestion + explicit sector->index mapping.

def test_kite_index_instruments_includes_sectoral_indices(config_dir):
    kite = load_kite_provider_config(config_dir)
    assert "NSE:NIFTY 50" in kite.index_instruments
    assert "NSE:NIFTY BANK" in kite.index_instruments
    for sectoral in (
        "NSE:NIFTY IT", "NSE:NIFTY AUTO", "NSE:NIFTY PHARMA", "NSE:NIFTY FMCG",
        "NSE:NIFTY METAL", "NSE:NIFTY REALTY", "NSE:NIFTY ENERGY", "NSE:NIFTY PSU BANK",
    ):
        assert sectoral in kite.index_instruments
    assert len(kite.index_instruments) == len(set(kite.index_instruments))


def test_sector_index_mapping_loads_real_config(config_dir):
    mapping = load_sector_index_mapping_config(config_dir)
    assert mapping.index_key_for_sector("Information Technology") == "nifty_it"
    assert mapping.index_key_for_sector("Automobile and Auto Components") == "nifty_auto"
    assert mapping.index_key_for_sector("Realty") == "nifty_realty"
    # Two sectors sharing one proxy index is intentional (documented approximation).
    assert mapping.index_key_for_sector("Oil Gas & Consumable Fuels") == "nifty_energy"
    assert mapping.index_key_for_sector("Power") == "nifty_energy"
    # Deliberately unmapped — never guessed.
    assert mapping.index_key_for_sector("Financial Services") is None
    assert mapping.index_key_for_sector(None) is None
    assert mapping.index_key_for_sector("") is None


def test_sector_index_mapping_rejects_duplicate_sector(config_dir):
    rewrite_json(config_dir / "sector_index_mapping.json", lambda d: d["mappings"].append({
        "sector": "Information Technology",
        "index_key": "nifty_it",
    }))
    with pytest.raises(ConfigError, match=r"duplicate sector mapping"):
        load_sector_index_mapping_config(config_dir)


def test_sector_index_mapping_allows_shared_index_key(config_dir):
    # Two different sectors pointing at the same index_key must NOT be
    # rejected as a "duplicate" — only duplicate *sectors* are invalid.
    rewrite_json(config_dir / "sector_index_mapping.json", lambda d: d.update(mappings=[
        {"sector": "Sector A", "index_key": "nifty_energy"},
        {"sector": "Sector B", "index_key": "nifty_energy"},
    ]))
    mapping = load_sector_index_mapping_config(config_dir)
    assert mapping.index_key_for_sector("Sector A") == "nifty_energy"
    assert mapping.index_key_for_sector("Sector B") == "nifty_energy"
