# SI-P2B — Stock 360 Research Workspace

Status: **COMPLETE AND FROZEN** — asset `9.244.0`.
Owner/Chief Architect source review passed; final visual re-check of
presentation hardening passed 2026-09-13. No implementation edits after freeze.
Date: 2026-09-13
Does not unfreeze SI-P1 or SI-P2A.
Governing discovery: `docs/research/SI-P2-SYMBOL-INTELLIGENCE-EXPERIENCE-DISCOVERY.md`.
Frozen IA/request: `docs/research/SI-P2A-EXPERIENCE-IA-IMPLEMENTATION.md`.

SI-P2C and later milestones are **not started**.

## 1. Executive Summary

SI-P2B is a **presentation / composition** milestone. Stock 360 becomes a
scanable research cockpit over the frozen SI-P1 bundle. No DecisionEngine,
no Portfolio Sync, no DarvaX scan, no DTO/composer semantic change, no new
score, no blended trend verdict.

The four P2A primary surfaces remain: Stock 360 (default), ATHENA Decision,
DarvaX, Evidence. GET-first / explicit Analyze / generation / AbortController
/ GET-vs-ANALYZE mode are unchanged.

Live-gate cosmetics handled here: duplicate ticker/name, invalid-symbol chart
whitespace, narrow-view Stock 360 clipping, sparse cards.

## 2. Owner research workflow

Search a valid NSE/BSE symbol (GET). Within the first viewport the owner
should see: identity, price/change, quote kind, market state, completed-D1
as-of, market-data vs SI coverage, then a compact strip of SMA structure,
SuperTrend, RSI, volume participation, and Decision availability.

Scroll for market snapshot, independent technical structure (with a
presentation-only disagreement note when SMA and SuperTrend differ), momentum
facts, a price map of supported D1 levels, compact ATHENA View, the completed
D1 chart, portfolio context, and a collapsible deterministic written review.

Analyze remains explicit and only hydrates stale D1. It never creates a
Decision.

## 3. Before / after IA

**Before (P2A).** Four surfaces, coverage banner, four equal core cards,
chart with 280px loading host even when invalid, duplicate name line,
“Methodology pending” on momentum, flat key-level table, Decision card
duplicated as a peer of structure.

**After (P2B).** Same four surfaces. Header is identity + quote + D1 as-of
only (coverage stays on the banner). Compact scan strip. Distinct market /
structure / momentum / price-map / ATHENA-view sections. Chart is featured
and omitted on unresolved symbols. Distances from completed-D1 close to D1
levels only. Evidence jump. Narrow CSS so Analyze and header stay usable.

## 4. Design matrix

Classification: EXISTING | DERIVED_SAFE | PRESENTATION_ONLY |
METHODOLOGY_REQUIRED | NEW_DATA_REQUIRED.

Only the first three are implemented.

| Field / Surface | Source | Classification | As-of semantics | Coherence | Implemented? | Reason |
|---|---|---|---|---|---|---|
| Ticker / company | `identity.symbol`, `identity.name` | PRESENTATION_ONLY | Catalog identity | Suppress name when normalized equal to ticker | Yes | Duplicate WIPRO/WIPRO live-gate |
| Canonical instrument id | `identity.instrument_id` | EXISTING | Resolution | Unchanged | Yes | Meta line only |
| Price / change | `live.last_price`, `live.change_pct` else `d1.close` | EXISTING | Quote as-of vs completed D1; never mixed in one number | `live.present` chooses quote | Yes | Frozen quote-vs-D1 split |
| Quote kind / market state | `live.quote_kind`, `live.market_state`, `live.label` | EXISTING | Quote session | Caption frozen P2A | Yes | Never LIVE when closed |
| Completed D1 close / date / OHLC | `d1.close`, `latest_session`, `open/high/low` | EXISTING | Last completed D1 | `d1.present` | Yes | Snapshot |
| SMA20 / SMA50 | `d1.fast_sma`, `d1.slow_sma` | EXISTING | Completed D1 SMA | Trend adapter coherence | Yes | Shown as values, not a blend |
| D1 trend (SMA structure) | `d1.symbol_trend` | EXISTING | Completed D1 | Independent of SuperTrend | Yes | Label Up/Down/Sideways/Mixed from existing enum |
| SuperTrend dir / value | `d1.supertrend_direction`, `supertrend_value` | EXISTING | Completed D1 ST 10,3 | Independent | Yes | |
| Structure vs SuperTrend note | SMA enum vs ST enum | PRESENTATION_ONLY | Same D1 bar | Shown only when both present and directionally opposite or SMA SIDEWAYS vs ST | Yes | No score, no winner |
| RSI14 | `d1.rsi14` | EXISTING | Completed D1 | `rsi_is_coherent` not re-derived | Yes | Numeric only |
| Volume vs MA20 | `d1.volume` vs `d1.volume_ma20` | EXISTING | Same D1 bar | Comparison already P2A | Yes | Above/Below MA20; also “vs 20D average” copy |
| Support 1 / Major support / Review trigger / Target 1 | `d1.*` zones | EXISTING | Structural review on completed D1 | Omit empty | Yes | |
| Target 2 / Target 3 | zones | EXISTING but omit empty | Same | Omit | Yes (omit) | No T2/T3 methodology |
| Available-history high | `d1.available_history_high` | EXISTING | Prior D1 history, **not** 52-week / ATH official | Never relabel | Yes | |
| Support / Major Support distance | completed-D1 close vs `zone.upper`; `(close − boundary) / boundary × 100` | DERIVED_SAFE | Both completed D1 | Finite non-zero close and boundary | Yes | Display **absolute magnitude** + ABOVE/BELOW/AT. Direction from arithmetic sign. No recommendation. Live quote unused. |
| Review Trigger / Target 1 / available-history-high distance | level vs completed-D1 close; `(level − close) / close × 100` | DERIVED_SAFE | Both completed D1 | Finite non-zero close and level | Yes | Display absolute magnitude + ABOVE/BELOW/AT. Trigger/Target use `zone.lower`. No recommendation. |
| % from live quote to D1 levels | quote vs D1 zone | — | **Session mismatch** | Deferred | No | Provenance ambiguity |
| ATHENA Decision type / confidence / ts / explanation | `decision.*` | EXISTING | Decision ts vs expected session via freshness | `present` | Yes | Compact 360 + full Decision surface |
| Score value | `decision.depth.score.value` if present | EXISTING | Persisted depth | Optional | Yes | Not recomputed |
| Gate summary | count `decision.gates` passed | DERIVED_SAFE | Persisted gates | Optional | Yes | “n of m gates passed” only |
| Plan freshness | `decision.plan_freshness.status` | EXISTING | Decision-bound | Optional | Yes | |
| TradePlan entry band | `decision.trade_plan` | EXISTING | Decision | Shown on Decision surface, not invented SI plan | Compact pointer only on 360 | Avoid duplicating Decision |
| MQ / EQ | placeholders | METHODOLOGY_REQUIRED | — | Deferred | No | |
| Blended trend / bullishness | none | METHODOLOGY_REQUIRED | — | Deferred | No | |
| Fundamentals / News | `NOT_INGESTED` | EXISTING | — | Chips only | Yes | |
| Portfolio qty / avg / last / value / investment / P&amp;L | `portfolio.*` | EXISTING | Snapshot | HELD only | Yes | Portfolio-owned labels |
| Portfolio HOLD/EXIT guidance | interpretation / next_action | EXISTING Portfolio | Not SI advice | Shown only as Portfolio-owned when present; SI does not mint BUY/SELL | Yes (unchanged policy) | |
| DarvaX scores/stops | satellite | — | Isolated | Pointer only | Yes | No blend |
| Chart SMA overlays | future P2C | METHODOLOGY_REQUIRED | — | Deferred | No | Existing S1/MS/RT lines stay |

## 5. Stock 360 hierarchy

A. Header (identity, price, quote caption, D1 as-of)  
B. Coverage banner  
C. Compact scan strip (SMA, SuperTrend, RSI, Volume, Decision)  
D. Market Snapshot  
E. Technical Structure (+ disagreement note)  
F. Momentum / Participation  
G. Price map  
H. Compact ATHENA View  
I. Completed-D1 chart (resolved + D1 present only)  
J. Portfolio Context  
K. Written summary (disclosure)  
L. Capability chips + DarvaX pointer + View evidence  

## 6. Market Snapshot

Latest/live quote, change, quote kind, market state, last completed D1 close
and date, D1 OHLC when present, available-history high. Quote and D1 stay
separate sentences/rows.

## 7. Technical Structure

Independent Daily SMA structure, SuperTrend (10,3) + value, SMA20, SMA50.
Disagreement copy when directions differ. No blended verdict.

## 8. Momentum / Participation

RSI (14) numeric. Volume vs 20D average: Above/Below MA20. No MQ.

## 9. Price Map

Supported zones only. Distances use **completed-D1 close**, never live/latest
quote. Direction is presentation-derived from the arithmetic sign. The
displayed percentage is the **absolute magnitude** to one decimal. Equal after
that precision is worded **at**. No buy/hold/sell, buffer, or break
recommendation is inferred.

Two denominators (different investor questions; not mixed):

- Support 1 / Major support — close relative to **zone.upper**,
  denominator = **boundary**:
  `(close − zone.upper) / zone.upper × 100`
  → `Completed D1 is 8.4% above Support 1 upper boundary.`
  → `Completed D1 is 3.2% below Support 1 upper boundary.`
  → `Completed D1 is at Support 1 upper boundary.`
- Review trigger / Target 1 / available-history high — **level** relative to
  completed-D1 close, denominator = **close**:
  `(level − close) / close × 100` (trigger/target use `zone.lower`)
  → `Review Trigger is 12.6% above completed-D1 close.`
  → `Target 1 is 9.7% above completed-D1 close.`
  → `Available-history high is 14.3% above completed-D1 close.`

Empty T2/T3 omitted. No midpoints.

## 10. ATHENA View

If present: type, confidence, persisted score if `depth.score.value` exists,
gate pass count, Decision date, plan freshness, one-line explanation, Open
ATHENA Decision (primary surface), Open Decision Brief. If absent: not
available; SI research remains available. No DecisionEngine.

## 11. Portfolio Context

Held: quantity, average, last, current value, investment, P&amp;L / %.
Not held: “Not held in My Portfolio”.

## 12. Chart treatment

Taller featured host. Loading placeholder only while a chart fetch is
actually issued. Unresolved/invalid: **no chart host**. Missing D1: compact
unavailable, no 280px void. Existing S1/MS/RT guides retained. No new SMA
overlay (SI-P2C).

## 13. Deterministic written review

Still collapsible. Shorter; mentions independent structure disagreement when
shown on cards. No LLM. SI-P2D remains the written-summary milestone.

## 14. Unavailable capabilities

Fundamentals / News: Not ingested chips. DarvaX: experimental pointer.

## 15. Responsive behavior

`~390px` / `max-width: 720px`: single column, header wrap, toolbar
`min-width: 0`, Analyze `flex-shrink: 0`, metrics wrap, chart `width: 100%`.
Does not restyle the global ATHENA rail.

## 16. Provenance / PIT safeguards

No live-quote arithmetic against D1 levels. No 52-week/ATH relabel. Coverage
statuses retain P2A meanings. Evidence table unchanged. View evidence jump
only.

## 17. Tests

`tests/symbol_intelligence/test_si_p2b_stock_360.py` plus SI-P2A, SI-P1
composer/API, dashboard hosting, chart release-gate, DarvaX isolation pins,
core SI API. Asset cache `9.244.0` after presentation/numeric-format
hardening (`9.243.0` was the live-gate source review).

## 18. Intentionally deferred

MQ, EQ, T2/T3 methodology, fundamentals/news vendors, CA intelligence,
blended trend, live-quote distances, SMA chart overlays (P2C), LLM written
report (P2D), Decision generation (P2E), DarvaX methodology, chart S1/MS
right-edge label collision (SI-P2C).

## 19. Owner live-release gates

A. CURRENT + READY + Decision (e.g. NSE:WIPRO)  
B. CURRENT + PARTIAL / NO_DECISION (e.g. NSE:TI)  
C. Held portfolio symbol if one exists in the live book  
D. Non-held  
E. SMA vs SuperTrend disagreement (TI historically)  
F. Invalid ZZNOPE999 — no chart loading void  
G. Closed-market quote caption  
H. Desktop first viewport  
I. ~390px Stock 360 + Analyze visible  
J. Open ATHENA Decision + Open Decision Brief  
K. DarvaX isolation  
L. Evidence provenance  

## 20. Screenshots required for validation

Stock 360 READY; PARTIAL; trend disagreement; price map; chart; portfolio if
held; invalid; narrow layout. Do not manufacture DB state.

## 21. Owner live release gate (2026-09-13)

**Historical.** Owner live gate on `9.243.0` passed for evidence/methodology
boundaries. Screenshots in `docs/research/si-p2b-live-gate/` remain the
record of that review and of the presentation defects corrected in §22.
SI-P2B was **not** left COMPLETE AND FROZEN after those screenshots.

| Gate | Result | Observed |
|---|---|---|
| 1 Assets / IA | PASS | Four surfaces; Stock 360 default; GET-first route loads; Analyze POST only; DarvaX isolated |
| 2 READY WIPRO | PASS | CURRENT + READY; Decision NO_TRADE; full hierarchy |
| 3 Duplicate name | PASS | WIPRO ticker once; INFY + INFOSYS both visible |
| 4 PARTIAL TI | PASS | CURRENT + PARTIAL; research remains available |
| 5 Disagreement | PASS | TI SMA Up / SuperTrend Down; independent copy; no blended verdict |
| 6 Momentum | PASS | RSI (14); Volume Above/Below MA20; no MQ |
| 7–9 Price Map | PASS | Absolute % + above/below; arithmetic matched; empty T2/T3 omitted on TI |
| 10 Session | PASS | Distances cite completed-D1 close; WIPRO quote ₹167.40 ≠ D1 ₹167.32 |
| 11 Snapshot terms | PASS | Available-history high not 52-week/ATH |
| 12 ATHENA View | PASS | 6 of 6 gates passed beside score 35.03; Decision Brief navigated |
| 13 Portfolio | PASS | ACMESOLAR held qty 418; WIPRO/TI not held; no SI-minted BUY/HOLD/SELL |
| 14 Chart | PASS | Featured D1; S1/MS/RT; no SMA overlay |
| 15 Invalid | PASS | ZZNOPE999; no chart host; no Loading D1 void |
| 16–19 | PASS | NOT_INGESTED chips; DarvaX pointer; Evidence provenance; collapsible written review |
| 20 Desktop | PASS | First viewport identity/price/coverage/structure/RSI/volume/Decision |
| 21 ~390px | PASS | No Stock 360 horizontal overflow; Analyze visible (tall control is shell/form cosmetic) |
| 22 P2A request | PASS | Route GET; explicit Analyze POST; duplicate Analyze disabled; different-symbol POST supersedes; invalid→valid recovery |

WIPRO Price Map manual check (completed-D1 close **167.32**): Major support
upper **169** → (167.32−169)/169×100 = **−0.994%** → displayed **1.0% below**.
Review trigger lower **169** → (169−167.32)/167.32×100 = **1.004%** → **1.0%
above**. Target 1 lower **178.14** → **6.5% above**. History high **266.25** →
**59.1% above**.

TI Support 1 upper **450.75**, close **521.60** → **15.7% above**.

Those screenshots also showed the presentation defects corrected in §22
(uneven zone precision, `₹-` P&L, Evidence wrap, duplicate unresolved copy,
tall 390px Analyze control, `NO_TRAD`/`E` wrap).

## 22. Presentation / numeric-format hardening (`9.244.0`)

Presentation-only. No DTO, composer, hydration, Price Map arithmetic, or
stored-value change.

Central SI helpers: `siMoney`, `siZoneShort`, `siPct`, `siRsi`, `siScore`,
`siInteger`, `siEnumLabel` (title-case typography; `friendlyLabel` leaves
`NO TRADE`), `siDisplayExplanation`.
Prices and zones use two-decimal INR; collapsed same-bound zones; signed
currency `-₹`; market/P&L % two decimals; Price Map distances stay one
decimal; RSI/score one decimal. Stock 360 uses No Trade / No Plan;
Evidence keeps raw enums. Empty quote/change snapshot cards omitted when
live quote is absent. Unresolved identity: header reason + UNAVAILABLE
statuses, no duplicate catalog card. Evidence table min-widths + stacked
cards at ≤720px. SI toolbar no longer `flex: 1` at narrow width; input and
Analyze capped at 3rem and stack.

Chart S1/MS label collision remains SI-P2C.

## 23. Final visual re-check (`9.244.0`, 2026-09-13)

Not a full 22-gate. Owner/Chief Architect source review of `9.244.0` passed.
This pass evidenced only the presentation fixes not shown in the earlier
WIPRO live-gate shots. No JS/CSS change.

| Check | Result | Observed | Shot |
|---|---|---|---|
| TI PARTIAL / no Decision | PASS | CURRENT + PARTIAL; no empty quote/change cards; SMA Up / SuperTrend Down readable; prices `₹xx.xx`; RSI `44.1` | `13-ti-partial-recheck.png` |
| ACMESOLAR portfolio money | PASS | Qty `418`; P&L **`-₹2,737.90`** (−1.60%); not `₹-`; Portfolio-owned HEALTHY | `14-acmesolar-pnl-recheck.png` |
| Invalid ZZNOPE999 | PASS | One reason `No instrument matched 'ZZNOPE999'.`; UNAVAILABLE statuses; no catalog-card duplicate; no stale identity; no chart host / Loading D1 void | `15-zznope999-recheck.png` |
| ~390px Stock 360 | PASS | Input/Analyze **40px** each (form **88px** stacked); no SI horizontal overflow (`scrollWidth === 390`); scan strip stacks; **No Trade** intact; Price Map readable; Evidence stacked cards readable; Analyze reachable | `16-wipro-390px-recheck.png`, `16b-wipro-390px-price-map.png`, `17-evidence-390px-recheck.png` |

Deferred (unchanged): chart S1/MS/RT labels → SI-P2C; Target 2/3 hierarchy;
written-summary verbosity → SI-P2D; DarvaX iframe; Decision/Evidence sparsity;
global sidebar. SI-P2C is **not started**.
