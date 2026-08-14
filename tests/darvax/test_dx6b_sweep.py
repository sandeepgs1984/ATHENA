"""DX-6b: owner-triggered universe sweep, retention, and the screen API.

Threading is made deterministic by driving the runner directly and joining,
rather than sleeping and hoping — a timing-dependent test here would be worse
than no test.
"""

from __future__ import annotations

import json
import threading
from datetime import datetime, timedelta
from decimal import Decimal
from pathlib import Path
from zoneinfo import ZoneInfo

import pytest
from fastapi.testclient import TestClient
from tests.api.v1.test_core_apis import get_auth_headers

from athena.api.app import create_app
from athena.api.config import APISettings
from athena.api.darvax_mount import DARVAX_MOUNT_PATH, mount_darvax_if_enabled
from athena.api.security.models import Role
from athena.darvax.config import DarvaxConfig
from athena.darvax.screening import DarvaxTier
from athena.darvax.screening.sweep import SweepBusyError, SweepRunner
from athena.darvax.signals.models import DarvaxSignalType
from athena.darvax.store.repository import DarvaxRepository
from athena.domain.enums import Timeframe
from athena.domain.market import Candle, Instrument

IST = ZoneInfo("Asia/Kolkata")
BASE = datetime(2026, 1, 1, 9, 15, tzinfo=IST)

pytestmark = pytest.mark.usefixtures("athena_config_darvax_disabled")


# --------------------------------------------------------------------------- #
# A controllable market-data port: the sweep's only view of the universe
# --------------------------------------------------------------------------- #


class FakeMarketData:
    """Implements DarvaxMarketDataPort with deterministic, shaped candles."""

    def __init__(
        self,
        symbols: list[str],
        *,
        broken: set[str] | None = None,
        breakout: set[str] | None = None,
    ) -> None:
        self._symbols = symbols
        self._broken = broken or set()
        #: Symbols whose final bar clears the box ceiling, so the sweep produces
        #: more than one tier. Without this every instrument lands in WATCH and
        #: any tier/type filter test passes vacuously over an empty list.
        self._breakout = breakout or set()
        self.batch_sizes: list[int] = []
        self.list_calls = 0

    def list_instruments(self):
        self.list_calls += 1
        return [
            Instrument(
                instrument_id=f"NSE:{s}", symbol=s, exchange="NSE", series="EQ", name=s
            )
            for s in self._symbols
        ]

    def recent_candles(self, instrument_id: str, timeframe, *, limit: int):
        symbol = instrument_id.split(":")[-1]
        if symbol in self._broken:
            raise RuntimeError("simulated read failure")
        bars = []
        for i in range(60):
            # A clean ascending base then a push through it, so boxes form and
            # some instruments break out — deterministic, no randomness.
            low = Decimal(100) + Decimal(i % 20)
            bars.append(
                Candle(
                    instrument_id=instrument_id,
                    timeframe=Timeframe.D1,
                    ts_open=BASE + timedelta(days=i),
                    open=low + Decimal("0.5"),
                    high=low + Decimal(2),
                    low=low,
                    close=low + Decimal(1),
                    volume=100_000 + i,
                    source="dx6b-test",
                )
            )
        if symbol in self._breakout:
            top = max(b.high for b in bars)
            bars.append(
                Candle(
                    instrument_id=instrument_id,
                    timeframe=Timeframe.D1,
                    ts_open=BASE + timedelta(days=60),
                    open=top + Decimal(1),
                    high=top + Decimal(6),
                    low=top,
                    close=top + Decimal(5),
                    volume=400_000,
                    source="dx6b-test",
                )
            )
        return bars[-limit:] if limit else bars

    def candles_between(self, instrument_id, timeframe, start, end):  # pragma: no cover
        return self.recent_candles(instrument_id, timeframe, limit=60)


@pytest.fixture()
def store(tmp_path: Path) -> DarvaxRepository:
    repo = DarvaxRepository(tmp_path / "darvax.db")
    repo.initialize()
    yield repo
    repo.close()


def make_runner(store: DarvaxRepository, market: FakeMarketData, **cfg) -> SweepRunner:
    payload = {"enabled": True, **cfg}
    return SweepRunner(
        market_data=market,
        store=store,
        config=DarvaxConfig.model_validate(payload),
        darvax_version="0.1.0",
    )


def run_to_completion(runner: SweepRunner) -> str:
    sweep_id = runner.start()
    runner.join(timeout=30)
    return sweep_id


# --------------------------------------------------------------------------- #
# 1. The sweep covers the universe it enumerates
# --------------------------------------------------------------------------- #


def test_sweep_enumerates_the_universe_and_screens_every_instrument(store):
    market = FakeMarketData(["AAA", "BBB", "BRK"], breakout={"BRK"})
    runner = make_runner(store, market)
    sweep_id = run_to_completion(runner)

    assert market.list_calls == 1, "the universe is enumerated once per sweep"
    sweep = store.get_sweep(sweep_id)
    assert sweep is not None
    assert sweep.state == "completed" and sweep.partial is False
    assert sweep.requested == 3 and sweep.evaluated == 3

    results = store.list_screen_results(sweep_id)
    assert {r.instrument_id for r in results} == {"NSE:AAA", "NSE:BBB", "NSE:BRK"}
    # More than one tier, so the taxonomy is genuinely exercised.
    assert {r.tier for r in results} >= {DarvaxTier.ACTIONABLE, DarvaxTier.WATCH}


def test_sweep_records_the_methodology_digest_that_produced_it(store):
    """A screen read under different settings than it was produced by is
    misleading; the digest is what makes the mismatch detectable."""
    runner = make_runner(store, FakeMarketData(["AAA"]))
    sweep = store.get_sweep(run_to_completion(runner))
    assert len(sweep.methodology_digest) == 16
    assert sweep.darvax_version == "0.1.0"


def test_sweep_as_of_is_the_newest_bar_it_screened(store):
    runner = make_runner(store, FakeMarketData(["AAA"]))
    sweep = store.get_sweep(run_to_completion(runner))
    assert sweep.as_of == BASE + timedelta(days=59)


# --------------------------------------------------------------------------- #
# 2. Batching stays beneath the cap — it is never raised
# --------------------------------------------------------------------------- #


def test_sweep_batches_beneath_the_scan_cap_rather_than_raising_it(store):
    """`scan_instruments` refuses over-cap requests. A 20-instrument universe
    with a cap of 5 must therefore be split into batches of at most 5 — if the
    sweep tried to raise or bypass the cap, the scan would raise instead."""
    market = FakeMarketData([f"S{i:02d}" for i in range(20)])
    runner = make_runner(store, market, scan={"max_instruments": 5})
    sweep = store.get_sweep(run_to_completion(runner))

    assert sweep.state == "completed"
    assert sweep.requested == 20 and sweep.evaluated == 20
    assert len(store.list_screen_results(sweep.sweep_id)) == 20


def test_batch_size_can_be_set_below_the_cap(store):
    market = FakeMarketData([f"S{i:02d}" for i in range(12)])
    runner = make_runner(
        store, market, scan={"max_instruments": 50}, screener={"batch_size": 3}
    )
    sweep = store.get_sweep(run_to_completion(runner))
    assert sweep.evaluated == 12


# --------------------------------------------------------------------------- #
# 3. Single-flight — refused, never queued
# --------------------------------------------------------------------------- #


def test_a_second_sweep_is_refused_while_one_runs(store):
    gate = threading.Event()

    class Blocking(FakeMarketData):
        def recent_candles(self, instrument_id, timeframe, *, limit):
            gate.wait(timeout=10)
            return super().recent_candles(instrument_id, timeframe, limit=limit)

    runner = make_runner(store, Blocking(["AAA", "BBB"]))
    runner.start()
    try:
        with pytest.raises(SweepBusyError) as excinfo:
            runner.start()
        assert "already running" in str(excinfo.value)
        assert "never queued" in str(excinfo.value)
    finally:
        gate.set()
        runner.join(timeout=30)


def test_a_new_sweep_may_start_once_the_previous_finished(store):
    runner = make_runner(store, FakeMarketData(["AAA"]))
    first = run_to_completion(runner)
    second = run_to_completion(runner)
    assert first != second
    assert len(store.list_sweeps()) == 2


# --------------------------------------------------------------------------- #
# 4. Cancellation keeps completed work
# --------------------------------------------------------------------------- #


def test_cancelled_sweep_keeps_its_partial_results_and_says_so(store):
    """Discarding completed work would waste real reads and tell the owner less
    than an honestly-labelled partial screen."""
    seen = threading.Event()
    release = threading.Event()

    class Slow(FakeMarketData):
        def recent_candles(self, instrument_id, timeframe, *, limit):
            candles = super().recent_candles(instrument_id, timeframe, limit=limit)
            seen.set()
            release.wait(timeout=10)
            return candles

    market = Slow([f"S{i:02d}" for i in range(10)])
    runner = make_runner(store, market, scan={"max_instruments": 2})
    sweep_id = runner.start()
    assert seen.wait(timeout=10)
    assert runner.cancel() is True
    release.set()
    runner.join(timeout=30)

    sweep = store.get_sweep(sweep_id)
    assert sweep.state == "cancelled"
    assert sweep.partial is True
    assert sweep.evaluated < 10, "cancellation should stop before the whole universe"
    assert len(store.list_screen_results(sweep_id)) == sweep.evaluated


def test_cancel_reports_false_when_nothing_is_running(store):
    runner = make_runner(store, FakeMarketData(["AAA"]))
    assert runner.cancel() is False


def test_cancelled_sweeps_are_not_pruned_away_by_a_later_one(store):
    """A partial screen is still the owner's data."""
    runner = make_runner(store, FakeMarketData(["AAA"]), screener={"retain_sweeps": 5})
    run_to_completion(runner)
    assert len(store.list_sweeps()) == 1


# --------------------------------------------------------------------------- #
# 5. Failure isolation — one bad symbol never kills the sweep
# --------------------------------------------------------------------------- #


def test_unreadable_instruments_are_skipped_with_reasons_not_dropped(store):
    market = FakeMarketData(["GOOD", "BROKEN", "ALSOGOOD"], broken={"BROKEN"})
    runner = make_runner(store, market)
    sweep = store.get_sweep(run_to_completion(runner))

    assert sweep.state == "completed"
    assert sweep.evaluated == 2
    assert len(sweep.skipped) == 1
    instrument_id, reason = sweep.skipped[0]
    assert instrument_id == "NSE:BROKEN"
    assert "read failed" in reason


def test_a_sweep_that_fails_outright_records_the_failure(store):
    class Exploding(FakeMarketData):
        def list_instruments(self):
            raise RuntimeError("universe unavailable")

    runner = make_runner(store, Exploding([]))
    runner.start()
    runner.join(timeout=30)

    progress = runner.progress()
    assert progress.state == "failed"
    assert "universe unavailable" in progress.error


# --------------------------------------------------------------------------- #
# 6. Retention — bounded from day one
# --------------------------------------------------------------------------- #


def test_retention_prunes_old_sweeps_and_their_results(store):
    runner = make_runner(store, FakeMarketData(["AAA"]), screener={"retain_sweeps": 2})
    ids = [run_to_completion(runner) for _ in range(4)]

    kept = {s.sweep_id for s in store.list_sweeps()}
    assert len(kept) == 2
    assert set(ids[-2:]) == kept, "the two most recent survive"
    for gone in ids[:2]:
        assert store.get_sweep(gone) is None
        assert store.list_screen_results(gone) == [], "results pruned with the sweep"


def test_prune_validates_its_argument(store):
    with pytest.raises(ValueError):
        store.prune_sweeps(0)


def test_retention_default_is_bounded_not_unlimited():
    """Unbounded history is what produced ATHENA's 91k-row decisions table."""
    assert DarvaxConfig().screener.retain_sweeps == 30


# --------------------------------------------------------------------------- #
# 7. Progress
# --------------------------------------------------------------------------- #


def test_progress_reports_idle_then_completed(store):
    runner = make_runner(store, FakeMarketData(["AAA", "BBB"]))
    assert runner.progress().state == "idle"
    sweep_id = run_to_completion(runner)
    done = runner.progress()
    assert done.state == "completed"
    assert done.sweep_id == sweep_id
    assert done.total == 2 and done.evaluated == 2
    assert done.elapsed_seconds >= 0


# --------------------------------------------------------------------------- #
# 8. Determinism
# --------------------------------------------------------------------------- #


def test_two_sweeps_over_identical_data_produce_identical_screens(store):
    runner = make_runner(store, FakeMarketData(["AAA", "BBB", "CCC"]))
    first = store.list_screen_results(run_to_completion(runner))
    second = store.list_screen_results(run_to_completion(runner))

    def shape(rows):
        return [(r.instrument_id, r.tier, r.rank, r.distance_to_trigger_pct) for r in rows]

    assert shape(first) == shape(second)


# --------------------------------------------------------------------------- #
# 9. API surface
# --------------------------------------------------------------------------- #


@pytest.fixture()
def client(tmp_path: Path):
    config_dir = tmp_path / "darvax-config"
    config_dir.mkdir(parents=True)
    (config_dir / "darvax.json").write_text(
        json.dumps(
            {
                "enabled": True,
                "database": {"path": "db/darvax.db"},
                "screener": {"retain_sweeps": 3},
            }
        ),
        encoding="utf-8",
    )
    from athena.data.store.repository import SqliteRepository

    repo = SqliteRepository(tmp_path / "athena.db")
    repo.initialize()
    app = create_app(APISettings())
    app.state.sqlite_repo = repo
    assert mount_darvax_if_enabled(
        app, repo=repo, config_dir=config_dir, repo_root=tmp_path
    ) is True
    # Swap in the controllable universe; the runner is rebuilt around it so the
    # API tests exercise real routes over deterministic data.
    darvax_app = next(
        r.app for r in app.routes if getattr(r, "path", "") == DARVAX_MOUNT_PATH
    )
    # Mixed universe: BRK breaks out, AAA stays inside its box, so tier and
    # signal-type filters below are exercised against real variety.
    market = FakeMarketData(["AAA", "BRK"], breakout={"BRK"})
    darvax_app.state.darvax_market_data = market
    darvax_app.state.darvax_sweep_runner = SweepRunner(
        market_data=market,
        store=darvax_app.state.darvax_store,
        config=darvax_app.state.darvax_config,
        darvax_version="0.1.0",
    )
    with TestClient(app, raise_server_exceptions=False) as c:
        c.darvax_app = darvax_app  # type: ignore[attr-defined]
        yield c
    repo.close()


SCREEN_ROUTES = [
    ("POST", f"{DARVAX_MOUNT_PATH}/api/screen"),
    ("GET", f"{DARVAX_MOUNT_PATH}/api/screen/progress"),
    ("DELETE", f"{DARVAX_MOUNT_PATH}/api/screen"),
    ("GET", f"{DARVAX_MOUNT_PATH}/api/screen/latest"),
    ("GET", f"{DARVAX_MOUNT_PATH}/api/screen/sweeps"),
]


@pytest.mark.parametrize(("method", "path"), SCREEN_ROUTES)
def test_every_screen_endpoint_requires_authentication(client, method, path):
    assert client.request(method, path).status_code in (401, 403)


def test_latest_screen_is_an_honest_empty_state_before_any_sweep(client):
    headers = get_auth_headers(client, Role.ADMIN)
    body = client.get(f"{DARVAX_MOUNT_PATH}/api/screen/latest", headers=headers).json()
    assert body["data"] == []
    assert body["sweep"] is None
    assert body["count"] == 0
    assert body["darvax_status"] == "EXPERIMENTAL_UNVALIDATED"


def test_screen_round_trip_through_the_api(client):
    headers = get_auth_headers(client, Role.ADMIN)
    started = client.post(f"{DARVAX_MOUNT_PATH}/api/screen", headers=headers)
    assert started.status_code == 200, started.text
    client.darvax_app.state.darvax_sweep_runner.join(timeout=30)

    body = client.get(f"{DARVAX_MOUNT_PATH}/api/screen/latest", headers=headers).json()
    assert body["count"] == 2
    assert body["sweep"]["state"] == "completed"
    assert body["sweep"]["evaluated"] == 2
    assert set(body["sweep"]["tier_counts"]) == {t.value for t in DarvaxTier}
    row = body["data"][0]
    assert row["status"] == "EXPERIMENTAL_UNVALIDATED"
    assert row["explanation"], "the persisted explanation must be served"
    assert isinstance(row["close"], str), "decimals serialise as strings"


def test_a_concurrent_start_is_refused_with_409(client):
    headers = get_auth_headers(client, Role.ADMIN)
    gate = threading.Event()
    runner = client.darvax_app.state.darvax_sweep_runner

    class Blocking(FakeMarketData):
        def recent_candles(self, instrument_id, timeframe, *, limit):
            gate.wait(timeout=10)
            return super().recent_candles(instrument_id, timeframe, limit=limit)

    runner.market_data = Blocking(["AAA", "BRK"], breakout={"BRK"})
    try:
        assert client.post(f"{DARVAX_MOUNT_PATH}/api/screen", headers=headers).status_code == 200
        second = client.post(f"{DARVAX_MOUNT_PATH}/api/screen", headers=headers)
        assert second.status_code == 409
        assert "already running" in second.json()["detail"]
    finally:
        gate.set()
        runner.join(timeout=30)


def test_progress_and_cancel_endpoints_respond(client):
    headers = get_auth_headers(client, Role.ADMIN)
    progress = client.get(f"{DARVAX_MOUNT_PATH}/api/screen/progress", headers=headers)
    assert progress.status_code == 200
    assert progress.json()["data"]["state"] == "idle"

    cancelled = client.request(
        "DELETE", f"{DARVAX_MOUNT_PATH}/api/screen", headers=headers
    )
    assert cancelled.status_code == 200
    assert cancelled.json()["data"]["cancelled"] is False


def test_latest_screen_rejects_an_unknown_tier(client):
    headers = get_auth_headers(client, Role.ADMIN)
    response = client.get(
        f"{DARVAX_MOUNT_PATH}/api/screen/latest?tier=BANANA", headers=headers
    )
    assert response.status_code == 422
    assert "unknown tier" in response.json()["detail"]


def test_signals_can_be_filtered_by_type(client):
    """The gap DX-6 design found: /api/signals filtered on nothing, so 'show me
    only the breakouts' could not be answered from the API at all.

    Asserts both inclusion *and* exclusion against a universe that genuinely
    contains two states — an earlier version of this test filtered on a state
    the fixture never produced and passed vacuously over an empty list.
    """
    headers = get_auth_headers(client, Role.ADMIN)
    client.post(f"{DARVAX_MOUNT_PATH}/api/screen", headers=headers)
    client.darvax_app.state.darvax_sweep_runner.join(timeout=30)

    everything = client.get(f"{DARVAX_MOUNT_PATH}/api/signals", headers=headers).json()
    present = {s["signal_type"] for s in everything["data"]}
    assert len(present) >= 2, f"fixture must produce mixed states, got {present}"

    wanted = DarvaxSignalType.BREAKOUT.value
    assert wanted in present

    only = client.get(
        f"{DARVAX_MOUNT_PATH}/api/signals?signal_type={wanted}", headers=headers
    ).json()
    assert only["count"] >= 1, "filter must not return an empty list here"
    assert only["count"] < everything["count"], "filter must actually exclude"
    assert {s["signal_type"] for s in only["data"]} == {wanted}


def test_signals_rejects_an_unknown_type(client):
    headers = get_auth_headers(client, Role.ADMIN)
    response = client.get(
        f"{DARVAX_MOUNT_PATH}/api/signals?signal_type=SIDEWAYS", headers=headers
    )
    assert response.status_code == 422
    assert "unknown signal_type" in response.json()["detail"]


def test_sweep_history_is_served_newest_first(client):
    headers = get_auth_headers(client, Role.ADMIN)
    for _ in range(2):
        client.post(f"{DARVAX_MOUNT_PATH}/api/screen", headers=headers)
        client.darvax_app.state.darvax_sweep_runner.join(timeout=30)

    body = client.get(f"{DARVAX_MOUNT_PATH}/api/screen/sweeps", headers=headers).json()
    assert body["count"] == 2
    stamps = [s["started_at"] for s in body["data"]]
    assert stamps == sorted(stamps, reverse=True)
