# ID-7D — Entry Actionability Next-Layer Discovery + Contract Reconciliation

**Status: DISCOVERY COMPLETE — READY FOR OWNER / CHIEF ARCHITECT SCOPE DECISION (2026-09-05).**
Read-only architecture/documentation discovery. No code, schema, or
production behavior was changed by this milestone. No provider calls, no
production `EntryActionability` rows, no methodology change.

Owner/Chief Architect closed ID-7C.2, ID-7C.1, and ID-7C overall on
2026-09-05 (V0 deterministic evaluator frozen) and authorized this
discovery to resolve a documentation/sequencing ambiguity around
"ID-7D" before any ID-7E workflow-wiring authorization.

---

## 1. Why this milestone exists

The ID-7 track's own original sub-milestone plan
(`docs/research/ID-7-INTRADAY-ENTRY-TRADEPLAN-DISCOVERY.md` §35, written
2026-09-03 before ID-7A0 was even authorized) proposed:

```
ID-7A0 — ADR proposal
ID-7A  — Immutable domain contract only. No engine logic, no persistence.
ID-7B  — Entry/stop/target methodology research
ID-7C  — Deterministic, pure engine
ID-7D  — Persistence, append-only, Decision+EntryQualification-bound identity
ID-7E  — Workflow integration
ID-7F  — Replay/shadow validation
```

That plan explicitly separated **ID-7A (domain only)** from **ID-7D
(persistence)** — mirroring the ID-6 precedent's own ID-6A (domain) /
ID-6C (persistence) split.

What was **actually authorized and built** diverged from that plan at
exactly one point: the owner's real ID-7A authorization message was
titled *"ATHENA — ID-7A ENTRY ACTIONABILITY DOMAIN + PERSISTENCE
IMPLEMENTATION"* and explicitly bundled domain contract **and**
persistence contract into one milestone (schema v18, the
`entry_actionabilities` table, and all five `SqliteRepository` methods
were all built and Owner-approved/closed under **ID-7A**, not a
separate ID-7D). ID-7B/ID-7C then proceeded exactly as originally
planned (methodology research, then the pure engine).

The result: two governing documents — ADR-015 itself and the ID-7A0
research report — still carry the **stale, pre-ID-7A-authorization**
description of "ID-7D" as the persistence milestone, even though that
persistence work is long since complete and closed. This milestone
exists to reconcile that documentation drift and to determine, from the
actual current architecture (not from the stale plan), whether anything
real is still missing between the now-frozen ID-7C evaluator and a
future ID-7E workflow-wiring milestone.

---

## 2. ID-7 milestone history — chronology and stale descriptions found

| Milestone | Originally proposed (§35, pre-ID-7A0) | Actually built/closed | Stale reference found |
|---|---|---|---|
| ID-7A0 | ADR proposal only | ✅ Closed 2026-09-04 — ADR-015 Accepted, `EntryActionability` artifact designed | none |
| ID-7A0.1 | (not in original plan; emerged from owner source review) | ✅ Closed 2026-09-04 — lifecycle/currentness/WATCH-scope corrections | none |
| ID-7A | "Immutable domain contract... **No engine logic, no persistence**" | ✅ Closed 2026-09-05 — domain contract **AND** schema v18 **AND** full repository (5 methods) **AND** the separate `is_currently_usable` currentness helper | **Yes** — see below |
| ID-7B/ID-7B.1/ID-7B.2/ID-7B.2.1 | "Entry/stop/target methodology research" | ✅ Closed 2026-09-04 — V0 methodology frozen exactly as planned | none |
| ID-7C/ID-7C.1/ID-7C.2 | "Deterministic, pure engine" | ✅ Closed 2026-09-05 — `EntryActionabilityEngine` built exactly as planned, plus two owner-driven hardening slices | none |
| **ID-7D** | **"Persistence, append-only, Decision+EntryQualification-bound identity (mirrors ID-6C/6C.1)"** | **Never separately built — its entire described scope was absorbed into ID-7A** | **Yes — this is the milestone this discovery resolves** |
| ID-7E | "Workflow integration... the exact point where §38 Owner Question 2 ... must be resolved" | Not started, not authorized | none (description still accurate) |
| ID-7F | "Replay/shadow validation (mirrors ID-6E ...)" | Not started, not authorized | none (description still accurate) |

**Exact stale references found (file:line):**

- `docs/adr/ADR-015-intraday-actionability-architecture.md:461` — *"ID-7C
  (engine), **ID-7D (persistence)**, ID-7E (workflow wiring), and ID-7F"*
  — written 2026-09-04, before ID-7A's actual scope (domain+persistence
  bundled) was authorized the next day.
- `docs/research/ID-7A0-INTRADAY-ACTIONABILITY-ARCHITECTURE.md:22` —
  *"does not create a schema (**ID-7D**), does not wire a workflow stage
  (ID-7E)"* — same era, same stale assumption.
- `docs/research/ID-7-INTRADAY-ENTRY-TRADEPLAN-DISCOVERY.md:751-752` —
  the original §35 proposal itself (correctly labeled at the time it was
  written; superseded by the owner's later ID-7A authorization, not
  itself an error).

**No other repository document** (checked: `docs/MILESTONES.md`,
`docs/ATHENA-ID-TRACK-HANDOFF.md`, `ATHENA_BRIEFING.md`,
`IMPLEMENTATION_SUMMARY.md`) attaches any substantive description to
"ID-7D" beyond the boilerplate closing line *"ID-7D/ID-7E/ID-7F remain
NOT STARTED, NOT AUTHORIZED"* — none of the actively-maintained tracking
docs assert a persistence-scope meaning for ID-7D, so the drift is
confined to the two frozen documents above (ADR-015 and the ID-7A0
report), both of which are historical/point-in-time records rather than
living status trackers.

---

## 3. Actual current responsibility of each closed ID-7 milestone

- **ID-7A** (Owner-approved/closed 2026-09-05, hardened by ID-7A.1/
  ID-7A.2 same day): the `EntryActionability` immutable domain object
  (`src/athena/intraday/entry_actionability_models.py`), schema v18
  (`entry_actionabilities` table, `src/athena/data/store/schema.py`),
  the full append-only repository contract (`save_entry_actionability`,
  `get_entry_actionability`,
  `latest_entry_actionability_for_entry_qualification`,
  `latest_entry_actionability_for_instrument_session`,
  `list_entry_actionabilities_for_instrument_session` —
  `src/athena/data/store/repository.py`), and the separate, never-
  persisted `is_currently_usable` read-time currentness predicate
  (`src/athena/intraday/entry_actionability_currentness.py`). **This is
  the entirety of what "ID-7D: persistence" was originally scoped to
  cover.**
- **ID-7B** (Owner-approved/closed 2026-09-04): the frozen V0
  entry/invalidation/reward methodology contract
  (`docs/research/ID-7B2-ENTRY-RISK-CALIBRATION-VALIDATION.md` §14, as
  corrected by §29) — pure evidence/research, zero code.
- **ID-7C** (Owner-approved/closed 2026-09-05, hardened by ID-7C.1/
  ID-7C.2 same day): the pure, deterministic `EntryActionabilityEngine`
  (`src/athena/intraday/entry_actionability_engine.py`) implementing
  the frozen V0 methodology — no persistence, no "latest" resolution,
  no currentness, no workflow wiring, no provider calls.
- **ID-7E** (documented, not authorized): "workflow integration" — still
  an accurate, not-yet-superseded description per
  `docs/research/ID-7-INTRADAY-ENTRY-TRADEPLAN-DISCOVERY.md` §35.
- **ID-7F** (documented, not authorized): "replay/shadow validation,
  mirrors ID-6E" — still accurate.

---

## 4. Canonical workflow architecture audited

**`src/athena/runtime/workflow.py`** — the generic orchestration
primitives every production pipeline uses:

- `WorkflowContext` (lines 31-61): an accumulator passed to each stage.
  `ctx.as_of` is the one shared market-time checkpoint for an entire
  per-instrument execution. Stages return output mappings the engine
  merges via `_merge`, rejecting key collisions — stages never mutate
  the context directly.
- `WorkflowStage` (64-77): `name`, `run` (a `Callable[[WorkflowContext],
  Mapping[str, object]]`), `depends_on`, `produces`.
- `WorkflowDefinition` (80-125): validates the stage set into a DAG,
  computes a deterministic Kahn topological order (`_topological_order`,
  104-118), raises `WorkflowError` on an unknown dependency or a cycle.
- `WorkflowEngine.execute` (134-191): runs stages in that deterministic
  order; **a stage whose dependency already failed/was skipped is itself
  marked `SKIPPED`** (150-158); **a stage that raises is caught, recorded
  `FAILED` with the exception message, and its own dependents are then
  skipped** (167-175) — **independent branches (stages with no
  dependency on the failed one) still run**. This is the exact,
  source-confirmed failure-isolation contract referenced throughout this
  report.

**`src/athena/scanner/scanner.py`** — the per-instrument coordination
layer one level up:

- `DailyMarketScanner.scan` (45-70) iterates the universe in sorted
  order, calling `_scan_one` per instrument.
- `_scan_one` (74-...) wraps pipeline-build and workflow-execution in
  `try`/`except`; the module's own docstring (line 14) states plainly:
  *"Failure isolation: one instrument's failure never terminates the
  scan."* Confirmed by source, not merely by docstring claim: `_scan_one`
  catches a build exception and returns a `FAILED`
  `InstrumentScanResult` for that instrument only, never propagating.

**`src/athena/ops/owner_validation.py`, `OwnerValidationPipeline._scan_eligible`**
(the real production per-instrument stage graph, lines 782-1519) — this
is where every canonical `Decision`/`EntryQualification` production row
actually comes from, and is the primary architectural precedent this
discovery uses for everything below.

---

## 5. EntryQualification production precedent (ID-6D) — the primary architectural precedent

The existing 11-stage per-instrument `WorkflowDefinition` (built inside
`builder(instrument_id)`, lines 932-1519) is, in execution order:
`indicators` → `regime` → `scoring` → `confidence` → `risk` →
`decision` → `session` → `relative_strength` → `relative_volume` →
`intraday_analytics` → `entry_qualification`.

Key structural facts, all read directly from source:

- **`dec_stage`** (1131-1157) calls `decision_engine.decide(...)`,
  `self._repo.save_decision(outcome.decision, trace=outcome.trace)`,
  and stashes the outcome in a per-instrument closure variable
  `box["cap"]`. It does **not** publish `decision` into `ctx` under that
  key — only `{"outcome": True}`.
- **`entry_qualification_stage`** (1360-1414) reads the canonical
  `Decision` via `decision = box["cap"].outcome.decision` — **the exact
  same object `dec_stage` just constructed and persisted this cycle**,
  never a repository re-query. The stage's own comment (1368-1377)
  states explicitly: *"Within one synchronous, single-threaded
  per-instrument pipeline execution, the Decision `dec_stage` just
  produced (and already persisted) is provably the freshest possible
  artifact for this instrument — no staleness/supersession is
  structurally reachable."* This is the load-bearing precedent for §9
  below (same-cycle Decision/EQ identity).
- It reads `session_context = ctx.get("session_context")` and
  `signal_set = ctx.get("intraday_signal_set")` (both produced by
  earlier stages in the same DAG), computes
  `evidence_finality = resolve_evidence_finality(decision,
  session_context)` **inline, inside the stage function itself** — there
  is **no separate "composition contract" milestone or class** between
  `EntryQualificationEngine` (ID-6B.2) and this stage (ID-6D). Evidence
  composition is simply the stage's own function body.
- It calls `entry_qualification_engine.evaluate(decision=decision,
  session_context=session_context, signal_set=signal_set,
  evidence_finality=evidence_finality)` unconditionally (the engine
  itself handles non-WATCH/TRADE Decision types), then persists only for
  WATCH/TRADE: `self._repo.save_entry_qualification(eq,
  persisted_at=self._persistence_clock())`.
- `persisted_at` is sourced from `self._persistence_clock` — an
  **injected wall-clock callable** on `OwnerValidationPipeline.__init__`
  (line 85), defaulting to `lambda: datetime.now(tz=timezone.utc)`
  (107-108) when not overridden — deliberately independent of
  `ctx.as_of` (market-time), never a bare `datetime.now()` call inside
  the stage or the engine.
- The `entry_qualification` `WorkflowStage` itself (1511-1516) declares
  `depends_on=("decision", "intraday_analytics")`, `produces=
  ("entry_qualification",)` — a single new stage added at the end of an
  existing 10-stage DAG, chosen specifically because it is *"the first
  stage to join the previously-independent 'decision' and
  'intraday_analytics' branches"* (1505-1509).

**What this precedent proves for ID-7 by direct analogy:** ID-6D did
**not** introduce a separate composition-layer milestone between the
pure engine (ID-6B.2) and workflow wiring (ID-6D) — evidence composition
(reading `ctx.get(...)`, calling one small pure helper function
`resolve_evidence_finality`, then calling the engine) was inlined
directly into the one new stage. This is the single strongest piece of
evidence this discovery found bearing on the classification question in
§9 below.

---

## 6. Producer/consumer map — every `EntryActionabilityEngine.evaluate()` input

| Input | Current producer | Current type | Already in `WorkflowContext`? | Recomputation needed? | Provider access needed? | PIT provenance already available? | Same-cycle identity preserved? |
|---|---|---|---|---|---|---|---|
| `decision` | `dec_stage` → `box["cap"].outcome.decision` | `Decision` | No (closure var, not a `ctx` key) | No | No | N/A | **Yes** — same-cycle object, not a repository re-query (§5) |
| `entry_qualification` | `entry_qualification_stage` → returns `{"entry_qualification": eq}` | `EntryQualification` | **Yes** — `"entry_qualification"` key | No | No | N/A | **Yes** — produced from the exact same-cycle `decision` above |
| `market_evidence.completed_m5_close` | `ind_stage`'s local `intraday_cs = completed_candles(vwap_raw, Timeframe.M5, as_of=ctx.as_of)` | `list[Candle]` (local only — **not published to `ctx`**) | **No** | No — data already fetched | No | Yes, if the *last* element of this already-completed-filtered list is selected | Yes — same instrument/session, same `ctx.as_of` |
| `market_evidence.session_vwap` | `ind_stage`'s `vwap_result = indicator_engine.compute(IndicatorName.VWAP, intraday_cs, as_of=ctx.as_of)` | `IndicatorResult` (raw price in `.values["vwap"]`) | **Yes** — `"vwap"` key (the *raw* `IndicatorResult`, not `VwapEvidence`) | No | No | Price yes; timestamp **no** (see §7) | Yes |
| `market_evidence.session_vwap_as_of` | **No current producer** | — | **No** | **Yes — must be derived** | No | **Gap — see §7** | N/A until derived |
| `market_evidence.opening_range_15` | `intraday_analytics_stage`'s `orb_by_window[OpeningRangeWindow.OR15]` | `OpeningRangeEvidence` | No (only the composed `intraday_signal_set` is published, not the raw `orb_by_window` dict) | No — already computed | No | **Yes — already exactly coherent** (§8) | Yes |
| `evaluated_at` | No current producer for an "evaluation" instant; `persisted_at` uses the injected `_persistence_clock` | `datetime` | No | No | No | N/A (diagnostic-only field) | N/A |

---

## 7. Completed-M5 input and session-VWAP provenance — the one real gap

**Composition path proof (source-grounded).** Inside `ind_stage`
(`owner_validation.py:980-988`):

```python
vwap_raw = self._repo.get_candles(
    instrument_id, Timeframe.M5,
    session_day_start(ctx.as_of, session_tzinfo), ctx.as_of,
)
intraday_cs = completed_candles(vwap_raw, Timeframe.M5, as_of=ctx.as_of)
vwap_result = (
    indicator_engine.compute(IndicatorName.VWAP, intraday_cs, as_of=ctx.as_of)
    if intraday_cs else None
)
```

`intraday_cs` is exactly the completed-M5, same-session, calendar-day-
bounded candle series ID-7C's frozen VWAP formula needs
(`indicators/calculations.py:196-220`'s own `vwap()` function — audited
in ID-7C and reconfirmed here — computes `vwap_value` from precisely
this kind of list, and its own `last_close = session_bars[-1].close`
is the same "last completed bar" concept `EntryActionabilityEngine`
calls the entry reference). `session.engine.latest_completed_candle`
(the exact canonical helper `EntryActionabilityMarketEvidence`'s own
docstring already names as the expected caller-side selection tool)
applied to `vwap_raw` would return the identical candle as
`intraday_cs[-1]` — proven by both functions sharing the same
`completed_candles`/`is_candle_completed` primitive
(`session/engine.py:36-58`).

**Two genuine, evidence-backed findings:**

1. **`completed_m5_close` is a presentation/composition gap, not a
   domain-methodology gap.** The exact right candle already exists,
   already fetched, already completed-filtered, inside `ind_stage`'s own
   local scope — it is simply never published into `ctx`. A future
   integration needs only to add it to `ind_stage`'s (or a later stage's)
   own return mapping, or call `latest_completed_candle` a second time
   from a later stage using the already-existing `self._repo.get_candles`
   read pattern. No new provider call, no new candle series, no new
   methodology.

2. **`session_vwap_as_of` cannot be derived from anything ID-6D already
   publishes to `ctx`.** `IndicatorResult.ts` (`indicators/models.py:62`)
   is set to `ctx.as_of` — the general per-cycle market-time checkpoint —
   **not** the timestamp of the specific last completed M5 bar VWAP was
   computed from. Under real production conditions these two values are
   *usually* close (a live cycle typically runs shortly after each bar
   completes) but are **not architecturally guaranteed identical** — the
   ID-7P0/ID-7P0.1 latency-attribution work already measured genuine
   multi-minute cycle latency in this exact pipeline
   (`docs/research/ID-7P0-PRODUCTION-CYCLE-LATENCY-ATTRIBUTION-REVIEW.md`).
   ID-7C.1's own `session_vwap_as_of` invariant exists precisely to catch
   this kind of drift, so a future integration **must** derive
   `session_vwap_as_of` from the *same selected candle's own*
   `ts_open + 5 minutes` — never from `ctx.as_of`/`IndicatorResult.ts` —
   or `EntryActionabilityMarketEvidence.__post_init__`'s own PIT-equality
   check (ID-7C.1) will correctly reject the mismatch as a contract
   error. This is the one concrete "required VWAP provenance gap" this
   discovery found: **a presentation/composition gap** (the raw data
   needed already exists in the same bounded candle series VWAP is
   computed from; it is not yet exposed under the exact identity/shape
   `EntryActionabilityMarketEvidence` requires), **not** a
   domain-methodology gap (no new methodology decision is needed to
   close it).

---

## 8. VWAP computation boundary audit — no PIT-leakage risk found

Traced `ind_stage`'s VWAP computation for every listed leakage
possibility (ID-7C.2's §7 checklist):

- **Forming M5 bar**: excluded — `intraday_cs = completed_candles(...)`
  filters through `is_candle_completed` (`session/engine.py:36-45`),
  the single canonical completed-candle authority; a still-forming tail
  bar is never included.
- **Quote data**: `ind_stage` never reads a quote for VWAP; quotes are
  read only in `session_stage` (`get_latest_quote`, for `SessionContext`
  data-quality provenance), an entirely separate concern.
- **Wider/unbounded candle set**: `vwap_raw` is fetched via
  `session_day_start(ctx.as_of, ...) → ctx.as_of` — calendar-day bounded,
  not a fixed row-count `limit=N` (the exact real-data truncation risk
  ID-3.1 already found and fixed for Opening Range; the same fix already
  applies here per the comment at `owner_validation.py:972-979`).
- **Recomputed at a different timestamp than EQ**: both `ind_stage` and
  `entry_qualification_stage` read `ctx.as_of` — the one shared
  per-instrument checkpoint for the whole synchronous execution: no
  possibility of a different timestamp within one cycle.

**Conclusion: no PIT-leakage risk found in the current VWAP computation
itself.** The only real integration task is *exposing* the already-
correct completed-candle boundary as an explicit provenance timestamp
(§7), not correcting the computation.

---

## 9. OR15 input composition — already fully coherent, zero adapter needed

`intraday_analytics_stage` (`owner_validation.py:1297-1358`) builds:

```python
five_min_raw = self._repo.get_candles(
    instrument_id, Timeframe.M5,
    session_day_start(ctx.as_of, session_tzinfo), ctx.as_of,
)
orb_by_window = opening_range_engine.assess(
    instrument_id, as_of=ctx.as_of,
    session_context=ctx.get("session_context"),
    five_min_candles=five_min_raw, calendar=calendar, tzinfo=session_tzinfo,
)
```

`orb_by_window[OpeningRangeWindow.OR15]` is a real `OpeningRangeEvidence`
with `instrument_id` = the same closure-local `instrument_id` every
other stage in this DAG uses, `as_of = ctx.as_of` (the same shared
checkpoint `entry_qualification_stage`/a future `entry_actionability`
stage would also use), and (via `session_context`, the same object
`EntryQualificationEngine` already derives `EntryQualification.session_date`
from) a `session_date` provably equal to `entry_qualification.session_date`.

This satisfies all three of `_validate_or15_coherence`'s own checks
(instrument, session, at-or-before-checkpoint) **by construction, with
zero adaptation** — the only missing piece is that `intraday_analytics_stage`
currently returns only the *composed* `intraday_signal_set` (which itself
carries `or15` — but as a field of `IntradaySignalSet`, and
`IntradaySignalSet` does not need to change; the raw
`orb_by_window[OpeningRangeWindow.OR15]` value, or equivalently
`intraday_signal_set.or15`, is the object a future stage needs). Both
are already computed and already coherent; a future stage simply needs
to *read* `ctx.get("intraday_signal_set").or15` (already published) —
**no new fetch, no new engine call, no new methodology.**

OR15 remains fully optional per ID-7B.2.1/ID-7C — nothing here changes
that; this section only concerns the *composition* of a coherent OR15
artifact when one is available, never a requirement that one exist.

---

## 10. Decision + EQ same-cycle identity — already structurally guaranteed

Per §5, `entry_qualification_stage` reads `decision` from the same-
cycle `box["cap"].outcome.decision`, never a repository re-query — and a
future `entry_actionability` stage reading `entry_qualification` from
`ctx.get("entry_qualification")` (already published by
`entry_qualification_stage`) would inherit that exact same guarantee
transitively: the `EntryQualification` object in `ctx` was itself built
from the exact same-cycle `Decision`, within the same single-threaded,
synchronous per-instrument `WorkflowContext` execution.

This directly answers the concern ID-7A.2's currentness review raised
(a caller could otherwise mix `D1`+`EQ1` binding with a separately-
resolved "latest" `D2`): **that risk is a read-time risk, specific to a
consumer that resolves "current Decision"/"current EQ" via separate
repository queries at some later, arbitrary wall-clock instant** (which
is exactly what `is_currently_usable` was built to guard against, §11).
It is **not reachable** for a synchronous, same-cycle write-path
integration that simply reads `ctx.get("decision")`-equivalent and
`ctx.get("entry_qualification")` from the one shared context — no
"latest" repository composition is needed or safe to add as a shortcut
here, matching the milestone's own explicit caution in §9 of its
authorization.

---

## 11. Currentness composition boundary — confirmed outside the write path

`is_currently_usable` (`entry_actionability_currentness.py`) requires
`current_decision_id`, `current_entry_qualification_identity` (the
*current*, not the *bound*, identity — resolved via a repository "latest"
query per its own docstring), `current_session_phase`, and `now` (a real
wall clock). None of these concepts exist inside the synchronous
per-instrument write-path `WorkflowContext`:

- There is no "current Decision" repository query anywhere in
  `_scan_eligible` — the Decision *being made this cycle* already *is*
  the freshest one, by construction (§5), so "is it still current" is
  not a question the write path ever needs to ask of itself.
- `ctx.as_of` is a market-time evaluation checkpoint, not a real wall
  clock — `now` for currentness purposes is a genuinely different
  concept, appropriate only for a *later* reader.
- No `SessionPhase` resolution occurs in this stage graph at all today.

This confirms, from the actual current architecture (not merely from
ADR-015's own stated intent), that currentness composition **structurally
cannot** occur inside the write-time workflow/persistence path — it can
only ever be composed by a genuinely separate, later, read-time consumer
(API, dashboard, Decision Brief, future supervision) that independently
resolves "what is current right now" at the moment of its own read. This
milestone does not design any of those consumers; it only confirms the
boundary ADR-015/ID-7A0.1 already drew is the one the real architecture
actually supports.

---

## 12. Failure-semantics precedent

From `WorkflowEngine.execute` (§4) and `DailyMarketScanner`/`_scan_one`
(§4): a stage-level exception (e.g. a genuine ID-7C contract-error
`ValueError` — a Decision/EQ binding mismatch, an incoherent OR15, a
future-dated candle) is caught by the orchestrator itself, recorded as
`StageResult(status=FAILED, error=...)` for that one stage, and its own
dependents are skipped — **it fails only that one instrument's execution
for that cycle**, never the whole scan, never another instrument, and
does not require the engine or a future stage to catch its own
exceptions defensively. `entry_qualification_stage` already relies on
exactly this behavior today (a coherence `ValueError` from
`EntryQualificationEngine._validate_input_coherence` gets identical
treatment); a future `entry_actionability` stage would inherit the same
contract with zero new failure-handling code. **Recommended reuse: none
needed — the existing `WorkflowEngine`/`DailyMarketScanner` contract
already provides correct, adequate isolation.** No new failure policy is
proposed or required.

---

## 13. Repository persistence readiness — verified sufficient

`entry_qualification_stage`'s own production usage of the EQ repository
contract is instructive: it calls exactly **one** repository method,
`save_entry_qualification(eq, persisted_at=...)`, and **zero** "get"/
"latest" methods — production write-path evaluation never reads its own
result back. By direct analogy, a future `entry_actionability` write-path
stage would need only `save_entry_actionability(ea, persisted_at=...)` —
already built, already Owner-approved/closed under ID-7A, append-only,
idempotent, dual-binding-validated (Decision + exact upstream EQ).

**Verdict: `PERSISTENCE_CONTRACT_ALREADY_SUFFICIENT`.** No new repository
method is required for a future ID-7E write path. The four read/"latest"
methods (`get_entry_actionability`,
`latest_entry_actionability_for_entry_qualification`,
`latest_entry_actionability_for_instrument_session`,
`list_entry_actionabilities_for_instrument_session`) exist for later
read-time consumers (API/dashboard/replay), exactly mirroring EQ's own
established shape — none of them are needed by the write path itself,
and none should be added to it.

---

## 14. run_id/cycle_id provenance — zero ambiguity

`EntryActionability.run_id`/`.cycle_id` are copied from `decision.run_id`/
`decision.cycle_id` (already enforced by `EntryActionabilityEngine.
_validate_binding`, which requires `eq.run_id == decision.run_id` and
`eq.cycle_id == decision.cycle_id`). Since a future integration would
supply the exact same-cycle `decision` object (§10), these values are
already fully determined with zero ambiguity — **no new run/cycle
identity generation is needed or appropriate; `EntryActionabilityEngine`
correctly has no such capability today and should not gain one.**

---

## 15. `evaluated_at` source — reuse the `persistence_clock` precedent

`OwnerValidationPipeline` already has exactly the right shape of
precedent: an injectable wall-clock callable
(`persistence_clock: Callable[[], datetime] | None`, defaulting to
`lambda: datetime.now(tz=timezone.utc)`), deliberately independent of
market-time `ctx.as_of`, never a bare `datetime.now()` call inside a
stage or an engine. A future integration has two source-consistent
options — **both legitimate, neither decided here**:

- reuse the exact same `self._persistence_clock()` callable for both
  `evaluated_at` (engine input) and `persisted_at` (repository input),
  since both are wall-clock write/evaluation instants and no source
  evidence requires them to differ; or
- inject a second, separately-named clock (e.g. an `evaluation_clock`)
  for clean semantic separation, mirroring `persistence_clock`'s own
  shape exactly.

Either way, `evaluated_at` must be **explicit and timezone-aware**,
**never hidden inside the engine** (already enforced —
`EntryActionabilityEngine.evaluate` requires it as an explicit parameter
and validates `.tzinfo is not None`). No new clock *abstraction* is
required; the existing `persistence_clock` pattern already covers this
need.

---

## 16. Methodology/config snapshot — recommend `policy=None`

`EntryActionabilityPolicy` (post-ID-7C.1) carries only
`config_snapshot_id: str | None`, which is **never read anywhere** in
`EntryActionabilityEngine` — not by `evaluate()`, not by `_emit` (ID-7C.1
removed the last read of `policy` from `_emit`'s call sites). Passing
`policy=None` (the default) is therefore behaviorally **identical** to
constructing any `EntryActionabilityPolicy` instance today. **Recommendation
for a future integration: call `evaluate(..., policy=None)` — i.e. omit
the parameter — rather than instantiate meaningless configuration
plumbing.** No new `config/entry_actionability.json` (or similar) file is
needed or justified for V0; no real current setting exists that would
populate one.

---

## 17. ID-7D classification

**Classification: A — ID-7D IS UNNECESSARY / HISTORICALLY SUPERSEDED.**

**Evidence supporting this classification:**

1. ID-7D's entire originally-proposed scope ("persistence, append-only,
   Decision+EntryQualification-bound identity") was fully absorbed into,
   and completed under, ID-7A — schema v18, the `entry_actionabilities`
   table, and the complete append-only repository contract are already
   built, tested, and Owner-approved/closed (§3).
2. The one genuine architectural question this discovery had to answer
   on its merits — "is there a real, reusable composition boundary that
   should exist as its own milestone before workflow wiring?" — is
   answered **no** by direct architectural precedent: ID-6D (the closest
   and only real precedent for wiring a pure evidence-consuming engine
   into the canonical runtime) did **not** introduce a separate
   composition-layer milestone between `EntryQualificationEngine`
   (ID-6B.2) and its own workflow wiring (ID-6D) — evidence composition
   (`ctx.get(...)` reads plus one small pure helper,
   `resolve_evidence_finality`) was inlined directly into the single new
   `entry_qualification_stage` function (§5).
3. The one real integration gap this discovery found — deriving
   `session_vwap_as_of` from the already-fetched, already-completed-
   filtered M5 candle series, and publishing the selected candle into
   `WorkflowContext` (§7) — is a small, single-call-site, mechanical
   detail with exactly the same shape and scale as `entry_qualification_stage`'s
   own inline `resolve_evidence_finality(decision, session_context)` call.
   It is not reusable outside a single future stage, and it is not
   complex enough to warrant independent unit-testing separate from that
   stage — the same standard ID-6D itself was held to.
4. Every other ID-7C input (`decision`, `entry_qualification`, OR15,
   `run_id`/`cycle_id`) is **already exactly coherent and directly
   available in the canonical `WorkflowContext` with zero adaptation**
   (§§5, 9, 10, 14).

**Recommendation: formally retire ID-7D** (in the sense of "no separate
implementation milestone is required"), and proceed next — once
separately authorized — to **ID-7E**, whose own design is responsible
for the modest, single-stage-sized composition work this discovery
identified (documented as explicit ID-7E preconditions in §19 below,
not implemented here).

**Outcome B (a narrow composition contract as its own milestone) was
considered and rejected** on the concrete grounds in point 2-3 above —
not merely deemed unnecessary in the abstract. **Outcome C was not
selected**: no source evidence was found for any other missing layer
between ID-7C and ID-7E.

---

## 18. What ID-7D explicitly must not do (now moot, recorded for completeness)

Since ID-7D is not being separately implemented, this section records —
for historical auditability only — what would have been out of scope had
ID-7D been redefined as a composition contract: no new methodology, no
schema change (schema v18 remains final for this artifact), no new
repository method, no workflow-stage creation, no production rows, no
provider calls, no currentness composition. All of these constraints are
satisfied trivially by not implementing anything.

---

## 19. ID-7E authorization preconditions — exact checklist

All of the following are **already true today**, proven by this
discovery, and require no new implementation before ID-7E design can
begin:

- [x] Exact same-cycle `Decision` available (§5, §10) — via the closure
      pattern `entry_qualification_stage` already uses, or an equivalent
      `ctx`-published key a future stage introduces.
- [x] Exact bound `EntryQualification` available (§6) — already published
      to `ctx["entry_qualification"]` by the existing `entry_qualification`
      stage.
- [x] Completed M5 candle obtainable without provider access (§7) — the
      exact candle already exists in `ind_stage`'s local scope; needs
      only to be published to `ctx` or re-derived via one more bounded
      repository read (no new provider call either way).
- [x] VWAP price available (§6, §7) — already published as
      `ctx["vwap"]` (an `IndicatorResult` carrying the raw price in
      `.values["vwap"]`).
- [ ] **Coherent VWAP `as_of` available** (§7) — **the one real gap**:
      must be derived from the selected completed M5 candle's own
      `ts_open + 5 minutes`, not from `ctx.as_of`/`IndicatorResult.ts`.
      This is ID-7E's own design/implementation responsibility, not a
      precondition blocking ID-7E's authorization.
- [x] Optional coherent OR15 available (§9) — already published as
      `ctx["intraday_signal_set"].or15`, already exactly coherent.
- [x] `evaluated_at` source identified (§15) — reuse or mirror the
      existing `persistence_clock` injectable-wall-clock pattern.
- [x] Repository save contract sufficient (§13) — `save_entry_actionability`
      already exists and needs no companion "get"/"latest" call in the
      write path.
- [x] `WorkflowContext` storage-key design precedent known (§5) — mirror
      `entry_qualification_stage`'s own shape: one new stage, its own
      inline composition, one new `produces` key.
- [x] Stage-dependency shape known (§5) — a future `entry_actionability`
      stage would `depends_on=("entry_qualification",)` at minimum (which
      itself transitively depends on `"decision"`/`"intraday_analytics"`),
      declared last so it cannot perturb existing stage order — exactly
      mirroring how `entry_qualification` itself was added last after
      ID-6D's own 10 pre-existing stages.
- [x] Failure semantics known (§12) — existing `WorkflowEngine`/
      `DailyMarketScanner` isolation is already correct and sufficient;
      no new failure policy needed.
- [x] Currentness kept out of the write path (§11) — confirmed
      structurally true of the current architecture, not merely asserted.

**None of these items requires any code change to be made now.** The
single unchecked item (`session_vwap_as_of` derivation) is explicitly an
ID-7E implementation task, not a blocker to authorizing ID-7E's design
phase.

---

## 20. ID-7F future preconditions

Not designed here. For future replay/shadow comparison (mirroring ID-6E's
own `id6e_replay_shadow_validation.py` pattern), ID-7F will need — once
ID-7E has produced real persisted rows — access to, at minimum: the exact
bound `Decision`, the exact bound `EntryQualification`, the persisted
`EntryActionability` itself (state, reason codes, all four V0 value
objects when `ACTIONABLE`), `evidence_as_of`/`entry_actionability_as_of`/
`evaluated_at`, and the methodology version string — **all of which the
existing ID-7A schema/repository contract already persists and exposes**
via `list_entry_actionabilities_for_instrument_session`/
`get_entry_actionability`.

**Correction (2026-09-05, ID-7E authorization, owner-flagged):** the
paragraph above originally also named `persisted_at` among the fields
"already exposed." That overstates the real ID-7A behavior — `persisted_at`
IS durably stored (an explicit column on the `entry_actionabilities`
table, written by `save_entry_actionability`), but it is write/audit
metadata only: `repository.py`'s own `_ENTRY_ACTIONABILITY_COLUMNS`
SELECT list (reused by `get_entry_actionability`,
`latest_entry_actionability_for_entry_qualification`,
`latest_entry_actionability_for_instrument_session`, and
`list_entry_actionabilities_for_instrument_session`) does not include
it, and it is not a field on the `EntryActionability` domain object
`row_to_entry_actionability` deserializes — so none of the normal
repository read paths return it today. If ID-7F later needs
`persisted_at` as exposed replay/audit metadata (as opposed to the
market-time timestamps already returned), that is a genuine future
decision for ID-7F to make explicitly, not something ID-7A/ID-7E already
provide. ID-7E does not change repository/domain/schema behavior to
address this — documentation correction only.

---

## 21. Documentation reconciliation required

The following documents carry the stale "ID-7D = persistence" statement
and should be corrected **only if/when the owner confirms the
Classification-A outcome above** (this discovery does not itself edit
frozen historical documents beyond the active tracking docs listed in
§22, per the milestone's own "preserve historical auditability" instruction):

- `docs/adr/ADR-015-intraday-actionability-architecture.md:461` — should
  eventually read something like *"ID-7C (engine), ID-7E (workflow
  wiring), and ID-7F (replay/shadow) remain unauthorized; ID-7D's
  originally-planned persistence scope was absorbed into ID-7A (see
  `docs/research/ID-7D-NEXT-LAYER-DISCOVERY-CONTRACT-RECONCILIATION.md`)."*
- `docs/research/ID-7A0-INTRADAY-ACTIONABILITY-ARCHITECTURE.md:22` —
  same correction, in context.

`docs/research/ID-7-INTRADAY-ENTRY-TRADEPLAN-DISCOVERY.md` §35 needs **no
correction** — it is an accurate historical record of what was proposed
*at the time it was written*, before ID-7A's actual scope was decided;
rewriting it would destroy exactly the auditability the owner's
instructions ask to preserve.

---

## 22. Active tracking-doc updates made by this milestone

`docs/MILESTONES.md`, `docs/ATHENA-ID-TRACK-HANDOFF.md`,
`ATHENA_BRIEFING.md`, `IMPLEMENTATION_SUMMARY.md` updated to record:
ID-7C.2/ID-7C.1/ID-7C all Owner-approved/closed 2026-09-05; ID-7D
discovery complete, classified Outcome A (historically superseded, no
separate implementation), ready for Owner scope decision; ID-7D itself
NOT marked Owner-approved (a classification decision belongs to the
owner, not this discovery); ID-7E/ID-7F remain NOT STARTED, NOT
AUTHORIZED.
