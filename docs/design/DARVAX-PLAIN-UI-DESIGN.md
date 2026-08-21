# DarvaX plain-language UI — redesign

Making the advisor readable by a trader rather than by someone who has read
ADR-010. The owner's verdict on DX-7c: *"not user friendly, very complicated,
not able to understand for a normal user."*

**Status:** 🔄 Design only — **no code written.** Decisions in §5 needed first.
**Designed:** 2026-08-16 · **Governing:** ADR-005 (explainability as data),
ADR-010 (no invented methodology), ADR-004 (no framework)

---

## 1. What is actually wrong

Read from the shipped screen, not from intuition.

### 1.1 The screen speaks two languages at once

| Vocabulary | Values |
|---|---|
| **Tier** | `ACTIONABLE` · `WATCH` · `EXIT_RELEVANT` · `NOT_ELIGIBLE` |
| **Action** | `ENTER` · `ENTER_ON_RETEST` · `WAIT` · `HOLD` · `EXIT` · `EXIT_IF_HELD` · `NO_ENTRY` |

They answer the same question. A reader has to learn both and then work out
that "ACTIONABLE" and "ENTER" are the same news. **The action is the answer;
the tier is an implementation detail of how it was derived.**

### 1.2 Internal enum names are shown to a human

`BREAKOUT_RETEST`, `INSIDE_TOPMOST_BOX`, `NOT_IN_TOPMOST_BOX` are Python
identifiers rendered as UI chips. They are precise and they are not English.

### 1.3 Column headings that require the methodology to decode

`TO BREAKOUT → "through"`, `BOX HT`, `RULE → B`. "through" is the worst: it
means *price is already past the level*, which is good news, and it reads like
an error.

### 1.4 The numbers a trader needs are missing

This is the serious one. The screen says **enter** and does not say **where to
get out**:

| Needed to act | On screen today |
|---|---|
| Buy above | buried as "to breakout", shown as a percentage |
| **Stop loss** | **absent** |
| **Risk per share** | **absent** |
| Current price | ✅ `close` |
| Why | ✅ but phrased in DAR-CARD terms |

`DarvaxSignal` carries a fully derived `stop` — level, basis and a written
derivation. `ScreenResult` never copied it, so the screener cannot show it.
**Rule B mandates that stop** ("A 10 percent stop-loss should be set on the
first breakout"), so a screen that omits it is not merely terse, it is
recommending half a trade.

### 1.5 Density

Eight columns × 2,191 rows, four tier groups, sortable headers, expandable rows.
That is a *data browser*. An advisor's first screen should answer "what do I do
today?" in one glance and keep the browser one click away.

---

## 2. The principle

> **Say what to do, at what price, with what risk, in one sentence of English.
> Keep the methodology one click away, not in the reader's face.**

Nothing is removed — the tier table, evidence trace and DAR-CARD citations all
stay reachable. What changes is what leads.

---

## 3. Proposed screen

### 3.1 One question, three answers, in urgency order

```
┌──────────────────────────────────────────────────────────────────┐
│  EXPERIMENTAL · UNVALIDATED                                       │
├──────────────────────────────────────────────────────────────────┤
│  SELL — 1 holding needs action                                    │
│  ┌────────────────────────────────────────────────────────────┐  │
│  │ JGCHEM            SELL                          −13.4%     │  │
│  │ Now ₹606.15 · you paid ₹700 · stop was ₹630                │  │
│  │ Price fell through your stop. The method says close it.     │  │
│  └────────────────────────────────────────────────────────────┘  │
├──────────────────────────────────────────────────────────────────┤
│  HOLD — 1 holding, nothing to do                                  │
│  BAJAJ-AUTO   ₹11,700  +6.4%   stop ₹9,900                        │
├──────────────────────────────────────────────────────────────────┤
│  BUY — 10 candidates closest to their trigger      [unvalidated]  │
│  ┌────────────────────────────────────────────────────────────┐  │
│  │ 1  RATNAVEER                                   BUY          │  │
│  │    Buy above    ₹223.75                                     │  │
│  │    Stop loss    ₹201.38        risk ₹22.37/share (10%)      │  │
│  │    Now          ₹230.16        already above the trigger    │  │
│  │    Price broke above its recent high range.                 │  │
│  └────────────────────────────────────────────────────────────┘  │
├──────────────────────────────────────────────────────────────────┤
│  ▸ Everything else (2,178)          ▸ Detailed screener view      │
└──────────────────────────────────────────────────────────────────┘
```

Sell first because it is time-critical; buy candidates next; the 2,178 rows with
nothing to say collapse behind one line.

### 3.2 Plain words, with the methodology behind a disclosure

| Today | Proposed | Methodology (on expand) |
|---|---|---|
| `BREAKOUT` / ACTIONABLE | **Buy** | Darvas rule B — buy above the topmost box |
| `BREAKOUT_RETEST` | **Buy on retest** | rule B, on the retest |
| `INSIDE_TOPMOST_BOX` / WATCH | **Wait** | rule A |
| `BELOW_BOX_BOTTOM` / EXIT_RELEVANT | **Sell** | rule C |
| `NOT_IN_TOPMOST_BOX` / NO_BOX | **Skip** | rule D |
| "to breakout: through" | **already above the trigger** | |
| "box ht 15.12%" | **trading range 15.1% wide** | |

### 3.3 The trade ticket

Every buy candidate shows the same four lines, because a trade is not actionable
without all four:

| Line | Source |
|---|---|
| **Buy above** | `trigger_price` — the prior day's high (deck p.44) |
| **Stop loss** | `signal.stop.price` — **needs to be persisted onto the screen result** |
| **Risk per share** | `trigger − stop`, arithmetic on two persisted numbers |
| **Now** | `close`, with distance in plain words |

Risk per share is division, not methodology — it introduces no rule the deck
does not state. **Position sizing is deliberately excluded**: how many shares to
buy is ATHENA's `sizing/` concern and importing it would breach ADR-010.

---

## 4. What this explicitly does not do

- **No profit target.** Darvas had none — he rode trends on a trailing stop.
  Inventing one would be exactly the fabrication ADR-010 forbids.
- **No conviction score, no star rating, no "strong buy".** DX-5 measured that
  most of the edge is the exit rule and market drift, not box detection.
  Simplifying the language must not smuggle in confidence the evidence denies.
- **No removal of the unvalidated badge**, which stays on every buy.
- **Nothing deleted.** The tier table, evidence and rule citations move behind a
  disclosure; they do not disappear.

---

## 5. Decisions — resolved 2026-08-16

| | Owner's decision |
|---|---|
| **1. Wording** | **1b — a second plain-language field.** Not the recommendation; taken knowingly. **The risk is drift**: two sentences about the same advice, free to disagree or to decay into copies of each other. Mitigated mechanically rather than by discipline — both are produced at one call site, and tests assert that every action yields *both*, that the plain one contains **no** rule jargon, and that the technical one **does**. Those two assertions together stop the fields collapsing into each other in either direction. |
| **2. Layout** | **2a — simple by default, detailed view one click away.** As recommended. |
| **3. Risk** | **3a — risk per share only.** As recommended; no sizing concepts enter DarvaX. |

### The options as presented

### Decision 1 — where does the plain sentence come from?

ADR-005 requires the engine to compute and persist the explanation; the UI
renders it. So a plain-English sentence must also come from the engine.

| Option | |
|---|---|
| **1a. Rewrite `action_reason` in plain English**, keep the DAR-CARD citation in the existing `explanation` | One sentence per result, no duplication. The rule reference moves to the disclosure, where `explanation` already lives |
| **1b. Add a second field** (`action_reason_plain`) beside the technical one | Both available; two strings to keep in step, and two places to get wrong |
| **1c. Translate in JavaScript** | **Rejected** — a second source of truth for advice, which is the thing ADR-005 exists to prevent |

**Recommendation: 1a.** `explanation` already carries the technical trace, so
the plain sentence replaces jargon in the one field the owner reads first
without losing anything.

### Decision 2 — how far does the simple view go?

| Option | |
|---|---|
| **2a. Simple by default, "Detailed view" toggle** | Advisor first; the DX-6c table one click away |
| **2b. Both always visible** | No mode to learn, but the page stays long and dense |
| **2c. Replace the table entirely** | Loses sorting, filtering and the full universe — too much |

**Recommendation: 2a.**

### Decision 3 — how much risk arithmetic?

| Option | |
|---|---|
| **3a. Risk per share only** | Pure arithmetic on persisted values; no sizing concepts enter DarvaX |
| **3b. Add a capital-per-trade input and show ₹ risk + share count** | More useful, but position sizing is ATHENA's `sizing/` module and ADR-010 keeps DarvaX out of it |

**Recommendation: 3a**, with 3b as a later ADR question if it proves needed.

---

## 6. Milestones

| | Scope |
|---|---|
| **DX-8a** | Persist `stop_price` and `stop_basis` onto `ScreenResult` (schema v6→v7); add `action_reason_plain` beside the technical reason per Decision 1b. **No UI.** |
| **DX-8b** | The three-section advisor screen, trade tickets, plain labels, detailed-view toggle. |
| **DX-8c** | Every honest state re-verified at the new layout, plus the DX-7d states still outstanding; live browser verification. |

DX-8a lands first and alone because the missing stop is a correctness gap, not a
presentation one: it is worth shipping even if the visual redesign is deferred.
