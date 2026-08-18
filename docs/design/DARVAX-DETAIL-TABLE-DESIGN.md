# DarvaX detailed view — redesign

Bringing the simple view's trade values into the detailed table, and making a
2,191-row table worth reading.

**Status:** 🔄 Design only — **no code written.** §5 decisions answered by me at
the owner's request (2026-08-17); §7 adds a third view he asked for.
**Designed:** 2026-08-17 · **Governing:** ADR-005 (explainability as data),
ADR-010 (no invented methodology), ADR-004 (no framework)

---

## 1. What the two views show today

The advisor screen gained a trade ticket at DX-8b. The detailed table did not
move, so the two views now describe the same sweep in different languages.

| Value | Simple view | Detailed table |
|---|---|---|
| Action (Buy / Wait / Sell) | ✅ chip | ❌ — only `State` and `Rule` |
| Buy above | ✅ | ❌ |
| **Stop loss** | ✅ | ❌ |
| **Risk per share** | ✅ | ❌ |
| Plain-English reason | ✅ leads | ❌ — expansion leads with the technical one |
| Distance in words | ✅ | ❌ `through` |
| Box range bar | ✅ | ✅ |

The table's six data columns are `signal_type`, `darvas_rule`, `close`,
`distance_to_breakout_pct`, `box_height_pct`, `rank` — every one of them
structural. **Nothing in the detailed view tells you what to do or where to get
out.**

## 2. The constraint that shapes everything: the data is not uniform

Measured on a real 2,191-instrument sweep:

| Action | Rows | has `trigger_price` | has `stop_price` | has `box_top` |
|---|---|---|---|---|
| `NO_ENTRY` | 1,562 | 0 | 0 | 1,550 |
| `WAIT` | 474 | 0 | 0 | 474 |
| `ENTER_ON_RETEST` | 68 | 68 | 68 | 68 |
| `ENTER` | 49 | 49 | 49 | 49 |
| `EXIT_IF_HELD` | 38 | 0 | 0 | 38 |

**A trigger and a stop exist for 117 rows out of 2,191 — 5%.** DX-3 records them
only where a breakout produced an entry, which is correct: there is no stop for a
trade nobody is in.

So literal parity is impossible, and pretending otherwise would produce three
columns that are 95% empty. Two honest moves instead:

**2.1 "Buy above" can be populated for 94% of rows, without inventing anything.**
The engine already falls back from `trigger_price` to `box_top` when ranking —
that is what `breakout_reference` records, and the distribution shows it:
`box_top` for 2,062 rows, `trigger_price` for 117. The column shows the level
the engine actually measured to, marked with which one it is.

**2.2 A blank stop is information, not a hole.** "—" in the Stop column means
*DarvaX has not computed a stop because this is not an entry yet.* That reads
correctly and matches the methodology. See §5 decision 3 for the alternative.

---

## 3. Proposed table

### 3.1 Replace the jargon columns rather than appending to them

Appending five columns to eight gives thirteen and an unusable table. But `State`
and `Rule` are what the action chip already encodes, and both stay in the row
expansion for traceability. That frees the space.

```
┌ ADVICE ─────┬ THE TRADE ───────────────────┬ PRICE ──────────────┬ STRUCTURE ─────────┐
│ Do   Symbol │ Buy above   Stop    Risk/sh  │ Now      Distance   │ Range        Width │
├─────────────┼──────────────────────────────┼─────────────────────┼────────────────────┤
│ BUY  BI     │ ₹66.99ᵗ    ₹60.29   ₹6.70    │ ₹76.81   ▲ above    │ ▁▃▅█▏        45.3% │
│ BUY  XTRANET│ ₹157.00ᵗ   ₹141.30  ₹15.70   │ ₹172.50  ▲ above    │ ▁▃▅█▏        11.8% │
│ WAIT ANANDR │ ₹2,176.20ᶜ    —        —     │ ₹2,174.7  0.07% away│ ▁▃█▁▏         3.1% │
│ SELL JGCHEM │     —          —        —    │ ₹606.15  below floor│ █▁▁▁▏        12.4% │
└─────────────┴──────────────────────────────┴─────────────────────┴────────────────────┘
  ᵗ prior day's high (the method's entry trigger)   ᶜ box ceiling
```

Nine columns in four labelled groups. The group header is what makes nine
readable: a reader scanning for risk does not have to parse the other six.

### 3.2 Sticky header

`NOT_ELIGIBLE` alone is 1,562 rows. The header currently scrolls away on the
first flick, so every column becomes unlabelled. `position: sticky` on `thead`,
two lines of CSS.

### 3.3 The row expansion leads with plain English

Today it opens with `explanation` — the technical trace. It should open with
`action_reason_plain`, then the technical reason, then evidence, then the stop
derivation and trace. Same order as the ticket's disclosure, so the two views
agree about what leads.

### 3.4 Distance in words, not `through`

`through` reads like an error and means the opposite. Same vocabulary as the
ticket: **▲ above** / **0.07% away** / **below floor**.

---

## 4. What this deliberately does not add

- **No profit target, no score, no star rating.** Unchanged from DX-8b: the
  method has a buy rule and a stop, and DX-5 found most of the measured edge is
  the exit rule and market drift rather than box detection.
- **No position sizing.** Risk per share only (ADR-010 keeps `sizing/` out).
- **No client-side derivation.** Every column reads a persisted field; risk per
  share is `buy − stop`, subtraction on two of them.
- **Nothing deleted.** `State`, `Rule`, `tier` and the full evidence trace all
  remain in the row expansion.

---

## 5. Decisions — answered 2026-08-17

The owner delegated these. Answers first, reasoning below.

| | Answer |
|---|---|
| **1. Grouping** | **1a — group the table by action.** Tier and action are near-duplicates and that duplication is the complaint that started DX-8; two views dividing the world differently is worse than either division. `tier` moves to the row expansion, where it stays traceable |
| **2. "Buy above"** | **2a — fall back to the box ceiling, marked with a superscript.** It is the level the engine already ranks against, so this reports a persisted fact rather than filling a column for the sake of it |
| **3. Prospective stop for watch rows** | **3a — show "—" for now.** The absence is true and informative. 3b is genuinely useful and is deferred to its own milestone precisely because it is *new persisted methodology output*, and a prospective stop shown beside live ones would be mistaken for one |
| **4. 2,191 rows** | **4a — measure first.** `NOT_ELIGIBLE` is collapsed by default so the common case is ~629 rows, and this session has repeatedly shown measurement beating assumption |

### The options as presented

### Decision 1 — group the table by action, or keep tier groups?

The table groups by **tier** (4 sections); the simple view groups by **action**.
They are near-duplicates, which was DX-8b's whole complaint, and leaving them
different means the two views disagree about how the world divides.

| Option | |
|---|---|
| **1a. Group by action** | Same shape as the simple view. 5 groups on this sweep (Buy 49 · Buy on dip 68 · Wait 474 · Sell if held 38 · Skip 1,562). `tier` moves to the expansion |
| **1b. Keep tier groups, add an action column** | Least churn; keeps two vocabularies side by side, which is the thing being complained about |

**Recommendation: 1a.**

### Decision 2 — how should "Buy above" behave when there is no trigger?

| Option | |
|---|---|
| **2a. Fall back to the box ceiling, marked** | Populated for 94% of rows, and it is exactly the level the engine already ranks against (`breakout_reference`) |
| **2b. Leave blank unless a trigger exists** | Strictly literal; leaves the column empty for 2,074 of 2,191 rows |

**Recommendation: 2a**, with the superscript marker so the two levels are never
confused.

### Decision 3 — should watch candidates get a prospective stop?

A `WAIT` row has no stop because no entry exists. A *prospective* stop — 10%
below the level it would buy above — is arguably the most useful number for
planning a trade you have not taken.

| Option | |
|---|---|
| **3a. Show "—"** | Honest and cheap. The absence correctly says "not a trade yet" |
| **3b. Engine computes and persists a prospective stop for watch rows** | Genuinely useful, and it is the deck's own 10% rule applied to a level the engine already has. But it is **new persisted methodology output**, so it needs its own milestone and must never be confused with a live stop |

**Recommendation: 3a now, 3b as a separate milestone if it proves wanted.**
Deriving it in the browser is not an option (ADR-005).

### Decision 4 — 2,191 rows × 9 columns

| Option | |
|---|---|
| **4a. Measure first** | Render the real sweep and time it; add paging only if measurably slow. `NOT_ELIGIBLE` is already collapsed by default, so the common case is ~629 rows |
| **4b. Cap per group with "show more"** | Predictable, but hides rows by default in a view whose purpose is completeness |
| **4c. Virtualise** | Correct at any scale, and a significant amount of hand-rolled code under ADR-004 |

**Recommendation: 4a.** This session has repeatedly shown measurement beating
assumption, and the default view is a quarter of the worst case.

---

## 6. Milestones

| | Scope |
|---|---|
| **DX-9a** | New column set with grouped headers, sticky header, action chip, plain distance wording; expansion reordered to lead with plain English. Grouping per decision 1. |
| **DX-9b** | Honest states re-verified at the new table, live; render timing per decision 4. |

DX-9a is one milestone rather than two because the column set and the grouping
are the same edit — splitting them would mean shipping a table whose groups and
columns disagree.

---

## 7. A third view: **Levels**

Darvas is a *visual* method — a box, a ceiling, a break above it. Both existing
views describe that in words and numbers; neither draws it. The owner asked for a
new view with proper trading levels, and this is the one thing the methodology
most obviously wants.

### 7.1 Three views, three questions

| View | Question | Form |
|---|---|---|
| **Advisor** | What do I do today? | text tickets, urgency-ordered |
| **Levels** *(new)* | Where are the prices? | a price ladder per instrument |
| **Table** | Show me everything | 2,191 rows, sortable |

No redundancy: each answers a question the others answer badly. The current
two-state toggle becomes a three-way segmented control.

### 7.2 The ladder

Five levels, drawn to scale on a vertical price axis, with the box as a filled
band and the region above its ceiling shaded as the breakout zone:

```
   XTRANET                                    BUY  [unvalidated]

   ₹172.50  ●─────────────────────────  NOW      +9.9% past trigger
                ░░░░░░░░░░░░░░░░░░░░░
   ₹157.00  ╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌  ENTRY    prior day's high
                ░░░ breakout zone ░░░
   ₹141.30  ▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬  STOP     risk ₹15.70 (10.0%)
   ₹136.90  ═════════════════════════  CEILING  the level it broke above
            ███████ the box ███████
   ₹122.50  ═════════════════════════  FLOOR

   Your stop sits ₹4.40 ABOVE the breakout level.
```

The last line is the point. Compare BI, same 10% rule:

```
   ₹75.00   ═════════  CEILING          ← stop is BELOW this
   ₹66.99   ╌╌╌╌╌╌╌╌╌  ENTRY
   ₹60.29   ▬▬▬▬▬▬▬▬▬  STOP
   Your stop sits ₹14.71 BELOW the breakout level — a stop-out
   gives back the whole breakout.
```

**Measured, not invented.** Both sentences are a comparison of two persisted
numbers, stated as fact. No recommendation is attached and no rule is added: the
methodology says 10% below entry, and this reports where that lands relative to a
level the engine already recorded. Per ADR-005 the comparison is computed and
persisted by the engine, not assembled in the browser.

### 7.3 Which rows get a ladder

A ladder needs levels, and §2 measured that only entries have five. So Levels
shows the actionable set and nothing else:

| Group | Rows on this sweep | Levels available |
|---|---|---|
| Your positions — sell | your holdings | 3 + your entry and stop |
| Your positions — hold | your holdings | 3 + your entry and stop |
| Buy candidates | 117 | **5** |
| Approaching (`WAIT`, nearest 12) | 474 → 12 | 3 (floor / ceiling / now) |

`NO_ENTRY` is excluded: 1,562 instruments with no box to draw. Reaching them is
what the Table view is for.

### 7.4 Scale

Prices on this sweep span ₹74 to ₹23,500, so the axis is per-card and relative,
with every level labelled in rupees. A shared axis across cards would render most
ladders as a flat line.

### 7.5 What it must not become

- **No candlestick chart.** Price history is not what the method reads, and a
  chart would invite reading it — plus ADR-004 rules out a charting library.
- **No target line.** There is no target in the method.
- **No colour that implies quality.** Colour marks *kind* of level (entry, stop,
  structure), never how good a candidate is.

### 7.6 Milestones

| | Scope |
|---|---|
| **DX-9c** | Persist the stop-versus-ceiling comparison on the screen result (engine-side, ADR-005). **No UI.** |
| **DX-9d** | The Levels view: three-way view switch, ladder rendering in plain CSS, the four groups above. |

DX-9c is separate and first for the same reason DX-8a was: it is a data question,
and shipping the ladder without it would mean the browser deriving the one
sentence on the card that carries real insight.

---

## As built (DX-9a/DX-9b)

Twelve columns, not the nine originally designed, and grouped three ways rather
than four. What changed from the design, and why:

| Design | Built | Reason |
|---|---|---|
| Drop `State` and `Rule` | `Rule` kept in the context group; `State` folded under the symbol as a sub-label | The persisted explanation is phrased in terms of the signal state, so removing it entirely would leave the expanded text referring to something the row no longer shows |
| Four groups (ADVICE / THE TRADE / PRICE / STRUCTURE) | Three (identity / **the trade** / context) | Four labels over twelve columns produced more grouping furniture than grouping. Only one group needs to stand out — the money you would act on — and it is the one that carries the banded background |
| Sticky header | Sticky **symbol column** | The header was already the smaller problem; twelve columns overflow horizontally, and scrolling right lost the symbol, which made every other cell unattributable |

**Risk is measured from the current price, never from the buy level.** The stop
is defined 10% below the trigger, so risk-to-trigger is 10% on every row by
construction — the tautology the owner caught on the Levels card. Measured on the
live sweep: BI's real risk from ₹76.81 down to ₹60.29 is **21.5%**, not 10%.

The arithmetic lives in `riskFromHere()`/`liqCrore()`, **shared with the Levels
card**, because two copies would eventually disagree and the owner would have no
way to tell which view was lying. Pinned by
`test_risk_arithmetic_is_defined_exactly_once`.

### What the browser caught that the tests did not

- **The action chip rendered unstyled.** The new cell emitted `act-enter`
  (lowercase, `act-` prefix) while every rule in `darvax.css` is `.act.a-ENTER`.
  Correctly labelled, no colour, nothing failed. The guard written for it was
  itself **vacuous on first attempt** — it collected class prefixes into a set,
  so the Advisor view's correct chip satisfied it while the broken one sat beside
  it. Verified by reintroducing the bug: fails, then passes on restore.
- **`Now` printed the raw decimal** — `1635.1` one column away from `₹66.99`.
  Same kind of number, two notations, adjacent.
- **A hardcoded `colspan="8"`** in the empty-tier and detail rows, which the
  twelfth column would have silently under-spanned. Both now track
  `COLUMNS.length`.
