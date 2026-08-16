# Symbol master and scanner universes — investigation

Why `RATNAVEER` and `PNGSREVA` are missing, what the current pipeline actually
does, and the smallest clean change that would support scanner-specific
universes.

**Status:** 🔄 Investigation complete — **no implementation.** Proposal in §6
needs an ADR and owner approval before any code.
**Investigated:** 2026-08-15 · **Trigger:** three owner-supplied DarvaX
candidates, two of which the screener structurally could not see.

---

## 1. The exact reason, traced end to end

Not an index filter. Not a series filter. Not SME exclusion. **The two symbols
were never added to the owner candidate list.**

The chain, in order:

| # | Component | What it does |
|---|---|---|
| 1 | `ops/full_validation.py` (and `cli.py`) | Reads `SqliteCandidateStore.list_candidates(active_only=True)` → passes those trading symbols as `kite_symbols` |
| 2 | `data/providers/factory.py` | `build_market_data_provider(..., kite_symbols=…)` |
| 3 | `KiteProvider.from_config_dir` | `if symbols is not None: config = config.model_copy(update={"symbols": …})` — the caller's scope **replaces** `kite.json`'s |
| 4 | `KiteProvider._ensure_catalog` | Filters the NSE dump by `instrument_type ∈ instrument_types`, then by `symbols` when non-empty |
| 5 | `data/ingestion/engine.py` `run_cycle` | `ingestion.instrument_ids` is `[]`, so `selected = list(instruments)` — **everything the provider returned** — then `upsert_instrument` for each |
| 6 | `darvax/adapters.py` | `list_instruments()` → `repo.list_instruments()` → the `instruments` table |

### The arithmetic reconciles exactly

| | |
|---|---|
| `owner_candidates` rows, active | **518** |
| Instruments in ledger | **528** |
| Configured index instruments + India VIX | 11 |
| Ledger minus index instruments | 517 |
| Non-index ledger instruments that are *not* candidates | **none** |

517 of 518 candidates resolved against the catalog (one did not), plus 11 index
instruments = 528.

`JGCHEM` is in `owner_candidates`, added **2026-08-11**. `RATNAVEER` and
`PNGSREVA` are absent. That is the whole reason.

### Correction to the previous session's hypothesis

An earlier note suggested the universe was Nifty-500/large-cap oriented and that
DarvaX was structurally blind to smallcaps. **That was wrong.** `JGCHEM` appears
in none of the 13 index constituent files (240 unique symbols) yet is ingested
and screened normally. The universe is an owner-curated candidate list, not an
index-derived one. The conclusion — that the discovery universe is too narrow —
still stands; the stated mechanism did not.

### One knob that is currently a no-op

`config/providers/kite.json` sets `symbols: ["INFY"]`. Because every real ingest
path passes a candidate scope that replaces it, this value never takes effect.
An ingest run *without* a scope would silently collapse the universe to INFY
plus index instruments. That is a live trap regardless of what is decided below.

---

## 2. Confirmed: scanner universe **is** the ingested candle universe

The coupling the brief asked about exists exactly as suspected:

```
owner_candidates → ingest scope → instruments table → DarvaX list_instruments() → screener
```

There is no separate notion of "symbols DarvaX may discover". A symbol is
visible to a scanner **only** if candles were permanently ingested for it, and
ingestion is driven by one global candidate list shared by every subsystem.

There is no per-scanner universe concept anywhere in the codebase.

---

## 3. What the Kite symbol master actually provides

Fetched live from `/instruments/NSE`:

| | |
|---|---|
| Total rows | 10,197 |
| `segment == "NSE"` | 10,061 |
| `segment == "INDICES"` | 136 |
| Distinct `instrument_type` values | **`EQ` only — all 10,197** |
| Columns | `instrument_token, exchange_token, tradingsymbol, name, last_price, expiry, strike, tick_size, lot_size, instrument_type, segment, exchange` |

Three findings that shape any eligibility design:

**1. `instrument_types: ["EQ"]` filters nothing.** Every NSE row is typed `EQ`,
including government debt, treasury bills, SME scrips and ETFs. The filter is
inert on this exchange.

**2. There is no `series` column, and ATHENA fabricates one.**
`kite_provider.py` does `series = itype or "EQ"`, so **every instrument in the
ledger carries `series="EQ"` whether or not that is true**. `config/universe.json`'s
`supported_series: ["EQ", "BE"]` is therefore filtering on a fabricated value.

**3. Series is inferable from the trading-symbol suffix — but only as a
heuristic.**

| Suffix | Count | Almost certainly |
|---|---|---|
| `-SG` | 4,298 | State government loans (debt) |
| `-SM` | 439 | **SME** |
| `-BE` | 230 | Trade-for-trade equity |
| `-GS` | 130 | Government securities |
| `-ST` | 120 | State development loans |
| `-TB` | 84 | Treasury bills |
| `-SF`, `-GB` | 50, 45 | Other government paper |

Also: `last_price` is `0` for **100%** of rows, so the dump cannot support any
liquidity or traded-value filter — that must come from quotes or candles.
ETFs are identifiable only by name heuristics (351 by `ETF` in name or `BEES`
suffix).

### Sizing a plausible discovery universe

Applying suffix/ETF/lot heuristics to the 10,061 NSE-segment rows:

| Step | Removed | Remaining |
|---|---|---|
| start | — | 10,061 |
| drop hyphen-suffixed (`-SG`/`-SM`/`-BE`/…) | 7,091 | 2,970 |
| drop `lot_size != 1` | 0 | 2,970 |
| drop ETF by name/`BEES` | 351 | 2,619 |
| drop symbols with 2+ digits | 69 | **2,550** |

**≈2,550 plausible plain-equity instruments**, against today's 518. All three
owner symbols survive every filter.

**This is heuristic, not authoritative.** Suffix inference is a good first cut
and a poor contract. Authoritative series/board data would need NSE's own equity
list (`EQUITY_L.csv` or the equivalent), which is a second source to obtain and
version — the same pattern `data/index_constituents/<effective-date>/` already
uses. **No thresholds are proposed here**, per the brief.

---

## 4. All three symbols verified in the NSE master

No typos — the tickers given are exact:

| Ticker | Name | Token | Lot | Tick |
|---|---|---|---|---|
| `RATNAVEER` | RATNAVEER PRECISION ENG L | 4716289 | 1 | 0.01 |
| `JGCHEM` | J.G.CHEMICALS | 5902337 | 1 | 0.05 |
| `PNGSREVA` | PNGS REVA DIAMOND JEWEL L | 194621953 | 1 | 0.05 |

None carries a series suffix; all three are plain-EQ. None appears in any of the
13 index constituent files.

---

## 5. The 365-day limit — answered

**It is ATHENA's own arbitrary bound, not a Kite constraint.**

| Evidence | |
|---|---|
| `IngestionConfig.lookback_days` | `Field(default=5, ge=1, le=365)` — ours |
| `config/providers/kite.json` → `capabilities.max_history_days` | **2000** (≈8 years) |
| `KiteProvider.intraday_candles` | Enforces `max_history_days` |
| `KiteProvider.daily_candles` | **Does not enforce any span limit** |

So the provider is declared capable of ~2000 days of history, the daily path
applies no span check, and the only thing stopping a deeper daily backfill is a
`le=365` validator in ATHENA's own config model.

Two caveats were raised before changing it:

- Kite's *own* historical API applies per-request span limits by interval (day
  candles allow long ranges; minute candles do not). A deep daily backfill may
  still need **windowed requests**, which `daily_candles` does not currently do —
  it issues one call for the whole range.
- Rate limiting is real: `historical_min_interval_seconds: 0.334` (~3 req/s). A
  2,550-symbol × multi-window backfill is on the order of tens of minutes and
  should be planned, not fired off inside a cycle.

The recommendation at the time was **"do not change `le=365` yet — measure
first."**

### Resolved (2026-08-16): measured, and the bound was raised

The measurement was taken. Probing Kite at 365 / 730 / 1095 / 1825 / 2000 /
2500 / **3650** days returned **the full requested span in a single daily
request** every time — 2,474 bars in 1.1 s at 3,650 days.

- **No windowing is needed.** The first caveat does not apply to daily candles;
  `daily_candles` issuing one call for the whole range is correct.
- **The rate-limit concern was overestimated for this shape of job**, because it
  is one request per symbol rather than per symbol × window. The full backfill
  of 513 symbols took **3.5 minutes**.

`IngestionConfig.lookback_days` was therefore raised to `le=3650`, with the
measurement recorded inline at the field. `config/ingestion.json` itself was
deliberately left shallow — the backfill was run as a one-off through SU-5's
`execute_backfill`, so the routine daily cycle still fetches only what it needs.

Result: the ledger went from 82 to **744 trading days** (43,223 → 362,949 daily
candles), which unblocked DX-5. See
[DARVAX-VALIDATION-EVIDENCE.md](DARVAX-VALIDATION-EVIDENCE.md) §3.

One correction that came out of the same exercise: **`skip_existing: true` skips
*writes*, not *fetches*.** It does not make a deeper re-ingest cheap, and
history does not accrete for free across runs.

---

## 6. Proposal — the smallest clean change

Four pieces. Deliberately additive: nothing below changes an existing engine's
behaviour until a scanner opts in.

### 6.1 Canonical symbol master (new table, one row per symbol)

`symbol_master(symbol, exchange, instrument_token, name, series, board, lot_size,
tick_size, status, first_seen, last_seen, source)`

Populated from the broker dump plus, when obtained, an authoritative NSE series
source. `series` becomes a **real** column sourced or inferred explicitly, with
provenance — replacing today's fabricated `"EQ"`.

### 6.2 Group membership (new table, many-to-many)

`symbol_group(symbol, group, effective_date, source)`

One symbol, many groups — `NIFTY_50`, `NIFTY_500`, `NIFTY_SMALLCAP_250`,
`NIFTY_TOTAL_MARKET`, `FNO`, `NSE_ALL_ELIGIBLE_EQUITY`. **No duplicated symbol
records**, exactly as the brief requires. Reuses the existing dated-snapshot
convention from `data/index_constituents/<effective-date>/`.

### 6.3 Universe resolver (new module, config-driven)

`config/universes.json`:

```jsonc
{
  "athena_core": { "groups": ["NIFTY_500"], "eligibility": "athena_default" },
  "darvax_discovery": {
    "groups": ["NSE_ALL_ELIGIBLE_EQUITY"],
    "eligibility": "darvax_discovery"
  }
}
```

`resolve_universe(name) -> list[symbol]` — group membership, then a **named
eligibility profile**. Scanners reference a universe *name*; no scanner
hardcodes a group or a filter.

### 6.4 Separate "required coverage" from "ingested universe"

The one genuinely structural change. Today ingestion decides the universe;
instead a scanner declares what it needs:

```
resolve_universe(name) -> symbols
   -> coverage requirement (timeframe, minimum bars)
   -> planner: which symbols lack coverage
   -> backfill only those
```

This is what lets DarvaX discover across 2,550 symbols without forcing every
ATHENA subsystem to process them.

### What this does **not** do

- Does not change ATHENA's own universe. `athena_core` resolves to today's
  behaviour.
- Does not widen the ingest by default. Nothing ingests more until a scanner
  asks for coverage.
- Does not touch DarvaX's detection rules — §7 of the brief, respected.

---

## 7. Impact analysis

| Area | Impact |
|---|---|
| `instruments` table | Unchanged. `symbol_master` sits beside it; migration later if ever |
| ATHENA schema | New tables ⇒ `SCHEMA_VERSION` bump + migration |
| `config/universe.json` | Its `supported_series` currently filters a fabricated value; would move to real series data — **a behaviour change to review carefully** |
| Ingestion engine | Gains a coverage-planner path; existing scope path untouched |
| DarvaX | `DarvaxMarketDataPort` unchanged. Only the *set* returned by `list_instruments()` widens — no DarvaX rule changes |
| DX-4a / DX-6d performance evidence | **Invalidated at 2,550 symbols.** Both measured 528. A universe ~5× larger needs re-measurement — DX-6d's own trigger |
| DX-5 validation | Improves in both dimensions: more instruments *and* (with backfill) more history |
| Kite rate limits | The real operational cost. A 2,550-symbol backfill needs planning |
| ADR | **Required.** New subsystem + schema + a data-layer concept. Architecture is frozen |

### Risks worth stating

1. **Heuristic series inference is not a contract.** Shipping suffix rules as
   though authoritative would quietly admit debt or SME paper. Obtain the NSE
   list first, or mark inferred series with explicit provenance.
2. **SME needs an explicit decision** (439 `-SM` symbols), per the brief — not an
   accidental include or exclude.
3. **Liquidity filters cannot come from the instrument dump** (`last_price` is
   always 0), so they need quotes or ingested candles — which is circular for a
   symbol not yet ingested. A two-stage approach may be forced by this, not by
   performance.
4. **A 5× universe invalidates existing performance evidence**, and DX-6d
   explicitly names universe growth as a re-measure trigger.

---

## 8. Recommended sequence

1. **Unblock the immediate question** — add `RATNAVEER` and `PNGSREVA` to
   `owner_candidates`, ingest, and re-run the three-symbol validation. This needs
   **no** architecture change and answers "does DarvaX detect them?" today.
2. **Establish the Kite daily-history span** empirically → decide the
   `lookback_days` question on evidence.
3. **Obtain an authoritative NSE equity/series list** → removes the heuristic.
4. **ADR-011** for §6, then implement in reviewable milestones: symbol master →
   groups → resolver → coverage planner.
5. **Re-measure DX-4a/DX-6d** at the new universe size.

Step 1 is independent of everything else and is the fastest route to the answer
the brief actually wants.

---

## 9. Step 1 executed — three-symbol validation (2026-08-15)

`RATNAVEER` and `PNGSREVA` added to `owner_candidates` (518 → 520), then a
**scoped** daily ingest for those symbols only. **All three qualify on their
exact reference dates**, evaluated strictly as-of with no lookahead.

| | JGCHEM | RATNAVEER | PNGSREVA |
|---|---|---|---|
| Canonical symbol | `NSE:JGCHEM` | `NSE:RATNAVEER` | `NSE:PNGSREVA` |
| In NSE/broker master | ✅ J.G.CHEMICALS | ✅ RATNAVEER PRECISION ENG L | ✅ PNGS REVA DIAMOND JEWEL L |
| Index/group membership | none of the 13 index files | none | none |
| In the old 528 universe? | **yes** — candidate since 2026-08-11 | **no** — never a candidate | **no** — never a candidate |
| Candle depth (after ingest) | 246 bars (was 69) | 246 bars | 111 bars (listed 2026-03-04) |
| Topmost box before ref | 457.3 – 532 | 171.12 – 197 | 407.05 – 476.75 |
| Breakout level | 532 | 197 | 476.75 |
| Breakout date | **2026-08-05** ✅ | **2026-08-13** ✅ | **2026-08-11** ✅ |
| Close on that date | 546 | 220 | 560.40 |
| Owner's reference price | 547 (−1.00) | 219 (+1.00) | 529 — not an OHLC value; inside the bar's 511.65–574.05 range |
| Rule triggered | **B** | **B** | **B** |
| Tier | **ACTIONABLE** | **ACTIONABLE** | **ACTIONABLE** |
| Behaviour after | +19.8% to 654 in 7 bars | +5.9% to 233.02 next bar | +14.9% to 644 in 3 bars |

### The match is informative, not near-permanent

ACTIONABLE is a **selective** state, so hitting three exact dates is meaningful
rather than inevitable:

| Symbol | Days evaluated | ACTIONABLE | WATCH |
|---|---|---|---|
| JGCHEM | 236 | 8 (3.4%) | 24 (10.2%) |
| RATNAVEER | 236 | 25 (10.6%) | 94 (39.8%) |
| PNGSREVA | 101 | 10 (9.9%) | 46 (45.5%) |

### Robust to history depth

JGCHEM re-ingested from 69 to 246 bars: completed boxes went 4 → 19 and the
topmost box moved 487.15–527 → 457.3–532, but the 5 Aug verdict was **identical**
(BREAKOUT / rule B / ACTIONABLE). The screener's answer did not depend on how
much history happened to be ingested.

### Honest caveats

- **These were not the only breakouts.** First rule-B events were 2026-05-29
  (JGCHEM), 2025-09-24 (RATNAVEER), 2026-05-06 (PNGSREVA). DarvaX flags every
  rule-B breakout, so matching a date confirms detection — it does not mean the
  engine uniquely selected that date.
- **Universe depth was inconsistent** when this was written: these three had
  246/246/111 bars while the other 517 still had ~82, so comparisons across the
  universe were not like-for-like. *Resolved 2026-08-16 by the uniform backfill
  described in §5 — the ledger now holds 744 trading days.*
- **`lookback_days: 365` returned a full year in a single Kite request** — no
  windowing was needed. This informed §5, where the question was then settled in
  full: a single daily request returns spans up to **3,650 days**, so windowing
  is not required at any depth ATHENA needs and the `le` bound was raised.


---

## 10. Live defect found by SU-2 (2026-08-15)

SU-2's first run against real data surfaced a **silent, live data-loss defect**
— which is the whole reason unresolved symbols are reported rather than dropped.

Two of the 520 active `owner_candidates` resolve to nothing in the current NSE
catalogue:

| Symbol | Catalogue | Ledger | Verdict |
|---|---|---|---|
| `INFSDFSD` | absent | 0 instruments, 0 candles | Junk entry, never resolved |
| **`E2E`** | **now listed as `E2E-BE`** | `NSE:E2E`, 78 daily bars | **Series change, silently broke ingestion** |

### What happened to E2E

`E2E NETWORKS` moved from the `EQ` series to the **`BE` series** (trade-for-trade,
typically a surveillance measure). NSE's trading symbol changed accordingly to
`E2E-BE`, so the candidate `E2E` stopped matching the catalogue.

**Its last daily bar is 2026-08-10.** The ledger's latest is 2026-08-14, and
**529 of 530 instruments have a bar that day — E2E is the only one missing.** It
has been silently stale for four sessions, with nothing reported.

Two distinct problems, both worth acting on:

1. **Ingestion fails silently on a series change.** A candidate that stops
   resolving produces no warning; it simply stops receiving data. Any engine
   reading `NSE:E2E` gets stale prices with no staleness signal.
2. **The series move is itself information.** A shift to trade-for-trade is
   material to a trader and ATHENA had no way to surface it, because until SU-1
   it did not model series at all.

### Why this validates the design

Nothing in ATHENA detected this. SU-2 found it on its first run purely because
`MembershipBuild` returns unresolved symbols instead of discarding them — the
same "surface, never swallow" discipline used for scan skips. A resolver that
quietly dropped non-matching symbols would have hidden it indefinitely.

**Not fixed here.** Repairing it means deciding whether a series change should
re-map a candidate automatically (and whether `E2E-BE` is even wanted, given
what BE implies), which is an owner decision and outside SU-2's scope.
