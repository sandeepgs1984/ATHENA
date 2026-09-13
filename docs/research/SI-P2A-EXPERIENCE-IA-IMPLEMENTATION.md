# SI-P2A — Symbol Intelligence Experience IA + State/Request Hardening

Status: **COMPLETE AND FROZEN** — 2026-09-13. Owner/Chief Architect
source review of asset `9.241.0` passed; owner live release gate (15
checks) passed. SI-P1 remains COMPLETE AND FROZEN. SI-P2B is **not
started**. Implementation is frozen; do not change SI-P2A source.
Date: 2026-09-13
Does not unfreeze SI-P1. Governing discovery:
`docs/research/SI-P2-SYMBOL-INTELLIGENCE-EXPERIENCE-DISCOVERY.md`.
Owner/Chief Architect decisions in the SI-P2A authorization are implemented
exactly. SI-P2B and later milestones are **not started**.

## 1. Implementation verdict

SI-P2A is a presentation and client request-lifecycle milestone. Frozen SI-P1
composer/DTO/hydration/freshness/DarvaX isolation semantics are unchanged.
The workspace now has four primary surfaces, GET-first first paint, explicit
POST Analyze, in-flight generation/abort protection, and Stock 360
reorganization of existing SI-P1 fields.

## 2. UX / IA changes

Primary nav (was eight equal tabs):

- Stock 360 (default)
- ATHENA Decision
- DarvaX (`data-si-section="experimental"`, ADR-010 isolation preserved)
- Evidence

Removed as primary peers: Complete Review, Technical / Structure,
Fundamentals, News & Catalysts.

Stock 360 above the fold:

1. Identity + price/change + quote/session
2. Coverage banner (Market data / SI coverage / Decision availability)
3. Independent Daily SMA structure and SuperTrend (10,3) — not blended
4. Momentum (RSI14 + Volume vs MA20 comparison) and Decision presence/absence
5. Key levels (empty T2/T3 omitted) + completed D1 chart

Secondary / disclosure:

- Collapsible deterministic written summary (former Complete Review text; no LLM)
- Portfolio context
- Fundamentals / News compact “Not ingested” chips (not errors, not tabs)
- DarvaX pointer only (iframe stays on the DarvaX surface)

Evidence keeps raw source / status / as-of / reference / reason / hydration
provenance. Owner-facing 360 labels do not rename `available_history_high` to
52-week high.

## 3. Request lifecycle

- Route open, tab refresh, inner SI surface change, search-hit select, and
  `loadSymbolIntelligenceWorkspace` use **GET**.
- `initializeRoute` no longer issues a second SI load after `switchTab`.
- POST Analyze runs only from Analyze / Enter (`analyze: true`).
- Stale D1 on GET does **not** auto-POST.
- POST semantics remain SI-P1: symbol-scoped D1 hydrate + re-read + quote.
  Still does not run DecisionEngine, Portfolio Sync, or DarvaX scan.
- In-flight: request generation token + AbortController. Stale AAA cannot
  replace BBB. Chart fetch also ignores superseded generation.
- Request mode is explicit (`GET` | `ANALYZE`). Duplicate suppression applies
  only when in-flight mode is **ANALYZE**, the new action is Analyze, and the
  trimmed query matches. A GET for NSE:AAA does **not** block Analyze NSE:AAA
  (GET is aborted; POST starts). Same-query Analyze while Analyze is in flight
  remains suppressed. Analyze/GET for a **different** symbol, or a different
  search-hit GET, increments generation, aborts the prior controller, and
  becomes the only request allowed to render.
- Analyze is HTML-disabled only while an Analyze for the current input query
  is in flight. GET loading leaves Analyze enabled. Editing to another query
  re-enables Analyze / Enter. No cancel/retry subsystem.
- GET loading copy vs Analyze “Refreshing D1 history… Analyzing…”.
- Error/invalid paths clear identity + `siBundle` so previous-symbol content
  cannot remain.

## 4. Defects fixed

- Eight-tab IA / empty Fundamentals and News primary tabs
- Complete Review as a peer tab (capability preserved as disclosure)
- initializeRoute + workspace **double POST**
- Automatic Analyze on first paint
- Symbol-switch race (stale response paint)
- Busy Analyze blocking a different-symbol Analyze / Enter (AAA in flight
  must yield to BBB; same-query duplicates remain suppressed)
- GET load treated as Analyze-busy (same-symbol Analyze during GET must
  supersede the GET)
- Technical “Volume vs MA20” showing the MA20 number instead of comparison
- PARTIAL coverage looking like an application error (coverage banner)

## 5. Frozen SI-P1 boundary

Unchanged: D1 freshness, hydration, RSI, SuperTrend, SMA trend, structural
zones, targets, Decision freshness, Portfolio, DarvaX experimental isolation,
SI overall coverage values. No DTO/composer edits in this milestone.

## 6. Tests

`tests/symbol_intelligence/test_si_p2a_experience.py` plus existing SI-P1,
dashboard hosting, chart release-gate, DarvaX isolation, and core API
regression. Asset cache bumped `9.238.0` → `9.241.0`. Request-race coverage
includes GET vs ANALYZE mode, GET+same-symbol Analyze supersession, same-query
Analyze duplicate suppression, and AAA→BBB Analyze/GET supersession.

## 7. Explicitly deferred (not SI-P2A)

- SI-P2B full Stock 360 density / remaining unused EXISTING fields
- SI-P2C SMA overlays on the D1 chart
- SI-P2E explicit Decision generation / Validate
- Corporate actions on Stock 360 (SI-N0 / later, knowledge-time)
- Fundamentals / news ingestion (SI-F0 / SI-N0)
- MQ/EQ formulas, blended trend scores, LLM narrative

## 8. Owner live release gate (2026-09-13)

Environment: freshly restarted uvicorn on `http://127.0.0.1:8100`,
`ATHENA_SINGLE_USER=true`, live `db/athena.db`, Kite `ICY240`, closed
market. Assets: `dashboard.js?v=9.241.0` and
`css/15-symbol-intelligence.css?v=9.241.0`. Screenshots:
`docs/research/si-p2a-live-gate/`.

| Gate | Result | Observation |
|---|---|---|
| 1 GET-first | PASS | Direct `NSE:WIPRO` first paint: `Loading persisted Symbol Intelligence…`; `GET /api/v1/symbol-intelligence/NSE%3AWIPRO`; no implicit POST Analyze. |
| 2 GET then Analyze same symbol | PASS | During GET `NSE:TI`, Analyze stayed enabled; click switched copy to `Refreshing D1 history… Analyzing…`; server `GET` then `POST` TI. |
| 3 Duplicate Analyze | PASS | While POST busy, Analyze `[disabled, busy]`; no second POST in the busy window. A later second `POST TI` occurred after re-enable (automation click), not a same-tick duplicate. |
| 4 Analyze AAA → BBB | PASS | Button path: in-flight TI Analyze, input INFY, Analyze re-enabled, `POST INFY`; final identity INFY. Enter path: `POST TCS` then `POST RELIANCE` after TCS completed (TCS POST was too fast to overlap); final identity RELIANCE. |
| 5 Search-hit supersession | PASS | Search hit `NSE:WIPRO · WIPRO` while TI in workspace issued `GET WIPRO` (not POST); final identity WIPRO. |
| 6 CURRENT + READY | PASS | `NSE:WIPRO`: Market data CURRENT, SI coverage READY, persisted Decision (NO_TRADE / Pass 35.03), Stock 360, Open Decision Brief → `/dashboard/decisions?decision=…WIPRO…`. Analyze does not recompute Decision. Shot `01-wipro-stock-360-ready.png`, `02-wipro-decision.png`. |
| 7 CURRENT + PARTIAL | PASS | `NSE:TI`: CURRENT + PARTIAL, informational banner, SMA vs SuperTrend independent, Volume Below MA20, empty T2/T3 omitted, no-Decision copy. Shots `05-ti-partial.png`, `06-ti-no-decision.png`. |
| 8 Stale D1 | PASS (N/A live) | No genuinely STALE symbol available (`NSE:20MICRONS` is CURRENT after SI-P1 hydrate). Did not manufacture staleness. Retain SI-P1 20MICRONS live-gate evidence. |
| 9 Closed-market session | PASS | Quote present: `LATEST QUOTE · MARKET CLOSED` (TI, RELIANCE). Never `LIVE · MARKET OPEN`. Completed D1 independently labelled `LAST COMPLETED D1`. |
| 10 Invalid symbol | PASS | `ZZNOPE999` Enter: `POST ZZNOPE999`; identity `No instrument matched`; WIPRO ₹167.32 gone; no stale Decision/chart. Shot `07-zznope999-invalid.png`. |
| 11 Stock 360 IA | PASS | Four nav peers only. Written summary is disclosure. Fundamentals/News chips, not tabs. |
| 12 DarvaX | PASS | Iframe `/darvax/symbol360?embedded=1&symbol=NSE%3AWIPRO`; `EXPERIMENTAL_UNVALIDATED`. Shot `03-wipro-darvax.png`. |
| 13 Evidence | PASS | Source / Status / As Of / Reference / Reason + HYDRATION SKIPPED on GET re-read. |
| 14 Responsive | PASS | Desktop Stock 360 usable. 390px with expanded rail is cramped (letterboxed capture); collapse-rail still readable. Density polish → SI-P2B. Shots `08`/`09`. |
| 15 Error/recovery | PASS | Invalid then `GET NSE:INFY` recovered INFOSYS CURRENT/READY; ZZNOPE999/WIPRO price gone. |

No SI-P2A implementation changes after freeze. SI-P2B not started.
