# DX-4a — DarvaX performance evidence

What an enabled DarvaX actually costs ATHENA, measured rather than asserted.

**Milestone:** DX-4a ([`docs/MILESTONES.md`](../MILESTONES.md)) ·
**Governing decision:** [ADR-010](../adr/ADR-010-darvax-satellite-module.md) ·
**Harness:** [`tests/darvax/bench/darvax_perf_bench.py`](../../tests/darvax/bench/darvax_perf_bench.py) ·
**Measured:** 2026-08-14 · **Host:** owner workstation (macOS, Python 3.14, SQLite WAL)

---

## 1. What was being tested

ADR-010 §Consequences makes a deliberately narrow claim: DarvaX introduces **no
synchronous dependency** into ATHENA's request, decision, scoring, scheduler,
write, or dashboard-render paths — and explicitly does **not** claim that an
enabled DarvaX has zero performance effect, because both processes share one
workstation and DarvaX reads ATHENA's SQLite ledger. It requires that contention
be *"measured, not assumed away"*, and states that any mitigation is a separate
decision, not a foregone conclusion.

This document is that measurement. It answers two distinct questions that are
easy to conflate:

1. **What does *mounting* DarvaX cost?** (is the satellite free when idle?)
2. **What does DarvaX *doing work* cost ATHENA?** (the actual contention question)

---

## 2. Method

Three states measured over one identical seeded ledger (25 instruments × 400
daily candles), same process, same data:

| State | Meaning |
|---|---|
| **A** | DarvaX disabled — not mounted, never imported |
| **B** | DarvaX enabled, idle |
| **C** | DarvaX enabled **and scanning continuously** in a background thread |

`B − A` answers question 1. `C − A` answers question 2. State C drives DarvaX's
scan service directly rather than through its HTTP route, so the load is DarvaX
doing real reads against ATHENA's ledger rather than FastAPI overhead measuring
itself.

Per route: 30 requests × 4 interleaved rounds (n = 120) after 3 warmup calls.
Percentiles are nearest-rank on observed samples, never interpolated.
Authenticated routes use the suite's in-process token helper — **no owner
credential is involved anywhere in this harness.**

### A confound found and controlled

The first run showed `decisions_list` **1.8 ms faster** with DarvaX enabled —
reproducibly, across two runs. A consistent negative is not noise, so it was
investigated rather than averaged away.

Cause: whichever state runs first absorbs SQLite page-cache warming and so looks
slower. Re-running with `--order C,B,A` dropped `decisions_list`'s state-A
baseline from 4.44 ms to 2.70 ms and the anomaly vanished (`B − A` = +0.05 ms).
It was an ordering artifact, not a DarvaX effect.

Consequence worth noting: A-first ordering **understates** contention, because
the baseline is inflated. All headline numbers below therefore use `--order
C,B,A`, where the baseline is warm. This is why the harness takes an `--order`
flag at all — reversing it is how a claimed finding gets falsified.

### What is deliberately not measured

`POST /api/v1/market/validate` is **excluded**, despite being the latency the
owner cares about most. It writes `Decision` rows, and polluting an immutable
append-only decision history to obtain a timing number is not a trade worth
making. The mechanism by which DarvaX could plausibly slow a validate is
shared-SQLite contention, which state C measures directly on read paths.

---

## 3. Question 1 — what does mounting DarvaX cost?

**Nothing measurable.** `B − A`, milliseconds, p50 (`--order C,B,A`):

| Route | A p50 | B p50 | B − A |
|---|---|---|---|
| `/health` | 0.69 | 0.69 | 0.00 |
| `/dashboard/` | 1.14 | 1.11 | −0.03 |
| `/dashboard/dashboard.js` | 1.54 | 1.52 | −0.02 |
| `/api/v1/dashboard/summary` | 458.95 | 457.39 | −1.56 |
| `/api/v1/decisions` | 2.72 | 2.75 | +0.03 |
| `/api/v1/decisions/latest` | 1.25 | 1.25 | 0.00 |
| `/api/v1/portfolio` | 2.57 | 2.56 | −0.01 |
| `/api/v1/market/summary` | 1.20 | 1.17 | −0.03 |

Every delta is within run-to-run noise, and several are negative — the signature
of no effect. An idle mounted satellite costs ATHENA nothing detectable.

---

## 4. Question 2 — what does DarvaX doing work cost?

This depends entirely on **how hard DarvaX is working**, so two load profiles
were measured. Reporting only one would be misleading.

### 4a. Realistic cadence — a scan every 5 s (0.2 scans/sec)

**No measurable contention.** `C − A`, p50:

| Route | A p50 | C p50 | C − A | C/A |
|---|---|---|---|---|
| `/health` | 0.68 | 0.68 | 0.00 | 1.00× |
| `/dashboard/` | 1.12 | 1.11 | −0.01 | 0.99× |
| `/dashboard/dashboard.js` | 1.51 | 1.51 | 0.00 | 1.00× |
| `/api/v1/dashboard/summary` | 450.35 | 443.46 | −6.89 | 0.98× |
| `/api/v1/decisions` | 2.70 | 2.65 | −0.05 | 0.98× |
| `/api/v1/decisions/latest` | 1.25 | 1.23 | −0.02 | 0.98× |
| `/api/v1/portfolio` | 2.58 | 2.47 | −0.11 | 0.96× |
| `/api/v1/market/summary` | 1.18 | 1.14 | −0.04 | 0.97× |

Every ratio is ≤ 1.01×. This is the profile that matches real use — the owner
opening the DarvaX tab and pressing Scan — and at that cadence DarvaX is
invisible to ATHENA.

### 4b. Pathological hot loop — 14.2 scans/sec, no think time

**Contention is real and measurable.** This is a deliberate worst case that no
real usage produces; it exists to find the ceiling, not to describe normal
operation.

| Route | A p50 | C p50 | C − A | C/A | A p95 | C p95 |
|---|---|---|---|---|---|---|
| `/health` | 0.69 | 2.23 | +1.54 | **3.23×** | 1.07 | 2.61 |
| `/dashboard/` | 1.14 | 3.55 | +2.41 | **3.11×** | 1.46 | 4.86 |
| `/dashboard/dashboard.js` | 1.54 | 6.21 | +4.67 | **4.03×** | 2.17 | 7.16 |
| `/api/v1/dashboard/summary` | 458.95 | 660.61 | **+201.66** | 1.44× | 485.18 | 727.98 |
| `/api/v1/decisions` | 2.72 | 6.94 | +4.22 | **2.55×** | 3.73 | 8.58 |
| `/api/v1/decisions/latest` | 1.25 | 3.98 | +2.73 | **3.18×** | 1.85 | 6.57 |
| `/api/v1/portfolio` | 2.57 | 13.54 | +10.97 | **5.27×** | 3.49 | 18.46 |
| `/api/v1/market/summary` | 1.20 | 3.33 | +2.13 | **2.78×** | 2.00 | 4.32 |

Reproducible: an independent A-first run of the same profile gave 3.28×, 3.17×,
4.16×, 5.38× on the same routes — the multipliers are stable, not a one-off.

Read this carefully. The **multipliers** look alarming; the **absolute** costs do
not. Every route except `dashboard/summary` stays under 14 ms even while DarvaX
hammers the ledger 14 times a second. Tripling 0.7 ms is not a user-visible
event. The one meaningful absolute number is `dashboard/summary` at +202 ms, and
that endpoint has a much larger DarvaX-independent problem (§6).

---

## 5. Real workstation, DarvaX enabled

Measured against the running server (`--live`, n = 60/route). Authenticated
routes report 401 rather than being silently skipped, because no token was
supplied — the harness never uses the owner's password.

| Route | p50 | p95 | max | status |
|---|---|---|---|---|
| `/health` | 1.12 | 1.73 | 2.40 | 200 |
| `/dashboard/` | 1.35 | 2.18 | 2.93 | 200 |
| `/dashboard/dashboard.js` | 2.21 | 3.07 | 3.49 | 200 |
| `/api/v1/dashboard/summary` | 454.91 | 475.36 | 506.05 | 200 |
| `/api/v1/decisions` | 1.98 | 3.15 | 3.51 | 401 |
| `/api/v1/decisions/latest` | 1.45 | 2.17 | 2.75 | 401 |
| `/api/v1/portfolio` | 1.36 | 2.16 | 2.94 | 401 |
| `/api/v1/market/summary` | 1.21 | 1.97 | 2.78 | 401 |

Live `dashboard/summary` (454.91 ms) matches in-process (450–459 ms) within 1%,
which cross-validates the harness against the real workstation.

To complete the on-workstation before/after, run the same command with DarvaX
disabled and restart in between (the flag is read at startup):

```bash
python3 tests/darvax/bench/darvax_perf_bench.py --live --reps 20 --rounds 3
```

Include authenticated routes by exporting a token you mint yourself:

```bash
export ATHENA_BENCH_TOKEN=<your dashboard access token>
```

---

## 6. Finding unrelated to DarvaX: `dashboard/summary` costs ~455 ms

`GET /api/v1/dashboard/summary` takes **~455 ms p50** — 200–400× every other
measured endpoint — both in-process and on the live workstation, and in **all
three** DarvaX states (`B − A` = −1.56 ms). **DarvaX does not cause it and
disabling DarvaX will not fix it.**

It is recorded here because DX-4a is where it was found, not because it is a
DarvaX issue. Investigating or optimising it is out of DX-4a's scope (a
measurement milestone) and is not proposed as part of it.

---

## 7. Conclusions

1. **ADR-010's architectural guarantee holds.** Mounting DarvaX adds no
   measurable latency to any ATHENA path (§3).
2. **ADR-010 was right not to claim zero physical effect.** Contention is real
   and reproducible under sustained load (§4b) — exactly the outcome the ADR
   refused to assume away.
3. **At realistic usage there is no measurable contention at all** (§4a). The
   3–5× multipliers require ~14 scans/sec with zero think time, which no
   owner-driven interaction produces.
4. **Absolute impact stays small** even at worst case: ≤ 14 ms on every route
   except `dashboard/summary`, which is dominated by its own DarvaX-independent
   cost.

### Recommended mitigation: none

ADR-010 states mitigation is a separate decision and explicitly does not license
worker processes, resource schedulers, or queues on the strength of measurement
alone. On this evidence none is warranted:

- Realistic-cadence contention is unmeasurable.
- Worst-case contention is bounded and already capped by DarvaX's own
  `scan.max_instruments` (default 50) and `lookback_bars` (default 400) — see
  [`DARVAX-CONFIGURATION.md`](DARVAX-CONFIGURATION.md).
- Adding process isolation to solve a sub-15 ms effect would add real complexity
  against no demonstrated problem.

Re-measure if any of these change: DarvaX gains a **scheduled** scan (moving it
from owner-driven to continuous), `max_instruments` is raised substantially, or
DarvaX starts writing to ATHENA's ledger (which ADR-010 forbids today).

---

## 7a. DX-6d — re-measured at universe scale

**Measured:** 2026-08-15 · **Milestone:** DX-6d · **Status:** 🔄 Ready for review

§7 concluded "no mitigation warranted" from a **25-instrument** scan repeated in
a loop, and listed universe-scale scanning as an explicit re-measure trigger.
DX-6b then made DarvaX able to sweep the **whole 528-instrument ledger** in one
operation. Carrying the old conclusion across without re-measuring would have
been exactly the assumption ADR-010 forbids, so this section re-runs it.

The harness gained `--load sweep`, which drives the real `SweepRunner` — same
batching, same retention pruning, same persistence — rather than a hand-rolled
imitation, so what is measured is the code that actually runs.

### Continuous sweeping — the worst case

0.68 sweeps/sec sustained (59 back-to-back sweeps, mean **1.48 s** each over 528
instruments), `--order C,B,A`:

| Route | A p50 | C p50 | C − A | C/A |
|---|---|---|---|---|
| `/health` | 0.66 | 1.52 | +0.86 | **2.30×** |
| `/dashboard/` | 1.09 | 3.37 | +2.28 | **3.09×** |
| `/dashboard/dashboard.js` | 1.46 | 5.90 | +4.44 | **4.04×** |
| `/api/v1/dashboard/summary` | 437.05 | 653.51 | **+216.46** | 1.50× |
| `/api/v1/decisions` | 3.97 | 11.54 | +7.57 | **2.91×** |
| `/api/v1/decisions/latest` | 1.19 | 3.57 | +2.38 | **3.00×** |
| `/api/v1/portfolio` | 2.48 | 12.60 | +10.12 | **5.08×** |
| `/api/v1/market/summary` | 1.13 | 3.14 | +2.01 | **2.78×** |

Mounting still costs nothing: every `B − A` is within ±0.10 ms.

**The headline result is that these numbers are the same as §4b's.** A
continuously-sweeping DarvaX (2.30×–5.08×, +216 ms on `dashboard/summary`) costs
almost exactly what a continuously-scanning DarvaX cost (3.23×–5.27×, +202 ms).
That makes sense: both saturate one thread doing SQLite reads, and the ceiling
is set by that, not by how many instruments each unit of work covers.

**Universe scale did not make contention worse.** It changed how much useful
work one unit of load performs, not how much contention that load creates.

### Realistic cadence — a sweep every 30 seconds

| Route | A p50 | C p50 | C − A | C/A |
|---|---|---|---|---|
| `/health` | 0.66 | 0.66 | 0.00 | 1.00× |
| `/dashboard/` | 1.08 | 1.06 | −0.02 | 0.98× |
| `/dashboard/dashboard.js` | 1.48 | 1.43 | −0.05 | 0.97× |
| `/api/v1/dashboard/summary` | 436.29 | 436.55 | +0.26 | 1.00× |
| `/api/v1/decisions` | 3.90 | 3.83 | −0.07 | 0.98× |
| `/api/v1/decisions/latest` | 1.16 | 1.17 | +0.01 | 1.01× |
| `/api/v1/portfolio` | 2.41 | 2.38 | −0.03 | 0.99× |
| `/api/v1/market/summary` | 1.11 | 1.10 | −0.01 | 0.99× |

Every ratio ≤ 1.01×. And a sweep every 30 seconds is already far heavier than
real use, which is a person pressing **Screen universe** occasionally.

### How long a sweep actually takes

Against a copy of the owner's real ledger, warm cache and no competing load:
**0.23 s** per 528-instrument sweep (35 consecutive sweeps in 8.0 s). Under the
benchmark's concurrent request load it rises to ~1.4–1.5 s.

Practical consequence worth stating: **the progress bar and cancel button added
in DX-6c are almost impossible to hit.** They remain correct and tested, and are
worth keeping for slower hosts and larger universes, but on this machine a sweep
is effectively instantaneous.

### Storage at the chosen retention

Measured, not extrapolated — 35 consecutive sweeps at the default
`retain_sweeps: 30`:

| | |
|---|---|
| Sweeps retained | 30 (pruning verified: 35 run, 30 kept) |
| Screen result rows | 15,840 (30 × 528) |
| `darvax.db` incl. WAL | **12.6 MB** |

`darvax_signals` stays flat at 528 rows across repeated sweeps, because a signal
is idempotent by `(instrument, as_of)` — re-sweeping the same trading day updates
in place rather than accumulating. Only the screen results scale with retention.

That is a bounded, trivial footprint, and it is bounded *by construction* rather
than by luck — which is the whole reason retention was settled before DX-6b
rather than after.

### Conclusion — the §7 recommendation stands

1. Universe scale did **not** worsen contention; the worst case is unchanged
   from DX-4a because it is thread-bound, not instrument-bound.
2. At any realistic cadence there is **no measurable contention at all**.
3. A sweep is short enough (0.23 s warm) that even its worst case is a
   sub-second window.
4. Storage is bounded at ~12.6 MB by the retention policy.

**No mitigation is warranted, and none is proposed.** The re-measure triggers
from §7 carry forward unchanged, with one addition: re-measure if a sweep ever
becomes **scheduled** rather than owner-triggered, since that would convert the
realistic profile into the continuous one measured above.

---

## 7b. Re-measured after the DarvaX opt-in — 2,191 instruments

**Measured:** 2026-08-16 · **Trigger:** SU-6 opt-in to `darvax_discovery`
(530 → 2,191 instruments, **4.1×**) plus the DX-5 backfill (82 → 744 trading
days). Both landed together, which matters for reading the sweep duration below.

### Contention is unchanged — the §7a conclusion holds at 4× the universe

Continuous sweeping, the worst case, `--order C,B,A`:

| Route | 528 C/A (§7a) | **2,191 C/A** | 2,191 C − A |
|---|---|---|---|
| `/health` | 2.30× | **2.09×** | +0.73 ms |
| `/dashboard/` | 3.09× | **3.28×** | +2.46 ms |
| `/dashboard/dashboard.js` | 4.04× | **4.01×** | +4.43 ms |
| `/api/v1/dashboard/summary` | 1.50× | **1.48×** | **+211.08 ms** |
| `/api/v1/decisions` | 2.91× | **2.99×** | +16.88 ms |
| `/api/v1/decisions/latest` | 3.00× | **2.92×** | +2.34 ms |
| `/api/v1/portfolio` | 5.08× | **5.00×** | +9.83 ms |
| `/api/v1/market/summary` | 2.78× | **2.96×** | +2.22 ms |

Every ratio is within run-to-run spread of the 528-instrument figures, and
`dashboard/summary` moved from +216 ms to +211 ms. **Quadrupling the universe
changed contention not at all**, which is the second independent confirmation
that the ceiling is thread-bound rather than instrument-bound. Mounting remains
free: every `B − A` is within ±0.03 ms except one 1.68 ms reading on the 438 ms
route.

### Realistic cadence — a sweep every 30 seconds

| Route | 528 C/A (§7a) | **2,191 C/A** |
|---|---|---|
| `/health` | 1.00× | 1.08× |
| `/dashboard/` | 0.98× | 1.07× |
| `/dashboard/dashboard.js` | 0.97× | 1.06× |
| `/api/v1/dashboard/summary` | 1.00× | 0.99× |
| `/api/v1/decisions` | 0.98× | 1.04× |
| `/api/v1/decisions/latest` | 1.01× | 1.06× |
| `/api/v1/portfolio` | 0.99× | 1.05× |
| `/api/v1/market/summary` | 0.99× | 1.04× |

Ratios rose from "≤1.01×" to "≤1.08×" — **a real change, and still negligible**:
the absolute deltas are 0.04–0.35 ms on sub-10 ms routes. The cause is simply
duty cycle. A 5.9 s sweep occupies ~20% of each 30 s interval where a 1.5 s
sweep occupied ~5%, so a larger share of the sampling window overlaps an active
sweep. Reported rather than rounded away, because "≤1.01×" would no longer be
true and the reason it changed is worth knowing.

### Sweep duration — and why 15× is not 4×

Against the owner's real ledger, warm, no competing load: **3.51 s** per sweep
(8 consecutive sweeps, min 3.48 / max 3.53), 2,191 evaluated, **0 skipped**.
Under the benchmark's concurrent request load, 5.9–6.5 s.

0.23 s → 3.51 s is **15.3×** for a universe that grew only 4.1×. The universe is
not the whole story, and reading it as such would mis-attribute the cost:

| | 528 | 2,191 |
|---|---|---|
| Mean bars read per instrument | 82 — *all the ledger held* | **360** (400-bar cap; 1,844 instruments at it) |
| **Bars read per sweep** | ~43k | **~793k — 18.3×** |
| Sweep duration | 0.23 s | **3.51 s — 15.3×** |

**Sweep cost tracks bars read, near-linearly and slightly sublinear.** Two
changes compounded: 4.1× more instruments *and* 4.4× more history for each. The
DX-5 backfill is as responsible for the slowdown as the opt-in is, and a future
universe change should be costed in bars, not symbols.

### This reverses §7a's note on the progress bar

§7a observed that DX-6c's progress bar and cancel button were "almost impossible
to hit" at 0.23 s, and kept them only for slower hosts and larger universes.
**That larger universe now exists.** At 3.5 s warm and ~6 s under load, both
controls are comfortably usable and are doing the job they were built for. The
prediction was right and the feature no longer needs defending as speculative.

### Storage

Measured after 8 sweeps at 2,191 instruments: 17,528 result rows, **12.6 MB**
including WAL — the same footprint 35 sweeps of 528 instruments produced. At the
default `retain_sweeps: 30` the steady state is ~65,700 rows, extrapolating to
roughly 45–50 MB. Still bounded by construction, still trivial, but ~4× §7a's
figure and no longer measured at the retention limit — worth re-measuring if
`retain_sweeps` is ever raised.

### Conclusion

The §7 recommendation stands unchanged: **no mitigation is warranted.** One
re-measure trigger is added to those in §7a: **re-measure when ledger depth
changes materially**, not only when the universe widens — this section is the
evidence that depth, not symbol count, is what the sweep actually pays for.

---

## 8. Reproducing this

```bash
# Worst case, warm baseline (the headline numbers in §4b)
python3 tests/darvax/bench/darvax_perf_bench.py \
    --reps 30 --rounds 4 --instruments 25 --candles 400 \
    --scan-interval 0 --order C,B,A

# Realistic cadence (§4a)
python3 tests/darvax/bench/darvax_perf_bench.py \
    --reps 30 --rounds 4 --instruments 25 --candles 400 \
    --scan-interval 5 --order C,B,A
```

Universe-scale sweeps (§7a) — `--load sweep` drives the real `SweepRunner`:

```bash
# Continuous sweeping, the worst case
python3 tests/darvax/bench/darvax_perf_bench.py --load sweep \
    --reps 30 --rounds 4 --instruments 528 --candles 400 \
    --scan-interval 0 --order C,B,A

# Realistic cadence — one sweep every 30s
python3 tests/darvax/bench/darvax_perf_bench.py --load sweep \
    --reps 30 --rounds 4 --instruments 528 --candles 400 \
    --scan-interval 30 --order C,B,A
```

For §7b substitute `--instruments 2191`.

> **`--instruments` defaults to 25.** The in-process harness seeds a *synthetic*
> ledger at that size and the results table looks entirely normal at any scale —
> only the `Seeding temp ledger: N instruments` line and the `Mean sweep: …s over
> N instruments` footer reveal which one was measured. A §7a/§7b run that omits
> the flag silently measures 25 instruments. Check the footer before believing a
> universe-scale number; the first attempt at §7b did not, and had to be redone.

Sweep duration and tier counts against the **real** ledger (§7b) are not from
the harness — it seeds synthetic data. Drive `SweepRunner` directly over
`SqliteMarketDataAdapter(SqliteRepository("db/athena.db")).with_universe(...)`,
timing `start()` until `progress()` leaves the running state, and point
`DarvaxRepository` at a scratch path so `db/darvax.db` is untouched.

The harness is not a pytest test on purpose: wall-clock latency is
nondeterministic, so threshold assertions would produce a flaky suite that gets
muted — the opposite of evidence. Add `--json <path>` to capture raw samples.
