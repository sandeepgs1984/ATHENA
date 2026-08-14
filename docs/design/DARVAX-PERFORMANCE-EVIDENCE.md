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

The harness is not a pytest test on purpose: wall-clock latency is
nondeterministic, so threshold assertions would produce a flaky suite that gets
muted — the opposite of evidence. Add `--json <path>` to capture raw samples.
