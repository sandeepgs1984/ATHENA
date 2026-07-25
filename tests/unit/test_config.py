"""Config framework tests — Phase 0 exit criterion:
invariant violations fail with readable errors; snapshots are deterministic."""

from __future__ import annotations

import pytest
from tests.conftest import rewrite_json

from athena.config.loader import load_config, load_external_links_file, snapshot_config
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
