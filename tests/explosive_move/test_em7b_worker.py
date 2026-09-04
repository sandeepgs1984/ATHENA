"""EM-7B: isolated EMR scheduling/invocation layer.

Proves: the disabled-worker zero-side-effect invariant; the
checkpoint-due algorithm (no duplicate semantic runs on repeated polls,
latest-due-only catch-up after a burst of missed checkpoints, restart
recoverability from persisted `emr_scan_runs` state rather than
in-memory flags); the mature-history universe wiring actually narrows
the scanned population (not a silent fallback to the full universe);
regime wiring; the `run_scan_cycle_with_lock` entrypoint proof; and
production-safety (`db/emr.db` absence).

Reuses `test_em5_scanner.py`'s fixtures/helpers for the general case
(all fixture instruments already mature -- 60 days of daily bars);
builds one dedicated, smaller repo for the "mature-history filter
actually filters" proof, since that needs a real immature instrument.
"""

from __future__ import annotations

from datetime import date, datetime, timedelta
from decimal import Decimal
from pathlib import Path
from zoneinfo import ZoneInfo

import pytest
from tests.explosive_move.test_em5_scanner import (
    CONFIG_DIR,
    INSTRUMENTS,
    SESSION_DATE,
    UNIVERSE_NAME,
    _fake_collector,
    _seed_athena_repo,
)

from athena.calendar.engine import CalendarEngine
from athena.config.loader import load_config
from athena.data.store import SqliteRepository
from athena.domain.enums import Timeframe
from athena.domain.market import Candle, Instrument
from athena.explosive_move.contracts import CANDIDATE_CHECKPOINTS_IST
from athena.explosive_move.live.market_data_port import SqliteEmrMarketDataAdapter
from athena.explosive_move.live.operational_config import EmrOperationalConfig
from athena.explosive_move.live.scan_lock import EmrScanLock
from athena.explosive_move.live.scanner import compute_run_id
from athena.explosive_move.live.worker import EMR_WORKER_TICK_ACTIONS, EmrWorker, run_once
from athena.explosive_move.store.repository import EmrRepository

IST = ZoneInfo("Asia/Kolkata")
_MARKET = load_config(CONFIG_DIR).market
_CALENDAR = CalendarEngine.from_config_dir(CONFIG_DIR, _MARKET)


def _config(**overrides) -> EmrOperationalConfig:
    base = {"enabled": True, "base_universe": UNIVERSE_NAME, "model_version": "v1"}
    base.update(overrides)
    return EmrOperationalConfig(**base)


def _at(checkpoint: str, *, offset_minutes: int = 0, session_date: date = SESSION_DATE) -> datetime:
    hour, minute = (int(p) for p in checkpoint.split(":"))
    return datetime(
        session_date.year, session_date.month, session_date.day, hour, minute, tzinfo=IST,
    ) + timedelta(minutes=offset_minutes)


class _CountingCollector:
    def __init__(self):
        self.calls = 0
        self.call_instants: list[datetime] = []

    def __call__(self, **kwargs):
        self.calls += 1
        self.call_instants.append(kwargs["checkpoint_instant"])
        return _fake_collector(**kwargs)


@pytest.fixture()
def worker_setup(tmp_path):
    athena_repo = _seed_athena_repo(tmp_path / "athena")
    emr_repo = EmrRepository(tmp_path / "emr" / "emr.db")
    emr_repo.initialize()
    yield athena_repo, emr_repo
    athena_repo.close()
    emr_repo.close()


def _run(athena_repo, emr_repo, *, now, operational_config=None, collect_checkpoint_prices=_fake_collector, lock=None):
    return run_once(
        now=now, operational_config=operational_config or _config(), athena_repo=athena_repo, emr_repo=emr_repo,
        calendar_engine=_CALENDAR, config_dir=CONFIG_DIR, tzinfo=IST,
        collect_checkpoint_prices=collect_checkpoint_prices, lock=lock,
    )


class TestDisabledWorker:
    def test_disabled_config_returns_disabled_and_touches_nothing(self, tmp_path):
        athena_repo = _seed_athena_repo(tmp_path / "athena")
        emr_db_path = tmp_path / "emr" / "emr.db"
        emr_repo = EmrRepository(emr_db_path)  # deliberately NOT initialized
        collector = _CountingCollector()

        outcome = _run(
            athena_repo, emr_repo, now=_at("10:00"),
            operational_config=_config(enabled=False), collect_checkpoint_prices=collector,
        )

        assert outcome.action == "DISABLED"
        assert collector.calls == 0
        assert not emr_db_path.exists(), "a disabled tick must never create db/emr.db"
        athena_repo.close()

    def test_worker_start_disabled_never_creates_a_thread_or_db(self, tmp_path):
        athena_repo = _seed_athena_repo(tmp_path / "athena")
        emr_db_path = tmp_path / "emr" / "emr.db"
        emr_repo = EmrRepository(emr_db_path)
        worker = EmrWorker(
            operational_config=_config(enabled=False), athena_repo=athena_repo, emr_repo=emr_repo,
            calendar_engine=_CALENDAR, config_dir=CONFIG_DIR, tzinfo=IST,
            collect_checkpoint_prices=_fake_collector, lock_path=tmp_path / "lock" / "emr-scan.lock",
            now=lambda: _at("10:00"),
        )

        worker.start()

        assert worker._thread is None
        assert not emr_db_path.exists()
        worker.stop()
        athena_repo.close()


class TestSingleTick:
    def test_enabled_fixture_mode_invokes_and_completes(self, worker_setup):
        athena_repo, emr_repo = worker_setup
        outcome = _run(athena_repo, emr_repo, now=_at("10:00"))
        assert outcome.action == "INVOKED"
        assert outcome.scan_result.status == "COMPLETE"
        assert outcome.scan_result.candidates_persisted > 0

    def test_before_first_checkpoint_is_not_due(self, worker_setup):
        athena_repo, emr_repo = worker_setup
        outcome = _run(athena_repo, emr_repo, now=_at("09:20", offset_minutes=-5))
        assert outcome.action == "NO_CHECKPOINT_DUE"

    def test_exactly_at_checkpoint_is_due(self, worker_setup):
        athena_repo, emr_repo = worker_setup
        outcome = _run(athena_repo, emr_repo, now=_at("09:20"))
        assert outcome.action == "INVOKED"
        assert outcome.checkpoint == "09:20"

    def test_shortly_after_checkpoint_does_not_reinvoke(self, worker_setup):
        athena_repo, emr_repo = worker_setup
        collector = _CountingCollector()
        first = _run(athena_repo, emr_repo, now=_at("09:20"), collect_checkpoint_prices=collector)
        assert first.action == "INVOKED"
        second = _run(athena_repo, emr_repo, now=_at("09:20", offset_minutes=2), collect_checkpoint_prices=collector)
        assert second.action == "ALREADY_REPRESENTED"
        assert collector.calls == 1

    def test_between_checkpoints_is_not_due_after_prior_one_completes(self, worker_setup):
        athena_repo, emr_repo = worker_setup
        _run(athena_repo, emr_repo, now=_at("09:20"))
        outcome = _run(athena_repo, emr_repo, now=_at("09:20", offset_minutes=5))  # before 09:30
        assert outcome.action == "ALREADY_REPRESENTED"

    def test_after_final_checkpoint_only_invokes_the_last_one(self, worker_setup):
        athena_repo, emr_repo = worker_setup
        outcome = _run(athena_repo, emr_repo, now=_at("14:00", offset_minutes=90))  # well after 14:00
        assert outcome.action == "INVOKED"
        assert outcome.checkpoint == "14:00"

    def test_next_session_gets_a_fresh_checkpoint_sequence(self, worker_setup):
        athena_repo, emr_repo = worker_setup
        first = _run(athena_repo, emr_repo, now=_at("09:20"))
        assert first.action == "INVOKED"
        # SESSION_DATE + 3 calendar days (2026-08-31, Monday) is a real
        # NORMAL trading session -- 2026-08-28 was a Friday.
        next_session = SESSION_DATE + timedelta(days=3)
        outcome = _run(athena_repo, emr_repo, now=_at("09:20", session_date=next_session))
        assert outcome.action == "INVOKED"
        assert outcome.checkpoint == "09:20"
        assert outcome.scan_result.run_id != first.scan_result.run_id

    def test_non_scannable_session_is_not_due(self, worker_setup):
        athena_repo, emr_repo = worker_setup
        weekend = SESSION_DATE + timedelta(days=1)  # 2026-08-29, Saturday
        outcome = _run(athena_repo, emr_repo, now=_at("10:00", session_date=weekend))
        assert outcome.action == "NON_SCANNABLE_SESSION"
        assert outcome.scan_result is None


class TestMultiCheckpointProgression:
    def test_progresses_through_all_nine_checkpoints_without_duplication_or_burst(self, worker_setup):
        athena_repo, emr_repo = worker_setup
        collector = _CountingCollector()
        invoked_checkpoints: list[str] = []
        run_ids: list[str] = []

        for checkpoint in CANDIDATE_CHECKPOINTS_IST:
            # One poll exactly at the checkpoint, then one redundant poll
            # 2 minutes later -- the second must never re-invoke.
            outcome_a = _run(athena_repo, emr_repo, now=_at(checkpoint), collect_checkpoint_prices=collector)
            outcome_b = _run(
                athena_repo, emr_repo, now=_at(checkpoint, offset_minutes=2), collect_checkpoint_prices=collector,
            )
            assert outcome_a.action == "INVOKED"
            assert outcome_b.action == "ALREADY_REPRESENTED"
            invoked_checkpoints.append(outcome_a.checkpoint)
            run_ids.append(outcome_a.scan_result.run_id)

        assert invoked_checkpoints == list(CANDIDATE_CHECKPOINTS_IST)
        assert len(set(run_ids)) == len(CANDIDATE_CHECKPOINTS_IST), "every checkpoint got its own distinct run_id"
        assert collector.calls == len(CANDIDATE_CHECKPOINTS_IST), "exactly one provider call per checkpoint, no burst"

    def test_burst_after_late_start_invokes_only_the_latest_due_checkpoint(self, worker_setup):
        """The worker starts for the first time well after checkpoint 5
        of 9 (12:00) has passed, with nothing yet attempted today. A
        single tick must invoke ONLY the latest due checkpoint (12:00),
        never back-fill 09:20/09:30/09:45/10:00/10:30/11:00 in a burst."""
        athena_repo, emr_repo = worker_setup
        collector = _CountingCollector()

        outcome = _run(athena_repo, emr_repo, now=_at("12:00", offset_minutes=5), collect_checkpoint_prices=collector)

        assert outcome.action == "INVOKED"
        assert outcome.checkpoint == "12:00"
        assert collector.calls == 1, "must invoke exactly the one latest-due checkpoint, not a burst of missed ones"
        for missed in ("09:20", "09:30", "09:45", "10:00", "10:30", "11:00"):
            run_id = compute_run_id(
                session_date=SESSION_DATE, checkpoint=missed,
                universe=f"{UNIVERSE_NAME}-mature-history", model_version="v1",
            )
            assert emr_repo.get_scan_run(run_id) is None, f"checkpoint {missed} must never be back-filled"


class TestRestartBehavior:
    def test_restart_does_not_rerun_a_completed_checkpoint_and_picks_up_the_next_one(self, tmp_path):
        athena_repo = _seed_athena_repo(tmp_path / "athena")
        emr_db_path = tmp_path / "emr" / "emr.db"
        emr_repo_first = EmrRepository(emr_db_path)
        emr_repo_first.initialize()
        collector = _CountingCollector()

        first = _run(athena_repo, emr_repo_first, now=_at("09:20"), collect_checkpoint_prices=collector)
        assert first.action == "INVOKED"
        assert collector.calls == 1
        emr_repo_first.close()

        # Simulate a process restart: an entirely fresh EmrRepository
        # instance (and fresh CalendarEngine) pointed at the SAME on-disk
        # file -- no in-memory state carries over.
        restarted_calendar = CalendarEngine.from_config_dir(CONFIG_DIR, _MARKET)
        emr_repo_second = EmrRepository(emr_db_path)
        emr_repo_second.initialize()

        # A redundant poll for the SAME already-completed checkpoint must
        # not re-invoke the provider.
        replay = run_once(
            now=_at("09:20", offset_minutes=1), operational_config=_config(), athena_repo=athena_repo,
            emr_repo=emr_repo_second, calendar_engine=restarted_calendar, config_dir=CONFIG_DIR, tzinfo=IST,
            collect_checkpoint_prices=collector,
        )
        assert replay.action == "ALREADY_REPRESENTED"
        assert collector.calls == 1, "restart must not re-invoke the provider for an already-COMPLETE checkpoint"

        # The next checkpoint proceeds normally after "restart."
        next_tick = run_once(
            now=_at("09:30"), operational_config=_config(), athena_repo=athena_repo, emr_repo=emr_repo_second,
            calendar_engine=restarted_calendar, config_dir=CONFIG_DIR, tzinfo=IST,
            collect_checkpoint_prices=collector,
        )
        assert next_tick.action == "INVOKED"
        assert next_tick.checkpoint == "09:30"
        assert collector.calls == 2

        emr_repo_second.close()
        athena_repo.close()


class TestLockEntrypointProof:
    def test_run_once_actually_goes_through_the_lock(self, worker_setup, tmp_path):
        """If run_once called raw run_scan_cycle instead of
        run_scan_cycle_with_lock, externally holding the same lock path
        would have no effect and this tick would wrongly succeed."""
        athena_repo, emr_repo = worker_setup
        lock_path = tmp_path / "external.lock"
        holder = EmrScanLock(lock_path)
        assert holder.acquire() is True
        try:
            outcome = _run(athena_repo, emr_repo, now=_at("09:20"), lock=EmrScanLock(lock_path))
            assert outcome.action == "LOCK_BUSY"
        finally:
            holder.release()

        # With the lock free again, the same checkpoint proceeds normally.
        outcome = _run(athena_repo, emr_repo, now=_at("09:20", offset_minutes=1), lock=EmrScanLock(lock_path))
        assert outcome.action == "INVOKED"


class TestFailedRetryOwnership:
    def test_worker_never_auto_retries_a_failed_checkpoint(self, worker_setup):
        athena_repo, emr_repo = worker_setup

        def raising_collector(**_kwargs):
            raise ValueError("synthetic provider failure")

        first = _run(athena_repo, emr_repo, now=_at("09:20"), collect_checkpoint_prices=raising_collector)
        # run_scan_cycle marks the row FAILED internally, then re-raises
        # the original exception to its caller (EM-7A.1's own contract:
        # it returns ScanCycleResult only on success) -- the worker's own
        # generic except-Exception boundary catches that here.
        assert first.action == "UNEXPECTED_ERROR"
        assert first.scan_result is None
        run_id = compute_run_id(
            session_date=SESSION_DATE, checkpoint="09:20", universe=f"{UNIVERSE_NAME}-mature-history",
            model_version="v1",
        )
        assert emr_repo.get_scan_run(run_id)["status"] == "FAILED"

        collector = _CountingCollector()
        second = _run(athena_repo, emr_repo, now=_at("09:20", offset_minutes=5), collect_checkpoint_prices=collector)
        assert second.action == "ALREADY_REPRESENTED"
        assert collector.calls == 0, "a FAILED checkpoint must never be auto-retried by the worker's own polling"
        assert emr_repo.get_scan_run(run_id)["status"] == "FAILED"


class TestActionVocabulary:
    def test_every_observed_action_is_in_the_declared_vocabulary(self, worker_setup):
        athena_repo, emr_repo = worker_setup
        outcome = _run(athena_repo, emr_repo, now=_at("09:20"))
        assert outcome.action in EMR_WORKER_TICK_ACTIONS


# ------------------------------------------------------------------ #
# Mature-history universe: a dedicated, smaller repo with one genuinely
# immature instrument, proving the filter actually narrows the scanned
# population rather than silently falling back to the full universe.
# ------------------------------------------------------------------ #

_UNIVERSE_WITH_IMMATURE = "em7b-mixed-maturity-universe"
_MATURE_A, _MATURE_B, _IMMATURE = "NSE:MATA", "NSE:MATB", "NSE:IMMATURE"


def _instrument(iid: str, symbol: str) -> Instrument:
    return Instrument(
        instrument_id=iid, symbol=symbol, exchange="NSE", series="EQ", isin=f"INE{symbol}00000A01",
        lot_size=1, tick_size=Decimal("0.05"), status="ACTIVE", listed_date=date(2020, 1, 1),
    )


def _daily_candle(iid: str, day: date) -> Candle:
    return Candle(
        instrument_id=iid, timeframe=Timeframe.D1, ts_open=datetime(day.year, day.month, day.day, 9, 15, tzinfo=IST),
        open=Decimal("100"), high=Decimal("101"), low=Decimal("99"), close=Decimal("100"),
        volume=50000, source="test",
    )


def _today_m5(iid: str, n: int) -> list[Candle]:
    start = datetime(SESSION_DATE.year, SESSION_DATE.month, SESSION_DATE.day, 9, 15, tzinfo=IST)
    return [
        Candle(
            instrument_id=iid, timeframe=Timeframe.M5, ts_open=start + timedelta(minutes=5 * i),
            open=Decimal("100"), high=Decimal("101"), low=Decimal("99"), close=Decimal("100"),
            volume=1000, source="test",
        )
        for i in range(n)
    ]


def _seed_mixed_maturity_repo(tmp_path: Path) -> SqliteRepository:
    tmp_path.mkdir(parents=True, exist_ok=True)
    repo = SqliteRepository(tmp_path / "athena.db")
    repo.initialize()
    for iid in (_MATURE_A, _MATURE_B, _IMMATURE):
        repo.upsert_instrument(_instrument(iid, iid.split(":")[1]))
    repo.save_resolved_universe(
        _UNIVERSE_WITH_IMMATURE, [_MATURE_A, _MATURE_B, _IMMATURE], resolved_at=_at("10:00"),
    )
    for iid in (_MATURE_A, _MATURE_B):
        repo.add_candles([_daily_candle(iid, SESSION_DATE - timedelta(days=i)) for i in range(60, 0, -1)])
        repo.add_candles(_today_m5(iid, 34))
    # Only 5 prior sessions -- well under MATURE_HISTORY_MINIMUM_SESSIONS (50).
    repo.add_candles([_daily_candle(_IMMATURE, SESSION_DATE - timedelta(days=i)) for i in range(5, 0, -1)])
    repo.add_candles(_today_m5(_IMMATURE, 34))
    return repo


class TestMatureHistoryUniverseWiring:
    def test_immature_instrument_is_excluded_from_the_scanned_population(self, tmp_path):
        athena_repo = _seed_mixed_maturity_repo(tmp_path / "athena")
        emr_repo = EmrRepository(tmp_path / "emr" / "emr.db")
        emr_repo.initialize()

        outcome = _run(
            athena_repo, emr_repo, now=_at("09:20"),
            operational_config=_config(base_universe=_UNIVERSE_WITH_IMMATURE),
        )

        assert outcome.action == "INVOKED"
        assert outcome.scan_result.status == "COMPLETE"
        scanned_ids = {r["instrument_id"] for r in emr_repo.list_candidates(run_id=outcome.scan_result.run_id)}
        assert scanned_ids == {_MATURE_A, _MATURE_B}, (
            "the immature instrument must never appear in the scanned population -- "
            f"got {scanned_ids}, proving no silent fallback to the unfiltered full universe"
        )
        athena_repo.close()
        emr_repo.close()

    def test_all_immature_universe_refuses_to_invoke(self, tmp_path):
        athena_repo = _seed_mixed_maturity_repo(tmp_path / "athena")
        athena_repo.save_resolved_universe("em7b-all-immature", [_IMMATURE], resolved_at=_at("10:00"))
        emr_repo = EmrRepository(tmp_path / "emr" / "emr.db")
        emr_repo.initialize()
        collector = _CountingCollector()

        outcome = _run(
            athena_repo, emr_repo, now=_at("09:20"), collect_checkpoint_prices=collector,
            operational_config=_config(base_universe="em7b-all-immature"),
        )

        assert outcome.action == "UNEXPECTED_ERROR"
        assert "mature-history" in outcome.detail
        assert collector.calls == 0
        athena_repo.close()
        emr_repo.close()


class TestRegimeWiring:
    def test_worker_wires_the_real_canonical_regime_lookup(self, worker_setup, monkeypatch):
        athena_repo, emr_repo = worker_setup
        calls: list[dict] = []
        import athena.explosive_move.live.worker as worker_module

        real_builder = worker_module.build_canonical_regime_lookup

        def spy(*, market_port, config_dir, tzinfo):
            calls.append({"market_port": market_port, "config_dir": config_dir, "tzinfo": tzinfo})
            return real_builder(market_port=market_port, config_dir=config_dir, tzinfo=tzinfo)

        monkeypatch.setattr(worker_module, "build_canonical_regime_lookup", spy)

        outcome = _run(athena_repo, emr_repo, now=_at("09:20"))

        assert outcome.action == "INVOKED"
        assert len(calls) == 1, "the worker must construct the real canonical regime lookup, never omit it"
        assert calls[0]["config_dir"] == CONFIG_DIR
        assert calls[0]["tzinfo"] == IST
        assert isinstance(calls[0]["market_port"], SqliteEmrMarketDataAdapter)


class TestScannerToleranceAuthority:
    """EM-7B.1: max_checkpoint_price_delay_seconds must always equal the
    frozen checkpoint_reference_price.MAX_CHECKPOINT_OBSERVATION_DELAY_SECONDS
    bound -- proven by spying on the actual ScanCycleConfig the worker
    constructs, not merely by the field being absent from config."""

    def test_worker_uses_the_frozen_checkpoint_price_delay_bound(self, worker_setup, monkeypatch):
        from athena.explosive_move.live.checkpoint_reference_price import (
            MAX_CHECKPOINT_OBSERVATION_DELAY_SECONDS,
        )

        athena_repo, emr_repo = worker_setup
        captured: list = []
        import athena.explosive_move.live.worker as worker_module

        real_run_with_lock = worker_module.run_scan_cycle_with_lock

        def spy(*, config, **kwargs):
            captured.append(config)
            return real_run_with_lock(config=config, **kwargs)

        monkeypatch.setattr(worker_module, "run_scan_cycle_with_lock", spy)

        outcome = _run(athena_repo, emr_repo, now=_at("09:20"))

        assert outcome.action == "INVOKED"
        assert len(captured) == 1
        assert captured[0].max_checkpoint_price_delay_seconds == MAX_CHECKPOINT_OBSERVATION_DELAY_SECONDS


class TestProductionSafety:
    def test_production_emr_db_if_present_is_a_legitimately_valid_schema(self):
        """Historical note: prior to EM-7C (2026-09-04), this test
        asserted db/emr.db did not exist at all -- EM-7B's own scope
        never created it; production activation was explicitly out of
        scope. EM-7C then performed the first controlled,
        owner-authorized production activation, so db/emr.db now
        legitimately exists -- mirroring config/darvax.json's own
        committed-`enabled: true`-after-real-activation history (commit
        0987d41). This test's remaining job, now: if the file exists, it
        must be a genuinely valid, current-schema EMR database -- never a
        corrupted file or a stale schema left over from some other
        process. If it does not exist (e.g. a fresh checkout that has
        never activated EMR), that is equally valid and this test is a
        no-op."""
        import sqlite3

        repo_root = Path(__file__).resolve().parents[2]
        emr_db_path = repo_root / "db" / "emr.db"
        if not emr_db_path.exists():
            return
        conn = sqlite3.connect(f"file:{emr_db_path}?mode=ro", uri=True)
        try:
            conn.execute("PRAGMA query_only=ON")
            version = conn.execute("SELECT version FROM emr_schema_version").fetchone()[0]
            assert version == 2
        finally:
            conn.close()

    def test_instruments_seeded_with_full_maturity_are_all_mature(self, worker_setup):
        """Sanity check on the shared EM-5 fixture this whole file reuses:
        confirms INSTRUMENTS' 60 daily bars really do clear the 50-session
        maturity bar, so TestSingleTick/TestMultiCheckpointProgression's
        'the scan runs at all' assumption is not accidentally masking a
        maturity-filter bug."""
        athena_repo, emr_repo = worker_setup
        outcome = _run(athena_repo, emr_repo, now=_at("09:20"))
        scanned_ids = {r["instrument_id"] for r in emr_repo.list_candidates(run_id=outcome.scan_result.run_id)}
        assert scanned_ids == set(INSTRUMENTS)
