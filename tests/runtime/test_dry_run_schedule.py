"""M10.2 scheduled dry-run: cadence evaluation + cycle orchestration + run ledger."""

from __future__ import annotations

from datetime import date, datetime, time, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

import pytest

from athena.calendar.engine import CalendarEngine
from athena.config.loader import load_config, load_scheduling_config, load_validation_config
from athena.config.models import (
    FileProviderConfig,
    IngestionConfig,
    PremarketScheduleConfig,
    ProviderCapabilitiesConfig,
    RefreshScheduleConfig,
    SchedulingConfig,
    SessionsConfig,
)
from athena.data.ingestion import LiveIngestionEngine, build_ingest_validator
from athena.data.ingestion.models import IngestionResult
from athena.data.providers.file_provider import FileProvider
from athena.data.store import SCHEMA_VERSION, SqliteRepository
from athena.data.validation import QuarantineRegistry
from athena.domain.enums import RunStatus, RunTrigger
from athena.errors import DataStaleError
from athena.scheduling import (
    DryRunCycleOrchestrator,
    due_triggers,
    is_closing_due,
    is_premarket_due,
    is_refresh_due,
)

IST = ZoneInfo("Asia/Kolkata")
SESSIONS = SessionsConfig(
    preopen_start=time(9, 0),
    preopen_end=time(9, 15),
    open=time(9, 15),
    close=time(15, 30),
)


def _sched(**kw) -> SchedulingConfig:
    base = dict(
        record_history=True,
        premarket=PremarketScheduleConfig(enabled=True, run_at=time(8, 15)),
        refresh=RefreshScheduleConfig(enabled=True, interval_minutes=15),
    )
    base.update(kw)
    return SchedulingConfig(**base)


class TestCadence:
    def test_premarket_due_in_window(self):
        as_of = datetime(2026, 2, 13, 8, 20, tzinfo=IST)
        assert is_premarket_due(
            as_of, sessions=SESSIONS, config=_sched(), last_premarket_date=None,
        )

    def test_premarket_not_before_run_at(self):
        as_of = datetime(2026, 2, 13, 8, 0, tzinfo=IST)
        assert not is_premarket_due(
            as_of, sessions=SESSIONS, config=_sched(), last_premarket_date=None,
        )

    def test_premarket_not_after_open(self):
        as_of = datetime(2026, 2, 13, 9, 20, tzinfo=IST)
        assert not is_premarket_due(
            as_of, sessions=SESSIONS, config=_sched(), last_premarket_date=None,
        )

    def test_premarket_once_per_day(self):
        as_of = datetime(2026, 2, 13, 8, 20, tzinfo=IST)
        assert not is_premarket_due(
            as_of, sessions=SESSIONS, config=_sched(),
            last_premarket_date=date(2026, 2, 13),
        )

    def test_refresh_due_in_session(self):
        as_of = datetime(2026, 2, 13, 10, 0, tzinfo=IST)
        assert is_refresh_due(
            as_of, sessions=SESSIONS, config=_sched(),
            base_interval_minutes=15, last_refresh_ts=None,
        )

    def test_refresh_respects_interval(self):
        as_of = datetime(2026, 2, 13, 10, 10, tzinfo=IST)
        last = datetime(2026, 2, 13, 10, 0, tzinfo=IST)
        assert not is_refresh_due(
            as_of, sessions=SESSIONS, config=_sched(),
            base_interval_minutes=15, last_refresh_ts=last,
        )
        assert is_refresh_due(
            as_of + timedelta(minutes=5), sessions=SESSIONS, config=_sched(),
            base_interval_minutes=15, last_refresh_ts=last,
        )

    def test_refresh_not_outside_session(self):
        as_of = datetime(2026, 2, 13, 16, 0, tzinfo=IST)
        assert not is_refresh_due(
            as_of, sessions=SESSIONS, config=_sched(),
            base_interval_minutes=15, last_refresh_ts=None,
        )

    def test_due_triggers_order(self):
        # Artificial sessions: open late so premarket + refresh can't both fire;
        # use a mid window only for premarket.
        as_of = datetime(2026, 2, 13, 8, 20, tzinfo=IST)
        due = due_triggers(
            as_of, sessions=SESSIONS, config=_sched(),
            base_interval_minutes=15,
        )
        assert due == (RunTrigger.PREMARKET,)

    def test_closing_due_after_run_at(self):
        as_of = datetime(2026, 2, 13, 15, 50, tzinfo=IST)
        assert is_closing_due(
            as_of, sessions=SESSIONS, config=_sched(), last_closing_date=None,
        )

    def test_closing_not_before_session_close(self):
        as_of = datetime(2026, 2, 13, 15, 0, tzinfo=IST)
        assert not is_closing_due(
            as_of, sessions=SESSIONS, config=_sched(), last_closing_date=None,
        )

    def test_closing_once_per_day(self):
        as_of = datetime(2026, 2, 13, 16, 0, tzinfo=IST)
        assert not is_closing_due(
            as_of, sessions=SESSIONS, config=_sched(),
            last_closing_date=date(2026, 2, 13),
        )

    def test_due_triggers_includes_closing_after_hours(self):
        as_of = datetime(2026, 2, 13, 16, 0, tzinfo=IST)
        due = due_triggers(
            as_of, sessions=SESSIONS, config=_sched(),
            base_interval_minutes=15,
        )
        assert due == (RunTrigger.CLOSING,)


class TestSchedulingConfigLoad:
    def test_loads_extended_scheduling_config(self, config_dir):
        cfg = load_scheduling_config(config_dir)
        assert cfg.premarket.enabled is True
        assert cfg.premarket.run_at == time(8, 15)
        assert cfg.refresh.interval_minutes is None


class FakeIngest:
    def __init__(self, result: IngestionResult | None = None, *, fail: Exception | None = None):
        self._result = result
        self._fail = fail
        self.calls = 0

    def run_cycle(self, *, as_of: datetime) -> IngestionResult:
        self.calls += 1
        if self._fail is not None:
            raise self._fail
        assert self._result is not None
        return self._result


class RecordingPipeline:
    def __init__(self):
        self.calls: list[RunTrigger] = []
        self.run_ids: list[str] = []

    def run(self, trigger, *, as_of, ingestion, run_id):
        self.calls.append(trigger)
        self.run_ids.append(run_id)
        return {"mode": "paper_pipeline", "ok": True, "as_of": as_of.isoformat()}


def _ingestion(as_of: datetime) -> IngestionResult:
    return IngestionResult(
        as_of=as_of,
        instruments_upserted=1,
        candles_fetched=3,
        candles_written=3,
        quotes_fetched=1,
        quotes_written=1,
        datasets_validated=2,
        datasets_skipped_empty=0,
    )


class TestDryRunCycle:
    def test_persists_completed_run(self, tmp_path):
        as_of = datetime(2026, 2, 13, 8, 20, tzinfo=IST)
        repo = SqliteRepository(tmp_path / "athena.db")
        repo.initialize()
        assert SCHEMA_VERSION == 7

        pipe = RecordingPipeline()
        orch = DryRunCycleOrchestrator(
            FakeIngest(_ingestion(as_of)),  # type: ignore[arg-type]
            repo,
            pipeline=pipe,
            run_id_factory=lambda t, a: "run-test-1",
        )
        result = orch.run_cycle(RunTrigger.PREMARKET, as_of=as_of)
        assert result.run.status is RunStatus.COMPLETED
        assert pipe.calls == [RunTrigger.PREMARKET]
        stored = repo.get_run("run-test-1")
        assert stored is not None
        assert stored.status is RunStatus.COMPLETED
        assert stored.trigger is RunTrigger.PREMARKET
        detail = repo.get_run_detail("run-test-1")
        assert detail["ingestion"]["candles_written"] == 3
        repo.close()

    def test_failure_persists_then_raises(self, tmp_path):
        as_of = datetime(2026, 2, 13, 10, 0, tzinfo=IST)
        repo = SqliteRepository(tmp_path / "athena.db")
        repo.initialize()
        orch = DryRunCycleOrchestrator(
            FakeIngest(fail=DataStaleError("stale quotes")),  # type: ignore[arg-type]
            repo,
            run_id_factory=lambda t, a: "run-fail-1",
        )
        with pytest.raises(DataStaleError, match=r"stale quotes"):
            orch.run_cycle(RunTrigger.REFRESH, as_of=as_of)
        stored = repo.get_run("run-fail-1")
        assert stored is not None
        assert stored.status is RunStatus.FAILED
        repo.close()

    def test_refresh_run_id_unique_per_call_even_with_same_as_of(self, tmp_path):
        """Regression test: outside live trading hours, resolve_validate_as_of
        always resolves to the same fixed session-close timestamp, so two
        separate ad-hoc REFRESH validations (e.g. two different symbols,
        each via the dashboard's "Re-validate") previously collided on the
        same default run_id. SqliteRepository.save_run's upsert
        (ON CONFLICT(run_id) DO UPDATE ... detail_json=excluded.detail_json)
        then silently overwrote the first call's persisted decision_reports —
        orphaning its decisions, which would render Score/Confidence/Risk as
        "Unknown" until re-validated again. Uses the real default
        run_id_factory (no override) to exercise the actual bug path."""
        as_of = datetime(2026, 2, 13, 15, 30, tzinfo=IST)
        repo = SqliteRepository(tmp_path / "athena.db")
        repo.initialize()

        pipe_a = RecordingPipeline()
        orch_a = DryRunCycleOrchestrator(
            FakeIngest(_ingestion(as_of)),  # type: ignore[arg-type]
            repo,
            pipeline=pipe_a,
        )
        result_a = orch_a.run_cycle(RunTrigger.REFRESH, as_of=as_of)

        pipe_b = RecordingPipeline()
        orch_b = DryRunCycleOrchestrator(
            FakeIngest(_ingestion(as_of)),  # type: ignore[arg-type]
            repo,
            pipeline=pipe_b,
        )
        result_b = orch_b.run_cycle(RunTrigger.REFRESH, as_of=as_of)

        assert result_a.run.run_id != result_b.run.run_id

        # The first run's persisted detail must survive the second run's
        # write — this is the exact data-loss the bug caused.
        first_detail = repo.get_run_detail(result_a.run.run_id)
        second_detail = repo.get_run_detail(result_b.run.run_id)
        assert first_detail["pipeline"]["as_of"] == as_of.isoformat()
        assert second_detail["pipeline"]["as_of"] == as_of.isoformat()
        assert repo.get_run(result_a.run.run_id) is not None
        assert repo.get_run(result_b.run.run_id) is not None
        repo.close()

    def test_premarket_run_id_still_deterministic_for_same_as_of(self, tmp_path):
        """PREMARKET/CLOSING are scheduled, at-most-once-per-day cycles where
        a stable run_id may be relied on for idempotent retries of the same
        logical run — confirm the fix does not touch this trigger's id
        format."""
        as_of = datetime(2026, 2, 13, 8, 20, tzinfo=IST)
        repo = SqliteRepository(tmp_path / "athena.db")
        repo.initialize()
        orch = DryRunCycleOrchestrator(
            FakeIngest(_ingestion(as_of)),  # type: ignore[arg-type]
            repo,
            pipeline=RecordingPipeline(),
        )
        result = orch.run_cycle(RunTrigger.PREMARKET, as_of=as_of)
        assert result.run.run_id == "run-premarket-20260213T082000"
        repo.close()


def _write_provider_tree(root: Path) -> FileProvider:
    root.mkdir(parents=True, exist_ok=True)
    (root / "daily").mkdir()
    (root / "intraday" / "5m").mkdir(parents=True)
    (root / "instruments.csv").write_text(
        "instrument_id,symbol,exchange,series,isin,lot_size,tick_size,status,listed_date,delisted_date\n"
        "SYN-AAA,AAA,NSE,EQ,,1,0.05,ACTIVE,,\n",
        encoding="utf-8",
    )
    (root / "daily" / "SYN-AAA.csv").write_text(
        "ts_open,open,high,low,close,volume\n"
        "2026-02-11T09:15:00+05:30,107.00,109.00,106.00,108.00,1000\n"
        "2026-02-12T09:15:00+05:30,108.00,110.00,107.00,109.00,1000\n"
        "2026-02-13T09:15:00+05:30,109.00,111.00,108.00,110.00,1000\n",
        encoding="utf-8",
    )
    (root / "intraday" / "5m" / "SYN-AAA.csv").write_text(
        "ts_open,open,high,low,close,volume\n"
        "2026-02-13T15:20:00+05:30,109.00,109.50,108.80,109.20,100\n"
        "2026-02-13T15:25:00+05:30,109.20,109.60,109.00,109.40,100\n"
        "2026-02-13T15:30:00+05:30,109.40,109.80,109.20,109.50,100\n",
        encoding="utf-8",
    )
    (root / "quotes.csv").write_text(
        "instrument_id,ts,last_price,volume\n"
        "SYN-AAA,2026-02-13T15:30:00+05:30,109.50,42000\n",
        encoding="utf-8",
    )
    (root / "snapshot.json").write_text(
        '{"ts":"2026-02-13T15:30:00+05:30","indices":{"NIFTY50":25000},"breadth_advances":1,'
        '"breadth_declines":0,"india_vix":14.5}',
        encoding="utf-8",
    )
    cfg = FileProviderConfig(
        data_root=str(root), instruments_file="instruments.csv", daily_dir="daily",
        intraday_dir="intraday", quotes_file="quotes.csv", snapshot_file="snapshot.json",
        capabilities=ProviderCapabilitiesConfig(
            timeframes=["1d", "5m"], max_history_days=365,
            supports_quotes=True, supports_market_snapshot=True,
        ),
    )
    return FileProvider(cfg, root)


class TestEndToEndIngestCycle:
    def test_file_provider_cycle_writes_run(self, tmp_path, config_dir):
        as_of = datetime(2026, 2, 13, 15, 35, tzinfo=IST)
        provider = _write_provider_tree(tmp_path / "data")
        base = load_config(config_dir)
        calendar = CalendarEngine.from_config_dir(config_dir, base.market)
        vcfg = load_validation_config(config_dir)
        ingest_cfg = IngestionConfig(
            provider="file", timeframes=["5m"], lookback_minutes=30, lookback_days=5,
            include_daily=True, include_quotes=True, validate_gaps=False,
            skip_existing=True, instrument_ids=["SYN-AAA"],
        )
        validator = build_ingest_validator(calendar, vcfg, ingest_cfg, IST)
        repo = SqliteRepository(tmp_path / "athena.db")
        repo.initialize()
        ingest = LiveIngestionEngine(
            provider, repo, validator, QuarantineRegistry(), ingest_cfg, vcfg, tzinfo=IST,
        )
        orch = DryRunCycleOrchestrator(
            ingest, repo, run_id_factory=lambda t, a: "run-e2e-1",
        )
        result = orch.run_cycle(RunTrigger.REFRESH, as_of=as_of)
        assert result.run.status is RunStatus.COMPLETED
        assert result.ingestion is not None
        assert result.ingestion.quotes_written == 1
        assert repo.record_counts()["runs"] == 1
        assert repo.latest_run("REFRESH") is not None
        repo.close()
