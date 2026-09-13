# SI-P2 — Symbol Intelligence Experience & Coverage Discovery

Status: Discovery only — no production implementation, no SI-P1 contract change  
Date: 2026-09-13  
Owner authorization: SI-P2 discovery after SI-P1 COMPLETE AND FROZEN  
Baseline UX evidence: `docs/research/si-p1-ux-baseline/` (owner NSE:TI screenshots)  
Does not rewrite SI-P0 or unfreeze SI-P1.

Inspection method: SI-P1 source (`composer.py`, DTOs, `08c-symbol-intelligence.js`,
`15-symbol-intelligence.css`, `index.html`, `03-app-shell.js`), SI-P0 inventory,
schema, Decision/Portfolio/DarvaX/corporate-action/evidence modules, and the
frozen owner screenshots. Where docs and code conflict, **code wins**.

---

## 1. Executive Summary

SI-P1 is a **correct composition foundation**. It is not yet a useful
owner-facing **stock research workstation**.

The NSE:TI baseline proves the frozen semantics work: quote vs session,
market-data CURRENT vs SI coverage PARTIAL, explicit no-Decision, honest
Fundamentals/News empty states, DarvaX `EXPERIMENTAL_UNVALIDATED`, completed-D1
chart, Evidence/Audit provenance. Those must not be destabilized.

The same screenshots prove the **experience gap**:

- Eight equal tabs scatter one research question across empty or duplicate
  surfaces.
- Overview is a field dump (nine cards), not a Stock 360 that answers
  “what is this stock doing / is it actionable / what is missing?”
- Complete Review restates Overview in prose and adds almost no new judgment.
- ATHENA Decision and Fundamentals/News tabs are mostly whitespace when
  unavailable.
- Engine terms leak (`UPTREND`, `BEARISH`, `SUPPORT 1`, `REVIEW TRIGGER`,
  `EXPERIMENTAL_UNVALIDATED` on Overview).
- SuperTrend BEARISH and SMA-structure UPTREND appear together with **no
  explanation that they are different engines** — the most important live
  research conflict is left for the owner to notice.
- Technical “Volume vs MA20” currently renders `volume_ma20` (the average),
  not a comparison. Overview already does Above/Below MA20. That is a
  **presentation defect**, not a methodology gap.
- Analyze (POST hydrate + quote) runs on every symbol load, including tab
  refresh and a possible **double POST** from `initializeRoute` +
  `loadTabData`.

**Verdict:** `READY FOR BOUNDED EXPERIENCE IMPLEMENTATION` after Owner
decisions in §19. Do **not** start Fundamentals or News ingestion in the
first SI-P2 implementation milestone. Do **not** invent MQ/EQ, consolidation,
extension, or breakout-quality scores. Do **not** wire Analyze to
DecisionEngine.

Highest-leverage SI-P2 work is **information architecture + Stock 360
presentation of the existing SI-P1 contract**, plus state/request hygiene.

---

## 2. Current SI-P1 capability inventory

Frozen and must remain:

| Capability | SI-P1 status | Owner-visible? |
|---|---|---|
| Canonical search / `EXCHANGE:SYMBOL` resolve | GET search + compose resolve | Search hits; header identity |
| GET re-read | yes | Header Refresh / fallback |
| POST Analyze = symbol-scoped D1 hydrate + re-read + live quote | yes | Analyze button; every current load |
| Live vs latest quote vs market open/closed | DTO `quote_kind` / `market_state` | Header + Overview market card |
| Completed D1 OHLCV + RSI14 + SuperTrend 10-3 + SMA20/50 trend + volume MA20 + available-history high + structural zones | D1 adapter | Overview + Technical |
| D1 SVG chart from `GET .../candles?timeframe=1d` | yes | Technical only |
| Persisted ATHENA Decision summary + TradePlan + link to Decision Brief | compose if present | Header/Overview/Decision tab |
| NO_DECISION / NOT_ANALYZED | first-class unavailable | Empty Decision copy |
| My Portfolio HELD / NOT_HELD | snapshot/holdings | Overview card |
| DarvaX iframe Symbol 360 | ADR-010, `NOT_READ` freshness | DarvaX tab; Overview teaser |
| MQ / EQ | `value=null`, named evidence only | “Methodology pending” |
| Fundamentals / News | `NOT_INGESTED` | Empty tabs |
| Evidence/Audit table | sources + unavailable + hydration | Audit tab |
| SI coverage READY / PARTIAL / STALE / UNAVAILABLE | `overall_freshness` | Header + freshness card |
| Market data CURRENT / STALE / UNAVAILABLE | `D1_CANDLES` source | Header + freshness card |

Not in SI-P1 UI despite existing on the DTO or elsewhere in ATHENA:

- `d1.open/high/low`, `live.session_open/high/low/previous_close/volume`
- `latest_high_exceeds_prior_history`, `latest_close_above_prior_history_high`
- `identity.sector`, `identity.catalog`, `identity.ingested`
- Decision `gates`, `plan_freshness`, `depth`, `intraday` when present
- IndicatorEngine MACD / ADX / ATR / EMA (pipeline-owned, not SI-adapted)
- `corporate_actions` (SPLIT/BONUS/DIVIDEND/RENAME for **price adjustment**)
- CalendarEngine **market-wide** events (not per-symbol catalysts)
- Sector health / ID-4 RS / opportunities RS (three different RS notions)

---

## 3. Owner workflow assessment

Intended path:

enter symbol → understand stock → assess trend → identify opportunity/risk →
understand ATHENA view → inspect evidence → decide next action

**What SI-P1 actually does on NSE:TI (baseline):**

1. Owner types `NSE:TI` and Analyze. POST hydrates if needed and fetches quote.
2. Header answers price, closed-market quote, D1 through, CURRENT/PARTIAL.
3. Overview dumps nine cards. Trend conflict (UPTREND vs SuperTrend BEARISH)
   is visible but unexplained. Opportunity/risk is **not** named; MQ/EQ cards
   say methodology pending. No “actionable now?” except implied by no Decision.
4. Complete Review repeats the same facts as sentences.
5. ATHENA Decision tab is two lines + vast empty space.
6. DarvaX tab is a second product (Symbol 360) with Scan & Validate.
7. Technical chart is the best “understand the stock” surface — and it is
   **tab 5**, not the first screen.
8. Fundamentals/News are honest empties that still occupy nav slots.
9. Evidence/Audit is the only place that states NO_DECISION as a source row
   with universe-not-required copy.

**Gap:** the owner can *see fields*. The owner cannot complete “understand →
trend → opportunity/risk → ATHENA view → next action” without synthesizing
across tabs and resolving engine conflicts manually.

SI-P2 should optimize **this workflow** using existing evidence, not add
tabs.

---

## 4. UX / UI findings

Evidence: `02-nse-ti-overview.png`, `01-nse-ti-decision-empty.png`,
`04-nse-ti-technical-chart.png`, `06-nse-ti-complete-review.png`, CSS
`15-symbol-intelligence.css` (one mobile breakpoint at 720px for the header
grid only).

### 4.1 Hierarchy and empty space

- Eight peer tabs + persistent identity header + Analyze disclaimer compete
  with content.
- Decision / Fundamentals / News empty states do not collapse; they leave
  most of the viewport unused (`01`, `03`, `05` baselines).
- Overview `auto-fit minmax(16rem)` wraps to a sparse last row (Key Levels +
  Data Freshness).
- DarvaX iframe `min-height: 640px` is appropriate for the satellite, not for
  Overview.

### 4.2 Redundant information

| Fact | Shown on |
|---|---|
| Last price / change / market closed | Header, Overview market card, Complete Review |
| D1 close | Header (if no live), market card, Technical, Complete Review |
| Support 1 / Review Trigger | Overview Entry, Overview Key Levels, Technical, Complete Review |
| No Decision | Overview card, Decision tab, Complete Review, Audit `NO_DECISION` |
| DarvaX experimental | Overview teaser, DarvaX tab banner, Complete Review |
| CURRENT / PARTIAL | Header, Overview freshness, Complete Review availability |

Redundancy is acceptable for a **header identity strip**. It is not acceptable
as the body of Complete Review.

### 4.3 Buried important information

- The D1 chart (best structure read) is behind Technical.
- Trend disagreement is unlabeled.
- `ATHENA Decision unavailable; this is SI coverage, not a market-data error`
  is a footnote on Data Freshness, not a first-line coverage banner.
- Audit’s “universe membership is not required” is the right reassurance and
  is hidden on tab 8.

### 4.4 Engine terminology leak

Owner-facing vs internal (baseline):

| Shown today | Investor phrasing (presentation only) |
|---|---|
| UPTREND | Daily SMA structure: up |
| SuperTrend BEARISH | SuperTrend (10,3): down |
| SUPPORT 1 / MAJOR SUPPORT | Structural support zone 1 / major support zone (Portfolio V2 lineage) |
| REVIEW TRIGGER | Structural review-trigger zone |
| AVAILABLE-HISTORY HIGH | High of available D1 history (not 52-week official) |
| SI coverage PARTIAL | ATHENA Decision not available |
| EXPERIMENTAL_UNVALIDATED on Overview | Keep exact label **on DarvaX only** |

Do not rename lineage in Audit. Rename **Overview labels** only.

### 4.5 Complete Review as a tab

Today it is a deterministic concatenation of already-shown states (`siCompleteReview`
in `08c-symbol-intelligence.js`). It does not rank, does not resolve UPTREND vs
BEARISH, does not say “actionable/not actionable.” As a **peer tab** it fails
the workflow test. As a **single scroll narrative under Overview** (or a
collapsed “Written summary”) it can still help print/readability later
(SI-P2D), without remaining a top-level destination in P2A.

### 4.6 Evidence / Audit prominence

Keep the table. Demote it to secondary (“Evidence” in an advanced strip or
footer control). It is the PIT/provenance surface, not the research surface.
Do not delete source rows; do not average freshness.

### 4.7 PARTIAL coverage

Baseline handling is **semantically correct** and **visually weak**. PARTIAL
looks like a status chip, not “you can research this stock; ATHENA has not
issued a Decision.” Overview should lead with a coverage banner and still
show D1 research.

---

## 5. Information architecture recommendation

**Do not keep eight equal tabs.**

Recommended P2A primary chrome (still one SI route, still one SI-P1 bundle):

1. **Stock 360** (default) — answers the research questions using existing
   fields + coverage banner + chart.
2. **ATHENA Decision** — persisted Decision or explicit empty + link to
   Decisions workspace (no engine call).
3. **DarvaX** — iframe only, experimental banner mandatory.
4. **Evidence** — current Audit table.

Remove from primary nav (do not delete capability):

- **Complete Review** — fold into Stock 360 as optional written summary, or
  keep behind “Summary” disclosure. Decision: Owner §19.
- **Fundamentals / News** — until ingested, show as **unavailable chips on
  Stock 360**, not empty tabs. Re-add tabs when a PIT source exists
  (separate later milestones).
- **Technical / Structure** — merge chart + levels into Stock 360; keep a
  “Technical detail” disclosure if the 360 would overflow.

This is presentation IA. The SI-P1 JSON contract stays. Tabs are CSS/JS
chrome, not new APIs.

---

## 6. Overview / Stock 360 recommendation

First screen should answer, **using only existing contract fields**:

| Question | Existing source | 360 placement |
|---|---|---|
| What is the stock doing? | live quote + D1 OHLC + chart | Hero: name, price, change, quote kind, session |
| Is the trend healthy? | `symbol_trend` **and** `supertrend_direction` as two labeled facts | Trend pair; never blended |
| Momentum improving or deteriorating? | RSI14 + volume vs MA20 as **measurements** | Momentum strip. No 0–10 MQ |
| Price vs structure? | close vs support_1 / major_support / review_trigger / available-history high | Chart + one “where is price” line if DERIVED_SAFE (see §7) |
| Important levels? | existing zones; hide null Target 2/3 | Levels list with lineage |
| ATHENA Decision? | `decision.present` | Coverage banner + Decision capsule |
| Actionable now? | **Do not invent.** If Decision present, show type/direction/confidence. If absent: “No ATHENA Decision” — not “not actionable” | |
| Major risks? | SuperTrend vs SMA disagreement (present both); missing Decision; stale D1; incoherent flags | Risk/missing list from `unavailable` + incoherent reasons |
| Catalysts? | none ingested | “Not ingested” chip |
| Held? | portfolio status | One line |
| Unavailable evidence? | coverage + fundamentals/news NOT_INGESTED + DarvaX status | Missing-evidence list |

Minimum 360 hierarchy (top → down):

1. Identity + quote + session (keep)
2. Coverage banner (Market data / SI coverage / one-sentence reason)
3. D1 chart (move from Technical)
4. Trend pair + RSI + volume comparison (correct the MA20 label)
5. Structure levels (only present zones)
6. ATHENA Decision capsule (or empty)
7. Portfolio one-liner
8. DarvaX: “Open experimental Symbol 360” (do not embed iframe on 360)
9. Missing: Fundamentals, News, MQ, EQ
10. Optional written summary (today’s Complete Review text)

No new scores. No fabricated T2/T3.

---

## 7. Technical / Structure gap analysis

### 7.1 Audit of what is shown

| Field | Classification | Notes |
|---|---|---|
| D1 OHLC / volume | EXISTING | Close shown; O/H/L on DTO unused |
| SMA20 / SMA50 | EXISTING | Overview trend card; not drawn on chart |
| `symbol_trend` (SMA structure) | EXISTING | PortfolioTrendAdapter |
| SuperTrend dir/value | EXISTING | Can disagree with SMA trend — must stay dual |
| RSI14 | EXISTING | Measurement only; SI-P1 already forbids OB/OS interpretation |
| Volume vs MA20 | EXISTING | Overview comparison OK; Technical metric **mislabels MA20 as “vs MA20”** |
| Support 1 / Major support / Review trigger | EXISTING | PortfolioStructuralReviewEngine; nulls allowed |
| Target 1/2/3 | EXISTING | Baseline T2/T3 `—`; **do not invent** |
| Available-history high | EXISTING | Not official 52-week |
| ATH exceed flags | EXISTING unused | Safe to **display the boolean** with lineage; not a “breakout quality” score |
| Chart + S1/MS/RT overlays | EXISTING | No SMA/SuperTrend overlay yet |
| Session OHLC from live quote | EXISTING unused | Presentation of Analyze quote only; not D1 methodology |
| Distance of close to a zone (pct) | DERIVED_SAFE | Arithmetic on existing Decimals + explicit “not a signal” |
| Close above/below SMA20/50 | DERIVED_SAFE | Already implied by trend adapter; showing the crosses is display |
| Consolidation / extension / breakout quality | METHODOLOGY_REQUIRED | SI-P0 + ID-7B.2 extension NO-GO; PS-P10C.1 S/R caution |
| MACD/ADX/ATR as SI cockpit | EXISTING in IndicatorEngine | Reuse only if SI-P2C explicitly adapts pipeline indicators with lineage; not required for 360 |
| Official 52-week high | NEW_DATA_REQUIRED | Available-history high is not this |
| Intraday structure | EXISTING on Decision-bound ID-11 | Only when Decision present; Decision-bound, not SI-global |

### 7.2 Chart UX (P2C, not methodology)

Safe: SMA20/50 overlays from the same series the adapter used; last-price
marker; hide empty target overlays; denser viewport; loading skeleton.

Unsafe: painting DarvaX boxes onto the ATHENA D1 chart; mixing live quote
into candle bodies; fabricating missing targets.

---

## 8. Fundamentals discovery

SI-P1 empty tab is **correct**. There is still **no** fundamentals table,
DTO, provider field, or test in ATHENA (reconfirmed from SI-P0 §2.10 and
schema). `Instrument` has identity only: name, sector, series, ISIN,
listed/delisted.

Useful owner categories (conceptual, not a vendor pick):

- Profile (name, sector, series) — **already on identity; sector unused in UI**
- Market cap / valuation, growth, margins, ROE/ROCE, debt, cash flow,
  shareholding, quarterly/annual, valuation history, peers — **all absent**

Separation:

| Bucket | Reality |
|---|---|
| 1. Already available | `identity.name/sector/exchange/series`; not financials |
| 2. Requires ingestion | All statement/valuation/shareholding series |
| 3. Requires PIT-safe historical storage | Restated filings; knowledge-time vs period-end; versioned rows + `fetched_at` / `as_of_known` |
| 4. Deterministic once ingested | YoY growth, margins, simple ratios from stored line items |
| 5. Methodology/interpretation | “Cheap”, “quality compounder”, peer rank, earnings acceleration score |

**Do not select a vendor in SI-P2 experience work.** NSE CA provider’s
filings URL is **not** a fundamentals API. DarvaX deck “superb quarterly
numbers” is a **human** filter, not ingested data.

Fundamentals should be a **later track** after Owner chooses a PIT source
and an ADR if a new provider Protocol is required (ADR-002 pattern).

---

## 9. News & Catalysts discovery

Empty tab is **correct**. `EvidenceCategory.NEWS` exists and is **unused**.
Decision context: “No news ingestion, no generated rationale.”
`CalendarEvent` is **exchange session / macro calendar**, not company news.
`corporate_actions` is SPLIT/BONUS/DIVIDEND/RENAME for **price adjustment**,
with `ex_date` and **no `fetched_at`**. NSE `FILINGS_URL` in the CA provider
feeds that adjustment/EMR coverage path, not an announcement feed.

Conceptual capability (trusted primary vs general news):

| Class | Trust | PIT requirement |
|---|---|---|
| Exchange filings / corporate actions already stored | Primary for **ex-date price effects** | Filter `ex_date <= as_of`; knowledge-time still missing |
| Earnings, dividends as **events** | Primary if from exchange/company PDF with publish timestamp | Store `published_at`, `event_date`, revision id; SI as_of uses `published_at <= as_of` |
| Orders, management, regulatory | Primary filings | Same |
| Wire/portal “material news” | Secondary / untrusted until sourced | Easy lookahead if “latest headline” is used in replay |
| Sentiment | Forbidden as SI methodology | — |

**Do not scrape generic news in SI-P2.** A later News track must version
rows so historical SI cannot see future publications.

Safe P2A display: “News & catalysts not ingested” chip; optional list of
**already persisted** `corporate_actions` for this `instrument_id` with
explicit “price-adjustment events, not a news feed” lineage (EXISTING data,
new presentation). That is the only CA reuse that does not pretend to be
fundamentals/news.

---

## 10. ATHENA Decision integration assessment

SI-P1: display latest persisted Decision per instrument; never call
`DecisionEngine`. NO_DECISION is valid for symbols outside the last cycle /
outside universe. Analyze hydrates **market data only**.

Options:

| Option | Meaning | Safety |
|---|---|---|
| A. Display only (current) | Empty state + “does not limit SI analysis” | Safest; keep as default |
| B. Link out | Deep-link Decisions tab if a Decision exists; if not, explain how ATHENA normally produces one (cycle / Validate) | Safe; no new engine |
| C. Explicit “Request ATHENA analysis” | Separate control that uses **existing** `POST /api/v1/market/validate` (or owner-candidate + cycle), **not** SI Analyze | Possible later; must not be the Analyze button; universe/eligibility/costly |
| D. Analyze runs DecisionEngine | Forbidden | Violates SI-P1 freeze |

**Recommendation:** keep **A+B** in SI-P2A/P2B. Do not implement C until Owner
accepts cost, eligibility, and that it is **not** SI hydration. Never D.

Empty-state UX: fill the Decision panel with coverage copy + “Open Decisions
workspace” rather than two lines on a black page. Still not an engine call.

---

## 11. DarvaX boundary assessment

Preserve SI-P1:

- iframe `/darvax/symbol360?embedded=1&symbol=`
- ATHENA core does not import `athena.darvax` / read `db/darvax.db`
- freshness `NOT_READ`
- label `EXPERIMENTAL_UNVALIDATED` (DX-5 still stands)
- ENTER ≠ ATHENA TRADE

UX-only notes:

- Overview teaser is enough; do not iframe DarvaX on Stock 360 (height +
  implied endorsement).
- DarvaX tab already has its own Look up / Scan & Validate — satellite-owned.
- SI must not hide the experimental banner to “clean up” 360.

No DarvaX methodology change in SI-P2.

---

## 12. Edge / error-state matrix

| State | Expected UX (P2A/P2B presentation; semantics already SI-P1) |
|---|---|
| Valid + READY | Coverage READY; Decision capsule populated; 360 full D1 |
| Valid + PARTIAL | Banner: market CURRENT, Decision unavailable; 360 still shows D1; not an error chrome |
| Valid + STALE | Banner STALE; Analyze enabled; do not present D1 as current |
| Valid + no Decision | Same as PARTIAL when D1 current; Decision panel empty-but-explained |
| Invalid symbol | Replace 360; identity unresolved; no leftover previous symbol |
| Ambiguous symbol | Qualify NSE vs BSE; do not pick silently (unit-tested; live catalog may have no BSE dual-list) |
| Stale D1 hydrated | Progress copy; then CURRENT; hydration row on Evidence |
| Hydration failure | Loud failure + last persisted D1 marked STALE; no fake CURRENT |
| Quote unavailable | D1 close as price; caption LAST COMPLETED D1 · market state |
| Market open | LIVE · MARKET OPEN when quote present |
| Market closed | LATEST QUOTE · MARKET CLOSED when quote present |
| Weekend/holiday | MARKET CLOSED via CalendarEngine; D1 expected = last session |
| Fundamentals unavailable | Chip, not empty tab (P2A IA) |
| News unavailable | Chip, not empty tab |
| DarvaX unavailable | Explicit UNAVAILABLE; never JSON dump |
| Decision stale | If D1 current + Decision dated off expected session: SI-P1 overall is still READY when Decision source is CURRENT only if dates match — Decision STALE does **not** force overall STALE (SI-P1). Show Decision as stale **inside** the capsule without marking market data stale |
| Held / not held | One line; no HOLD_* on non-held |
| Backend/API failure | `siShowWorkspaceError`; clear previous bundle |
| Slow Analyze | Existing “Refreshing D1 history… Analyzing…”; add cancel + disable double-submit in P2A |
| Repeated Analyze | Idempotent hydrate skip when CURRENT; still may re-fetch quote |
| Symbol switch during request | **Gap:** no AbortController; in-flight POST can apply to the wrong symbol. P2A must ignore stale responses |

---

## 13. Data-source and PIT / replay requirements

Unchanged from SI-P0 §12, applied to P2:

- D1 / indicators / structural zones: market-time `as_of` on candles.
- Live quote: **current-state only**; never mix into D1 engines (already frozen).
- Decision: latest `ts`; historical SI replay would need `decision.ts <= as_of`
  (not in SI-P1; do not pretend P2 Overview is a replay product).
- DarvaX: satellite-owned; ATHENA must not stamp CURRENT from iframe.
- Corporate actions: `ex_date`; no knowledge-time column — do not present as
  “news known that morning” without `fetched_at`.
- Future fundamentals/news: **knowledge-time versioning is mandatory** or
  replay will leak restatements and future headlines.

Attractive UI that would violate PIT:

- “Today’s news” scraped at view time and stored as if known on `d1.latest_session`
- Mixing live LTP into RSI/SuperTrend
- Averaging DarvaX ENTER into SI coverage READY
- Filling T2/T3 from ATR TradePlan while labeling them structural targets

---

## 14. Performance / request-model assessment

Current (`08c` + `03-app-shell.js`):

| Event | Work |
|---|---|
| Open SI with `?symbol=` | `switchTab` → `loadSymbolIntelligenceWorkspace` **POST Analyze**; `initializeRoute` may **POST again** |
| Click Analyze / Enter | POST Analyze (hydrate if stale + Kite quote) |
| Header Refresh | `loadTabData` → workspace loader → POST again |
| Switch SI inner tab | Client `hidden` only — **no extra backend** |
| Technical chart | Extra GET `candles?timeframe=1d&limit=180` after render |
| Search input | GET `/search?q=` after 200ms; scans `list_instruments` + symbol master in process |

Recommendations (no implementation here):

- **Eager:** identity resolve + persisted GET composition for first paint.
- **Analyze/POST:** only when D1 STALE, owner clicks Analyze, or explicit
  refresh. Do not POST on every tab visit if GET is CURRENT.
- **Quote:** Analyze-only remains correct for PIT; optional later GET quote
  is current-state and must stay labeled.
- **Chart:** lazy-load when Stock 360 or Technical is shown (if still split).
- **Fundamentals/news (future):** never on the Analyze path; separate GET with
  `as_of`.
- **Search:** keep prefix scan for single-user; no new index required in P2A.
- **In-flight:** generation token or AbortController on symbol change.
- **Deduplicate** `initializeRoute` vs `loadTabData` double Analyze.

Do not change hydration engine or lookback in P2A.

---

## 15. Existing vs derived vs methodology-required vs new-data matrix

| Item | Class | SI-P2? |
|---|---|---|
| All SI-P1 DTO fields already shown | EXISTING | Present better |
| Sector, D1 OHLC, live session OHLC, ATH flags, Decision gates/plan | EXISTING unused | P2B/P2C display |
| Close vs zone / vs SMA (pct, side) | DERIVED_SAFE | Optional P2B; labeled arithmetic |
| Correct “volume vs MA20” comparison on Technical | EXISTING (fix label) | P2A defect |
| Dual trend labels | EXISTING | P2A/P2B explanation |
| MQ / EQ scores | METHODOLOGY_REQUIRED | Non-goal |
| Consolidation / extension / breakout quality | METHODOLOGY_REQUIRED | Non-goal |
| Official 52w, financials, peers | NEW_DATA_REQUIRED | Later track |
| Company news / earnings calendar feed | NEW_DATA_REQUIRED | Later track |
| CA split/bonus/div list as adjustment events | EXISTING | Optional P2B footnote |
| Request DecisionEngine from Analyze | Unsafe | Forbidden |
| SMA overlays on D1 chart | DERIVED_SAFE / EXISTING series | P2C |
| AI Complete Review | METHODOLOGY_REQUIRED + non-PIT unless versioned | Non-goal |

---

## 16. Proposed SI-P2 milestone decomposition

Experience first. Data vendors later. Names adjusted from the brief because
Fundamentals/News are **new-data tracks**, not the next coding slice.

| Milestone | Objective | Touches SI-P1 contract? |
|---|---|---|
| **SI-P2A** — Experience IA + state/request hardening | Collapse primary nav; coverage banner; empty-state fill; fix volume-vs-MA20 label; abort/dedupe Analyze; PARTIAL treatment; terminology on Overview only | Presentation + JS request hygiene. No DTO breakage |
| **SI-P2B** — Stock 360 | Chart on first screen; trend pair; missing-evidence list; Decision capsule; hide null targets; optional CA footnote | Display unused EXISTING fields; additive DTO only if a new view-model is cleaner — prefer mapping in JS |
| **SI-P2C** — Technical chart UX | SMA overlays, loading/empty chart, denser layout; still completed-D1 only | No new methodology |
| **SI-P2D** — Written summary | Relocate Complete Review under 360; still deterministic sentences; no LLM | No new facts |
| **SI-P2E** — Decision empty-state / outbound links | Better no-Decision UX; optional later **separate** “request validate” (Owner C) | No Analyze→engine |
| **SI-F0 / SI-N0** (after P2 experience) | Fundamentals / News PIT discovery **with vendor/ADR** | New data; not SI-P2A–E |

SI-P2G-style release gates belong **inside each** sub-milestone, not as a
dumping ground after mixing data ingestion.

**Recommended next implementation milestone: SI-P2A.**

---

## 17. Risks / architectural boundaries

- Unfreezing SI-P1 freshness, hydration, or DarvaX isolation to “make 360 nicer.”
- Blending SuperTrend and SMA into one “health” badge.
- Filling empty targets from TradePlan ATR.
- Putting DarvaX action on Stock 360 as if it were ATHENA.
- POST Analyze on every navigation (Kite + ingest cost; race on symbol switch).
- Treating `corporate_actions` as a news feed.
- Starting a vendor integration under an “experience” milestone.
- New ADR needed only if a new **provider Protocol** or DecisionEngine seam
  is proposed — **not** for CSS/IA.

---

## 18. Explicit non-goals (this SI-P2 experience track)

- DecisionEngine / Portfolio Sync / DarvaX scan from Analyze
- MQ / EQ formulas
- AI narrative
- High-level consolidation / extension / breakout-quality methodology
- New S/R engine
- External fundamentals or news vendor selection
- Historical SI replay product
- EMR as SI input
- Order placement
- Changing SI-P1 GET/POST semantics except request **when** they fire from UI

---

## 19. Questions requiring Owner / Chief Architect decision

1. **Primary nav:** Accept four surfaces (Stock 360 / Decision / DarvaX /
   Evidence) vs keep eight tabs with only visual density fixes?
2. **Complete Review:** Fold under 360 now (P2A/P2D) or keep a tab until P2D?
3. **Analyze vs GET:** May first paint use GET, with POST only when D1 is
   stale or the owner clicks Analyze?
4. **Decision request:** Stay display-only (A+B) or later explicit Validate
   control (C), never on Analyze?
5. **Terminology:** Investor labels on Overview, raw codes on Evidence only?
6. **Corporate actions list** on 360 as price-adjustment events — yes/no?
7. **SI-P2A scope includes** the volume-vs-MA20 label fix and double-POST
   fix as **presentation/request defects** (recommended yes)?
8. **Fundamentals/News:** Confirm deferred to SI-F0/SI-N0, not P2A?

---

## 20. Recommended next implementation milestone

**SI-P2A — Symbol Intelligence experience IA and state/request hardening**

In scope: Stock 360 chrome (or approved nav subset), coverage banner, empty
states that don’t waste the viewport, PARTIAL-as-research-OK, Overview
terminology, Technical volume-vs-MA20 label, Analyze in-flight/dedupe,
optional GET-first if Owner approves Q3.

Out of scope: new data, new methodology, DecisionEngine, DarvaX methodology,
Fundamentals/News ingestion, chart SMA overlays (P2C), LLM.

Stop after SI-P2A design approval; do not auto-start P2B.

---

## Appendix A — Baseline screenshot index

| File | UX evidence used |
|---|---|
| `01-nse-ti-decision-empty.png` | Empty Decision tab / whitespace |
| `02-nse-ti-overview.png` | Nine-card dump; trend conflict; PARTIAL |
| `03-nse-ti-news.png` | Honest empty News |
| `04-nse-ti-technical-chart.png` | Best structure surface buried; T2/T3 null; ST vs SMA |
| `05-nse-ti-fundamentals.png` | Honest empty Fundamentals |
| `06-nse-ti-complete-review.png` | Prose duplicate of Overview |
| `07-nse-ti-darvax.png` | Satellite iframe + experimental banner |
| `08-nse-ti-audit.png` | Provenance; keep secondary |
