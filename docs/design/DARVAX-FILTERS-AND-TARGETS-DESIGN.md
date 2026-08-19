# DarvaX filters, scanners and the target question

Two owner requests: conviction filters (market cap, volume breakouts) on the
DarvaX list, and a target price per symbol.

**Status:** 🔄 Design only — **no code written.** One of the two requests cannot
be met as asked, and §2 says why rather than quietly substituting something else.
**Designed:** 2026-08-18 · **Governing:** ADR-010 (no invented methodology),
ADR-005, ADR-011 (universes/eligibility)

---

## 1. Filters — what the data supports, measured

| Filter | Feasible? | Evidence |
|---|---|---|
| **Volume expansion** on the breakout | ✅ but needs engine work | 1,394,149 daily candles, only 924 with `volume=0` (0.07%), no NULLs |
| **Liquidity** (traded value/day) | ✅ | Computed for **2,191 of 2,604** — median **₹7.18 cr/day**, 10th pct ₹0.07 cr, 90th pct ₹143.89 cr |
| **Index membership** (Nifty 50 / Next 50 / Midcap 100) | ✅ but thin | Covers **200 of 2,604 — 7.7%.** 92.3% of the universe has no index tier |
| **Box height / tightness** | ✅ already persisted | `box_height_pct` on every screen result |
| **Distance to buy level** | ✅ already persisted | the current ranking key |
| **Market capitalisation** | ❌ **not possible today** | see §1.1 |

### 1.1 Market cap does not exist anywhere in ATHENA

Checked every table: no `market_cap`, no `shares_outstanding`, no free-float
column. `symbol_master` holds series, board, lot and tick — nothing about size.
And the Kite instrument dump reports **`last_price = 0` for 100% of rows**, so
even price × shares is unavailable, and the share count is absent regardless.

**Market-cap filtering therefore requires a new versioned data source** — NSE's
own equity list with capitalisation, or a fundamentals feed — obtained and
snapshotted the way `data/index_constituents/<effective-date>/` already is. That
is a data-acquisition milestone, not a UI one, and inventing a proxy and calling
it market cap would be worse than not offering it.

**What substitutes honestly, and arguably better for trading:** *liquidity*.
Market cap tells you how large a company is; **traded value tells you whether you
can get out of the position**, which is the question conviction actually rests
on. It is computable today for every screened symbol, and the spread is wide
enough to be a useful filter — ₹0.07 cr/day at the 10th percentile against
₹143.89 cr at the 90th is a factor of 2,000.

Index membership stays available as a true size tier, but at 7.7% coverage it can
only ever be a *narrowing* filter ("Nifty 50 only"), never a classification of
the list.

### 1.2 Volume expansion needs the signal engine extended first

DX-6a deferred volume expansion as a ranking quantity for a stated reason:
`DarvaxSignal` records `close`, `box_top`, `box_bottom` and `trigger_price` as
structured fields **but no volume measure at all**. The evidence trace holds
`bars_examined`, which is the lookback size, not volume.

So a volume filter is not a UI feature. It requires DX-3 to measure and persist
something like breakout-day volume against its 20-day median — and, as DX-6a
noted, **it cannot backfill signals stored before it**. Screens taken today would
show the filter as unavailable rather than as zero.

Doing it in the browser is not an option: it would mean the UI reading candles,
which the screening layer deliberately cannot do (ADR-005, and the purity
property tested in DX-7b).

---

## 2. The target question — answered honestly

**No, and this one is not a data gap: the methodology has no target.**

Darvas did not take profit at a level. He raised his stop as each new box formed
and stayed in until the stop was hit. The DAR-CARD has four rules — hold in the
topmost box, buy above it, sell below a new box bottom, no reason outside it —
and **none of them names a price to sell into strength**. ADR-010 forbids DarvaX
inventing methodology the deck does not state, and this file has three tests
asserting no target line exists precisely because it is the most tempting thing
to add.

A projected target would also be the single most misleading number the screen
could carry: DX-5 measured that most of DarvaX's apparent edge is the exit rule
and market drift rather than box detection, and the box-detection increment is
only marginally significant. Printing "target ₹92" on that evidence base would
manufacture confidence the methodology has not earned.

### 2.1 What can be offered instead, and why each is honest

| Option | What it is | Honest? |
|---|---|---|
| **2a. R-multiples** | "1R = ₹16.52 · 2R = ₹109.85 · 3R = ₹126.37" — what a 2× or 3× return *on the risk already shown* would be | ✅ Arithmetic on the stop distance. Makes no claim price will get there; it answers "what would 2:1 look like" |
| **2b. The trailing stop, made explicit** | Darvas' actual answer to the upside: as a new higher box forms, the stop moves up under it. Show where the stop would move next | ✅ **This is the methodology**, currently invisible in the UI |
| **2c. Measured move** (project box height above the breakout) | A common charting convention: ₹75 ceiling + ₹23.38 box height = ₹98.38 | ❌ Not in the deck. It looks like Darvas and is not |
| **2d. A predicted target** | Any number claiming where price will go | ❌ Fabrication |

**Recommendation: 2a and 2b together.** R-multiples give the planning number a
trader wants without predicting anything, and the trailing stop is the deck's own
mechanism for exits — surfacing it answers the real question behind "what's my
target?", which is *when do I get out on the way up?*

2b needs the box history the engine already sees: the evidence trace records
`boxes_completed` and `latest_completed_box`, so the data exists but is not
structured for a UI to read.

---

## 3. Where filters belong

Not a new view. The Advisor, Levels and Table views all render the same
`screen.rows`, so a filter bar above the mode switch narrows all three at once —
otherwise "filtered" means something different depending on which tab is open.

```
[ Filter symbol… ]  [ Liquidity ▾ ]  [ Size ▾ ]  [ Box ▾ ]   Advisor | Levels | Table
                     any / ≥₹1cr      any / N50      any
                     ≥₹5cr / ≥₹25cr   N100 / Midcap  ≤10% / ≤20%
```

Every filter states its coverage. A liquidity filter says how many symbols it
could not evaluate rather than silently dropping them — the same discipline the
sweep already applies to skips.

---

## 4. Milestones

| | Scope |
|---|---|
| **DX-10a** | Persist per-symbol liquidity (median traded value over a stated window) on the screen result, engine-side. **No UI.** |
| **DX-10b** | Filter bar over all three views: liquidity, index tier, box height. Each states coverage. |
| **DX-10c** | R-multiples on the Levels card, labelled as *not a prediction*. |
| **DX-10d** | Extend DX-3 to measure and persist breakout volume against its median, then add the volume filter. Cannot backfill; screens taken before it report the filter unavailable. |
| **DX-10e** *(only if wanted)* | Acquire and version a market-cap source, then add a true size filter. Data acquisition, not UI. |

DX-10d is last among the implemented ones because it is the only item requiring a
change to the signal engine, which is the most load-bearing code in DarvaX and
the one place a mistake corrupts every stored signal.

---

## 8. DX-10c as built — the target question, answered

### 8.1 There is no target, and the deck is the reason

The owner asked for a target price. DarvaX does not show one, and this is the
argument rather than a preference:

- Darvas took profit at no level. He raised the stop and let the trend end
  itself.
- The DAR-CARD, as quoted verbatim in `screening/engine.py`, defines exactly two
  exits: **rule B**'s 10% stop, and **rule C** — *"if the price falls below the
  bottom … the stock is a SELL."*
- **Rule C is the trailing stop.** As each new higher box forms, its floor rises,
  and rule C exits at that rising floor. No separate trailing mechanism needed to
  be invented, and none was: the floor is already drawn on every Levels card.

So a "trail your stop to ₹X" advisory was considered and **rejected** — it would
have been a recommendation the deck never makes, and ADR-005 would in any case
require the engine to compute and persist it rather than the UI to synthesise it.

### 8.2 What is shown instead: R

`R = buy level − stop` — the per-share risk the methodology itself defines. The
card shows `R`, then 1R / 2R / 3R measured upward from the buy level, then how
far price has **already** travelled in the same unit.

The last of those is the one that changes decisions. A candidate sitting at
`already +1.5R` has spent one and a half times the trade's risk before the owner
has paid anything for it — measured on BI in the live sweep: buy level ₹66.99,
stop ₹60.29, R = ₹6.70, price ₹76.81, so **+1.5R already gone**.

This predicts nothing. It is division. The label says so, and
`test_the_r_multiple_scale_denies_being_a_target` fails if that wording is
removed.

### 8.3 A guard that had to be rewritten rather than relaxed

`test_no_profit_target_is_invented` banned the substring `"profit target"` and
therefore fired on the R label, whose entire purpose is to state that the method
has none. A keyword ban cannot distinguish an invention from a denial of one, so
it now checks the two things that actually constitute inventing a target: a
**field** that stores one, and prose that **offers** one (every occurrence of the
phrase must be negated). Strictly stronger than the version it replaced.

### 8.4 Honest states added

| State | Before | Now |
|---|---|---|
| Sweep recorded no liquidity | Choosing any threshold emptied the list and reported *"0 of 2191 match · 2191 excluded because their liquidity could not be measured"* — true, useless, and reads as a dead market | Control **disables itself**, relabels to *"Liquidity: not in this sweep"*, states the remedy (re-run the sweep) in its tooltip and in the note. Its value is cleared, because a disabled `select` still submits one |
| Sweep record reports fewer evaluated than the rows on screen | *"0 instrument(s) screened"* printed above 2,191 rows | Reports the row count, then says the record did not finish and to re-run to be sure. Flagged as an error state |

Both were found on the owner's real database, not in a fixture.

### 8.5 Filter labels — two attempts, and what the second one got wrong

**Attempt 1** named the options for the picture: `Stop above breakout`. Owner:
not understandable. Correct — it describes the geometry and leaves the reader to
derive the consequence.

**Attempt 2** put the consequence in the option text: `Stop keeps part of the
breakout`. Owner: *"more confusing and not at all user friendly."* Also correct,
and the mistake is worth naming: **an option is a label, and a label that has
become a sentence is doing the wrong job.** Compressing a causal explanation into
a dropdown gives you neither the precision of the short form nor the clarity of
the long one.

**Attempt 3 — the split.** The option states the fact, briefly and precisely.
The plain meaning goes in the filter note under the bar, where a full sentence
fits and can be read once rather than re-read on every glance at the control.

| Control | Option (the fact) | Note (the meaning) |
|---|---|---|
| Stop-loss | `Stop-loss below the breakout level` | *"Showing only entries whose stop-loss sits below the level price broke out from — if the stop-loss is hit, price has fallen all the way back into its old range and the whole breakout is given up."* |
| Box height | `Tight box — 10% or less` | *"Box height is how tall the price range itself is — from its floor up to the ceiling that price broke out of, as a percentage of the floor. It is not measured from your buy level."* |

### 8.6 Say "stop-loss", not "stop"

The owner asked: *"stop means stop loss?"* Having to ask is conclusive evidence
the abbreviation was not carrying its meaning, and DarvaX had used the short form
in **every** place it names that price. All of them now spell it out: the filter
options, the `Stop-loss` table column, the ladder row, `Your stop-loss` on a held
position, and the `Stop-loss (optional)` entry field.

**Engine-persisted prose is deliberately untouched.** `stop_vs_ceiling_note` says
*"The stop sits ₹14.71 below…"*, and ADR-005 puts that wording with the engine
that computed it — the UI renders it, and rewording it here would both violate
that and require a re-sweep to take effect on the 2,191 existing rows. Reads
naturally in a sentence, so it is left alone. `test_the_ui_says_stop_loss_not_stop`
scopes itself to labels for this reason.

`Box ht` was spelled out to `Box height` for the same reason, and three column
headers gained hover explanations (`Risk now`, `To buy level`, `Box height`).

### 8.7 Was box height measured from the buy level? No — and it cannot be inferred

The owner asked whether box height was a distance above the buy level. It is
`(ceiling − floor) / floor`: the range's own height. There is also **no fixed
relationship** to fall back on, measured across 117 rows carrying both a box and
a buy level:

| Where the buy level sits | Count | Share |
|---|---|---|
| Above the ceiling | 107 | 91% |
| **Inside the box** | **10** | **9%** |
| Below the floor | 0 | 0% |

Box heights on that sweep ran 3.6% to 45.3%, median 11.5%. Because the buy level
is inside the box on nearly one row in ten (BI is one: buy level ₹66.99 against a
ceiling of ₹75), the explanation states the negative explicitly rather than
trusting the reader to infer a rule that does not hold.

### 8.8 Verified, not assumed

Width was the standing risk, since a `select` sizes itself to its widest option:

- Control row is a **single 38px line at both 1280px and 960px** — no wrap.
- The page **never scrolls sideways**; the twelve-column table scrolls inside its
  own box, and the sticky symbol column holds at x=19 through a 400px scroll.
- Filter logic unaffected by any rewording — the option **values** are the
  contract: 67 rows stop-loss-below, narrowing to 32 with a tight box.
- The note renders as separate lines (`.fnwhat` per sentence, `.fncount` for the
  tally) rather than a `·`-joined run, which with two explanations would have
  been the wall of text this rewrite exists to remove.
- Every line is a `textContent` on its own element — the note now carries prose,
  and prose invites `innerHTML`.

Three tests that pinned literal label prose were re-anchored to the option values
across these attempts. Pinning wording meant every legitimate improvement failed
a test for no reason that mattered, which trains the reflex to edit the
expectation — turning a guard into a formality.

---

## 9. DX-11: the in-app "How DarvaX works" guide

Owner's request, verbatim: *"add world class ux reading guide about darvax...
complete information about darvax (what it is, how it works, each and every
minute detail)."*

**Placement.** A dialog reachable from a `Guide` button in the header, not a
fourth mode alongside Advisor/Levels/Table. Those three switch what live sweep
data is on screen; the guide is reference material that applies regardless of
which one is open, so folding it into the mode switch would make "how does
this work" compete for a slot with "what should I do today" — different
questions, asked at different times.

**Structure.** Twelve sections behind a sticky table of contents: what DarvaX
is, the Darvas box (with an inline SVG diagram — floor, ceiling, breakout,
retest, stop-loss, and the new higher box that forms after), the four DAR-CARD
rules quoted verbatim, what each of the seven actions means, how to read every
field on a card, the three views, the three filters, the stop-loss (including
the deck's own 10%-vs-1% self-contradiction), liquidity, the screened universe,
the DX-5 validation status, and what DarvaX deliberately will not do.

**Grounding, not paraphrase.** Every quoted rule and every numeric threshold in
the guide is asserted in `test_dx11_guide.py` against the same source it
describes — `DAR_CARD_TEXT` for the four rules, `config.py` for box/swing/
retest/stop parameters, `validation/summary.py` for the 200-trade/500-day
sufficiency gate, `screening/liquidity.py` for the 20-session window. A
reference document that can drift from the code it documents is worse than no
document, because it is trusted while being wrong; this is the guard against
that specific failure.

**Verified in-browser, not just asserted in markup:** opening moves focus into
the dialog and closing (Escape, backdrop click, or the × button) returns it to
the button that opened it — checked with a real click, since a synthetic
`element.click()` does not set `document.activeElement` the way a user
interaction does and gave a false negative on the first pass. The TOC's 12
links were checked to scroll their sections into view. The box diagram's six
labels were checked programmatically (`getBBox()` pairwise overlap) for zero
collisions, given this project's repeat history of that exact defect in the
Levels ladder. The panel was also checked at 400px: the TOC switches to a
horizontal row, the page never scrolls sideways.

**One existing test had to be narrowed, not the guide.**
`test_there_is_no_market_cap_filter` banned the phrase "market cap" anywhere on
the page. The guide's §12 says *"It will not filter on market
capitalisation... liquidity is the closest measured substitute"* — disclosing
an absence, the opposite of offering the feature the original test existed to
prevent. Rescoped to the filter bar and to form-control attributes specifically,
so the guide's honest disclosure and the original guard against an invented
filter both hold at once.
