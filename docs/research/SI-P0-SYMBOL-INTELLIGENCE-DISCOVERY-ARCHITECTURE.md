# SI-P0 — ATHENA Symbol Intelligence: Discovery & Architecture

Status: Discovery only — no implementation, no schema/API/frontend/scoring changes  
Date: 2026-09-13  
Scope: New first-class dashboard workspace, "Symbol Intelligence"  
Boundary: Evidence-first composition over existing ATHENA / DarvaX / Portfolio artifacts. Do not duplicate DecisionEngine, DarvaX, or Portfolio holdings logic.

Inspection method: repository source, tests, schema, and live API/UI wiring. Documentation is cited only when it matches code. Where docs and code conflict, **code wins** and the conflict is named.

---

## 1. Executive Summary

**Symbol Intelligence (SI) is architecturally feasible as a composition workspace, not as a new decision engine.**

ATHENA already has most of the *symbol-level raw evidence* a cockpit needs:

- persisted D1/M5/M15 OHLCV (`candles` in `db/athena.db`, `SCHEMA_VERSION` 20)
- a full Decision pipeline (regime → indicators → evidence bundle → score → confidence → risk → `Decision` + `TradePlan` + `GateResult` + trace)
- Entry Qualification, Entry Actionability, and ID-11 Intraday Intelligence bound to a Decision
- DarvaX boxes/signals/screen results in a separate `db/darvax.db`
- My Portfolio holdings, sync snapshots, interpretation, Daily Review, and structural review for *held* symbols
- SuperTrend 10,3, RSI14, volume MA, ATH/rolling-high, and D1 swing-zone structural levels (portfolio-owned, D1-candle consumers)
- session, advisory-freshness, Decision TradePlan freshness, DarvaX sweep freshness, portfolio snapshot currentness

ATHENA does **not** currently have:

- a first-class symbol investigation workspace (the closest analog is DarvaX-owned **Symbol 360**, which is a thin side-by-side of Decision + DarvaX screen + saved-symbol + journal)
- quarterly fundamentals / earnings acceleration
- exchange filings / news / catalyst ingestion
- a frozen methodology for "Momentum Quality" or "Entry Quality" as distinct owner-facing scores
- a frozen D1 structural-state vocabulary (breakout already occurred / high-level consolidation / extended / compression / base / price discovery) as an SI contract
- an LLM/AI interpretation layer (explicitly forbidden in live explainability engines)

**Recommended architectural direction**

```
persisted / deterministic ATHENA evidence
  → SI composition contract (typed, source-tagged, freshness-tagged, nullable)
    → optional deterministic SI interpreters (future, owner-frozen, never silent forks)
      → optional AI narrative over the contract only
        → Symbol Intelligence workspace (Overview + Complete Review + owned segments)
```

SI must **consume and present** ATHENA Decision, DarvaX, and Portfolio. It must not create:

- `SI DecisionEngine`
- a second Darvas box/breakout engine
- a second holdings ledger or portfolio interpreter
- a second ScoringEngine "momentum quality" that re-weights RSI/trend/RS already inside `ScoringEngine`

**Verdict:** `READY WITH OWNER DECISIONS REQUIRED` — see §21. Composition can start; scoring, structural-state methodology, fundamentals/news providers, and the ATHENA→DarvaX read seam cannot be silently invented.

---

## 2. Existing Capability Inventory

### 2.1 Dashboard / frontend composition (confirmed)

Top-level tabs in `src/athena/api/static/index.html`:

| Tab | `data-tab` | Route | Loader (`03-app-shell.js::loadTabData`) |
|---|---|---|---|
| Portfolio Overview | `overview` | `/dashboard/overview` | `loadPortfolioData` |
| Market Intelligence | `market` | `/dashboard/market` | `loadMarketIntelligence` (+ optional EMR) |
| My Portfolio | `my-portfolio` | `/dashboard/my-portfolio` | `loadMyPortfolioWorkspace` |
| Strategies & Scans | `strategies` | `/dashboard/strategies` | `loadStrategiesWorkspace` |
| Decisions & Trace | `decisions` | `/dashboard/decisions` | `loadDecisionsWorkspace` |
| Live Operations | `operations` | `/dashboard/operations` | `loadOperationsWorkspace` |
| Reports & Analytics | *(disabled)* | none | inert `nav-item-disabled` |
| DarvaX | `darvax` (injected) | `/dashboard/darvax` | `src/athena/darvax/api/static/tab.js` iframe of `/darvax/` |

JS assembly is `DASHBOARD_JS_PARTS` in `src/athena/api/app.py` (static HTML + vanilla JS, ADR-004). Decision Brief is **not** a separate route; it is a panel on the Decisions tab composed from multiple Decision APIs (`13-decision-brief-*.js`, `19b-decision-brief-intraday.js`).

**Symbol Intelligence should be a new `.nav-item` tab** (same pattern as My Portfolio), not a reuse of the disabled Reports & Analytics placeholder, and not a DarvaX-injected tab.

### 2.2 Symbol identity and search (confirmed)

| Capability | Location | Persisted? | Notes |
|---|---|---|---|
| Canonical instrument id `EXCHANGE:SYMBOL` | `instruments` table; Kite dump in `kite_provider.py` | yes | e.g. `NSE:MARKSANS` |
| Symbol master / universes | `src/athena/symbols/` (ADR-011) | `symbol_master`, `symbol_group`, `resolved_universe` | scanners resolve a universe *name* |
| Owner candidates / validate | `GET/POST /api/v1/market/candidates`, `/validate` | `owner_candidates` | Symbol 360 uses this to resolve a typed symbol |
| Saved symbols watchlist | `GET/POST/DELETE /api/v1/saved-symbols` | `saved_symbols` | UX-9b; not a search index |
| Portfolio symbol resolution | `src/athena/portfolio/imports.py` | holdings | NSE→BSE remap aware |

There is **no dedicated symbol-search API**. SI search should reuse candidate/instrument lookup (as Symbol 360 already does), not invent a second master.

### 2.3 Market data / D1 candles (confirmed)

| Item | Implementation |
|---|---|
| Storage | `candles` PK `(instrument_id, timeframe, ts_open)`; timeframes `1m`/`5m`/`15m`/`1d` (`Timeframe` in `domain/enums.py`) |
| Ingestion | `src/athena/data/ingestion/engine.py`; Kite maps `Timeframe.D1 → "day"` |
| PIT read | `SqliteRepository.list_candles_recent(..., as_of=)` filters `ts_open<=as_of` in SQL (ID-5E). **Market-time only.** Schema does **not** store knowledge-time / ingest timestamp per candle |
| Dashboard candle API | `GET /api/v1/market/instruments/{id}/candles` — **Literal `1m`/`5m`/`15m` only** (`market.py`). D1 is used internally (ticker, portfolio, pipeline) but is **not** a first-class chart API today |
| Chart UI | `16-decision-brief-chart.js` — persisted 5m/15m + ATR/SMA overlays from `MarketHistoryService.recent_candles`; TradePlan overlays from the Decision, not from the chart |
| Quotes | `quotes` table; live LTP via `kite_ltp.py` with a 5s process cache |
| Adjusted flag | `candles.adjusted`; corporate-action engine can adjust splits/bonuses/dividends |

### 2.4 Indicators (confirmed)

`src/athena/indicators/engine.py` + `calculations.py`, params `config/indicators.json`:

| Indicator | Status | Interpretation? |
|---|---|---|
| SMA(20) | implemented | measurement only |
| EMA(21) | implemented | measurement only |
| RSI(14) Wilder | implemented | measurement only |
| ATR(14) Wilder | implemented | measurement only |
| MACD 12/26/9 | implemented | measurement only |
| ADX(14) | implemented | measurement only |
| Volume MA(20) | implemented | measurement only |
| VWAP (session) | implemented | measurement only |
| SuperTrend | **not** in IndicatorEngine | `portfolio/daily_chart_evidence.py` `supertrend-10-3-athena-v0` |
| SMA(50) | **not** IndicatorEngine default | Regime/Portfolio Trend use `config/regime.json` `trend_ma_fast=20`, `trend_ma_slow=50` |

### 2.5 Regime / market / sector / universe (confirmed)

| Subsystem | Files | Role |
|---|---|---|
| Regime | `src/athena/regime/engine.py`, `models.py` | D1 trend (`BULL_TREND`/`BEAR_TREND`/`SIDEWAYS`), volatility, gap labels |
| Market health | `src/athena/market_health/` | categorical + F-5 score; `GET /api/v1/market/summary` |
| Sector health | `src/athena/sector_health/` | per-sector trend/breadth/momentum/volatility labels |
| Universe | `src/athena/universe/` | eligibility assessments in EvidenceBundle |
| Index intelligence | `GET /api/v1/market/index-intelligence/...` | official NSE membership snapshots |
| Opportunities RS | `opportunities_service.py` | **session quote vs sector change %** — not ID-4 RelativeStrengthEngine, not a multi-week RS rank |

Evidence aggregation (`src/athena/evidence/engine.py`) gathers **only**: `REGIME`, `MARKET_HEALTH`, `SECTOR_HEALTH`, `UNIVERSE`, `CORPORATE_ACTION`, `VALIDATION`. It does not gather news, fundamentals, DarvaX, portfolio, or Decision.

### 2.6 Scoring / confidence / risk / decision (confirmed)

| Engine | File | What it actually computes |
|---|---|---|
| ScoringEngine | `scoring/engine.py` | components: `trend`, `momentum` (**RSI points**), `market_quality`, `sector_quality`, `liquidity`, `technical_structure` (price-vs-SMA + MACD + VWAP) → composite 0–100 |
| ConfidenceEngine | `confidence/engine.py` | reliability: completeness, data freshness, indicator availability, cross-engine agreement, unknown ratio, consistency — **not attractiveness** |
| Risk | `src/athena/risk/` | evaluation vs limits |
| DecisionEngine | `decision/engine.py` | TRADE/WATCH/WAIT/NO_TRADE/… from artifacts; TRADE requires direction + TradePlan + all gates passed |
| TradePlan builder | `DecisionEngine._build_plan` | **last close ± ATR multiples** from `config` plan; `entry_low == entry_high == last_close`; **not structural S/R** |
| Persistence | `decisions`, `decision_traces`; score/confidence/risk **inside `runs.detail_json` pipeline `decision_reports[decision_id]`** (`confidence/report_lookup.py`) | `score_ref` is a string id, not a separate scores table |

Quality gates (`QualityGate` enum): DATA, EVIDENCE, RISK, EXPLAINABILITY, CONFIDENCE, MARKET.

### 2.7 Intraday / entry stack (confirmed, Decision-bound)

| Artifact | Files | Answers |
|---|---|---|
| SessionContext | `src/athena/session/` | completed-candle / canonical slot |
| IntradaySignalSet | `intraday/models.py`, `engine.py` | VWAP relation, M5/M15 trend aggregate |
| OpeningRangeEvidence | `opening_range_*.py` | OR15/OR30 measure, not failed-breakout labels |
| RelativeStrengthContext | `relative_strength_*.py` | **intraday** stock vs sector vs market session return; not RSI |
| GapContext | `gap_*.py` | prior D1 close → current D1 open; GAP_UP/DOWN/FLAT only |
| RelativeVolumeContext | `relative_volume_*.py` | cumulative same-time-of-day M5 RVOL vs 1.0 |
| EntryQualification | `entry_qualification_*.py`; table `entry_qualifications` | v0: VWAP+ AND aggregate BULLISH AND (RS support OR RVOL support). Long-biased. Bound to Decision |
| EntryActionability | `entry_actionability_*.py`; table `entry_actionabilities` | TRADE+QUALIFIED WHEN/entry/risk; VWAP-loss invalidation; **not D1 extension score** |
| Currentness | `entry_actionability_currentness.is_currently_usable` | read-time, never persisted |
| Position sizing / live supervision | ID-9 / ID-10 | Decision-bound |
| ID-11 | `GET /api/v1/decisions/{id}/intraday-intelligence` | composition of the above for **current** read; **no historical `as_of` query param** |

### 2.8 DarvaX satellite (confirmed)

| Item | Location |
|---|---|
| ADR | `docs/adr/ADR-010-darvax-satellite-module.md` — ATHENA core **never imports** DarvaX; one-way dependency; `enabled` boolean only |
| Mount | `src/athena/api/darvax_mount.py` → `/darvax` |
| Boxes | `darvax/primitives/boxes.py` `darvas_boxes()` |
| Signals | `darvax/signals/`; table `darvax_signals` |
| Screen | `darvax/screening/`; tiers ACTIONABLE/WATCH/EXIT_RELEVANT/NOT_ELIGIBLE; actions ENTER/WAIT/HOLD/EXIT/… **not a score** |
| Store | `db/darvax.db`, `DARVAX_SCHEMA_VERSION` 10 |
| APIs | `/darvax/api/signals`, `/signals/{instrument_id}`, `/screen/latest`, `/scan`, `/positions`, freshness on latest sweep |
| UI | `/darvax/` iframe tab; **Symbol 360** `darvax/api/static/symbol360.html` + `symbol360.js` |
| Label | every payload `EXPERIMENTAL_UNVALIDATED` |
| Isolation | DarvaX must not contribute to ScoringEngine/DecisionEngine/TradePlan (ADR-010). SI must not smuggle DarvaX levels into ATHENA Decision |

### 2.9 Portfolio (confirmed)

Authoritative holdings path is **My Portfolio**, not frozen-domain `Position`/`Portfolio` and not `owner_positions` (legacy owner-entered fills).

| Item | Location |
|---|---|
| Holdings | `portfolio_holdings` |
| Sync / snapshots | `portfolio_sync_runs`, `portfolio_analysis_snapshots` |
| Interpreter | `portfolio/interpretation.py` `portfolio-interpretation-v4` — Status / Next Action / Conviction / Trend / Setup |
| Conviction | `confidence_adapter.py` — Decision Confidence HIGH/MEDIUM/LOW only |
| D1 Trend | `trend_adapter.py` — SMA20/50 of the **holding's** D1 |
| Setup | `setup_adapter.py` — OR15/OR30 L1 |
| Daily Review | `daily_review.py` `portfolio-daily-review-v0` — HOLD_STRONG / HOLD / REVIEW_HOLD_TIGHT (holdings context) |
| D1 evidence | `daily_chart_evidence.py` SuperTrend/RSI/volume/ATH |
| Structural review | `structural_review.py` `portfolio-structural-review-v1` — Support 1, Major Support, Review Trigger, Targets 1–3, EXIT_RISK |
| APIs | `GET /api/v1/my-portfolio/snapshot`, holdings, sync, timeline, notes, exports |
| Currentness | `MyPortfolioService._snapshot_currentness` — CURRENT / STALE_HOLDINGS_CHANGED / UNKNOWN vs holdings digest |

**Daily Review and Structural Review are holdings-oriented.** Their D1 primitives can likely run on any symbol's candles; their *status vocabulary* (HOLD_STRONG, EXIT_RISK as holding invalidation) is not a fresh-entry SI vocabulary. Do not present Daily Review as SI "Entry Quality."

### 2.10 Corporate actions / news / fundamentals (confirmed)

| Claim in docs | Code reality |
|---|---|
| `EvidenceCategory.NEWS` and `AI` in `domain/enums.py` | Frozen enum. **No engine instantiates NEWS or AI evidence.** Workflow methodology explicitly says this (`docs/ATHENA-WORKFLOW-METHODOLOGY.md`) |
| Decision context "news" | `get_decision_context`: **"No news ingestion, no generated rationale."** External links are owner-curated `config` file |
| `corporate_actions` table | SPLIT / BONUS / DIVIDEND / RENAME for **price adjustment** (`data/corporate_actions/models.py`) |
| NSE filings URL | `nse_corporate_actions_provider.py` `FILINGS_URL` — used for **corporate-action / EMR survivor-cohort** coverage, not company announcement feed |
| Quarterly revenue/EBITDA/PAT | **no table, no DTO, no provider field, no tests** |
| LLM | Explainability engines: **"NO LLM generation"** |

### 2.11 Freshness / session (confirmed, several independent clocks)

| Clock | Owner | Status vocabulary |
|---|---|---|
| Advisory / market snapshot | `AdvisoryFreshnessService` `GET /api/v1/dashboard/advisory-freshness` | CURRENT / AGING / STALE / UNAVAILABLE |
| Candle series | `MarketHistoryService.recent_candles` | FRESH / STALE / NO_DATA vs threshold minutes |
| TradePlan window | `GET /api/v1/decisions/{id}/plan-freshness` | arithmetic on persisted `valid_from`/`valid_until` |
| EntryActionability | `is_currently_usable` | CURRENT vs SUPERSEDED/etc.; +10m evidence-age band (ID-7B.2) |
| DarvaX sweep | `DarvaxSweepFreshnessClassifier` | CURRENT / STALE / UNAVAILABLE vs expected NSE session |
| Portfolio snapshot | holdings digest match | CURRENT / STALE_HOLDINGS_CHANGED / UNKNOWN |
| Portfolio price session | `price_is_current` in interpretation evidence | expected D1 session |
| Calendar | `CalendarEngine` | sole session authority |

There is **no existing multi-source SI freshness aggregator**. Patterns exist to copy, not a single function to call.

### 2.12 Existing "unified workspace" (do not confuse)

`src/athena/workspace/engine.py` `UnifiedIntelligenceWorkspace` is a Phase-6 catalog of reports/dashboard/explainability/timeline/monitoring/export snapshots. It is **not** a symbol investigation cockpit. `GET /api/v1/workspace/snapshots` is that catalog. SI must not overload this name/module without a deliberate rename/boundary.

### 2.13 EMR (research satellite)

Explosive Move Radar is an isolated research/live-shadow lane (ADR-012/014). It is **not** authoritative SI methodology. Optional later cross-link only, never a hidden SI score input.

---

## 3. Desired Report-to-Evidence Matrix

Legend: **Reuse** = consume as-is; **Adapt** = same engine/data, new presentation or a thin adapter; **New** = missing data or methodology; **Unsafe** = would contradict an owner-frozen engine.

| Desired output | Existing source | Owning subsystem | Reuse/Adapt/New | Freshness | PIT | Mapping confidence | Notes / gaps |
|---|---|---|---|---|---|---|---|
| Current price / change | `quotes` + live LTP; D1 close | Market | Reuse | quote vs D1 session | market-time candles likely; live quote is current-state | HIGH | Distinguish last D1 close vs live LTP |
| Primary trend | Regime D1 labels; Portfolio Trend SMA20/50; SuperTrend direction | Regime **owns market**; Portfolio Trend is holding adapter of same SMA rule | Reuse (present both if they differ) | cycle `as_of` / accepted D1 session | replay via `as_of` candles | HIGH | Do not invent a third trend engine |
| Structural setup (consolidation / breakout / extension) | No SI contract. Partial: DarvaX box/tier; structural zones; ATH evidence; SuperTrend | Split | Adapt later / New methodology | mixed | mixed | MEDIUM | **Methodology gap.** PS-P10C.1 originally NO-GO'd naive S/R; V2 engine exists for holdings |
| Breakout already occurred? | DarvaX `BREAKOUT` / screen `ACTIONABLE`; ATH `latest_high_exceeds_prior_history`; TradePlan does **not** say this | DarvaX (box breakout); Portfolio ATH (history high) | Reuse with lineage | DarvaX sweep vs D1 | DarvaX `as_of`; D1 `as_of` | MEDIUM | Two different "breakout" meanings — must not merge |
| Consolidating near highs? | Not implemented as a state | — | New methodology | — | derivable from D1 if frozen | LOW | Example narrative in the brief is **not** currently a typed conclusion |
| Extended? | ID-7B.2 froze `EXTENSION_GATE_NOT_SUPPORTED` for **intraday** EntryActionability. No D1 extension classification | — | New (D1) / Unsafe (reusing rejected ID-7 extension gate) | — | ATR/distance derivable | LOW | Do not reverse ID-7B.2 |
| Support / resistance | PortfolioStructuralReviewEngine zones; DarvaX box_top/bottom; TradePlan stop/targets (ATR) | Portfolio V2 / DarvaX / DecisionEngine | Reuse with **lineage tags** | D1 session / sweep / plan validity | structural engine claims PIT-safe candidate generation | HIGH for existence; MEDIUM for SI use on non-held symbols | Never present ATR TradePlan stop as "structural support" |
| Darvas box / trigger / invalidation | `darvas_boxes`, `DarvaxSignal.trigger_price`, stop JSON, screen action | DarvaX | Reuse only | sweep freshness | signal `as_of` + methodology_digest | HIGH | Experimental label must remain visible |
| Logical targets | Decision TradePlan.targets (ATR); Portfolio structural T1–T3; DarvaX does not own a target ladder as ATHENA Decision | Decision / Portfolio V2 | Reuse with lineage | plan freshness / D1 | as persisted | HIGH | Do not blend into one "target path" without tagging |
| Momentum quality 0–10 | Scoring `momentum` is RSI-only component; RS/sector/trend are **other** score components | ScoringEngine | **Unsafe to rebrand**; New SI concept | cycle | run report | HIGH that RSI-momentum ≠ desired MQ | See §7 |
| Entry quality 0–10 | EntryQualification (intraday readiness); EntryActionability (WHEN); TradePlan location vs last close; Portfolio Next Action (held) | ID-6/7 / Decision / Portfolio | Adapt evidence, **New score forbidden in P0** | several clocks | Decision-bound rows | HIGH overlap risk | See §8 |
| Conviction | ConfidenceLevel HIGH/MEDIUM/LOW via Decision report + Portfolio conviction adapter | Confidence / Portfolio | Reuse | cycle / snapshot | report in run JSON | HIGH | Confidence ≠ attractiveness |
| ATHENA Decision | `decisions` + depth + context + brief JS | Decision | Reuse components/APIs | latest per instrument + plan freshness | historical decisions exist; "current" is latest ts | HIGH | Latest ≠ owner-journal ACCEPTED |
| DarvaX report | screen row + latest signal | DarvaX | Reuse (frontend/API); not ATHENA import | sweep classifier | stored sweeps | HIGH | ADR-010 seam |
| Portfolio context | snapshot row for instrument_id | My Portfolio | Reuse | snapshot currentness | snapshots history yes; live holdings are current | HIGH | Null = not held → fresh-entry context |
| Quarterly fundamentals | none | — | New data + methodology | n/a | n/a | HIGH missing | External provider required later |
| Filings / news / catalysts | none (CA adjustments ≠ news) | — | New data + taxonomy | n/a | n/a | HIGH missing | Do not generic-sentiment scrape |
| Sector / RS | SectorHealthResult; ID-4 RS (intraday); opportunities RS (quote) | Sector / Intraday / Opportunities | Reuse separately labeled | cycle / session | ID-4 is session PIT | HIGH | Three different RS notions |
| Next action | Decision type; DarvaX action; Portfolio Next Action; EQ/EA | four owners | Compose + show divergence | mixed | mixed | HIGH | Never collapse to one silent winner |
| Complete Review narrative | no AI layer | — | New interpretation **over contract only** | depends | depends | HIGH | Facts must be pre-computed |
| Screenshot parsing | no OCR/CV in repo | — | Non-goal | — | — | HIGH | Optional later visual check only |

---

## 4. ATHENA Decision Integration Analysis

### 4.1 End-to-end (confirmed)

```
OwnerValidationPipeline (ops/owner_validation.py)
  per-instrument DAG: session → candles/indicators → regime/MH/sector
    → evidence → scoring → confidence → risk → DecisionEngine.decide
    → persist Decision + DecisionTrace
    → entry_qualification → entry_actionability → sizing → supervision
```

Domain: `src/athena/domain/decision.py` — `Decision`, `TradePlan`, `GateResult`, `DecisionTrace`.

Engine: `src/athena/decision/engine.py`.

Persistence:

- `decisions` (immutable append-only; `list_latest_decisions_by_instrument` = newest `ts` per `instrument_id`)
- `decision_traces`
- `decision_journal` (`UserAction` ACCEPTED/REJECTED/IGNORED) — **owner response, not "accepted run"**
- `trade_outcomes`
- analytical depth: `runs.detail_json` → `pipeline.decision_reports[decision_id]` (`decision_report_from_pipeline`)

### 4.2 API surface (confirmed)

Prefix `/api/v1/decisions` (`routers/decisions.py`):

- `GET /` list (filter includes `instrument_id`)
- `GET /latest` one current Decision per instrument
- `GET /{id}` DecisionDTO (gates, plan)
- `GET /{id}/depth` eligibility + score + confidence + risk (**render persisted, no recompute**)
- `GET /{id}/context` calendar + regime + market health + curated links
- `GET /{id}/counterfactual` distance to TRADE from persisted numbers
- `GET /{id}/plan-freshness`
- `GET /{id}/intraday-intelligence` (ID-11, current-only)
- `GET /{id}/analogs`, journal, outcome, trace
- `GET /near-misses`, `/track-record`

Brief export composition: `api/v1/services/decision_brief.py` `DecisionBriefSnapshot` (Decision+Depth+Context; **"Adds no analysis, no recomputation, no news"**). Dashboard export via `exports_service.py`.

### 4.3 Frontend (confirmed)

Decisions tab + in-panel brief:

- `12-decisions-list.js`
- `13-decision-brief-core.js`
- `14-decision-brief-analysis.js`
- `15-decision-brief-context.js`
- `16-decision-brief-chart.js`
- `18-decision-brief-trace.js`
- `19-decision-brief-history.js`
- `19b-decision-brief-intraday.js`

### 4.4 Recommended SI reuse model

**Shared DTO/API + shared report components, not a fork.**

1. SI backend composition **reads** `list_latest_decisions` / `GET /decisions?instrument_id=` and attaches `decision_id`.
2. SI Decision **segment** reuses the existing brief renderers (extract shared functions rather than copy HTML) **or** deep-links/embeds the same panel with `instrument_id` selected.
3. SI must pass through `decision_type`, gates, plan, score, confidence **verbatim**.
4. SI must **not** recompute DecisionEngine for the workspace "Refresh" unless the owner explicitly triggers an existing validation/scan path (and even then, SI should wait on persisted output).
5. Freshness: Decision `ts` + run `finished_ts` + `plan-freshness` + (if shown) EQ/EA currentness. Label **CURRENT DECISION** = latest persisted cycle row, not journal ACCEPTED unless the owner later asks for that semantics.

**Do not** introduce `SI_DECISION` or reinterpret TRADE as WAIT inside the Decision object. Divergence lives in an SI overlay (§12–13, §18).

---

## 5. DarvaX Integration Analysis

### 5.1 Ownership

DarvaX is an **opt-in satellite**. Isolation is both product (disable without affecting ATHENA) and methodology (unvalidated). ADR-010: core never imports `athena.darvax`; scoring component `darvax_structure` was **explicitly rejected**.

### 5.2 What SI may consume

| Artifact | API / store | SI may |
|---|---|---|
| Latest signal | `GET /darvax/api/signals/{instrument_id}` | present explanation, box_top/bottom, trigger, stop, evidence as **data** |
| Latest screen row | `GET /darvax/api/screen/latest` (filter client-side by instrument) | present tier, action, distance_to_breakout_pct, breakout_reference |
| Sweep freshness | classifier payload on latest screen | show CURRENT/STALE/UNAVAILABLE |
| Boxes geometry | primitives; also encoded on signal | lineage `DARVAX` |
| Experimental label | every envelope | **must remain visible** |

### 5.3 What SI must not do

- Reimplement `darvas_boxes` / signal engine / screener under SI names
- Feed DarvaX into ScoringEngine or DecisionEngine
- Drop `EXPERIMENTAL_UNVALIDATED`
- Treat DarvaX ENTER as ATHENA TRADE
- Import `athena.darvax` from ATHENA core without an ADR (current law)

### 5.4 Existing Symbol 360 (important precedent)

`src/athena/darvax/api/static/symbol360.js` already does a **DarvaX-owned** composition:

- ATHENA `GET /api/v1/decisions?instrument_id=`
- DarvaX screen row + signal
- saved-symbols
- journal/outcome history
- optional candidate validate to resolve the typed name

This is the closest shipped UX to SI, but:

- it lives **inside DarvaX**, not as an ATHENA top-level workspace
- it has no D1 structure cockpit, no portfolio Daily Review, no fundamentals/news, no MQ/EQ, no Complete Review
- ATHENA→DarvaX is the forbidden direction in core Python; Symbol 360 is allowed because **DarvaX JS reads ATHENA HTTP**

### 5.5 Recommended reuse model

**Preferred (no ADR):** SI DarvaX segment is presentation-only:

- iframe of Symbol 360 / DarvaX detail for that instrument (same pattern as `tab.js`), **or**
- SI frontend JS fetches `/darvax/api/...` the way Symbol 360 fetches `/api/v1/...` (HTTP, not Python import)

**Requires ADR:** an ATHENA-core SI service that reads `db/darvax.db` or imports `athena.darvax`. That would weaken "delete DarvaX and ATHENA is unchanged" unless the adapter is optional, fail-open, and lives behind the same `enabled` seam.

P0 recommendation: **do not ADR in P0**. Treat HTTP/iframe composition as the default; owner may later authorize a narrow read port.

---

## 6. Technical / Structure Capability Analysis

Classification requested: (1) implemented reusable (2) partial/adaptable (3) derivable (4) missing (5) methodologically unsafe / not yet supportable.

| Desired item | Class | Evidence |
|---|---|---|
| OHLCV | 1 | `candles`; D1 used throughout pipeline/portfolio |
| SMA/EMA | 1 | IndicatorEngine; SMA50 via regime periods / `sma()` |
| RSI | 1 | IndicatorEngine + `RsiReviewEvidence` |
| SuperTrend | 1 (portfolio evidence) | `supertrend-10-3-athena-v0`; **not** TradingView-claimed equivalent (PS-P10B.1) |
| ATR | 1 | IndicatorEngine; TradePlan sizing |
| Relative volume | 1 (intraday) / 4 (D1 expansion) | ID-5D cumulative M5 RVOL; D1 volume vs MA exists as measurement (`VolumeReviewEvidence`) without expansion/contraction **state** |
| Volume expansion/contraction | 3–4 | D1 volume/MA measurable; no frozen expansion state |
| HH/HL or LH/LL | 2 | Structural review uses fractal swings (`SWING_HALF_WINDOW=3`) internally; **not** an owner-facing HH/HL series |
| Breakout | 2 | DarvaX box breakout; ATH new-high flags; **not** a generic "range breakout" engine |
| Failed breakout | 4–5 | OpeningRange explicitly **forbids** FAILED labels; DarvaX EXIT_RELEVANT is box-floor, not "failed breakout" |
| Retest | 2 | DarvaX `BREAKOUT_RETEST` / `ENTER_ON_RETEST` only |
| Pullback | 4 | no typed pullback engine |
| Consolidation / high-level consolidation | 4 | desired SI example; **not implemented** |
| Compression | 4 | ATR measurable; no compression state |
| Base formation | 4 | DarvaX box is related but not "base" methodology |
| Price discovery | 2 | ATH / no-overhead-resistance (`NO_OVERHEAD_RESISTANCE`) in structural review |
| Extension | 5 for ID-7 reuse; 4 for D1 | ID-7B.2 `EXTENSION_GATE_NOT_SUPPORTED` |
| ATH / 52W proximity | 2 | `AthRollingHighEvidence` is **available-history** high, not guaranteed official 52-week; `adjusted_history` flag exists |
| Support/resistance | 2 | Portfolio V2 zones (holdings); DarvaX box; ATR plan ≠ S/R |
| Structural ranges | 2 | `StructuralZone` lower/upper |
| Darvas-style boxes | 1 | DarvaX only |
| Trend persistence | 2 | Regime labels over time exist as sequential Decisions; no dedicated persistence metric |
| Candle quality | 4 | no candle-quality engine |
| Gap behavior | 2 | ID-5C + Regime gap labels; **no** fill/hold/rejection |

**D1 chart API gap (implementation, not methodology):** dashboard `candles` route omits `1d`. SI Technical segment will need a D1 series endpoint or an approved extension of `MarketHistoryService` — that is SI-Pn API work, not a new indicator.

**Unsafe to guess in later phases without freeze:** support/resistance selection was already proven noisy (PS-P10C.1 NO-GO), then a **separate** significance-selection engine was frozen as `portfolio-structural-review-v1`. SI must reuse that engine or run a new bounded freeze — not a third mechanical pivot list.

---

## 7. Momentum Quality Discovery

**P0 does not define a formula.**

### 7.1 Available signals (already scored or labeled)

| Signal | Where | Overlap risk |
|---|---|---|
| RSI-based `momentum` component | ScoringEngine._momentum | **Direct collision** if SI "Momentum Quality" is numeric |
| `trend` component | ScoringEngine from regime + confluence | High if MQ includes "primary trend" |
| `sector_quality` | ScoringEngine | High if MQ includes sector strength |
| `technical_structure` | SMA/MACD/VWAP | High if MQ includes "structural cleanliness" |
| Composite score | ScoringEngine | **Do not rebrand as MQ** |
| ID-4 RS OUTPERFORMING | EQ input; not a score | Medium — different horizon (intraday) |
| SectorHealth momentum labels | sector_health | Medium |
| SuperTrend direction / ATH proximity | portfolio daily evidence | Medium |
| DarvaX topmost-box / breakout | DarvaX | Medium; experimental; isolation |
| Earnings acceleration | **missing** | cannot include |

### 7.2 What ATHENA "momentum" actually is

Confirmed in `scoring/engine.py`: the component named `momentum` is **RSI point-map only**. It is not relative strength, not earnings, not breakout quality.

### 7.3 Recommendation (no freeze)

Until a methodology milestone:

- Treat **Momentum Quality as a future SI interpreter**, not a ScoringEngine fork.
- Near-term SI should **display existing named evidence** (regime trend, RSI value, SuperTrend, sector label, ID-4 RS, DarvaX tier) as a cockpit, **not** a 9.4/10.
- If a numeric MQ is later wanted, it must be a **new named methodology version** with explicit non-overlap vs ScoringEngine weights, or it must be a **classified state** (e.g. STRONG / MIXED / WEAK) built from already-categorical labels only.
- **Warn:** composing RSI + trend + RS + sector + breakout into MQ **double-counts** the same factors Decision already used to say TRADE/WATCH.

**AI interpretation over evidence** is acceptable later **only** to explain those named facts ("RSI cooled from A to B" if A and B are computed). It must not invent 9.4.

---

## 8. Entry Quality Discovery

**P0 does not define a formula.** Conceptual split vs Momentum Quality is mandatory.

### 8.1 What already answers "can I buy now?" (different questions)

| Artifact | Question it actually answers | Horizon |
|---|---|---|
| DecisionType TRADE | "Does the daily/structural pipeline authorize a trade plan?" | cycle; ATR plan from last close |
| TradePlan | "Where is the analytical entry/stop/target from last close ± ATR?" | `validity_hours` |
| EntryQualification QUALIFIED | "Intraday v0 readiness: VWAP+ AND bullish M5/M15 AND (RS or RVOL)?" | checkpoint; long-only |
| EntryActionability ACTIONABLE | "Is the TRADE+QUALIFIED plan currently usable / invalidation geometry?" | +10m currentness |
| Portfolio Next Action ADD/HOLD/EXIT | "What should a **holder** do?" | snapshot + coherent Decision |
| DarvaX ENTER / WAIT / ENTER_ON_RETEST | "DAR-CARD box state" | daily sweep |
| Daily Review HOLD_* | "Chart health for a **holding**" | D1 SuperTrend-led |

**None of these is "D1 location quality: extended vs coiled vs at trigger."** That is the SI Entry Quality hole.

### 8.2 Reusable evidence vs new evidence

Reusable without a new engine:

- distance to TradePlan entry/stop/targets (plan still valid?)
- distance to DarvaX box_top / trigger / floor (lineage DarvaX)
- distance to Portfolio Support 1 / Major Support / Review Trigger (if SI is allowed to run structural review on non-held symbols)
- ATR as a volatility scale (measurement)
- SuperTrend side and latest close
- EQ/EA states as **intraday** entry context, clearly labeled

New (methodology milestone, not P0):

- "position inside range", "extension from trend/support", "pullback quality", "reward/risk of a fresh buy at last close" as SI scores

### 8.3 Contradiction risks

- Decision TRADE + price now far above TradePlan entry (plan `entry_low==entry_high==last_close` **at decision time**; a later D1 close is a **different instant**) — legitimate divergence
- EQ NOT_YET vs DarvaX ENTER (intraday vs daily box)
- Portfolio HOLD vs SI fresh-entry WAIT
- ID-7B.2: more **intraday** extension associated with *better* outcomes — do not encode "extended = bad entry" using that gate

**Recommendation:** SI Entry Quality near-term = **labeled location evidence + existing artifacts**, not a parallel entry engine. Numeric 6.5/10 deferred. Never override DecisionEngine.

---

## 9. Fundamentals / Earnings Data Discovery

**Finding: ATHENA has no usable persisted fundamental time series.**

Searched: schema tables, providers, DTOs, tests, config. No revenue, EBITDA, PAT, margins, ROE/ROCE, debt, cash, valuation, guidance, order book, or segment fields.

Corporate actions are **capital-structure / cash dividend adjustments**, not earnings.

DarvaX source deck screening checklist mentions "superb quarterly numbers" as a **human** filter; the implemented screener does **not** ingest fundamentals (eligibility is box geometry / DAR-CARD mapping).

### 9.1 What would be required later (not in P0)

- A new provider (Kite does not currently appear to be used for financial statements in this repo)
- Point-in-time versioning: announcement date vs period end vs restatement vintage
- Explicit UNKNOWN when a quarter is missing
- Replay: as-of date must exclude later-reported quarters and later restatements

**PIT concern is first-class:** using "latest Yahoo/NSE revised annual" as if it were known on a historical date is not replay-safe.

**Operating leverage interpretation** (Revenue +35% / EBITDA +113% / PAT +174%) is a **methodology** step after numbers exist. Do not prompt an LLM to infer leverage from prose.

---

## 10. News / Filing / Catalyst Discovery

**Finding: no news/filing/catalyst ingestion pipeline for SI.**

| Possible confusion | Reality |
|---|---|
| `EvidenceCategory.NEWS` | unused frozen enum |
| Decision context links | owner-curated URLs, not ingested events |
| NSE corporate filings URL in CA provider | corporate **actions** (split/bonus/div/rename) / EMR coverage |
| EMR corporate_action_coverage | survivor cohort / replay hygiene, not catalyst cards |
| Explainability engine | no LLM, no news synthesis |

Desired event fields (source, timestamps, category, materiality, polarity, thesis impact, new-vs-known) are **greenfield**. Do not build generic sentiment because text could be scraped.

PIT: publication timestamp ≠ event date; revisions and deletions need versioning. Unknown until a source is chosen.

---

## 11. Portfolio Context Integration

**Reuse My Portfolio as the only holdings authority.**

If held (match `instrument_id` or same tradingsymbol after NSE→BSE remap, as snapshot matching already does in `my_portfolio_service.py`):

- quantity, avg price, current value, P&L from latest **completed** snapshot
- portfolio weight is **not** a persisted snapshot field; `current_value` and snapshot `total_current_value` exist (`api/v1/dtos/portfolio.py`). A display share may be exact arithmetic over those two, not a new weighting methodology
- Status, Conviction, Trend, Setup, Daily Review, Structural Review, Next Action, guidance
- `snapshot_currentness` + price session currentness
- owner notes (`portfolio_holding_notes`) as **owner-authored**, never as ATHENA evidence

If not held:

- SI shows `portfolio_context = NOT_HELD` (or equivalent null)
- skip HOLD_* Daily Review as if it were a buy rating
- "fresh-entry context" uses Decision / DarvaX / D1 evidence only

**Do not** create `si_holdings`. **Do not** call Portfolio interpreter to mint a Status for a non-holding.

API: `GET /api/v1/my-portfolio/snapshot` (and holdings GET). SI composition looks up one row.

---

## 12. Freshness / Currentness Model

### 12.1 Principle

The SI envelope is **as current as its weakest claimed section**. Never stamp COMPLETE/CURRENT on the whole report if Decision, D1, or (when shown as factual) DarvaX/portfolio/fundamentals/news is stale or missing.

### 12.2 Proposed source-level model (conceptual, not frozen enum)

Each section carries:

- `source_id` (e.g. `ATHENA_DECISION`, `D1_CANDLES`, `DARVAX_SWEEP`, `PORTFOLIO_SNAPSHOT`, `FUNDAMENTALS`, `NEWS`)
- `as_of` / `data_through` / `observed_at` as the **source already defines them**
- `status` reused from that source's classifier where one exists
- `null_reason` when absent (`NO_DECISION`, `DARVAX_DISABLED`, `NOT_HELD`, `FUNDAMENTALS_NOT_INGESTED`, …)

Overall rollup (suggested, not frozen):

- `READY` — required SI-P1 sections present and current (define required set in SI-P1: at least D1 identity + Decision-or-explicit-none + freshness block)
- `PARTIAL` — some sections current, some missing/stale; UI shows per-section chips
- `STALE` — required market/Decision evidence older than its own classifier
- `UNAVAILABLE` — symbol unresolved or no candles

Do **not** average clocks. A current Decision plus stale DarvaX is PARTIAL, not CURRENT.

### 12.3 Horizon cheat sheet

| Source | Horizon |
|---|---|
| D1 structure / SuperTrend / ATH | last completed D1 session (`list_candles_recent` + calendar) |
| Live price | LTP / quote age |
| ATHENA Decision | latest decision `ts` for instrument (cycle) |
| TradePlan | `valid_until` vs now |
| EQ / EA | evidence_as_of + `is_currently_usable` |
| DarvaX | latest authoritative sweep vs expected session |
| Portfolio | last SUCCESS snapshot + holdings digest |
| Fundamentals (future) | last published quarter known as of `as_of` |
| News (future) | last ingest check vs last event time — two timestamps |

Reuse `CalendarEngine` for "expected D1 session." Reuse existing classifiers; SI wraps them.

---

## 13. Point-in-Time / Historical Replay Assessment

Question: "What would SI have said on DATE using only information available then?"

| Source | Classification | Why |
|---|---|---|
| D1/M5/M15 candles | **likely PIT-safe with existing timestamps** (market-time) | `as_of` SQL cutoff. **Not** knowledge-time: a late backfill dated `ts_open<=DATE` would still appear. Documented in `list_candles_recent` docstring |
| Quotes / LTP | **not PIT-safe** as live; quotes table is timestamped but not a full history contract | use D1 close for replay |
| Decisions + traces | **PIT-safe now** if SI selects `decision.ts <= as_of` (and coherent run) | "current Decision" helper is latest-only — replay needs a dated query |
| Score/confidence/risk | **likely PIT-safe** via that Decision's `run_id` → `runs.detail_json` `decision_reports` | `owner_validation.py` documents a **fixed** historical bug where the wrong `run_id` caused `detail_json` to look overwritten across validations. Current path uses the orchestrator's `run_id`. Replay must still bind the historical Decision to **its** run, not "latest run" |
| Indicators | **PIT-safe** if recomputed from PIT candles with injected `as_of` | IndicatorEngine is pure |
| SuperTrend / structural review / daily evidence | **likely PIT-safe** (engines take candle sequences; V2 claims no lookahead on swings) | must pass PIT-bounded candles; do not use "latest snapshot" for historical SI |
| Regime/MH/sector | **likely PIT-safe** if reconstructed from dated candles/index members | live pipeline stores in run reports; index constituents are dated snapshots (`data/index_constituents/<effective-date>/`) |
| EQ / EA rows | **PIT-safe** as historical observations | `as_of` on row; currentness is **not** a historical fact |
| ID-11 DTO | **not PIT-safe** | current-only, no `as_of` |
| DarvaX signals/sweeps | **likely PIT-safe** if SI uses sweep `as_of`/`started_at` ≤ DATE and that sweep's rows | `latest_signal` / `latest_authoritative_sweep` are current-state helpers |
| Portfolio holdings | **requires snapshot history** | `portfolio_analysis_snapshots` exist; live `portfolio_holdings` is current. Replay = snapshot whose `as_of` ≤ DATE |
| Corporate actions | **likely PIT-safe by ex_date**; **unknown** for restatement/knowledge-time | no fetched_at on `corporate_actions` table (unlike `institutional_flows.fetched_at`) |
| Fundamentals | **not PIT-safe** (absent); future **requires versioning** | restatements |
| News | **not PIT-safe** (absent); future **requires versioning** | |
| AI narrative | **not PIT-safe** unless regenerated from frozen contract + model/prompt version | persist the contract, not just prose |

**Replay-readiness of SI as a product:** not ready. Individual market-time candle + Decision history is the strongest core. Knowledge-time gaps (candle ingest time, CA fetch time, run detail overwrite) must be audited in a later replay milestone before claiming historical SI.

---

## 14. Evidence / Provenance Architecture

### 14.1 Existing patterns to copy (not reinvent)

- ADR-005: explanations **persisted as data**; UI renders, does not reconstruct
- `EvidenceItem`: source, kind, reference_id, ts, explanation, payload
- IndicatorResult.evidence formula/inputs
- DecisionTrace stages
- DarvaX signal `evidence[]` + `methodology_digest`
- Portfolio reason codes + methodology_version fields
- EQ/EA reason codes + evidence refs
- `missing_sources` on EvidenceBundle; UNKNOWN statuses everywhere

### 14.2 Proposed SI audit record (conceptual)

For each SI **conclusion** (future interpreters) and each **displayed fact**:

- `conclusion_id` / `fact_id`
- `methodology_version` or `SOURCE_PASSTHROUGH`
- `evidence[]` with `{source, reference, as_of, value, null_reason}`
- `data_cutoff`
- `unavailable_evidence[]`
- `freshness_status` of each source
- `accepted_session` / `run_id` / `sweep_id` / `snapshot_id` as applicable

Example (only once a consolidation interpreter exists):

```
Conclusion: HIGH_LEVEL_CONSOLIDATION
Evidence:
  - D1 sessions_in_range = … (method v…)
  - pct_from_high = … (ATH evidence)
  - rsi_from, rsi_to = … (computed series, not LLM)
  - no_close_below = … (named support lineage PORTFOLIO_STRUCTURAL or DARVAX_BOX)
  - volume vs MA = … (VolumeReviewEvidence)
  - D1 SuperTrend = BULLISH
Null: fundamentals not ingested
```

Until that interpreter exists, the Evidence segment should still list **passthrough facts** with lineage, not empty "why."

---

## 15. AI Interpretation Boundary

ATHENA today: **no LLM in production engines.** `explainability/engine.py` and `config/models.py` state no LLM generation.

When an AI layer is added (later milestone):

**Allowed**

- Explain, compare, summarize, synthesize **from the SI contract JSON**
- Contrast ATHENA Decision vs DarvaX vs Portfolio vs SI location evidence
- Produce Complete Review prose that **quotes contract fields**
- Say "insufficient evidence" when `null_reason` is set

**Forbidden**

- Invent support/resistance, breakout levels, targets, technical states
- Invent financial values, news facts, holdings, Decision or DarvaX states
- Collapse MQ and Entry Quality
- Override DecisionEngine or DarvaX
- Use chart images / OCR as canonical input
- Fill gaps with "typical for this sector" knowledge
- Emit a verdict that is not a function of typed states already on the contract

**Placement:** last stage, read-only, versioned prompt + model id persisted with the narrative. Deterministic contract must be reviewable without the model.

P0/P1 should ship **without** AI so the contract can be audited.

---

## 16. Frontend / UX Composition Proposal

### 16.1 Top-level

New nav item **Symbol Intelligence** (`data-tab="symbol-intelligence"`, route `/dashboard/symbol-intelligence`), implemented as ATHENA static HTML/JS parts (new `08c-` or `22-` file in `DASHBOARD_JS_PARTS`), same `switchTab` / `loadTabData` pattern as My Portfolio.

Not: DarvaX-injected tab, not Workspace snapshots, not disabled Reports & Analytics.

### 16.2 Chrome (all sub-segments)

- Symbol search/select (candidates + instruments + saved symbols)
- Resolved `instrument_id` + name from `instruments`
- Refresh = **re-read persisted sources** (default). Triggering a Decision cycle or DarvaX scan is an owner-gated separate action, not implicit
- Freshness strip: per-source chips (Decision, D1, DarvaX, Portfolio, …)
- Divergence chip when Decision vs DarvaX vs SI location evidence disagree (informational taxonomy, not frozen)

### 16.3 Sub-tabs (recommended, not frozen)

Keep the owner's list; map to reuse:

| Segment | Contents | Reuse |
|---|---|---|
| Overview | cockpit of **already-typed** fields + explicit TBD/null for MQ/EQ scores | compose DTOs |
| Complete Review | later AI; P1 can be a structured fact sheet | contract dump |
| ATHENA Decision | existing brief | `13–19b` components or embed |
| DarvaX | iframe Symbol 360 / screen+signal | `tab.js` pattern; HTTP |
| Technical / Structure | D1 chart (needs D1 API), SuperTrend/RSI/volume/ATH, structural zones **if authorized**, DarvaX box overlay **labeled experimental** | chart JS + portfolio evidence functions |
| Fundamentals | Unavailable empty state until ingestion | honest null |
| News & Catalysts | Unavailable empty state | honest null |
| Evidence / Audit | lineage table | ADR-005 style |

Portfolio context is an Overview module **and** a Decision/Daily-Review cross-link, not a ninth tab unless the owner prefers it.

### 16.4 Component reuse (do not duplicate)

- Decision brief modules
- `16-decision-brief-chart.js` (extend timeframe list only with a real D1 API)
- My Portfolio detail overlay fields for holdings
- DarvaX iframe / Symbol 360
- Advisory freshness presentation patterns
- Saved-symbols toggle (Symbol 360 already has this)

---

## 17. Backend Contract Proposal (conceptual DTO only)

No implementation. Illustrative shape:

```
SymbolIntelligenceBundle
  identity: { instrument_id, symbol, name, exchange }
  as_of: datetime                    # SI read time
  overall_freshness: { status, sections[] }
  sources: {
    decision: DecisionRef | null     # decision_id, type, ts, run_id, plan_freshness
    darvax: DarvaxRef | null         # sweep_id, signal_id, tier, action, experimental=true
    portfolio: PortfolioRef | null   # snapshot_id, held, qty, pnl, interpretation_version
    d1: D1EvidenceRef | null         # last session, candle count, supertrend, rsi, volume, ath
    regime: ...
    scoring: ...                     # passthrough from decision_reports, not new scores
    entry_intraday: { eq, ea, currentness } | null
  }
  location_evidence: {               # measurements only in P1
    last_close, atr, pct_from_ath_or_available_high,
    tradeplan_distances?, darvax_distances?, structural_zones?
  }
  momentum_quality: null             # until methodology freeze
  entry_quality: null
  fundamentals: { status: NOT_INGESTED }
  news: { status: NOT_INGESTED }
  divergence: [ { left, right, note } ]   # not a frozen enum
  unavailable: [ { code, detail } ]
```

Service: a **read composer** in a new `src/athena/symbol_intelligence/` (or similar) that:

- does not import DarvaX (HTTP/optional port later)
- does not call DecisionEngine
- may call **pure** D1 evidence functions if owner authorizes non-held use of `daily_chart_evidence.py` / `structural_review.py`
- never writes holdings

P1 API sketch: `GET /api/v1/symbol-intelligence/{instrument_id}` returning the bundle. Optional `as_of` **deferred** until replay milestone.

---

## 18. Gaps / Risks / Open Methodology Questions

### Implementation gaps

- No SI tab, route, DTO, or composer
- Dashboard candles API lacks D1
- No per-instrument DarvaX screen GET (must filter `/screen/latest` or use `/signals/{id}`)
- ID-11 has no historical checkpoint
- Historical Decision depth depends on the Decision's own `run_id` still holding `decision_reports` (fixed run_id bug; replay should still prove old runs retain reports)
- Decision brief JS is not a reusable web component — extraction work

### Data gaps

- Fundamentals / earnings
- Filings / news / catalysts
- Knowledge-time candle ingest
- Official 52-week high as distinct from available-history high

### Methodology gaps

- Momentum Quality vs ScoringEngine.momentum
- Entry Quality vs EQ/EA/TradePlan/Daily Review
- D1 structural states (consolidation, extension, compression, base, failed breakout)
- Whether PortfolioStructuralReviewEngine may run for non-holdings
- Operating leverage rules
- Event materiality / polarity
- Divergence taxonomy freeze
- Whether SI "Refresh" may start cycles/scans

### PIT gaps

- Knowledge-time vs market-time
- CA table without fetched_at
- Fundamentals/news absent
- Current-state helpers (`/latest`, `latest_signal`, ID-11)

### UX gaps

- Symbol 360 is DarvaX-owned and incomplete vs SI intent
- Mixing HOLD-oriented Daily Review into a fresh-entry cockpit would mislead
- Experimental DarvaX vs authoritative Decision in one Overview without hierarchy

### Open questions (do not resolve in P0)

1. Numeric MQ/EQ vs classified states vs evidence-only cockpit?
2. Authoritative structure for S/R: Portfolio V2, DarvaX box, ATR plan, or tagged union only?
3. ATHENA→DarvaX read: iframe/HTTP vs ADR read-port?
4. Fundamentals provider and PIT versioning?
5. News source and materiality methodology?
6. Extract D1 evidence modules out of `portfolio/` into a shared `daily_structure/` package?

---

## 19. Recommended Milestones

Repository evidence argues **against** starting with scoring or AI.

| ID | Objective | Why this order |
|---|---|---|
| **SI-P1** | Workspace shell + identity/search + **read-only composition bundle** of existing Decision, D1 measurements (reuse portfolio evidence **if owner allows**), Portfolio row, DarvaX via HTTP/iframe, per-source freshness, honest nulls for MQ/EQ/fundamentals/news. No new scores. No AI. No providers. | Lowest architectural risk; makes reuse claims testable in UI |
| **SI-P1.1** (if P1 blocked on DarvaX) | Owner decision on ADR-010 read seam; P1 can ship DarvaX segment as iframe-only | Isolation preserved |
| **SI-P2** | D1 Technical/Structure **presentation**: D1 candle API, SuperTrend/RSI/volume/ATH, tagged levels (TradePlan vs DarvaX vs structural), no new states | Uses frozen engines |
| **SI-P3** | Divergence / consistency overlay (display only) | After both Decision and DarvaX are on one page |
| **SI-P4** | Methodology freeze for **structural states** (consolidation/extension/etc.) with replay on real D1 — **or** explicit deferral | PS-P10C.1 shows this is easy to get wrong |
| **SI-P5** | Entry Quality methodology freeze (evidence composition, not a second EQ engine) | After structural states or using tagged distances only |
| **SI-P6** | Momentum Quality methodology freeze with anti-double-count vs ScoringEngine | After P5 so MQ≠EQ |
| **SI-P7** | Fundamentals ingestion + PIT versioning + operating-leverage rules | Data gap; expensive; canary required |
| **SI-P8** | News/filings/catalysts + materiality (not generic sentiment) | Data gap |
| **SI-P9** | AI Complete Review over frozen contract | Last |
| **SI-P10** | Historical SI replay (`as_of`) | After knowledge-time audit |

Do **not** put EMR, screenshot OCR, or a new DecisionEngine in this sequence.

If the owner wants a thinner first ship: SI-P1 without structural zones and without DarvaX (Decision + D1 chart + portfolio + nulls) is still a valid composition MVP.

---

## 20. Explicit Non-Goals / Do-Not-Duplicate List

SI must **not** recreate or silently fork:

- `DecisionEngine` / `ScoringEngine` / `ConfidenceEngine` / risk engines
- `TradePlan` ATR construction
- `EntryQualificationEngine` / `EntryActionabilityEngine` / ID-11 composition
- DarvaX `darvas_boxes`, signal engine, screener, stop ladder, positions
- My Portfolio import/reconcile/sync/holdings/interpretation/Daily Review/structural **ownership**
- RegimeEngine, MarketHealthEngine, SectorHealthEngine, UniverseEngine
- IndicatorEngine formulas (call them; don't copy-paste Wilder)
- CalendarEngine session truth
- EvidenceAggregationEngine as a second news-capable fork without actually adding sources
- `UnifiedIntelligenceWorkspace` (wrong abstraction)
- EMR research models as SI authority
- Order placement (constitution)
- LLM-first candle/news analysis
- Screenshot-canonical structure
- Generic sentiment scoring
- Parallel `si_decisions` / `si_holdings` / `si_darvas` tables of computed methodology that diverge from owners above

Consume, cite lineage, present.

---

## 21. SI-P0 Verdict

### READY WITH OWNER DECISIONS REQUIRED

Composition is feasible and aligned with ATHENA's evidence-first architecture. Implementation of a **read-only workspace** can proceed after the following **minimal** owner decisions. Methodology scores, fundamentals, news, and AI remain blocked.

### Owner decisions (minimal)

1. **DarvaX seam for an ATHENA-owned tab**  
   Default proposed: frontend HTTP and/or iframe (no core import, no ADR). Alternative: authorize a narrow ADR-010 amendment for an optional read port.  
   *Needed before* a first-class DarvaX segment inside SI. Overview can still ship with "DarvaX unavailable / open DarvaX tab."

2. **Non-held use of Portfolio D1 evidence / structural review**  
   May SI call `daily_chart_evidence.py` / `PortfolioStructuralReviewEngine` for symbols that are not holdings?  
   - Yes, as shared D1 engines (possibly later extracted from `portfolio/`)  
   - No, Technical segment is measurements + DarvaX + TradePlan only until a shared package exists  
   Daily Review HOLD_* vocabulary must **not** be applied to non-holdings regardless.

3. **SI-P1 Refresh semantics**  
   Re-read persisted artifacts only (recommended) vs also triggering OwnerValidation / DarvaX sweep / Portfolio Sync.

4. **Near-term Momentum Quality / Entry Quality**  
   Confirm P1 shows **null + named evidence**, not prototype numbers. (P0 already forbids formulas; this is a product confirmation.)

5. **Fundamentals / news**  
   Confirm they stay empty states until explicit provider+PIT milestones (recommended). Choosing a provider is **not** required to start SI-P1.

Decision 2 is the only one that changes SI-P1 engineering shape for Technical/Overview. Decision 1 changes the DarvaX segment only.

---

## Discovery questions — short answers

1. **Reusable intelligence?** Decision stack, D1 candles, indicators, regime/sector/MH, EQ/EA, DarvaX, Portfolio snapshot/review/structure, freshness classifiers, Symbol 360 as UX precedent.  
2. **Where?** See §2 file/API tables.  
3. **Ownership?** Decision / DarvaX / Portfolio / Market-data / Intraday — SI composes.  
4. **Persisted vs recomputed?** Decisions/EQ/EA/DarvaX/portfolio snapshots persisted; indicators/SuperTrend/structural often **recomputed from persisted candles**; scores in run JSON.  
5. **Freshness?** Multiple independent clocks — wrap, don't replace (§12).  
6. **Replay-safe?** Mixed; candles+decisions strongest; knowledge-time weak; fundamentals/news absent (§13).  
7. **Direct consume?** Yes for ATHENA APIs/repos; DarvaX via HTTP/iframe under current ADR.  
8. **Adapter?** Yes: SI composer + optional D1 evidence adapter for non-holdings; no engine forks.  
9. **Missing data?** Fundamentals, news/filings, D1 chart API, knowledge-time.  
10. **New methodology?** MQ, EQ, D1 structural states, operating leverage, event materiality.  
11. **New external source?** Yes for fundamentals and news (later).  
12. **Dangerous to duplicate?** Entire §20.  
13. **Reusable APIs/UI?** Decision* , my-portfolio/snapshot, market candles (extend D1), darvax/api/*, brief JS, Symbol 360, saved-symbols.  
14. **Backend contract?** §17 composition bundle.  
15. **Frontend?** New top-level tab + segments; embed/reuse; iframe DarvaX.  
16. **AI seat?** After deterministic contract; explain only.  
17. **Supportable now?** Price, trend labels, RSI/ATR/SMA/SuperTrend, Decision, EQ/EA, DarvaX box/tier, holdings context, tagged ATR/box/structural levels, freshness chips, divergence display.  
18. **Not supportable now?** MQ/EQ scores, earnings acceleration, catalysts, high-level consolidation as a typed verdict, official 52W if not in evidence, LLM Complete Review as fact.  
19. **Null behavior?** Per-source `null_reason`; overall PARTIAL; never fabricate 0 or "COMPLETE."  
20. **Milestone sequence?** §19 — composition first.

---

## Doc vs code conflicts noted

| Documentation impression | Code |
|---|---|
| `EvidenceCategory.NEWS` / `AI` as pipeline inputs | Unused; EvidenceAggregationEngine has no NEWS source |
| "Accepted run" as Decision currentness | Latest `decisions.ts` per instrument; `ACCEPTED` is journal |
| Scoring "momentum" as broad momentum quality | RSI component only |
| TradePlan as structural entry zone | `entry_low == entry_high == last_close`; stop/target ATR multiples |
| Opening-range "failed breakout" | Explicitly not in OR evidence |
| SuperTrend as IndicatorEngine | Portfolio daily-chart evidence only |
| Workspace = symbol cockpit | Phase-6 artifact catalog |
| Corporate filings = news | Adjustments / EMR CA coverage |
| Dashboard candles include D1 | API Literal excludes `1d` |

---

## Non-goals of this document

No code, schema, APIs, scores, thresholds, S/R methodology, LLM prompts, or provider integration were added. Production files were not modified.
