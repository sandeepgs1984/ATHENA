# DX-5 — DarvaX validation evidence

Does the DarvaX methodology earn the removal of its `EXPERIMENTAL_UNVALIDATED`
label?

**Answer: no.** The ledger cannot currently support validation, and what
evidence it does support is unfavourable.

**Milestone:** DX-5 · **Governing decision:**
[ADR-010](../adr/ADR-010-darvax-satellite-module.md) ·
**Harness:** [`src/athena/darvax/validation/`](../../src/athena/darvax/validation/) ·
**Measured:** 2026-08-15 · **Verdict:** `EXPERIMENTAL_UNVALIDATED`

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

## 3. The blocker: the ledger holds 82 trading days

| | |
|---|---|
| Daily candles | 43,223 |
| Instruments | 528 |
| Date range | 2026-04-20 → 2026-08-14 |
| **Trading days** | **82** |
| Bars per instrument | min 65, median 82 |

Against a **500 trading day** floor (roughly two years). A breakout methodology
measured across 82 days of a single market regime tells you about that regime,
not about the methodology.

**This is a configuration limit, not a vendor one.** `config/ingestion.json`
sets `lookback_days: 90`, which is why the ledger starts in April. Kite Connect
serves far more daily history than that.

**Correction (2026-08-15):** raising `lookback_days` alone does not reach the
floor. `IngestionConfig` bounds it at **365** (`ge=1, le=365`), and 365 calendar
days is roughly 248 trading days — still short of 500. The realistic path is
therefore two-stage, because `skip_existing: true` means each ingest *keeps*
prior candles and history accretes across runs:

1. Set `lookback_days: 365` and re-ingest once, taking the ledger from 82 to
   roughly 248 trading days — enough to make the numbers meaningfully better
   than they are now, though still under the floor.
2. Let it accumulate. At ~250 sessions a year the 500-day floor is reached about
   a year later, without any further change.

Raising the `le=365` bound to reach 500 in one step is a config-model change and
is **not** proposed here: the bound presumably reflects a vendor or rate-limit
consideration that should be checked before it is widened.

---

## 4. What the available data does show

Full universe, 528 instruments, 82 trading days. Both documented stop policies
were run, because ADR-010 records the deck's contradiction between them and
deliberately left it for evidence to settle.

| | **canonical_darvas** (10%, deck p.67) | **darvax_tight** (1%, deck p.44) |
|---|---|---|
| Closed trades | 301 | 677 |
| Still open | 159 (35%) | 59 (8%) |
| **Win rate** | **21.3%** | **4.3%** |
| **Expectancy / trade** | **−3.62%** | **−0.48%** |
| Average win | +9.29% | +11.01% |
| Average loss | −7.10% | −1.00% |
| Profit factor | 0.35 | 0.49 |
| Average bars held | 17.1 | 3.3 |
| Exits by stop | 103 (34%) | **647 (96%)** |
| Exits by rule C | 198 | 30 |
| **Verdict** | `EXPERIMENTAL_UNVALIDATED` | `EXPERIMENTAL_UNVALIDATED` |

### The 1% stop is measurably noise-level

ADR-010's Context predicted this in words: *"a 1% stop on a breakout entry is
removed by ordinary noise."* It is now measured. Under the tight policy **96% of
all exits are stops**, the average trade lasts **3.3 bars**, and the win rate is
**4.3%** — the position is being closed by ordinary daily fluctuation before the
thesis has any opportunity to resolve.

This conclusion is also the more trustworthy of the two, because the tight
policy leaves only 8% of trades open — so it is barely affected by the exclusion
bias described below.

### The 10% result is genuinely uncertain

Canonical Darvas has the better per-trade economics (+9.29% average win against
−7.10% average loss), but a negative expectancy on this sample. That figure is
**not reliable**, and the direction of its unreliability is knowable: 35% of
entries were still open when the data ended, losers exit quickly on the stop
while winners ride, so the excluded trades are disproportionately the good ones.
**These figures are likely pessimistic.** How pessimistic cannot be established
from 82 days.

### On the drawdown figure

The harness reports −100% peak-to-trough for the canonical policy. That is
arithmetically correct for its model — one position at a time, compounding the
full account — and **misleading as an account outcome**, because the deck's own
rule is to divide capital into ten parts. With a negative expectancy, full
compounding drives any curve towards −100%. Read it as a property of the
assumption, not a prediction. It is reported with that caveat attached rather
than suppressed.

---

## 5. Limitations that no amount of data removes

Reported alongside every summary, by construction:

- **Survivorship bias.** The universe is the instruments in the ledger *today*,
  so names delisted during the period are absent — and their outcomes are
  disproportionately bad.
- **Costs excluded.** No brokerage, STT, slippage or impact. A breakout system
  trades often, so real returns are materially lower than shown.
- **Idealised fills.** Entries at the next bar's open, stops filled exactly at
  the stop, with no gap-through modelling.

---

## 6. Verdict and what would change it

**`EXPERIMENTAL_UNVALIDATED` stands.** Every DarvaX payload and view keeps the
label. The gate is enforced in code, not left to the reader: `summarise()`
returns `VALIDATED` only when both thresholds clear, and no configuration
setting overrides it.

| Threshold | Required | Actual |
|---|---|---|
| Closed trades | ≥ 200 | 301 ✅ |
| Trading days | ≥ 500 | **82 ❌** |

The sample size already clears. **The period is the sole blocker**, and it has
one fix: raise `lookback_days` in `config/ingestion.json`, re-ingest daily
history, and re-run. That is an owner decision with real ingestion cost, so it
is proposed here rather than performed.

Re-running after a deeper backfill is a single command (§7). If the numbers
still look like §4 with two years of data behind them, that is a real answer
too — and a more valuable one than the label.

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
print(summarise(trades, instruments=n, trading_days=82))
EOF
```

The full 528-instrument simulation takes about **2 seconds**. Pass a
`DarvaxMethodologyConfig(stop_policy=...)` as the second argument to
`simulate_instrument` to compare policies.
