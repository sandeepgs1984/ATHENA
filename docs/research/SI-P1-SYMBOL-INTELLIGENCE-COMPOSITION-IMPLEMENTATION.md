# SI-P1 — Symbol Intelligence Composition Implementation

Status: SI-P1 freeze candidate after owner-requested product cleanup.
Date: 2026-09-13
Does not rewrite SI-P0. Governing discovery:
`docs/research/SI-P0-SYMBOL-INTELLIGENCE-DISCOVERY-ARCHITECTURE.md`.

## 1. Implementation summary

SI-P1 is ATHENA's universal Symbol Intelligence workspace foundation for any
valid supported NSE/BSE canonical instrument (not restricted to the active
ATHENA universe).

GET composition **re-reads** persisted sources. POST Analyze may run
**symbol-scoped D1 hydration** through existing market-data ingestion, persist
refreshed candle rows, re-read evidence, and compose latest SI. Analyze does
**not** run DecisionEngine, Portfolio Sync, or DarvaX scan.

It does **not** invent Momentum Quality / Entry Quality, ingest
fundamentals/news, or persist an SI ledger.

## 2. Files added / modified

Added:

- `src/athena/symbol_intelligence/__init__.py`
- `src/athena/symbol_intelligence/composer.py`
- `src/athena/symbol_intelligence/d1_hydrate.py`
- `src/athena/api/v1/dtos/symbol_intelligence.py`
- `src/athena/api/v1/services/symbol_intelligence_service.py`
- `src/athena/api/v1/routers/symbol_intelligence.py`
- `src/athena/api/static/js/08c-symbol-intelligence.js`
- `src/athena/api/static/css/15-symbol-intelligence.css`
- `tests/symbol_intelligence/test_si_p1_composer.py`
- `tests/api/v1/test_symbol_intelligence.py`
- `docs/research/SI-P1-SYMBOL-INTELLIGENCE-COMPOSITION-IMPLEMENTATION.md` (this file)

Modified:

- `src/athena/api/app.py` — `08c-symbol-intelligence.js` in `DASHBOARD_JS_PARTS`
- `src/athena/api/dependencies.py` — `get_symbol_intelligence_service`
- `src/athena/api/v1/router.py`
- `src/athena/api/v1/routers/market.py` — candle timeframe Literal includes `1d`
- `src/athena/api/static/index.html` — nav + pane; asset cache `9.238.0`
- `src/athena/api/static/js/03-app-shell.js` — route allowlist + load hook
- `src/athena/api/static/dashboard.css` — import SI CSS
- hosting / chart release-gate version pins
- `docs/MILESTONES.md`, `ATHENA_BRIEFING.md` §6, `IMPLEMENTATION_SUMMARY.md`

## 3. Backend contract

`GET /api/v1/symbol-intelligence/search?q=`
`GET /api/v1/symbol-intelligence/{query}` (read-only)
`POST /api/v1/symbol-intelligence/{query}` (Analyze: symbol-scoped D1 hydrate + re-read)

`query` may be `EXCHANGE:SYMBOL` or an unambiguous ticker. Ambiguous NSE/BSE
tickers return `resolved=false` with a qualify instruction.

`SymbolIntelligenceBundleDTO` contains:

- identity / `read_as_of`
- `overall_freshness` — **SI coverage** (READY / PARTIAL / STALE / UNAVAILABLE)
- per-source `sources[]` (never averaged); `D1_CANDLES` is **market data**
- `live` quote presentation: `quote_kind` LIVE | LATEST_QUOTE | UNAVAILABLE,
  `market_state` MARKET OPEN | MARKET CLOSED, combined `label`
- Decision summary (persisted Decision + optional TradePlan freshness / depth / ID-11)
- D1 evidence
- Portfolio context (`HELD` | `NOT_HELD`)
- DarvaX iframe presentation
- `momentum_quality.value = null`
- `entry_quality.value = null`
- `fundamentals.status = NOT_INGESTED`
- `news.status = NOT_INGESTED`
- `unavailable[]` codes (`UNRESOLVED_SYMBOL`, `NO_D1_DATA`, `NO_DECISION`)

No SI decisions/holdings/DarvaX tables.

## 4. Source ownership

| Surface | Owner | SI-P1 access |
|---|---|---|
| Instrument identity | symbol master / `SqliteRepository` | read |
| D1 candles | data ledger | `list_candles_recent(..., Timeframe.D1, as_of=read_as_of)` |
| RSI / SuperTrend / volume / available-history high | `DailyChartEvidenceEngine` via thin adapter | compute from persisted D1 only |
| Structural zones | `PortfolioStructuralReviewEngine` via adapter (`daily_review_status=None`) | zones only; no EXIT_RISK / HOLD guidance exposed |
| D1 trend label | `PortfolioTrendAdapter.classify_candles` | SMA20/50 trend, not ScoringEngine.momentum |
| ATHENA Decision | `DecisionsService` / decisions table | get existing Decision only |
| My Portfolio | holdings + optional latest snapshot | read; My Portfolio remains authoritative |
| DarvaX | satellite | iframe `/darvax/symbol360?embedded=1&symbol=<EXCHANGE:SYMBOL>` |
| Fundamentals / news | none | NOT_INGESTED |

ATHENA core Python SI path does **not** `import athena.darvax` and does not
read `db/darvax.db`.

## 5. UI composition

Route: `/dashboard/symbol-intelligence` (ATHENA `.nav-item`, not Reports
placeholder, not DarvaX tab injection).

Sections: Overview, Complete Review (factual sheet only), ATHENA Decision,
DarvaX, Technical / Structure, Fundamentals, News & Catalysts, Evidence / Audit.

Analyze (POST) hydrates stale/missing D1 for this symbol, then re-reads.
Header Refresh still re-runs GET composition + iframe src only.

Decision Brief is **linked** into the existing Decisions workspace
(`?decision=`), not copied as HTML.

## 6. Decision reuse

Composer loads the latest persisted Decision per instrument. It never calls
`DecisionEngine`. NO_DECISION is a first-class empty state. TRADE/WATCH/WAIT
semantics are displayed verbatim.

## 7. DarvaX boundary

Iframe-only (owner-approved option A). Label `EXPERIMENTAL_UNVALIDATED`.
ENTER is not presented as ATHENA TRADE. Disabled/unmounted → explicit
DISABLED/UNAVAILABLE. Freshness for DarvaX is `NOT_READ` when the iframe is
enabled, because ATHENA core does not read satellite artifacts.

**Identity (source-review correction):** Symbol 360 already reads `?symbol=`
and `normalizeInstrumentId` keeps a colon-qualified id (`EXCHANGE:SYMBOL`)
or prefixes `NSE:` for a bare ticker. SI therefore passes
`instrument.instrument_id` (e.g. `NSE:MARKSANS`), not the bare tradingsymbol.
A narrow Symbol 360 presentation change writes that canonical id back into
the query string after lookup instead of stripping to bare, so a reload of
the iframe cannot collapse BSE/NSE identity. Bare-symbol deep links remain
valid via the existing NSE default.

## 8. Non-held D1 reuse

Adapter runs RSI14, SuperTrend 10,3, volume MA, available-history high, D1
trend classification, and structural **zones**. Those values appear under
Technical / Structure with lineage `PORTFOLIO_D1_EVIDENCE` /
`PORTFOLIO_STRUCTURAL_REVIEW`.

The SI D1 contract **passes through** owning-engine `is_coherent` flags
(`rsi_is_coherent`, `supertrend_is_coherent`, `volume_is_coherent`,
`ath_is_coherent`, `symbol_trend_is_coherent`, `structural_is_coherent`)
and owning-engine reason codes. The composer does not recompute coherence.
Incoherent named Momentum/Entry evidence has `value=null` with
`is_coherent=false` and the original reason; structural Support 1 is not
presented as valid Entry named evidence when structural review is incoherent.

Non-held Portfolio context is **only** `NOT_HELD`. No HOLD_STRONG / HOLD /
REVIEW_HOLD_TIGHT / Next Action / Daily Review / EXIT guidance.

Available-history high is **not** labeled 52-week high.

## 9. Portfolio behavior

Held: quantity/avg/last/value/P&amp;L from holdings and, when present, the
latest snapshot row (including snapshot currentness and Portfolio-owned
interpretation fields for that holding).

Non-held: `NOT_HELD`. Missing snapshot on a holding → STALE Portfolio
freshness, not invented valuation.

## 10. Freshness vs coverage

Expected D1/Decision session uses `CalendarEngine` via
`latest_trading_day_on_or_before` on market-timezone `read_as_of.date()`.

**Market data** is `sources[D1_CANDLES].status`: CURRENT / STALE / UNAVAILABLE.
A missing Decision never marks market data stale.

**SI coverage** is `overall_freshness.status`:

| D1 | Decision | SI coverage |
|---|---|---|
| CURRENT | CURRENT | READY |
| CURRENT | UNAVAILABLE | PARTIAL (ATHENA Decision unavailable; not an SI analysis error) |
| STALE | any | STALE |
| UNAVAILABLE | any | UNAVAILABLE |

UI labels these separately (`Market data` / `SI coverage`). The JS layer
does not invent a second freshness algorithm.

DarvaX `NOT_READ` is never averaged and never used to claim COMPLETE/CURRENT.

**Quote vs completed D1.** Live/latest quote is presentation only.
RSI / SuperTrend / SMA / structure use last completed D1 only.

**Session wording.** MARKET OPEN + current quote → `LIVE · MARKET OPEN`.
MARKET CLOSED + quote → `LATEST QUOTE · MARKET CLOSED`. Never
`LIVE / CURRENT SESSION` on a closed market.

## 11. Null / unavailable behavior

Unresolved, no D1, no Decision, DarvaX disabled, MQ/EQ undefined, fundamentals
and news NOT_INGESTED all render as explicit states. No mock data.

## 12. D1 chart decision

SI-P0 noted the dashboard candle API omitted `1d`. SI-P1 adds `1d` to
`GET /api/v1/market/instruments/{id}/candles` as a small, methodology-neutral
read extension of `MarketHistoryService` / `Timeframe.D1`.

The SI UI shows latest D1 measurements and a persisted `timeframe=1d` SVG
candlestick on Technical / Structure. That chart is completed-D1 only.

## 13. Tests

- `tests/symbol_intelligence/test_si_p1_composer.py`
- `tests/api/v1/test_symbol_intelligence.py`
- dashboard hosting allowlist / asset version `9.238.0`

Covered: held + Decision + D1 + DarvaX iframe flag; non-held; NO_DECISION;
NO_D1; stale D1; DarvaX disabled; MQ/EQ null; NOT_INGESTED; write spies on
`save_decision`/`add_candles`; distinguishable lineage; calendar expected
session; `1d` accepted / `30m` still 422.

## 14. Known limitations

- DarvaX iframe requires the satellite to be mounted (`enabled` in
  `config/darvax.json`).
- Decision depth / ID-11 are best-effort reads; missing artifacts stay null.
- Structural zones reuse Portfolio V2 engine output; they remain
  Portfolio-methodology zones displayed as D1 structure, not a new SI
  structure language.
- `list_instruments()` scan for search is acceptable for single-user scale;
  not a second symbol master.

## 15. Deferred beyond SI-P1 freeze

- AI Complete Review narrative
- Momentum Quality / Entry Quality methodology
- Fundamentals / news / filings / earnings PIT ingestion
- High-level consolidation, extension, breakout-quality methodology
- Advanced comparison / historical SI replay
- HTTP composition of DarvaX JSON (iframe is sufficient for P1)
- Broad extraction of `portfolio/` into a shared evidence package

ADR-010 isolation tests were updated so DarvaX still cannot become a
`DASHBOARD_JS_PARTS` filename or own `data-tab="darvax"` in ATHENA HTML, while
ATHENA-owned SI-P1 assets may name DarvaX and load Symbol 360 in an iframe.

## 16. SI-P0 contradictions found in implementation

None that reopen discovery.

Confirmed and acted on: dashboard candle API omitted `1d`; P1 added `1d` as
the allowed small extension and deferred the visual chart.

## 17. Live-browser validation / Load correction (same SI-P1)

Owner live-browser review found Load returned the workspace to the empty
state with no error. This section records the proven defect and the
narrow correction. It does not reopen SI-P0 or SI methodology.

**Root cause.** The SI toolbar used a native `<form>` with `type="submit"`.
Clicking Load (or pressing Enter) issued a GET navigation of
`/dashboard/symbol-intelligence`. The search input has no `name`, so the
reload had no `?symbol=` and `initializeRoute` showed the empty prompt.
On the owner's running process this was compounded because assembled
`/dashboard/dashboard.js` did not yet include `08c-symbol-intelligence.js`
(stale `DASHBOARD_JS_PARTS` in the already-running app), so the JS
`preventDefault` never bound. Source tests used `create_app()` with current
parts, so they could not see the live navigation.

Classification: **A** (native form submission / page navigation), with
stale assembly as the reason the submit handler was absent.

**Exact correction.**

- Replace the `<form>` with a `role="search"` toolbar.
- Load is `type="button"`; Enter on the input calls `preventDefault` then Load.
- Visible workspace errors: `EMPTY_SYMBOL`, `API_ERROR`,
  `COMPOSITION_UNAVAILABLE`, plus composer `identity.unresolved_reason`
  / `unavailable[]` codes on 200 responses (`UNRESOLVED_SYMBOL`,
  `NO_D1_DATA`, …).
- Sub-tab label is **DarvaX**; iframe/unavailable copy still shows
  `EXPERIMENTAL_UNVALIDATED`.
- Asset cache `9.236.0`.

**Regression coverage.**
`tests/api/platform/test_dashboard_hosting.py::test_symbol_intelligence_load_cannot_native_navigate`
asserts the SI pane contains no `<form>`/`type="submit"`, Load is
`type="button"`, assembled JS contains the click + Enter handlers,
`encodeURIComponent` for the composition URL, and visible error helpers.

**Live scenarios.** Exercised on a current-code scratch server (port 8100,
single-user bypass; production `:8000` left untouched): open SI, Load
`NSE:MARKSANS` and `MARKSANS` if unambiguous, invalid symbol visible error,
segment walk-through, header Refresh re-read, second symbol replaces state,
page reload with `?symbol=` retained. See owner return for screenshots.

**Result.** SI-P1 Load is usable end-to-end without dashboard reset.

## 18. Canonical catalog vs ATHENA universe (same SI-P1)

Owner clarification: SI may load any valid supported NSE/BSE instrument in
the tracked exchange catalogue. ATHENA universe membership is not an
eligibility filter.

**Authority used.** ADR-011 `symbol_master` (full broker-dump catalogue,
provider-independent records) **union** ingested `instruments` rows.
`owner_candidates`, `resolved_universe`, saved symbols, Decisions, and
holdings are not consulted for identity. `instruments` remains the
ingested/operational ledger; a symbol can be valid on `symbol_master`
with `ingested=false`.

**Resolution states.**

| State | `resolution_code` / `unavailable` |
|---|---|
| Valid + artifacts | `VALID_INSTRUMENT`; Decision/D1 present as available |
| Valid, not analyzed | `VALID_INSTRUMENT` + `NO_DECISION` (`NOT_ANALYZED`) |
| Valid, no D1 | `VALID_INSTRUMENT` + `NO_D1_DATA` |
| Ambiguous bare ticker | `AMBIGUOUS_SYMBOL` |
| Unknown | `UNKNOWN_INSTRUMENT` |

SI-P1 **GET** composition still re-reads only. **POST Analyze** hydrates
stale/missing D1 for that one symbol, then re-reads.

## 19. Fresh-data requirement (same SI-P1)

Owner product principle: **STALE DATA → REFRESH/HYDRATE → ANALYZE**, not
display a stale persisted report when Kite can supply the missing
sessions.

ATHENA Decision remains independent. `NO_DECISION / NOT_ANALYZED` does
not block SI D1 analysis and does **not** invoke `DecisionEngine`.
Outside-universe valid instruments may still hydrate D1.

## 20. Market-data hydration architecture

Existing path reused (no second Kite client, no browser Kite calls):

1. Resolve canonical `EXCHANGE:SYMBOL` from `symbol_master` ∪ `instruments`.
2. Expected completed D1 session via `CalendarEngine` /
   `latest_trading_day_on_or_before`.
3. If persisted D1 latest session `< expected`, `SymbolIntelligenceD1Hydrator`
   builds a **scoped** `KiteProvider` (`kite_symbols=[bare]`) and runs
   `LiveIngestionEngine` with `instrument_ids=[canonical]`,
   `include_daily=True`, `include_quotes=False`.
4. Re-read persisted D1, then compute SI D1 evidence.
5. Live quote uses existing `fetch_live_quote_view` (Kite `/quote`) on
   Analyze only. Quote kind is **LIVE** when the market session is open and
   **LATEST QUOTE** when closed. RSI / SuperTrend / SMA / structure use
   **LAST COMPLETED D1** only.

Ingestion config still requires at least one intraday timeframe, so a
hydrate cycle may also fetch the configured companion 5m window. That is
the existing engine contract, not a new ingest stack. Daily lookback is
the configured `lookback_days` (90).

`validate_symbols` / scanner / OwnerValidation / DecisionEngine /
Portfolio Sync / DarvaX scan are **not** called.

GET `/api/v1/symbol-intelligence/{query}` remains read-only.
POST `/api/v1/symbol-intelligence/{query}` (EXECUTE) is Analyze.

## 21. Stale-recovery semantics

| Situation | Hydration | Overall SI |
|---|---|---|
| D1 already matches expected session | `CURRENT`, not attempted | CURRENT/READY/PARTIAL from D1 |
| D1 missing/stale, hydrate writes, re-read current | `HYDRATED` | not STALE from D1 |
| Hydrate fails | `FAILED` + `D1_HYDRATION_FAILED` | STALE if D1 still stale |
| Hydrate writes but D1 still stale | `HYDRATED` + `D1_STILL_STALE` | STALE |
| GET compose | `SKIPPED` | may report STALE D1 |

Decision staleness no longer forces overall SI `STALE`.

## 22. UX correction

Primary action is **Analyze**. Cockpit cards (market, trend, momentum,
entry, Decision, DarvaX, portfolio, levels, freshness). Lineage/reason
codes live on Evidence / Audit. Complete Review is deterministic
sentences from typed states (no LLM, no BUY language). MQ/EQ remain
`null`. Fundamentals/News are compact NOT_INGESTED cards. D1 SVG chart
loads persisted `timeframe=1d` candles.

Asset cache `9.238.0`.

## 25. SI-P1 freeze boundary

ATHENA Symbol Intelligence universal symbol workspace foundation:

- any valid supported NSE/BSE canonical instrument
- not restricted to ATHENA active universe
- canonical symbol search/resolution
- on-demand symbol-scoped D1 hydration
- current/latest quote, distinct from market session state
- completed-D1 technical evidence
- D1 candlestick chart
- existing structural evidence
- ATHENA Decision composition where available
- DarvaX satellite composition
- Portfolio context
- evidence/coherence/audit trail
- explicit missing-source states
- MQ/EQ deliberately undefined
- Fundamentals/News deliberately not ingested


## 23. DarvaX live fix

**Root cause.** Composer iframe used `/darvax/symbol360.html`. The
mounted satellite route is `GET /darvax/symbol360` (FileResponse of
`symbol360.html`). FastAPI therefore returned JSON `{"detail":"Not Found"}`.

**Fix.** Iframe URL is `/darvax/symbol360?embedded=1&symbol=...`. If the
iframe still loads JSON Not Found, the UI replaces it with
**DARVAX UNAVAILABLE** (never leave raw JSON as the owner-facing surface).
`EXPERIMENTAL_UNVALIDATED` is retained.

## 24. Live validation scenarios

Required: universe+fresh D1, universe+stale D1 (hydrate), outside universe,
no Decision, invalid, held/non-held, DarvaX available/unavailable,
hydration failure. Network must show POST Analyze + scoped ingest when
D1 is stale.

