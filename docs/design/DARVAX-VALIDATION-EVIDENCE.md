# DX-5 — DarvaX validation evidence

Does the DarvaX methodology earn the removal of its `EXPERIMENTAL_UNVALIDATED`
label?

**Answer: not yet — but the reason has changed, and so has the evidence.**

The original blocker (82 trading days) is gone: the ledger now holds **744
trading days** and the mechanical sufficiency gate returns `VALIDATED` for both
stop policies. The measured expectancy also **reversed sign** — from −3.62% to
**+4.09%** per trade under the canonical 10% stop.

That is a real and important result, and it is still not sufficient to drop the
label. The gate tests *sample size and period only*. It does not test the three
limitations in §5, and those limitations are exactly what a positive result
needs to survive. §4 tests them directly: **the canonical policy survives; the
tight policy does not**, despite the gate labelling them identically.

**Milestone:** DX-5 · **Governing decision:**
[ADR-010](../adr/ADR-010-darvax-satellite-module.md) ·
**Harness:** [`src/athena/darvax/validation/`](../../src/athena/darvax/validation/) ·
**First measured:** 2026-08-15 (82 days) · **Re-measured:** 2026-08-16 (744 days) ·
**Verdict:** `EXPERIMENTAL_UNVALIDATED` (label removal is an owner decision — §6)

---

## 1. Why this milestone exists

ADR-010 records that the source deck ships **no validation evidence of any
kind** — only cherry-picked winners (Tarmat +36%, BSL +65%, Adani Power +80%)
and follower P&L screenshots, with no sample size, no loss rate, no expectancy
and no drawdown. Its own author disclaims it on p.77. Everything DarvaX shows is
therefore labelled `EXPERIMENTAL_UNVALIDATED`, and DX-5 is the milestone that
either removes that label on evidence or explains why it stays.

## 2. Approach — DarvaX-owned, and why

ADR-010 §1 pins the DarvaX→ATHENA import surface, and a DX-4 test asserts DarvaX
never imports an ATHENA analytical engine — which `athena.backtest` is. Routing
validation through ATHENA's backtester would have widened that surface and
coupled the satellite's validation to ATHENA's engine. DarvaX owns its EMA, its
config, its schema, its sweep and its UI for the same reason; it owns its
validation too. **The generic-contract option was rejected on the frozen
invariant, not on preference.**

### No new methodology, and no lookahead

Entries and exits come from replaying the **DX-3 engine** bar by bar —
`evaluate_signal` on progressively longer prefixes — so what is measured is
exactly what the screener shows. A separate "backtest interpretation" of the
rules would validate something the owner never sees.

Lookahead is prevented structurally rather than by convention: the engine only
ever receives `candles[: t + 1]`, so a signal at bar *t* cannot consult bar
*t+1*. A test instruments the engine and asserts the largest bar it was ever
shown. This matters more than any statistic below — lookahead is the easiest way
to produce a backtest that looks excellent and is a lie.

### Trade model

| | |
|---|---|
| Entry | Engine reports `BREAKOUT` (rule B); filled at the **next bar's open** — the first tradable price after the signal |
| Exit — stop | Configured policy, measured off the actual fill; filled **at the stop**, since a stop is a resting order rather than an observation |
| Exit — rule C | Engine reports `BELOW_BOX_BOTTOM`, the methodology's own exit; filled at the next bar's open |
| Unresolved | Reported `OPEN` and **excluded** from closed-trade statistics — counting an open position as a non-loss is how backtests flatter themselves |

---

## 3. The original blocker, and how it was removed

The first run of DX-5 could not validate anything, for one reason:

| | At first measurement (2026-08-15) | After backfill (2026-08-16) |
|---|---|---|
| Daily candles | 43,223 | **362,949** |
| Instruments | 528 | 530 |
| Date range | 2026-04-20 → 2026-08-14 | **2023-08-16 → 2026-08-14** |
| **Trading days** | **82** ❌ | **744** ✅ |
| Instruments with ≥500 bars | 0 | 471 |

Against a **500 trading day** floor (roughly two years). A breakout methodology
measured across 82 days of a single market regime tells you about that regime,
not about the methodology.

### The two-stage plan was wrong, and measurement is why

The 2026-08-15 revision of this document proposed reaching the floor in two
stages — ingest 365 days now, then *wait about a year* for the rest to accrete.
It also declined to raise the `le=365` bound in `IngestionConfig`, on the
reasoning that the bound "presumably reflects a vendor or rate-limit
consideration".

**That assumption was never checked, and it was false.** Probing Kite directly
at 365 / 730 / 1095 / 1825 / 2000 / 2500 / 3650 days showed the vendor returns
the **entire requested span in a single daily request** — 2,474 bars in 1.1
seconds at 3,650 days, with no windowing, no pagination and no extra rate-limit
cost. The bound was a config-model limit with nothing behind it. It was raised
to `le=3650` with the measurement recorded inline at
[`config/models.py`](../../src/athena/config/models.py).

The whole backfill then took **3.5 minutes** for 513 symbols — not a year.

Two further corrections came out of the same exercise, both worth keeping:

- `skip_existing: true` skips *writes*, not *fetches*. It does not make a deeper
  re-ingest cheap, and history does not accrete for free.
- `config/ingestion.json` was deliberately left shallow. The backfill was run as
  a **one-off** through SU-5's `execute_backfill` rather than by deepening the
  daily cycle, so routine ingestion still fetches only what it needs.

2 of 515 symbols failed (`E2E`, `INFSDFSD`) and were logged and skipped without
stopping the batch.

---

## 4. What three years of data show

Full universe, 530 instruments, 744 trading days (2023-08-16 → 2026-08-14). Both
documented stop policies were run, because ADR-010 records the deck's
contradiction between them and deliberately left it for evidence to settle.

| | **canonical_darvas** (10%, deck p.67) | **darvax_tight** (1%, deck p.44) |
|---|---|---|
| Closed trades | 1,975 *(was 301)* | 3,808 *(was 677)* |
| Still open | 72 (3.5%) *(was 35%)* | 26 (0.7%) |
| **Win rate** | **37.9%** *(was 21.3%)* | **8.8%** *(was 4.3%)* |
| **Expectancy / trade** | **+4.09%** *(was −3.62%)* | **+1.27%** *(was −0.48%)* |
| Average win | +22.97% | +24.91% |
| Average loss | −7.45% | −1.00% |
| Profit factor | 1.88 *(was 0.35)* | 2.40 *(was 0.49)* |
| Average bars held | 36.5 | 7.9 |
| Exits by stop | 689 (35%) | **3,472 (91%)** |
| Exits by rule C | 1,286 | 336 |
| Sufficiency gate | **SUFFICIENT** ✅ | **SUFFICIENT** ✅ |

**Both signs reversed.** The 82-day sample was measuring one adverse regime, and
this document said so at the time — *"these figures are likely pessimistic"*,
with the reason given (winners were still open, losers had already stopped out).
The open-trade share falling from 35% to 3.5% is that bias being removed, and it
moved the result in the predicted direction. The earlier negative reading should
be treated as retracted, not as a second data point.

That is where the mechanical verdict stops being useful, and the two policies
have to be separated.

### The canonical 10% stop survives adversarial testing

The gate says `SUFFICIENT`; these two tests ask whether the edge is *real*:

| Stress applied | Expectancy / trade |
|---|---|
| Raw | +4.09% |
| Less 0.2% round-trip cost | +3.89% |
| Less 0.6% round-trip cost | +3.49% |
| Less 1.0% round-trip cost | +3.09% |
| **Discarding the best 1% of trades entirely** | **+2.40%** |

It remains solidly positive under a 1% round-trip cost assumption — generous for
Indian equities including STT and slippage — and, more importantly, it survives
deleting its 19 best trades. The edge is distributed across the sample rather
than carried by a handful of outliers. A 37.9% win rate against a 3.1:1
win/loss ratio is a coherent, ordinary trend-following profile.

### The tight 1% stop does not, and the gate cannot see it

The tight policy's gate result is identical, and its profit factor is *higher*
(2.40 vs 1.88). Both are misleading:

| Stress applied | Expectancy / trade |
|---|---|
| Raw | +1.27% |
| Less 0.6% round-trip cost | +0.67% |
| **Discarding the best 1% of trades entirely** | **+0.38%** |

**The top 1% of trades — 38 of 3,808 — account for 70.8% of all P&L.** Remove
them and almost the entire result disappears; add realistic costs to *that* and
it is indistinguishable from zero. Meanwhile 91% of exits are still stops and
the average trade lasts 7.9 bars.

So ADR-010's original prediction — *"a 1% stop on a breakout entry is removed by
ordinary noise"* — is **confirmed, not overturned**, by a result that
superficially looks positive. The 1% stop is a lottery-ticket distribution: it
loses 91% of the time and depends on a few extreme winners to pay for it. The
canonical 10% stop is the policy the evidence supports.

**This is the single most important finding of the re-run**, and the gate is
blind to it: `summarise()` returns the same `VALIDATED` for both.

### On the drawdown figure — now confirmed to be an artifact

The harness reports −100.00% peak-to-trough for the canonical policy and −99.22%
for the tight one, *alongside a positive expectancy*. That contradiction was
investigated rather than reported, and it is a defect in the metric:

- The worst individual trades are exactly **−10.00%** — the stop working
  correctly. There is no bad data and no runaway trade.
- The equity model compounds **100% of capital into one trade at a time, in exit
  order**, across 530 instruments whose trades in reality overlap heavily. An
  early losing run drove the notional curve to 0.000006 at trade #298
  (2023-12-21), after which the same multiplicative model "recovers" it to
  4.2 × 10¹⁷.

Both ends of that curve are fiction, and the deck's own rule is to divide
capital into ten parts. **The drawdown and any equity-curve return from this
harness should not be quoted at all** — only per-trade expectancy is meaningful
under this model. Suppressing or fixing the figure is a code change and is
proposed in §6, not made here.

---

## 5. Limitations that no amount of data removes

Reported alongside every summary, by construction — and now more consequential,
because a *positive* result is the one these biases would produce spuriously:

- **Survivorship bias — materially worse than before.** The universe is the
  instruments in the ledger *today*, so every name delisted between 2023 and
  2026 is absent, along with its outcome. Over four months this was a minor
  effect; over three years it is not. It biases results **upward**, which is the
  direction the result just moved. This cannot be quantified from the current
  data: the Kite dump is a point-in-time snapshot of live instruments with no
  historical membership, so measuring it requires a delisting history the
  project does not hold.
- **Costs excluded.** The harness models none. §4 applies them externally as a
  sensitivity; they are not in the reported expectancy.
- **Idealised fills.** Entries at the next bar's open, stops filled exactly at
  the stop, with no gap-through modelling. A 10% stop gapped through on bad news
  fills below the stop, so the −7.45% average loss is optimistic.
- **One market.** 2023-08 → 2026-08 was, on balance, a rising Indian market.
  Three years is above the gate's floor; it is not a full cycle.

---

## 6. Verdict, and what the evidence does and does not support

**`EXPERIMENTAL_UNVALIDATED` stands**, and every DarvaX payload and view keeps
the label. Removing it is an owner decision, not an automatic consequence of a
gate flipping — the label is hard-coded across the DarvaX surface and was not
touched.

| Threshold | Required | First run | Re-run |
|---|---|---|---|
| Closed trades | ≥ 200 | 301 ✅ | 1,975 ✅ |
| Trading days | ≥ 500 | 82 ❌ | **744 ✅** |

What the re-run genuinely establishes:

1. The methodology's canonical form has a **positive, cost-robust,
   non-outlier-dependent per-trade expectancy** on three years of NSE data. That
   is far more than the source deck ever supplied.
2. The **10%/1% contradiction in the deck is settled on evidence**: canonical.
3. The earlier negative result was a small-sample artifact, as predicted.

What it does not establish, and why the label should stay:

1. **Survivorship bias is unquantified and points the wrong way.** A positive
   result from a survivor-only universe is the textbook false positive.
2. **The sufficiency gate is now the weak link.** It certifies sample size and
   period, and it passed a policy that §4 shows to be outlier-dependent noise.
   A gate that cannot distinguish the two should not be the thing that removes a
   warning label.
3. **One market regime**, and no walk-forward or out-of-sample split.

### Proposed follow-ups (not implemented — each needs approval)

| | Change | Why |
|---|---|---|
| a | Suppress or redesign `max_drawdown` and any equity-curve figure in `summarise()` | §4 — it is currently a fiction that could be quoted in good faith |
| b | Add outlier-dependence (P&L share of top 1%) and a cost sensitivity to the summary | §4 computed these externally; they changed the conclusion, so they belong in the harness |
| c | Split the gate's `verdict` from its `sufficient` flag | They mean different things and are currently conflated |
| d | Walk-forward / out-of-sample split | Not attempted at all |

Items (a)–(c) would each have changed how this document reads, which is the
argument for them being in the harness rather than in a document.

---

## 7. Reproducing this

```bash
python3 - <<'EOF'
import sys; sys.path.insert(0, "src")
from athena.data.store.repository import SqliteRepository
from athena.darvax.adapters import SqliteMarketDataAdapter
from athena.darvax.validation import simulate_instrument, summarise
from athena.domain.enums import Timeframe

repo = SqliteRepository("db/athena.db")
market = SqliteMarketDataAdapter(repo)
trades, n = [], 0
for inst in market.list_instruments():
    candles = market.recent_candles(inst.instrument_id, Timeframe.D1, limit=5000)
    if candles:
        n += 1
        trades.extend(simulate_instrument(candles))
print(summarise(trades, instruments=n, trading_days=744))
EOF
```

Pass a `DarvaxMethodologyConfig(stop_policy=...)` as the second argument to
`simulate_instrument` to compare policies. Derive `trading_days` from the ledger
rather than hardcoding it — the figure above is correct as of 2026-08-14 and
grows with every daily cycle.

The cost and outlier-dependence figures in §4 are **not** produced by
`summarise()` (that is proposed follow-up (b)). They are computed from the
closed-trade `return_pct` values: sort descending, then compare the mean of all
trades against the mean excluding the top 1%, and subtract a flat round-trip
cost from the per-trade expectancy.
