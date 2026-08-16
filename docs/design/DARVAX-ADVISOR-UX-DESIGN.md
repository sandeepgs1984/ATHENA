# DarvaX advisor dashboard — design

Turning the DarvaX screener into a trading-advisor surface: a ranked shortlist
of ~10 candidates and a per-symbol action the owner can read at a glance
(**enter / wait / hold / exit / no entry**).

**Status:** ✅ Design approved 2026-08-16; decisions recorded in §4. Implementing
as DX-7a→d.
**Designed:** 2026-08-16 · **Governing:** ADR-010 (satellite isolation),
ADR-005 (explainability as data), ADR-004 (no frontend framework)

---

## 1. What exists today

DX-6c shipped a *screener*: four tiers, sortable columns, a box visualisation,
row expansion, and every honest empty state.

| Tier | From signal | Count on the 2,191 sweep |
|---|---|---|
| `ACTIONABLE` | `BREAKOUT`, `BREAKOUT_RETEST` | 117 |
| `WATCH` | `INSIDE_TOPMOST_BOX` | 476 |
| `EXIT_RELEVANT` | `BELOW_BOX_BOTTOM` | 35 |
| `NOT_ELIGIBLE` | `NOT_IN_TOPMOST_BOX`, `NO_BOX` | 1,563 |

A screener answers *"what matched?"*. An advisor answers *"what should I do,
and about which ten things first?"*. That is the gap this design closes.

## 2. Three constraints that shape everything

### 2.1 DarvaX cannot see what you own

Its entire view of ATHENA is `DarvaxMarketDataPort` — `list_instruments`,
`recent_candles`, `candles_between`. **No positions, no portfolio.** ATHENA has
an `owner_positions` table (3 rows today), but reading it would widen the import
surface ADR-010 §1 pins and a DX-4 test asserts.

This is not a detail. Of the five actions requested:

| Action | Needs a position? | Attributable today |
|---|---|---|
| **ENTER** | no | ✅ rule B breakout |
| **WAIT** | no | ✅ rule A, inside topmost box |
| **NO ENTRY** | no | ✅ no box / not topmost |
| **HOLD** | **yes** | ❌ meaningless without knowing you hold it |
| **EXIT** | **yes** | ⚠️ today's `EXIT_RELEVANT` is honestly named — it means *"rule C fired; relevant **if** you hold it"* |

**Decision 1 below.** Without resolving it, "hold" and "exit" are decoration.

### 2.2 "Best 10" is a ranking claim, and DarvaX has no quality score

DX-6a deliberately implemented **two** measured quantities — distance-to-breakout
and box height — and *deferred* bars-in-box and volume expansion for lack of
evidence. There is no composite "quality" score, and ADR-010 forbids inventing
methodology the deck does not support.

So "the 10 best" cannot be delivered as stated. What *can* be delivered is a top
10 by one stated, measured, sortable quantity — which is a fact rather than a
judgement. **Decision 2.**

### 2.3 DX-5 says this methodology has not earned confident phrasing

The negative controls measured that **roughly two-thirds of DarvaX's expectancy
comes from the exit rule operating in a rising market, not from box detection**;
random entries with identical exits returned +2.80% against the real +4.09%, and
the box-detection increment (+1.23pp) is only marginally significant.

A panel headed *"Top 10 Best Trades"* launders that into confidence the evidence
does not support. The label `EXPERIMENTAL_UNVALIDATED` is on every DarvaX payload
for exactly this reason, and a redesign is the easiest place to quietly lose it.
**It must survive this redesign, prominently.**

---

## 3. Proposed design

### 3.1 The action vocabulary — derived in the engine, persisted, never in JS

ADR-005 requires the engine that produces a value to compute and persist its
explanation; the UI renders and never re-derives. So `action` becomes a **new
persisted column** on `darvax_screen_results`, alongside a plain-language
`action_reason`, exactly as `tier` and `explanation` already are.

| Action | Rule | Reason text (persisted, illustrative) |
|---|---|---|
| `ENTER` | `BREAKOUT` and close > prior-day high (deck p.44) | "Cleared the box ceiling at ₹X on rule B; entry trigger is ₹Y." |
| `ENTER_ON_RETEST` | `BREAKOUT_RETEST` | "Broke out and is retesting the ceiling as support." |
| `WAIT` | `INSIDE_TOPMOST_BOX` | "Consolidating inside the topmost box; 2.4% below the ₹Y trigger." |
| `EXIT` | `BELOW_BOX_BOTTOM` **and** held | "Closed below the box floor — rule C exit." |
| `HOLD` | held, no rule-C, above stop | "Above the 10% stop at ₹Z; box intact." |
| `NO_ENTRY` | `NOT_IN_TOPMOST_BOX`, `NO_BOX` | "No topmost box has formed." |

`HOLD` and `EXIT` are emitted **only** when a position is known; otherwise the
row keeps today's honest conditional framing. That is a property of the data,
not a UI choice.

### 3.2 Layout

Three zones, top to bottom, hand-rolled CSS grid (ADR-004 — no framework, no
build step; DarvaX's own assets, so ATHENA's `?v=` discipline is untouched):

```
┌──────────────────────────────────────────────────────────────┐
│  EXPERIMENTAL · UNVALIDATED — advisory only, never an order   │  ← persistent
├──────────────────────────────────────────────────────────────┤
│  YOUR POSITIONS (n)          [HOLD 2] [EXIT 1]               │  ← only if D1
│  Symbol   Entry   Now    P&L    Stop    Action   Why          │     resolved
├──────────────────────────────────────────────────────────────┤
│  TOP 10 — nearest to breakout trigger                         │
│  ┌────────┬─────────┬──────────┬─────────┬──────────────┐    │
│  │ RANK 1 │ RATNAVEER │ ENTER  │ ₹230.16 │ box ▇▇▇▁    │    │
│  │        │ trigger ₹228.40 · box 6.2% · +0.8% past    │    │
│  └────────┴─────────┴──────────┴─────────┴──────────────┘    │
├──────────────────────────────────────────────────────────────┤
│  FULL SCREEN  [Enter 117] [Wait 476] [Exit 35] [None 1563]   │  ← DX-6c table
└──────────────────────────────────────────────────────────────┘
```

The existing DX-6c table becomes the third zone rather than being replaced —
it already handles sorting, filtering, row expansion, sweep progress, cancel,
staleness and the methodology-digest mismatch. Rebuilding it would discard
tested behaviour for no gain.

### 3.3 What each top-10 card shows

Only quantities the engine already persists: `close`, `box_top`, `box_bottom`,
`trigger_price`, `distance_to_breakout_pct`, `box_height_pct`,
`breakout_reference`, `explanation`, plus the new `action` / `action_reason`.
**No new number is computed in the browser.**

The box visualisation is DX-6c's, reused at card scale.

### 3.4 Honest states, kept

Every state DX-6c built stays reachable and must be designed for, not bolted on:
no sweep yet · sweep running with progress · cancelled · partial with skip
reasons · stale as-of · methodology-digest mismatch · empty tier. A dashboard
that only looks good with fresh data is not finished.

---

## 4. Decisions — resolved 2026-08-16

| | Owner's decision |
|---|---|
| **1. Positions** | **1a — DarvaX keeps its own position list.** Not the recommendation below, and taken knowingly: it keeps the two lanes genuinely separate, which is ADR-010's own principle, at the cost of a second record of what is held. **Consequence:** no ADR amendment is needed, but DX-7b grows — DarvaX needs its own `darvax_positions` table, write API and editing UI, none of which 1b would have required. The drift risk is real and is accepted; nothing reconciles the two lists, so a position closed in ATHENA stays open in DarvaX until edited. |
| **2. Top-10 ranking** | **2a — nearest to breakout trigger**, panel titled accordingly. As recommended. |
| **3. Label** | **3b — a badge on each action chip**, rather than a page banner. Defensible and arguably stronger: the warning sits at the point of decision, where a banner is learned and ignored. Requirement carried forward: **the badge must appear on every `ENTER`/`HOLD` chip**, not only in the shortlist, or the redesign becomes the place the warning disappears. |

The original options and reasoning are kept below, because a decision is only
reviewable against the alternatives it was chosen over.

### The options as presented

### Decision 1 — how does DarvaX learn what you hold?

| Option | What it means | Cost |
|---|---|---|
| **1a. DarvaX keeps its own position list** | Owner records DarvaX-lane positions in DarvaX's own store. Self-contained, no ADR change, keeps the lanes genuinely separate — which is ADR-010's whole point. | Duplicate entry; can drift from ATHENA's `owner_positions` |
| **1b. Widen the port to read ATHENA positions** | One new read-only method on `DarvaxMarketDataPort`. Single source of truth. | **Needs an ADR-010 amendment** — it widens the pinned surface a test currently guards |
| **1c. Stay position-free** | `EXIT_RELEVANT` keeps its conditional wording; no `HOLD` at all. | Cheapest and honest, but does not deliver the advisor experience asked for |

**Recommendation: 1b**, as an explicit ADR-010 amendment. 1a duplicates the
position record and two sources of truth about what you own is a bad trade for a
single-user system; 1c does not answer the request. The amendment is small and
one-directional — DarvaX reads positions, ATHENA still learns nothing about
DarvaX.

### Decision 2 — what orders the top 10?

| Option | Basis |
|---|---|
| **2a. Nearest to breakout trigger** | `distance_to_breakout_pct`, already measured, already the default sort |
| **2b. Composite score** | Weighted blend of distance, box height, bars-in-box, volume expansion |
| **2c. Tightest box** | `box_height_pct` — a tight box means a nearer, better-defined stop |

**Recommendation: 2a**, with the panel titled **"Nearest to trigger"** rather
than "Best". 2b requires inventing weights DX-6a deferred for lack of evidence,
and a made-up composite presented as "best" is precisely the false precision
DX-5 warns about. 2a is a fact; "best" is a claim DarvaX cannot support.

### Decision 3 — how prominent is the unvalidated label?

**Recommendation: a persistent header banner**, not a footnote — stating that
the methodology is unvalidated and that DX-5 attributes most of its measured
edge to the exit rule and market drift rather than to box detection. This is the
single most important honesty decision in the redesign.

---

## 5. Proposed milestones

Each small enough to review in one sitting; none starts before the previous is
approved.

| | Scope |
|---|---|
| **DX-7a** | `action` + `action_reason` persisted on screen results; schema v4→v5; engine-side derivation and tests. Position-free actions only: `ENTER`, `ENTER_ON_RETEST`, `WAIT`, `EXIT_IF_HELD`, `NO_ENTRY`. **No UI.** |
| **DX-7b** | DarvaX's own `darvax_positions` store, write API and validation (Decision 1a); adds `HOLD` and position-confirmed `EXIT`. `EXIT_IF_HELD` stays for symbols with no recorded position, so nothing is renamed. **No UI.** |
| **DX-7c** | Top-10 panel, positions zone with editing; the DX-6c table becomes zone 3; the unvalidated badge on every action chip. |
| **DX-7d** | Every honest state re-verified at the new layout; live-data verification against the real 2,191 sweep. |

`EXIT_IF_HELD` is deliberately named so DX-7b is **additive**: it gains `HOLD`
and `EXIT` without redefining a value DX-7a already persisted. Renaming a
persisted action between milestones would break replay of stored sweeps.

DX-7d is not a formality: this session's live checks repeatedly caught what
fixtures missed — WATCH tier ordering alphabetically, freshness computed in UTC,
a stale server serving DX-1 code.

---

## 6. What this design deliberately does not do

- **No order placement, ever.** `ENTER` is advice the owner acts on manually in
  their broker. Nothing here touches an order API, and none exists in the repo.
- **No new methodology.** Every action maps to a DAR-CARD rule the engine
  already evaluates; no new signal type, no new threshold.
- **No client-side derivation.** ADR-005: if a number or a reason appears on
  screen, an engine computed and persisted it.
- **No removal of the experimental label**, which remains an owner decision on
  evidence (DX-5 §7) and is not granted by a nicer interface.
