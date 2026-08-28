"""EM-5 production canary gate (contract Section 14) -- exercised against
the REAL promoted `config/emr/frozen_models/v1/` artifacts, real
`SqliteRepository`-backed market data, and zero Kite calls (the collector
is network-free by construction -- see `canary_gate.py`).
"""

from __future__ import annotations

from datetime import date, datetime, timedelta
from decimal import Decimal
from pathlib import Path
from zoneinfo import ZoneInfo

import pytest

from athena.data.store import SqliteRepository
from athena.domain.enums import SessionType, Timeframe
from athena.domain.market import Candle, Instrument
from athena.explosive_move.live.canary_gate import (
    MATURE_HISTORY_MINIMUM_SESSIONS,
    run_em5_production_canary,
)
from athena.explosive_move.live.market_data_port import SqliteEmrMarketDataAdapter

IST = ZoneInfo("Asia/Kolkata")
REPO_ROOT = Path(__file__).resolve().parents[2]
CONFIG_DIR = REPO_ROOT / "config"
SESSION_DATE = date(2026, 8, 28)
UNIVERSE_NAME = "em5-canary-test-universe"
MATURE_INSTRUMENT = "NSE:MATURE"
IMMATURE_INSTRUMENT = "NSE:IMMATURE"
CHECKPOINTS = ("09:20", "09:30", "10:00")
NIFTY = "NSE:NIFTY 50"
VIX = "NSE:INDIA VIX"


def _instrument(iid: str, symbol: str) -> Instrument:
    return Instrument(instrument_id=iid, symbol=symbol, exchange="NSE", series="EQ",
                      isin=f"INE{symbol[:6]}0001", lot_size=1, tick_size=Decimal("0.05"),
                      status="ACTIVE", listed_date=date(2020, 1, 1))


def _daily_candle(iid: str, day: date, close: str) -> Candle:
    c = Decimal(close)
    return Candle(instrument_id=iid, timeframe=Timeframe.D1,
                  ts_open=datetime(day.year, day.month, day.day, 9, 15, tzinfo=IST),
                  open=c, high=c + 1, low=c - 1, close=c, volume=50000, source="test")


def _today_m5_through(iid: str, last_time: str) -> list[Candle]:
    """09:15 through `last_time` inclusive, on the real 5-minute grid."""
    start = datetime(2026, 8, 28, 9, 15, tzinfo=IST)
    end = datetime.combine(SESSION_DATE, datetime.strptime(last_time, "%H:%M").time(), tzinfo=IST)
    candles, ts = [], start
    while ts <= end:
        candles.append(Candle(
            instrument_id=iid, timeframe=Timeframe.M5, ts_open=ts,
            open=Decimal("100"), high=Decimal("101"), low=Decimal("99"), close=Decimal("100"),
            volume=1000, source="test",
        ))
        ts += timedelta(minutes=5)
    return candles


def _seed_repo(tmp_path: Path, *, with_regime_data: bool = True) -> SqliteRepository:
    repo = SqliteRepository(tmp_path / "athena.db")
    repo.initialize()
    for iid in (MATURE_INSTRUMENT, IMMATURE_INSTRUMENT):
        repo.upsert_instrument(_instrument(iid, iid.split(":")[1]))
    repo.save_resolved_universe(
        UNIVERSE_NAME, [MATURE_INSTRUMENT, IMMATURE_INSTRUMENT], resolved_at=datetime.now(tz=IST),
    )

    mature_daily = [_daily_candle(MATURE_INSTRUMENT, SESSION_DATE - timedelta(days=i), "100") for i in range(70, 0, -1)]
    repo.add_candles(mature_daily)
    repo.add_candles(_today_m5_through(MATURE_INSTRUMENT, "10:00"))

    immature_daily = [
        _daily_candle(IMMATURE_INSTRUMENT, SESSION_DATE - timedelta(days=i), "100") for i in range(5, 0, -1)
    ]
    repo.add_candles(immature_daily)
    repo.add_candles(_today_m5_through(IMMATURE_INSTRUMENT, "10:00"))

    if with_regime_data:
        # Real NIFTY 50 / INDIA VIX D1 history so the canonical regime
        # source (Owner ruling 2026-08-28) resolves genuine, non-UNKNOWN
        # labels -- 60 rising sessions clears RegimeConfig's real
        # trend_ma_slow=50 default with margin.
        for iid in (NIFTY, VIX):
            repo.upsert_instrument(_instrument(iid, iid.split(":")[1]))
        nifty_daily = [
            _daily_candle(NIFTY, SESSION_DATE - timedelta(days=i), str(20000 + (60 - i) * 5))
            for i in range(60, 0, -1)
        ]
        repo.add_candles(nifty_daily)
        repo.add_candles([_daily_candle(NIFTY, SESSION_DATE, "20500")])  # real ~1% gap up vs prior close 20295
        repo.add_candles([_daily_candle(VIX, SESSION_DATE - timedelta(days=1), "15.0")])  # inside [12, 20]
    return repo


@pytest.fixture()
def canary_setup(tmp_path):
    athena_repo = _seed_repo(tmp_path)
    market_port = SqliteEmrMarketDataAdapter(athena_repo)
    yield market_port
    athena_repo.close()


@pytest.fixture()
def canary_setup_no_regime(tmp_path):
    athena_repo = _seed_repo(tmp_path, with_regime_data=False)
    market_port = SqliteEmrMarketDataAdapter(athena_repo)
    yield market_port
    athena_repo.close()


def _run(market_port, **overrides):
    kwargs = dict(
        market_port=market_port, universe=UNIVERSE_NAME, session_date=SESSION_DATE,
        calendar_context_session_type=SessionType.NORMAL, config_dir=CONFIG_DIR, model_version="v1",
        session_open_time=datetime(2026, 8, 28, 9, 15).time(), tzinfo=IST, checkpoints=CHECKPOINTS,
    )
    kwargs.update(overrides)
    return run_em5_production_canary(**kwargs)


def test_only_the_mature_instrument_is_admitted_to_the_canary(canary_setup):
    result = _run(canary_setup)
    assert result.mature_instrument_ids == (MATURE_INSTRUMENT,)
    maturity_check = next(h for h in result.hard_invariants if h.name == "MATURE_HISTORY_UNIVERSE_NONEMPTY")
    assert maturity_check.passed
    assert "1 of 2" in maturity_check.detail


def test_all_immature_universe_fails_closed_without_running_a_scan(canary_setup):
    result = _run(canary_setup, session_date=SESSION_DATE - timedelta(days=60))
    assert result.passed is False
    assert "MATURE_HISTORY_UNIVERSE_NONEMPTY" in result.failure_reasons
    assert result.completeness == ()


def test_canonical_regime_wiring_resolves_real_labels_and_lifts_completeness(canary_setup):
    """Owner/Chief Architect ruling (2026-08-28): wire the real canonical
    RegimeEngine into `run_scan_cycle`'s `regime_lookup` rather than
    rescoping the completeness floor. With real NIFTY 50/INDIA VIX history
    seeded, REGIME_TREND/REGIME_VOLATILITY/REGIME_GAP resolve to genuine
    labels instead of the permanent 0% the unwired gate produced -- proving
    the wiring is actually connected, not just present in source."""

    result = _run(canary_setup)
    assert result.regime_assessment == {
        "trend": "BULL_TREND", "volatility": "NORMAL_VOLATILITY", "gap": "GAP_UP",
    }
    # This fixture seeds no PRIOR-SESSION M5 candles, so REL_VOLUME_C stays
    # genuinely UNKNOWN regardless of regime -- all_fields_known_rate can
    # legitimately stay 0% here (a fixture gap, not a regime regression).
    # The claim this test actually proves: regime fields specifically are
    # now fully known on every mature-instrument row, where before wiring
    # they were unknown on all of them.
    for c in result.completeness:
        field_rate = result.field_known_count[c.checkpoint]
        verified = result.field_verified_count[c.checkpoint]
        assert verified > 0
        for regime_field in ("regime_trend", "regime_volatility", "regime_gap"):
            assert field_rate.get(regime_field, 0) == verified  # every mature instrument, every regime field known


def test_regime_source_still_degrades_honestly_when_index_data_is_absent(canary_setup_no_regime):
    """Without real NIFTY/VIX history in the repository, the canonical
    regime source (not an EMR-specific fallback) correctly reports
    `*_UNKNOWN` rather than fabricating a label -- the same honest
    degradation `test_em5_regime_source.py` proves at the unit level,
    reproduced here through the full canary path."""

    result = _run(canary_setup_no_regime)
    assert result.regime_assessment == {
        "trend": "TREND_UNKNOWN", "volatility": "VOLATILITY_UNKNOWN", "gap": "GAP_UNKNOWN",
    }
    assert result.passed is False
    for c in result.completeness:
        assert c.all_fields_known_rate == 0.0
        assert f"COMPLETENESS_FLOOR[{c.checkpoint}]" in result.failure_reasons


def test_hard_invariants_other_than_completeness_pass_on_clean_real_data(canary_setup):
    result = _run(canary_setup)
    singular = {h.name: h for h in result.hard_invariants if h.name != "CHECKPOINT_BOUNDARY_REGRESSION"}
    assert singular["FROZEN_ARTIFACT_INTEGRITY"].passed
    assert singular["HARD_ELIGIBILITY_INPUTS_WELL_FORMED"].passed
    assert singular["NO_SYSTEMIC_STALE_DATA"].passed
    assert singular["ZERO_PROVIDER_NETWORK_CALLS"].passed
    assert singular["REPLAY_DETERMINISM"].passed

    boundary_checks = [h for h in result.hard_invariants if h.name == "CHECKPOINT_BOUNDARY_REGRESSION"]
    assert len(boundary_checks) == len(CHECKPOINTS)
    assert all(h.passed for h in boundary_checks)


def test_corrupted_frozen_artifact_fails_fast_before_any_scan(canary_setup, tmp_path):
    corrupt_root = tmp_path / "corrupt_config"
    real_root = CONFIG_DIR / "emr" / "frozen_models" / "v1"
    dest_root = corrupt_root / "emr" / "frozen_models" / "v1"
    (dest_root / "em4b").mkdir(parents=True)
    (dest_root / "em4d").mkdir(parents=True)
    (dest_root / "FROZEN_MODEL_MANIFEST.json").write_text(
        (real_root / "FROZEN_MODEL_MANIFEST.json").read_text(encoding="utf-8"), encoding="utf-8",
    )
    (dest_root / "em4b" / "TOUCH_10.json").write_text(
        (real_root / "em4b" / "TOUCH_10.json").read_text(encoding="utf-8") + " ", encoding="utf-8",
    )
    (dest_root / "em4d" / "TOUCH_10.json").write_text(
        (real_root / "em4d" / "TOUCH_10.json").read_text(encoding="utf-8"), encoding="utf-8",
    )

    result = _run(canary_setup, config_dir=corrupt_root, families_thresholds=(("TOUCH", 10),))
    assert result.passed is False
    assert result.failure_reasons == ("FROZEN_ARTIFACT_INTEGRITY",)
    assert result.mature_instrument_ids == ()


def test_mature_history_minimum_is_pinned_to_the_contract_section_14_value():
    assert MATURE_HISTORY_MINIMUM_SESSIONS == 50
