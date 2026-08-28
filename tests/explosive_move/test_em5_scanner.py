"""EM-5 scan orchestration -- end-to-end wiring proof against the REAL
promoted `config/emr/frozen_models/v1/` artifacts (not synthetic
fixtures): eligibility, evidence assembly, frozen inference,
deterministic scoring, explanation, ranking, the state machine, and
persistence, all through one `run_scan_cycle` call. The checkpoint-price
collector is injected (no live Kite call in tests) -- everything else
is real, tested code.
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
from athena.explosive_move.live.checkpoint_reference_price import CheckpointReferencePrice
from athena.explosive_move.live.market_data_port import SqliteEmrMarketDataAdapter
from athena.explosive_move.live.scanner import FAMILIES_THRESHOLDS, ScanCycleConfig, run_scan_cycle
from athena.explosive_move.store.repository import EmrRepository

IST = ZoneInfo("Asia/Kolkata")
REPO_ROOT = Path(__file__).resolve().parents[2]
CONFIG_DIR = REPO_ROOT / "config"
SESSION_DATE = date(2026, 8, 28)
CHECKPOINT = "10:00"
CHECKPOINT_INSTANT = datetime(2026, 8, 28, 10, 0, tzinfo=IST)
UNIVERSE_NAME = "em5-test-universe"
INSTRUMENTS = ("NSE:AAA", "NSE:BBB")


def _instrument(iid: str, symbol: str) -> Instrument:
    return Instrument(instrument_id=iid, symbol=symbol, exchange="NSE", series="EQ",
                      isin=f"INE{symbol}00000A01", lot_size=1, tick_size=Decimal("0.05"),
                      status="ACTIVE", listed_date=date(2020, 1, 1))


def _daily_candle(iid: str, day: date, close: str) -> Candle:
    c = Decimal(close)
    return Candle(instrument_id=iid, timeframe=Timeframe.D1,
                  ts_open=datetime(day.year, day.month, day.day, 9, 15, tzinfo=IST),
                  open=c, high=c + 1, low=c - 1, close=c, volume=50000, source="test")


def _today_m5(iid: str, n: int) -> list[Candle]:
    start = datetime(2026, 8, 28, 9, 15, tzinfo=IST)
    return [
        Candle(instrument_id=iid, timeframe=Timeframe.M5, ts_open=start + timedelta(minutes=5 * i),
               open=Decimal("100"), high=Decimal("101"), low=Decimal("99"), close=Decimal("100"),
               volume=1000, source="test")
        for i in range(n)
    ]


def _seed_athena_repo(tmp_path: Path) -> SqliteRepository:
    tmp_path.mkdir(parents=True, exist_ok=True)
    repo = SqliteRepository(tmp_path / "athena.db")
    repo.initialize()
    for iid in INSTRUMENTS:
        repo.upsert_instrument(_instrument(iid, iid.split(":")[1]))
    repo.save_resolved_universe(UNIVERSE_NAME, list(INSTRUMENTS), resolved_at=CHECKPOINT_INSTANT)
    for iid in INSTRUMENTS:
        daily = [
            _daily_candle(iid, SESSION_DATE - timedelta(days=i), "100")
            for i in range(60, 0, -1)
        ]
        repo.add_candles(daily)
        repo.add_candles(_today_m5(iid, 34))  # 09:15 through 09:55, closed before 10:00
    return repo


def _fake_collector(*, instrument_ids, checkpoint_instant, **_kwargs):
    qualified = {
        iid: CheckpointReferencePrice(
            instrument_id=iid, checkpoint_instant=checkpoint_instant,
            reference_price_semantic="FIRST_OBSERVED_POST_CHECKPOINT_TRADE",
            last_price=Decimal("103"), last_trade_time=checkpoint_instant + timedelta(seconds=5),
            snapshot_timestamp=checkpoint_instant + timedelta(seconds=6), latency_seconds=5.0, provider="kite",
        )
        for iid in instrument_ids
    }
    return qualified, (), 1


def _config(config_dir=CONFIG_DIR, families_thresholds=FAMILIES_THRESHOLDS) -> ScanCycleConfig:
    return ScanCycleConfig(
        universe=UNIVERSE_NAME, session_date=SESSION_DATE, checkpoint=CHECKPOINT,
        checkpoint_instant=CHECKPOINT_INSTANT, session_open_time=datetime(2026, 8, 28, 9, 15).time(),
        model_version="v1", config_dir=config_dir, max_staleness_minutes=30.0,
        max_checkpoint_price_delay_seconds=300.0, families_thresholds=families_thresholds,
    )


@pytest.fixture()
def scan_setup(tmp_path):
    athena_repo = _seed_athena_repo(tmp_path / "athena")
    market_port = SqliteEmrMarketDataAdapter(athena_repo)
    emr_repo = EmrRepository(tmp_path / "emr" / "emr.db")
    emr_repo.initialize()
    yield market_port, emr_repo
    athena_repo.close()
    emr_repo.close()


def test_full_scan_cycle_persists_a_candidate_per_instrument_per_combo(scan_setup):
    market_port, emr_repo = scan_setup
    result = run_scan_cycle(
        config=_config(), market_port=market_port, emr_repo=emr_repo,
        calendar_context_session_type=SessionType.NORMAL, collect_checkpoint_prices=_fake_collector,
        now=lambda: CHECKPOINT_INSTANT,
    )
    assert result.status == "COMPLETE"
    assert result.eligible_count == 2
    assert result.ineligible_count == 0
    assert result.candidates_persisted == len(INSTRUMENTS) * len(FAMILIES_THRESHOLDS)

    rows = emr_repo.list_candidates(run_id=result.run_id)
    assert len(rows) == 36
    assert {r["instrument_id"] for r in rows} == set(INSTRUMENTS)
    touch_10 = [r for r in rows if r["family"] == "TOUCH" and r["threshold_percent"] == 10]
    assert len(touch_10) == 2
    assert all(isinstance(r["raw_logistic_estimate"], float) for r in touch_10)
    assert all(r["rank"] in (1, 2) for r in touch_10)
    assert {r["rank"] for r in touch_10} == {1, 2}
    assert all(r["state"] in ("WATCH", "DEVELOPING", "CONFIRMED", "HIGH_CONVICTION") for r in touch_10)
    assert all(Decimal(r["checkpoint_price"]) == Decimal("103") for r in touch_10)
    assert all(r["checkpoint_price_semantic"] == "FIRST_OBSERVED_POST_CHECKPOINT_TRADE" for r in touch_10)


def test_scan_cycle_creates_transitions_from_inactive_on_first_checkpoint(scan_setup):
    market_port, emr_repo = scan_setup
    result = run_scan_cycle(
        config=_config(), market_port=market_port, emr_repo=emr_repo,
        calendar_context_session_type=SessionType.NORMAL, collect_checkpoint_prices=_fake_collector,
        now=lambda: CHECKPOINT_INSTANT,
    )
    transitions = emr_repo.list_transitions(
        instrument_id=INSTRUMENTS[0], family="TOUCH", threshold_percent=10, session_date=SESSION_DATE.isoformat(),
    )
    assert len(transitions) == 1
    assert transitions[0]["from_state"] == "INACTIVE"
    assert transitions[0]["run_id"] == result.run_id


def test_skipped_session_type_persists_no_candidates(scan_setup):
    market_port, emr_repo = scan_setup
    result = run_scan_cycle(
        config=_config(), market_port=market_port, emr_repo=emr_repo,
        calendar_context_session_type=SessionType.MUHURAT, collect_checkpoint_prices=_fake_collector,
        now=lambda: CHECKPOINT_INSTANT,
    )
    assert result.status == "SKIPPED_SESSION_TYPE"
    assert result.candidates_persisted == 0
    assert emr_repo.list_candidates(run_id=result.run_id) == []


def test_two_independent_runs_against_identical_inputs_produce_byte_identical_scores(tmp_path):
    results = []
    for suffix in ("a", "b"):
        athena_repo = _seed_athena_repo(tmp_path / f"athena-{suffix}")
        market_port = SqliteEmrMarketDataAdapter(athena_repo)
        emr_repo = EmrRepository(tmp_path / f"emr-{suffix}" / "emr.db")
        emr_repo.initialize()
        result = run_scan_cycle(
            config=_config(families_thresholds=(("TOUCH", 10),)), market_port=market_port, emr_repo=emr_repo,
            calendar_context_session_type=SessionType.NORMAL, collect_checkpoint_prices=_fake_collector,
            now=lambda: CHECKPOINT_INSTANT,
        )
        rows = emr_repo.list_candidates(run_id=result.run_id)
        results.append(sorted(rows, key=lambda r: r["instrument_id"]))
        athena_repo.close()
        emr_repo.close()

    first, second = results
    assert len(first) == len(second) == 2
    for a, b in zip(first, second, strict=True):
        assert a["raw_logistic_estimate"] == b["raw_logistic_estimate"]
        assert a["calibrated_probability"] == b["calibrated_probability"]
        assert a["rank"] == b["rank"]
        assert a["state"] == b["state"]
