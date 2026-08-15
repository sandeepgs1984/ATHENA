"""DX-4a performance harness: what does an enabled DarvaX cost ATHENA?

ADR-010 §Consequences makes a precise claim and refuses to overstate it: DarvaX
introduces **no synchronous dependency** into ATHENA's request, decision,
scoring, scheduler, write, or dashboard-render paths — but it does *not* claim
zero performance effect, because both run on one workstation and DarvaX reads
ATHENA's SQLite ledger. Host-level contention is therefore to be **measured, not
assumed away**. This harness is that measurement.

Deliberately **not** a pytest test. Wall-clock latency is nondeterministic, so
asserting thresholds on it would produce a flaky suite that gets muted — the
opposite of evidence. It is a script that prints numbers for a human to read and
for `docs/design/DARVAX-PERFORMANCE-EVIDENCE.md` to record.

It lives under ``tests/darvax/`` so that deleting DarvaX still deletes all of
it, preserving ADR-010's "enabled, disabled, or deleted" property.

## Two modes

**In-process (default)** — the primary evidence, because it is the only mode
that can isolate the variable. One seeded temp ledger, three states measured
over the same data:

* ``A`` DarvaX disabled
* ``B`` DarvaX enabled, idle
* ``C`` DarvaX enabled **and actively scanning** in a background thread

`B - A` is the cost of merely mounting the satellite. `C - A` is the contention
ADR-010 asks about: DarvaX reading the same SQLite file while ATHENA serves.
State C is the one that matters — an idle satellite is uninteresting by
construction, since nothing is running.

Authenticated routes are included, using the same in-process token helper the
test suite uses. No owner credential is involved anywhere in this file.

**Live (`--live`)** — probes the real running workstation, which is what ADR-010
asks for. Run it once with DarvaX disabled and once enabled to get true
on-workstation before/after numbers. Unauthenticated routes are measured by
default; export ``ATHENA_BENCH_TOKEN`` to include authenticated ones. This
script never asks for, stores, or reads a password.

## What is deliberately NOT measured, and why

``POST /api/v1/market/validate`` — the endpoint whose latency the owner cares
about most — is **excluded**. It writes `Decision` rows, so benchmarking it
against the live ledger would pollute an immutable, append-only decision history
for the sake of a timing number. That trade is not worth making. The mechanism
by which DarvaX could plausibly slow a validate is shared-SQLite contention, and
state C measures that mechanism directly on read paths.

Usage:
    python3 tests/darvax/bench/darvax_perf_bench.py                 # in-process A/B/C
    python3 tests/darvax/bench/darvax_perf_bench.py --live          # running server
    python3 tests/darvax/bench/darvax_perf_bench.py --reps 60 --rounds 5
    python3 tests/darvax/bench/darvax_perf_bench.py --json out.json
"""

from __future__ import annotations

import argparse
import json
import os
import statistics
import sys
import threading
import time
from collections.abc import Callable, Iterable, Sequence
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from decimal import Decimal
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[3]
if str(REPO_ROOT / "src") not in sys.path:
    sys.path.insert(0, str(REPO_ROOT / "src"))
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

#: ATHENA read paths spanning what ADR-010 names: dashboard load, decision path,
#: market intelligence. Kept to reads — see the module docstring on validate.
IN_PROCESS_ROUTES: tuple[tuple[str, str, bool], ...] = (
    # (label, path, needs_auth)
    ("health", "/health", False),
    ("dashboard_html", "/dashboard/", False),
    ("dashboard_js", "/dashboard/dashboard.js", False),
    ("dashboard_summary", "/api/v1/dashboard/summary", False),
    ("decisions_list", "/api/v1/decisions", True),
    ("decisions_latest", "/api/v1/decisions/latest", True),
    ("portfolio", "/api/v1/portfolio", True),
    ("market_summary", "/api/v1/market/summary", True),
)

LIVE_ROUTES: tuple[tuple[str, str, bool], ...] = IN_PROCESS_ROUTES


# --------------------------------------------------------------------------- #
# Measurement primitives
# --------------------------------------------------------------------------- #


@dataclass
class Sample:
    """Latencies for one route in one state, in milliseconds."""

    label: str
    millis: list[float] = field(default_factory=list)
    statuses: set[int] = field(default_factory=set)

    def add(self, ms: float, status: int) -> None:
        self.millis.append(ms)
        self.statuses.add(status)

    @property
    def n(self) -> int:
        return len(self.millis)

    def pct(self, q: float) -> float:
        """Percentile by nearest-rank on sorted samples.

        Deliberately not `statistics.quantiles`, which interpolates: for latency
        evidence a real observed sample is more honest than a synthesised value
        between two of them.
        """
        if not self.millis:
            return float("nan")
        ordered = sorted(self.millis)
        rank = max(0, min(len(ordered) - 1, round(q * (len(ordered) - 1))))
        return ordered[rank]

    def summary(self) -> dict[str, Any]:
        return {
            "n": self.n,
            "p50_ms": round(self.pct(0.50), 2),
            "p95_ms": round(self.pct(0.95), 2),
            "max_ms": round(max(self.millis), 2) if self.millis else float("nan"),
            "median_ms": round(statistics.median(self.millis), 2) if self.millis else float("nan"),
            "statuses": sorted(self.statuses),
        }


def _time_call(call: Callable[[], int]) -> tuple[float, int]:
    """One timed request. `perf_counter` because it is monotonic."""
    start = time.perf_counter()
    status = call()
    return (time.perf_counter() - start) * 1000.0, status


def measure(
    routes: Sequence[tuple[str, str, bool]],
    fetch: Callable[[str, bool], int],
    *,
    reps: int,
    rounds: int,
    warmup: int,
) -> dict[str, Sample]:
    """Measure every route, interleaving rounds to spread out ambient drift.

    Rounds matter: measuring state A fully, then B, then C would let a slow
    stretch of the host land entirely on one state and masquerade as a finding.
    """
    samples = {label: Sample(label) for label, _, _ in routes}

    for _label, path, needs_auth in routes:
        for _ in range(warmup):
            try:
                fetch(path, needs_auth)
            except Exception:  # warmup failures resurface in the timed loop below
                break

    for _ in range(rounds):
        for label, path, needs_auth in routes:
            for _ in range(reps):
                try:
                    # Bind as defaults rather than closing over the loop
                    # variables: correct today only because _time_call invokes
                    # immediately, and one refactor away from silently timing
                    # the wrong route.
                    ms, status = _time_call(
                        lambda p=path, a=needs_auth: fetch(p, a)
                    )
                except Exception as exc:
                    print(f"  ! {label}: {type(exc).__name__}: {exc}", file=sys.stderr)
                    break
                samples[label].add(ms, status)
    return samples


# --------------------------------------------------------------------------- #
# In-process states
# --------------------------------------------------------------------------- #


def _seed_ledger(db_path: Path, *, instruments: int, candles: int) -> Any:
    """A ledger with enough candles that DarvaX scans do real SQLite work.

    A one-candle fixture would make state C measure nothing: the point is for
    DarvaX to actually read while ATHENA is serving.
    """
    from zoneinfo import ZoneInfo

    from athena.data.store.repository import SqliteRepository
    from athena.domain.enums import Timeframe
    from athena.domain.market import Candle, Instrument

    ist = ZoneInfo("Asia/Kolkata")
    base = datetime(2026, 1, 1, 9, 15, tzinfo=ist)

    repo = SqliteRepository(db_path)
    repo.initialize()

    for idx in range(instruments):
        symbol = f"BENCH{idx:03d}"
        instrument = Instrument(
            instrument_id=f"NSE:{symbol}",
            symbol=symbol,
            exchange="NSE",
            series="EQ",
            name=f"Bench {idx}",
        )
        repo.upsert_instrument(instrument)
        bars = []
        for bar in range(candles):
            # A deterministic sawtooth: enough shape for boxes to form, with no
            # randomness, so repeated runs read identical data.
            drift = Decimal(bar % 40) / Decimal(4)
            low = Decimal(100) + drift
            bars.append(
                Candle(
                    instrument_id=instrument.instrument_id,
                    timeframe=Timeframe.D1,
                    ts_open=base + timedelta(days=bar),
                    open=low + Decimal("0.5"),
                    high=low + Decimal(2),
                    low=low,
                    close=low + Decimal(1),
                    volume=100_000 + bar,
                    source="dx4a-bench",
                )
            )
        repo.add_candles(bars)
    return repo


def _build_app(config_dir: Path, *, enabled: bool, repo: Any, repo_root: Path):
    """An ATHENA app with DarvaX either absent or mounted, over `repo`."""
    from athena.api.app import create_app
    from athena.api.config import APISettings
    from athena.api.darvax_mount import mount_darvax_if_enabled

    os.environ["ATHENA_CONFIG_DIR"] = str(config_dir)
    app = create_app(APISettings())
    app.state.sqlite_repo = repo

    darvax_config = config_dir / "darvax.json"
    darvax_config.write_text(json.dumps({"enabled": enabled}), encoding="utf-8")
    mounted = mount_darvax_if_enabled(
        app, repo=repo, config_dir=config_dir, repo_root=repo_root
    )
    if mounted is not enabled:
        raise RuntimeError(f"expected mounted={enabled}, got {mounted}")
    return app


def _auth_headers(client: Any) -> dict[str, str]:
    """Mint an in-process bearer token via the app's own signer.

    Reuses the suite's helper rather than reimplementing token minting, so this
    cannot drift from how ATHENA actually authenticates. No password anywhere.
    """
    from tests.api.v1.test_core_apis import get_auth_headers

    from athena.api.security.models import Role

    return get_auth_headers(client, Role.ADMIN, username="bench")


class _ScanLoad:
    """Drives DarvaX scans in a background thread: the contention generator.

    Uses the DarvaX scan service directly rather than its HTTP route, so the
    load is DarvaX doing real reads against ATHENA's ledger — not FastAPI
    request overhead measuring itself.
    """

    def __init__(
        self,
        repo: Any,
        config_dir: Path,
        instrument_ids: list[str],
        *,
        interval: float = 0.0,
    ) -> None:
        self._repo = repo
        self._config_dir = config_dir
        self._ids = instrument_ids
        #: Seconds to wait between scans. 0 is a pathological hot loop — a
        #: deliberate worst case, not a realistic one. Real DarvaX use is an
        #: owner pressing Scan occasionally, so a realistic interval must also
        #: be measured before any contention number is called meaningful.
        self._interval = interval
        self._stop = threading.Event()
        self._thread: threading.Thread | None = None
        self.scans = 0
        self.elapsed = 0.0
        self.errors: list[str] = []

    @property
    def rate_per_sec(self) -> float:
        return self.scans / self.elapsed if self.elapsed > 0 else 0.0

    def __enter__(self) -> _ScanLoad:
        self._started = time.perf_counter()
        self._thread = threading.Thread(target=self._run, daemon=True)
        self._thread.start()
        # Let the first scan get underway so ATHENA is measured under real load.
        time.sleep(0.4)
        return self

    def __exit__(self, *exc: object) -> None:
        self._stop.set()
        if self._thread is not None:
            self._thread.join(timeout=30)
        self.elapsed = time.perf_counter() - self._started

    def _run(self) -> None:
        from athena.darvax.api import SqliteMarketDataAdapter
        from athena.darvax.config import load_darvax_config
        from athena.darvax.scan import scan_instruments
        from athena.darvax.store.repository import DarvaxRepository

        try:
            config = load_darvax_config(self._config_dir)
            darvax_db = self._config_dir.parent / "darvax-bench.db"
            store = DarvaxRepository(darvax_db)
            store.initialize()
            market = SqliteMarketDataAdapter(self._repo)
            while not self._stop.is_set():
                scan_instruments(
                    instrument_ids=self._ids,
                    market_data=market,
                    store=store,
                    config=config,
                )
                self.scans += 1
                if self._interval and not self._stop.is_set():
                    self._stop.wait(self._interval)
        except Exception as exc:  # reported below, never silently swallowed
            self.errors.append(f"{type(exc).__name__}: {exc}")


class _SweepLoad(_ScanLoad):
    """DX-6d load: full **universe sweeps** rather than fixed-size scans.

    DX-4a measured a 25-instrument scan repeated in a loop. DX-6b made DarvaX
    able to sweep the entire ledger in one go, and DX-4a named exactly that as a
    re-measure trigger — a 528-instrument sweep is a different load profile, and
    carrying the old conclusion across would be the assumption ADR-010 forbids.

    Drives the real ``SweepRunner``, not a hand-rolled imitation, so what is
    measured is the code the owner actually runs: same batching, same retention
    pruning, same persistence.
    """

    def __init__(self, repo: Any, config_dir: Path, *, interval: float = 0.0) -> None:
        super().__init__(repo, config_dir, [], interval=interval)
        self.durations: list[float] = []
        self.instruments_per_sweep = 0

    @property
    def mean_sweep_seconds(self) -> float:
        return sum(self.durations) / len(self.durations) if self.durations else 0.0

    def _run(self) -> None:
        from athena.darvax.api import SqliteMarketDataAdapter
        from athena.darvax.config import load_darvax_config
        from athena.darvax.screening.sweep import SweepRunner
        from athena.darvax.store.repository import DarvaxRepository

        try:
            config = load_darvax_config(self._config_dir)
            store = DarvaxRepository(self._config_dir.parent / "darvax-bench.db")
            store.initialize()
            runner = SweepRunner(
                market_data=SqliteMarketDataAdapter(self._repo),
                store=store,
                config=config,
                darvax_version="bench",
            )
            while not self._stop.is_set():
                started = time.perf_counter()
                runner.start()
                runner.join(timeout=600)
                self.durations.append(time.perf_counter() - started)
                self.scans += 1

                progress = runner.progress()
                self.instruments_per_sweep = progress.total
                if progress.state == "failed":
                    self.errors.append(f"sweep failed: {progress.error}")
                    break
                if self._interval and not self._stop.is_set():
                    self._stop.wait(self._interval)
        except Exception as exc:  # reported below, never silently swallowed
            self.errors.append(f"{type(exc).__name__}: {exc}")


def run_in_process(args: argparse.Namespace) -> dict[str, Any]:
    import shutil
    import tempfile

    from fastapi.testclient import TestClient

    root = Path(tempfile.mkdtemp(prefix="darvax-bench-"))
    config_dir = root / "config"
    shutil.copytree(REPO_ROOT / "config", config_dir)

    print(
        f"Seeding temp ledger: {args.instruments} instruments x {args.candles} candles"
    )
    repo = _seed_ledger(root / "athena.db", instruments=args.instruments, candles=args.candles)
    instrument_ids = [f"NSE:BENCH{i:03d}" for i in range(args.instruments)]

    results: dict[str, Any] = {"states": {}, "scan_rounds": None, "scan_errors": []}

    def _run_state(name: str, *, enabled: bool, under_load: bool) -> None:
        app = _build_app(config_dir, enabled=enabled, repo=repo, repo_root=root)
        with TestClient(app, raise_server_exceptions=False) as client:
            headers = _auth_headers(client)

            def fetch(path: str, needs_auth: bool) -> int:
                response = client.get(path, headers=headers if needs_auth else None)
                return response.status_code

            load: _ScanLoad | None = None
            if under_load:
                load = (
                    _SweepLoad(repo, config_dir, interval=args.scan_interval)
                    if args.load == "sweep"
                    else _ScanLoad(
                        repo, config_dir, instrument_ids, interval=args.scan_interval
                    )
                )
                load.__enter__()
            try:
                samples = measure(
                    IN_PROCESS_ROUTES,
                    fetch,
                    reps=args.reps,
                    rounds=args.rounds,
                    warmup=args.warmup,
                )
            finally:
                if load is not None:
                    load.__exit__()
                    results["scan_rounds"] = load.scans
                    results["scan_rate_per_sec"] = load.rate_per_sec
                    results["scan_interval"] = args.scan_interval
                    results["load_kind"] = args.load
                    results["scan_errors"].extend(load.errors)
                    if isinstance(load, _SweepLoad):
                        results["mean_sweep_seconds"] = round(load.mean_sweep_seconds, 3)
                        results["instruments_per_sweep"] = load.instruments_per_sweep

        results["states"][name] = {
            label: sample.summary() for label, sample in samples.items()
        }
        print(f"  {name}: done")

    # State order is configurable because it is a confounder, not a detail:
    # whichever state runs first pays the SQLite page-cache warming cost and so
    # looks slower. Re-running with --order C,B,A is how you tell a real delta
    # from a warming artifact — if a "finding" flips sign, it was the ordering.
    plan = {
        "A": ("A_disabled", False, False),
        "B": ("B_enabled_idle", True, False),
        "C": ("C_enabled_scanning", True, True),
    }
    labels = {
        "A": "DarvaX disabled",
        "B": "DarvaX enabled, idle",
        "C": "DarvaX enabled and scanning concurrently",
    }
    order = [part.strip().upper() for part in args.order.split(",") if part.strip()]
    unknown = [key for key in order if key not in plan]
    if unknown:
        raise SystemExit(f"--order: unknown state(s) {unknown}; valid keys are A, B, C")

    results["order"] = order
    for key in order:
        name, enabled, under_load = plan[key]
        print(f"\nState {key} — {labels[key]}")
        _run_state(name, enabled=enabled, under_load=under_load)

    repo.close()
    return results


# --------------------------------------------------------------------------- #
# Live workstation
# --------------------------------------------------------------------------- #


def run_live(args: argparse.Namespace) -> dict[str, Any]:
    import urllib.error
    import urllib.request

    token = os.environ.get("ATHENA_BENCH_TOKEN", "").strip()
    if token:
        print("Using ATHENA_BENCH_TOKEN for authenticated routes.")
    else:
        print(
            "No ATHENA_BENCH_TOKEN set — measuring unauthenticated routes only.\n"
            "Authenticated routes will report their 401s rather than being skipped "
            "silently."
        )

    def fetch(path: str, needs_auth: bool) -> int:
        request = urllib.request.Request(args.base_url.rstrip("/") + path)
        if needs_auth and token:
            request.add_header("Authorization", f"Bearer {token}")
        try:
            with urllib.request.urlopen(request, timeout=args.timeout) as response:
                response.read()
                return int(response.status)
        except urllib.error.HTTPError as exc:
            exc.read()
            return int(exc.code)

    try:
        fetch("/health", False)
    except Exception as exc:
        raise SystemExit(
            f"Cannot reach {args.base_url}: {exc}\nStart the workstation first."
        ) from exc

    darvax_mounted = fetch("/darvax/status", False) == 200
    print(f"DarvaX mounted on this server: {darvax_mounted}")

    samples = measure(
        LIVE_ROUTES, fetch, reps=args.reps, rounds=args.rounds, warmup=args.warmup
    )
    return {
        "base_url": args.base_url,
        "darvax_mounted": darvax_mounted,
        "authenticated": bool(token),
        "routes": {label: sample.summary() for label, sample in samples.items()},
    }


# --------------------------------------------------------------------------- #
# Reporting
# --------------------------------------------------------------------------- #


def _fmt(value: float) -> str:
    """Fixed 9-wide so large values (a 500ms endpoint) cannot collide."""
    return f"{'—':>9}" if value != value else f"{value:9.2f}"


def _ratio(new: float, base: float) -> str:
    if base != base or new != new or base <= 0:
        return f"{'—':>7}"
    return f"{new / base:6.2f}x"


def print_in_process_report(results: dict[str, Any]) -> None:
    states = results["states"]
    a, b, c = states["A_disabled"], states["B_enabled_idle"], states["C_enabled_scanning"]
    width = 20 + 9 * 7 + 8

    print("\n" + "=" * width)
    print("DX-4a in-process results — ATHENA latency by DarvaX state (ms)")
    print("=" * width)
    print(
        f"{'route':<20}{'A p50':>9}{'B p50':>9}{'C p50':>9}"
        f"{'B-A':>9}{'C-A':>9}{'A p95':>9}{'C p95':>9}{'C/A p50':>8}"
    )
    print("-" * width)
    for label, _, _ in IN_PROCESS_ROUTES:
        ap, bp, cp = a[label]["p50_ms"], b[label]["p50_ms"], c[label]["p50_ms"]
        a95, c95 = a[label]["p95_ms"], c[label]["p95_ms"]
        print(
            f"{label:<20}{_fmt(ap)}{_fmt(bp)}{_fmt(cp)}"
            f"{_fmt(bp - ap)}{_fmt(cp - ap)}{_fmt(a95)}{_fmt(c95)}{_ratio(cp, ap)}"
        )
    print("-" * width)
    rate = results.get("scan_rate_per_sec")
    kind = results.get("load_kind", "scan")
    label = "sweeps" if kind == "sweep" else "scans"
    print(
        f"DarvaX {label} during state C: {results['scan_rounds']}"
        + (f"  (~{rate:.2f}/sec, interval={results['scan_interval']}s)" if rate else "")
    )
    if results.get("mean_sweep_seconds"):
        print(
            f"Mean sweep: {results['mean_sweep_seconds']}s over "
            f"{results.get('instruments_per_sweep', 0)} instruments"
        )
    if results["scan_errors"]:
        print("Scan errors (state C measured NO real load — treat C as invalid):")
        for error in results["scan_errors"]:
            print(f"  ! {error}")
    statuses = {
        label: a[label]["statuses"] for label, _, _ in IN_PROCESS_ROUTES
    }
    print(f"HTTP statuses seen (state A): {statuses}")
    print(
        "\nB-A is the cost of mounting DarvaX. C-A is the host contention ADR-010\n"
        "asks about. Both are wall-clock on a shared machine: read percentiles,\n"
        "not single samples, and re-run before concluding anything from a delta\n"
        "smaller than the run-to-run spread."
    )


def print_live_report(results: dict[str, Any]) -> None:
    print("\n" + "=" * 72)
    print(f"DX-4a live results — {results['base_url']}")
    print(f"DarvaX mounted: {results['darvax_mounted']} | "
          f"authenticated: {results['authenticated']}")
    print("=" * 72)
    print(f"{'route':<20}{'n':>5}{'p50':>9}{'p95':>9}{'max':>9}  statuses")
    print("-" * 72)
    for label, _, _ in LIVE_ROUTES:
        row = results["routes"][label]
        print(
            f"{label:<20}{row['n']:>5}{_fmt(row['p50_ms'])}"
            f"{_fmt(row['p95_ms'])}{_fmt(row['max_ms'])}  {row['statuses']}"
        )
    print("-" * 72)
    print(
        "Run this once with DarvaX disabled and once enabled, then compare.\n"
        "The flag is read at startup, so restart between runs."
    )


def main(argv: Iterable[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("--live", action="store_true", help="probe a running server")
    parser.add_argument("--base-url", default="http://127.0.0.1:8000")
    parser.add_argument("--reps", type=int, default=25, help="requests per route per round")
    parser.add_argument("--rounds", type=int, default=3, help="interleaved sweeps")
    parser.add_argument("--warmup", type=int, default=3)
    parser.add_argument(
        "--scan-interval",
        type=float,
        default=0.0,
        help=(
            "seconds between DarvaX scans in state C. 0 (default) is a "
            "pathological hot loop = worst case; use e.g. 5 to model realistic "
            "owner-driven use"
        ),
    )
    parser.add_argument(
        "--order",
        default="A,B,C",
        help=(
            "state order, e.g. 'C,B,A'. Whichever state runs first absorbs "
            "SQLite page-cache warming, so reversing the order is how you check "
            "whether a delta is real or an ordering artifact"
        ),
    )
    parser.add_argument(
        "--load",
        choices=("scan", "sweep"),
        default="scan",
        help=(
            "what state C runs: 'scan' repeats a fixed-size scan (DX-4a), "
            "'sweep' repeats a full universe sweep through SweepRunner (DX-6d)"
        ),
    )
    parser.add_argument("--instruments", type=int, default=25)
    parser.add_argument("--candles", type=int, default=400)
    parser.add_argument("--timeout", type=float, default=30.0)
    parser.add_argument("--json", dest="json_out", default=None)
    args = parser.parse_args(list(argv) if argv is not None else None)

    started = time.strftime("%Y-%m-%d %H:%M:%S")
    print(f"DX-4a DarvaX performance harness — {started}")
    print(f"reps={args.reps} rounds={args.rounds} warmup={args.warmup}")

    if args.live:
        results = run_live(args)
        print_live_report(results)
    else:
        results = run_in_process(args)
        print_in_process_report(results)

    results["started_at"] = started
    results["mode"] = "live" if args.live else "in_process"
    if args.json_out:
        Path(args.json_out).write_text(json.dumps(results, indent=2), encoding="utf-8")
        print(f"\nWrote {args.json_out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
