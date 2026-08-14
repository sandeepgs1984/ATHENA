# DarvaX universe screener — design (DX-6)

Design proposal for turning DarvaX from *"tell me about these symbols"* into
*"tell me which symbols are worth looking at"*.

**Status:** 🔄 Proposed — needs owner approval, and ADR-010 **Amendment 2**
accepted, before any code. **Governing decision:**
[ADR-010](../adr/ADR-010-darvax-satellite-module.md) ·
**Related:** [`DARVAX-CONFIGURATION.md`](DARVAX-CONFIGURATION.md),
[`DARVAX-PERFORMANCE-EVIDENCE.md`](DARVAX-PERFORMANCE-EVIDENCE.md)

---

## 1. The gap

DarvaX today is **push, not pull**. `POST /darvax/api/scan` requires a non-empty
`instrument_ids` list and 422s without one; `GET /darvax/api/signals` accepts
only `limit` — no filter by state or rule. You name the symbols, DarvaX reports
each one's Darvas state, and finding candidates remains entirely your job.

The ledger holds **528 instruments**. DarvaX has evaluated 3.

Two capabilities already exist and are unused:

- `list_instruments()` is declared on `DarvaxMarketDataPort` and **implemented**
  in the adapter — nothing calls it.
- The engine already classifies every instrument into six states plus DAR-CARD
  rules A/B/C/D. Eligibility is already computed; it is simply never asked for
  across the universe, never persisted as a screen, and never surfaced.

So this is a wiring and presentation milestone over existing methodology. **No
new trading logic is proposed.** That matters: DX-2/DX-3 established the
primitives and the state machine under review, and this design deliberately adds
nothing to them.

---

## 2. What "eligible" means — derived, never invented

The single most important design decision here is refusing to invent a
conviction score.

DarvaX output is `EXPERIMENTAL_UNVALIDATED` and the source deck ships no
backtest evidence at all. A composite 0–100 "DarvaX score" would manufacture
precision the methodology cannot support, and would be the exact failure mode
ATHENA's constitution exists to prevent. **Eligibility is therefore a
classification taken straight from the DAR-CARD rules, not a score.**

| Tier | States | Darvas rule | Meaning |
|---|---|---|---|
| **ACTIONABLE** | `BREAKOUT`, `BREAKOUT_RETEST` | **B** — buy above the topmost box | Price has cleared the topmost box ceiling |
| **WATCH** | `INSIDE_TOPMOST_BOX` | **A** — hold while in the topmost box | Coiled inside the topmost box; a breakout candidate |
| **EXIT_RELEVANT** | `BELOW_BOX_BOTTOM` | **C** — sell below a new box bottom | Only meaningful if the instrument is held |
| **NOT_ELIGIBLE** | `NOT_IN_TOPMOST_BOX`, `NO_BOX` | **D** / none | No Darvas reason to act |

Every tier is a pure function of `signal_type`, which the engine already
produces and already explains. The tier adds a name and an ordering — it adds no
judgement.

### Ranking: measured quantities, shown separately

Within a tier, rows are ordered by **one named, methodology-attributable key**,
with every input displayed as its own column so the owner can re-sort and see
exactly what drove the order. No hidden weighting, no blended index.

| Quantity | Definition | Provenance |
|---|---|---|
| `distance_to_trigger_pct` | `(trigger_price − close) / close × 100` | `trigger_price` already exists on `DarvaxSignal` — the prior bar's high, deck p.44 "Enter above the Previous Day High Price" |
| `box_height_pct` | `(box_top − box_bottom) / box_bottom × 100` | Darvas favoured tight boxes; both bounds already persisted |
| `bars_in_box` | Bars since the topmost box confirmed | Derived from the DX-2 box primitive |
| `volume_expansion` | Latest-bar volume vs its trailing mean | Existing DX-2 primitive, currently unused by the engine |

**Default order:** ACTIONABLE first, then WATCH ascending by
`distance_to_trigger_pct` — closest to breaking out, first. That is a defensible
default because it answers the question the tier poses, and nothing else is
smuggled into it.

Each of these is a *measurement*. None is a prediction, and the UI must never
present them as one.

---

## 3. Execution — mirroring an approved ATHENA pattern

Sweeping 528 instruments cannot be a synchronous request. ATHENA already solved
this exact problem for its own full-universe validation
(`athena/ops/full_validation.py`, ADR-007): a **single-flight background daemon
thread** with a transient progress object and an explicit busy error.

DarvaX will mirror that shape with its **own** implementation. It must not
import ATHENA's — ADR-010 §1 permits DarvaX to import frozen domain objects and
read-only contracts, not ATHENA's ops machinery, and reusing it would couple the
satellite's lifecycle to ATHENA's cycle lock.

| Concern | Decision |
|---|---|
| Concurrency | One sweep at a time. A second request gets **409 Conflict**, never a queue — ADR-010's scope guard explicitly forbids queues and schedulers |
| Trigger | **Owner-triggered only.** No scheduler, no cron, no auto-refresh. This is what keeps DX-4a's "no measurable contention" result valid |
| Batching | The universe is processed in chunks of `scan.max_instruments` (default 50). The per-request cap keeps its existing "**refuse, not truncate**" semantics; the sweep is a distinct concept that batches *below* that cap rather than raising it |
| Cancellation | A running sweep can be cancelled; partial results persist and are labelled partial. Silently discarding completed work would be worse |
| Failure isolation | Per-instrument, exactly as `scan_instruments` already does. One unreadable symbol never fails the sweep; it lands in `skipped` with a reason |

### Replayability

A sweep is persisted as a run record, not just a pile of signals, so any screen
can be reproduced and audited:

`darvax_sweeps(sweep_id, started_at, finished_at, state, as_of, methodology_digest,
darvax_version, requested, evaluated, skipped_json, tier_counts_json, partial)`

`methodology_digest` is captured per sweep because changing any methodology value
changes it — a screen must be interpretable against the parameters that produced
it, and old screens must not appear to have been produced by current settings.

---

## 4. Persistence — explanations stay data (ADR-005)

`DarvaxSignal` persistence is unchanged. Screen results go in their own table so
the frozen signal contract stays frozen:

`darvax_screen_results(sweep_id, instrument_id, signal_id, tier, rank,
distance_to_trigger_pct, box_height_pct, bars_in_box, volume_expansion,
explanation)`

The tier and every ranking input are **computed once by the screening engine and
persisted**. The API serialises them and the UI renders them. Neither recomputes,
re-derives, or re-words anything — that is ADR-005, and it is why the screener
can be replayed and audited rather than merely re-run.

DarvaX schema goes **v2 → v3**, versioned independently of ATHENA's.

---

## 5. API surface

Additive only. Nothing existing changes shape.

| Endpoint | Purpose |
|---|---|
| `POST /darvax/api/screen` | Start a universe sweep. 409 if one is running |
| `GET /darvax/api/screen/progress` | Transient progress: state, stage, evaluated/total, elapsed |
| `DELETE /darvax/api/screen` | Cancel the running sweep |
| `GET /darvax/api/screen/latest` | Latest sweep's results; `?tier=`, `?limit=` |
| `GET /darvax/api/screen/sweeps` | Sweep history for replay/comparison |

Plus one fix to an existing gap found while investigating: **`GET /api/signals`
gains a `signal_type` filter**, so "show me only the breakouts" is answerable
from the API rather than by eyeballing an unfiltered list.

All behind `RequirePermission`, all carrying `EXPERIMENTAL_UNVALIDATED`, exactly
as DX-4 established.

---

## 6. UX design

Darvas is a fundamentally **visual** method — a box, a ceiling, a break. A
numbers-only table hides the entire idea. The design below is organised around
showing the structure, not tabulating it.

### 6.1 Organising principle: tiers, not a flat list

The screen opens as three labelled groups — **Actionable**, **Watch**,
**Exit-relevant** — each with a count, each collapsible, in that order.
`NOT_ELIGIBLE` is hidden behind a "show all evaluated" toggle: it is the large
majority of 528 rows and showing it by default would bury the signal.

A flat sortable table would technically contain the same data and would be
materially worse, because the first question is always *"is there anything to
act on?"* — the layout should answer that before any scrolling.

### 6.2 The box visualisation

Each row carries a compact horizontal **box-range bar**, the core UI element:

```
   floor ├──────────────█████──┤ ceiling        ▲ trigger
                          ↑ close
```

- The bar spans the topmost box, floor to ceiling
- A marker shows the latest close within (or above/below) that range
- A tick marks `trigger_price` (prior bar's high)
- Colour follows the existing tone map: breakout `--good`, inside `--warn`,
  below-floor `--bad`

Rendered as inline SVG/CSS with no library — ADR-004 keeps this dashboard
framework-free and build-step-free, and that constraint holds here.

This single element makes a 30-row screen readable at a glance: you see which
instruments are pressed against their ceiling versus sitting mid-box.

### 6.3 Row anatomy

| Column | Notes |
|---|---|
| Symbol | Monospace, primary |
| State badge | `BREAKOUT` etc., toned — descriptive never imperative |
| Rule | A/B/C/D chip, with the verbatim DAR-CARD text on hover |
| Box range | The visualisation above |
| Close | Monospace, aligned |
| Distance to trigger | Signed %, with a proportional micro-bar |
| Box height | % — tightness |
| Stop | Price + policy chip |
| As-of | Bar date, **amber if older than the latest trading day** |

### 6.4 Progressive disclosure

Clicking a row expands the DX-4 detail already built: the **persisted**
explanation, the evidence trace, and the stop derivation. Nothing new is
computed on expand — it is the stored rationale, rendered.

### 6.5 States that must be honest

| State | Treatment |
|---|---|
| No sweep yet | Explain what a sweep does and its expected duration — never an empty grid with no explanation |
| Running | Live progress bar, evaluated/total, elapsed, cancel button. Partial results stream in as tiers fill |
| Cancelled | Results shown, clearly labelled **partial**, with the evaluated count |
| Skipped symbols | Surfaced in a collapsible panel with per-symbol reasons — **never silently dropped**, matching the existing scan behaviour |
| Stale | If the sweep's `as_of` predates the latest trading day, an amber freshness notice |
| Digest changed | If the current `methodology_digest` differs from the sweep's, say so plainly: these results came from different parameters |

That last one matters and is easy to omit. A screen produced under a 10% stop
and read under a 1% stop is misleading unless the mismatch is stated.

### 6.6 Interaction

- Client-side sort on every numeric column, and a symbol filter box — the result
  set is bounded at 528 rows, so no server round-trips
- Sort state and tier collapse persist in `sessionStorage`, scoped to DarvaX
- The **EXPERIMENTAL / UNVALIDATED** banner stays unconditional. It is a
  correctness requirement, not decoration, and no view hides it
- Works inside the iframe tab and standalone at `/darvax/`, unchanged

---

## 7. What this design deliberately refuses

Stating these explicitly, because each is a plausible-sounding feature that would
damage the system:

1. **No composite conviction score.** Fabricated precision on an unvalidated
   methodology (§2).
2. **No scheduled or automatic sweeps.** Owner-triggered only — this is what
   preserves the DX-4a result. A background scheduler would invalidate the
   measured "no contention" finding on day one.
3. **No feeding ATHENA.** Screen output never reaches ATHENA's scoring,
   confidence, risk, Decision, TradePlan, or universe. ADR-010's core invariant.
4. **No order-placement affordances.** No "buy" button, no broker hand-off, no
   quantity field. States stay descriptive (`BREAKOUT`, not `BUY`).
5. **No raising `max_instruments` to 528.** The cap's refuse-not-truncate
   semantics are load-bearing; the sweep batches beneath it instead.
6. **No new methodology.** Zero changes to DX-2 primitives or the DX-3 state
   machine.

---

## 8. Architectural delta — needs ADR-010 Amendment 2

Three things exceed what ADR-010 currently authorises, so this needs an
amendment rather than silent implementation:

1. **A background worker thread inside DarvaX.** ADR-010's scope guard forbade
   speculative concurrency infrastructure. This is not speculative — it is
   required by a 528-instrument sweep and mirrors ADR-007's approved pattern —
   but it is a genuine extension of DarvaX's decision surface.
2. **Universe-wide reads.** DarvaX moves from reading a handful of named
   instruments to enumerating all of them via `list_instruments()`. Bounded, but
   a materially different read profile.
3. **A second DarvaX schema table and a v2→v3 bump.**

Amendment 2 is proposed alongside this design.

---

## 9. Milestone split

CLAUDE.md requires milestones small enough to review in one sitting, split
*before* implementing. This is too large as one:

| Milestone | Scope | Reviewable independently? |
|---|---|---|
| **DX-6a** Screening engine | Eligibility taxonomy, ranking quantities, `darvax_screen_results` + schema v3, pure functions over existing signals. **No sweep job, no UI, no API** | Yes — pure logic with fixture tests |
| **DX-6b** Universe sweep + API | Single-flight background job, progress, cancel, batching, the five endpoints, `signal_type` filter | Yes — service + routes |
| **DX-6c** Screener UX | Tier groups, box visualisation, sorting/filtering, all honest states | Yes — one asset surface |
| **DX-6d** Perf re-measure | Re-run the DX-4a harness at universe scale | Yes — evidence only |

**DX-6d is not optional.** DX-4a measured 25 instruments and explicitly names
"`max_instruments` raised substantially" and continuous scanning as re-measure
triggers. A 528-instrument sweep is a different load profile, and carrying the
old "no contention" conclusion across would be exactly the assumption ADR-010
forbids.

### Definition of Done (all milestones)

Full suite green · ruff clean · architecture boundaries intact · frozen contracts
unchanged · deterministic and replayable · explanations persisted not recomputed
· DarvaX still deletable with ATHENA unaffected · `EXPERIMENTAL_UNVALIDATED`
preserved on every payload and view · no order-placement code.

---

## 10. Open questions for the owner

1. **Timeframe.** Sweep daily (`D1`) only, or make the timeframe a parameter?
   Daily matches the deck and ATHENA's swing focus; anything else multiplies cost.
2. **Universe definition.** All 528 ledger instruments, or ATHENA's *eligible*
   universe (which already excludes delisted/illiquid names)? Reusing ATHENA's
   eligibility is cheaper and more sensible, but is a read of an ATHENA concept —
   worth a deliberate decision rather than a default.
3. **History depth.** How many past sweeps to retain? Unbounded growth is the
   decisions-table problem again; a retention policy is easier now than later.
