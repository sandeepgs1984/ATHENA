# ADR-011 — Canonical symbol master and scanner-specific universes

| | |
|---|---|
| Status | **Accepted** (2026-08-15) |
| Date | 2026-08-15 |
| Deciders | sandeep (owner) |
| Investigation | [`docs/design/SYMBOL-UNIVERSE-INVESTIGATION.md`](../design/SYMBOL-UNIVERSE-INVESTIGATION.md) |

## Context

DarvaX could not see two of three owner-supplied candidates. The investigation
traced the exact cause, and it was **not** the one first suspected.

### What the investigation established

**The ingest scope is an owner-curated list, not an index.**
`ops/full_validation.py` reads `owner_candidates` (518 active rows) and passes
those symbols as the Kite catalog filter; `data/ingestion/engine.py` then
ingests **everything the provider returns**, because `ingestion.instrument_ids`
is empty. 517 of 518 resolved, plus 11 index instruments, reconciles the ledger
exactly at 528. `RATNAVEER` and `PNGSREVA` were simply never candidates.

An earlier hypothesis that the universe was Nifty-500-shaped was **wrong**:
`JGCHEM` appears in none of the 13 index constituent files and was ingested and
screened normally.

**Scanner universe and ingested candle universe are the same thing.**

```
owner_candidates → ingest scope → instruments table → DarvaX list_instruments() → screener
```

A symbol is visible to any scanner only if candles were permanently ingested for
it, and one global list drives ingestion for every subsystem. There is no
per-scanner universe concept anywhere in the codebase.

**The broker dump cannot classify instruments on its own.** Fetched live from
`/instruments/NSE`: 10,197 rows, of which 10,061 are NSE-segment — and
**`instrument_type` is `EQ` for every single one**, including government debt,
treasury bills, SME scrips and ETFs. There is no `series` column, and
`kite_provider.py` fabricates one (`series = itype or "EQ"`), so **every
instrument in the ledger carries `series="EQ"` whether or not that is true**.
`config/universe.json`'s `supported_series` is therefore filtering a
manufactured value.

Series is *inferable* from the trading-symbol suffix — `-SG` 4,298 (state
government loans), `-SM` 439 (SME), `-BE` 230, `-GS` 130, `-ST` 120, `-TB` 84 —
but that is a heuristic, not a contract. `last_price` is `0` for 100% of rows,
so no liquidity filter can be derived from the dump at all.

Filtering heuristically to plain equity yields **≈2,550** instruments against
today's 518 — an *estimate* for sizing, not a definition (§2.3).

**The 365-day limit is ATHENA's own.** `IngestionConfig.lookback_days` is bounded
`le=365`; the Kite provider declares `capabilities.max_history_days: 2000` and
`daily_candles()` applies no span check. A measured 365-day daily request
returned a full year **in a single call**, so windowing is only a question
beyond that bound.

**Validation result.** With the two symbols added and ingested, all three
qualify as rule B / ACTIONABLE on their exact reference dates, under strict
as-of evaluation. The detection logic is not in question; the discovery universe
is.

### Why this needs an ADR

Architecture is frozen. This introduces a new data-layer concept (a canonical
symbol master with group membership), a new resolution stage between symbols and
scanners, and changes what "the universe" means for every consumer. It also
touches ADR-010's pinned DarvaX boundary, which must not be widened casually.

### The distinction this ADR exists to make explicit

**Symbol existence ≠ scanner-universe membership ≠ scanner qualification.**

A stock can legitimately exist on NSE, sit outside NIFTY 500, belong to DarvaX's
discovery universe, and still fail DarvaX qualification. Today the first two are
conflated — a symbol effectively "exists" to ATHENA only once someone curates it
into a candidate list. There is a fourth link worth naming too: **a faithful
implementation of a rule is not evidence the rule is useful** (DX-5 measured
negative expectancy while detection validated 3/3).

---

## Decision

Five parts. Deliberately additive: nothing here changes an existing engine's
behaviour until a scanner opts in by name.

### 1. Canonical symbol master — one row per symbol

`symbol_master(symbol, exchange, instrument_id, name, series, series_source,
board, lot_size, tick_size, status, first_seen, last_seen, source,
classification_reason)`

> **SU-1 deviation, recorded:** this sketch originally listed `instrument_token`.
> It was **dropped during implementation**. A token is one vendor's identifier,
> and embedding it in the canonical model would bind the symbol master to Kite —
> exactly the coupling ADR-002 keeps behind the provider Protocol. Token lookup
> stays a provider concern. `classification_reason` was added in its place so an
> exclusion is traceable to a stated reason rather than an opaque rule.

Populated from the broker dump and, when obtained, an authoritative NSE series
list. `series` becomes a **real column with recorded provenance**
(`series_source ∈ {nse_official, inferred_suffix, broker}`) rather than the
fabricated `"EQ"` in use today. An inferred series is never presented as
authoritative.

The existing `instruments` table is **not** replaced. `symbol_master` is the
catalogue of what exists; `instruments` remains the record of what has been
ingested. Conflating them is the current defect.

### 2. Group membership as metadata — many-to-many, no duplicated symbols

`symbol_group(symbol, group, effective_date, source)`

One symbol belongs to many groups. **No symbol record is duplicated per group**,
as the brief requires. Membership is dated and sourced, reusing the immutable
dated-snapshot convention already established by
`data/index_constituents/<effective-date>/`.

Groups fall into four kinds, and keeping them distinct matters:

| Kind | Groups | Source |
|---|---|---|
| **Index** | `NIFTY_50`, `NIFTY_100`, `NIFTY_200`, `NIFTY_500`, `NIFTY_MIDCAP_150`, `NIFTY_SMALLCAP_250`, `NIFTY_MICROCAP_250`, `NIFTY_TOTAL_MARKET` | Dated NSE constituent snapshots |
| **Segment** | `FNO` | Derivatives eligibility |
| **Board** | **`NSE_MAINBOARD`**, **`NSE_SME`** | Listing board — see below |
| **Curated** | **`OWNER_CANDIDATES`** | The owner's own list — see below |
| **Derived** | `NSE_ALL_ELIGIBLE_EQUITY` | Rule-defined, see §2.3 |

#### 2.1 `OWNER_CANDIDATES` is a first-class group, not a legacy artefact

The `owner_candidates` table is **the owner's curated conviction list**, and it
is what ATHENA's pipeline runs on today. It is not scaffolding to be migrated
away from — it is a legitimate, deliberately-chosen universe that happens to
contain names no index does (`JGCHEM` being the proof).

It therefore becomes a first-class group, sourced from the existing table, and
remains independently editable. Nothing about this ADR deprecates it, and a
scanner may reference it alone, in combination, or not at all.

#### 2.2 `NSE_MAINBOARD` and `NSE_SME` are explicit groups

SME is a **board**, not a filter threshold. Modelling it as a group rather than
as an eligibility rule means the choice is made by naming a group in
`config/universes.json` — visible in configuration and reviewable in a diff —
instead of being buried in a suffix heuristic where it could be included or
excluded by accident. The brief asked for SME to be an explicit decision; this
is the mechanism that makes it one.

`-SM`-suffixed symbols (439 observed) map to `NSE_SME`; the remainder of
tradable equity maps to `NSE_MAINBOARD`. Both carry `series_source` provenance
until an authoritative NSE board list is obtained.

#### 2.3 `NSE_ALL_ELIGIBLE_EQUITY` is defined by rules, not by a number

**The group is whatever its rules currently resolve to.** Its definition is the
ordered, individually-explainable exclusion set in §4 — never a symbol count and
never a frozen list.

The **≈2,550** figure in the investigation is an **observed estimate on
2026-08-15 under heuristic filters**, recorded to size the problem and to
establish that existing performance evidence is invalidated. It is explicitly
**not** the contract. The real number will move as listings change, as an
authoritative series source replaces suffix inference, and as eligibility
thresholds are decided in SU-4 — and it is expected to.

Any test, document or config that pins a specific count as the definition of
this group is wrong by construction.

### 3. Universe resolver — configuration-driven, never hardcoded

`config/universes.json` maps a **universe name** to groups plus a named
eligibility profile:

```jsonc
{
  // Today's real universe. NOT an index — see §3.1.
  "athena_core":       { "groups": ["OWNER_CANDIDATES"],         "eligibility": "none" },

  "darvax_discovery":  { "groups": ["NSE_ALL_ELIGIBLE_EQUITY"],  "eligibility": "darvax_discovery" },
  "largecap_scanner":  { "groups": ["NIFTY_100"],                "eligibility": "athena_default" },
  "midcap_scanner":    { "groups": ["NIFTY_MIDCAP_150"],         "eligibility": "athena_default" },
  "smallcap_scanner":  { "groups": ["NIFTY_SMALLCAP_250"],       "eligibility": "athena_default" },
  "broad_scanner":     { "groups": ["NIFTY_TOTAL_MARKET"],       "eligibility": "athena_default" },
  "fno_scanner":       { "groups": ["FNO"],                      "eligibility": "athena_default" }
}
```

`resolve_universe(name) -> list[symbol]`. Scanners reference a **name**; no
scanner hardcodes a group or a filter, and adding a scanner is a config change.

#### 3.1 `athena_core` must reproduce today's universe exactly — and today's universe is not an index

An earlier draft of this ADR defined `athena_core` as `NIFTY_500`. **That was
wrong, and it contradicted this ADR's own Context section.** ATHENA does not run
on NIFTY 500 today; it runs on the 518-row `owner_candidates` table, which
contains names in no index at all. Defining `athena_core` as an index would have
silently changed the universe of every ATHENA engine at the exact moment the
migration was supposed to be behaviour-preserving — the most dangerous possible
outcome for a "purely additive" change.

`athena_core` therefore resolves to `OWNER_CANDIDATES` with **no eligibility
filter applied** (`"eligibility": "none"`), because no filter is applied today
either. Adding one would be a behaviour change wearing the costume of a
refactor.

**SU-3 acceptance criterion, non-negotiable:** `resolve_universe("athena_core")`
must return a set **identical** to the symbols ATHENA ingests today, asserted by
a test that compares the resolver's output against the live `owner_candidates`
list — not against a count, and not against a hand-written fixture. If the sets
differ by even one symbol, SU-3 has failed regardless of how clean the
abstraction looks.

Migrating ATHENA to a different universe is a **separate, later, deliberate
decision** with its own approval. It is not part of this ADR.

### 4. Scanner-specific eligibility profiles

Each profile is a named, configured set of filters over the resolved group.
**No thresholds are fixed by this ADR** — the investigation deliberately stopped
short of inventing them. What the ADR fixes is that eligibility is *explicit,
named, per-scanner, and explainable*, with each exclusion attributable to a
named rule.

Categories the investigation shows must be decided (not defaulted): tradable
series, SME inclusion, ETFs, debt and government paper, indices, preference
shares, warrants, rights, duplicate listings, suspended instruments, surveillance
categories, minimum liquidity, minimum history.

Two constraints discovered that shape this:

- **Liquidity cannot come from the instrument dump** (`last_price` is always 0),
  so any liquidity rule needs quotes or ingested candles — which is circular for
  a symbol not yet ingested. This may force a staged approach for *correctness*
  reasons rather than performance ones.
- **SME must be an explicit decision** (439 `-SM` symbols), never an accident of
  suffix filtering.

### 5. Separate required coverage from ingested universe

The one genuinely structural change:

```
resolve_universe(name) → symbols
   → coverage requirement (timeframe, minimum bars)
   → planner: which symbols fall short
   → backfill only those
```

Membership of a discovery universe no longer implies permanent ingestion for
every subsystem. This is what allows DarvaX to discover across ~2,550 symbols
without forcing ATHENA's pipeline to process them.

### How DarvaX consumes this without breaching ADR-010

**A universe is data, not a service DarvaX calls.** The resolver writes its
result where DarvaX's existing read-only port can see it, and DarvaX reads it as
data through `DarvaxMarketDataPort` — exactly as it already reads candles.

DarvaX therefore imports **no** ATHENA resolver, engine or config model, and
ADR-010 §1's pinned import surface is unchanged. This is a deliberate rejection
of the more obvious design (DarvaX calls a resolver), which would have widened
the dependency ADR-010 exists to prevent.

---

## What this explicitly does not do

- **Does not widen ATHENA's own universe.** `athena_core` resolves to
  `OWNER_CANDIDATES` with no eligibility filter — set-identical to what ATHENA
  ingests today (§3.1). Changing ATHENA's universe is a separate decision.
- **Does not ingest more by default.** Nothing is fetched until a scanner
  declares a coverage requirement.
- **Does not change any DarvaX detection rule.** Validation confirmed the logic;
  only the search space is at issue.
- **Does not raise `lookback_days`.** That is a separate decision on separate
  evidence (see Consequences).
- **Does not introduce a staged/two-phase scan.** Only if measurement shows it
  is necessary — correct coverage before premature optimisation.

---

## Alternatives considered

**Widen `owner_candidates` to all NSE equities.** Rejected by the brief and on
merit: it would force every ATHENA subsystem to process ~2,550 symbols to serve
one scanner, and would conflate curation with discovery permanently.

**Give DarvaX its own separate symbol ingestion.** Rejected: two independent
symbol catalogues would drift, and DarvaX would gain write concerns ADR-010
denies it.

**Filter by index membership only.** Rejected by evidence: `JGCHEM` is in no
index file yet is a valid candidate, and the owner's examples are deliberately
broader-market.

**Keep inferring series from symbol suffixes as the contract.** Rejected as a
permanent answer: it is a serviceable first cut but would quietly admit debt or
SME paper. Acceptable only with `series_source` recorded and an authoritative
list pursued.

**DarvaX calls a universe resolver directly.** Rejected — see the ADR-010 note
above. Passing resolved data through the existing port achieves the same result
without widening the satellite's import surface.

---

## Consequences

| Area | Impact |
|---|---|
| `instruments` table | Unchanged; `symbol_master` sits beside it |
| ATHENA schema | New tables ⇒ `SCHEMA_VERSION` bump + migration |
| `config/universe.json` | Its `supported_series` currently filters a fabricated value; moving to real series data **is a behaviour change requiring its own review**. Not triggered by `athena_core`, which applies no eligibility filter |
| Ingestion | Gains a coverage-planner path; the existing scope path is untouched |
| DarvaX | Port and rules unchanged; only the returned symbol set widens |
| DX-4a / DX-6d evidence | **Invalidated at ~2,550 symbols.** Both measured 528, and DX-6d names universe growth as its own re-measure trigger |
| DX-5 validation | Improves on both axes — more instruments and, with backfill, more history |
| Kite rate limits | The real operational cost: `historical_min_interval_seconds: 0.334` (~3 req/s) means a 2,550-symbol backfill is tens of minutes and must be planned, not run inside a cycle |

### Risks accepted

1. **Heuristic series inference is not authoritative.** Mitigated by
   `series_source` provenance and by pursuing the NSE list; never presented as
   fact.
2. **A ~5× universe invalidates existing performance evidence.** DX-6d must be
   re-run; this is a known, planned cost rather than a surprise.
3. **Liquidity filtering is circular for un-ingested symbols** and may force
   staging on correctness grounds.
4. **A larger ACTIONABLE set.** The current sweep flags 13.8% of the universe;
   at 2,550 symbols that is ~350 names at once. Correct coverage will make the
   *precision* question urgent — which the current three-symbol validation, being
   confirmation-only with no negative controls, does not address.

### A latent defect to fix regardless of this ADR

`config/providers/kite.json` sets `symbols: ["INFY"]`. It is inert only because
every real ingest path overrides it. An ingest run without a candidate scope
would silently collapse the universe to INFY plus index instruments. This should
be corrected whatever is decided here.

---

## Implementation gate

**No implementation until this ADR is Accepted.** Then, one reviewable milestone
at a time, each stopping for owner approval:

| Milestone | Scope |
|---|---|
| **SU-1** | `symbol_master` table + broker-dump population + `series_source` provenance. No consumer changes |
| **SU-2** | `symbol_group` membership + loaders for the dated index snapshots, plus `OWNER_CANDIDATES` from the existing table and the `NSE_MAINBOARD`/`NSE_SME` board split |
| **SU-3** | `config/universes.json` + `resolve_universe()`; **`athena_core` → `OWNER_CANDIDATES`, asserted set-identical to the live table** (§3.1) |
| **SU-4** | Eligibility profiles, with thresholds decided from data and each exclusion individually explainable |
| **SU-5** | Coverage planner + bounded backfill, respecting Kite rate limits |
| **SU-6** | DarvaX opts into `darvax_discovery`; re-run DX-4a/DX-6d at the new size |

Open questions to settle before SU-4, all noted as owner decisions in the
investigation:

- Is an authoritative NSE series/board list obtainable, or does inference stand?
- SME: in or out?
- What liquidity and history minimums, given they cannot be measured before
  ingestion?
